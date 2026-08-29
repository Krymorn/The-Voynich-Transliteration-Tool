"""Selecting the part of the manuscript you actually want to study.

A :class:`Corpus` is a parsed transcription plus folio metadata.  Calling
:meth:`Corpus.select` with a :class:`Selection` returns a new corpus holding
only the lines that match - "Currier B paragraph text written by scribe 2",
"every zodiac label", "the first line of every paragraph".

Why this matters
----------------
Voynichese behaves differently depending on where it sits on the page.  Labels
are shorter and use a different vocabulary than running text.  The first word
of a line is drawn from a restricted set (the "line as a functional unit", or
LAAFU, effect).  Currier A and Currier B have measurably different statistics.
A mapping that looks convincing over the whole manuscript often falls apart the
moment you look at one section, which is exactly what you want to find out.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from .errors import ConfigError
from .folios import SECTION_NAMES, FolioTable, load_folios, parse_folio_range
from .ivtff import (
    LOCUS_TYPE_NAMES,
    ParseOptions,
    Transliteration,
    normalise_folio,
    parse_file,
)
from .paths import transcription_file
from .util import sha256_file

# --------------------------------------------------------------------------
# Known transcriptions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TranscriptionSpec:
    """One published transliteration of the manuscript."""

    key: str
    title: str
    filename: str
    alphabet: str
    transcriber: str
    description: str
    url: str = ""


TRANSCRIPTIONS: dict = {
    spec.key: spec
    for spec in (
        TranscriptionSpec(
            "zl",
            "Zandbergen-Landini (ZL)",
            "ZL3b-n.txt",
            "Eva-",
            "Rene Zandbergen and Gabriel Landini",
            "The most complete EVA transliteration: all 5374 loci, extended EVA glyphs, "
            "regularly corrected. The recommended default.",
            "https://www.voynich.nu/data/ZL3b-n.txt",
        ),
        TranscriptionSpec(
            "v101",
            "v101 (Glen Claston), IVTFF form",
            "GC2a-n.txt",
            "v101",
            "Glen Claston",
            "The v101 alphabet, which distinguishes far more glyph shapes than EVA. "
            "This is the IVTFF conversion, so it carries locus and page metadata.",
            "https://www.voynich.nu/data/GC2a-n.txt",
        ),
        TranscriptionSpec(
            "v101_native",
            "v101 (original layout)",
            "voyn_101.txt",
            "v101",
            "Glen Claston",
            "The original, unmodified v101 file with high-ASCII bytes and its own "
            "locus ordering. Kept for compatibility with older work.",
            "https://www.voynich.nu/data/voyn_101.txt",
        ),
        TranscriptionSpec(
            "takahashi",
            "Takahashi (H), interlinear form",
            "IT2a-n.txt",
            "EvaT",
            "Takeshi Takahashi",
            "Takeshi Takahashi's transliteration as it appears in Jorge Stolfi's 1999 "
            "interlinear file. Basic lowercase EVA.",
            "https://www.voynich.nu/data/IT2a-n.txt",
        ),
        TranscriptionSpec(
            "voynichese",
            "Takahashi (voynichese.com edition)",
            "VT0e-n.txt",
            "EvaT",
            "Takeshi Takahashi",
            "The Takahashi text as served by voynichese.com. Differs from the interlinear "
            "edition only in how unreadable characters are marked.",
            "https://www.voynich.nu/data/VT0e-n.txt",
        ),
        TranscriptionSpec(
            "currier",
            "Currier / D'Imperio (C)",
            "CD2a-n.txt",
            "Curr",
            "Prescott Currier and Mary D'Imperio",
            "The original Currier transliteration in the Currier alphabet. Covers about "
            "half the manuscript, and is the source of the Currier A/B distinction.",
            "https://www.voynich.nu/data/CD2a-n.txt",
        ),
        TranscriptionSpec(
            "fsg",
            "FSG (Friedman First Study Group)",
            "FG2a-n.txt",
            "FSG-",
            "Friedman First Study Group",
            "The oldest machine-readable transliteration, in the FSG alphabet, from William Friedman's study group.",
            "https://www.voynich.nu/data/FG2a-n.txt",
        ),
        TranscriptionSpec(
            "reference",
            "Reference transliteration (RF, extended)",
            "RF1b-e.txt",
            "Eva-",
            "Rene Zandbergen",
            "An automatic merge of the GC and ZL transliterations, expressed in extended "
            "EVA. Useful as a tie-breaker when two transcribers disagree.",
            "https://www.voynich.nu/data/RF1b-e.txt",
        ),
        TranscriptionSpec(
            "reference_basic",
            "Reference transliteration (RF, basic)",
            "RF1b-er.txt",
            "Eva-",
            "Rene Zandbergen",
            "The same reference transliteration reduced to basic EVA, with no extended glyphs.",
            "https://www.voynich.nu/data/RF1b-er.txt",
        ),
    )
}

TRANSCRIPTION_KEYS = tuple(TRANSCRIPTIONS)

#: Older configs used these names.
LEGACY_ALIASES = {"eva": "zl", "ZL": "zl", "v121": "v101"}


def resolve_transcription(name: str) -> TranscriptionSpec:
    key = LEGACY_ALIASES.get(name, name)
    spec = TRANSCRIPTIONS.get(key)
    if spec is None:
        raise ConfigError(
            "unknown transcription %r" % name,
            hint="Available: " + ", ".join(TRANSCRIPTION_KEYS),
        )
    return spec


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

TEXT_CLASSES = ("all", "running", "labels", "circular", "radial")
LINE_MODES = ("all", "first", "last", "not_first", "single")
WORD_MODES = ("all", "first", "not_first", "last")


@dataclass(frozen=True)
class Selection:
    """Which lines of the manuscript to keep.

    Every field is a filter; leaving a field empty means "do not filter on
    this".  Filters combine with AND.
    """

    sections: tuple = ()
    folios: tuple = ()
    exclude_folios: tuple = ()
    currier: str = "any"
    scribes: tuple = ()
    currier_hands: tuple = ()
    quires: tuple = ()
    locus_types: tuple = ()
    locus_kinds: tuple = ()
    text_class: str = "all"
    lines: str = "all"
    words: str = "all"
    start_line: int = 1
    end_line: int = -1
    min_words: int = 0
    drop_ambiguous: bool = False
    drop_unreadable: bool = False

    def validate(self) -> None:
        for name in self.sections:
            if name not in SECTION_NAMES:
                raise ConfigError(
                    "unknown section %r in selection.sections" % name,
                    hint="Known sections: " + ", ".join(SECTION_NAMES),
                )
        for field_name, value, allowed in (
            ("text_class", self.text_class, TEXT_CLASSES),
            ("lines", self.lines, LINE_MODES),
            ("words", self.words, WORD_MODES),
        ):
            if value not in allowed:
                raise ConfigError(
                    "selection.%s=%r is not recognised" % (field_name, value),
                    hint="Allowed values: " + ", ".join(allowed),
                )
        if self.currier not in ("any", "A", "B"):
            raise ConfigError(
                "selection.currier=%r is not recognised" % self.currier,
                hint="Allowed values: any, A, B",
            )

    def is_empty(self) -> bool:
        """True when this selection keeps the whole manuscript unchanged."""
        return self == Selection()

    def describe(self) -> str:
        bits = []
        if self.sections:
            bits.append("sections=" + "+".join(self.sections))
        if self.folios:
            shown = ", ".join(self.folios[:4])
            if len(self.folios) > 4:
                shown += ", ..."
            bits.append("folios=" + shown)
        if self.currier != "any":
            bits.append("Currier " + self.currier)
        if self.scribes:
            bits.append("scribe " + "/".join(self.scribes))
        if self.quires:
            bits.append("quire " + "/".join(self.quires))
        if self.locus_types:
            bits.append("locus " + "/".join(self.locus_types))
        if self.text_class != "all":
            bits.append(self.text_class)
        if self.lines != "all":
            bits.append(self.lines + " lines")
        if self.words != "all":
            bits.append(self.words + " words")
        if self.start_line > 1 or self.end_line != -1:
            bits.append("lines %d..%s" % (self.start_line, self.end_line if self.end_line != -1 else "end"))
        return ", ".join(bits) or "whole manuscript"


_TEXT_CLASS_KINDS = {"running": "P", "labels": "L", "circular": "C", "radial": "R"}


# --------------------------------------------------------------------------
# Corpus
# --------------------------------------------------------------------------


@dataclass
class Corpus:
    """A transcription (or a slice of one) ready to be analysed."""

    key: str
    title: str
    alphabet: str
    source: str
    loci: list
    pages: dict
    folios: FolioTable
    selection: Selection = field(default_factory=Selection)
    parse_options: ParseOptions = field(default_factory=ParseOptions)
    source_sha256: str = ""
    dropped: int = 0

    # -- basic accessors -------------------------------------------------
    def __len__(self) -> int:
        return len(self.loci)

    def __iter__(self):
        return iter(self.loci)

    @property
    def is_empty(self) -> bool:
        return not self.loci

    def line_texts(self) -> list:
        return [locus.text for locus in self.loci]

    def text(self) -> str:
        """All selected lines joined by newlines, separators intact."""
        return "\n".join(locus.text for locus in self.loci)

    def line_words(self) -> list:
        """Words grouped per line."""
        return [_split_words(locus.text) for locus in self.loci]

    def words(self) -> list:
        out = []
        for locus in self.loci:
            out.extend(_split_words(locus.text))
        return out

    def word_counts(self) -> Counter:
        return Counter(self.words())

    def glyph_counts(self) -> Counter:
        counter = Counter()
        for locus in self.loci:
            counter.update(locus.text)
        counter.pop(".", None)
        counter.pop(",", None)
        return counter

    @property
    def paragraph_marks(self) -> int:
        """How many paragraph starts the source actually marks.

        Not every transliteration defines paragraphs: the reference file has no
        ``<%>`` markers at all, so asking it for first lines correctly yields
        nothing. Callers use this to say so out loud rather than silently
        returning an empty selection.
        """
        return sum(1 for locus in self.loci if locus.para_start)

    def folio_keys(self) -> list:
        seen = {}
        for locus in self.loci:
            seen.setdefault(locus.key, None)
        return list(seen)

    def stats_line(self) -> str:
        words = self.words()
        return "%d lines, %d words, %d word types, %d folios" % (
            len(self.loci),
            len(words),
            len(set(words)),
            len(self.folio_keys()),
        )

    # -- filtering -------------------------------------------------------
    def select(self, selection: Selection) -> Corpus:
        """Return a new corpus holding only the lines matching ``selection``."""
        selection.validate()
        loci = self.loci

        allowed_keys = None
        if selection.sections:
            allowed_keys = set()
            for name in selection.sections:
                allowed_keys |= self.folios.in_section(name)
        if selection.folios:
            explicit = set()
            for spec in selection.folios:
                found = parse_folio_range(spec)
                # A folio nobody has is a typo, not an empty result. Sections
                # are already checked this way; the rest of the filters were
                # not, so "--folio f999r" quietly produced nothing at all.
                if not (set(found) & set(self.folios.entries)):
                    raise ConfigError(
                        "no folio matches %r" % spec,
                        hint="Run 'tvtt folios' to list them. Ranges look like 1r-10v.",
                    )
                explicit.update(found)
            allowed_keys = explicit if allowed_keys is None else (allowed_keys & explicit)
        if selection.currier != "any":
            keys = self.folios.by_currier(selection.currier)
            allowed_keys = keys if allowed_keys is None else (allowed_keys & keys)
        if selection.scribes:
            keys = set()
            for scribe in selection.scribes:
                found = self.folios.by_scribe(str(scribe))
                if not found:
                    raise ConfigError(
                        "no folio is attributed to scribe %r" % scribe,
                        hint="Known scribes: " + (", ".join(self.folios.known_scribes()) or "none recorded"),
                    )
                keys |= found
            allowed_keys = keys if allowed_keys is None else (allowed_keys & keys)
        if selection.currier_hands:
            wanted = {str(h) for h in selection.currier_hands}
            known = {info.currier_hand for info in self.folios.entries.values() if info.currier_hand}
            for hand in sorted(wanted - known):
                raise ConfigError(
                    "no folio is attributed to Currier hand %r" % hand,
                    hint="Known hands: " + (", ".join(sorted(known)) or "none recorded"),
                )
            keys = {k for k, info in self.folios.entries.items() if info.currier_hand in wanted}
            allowed_keys = keys if allowed_keys is None else (allowed_keys & keys)
        if selection.quires:
            keys = set()
            for quire in selection.quires:
                found = self.folios.by_quire(str(quire))
                if not found:
                    raise ConfigError(
                        "no folio is in quire %r" % quire,
                        hint="Quires are numbered 1 to 20, or given by letter: "
                        + (", ".join(self.folios.known_quires()) or "none recorded"),
                    )
                keys |= found
            allowed_keys = keys if allowed_keys is None else (allowed_keys & keys)

        excluded = set()
        for spec in selection.exclude_folios:
            excluded.update(parse_folio_range(spec))

        kind_filter = _TEXT_CLASS_KINDS.get(selection.text_class)
        type_filter = set(selection.locus_types) if selection.locus_types else None
        kinds_filter = set(selection.locus_kinds) if selection.locus_kinds else None

        kept = []
        for locus in loci:
            if allowed_keys is not None and locus.key not in allowed_keys:
                continue
            if excluded and locus.key in excluded:
                continue
            if kind_filter and locus.kind != kind_filter:
                continue
            if type_filter and locus.locus_type not in type_filter:
                continue
            if kinds_filter and locus.kind not in kinds_filter:
                continue
            if selection.drop_ambiguous and locus.had_alternates:
                continue
            if selection.drop_unreadable and locus.had_unreadable:
                continue
            kept.append(locus)

        kept = _filter_lines(kept, selection.lines)
        kept = _slice_lines(kept, selection.start_line, selection.end_line)
        kept = _filter_words(kept, selection.words)

        if selection.min_words:
            kept = [locus for locus in kept if len(_split_words(locus.text)) >= selection.min_words]

        return replace(self, loci=kept, selection=selection)

    def by_folio(self) -> dict:
        """Group the selected lines by folio, in binding order."""
        groups: dict = {}
        for locus in self.loci:
            groups.setdefault(locus.key, []).append(locus)
        return groups

    def split_sections(self, names: Iterable = ()) -> dict:
        """Return one sub-corpus per named section (skipping empty ones)."""
        names = tuple(names) or SECTION_NAMES
        out = {}
        for name in names:
            sub = self.select(replace(self.selection, sections=(name,)))
            if not sub.is_empty:
                out[name] = sub
        return out

    def describe_locus_types(self) -> list:
        counts = Counter(locus.locus_type for locus in self.loci)
        return [
            (code, counts[code], LOCUS_TYPE_NAMES.get(code, "unknown locus type"))
            for code in sorted(counts, key=lambda c: -counts[c])
        ]


_WORD_SPLIT = re.compile(r"[.,]")


def _split_words(text: str) -> list:
    return [w for w in _WORD_SPLIT.split(text) if w]


def _filter_lines(loci: list, mode: str) -> list:
    if mode == "all":
        return loci
    if mode == "first":
        return [locus for locus in loci if locus.para_start]
    if mode == "last":
        return [locus for locus in loci if locus.para_end]
    if mode == "not_first":
        return [locus for locus in loci if not locus.para_start]
    if mode == "single":
        return [locus for locus in loci if locus.para_start and locus.para_end]
    return loci


def _slice_lines(loci: list, start: int, end: int) -> list:
    if start <= 1 and end in (-1, 0, None):
        return loci
    lo = max(0, start - 1)
    hi = len(loci) if end in (-1, 0, None) else end
    return loci[lo:hi]


def _filter_words(loci: list, mode: str) -> list:
    if mode == "all":
        return loci
    out = []
    for locus in loci:
        words = _split_words(locus.text)
        if not words:
            continue
        if mode == "first":
            keep = words[:1]
        elif mode == "last":
            keep = words[-1:]
        else:  # not_first
            keep = words[1:]
        if not keep:
            continue
        out.append(replace(locus, text=".".join(keep)))
    return out


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_corpus(
    transcription: str = "zl",
    parse_options: ParseOptions = None,
    selection: Selection = None,
) -> Corpus:
    """Load a transcription by short name and apply an optional selection."""
    spec = resolve_transcription(transcription)
    path = transcription_file(spec.filename)
    parsed = parse_file(path, parse_options)
    corpus = from_transliteration(parsed, spec)
    return corpus.select(selection) if selection else corpus


def from_transliteration(parsed: Transliteration, spec: TranscriptionSpec = None) -> Corpus:
    """Wrap an already-parsed IVTFF file as a :class:`Corpus`."""
    key = spec.key if spec else "custom"
    title = spec.title if spec else parsed.source
    try:
        digest = sha256_file(parsed.source)
    except OSError:
        digest = ""
    return Corpus(
        key=key,
        title=title,
        alphabet=parsed.alphabet,
        source=parsed.source,
        loci=list(parsed.loci),
        pages=parsed.pages,
        folios=load_folios(),
        parse_options=parsed.options,
        source_sha256=digest,
        dropped=parsed.dropped,
    )


def selection_from_dict(data: dict) -> Selection:
    """Build a :class:`Selection` from the ``selection`` block of config.json."""

    def tup(name, default=()):
        value = data.get(name, default)
        if value in (None, ""):
            return ()
        # A single value is allowed wherever a list is: "--set selection.scribes=2"
        # and "quires": 13 both mean a list of one.
        if isinstance(value, (str, int, float, bool)):
            return (str(value),)
        try:
            return tuple(str(v) for v in value)
        except TypeError:
            raise ConfigError(
                "selection.%s should be a value or a list of values, not %s" % (name, type(value).__name__)
            ) from None

    sel = Selection(
        sections=tup("sections"),
        folios=tup("folios"),
        exclude_folios=tup("excludeFolios"),
        currier=str(data.get("currier", "any")),
        scribes=tup("scribes"),
        currier_hands=tup("currierHands"),
        quires=tup("quires"),
        locus_types=tup("locusTypes"),
        locus_kinds=tup("locusKinds"),
        text_class=str(data.get("textClass", "all")),
        lines=str(data.get("lines", "all")),
        words=str(data.get("words", "all")),
        start_line=int(data.get("startLine", 1)),
        end_line=int(data.get("endLine", -1)),
        min_words=int(data.get("minWords", 0)),
        drop_ambiguous=bool(data.get("dropAmbiguousLines", False)),
        drop_unreadable=bool(data.get("dropUnreadableLines", False)),
    )
    sel.validate()
    return sel


def normalise_folio_list(values: Iterable) -> list:
    return [normalise_folio(v) for v in values]
