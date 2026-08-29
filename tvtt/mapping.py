"""The mapping engine: turning Voynich glyphs into letters, quickly.

A *mapping* says what each glyph becomes.  Rules can be plain
(``"f" -> "a"``), positional (``"9" -> "s"`` only at the end of a word),
occurrence-based (``"o" -> "u"`` the second time it appears in a word), and can
cover glyph groups (``"4o" -> "d"``) or expand one glyph into several letters
(``"9" -> "con"``).

How it stays fast
-----------------
Applying a mapping naively means a Python function call per character, which is
slow and gets slower every time a solver tries another candidate.  Instead the
engine splits the work in two:

1. **Segmentation** depends only on which glyph groups exist, not on what they
   turn into.  Each distinct word is segmented once into a tuple of small
   integers - one per glyph, already encoding "is this glyph word-initial,
   word-final, and which occurrence is it".  Segmentation is cached per word
   type, and the manuscript only has about 8,700 word types.

2. **Application** is then a flat table lookup: ``"".join(table[i] for i in
   plan)``.  Changing one rule rebuilds 20 table entries and only re-maps the
   words that contain that glyph, which is what makes the hill-climbing solver
   practical in pure Python.

Rule precedence
---------------
When several rules could apply, the order is configurable and defaults to::

    word-initial  >  word-final  >  Nth occurrence  >  plain

``tvtt mapping conflicts`` prints every place where rules overlap and shows
which one wins.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .errors import MappingError
from .ivtff import describe_glyph
from .paths import display_path
from .util import read_text, stable_hash

# --------------------------------------------------------------------------
# Slots and contexts
# --------------------------------------------------------------------------

SLOT_PLAIN = 0
SLOT_INITIAL = 1
SLOT_FINAL = 2
SLOT_OCC1 = 3
SLOT_OCC2 = 4
SLOT_OCC3 = 5
SLOT_OCC4 = 6
N_SLOTS = 7

SLOT_NAMES = {
    SLOT_PLAIN: "plain",
    SLOT_INITIAL: "initial",
    SLOT_FINAL: "final",
    SLOT_OCC1: "occurrence1",
    SLOT_OCC2: "occurrence2",
    SLOT_OCC3: "occurrence3",
    SLOT_OCC4: "occurrence4",
}
SLOT_BY_NAME = {v: k for k, v in SLOT_NAMES.items()}
OCCURRENCE_SLOTS = (SLOT_OCC1, SLOT_OCC2, SLOT_OCC3, SLOT_OCC4)

#: 2 (initial?) x 2 (final?) x 5 (occurrence 1-4 or later) = 20 contexts.
N_CONTEXTS = 20

DEFAULT_PRECEDENCE = ("initial", "final", "occurrence", "plain")
PRECEDENCE_TERMS = ("initial", "final", "occurrence", "plain")


def context_index(at_start: bool, at_end: bool, occurrence: int) -> int:
    """Pack a glyph's word context into one small integer."""
    occ = occurrence if 1 <= occurrence <= 4 else 0
    return occ + (5 if at_end else 0) + (10 if at_start else 0)


def unpack_context(ctx: int) -> tuple:
    return (ctx >= 10, (ctx % 10) >= 5, ctx % 5)


# --------------------------------------------------------------------------
# Markers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Markers:
    """The suffix characters that turn a plain rule into a positional one."""

    start_of_word: str = "@"
    end_of_word: str = "/"
    occurrence: tuple = ("'", '"', ":", ";")

    def all(self) -> tuple:
        return (self.start_of_word, self.end_of_word) + tuple(self.occurrence)

    def slot_for(self, marker: str) -> int:
        if marker == self.start_of_word:
            return SLOT_INITIAL
        if marker == self.end_of_word:
            return SLOT_FINAL
        if marker in self.occurrence:
            return OCCURRENCE_SLOTS[self.occurrence.index(marker)]
        raise MappingError("unknown marker %r" % marker)


DEFAULT_MARKERS = Markers()


# --------------------------------------------------------------------------
# Mapping documents
# --------------------------------------------------------------------------


@dataclass
class Mapping:
    """A mapping as authored: glyph -> {slot name: replacement}."""

    rules: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    path: str = ""

    # -- construction ----------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict, markers: Markers = DEFAULT_MARKERS, path: str = "") -> Mapping:
        """Read either the structured or the legacy flat mapping format.

        The two formats differ in how a bare string is read.  In the legacy
        flat file a trailing marker character is part of the notation, so
        ``"a@"`` means "a, at the start of a word".  In the structured format
        positions have their own named keys, so a string is taken literally -
        which matters for glyphs whose own character happens to be a marker,
        such as the apostrophe in EVA.
        """
        structured = isinstance(data, dict) and "rules" in data
        meta = dict(data.get("meta", {})) if isinstance(data, dict) else {}
        raw_rules = data.get("rules") if structured else data
        if not isinstance(raw_rules, dict):
            raise MappingError(
                "a mapping file must be a JSON object",
                hint='Expected {"glyph": "letter", ...} or {"meta": {...}, "rules": {...}}.',
            )

        rules: dict = {}
        for glyph, value in raw_rules.items():
            if glyph in ("meta", "$schema"):
                continue
            if isinstance(value, dict):
                slots = {}
                for slot_name, replacement in value.items():
                    if slot_name not in SLOT_BY_NAME:
                        raise MappingError(
                            "rule for %r uses unknown position %r" % (glyph, slot_name),
                            hint="Valid positions: " + ", ".join(SLOT_BY_NAME),
                        )
                    slots[SLOT_BY_NAME[slot_name]] = str(replacement)
                rules.setdefault(glyph, {}).update(slots)
            elif isinstance(value, list):
                for item in value:
                    slot, text = _parse_legacy_value(str(item), markers)
                    rules.setdefault(glyph, {})[slot] = text
            elif structured:
                rules.setdefault(glyph, {})[SLOT_PLAIN] = str(value)
            else:
                slot, text = _parse_legacy_value(str(value), markers)
                rules.setdefault(glyph, {})[slot] = text
        return cls(rules=rules, meta=meta, path=path)

    @classmethod
    def load(cls, path, markers: Markers = DEFAULT_MARKERS) -> Mapping:
        p = Path(path)
        if not p.exists():
            raise MappingError(
                "mapping file not found: %s" % display_path(p),
                hint="Create one with 'tvtt mapping init', or point config.json at an existing file.",
            )
        text = read_text(p)

        if looks_like_v1_text(text):
            mapping = parse_v1_text(text, markers)
            mapping.path = str(p)
            mapping.meta.setdefault("name", p.stem)
            mapping.meta.setdefault("notes", "Read from a TVTT 1.x mapping list.")
            return mapping

        try:
            data = json.loads(_strip_trailing_commas(text))
        except json.JSONDecodeError as exc:
            raise MappingError(
                "%s is not valid JSON (line %d, column %d): %s" % (p, exc.lineno, exc.colno, exc.msg),
                hint='Every entry needs quotes and a comma except the last one: "f": "a",',
            ) from exc
        return cls.from_dict(data, markers, path=str(p))

    # -- serialisation ---------------------------------------------------
    def to_dict(self, structured: bool = True, markers: Markers = DEFAULT_MARKERS) -> dict:
        if not structured:
            flat = {}
            for glyph, slots in self.rules.items():
                if list(slots) == [SLOT_PLAIN]:
                    flat[glyph] = slots[SLOT_PLAIN]
                else:
                    flat[glyph] = [_render_legacy_value(slot, text, markers) for slot, text in sorted(slots.items())]
            return flat
        rules = {}
        for glyph in sorted(self.rules):
            slots = self.rules[glyph]
            if list(slots) == [SLOT_PLAIN]:
                rules[glyph] = slots[SLOT_PLAIN]
            else:
                rules[glyph] = {SLOT_NAMES[s]: t for s, t in sorted(slots.items())}
        return {"meta": self.meta, "rules": rules}

    def save(self, path, structured: bool = True, markers: Markers = DEFAULT_MARKERS) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(structured, markers), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return p

    # -- inspection ------------------------------------------------------
    def glyphs(self) -> list:
        return sorted(self.rules)

    def plain(self) -> dict:
        return {g: s[SLOT_PLAIN] for g, s in self.rules.items() if SLOT_PLAIN in s}

    def rule_count(self) -> int:
        return sum(len(s) for s in self.rules.values())

    def complexity(self) -> int:
        """Rules beyond one plain rule per glyph.

        This is the number the overfitting warning watches: every extra
        positional or occurrence rule is another free parameter.
        """
        return sum(max(0, len(s) - 1) for s in self.rules.values())

    def signature(self) -> str:
        return stable_hash({g: {SLOT_NAMES[s]: t for s, t in sorted(v.items())} for g, v in sorted(self.rules.items())})

    def copy(self) -> Mapping:
        return Mapping(rules={g: dict(s) for g, s in self.rules.items()}, meta=dict(self.meta), path=self.path)

    def set(self, glyph: str, text: str, slot: int = SLOT_PLAIN) -> None:
        self.rules.setdefault(glyph, {})[slot] = text

    def is_identity(self) -> bool:
        return all(list(s) == [SLOT_PLAIN] and s[SLOT_PLAIN] == g for g, s in self.rules.items())


def _parse_legacy_value(value: str, markers: Markers) -> tuple:
    """Split ``"a@"`` into ``(SLOT_INITIAL, "a")`` using the marker suffixes.

    A value that is nothing but a marker - ``"'"`` say, which is a real EVA
    glyph - is kept as the replacement rather than being read as an empty
    occurrence rule.
    """
    marker_chars = set(markers.all())
    slot = SLOT_PLAIN
    text = value
    while len(text) > 1 and text[-1] in marker_chars:
        slot = markers.slot_for(text[-1])
        text = text[:-1]
    return slot, text


def _render_legacy_value(slot: int, text: str, markers: Markers) -> str:
    if slot == SLOT_PLAIN:
        return text
    if slot == SLOT_INITIAL:
        return text + markers.start_of_word
    if slot == SLOT_FINAL:
        return text + markers.end_of_word
    return text + markers.occurrence[OCCURRENCE_SLOTS.index(slot)]


# --------------------------------------------------------------------------
# The TVTT 1.x mapping list
# --------------------------------------------------------------------------
#
# Before version 1.8 a mapping was a plain text file, one rule per line:
#
#     0=f~f          glyph f becomes f
#     53=9~con       glyph 9 becomes the three letters "con"
#     105=4o~d@      the pair "4o" becomes d, but only at the start of a word
#
# The number is the position the glyph happened to occupy in the alphabet the
# old tool had scanned. Nothing referred to it, so it is read and discarded.
#
# The input must be captured non-greedily but with at least one character, or
# lines like ``18=@~@`` and ``26='~'`` - where the glyph *is* a marker
# character - would parse with an empty glyph.
_V1_LINE = re.compile(r"^\s*(\d+)\s*=(.+?)~(.*?)\s*$")

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def looks_like_v1_text(text: str) -> bool:
    """True for a version 1.x mapping list rather than a JSON mapping."""
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        return False
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return False
    return sum(1 for line in lines if _V1_LINE.match(line)) >= max(1, len(lines) // 2)


def parse_v1_text(text: str, markers: Markers = DEFAULT_MARKERS) -> Mapping:
    """Read a version 1.x mapping list into a :class:`Mapping`."""
    rules: dict = {}
    bad: list = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _V1_LINE.match(line)
        if not match:
            bad.append((number, line.strip()))
            continue
        glyph = match.group(2)
        slot, replacement = _parse_legacy_value(match.group(3), markers)
        rules.setdefault(glyph, {})[slot] = replacement

    if not rules:
        raise MappingError(
            "no rules found in this mapping list",
            hint="A version 1 mapping has one rule per line, like: 0=f~f",
        )
    if bad:
        first = bad[0]
        raise MappingError(
            "line %d of this mapping list is not a rule: %r" % (first[0], first[1]),
            hint="Each line looks like number=glyph~letters, for example 105=4o~d@. "
            "Blank lines and lines starting with # are ignored.",
        )
    return Mapping(rules=rules)


def _strip_trailing_commas(text: str) -> str:
    """Tolerate the trailing comma the old ``mapping.py`` used to emit."""
    return _TRAILING_COMMA.sub(r"\1", text)


# --------------------------------------------------------------------------
# The compiled engine
# --------------------------------------------------------------------------

UNMAPPED_MODES = ("keep", "drop", "placeholder")


class MappingEngine:
    """A mapping compiled into flat tables, plus a per-word segmentation cache."""

    __slots__ = (
        "mapping",
        "markers",
        "precedence",
        "unmapped",
        "placeholder",
        "keys",
        "key_index",
        "slot_table",
        "resolved",
        "lengths_by_first",
        "max_key_len",
        "_plans",
        "_word_cache",
        "_keys_using",
    )

    def __init__(
        self,
        mapping: Mapping,
        glyphs: Iterable = (),
        markers: Markers = DEFAULT_MARKERS,
        precedence: Sequence = DEFAULT_PRECEDENCE,
        unmapped: str = "keep",
        placeholder: str = "?",
    ) -> None:
        if unmapped not in UNMAPPED_MODES:
            raise MappingError(
                "mapping.unmapped=%r is not recognised" % unmapped,
                hint="Allowed values: " + ", ".join(UNMAPPED_MODES),
            )
        for term in precedence:
            if term not in PRECEDENCE_TERMS:
                raise MappingError(
                    "mapping.precedence contains unknown term %r" % term,
                    hint="Allowed terms: " + ", ".join(PRECEDENCE_TERMS),
                )
        self.mapping = mapping
        self.markers = markers
        self.precedence = tuple(precedence)
        self.unmapped = unmapped
        self.placeholder = placeholder

        keys = set(mapping.rules)
        keys.update(g for g in glyphs if g not in (".", ",", "\n"))
        self.keys = sorted(keys, key=lambda k: (-len(k), k))
        self.key_index = {k: i for i, k in enumerate(self.keys)}
        self.max_key_len = max((len(k) for k in self.keys), default=1)

        by_first = defaultdict(set)
        for key in self.keys:
            by_first[key[0]].add(len(key))
        self.lengths_by_first = {ch: tuple(sorted(sizes, reverse=True)) for ch, sizes in by_first.items()}

        self.slot_table = [None] * (len(self.keys) * N_SLOTS)
        for glyph, slots in mapping.rules.items():
            idx = self.key_index[glyph]
            for slot, text in slots.items():
                self.slot_table[idx * N_SLOTS + slot] = text

        self.resolved = [""] * (len(self.keys) * N_CONTEXTS)
        for idx in range(len(self.keys)):
            self._rebuild_key(idx)

        self._plans: dict = {}
        self._word_cache: dict = {}
        self._keys_using: dict = {}

    # -- table construction ---------------------------------------------
    def _fallback(self, key: str) -> str:
        if self.unmapped == "drop":
            return ""
        if self.unmapped == "placeholder":
            return self.placeholder
        return key

    def _rebuild_key(self, idx: int) -> None:
        base = idx * N_SLOTS
        table = self.slot_table
        key = self.keys[idx]
        fallback = table[base + SLOT_PLAIN]
        if fallback is None:
            fallback = self._fallback(key)
        for ctx in range(N_CONTEXTS):
            at_start, at_end, occ = unpack_context(ctx)
            value = None
            for term in self.precedence:
                if term == "initial" and at_start:
                    value = table[base + SLOT_INITIAL]
                elif term == "final" and at_end:
                    value = table[base + SLOT_FINAL]
                elif term == "occurrence" and 1 <= occ <= 4:
                    value = table[base + OCCURRENCE_SLOTS[occ - 1]]
                elif term == "plain":
                    value = table[base + SLOT_PLAIN]
                if value is not None:
                    break
            self.resolved[idx * N_CONTEXTS + ctx] = fallback if value is None else value

    # -- mutation (used by the solver) -----------------------------------
    def set_rule(self, glyph: str, text: str, slot: int = SLOT_PLAIN) -> None:
        """Change one rule and refresh only what depends on it."""
        idx = self.key_index.get(glyph)
        if idx is None:
            raise MappingError("glyph %r is not part of this alphabet" % glyph)
        self.slot_table[idx * N_SLOTS + slot] = text
        self.mapping.rules.setdefault(glyph, {})[slot] = text
        self._rebuild_key(idx)
        self._invalidate_key(idx)

    def _invalidate_key(self, idx: int) -> None:
        affected = self._keys_using.get(idx)
        if affected is None:
            self._word_cache.clear()
            return
        for word in affected:
            self._word_cache.pop(word, None)

    # -- segmentation ----------------------------------------------------
    def segment(self, word: str) -> tuple:
        """Split a word into glyph groups, tagged with their word context.

        The result is a tuple of flat indices into :attr:`resolved`; it depends
        only on the alphabet, so it is computed once per distinct word.
        """
        plan = self._plans.get(word)
        if plan is not None:
            return plan

        key_index = self.key_index
        lengths_by_first = self.lengths_by_first
        n = len(word)
        counts: dict = {}
        pieces = []
        i = 0
        while i < n:
            ch = word[i]
            match_len = 1
            idx = -1
            for length in lengths_by_first.get(ch, (1,)):
                if i + length > n:
                    continue
                found = key_index.get(word[i : i + length])
                if found is not None:
                    idx = found
                    match_len = length
                    break
            if idx < 0:
                idx = key_index.get(ch, -1)
                if idx < 0:
                    i += 1
                    continue
            occ = counts.get(idx, 0) + 1
            counts[idx] = occ
            at_start = i == 0
            at_end = i + match_len >= n
            pieces.append(idx * N_CONTEXTS + context_index(at_start, at_end, occ))
            i += match_len

        plan = tuple(pieces)
        self._plans[word] = plan
        return plan

    def keys_in(self, word: str) -> set:
        return {p // N_CONTEXTS for p in self.segment(word)}

    def register_vocabulary(self, words: Iterable) -> None:
        """Pre-segment a vocabulary and build the glyph -> words index.

        Doing this once makes later rule changes cheap: only the words that
        actually contain the changed glyph are re-mapped.
        """
        using: dict = {}
        for word in words:
            for idx in self.keys_in(word):
                using.setdefault(idx, set()).add(word)
        self._keys_using = using

    # -- application -----------------------------------------------------
    def map_word(self, word: str) -> str:
        cached = self._word_cache.get(word)
        if cached is not None:
            return cached
        resolved = self.resolved
        out = "".join([resolved[p] for p in self.segment(word)])
        self._word_cache[word] = out
        return out

    def map_words(self, words: Iterable) -> list:
        cache = self._word_cache
        out = []
        append = out.append
        for word in words:
            value = cache.get(word)
            append(self.map_word(word) if value is None else value)
        return out

    def map_line(self, text: str, separator: str = " ", uncertain: str = " ") -> str:
        """Map one transcription line, keeping certain/uncertain space marks."""
        out = []
        token = []
        for ch in text:
            if ch == ".":
                out.append(self.map_word("".join(token)))
                out.append(separator)
                token = []
            elif ch == ",":
                out.append(self.map_word("".join(token)))
                out.append(uncertain)
                token = []
            else:
                token.append(ch)
        out.append(self.map_word("".join(token)))
        return "".join(out)

    # -- diagnostics -----------------------------------------------------
    def collisions(self) -> dict:
        """Replacements produced by more than one glyph (mapping not injective)."""
        buckets: dict = defaultdict(list)
        for glyph, slots in self.mapping.rules.items():
            for slot, text in slots.items():
                buckets[text].append((glyph, SLOT_NAMES[slot]))
        return {text: sources for text, sources in buckets.items() if len(sources) > 1}

    def unmapped_glyphs(self) -> list:
        return [k for k in self.keys if k not in self.mapping.rules]

    def conflicts(self) -> list:
        """Every place where two rules could both apply, and which one wins."""
        out = []
        for glyph, slots in sorted(self.mapping.rules.items()):
            if len(slots) > 1:
                order = [t for t in self.precedence if _slot_term(t) & set(slots)]
                winner = _winning_slot(slots, self.precedence)
                out.append(
                    {
                        "glyph": describe_glyph(glyph) if len(glyph) == 1 else glyph,
                        "kind": "position",
                        "rules": {SLOT_NAMES[s]: t for s, t in sorted(slots.items())},
                        "winner": SLOT_NAMES[winner],
                        "explanation": (
                            "For a glyph that is both word-initial and word-final the order %s decides; "
                            "%s wins." % (" > ".join(order or self.precedence), SLOT_NAMES[winner])
                        ),
                    }
                )
        # Overlapping glyph groups: "4" and "4o" both defined.
        keys = set(self.mapping.rules)
        for key in sorted(keys):
            longer = [k for k in keys if k != key and k.startswith(key)]
            if longer:
                out.append(
                    {
                        "glyph": key,
                        "kind": "group",
                        "rules": dict.fromkeys([key] + sorted(longer), "defined"),
                        "winner": max(longer + [key], key=len),
                        "explanation": (
                            "%s is a prefix of %s. The longest group always matches first, "
                            "so %s only applies where the longer group does not."
                            % (key, ", ".join(sorted(longer)), key)
                        ),
                    }
                )
        return out

    def signature(self) -> str:
        return stable_hash([self.mapping.signature(), self.precedence, self.unmapped, self.placeholder])


def _slot_term(term: str) -> set:
    if term == "initial":
        return {SLOT_INITIAL}
    if term == "final":
        return {SLOT_FINAL}
    if term == "occurrence":
        return set(OCCURRENCE_SLOTS)
    return {SLOT_PLAIN}


def _winning_slot(slots: dict, precedence: Sequence) -> int:
    for term in precedence:
        candidates = _slot_term(term) & set(slots)
        if candidates:
            return min(candidates)
    return SLOT_PLAIN


# --------------------------------------------------------------------------
# Round-trip validation
# --------------------------------------------------------------------------


@dataclass
class RoundTripReport:
    """Whether a mapping can be undone, and where it loses information."""

    injective: bool
    collisions: dict
    unmapped: list
    empty_rules: list
    expanding: list
    coverage: float
    checked_words: int
    reversible_words: int

    def summary(self) -> str:
        state = "injective (reversible)" if self.injective else "NOT injective"
        return (
            "Mapping is %s. %d collisions, %d unmapped glyphs, "
            "%d/%d sample words round-tripped (%.1f%% glyph coverage)."
            % (
                state,
                len(self.collisions),
                len(self.unmapped),
                self.reversible_words,
                self.checked_words,
                self.coverage * 100,
            )
        )


def round_trip_check(engine: MappingEngine, words: Sequence = ()) -> RoundTripReport:
    """Check that the mapping is injective and can be reversed.

    A mapping that sends two different glyphs to the same letter throws away
    information: no matter how good the output looks, you can never recover the
    original text from it, and any "decipherment" is partly your own invention.
    """
    collisions = engine.collisions()
    unmapped = engine.unmapped_glyphs()
    empty = [g for g, slots in engine.mapping.rules.items() if any(t == "" for t in slots.values())]
    expanding = [g for g, slots in engine.mapping.rules.items() if any(len(t) > 1 for t in slots.values())]

    inverse: dict = {}
    ambiguous = False
    for glyph, slots in engine.mapping.rules.items():
        for text in slots.values():
            if not text:
                # A glyph mapped to nothing cannot be inverted at all.
                continue
            if text in inverse and inverse[text] != glyph:
                ambiguous = True
            inverse.setdefault(text, glyph)

    lengths = sorted({len(k) for k in inverse if k}, reverse=True) or [1]
    checked = list(words)[:4000]
    reversible = 0
    for word in checked:
        mapped = engine.map_word(word)
        if not ambiguous and mapped and _reverse_word(mapped, inverse, lengths) == word:
            reversible += 1

    mapped_keys = sum(1 for k in engine.keys if k in engine.mapping.rules)
    coverage = mapped_keys / len(engine.keys) if engine.keys else 0.0

    return RoundTripReport(
        injective=not collisions and not ambiguous,
        collisions=collisions,
        unmapped=unmapped,
        empty_rules=empty,
        expanding=expanding,
        coverage=coverage,
        checked_words=len(checked),
        reversible_words=reversible,
    )


def _reverse_word(text: str, inverse: dict, lengths: Sequence = ()) -> str:
    """Read a mapped word back to glyphs, longest replacement first."""
    if not lengths:
        lengths = sorted({len(k) for k in inverse if k}, reverse=True) or [1]
    out = []
    i = 0
    n = len(text)
    while i < n:
        for length in lengths:
            if length <= 0:
                continue
            piece = text[i : i + length]
            if piece in inverse:
                out.append(inverse[piece])
                i += length
                break
        else:
            return ""
    return "".join(out)


# --------------------------------------------------------------------------
# Building mappings
# --------------------------------------------------------------------------

LATIN_LOWER = "abcdefghijklmnopqrstuvwxyz"


def identity_mapping(glyphs: Iterable, meta: dict = None) -> Mapping:
    """A mapping that leaves every glyph unchanged - the usual starting point."""
    return Mapping(
        rules={g: {SLOT_PLAIN: g} for g in sorted(set(glyphs))},
        meta=meta or {"name": "identity", "notes": "Every glyph maps to itself."},
    )


def random_mapping(
    glyphs: Sequence,
    alphabet: str = LATIN_LOWER,
    rng: random.Random = None,
    injective: bool = False,
    meta: dict = None,
) -> Mapping:
    """A random glyph -> letter mapping, used for control runs.

    Scoring random mappings is the cheapest defence against fooling yourself:
    if your carefully designed mapping scores no better than the middle of a
    random distribution, the score is measuring the manuscript, not your idea.
    """
    rng = rng or random.Random(0)
    glyph_list = list(glyphs)
    if injective and len(alphabet) >= len(glyph_list):
        letters = rng.sample(list(alphabet), len(glyph_list))
    else:
        letters = [rng.choice(alphabet) for _ in glyph_list]
    return Mapping(
        rules={g: {SLOT_PLAIN: letters[i]} for i, g in enumerate(glyph_list)},
        meta=meta or {"name": "random", "notes": "Randomly generated control mapping."},
    )


def frequency_matched_mapping(
    glyph_counts: Counter,
    letter_counts: Sequence,
    meta: dict = None,
) -> Mapping:
    """Map the commonest glyph to the commonest letter, and so on.

    This is the classic first guess for a simple substitution cipher, and a
    useful starting point for the solver.
    """
    glyphs = [g for g, _ in glyph_counts.most_common()]
    letters = [letter for letter, _ in letter_counts]
    rules = {}
    for i, glyph in enumerate(glyphs):
        rules[glyph] = {SLOT_PLAIN: letters[i] if i < len(letters) else ""}
    return Mapping(rules=rules, meta=meta or {"name": "frequency-matched"})


def mapping_diff(left: Mapping, right: Mapping) -> list:
    """Every rule that differs between two mappings."""
    glyphs = sorted(set(left.rules) | set(right.rules))
    rows = []
    for glyph in glyphs:
        a = left.rules.get(glyph, {})
        b = right.rules.get(glyph, {})
        for slot in sorted(set(a) | set(b)):
            before = a.get(slot)
            after = b.get(slot)
            if before != after:
                rows.append(
                    {
                        "glyph": describe_glyph(glyph) if len(glyph) == 1 else glyph,
                        "position": SLOT_NAMES[slot],
                        "before": before,
                        "after": after,
                        "change": "added" if before is None else ("removed" if after is None else "changed"),
                    }
                )
    return rows
