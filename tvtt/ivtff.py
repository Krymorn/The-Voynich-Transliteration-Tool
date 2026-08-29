"""A full parser for IVTFF, the Intermediate Voynich Transliteration File Format.

Every transliteration published on voynich.nu uses IVTFF.  A file looks like::

    #=IVTFF Eva- 2.0 M 5                       <- header (alphabet, version)
    # free-form comment
    <f1r>   <! $Q=A $P=A $I=T $L=A $H=1 $C=1>   <- page header + page variables
    <f1r.1,@P0>  <%>fachys.ykal.ar.[cth:oto]res
    ^folio ^locus  ^locus type  ^text

Parsing this properly is what unlocks the rest of TVTT: once every line knows
which folio, paragraph and locus type it belongs to, you can ask for "only
zodiac labels", "only Currier B paragraph text", "only first lines", and so on.

Text-level markup handled here
------------------------------
``.``            certain word separator
``,``            uncertain word separator
``[a:o]``        alternate readings by different transcribers (first = preferred)
``{ck}``         a ligature: two glyphs written as one
``@253;``        a glyph outside the alphabet, referenced by code number
``?``            one unreadable glyph
``<%> <$> <->``  paragraph start / paragraph end / a drawing interrupts the line
``<!...>``       inline comment
``<@H=2>``       an inline page-variable override

Ambiguity is not silently discarded.  :class:`ParseOptions` decides whether an
alternate reading resolves to the first choice, the last choice, expands into
every variant, or drops the line entirely, and each line records whether it was
ambiguous at all, so analyses can report how much of a result rests on
uncertain readings.
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .errors import DataError
from .paths import display_path
from .util import read_text

# --------------------------------------------------------------------------
# Regular expressions
# --------------------------------------------------------------------------

RE_FILE_HEADER = re.compile(r"^#=IVTFF\s+(?P<alphabet>\S+)\s+(?P<version>\S+)(?:\s+(?P<rest>.*))?$")
RE_PAGE_HEADER = re.compile(r"^<(?P<folio>[^.,>]+)>\s*(?P<tail>.*)$")
RE_LOCUS = re.compile(
    r"^<(?P<folio>[^.,>]+)\.(?P<num>[^,>]+)(?:,(?P<prefix>[@+*=&])(?P<type>[A-Za-z0-9]+))?>(?P<text>.*)$"
)
RE_PAGE_VAR = re.compile(r"\$([A-Za-z])=([^\s>]+)")
RE_INLINE_TAG = re.compile(r"<[^>]*>")
RE_HIGH_ASCII = re.compile(r"@(\d{1,4});")
RE_ALTERNATE = re.compile(r"\[([^\[\]]*)\]")
RE_LIGATURE = re.compile(r"\{([^{}]*)\}")
#: ``<->`` and ``<~>`` mark text interrupted by a drawing. The specification is
#: explicit that each "implies a word space", so they must become a separator
#: rather than being stripped like an ordinary tag - otherwise the words either
#: side are silently fused into one.
RE_DRAWING_BREAK = re.compile(r"<[-~]>")
#: ``?`` is one unreadable character; ``???`` is an unknown number of them.
RE_UNREADABLE_RUN = re.compile(r"\?{2,}")

#: Private-use codepoint base for ``@nnn;`` glyphs, so that every glyph stays
#: exactly one character wide.  ``@253;`` becomes ``chr(0xE000 + 253)``.
PUA_BASE = 0xE000

EVA_FAMILY = {"Eva-", "EvaT", "Eva", "EVA"}

# --------------------------------------------------------------------------
# Locus type vocabulary (from the IVTFF specification)
# --------------------------------------------------------------------------

#: Generic locus types, from Table 9 of the IVTFF format definition.
LOCUS_KIND_NAMES = {
    "P": "linear text in paragraphs",
    "L": "a short piece of text, a word or a character: mostly labels",
    "C": "text along the circumference of a circle",
    "R": "text along the radius of a circle",
}

#: Complete locus types, quoted from Table 9 of the IVTFF format definition.
#: These were previously guessed and several were wrong - ``Lf`` and ``Lp`` in
#: particular were the wrong way round, which made the reports describe
#: pharmaceutical labels as plant labels and vice versa.
LOCUS_TYPE_NAMES = {
    "P0": "normal left-justified paragraph text",
    "P1": "paragraph text set well in from the left, usually because of a drawing",
    "Pb": "a free-floating set of lines in a non-standard location",
    "Pc": "a roughly centred line",
    "Pr": "a roughly right-justified line",
    "Pt": "a right-justified title on the same line as the previous item",
    "L0": "a label not clearly near any drawing element",
    "La": "a label of an astronomical or cosmological element (not a star or zodiac sign)",
    "Lc": "a label of a container in the pharmaceutical section",
    "Lf": "a label of a herb fragment in the pharmaceutical section",
    "Ln": "a label of a nymph in the biological section",
    "Lp": "a label of a large herb or plant drawing in the herbal section",
    "Ls": "a label of a star",
    "Lt": "a label of a tube or tub in the biological section",
    "Lx": "extraneous writing, for example in the margin",
    "Lz": "a label of a zodiac element",
    "Ca": "circular text running anti-clockwise",
    "Cc": "circular text running clockwise",
    "Ri": "radial text running outside to inside",
    "Ro": "radial text running inside to outside",
}

#: The locator character says where a locus sits relative to the previous one.
#: It is purely spatial: it says nothing about paragraph structure, which is
#: carried by the ``<%>`` and ``<$>`` markers instead. (Table 8.)
PREFIX_NAMES = {
    "@": "position unrelated to the previous item; always used for the first item on a page",
    "+": "generally below the previous item",
    "*": "at the start of the line below, at the left margin, where the previous item was not",
    "=": "on the same line as the previous item, separated by white space",
    "&": "like =, but along a circular line",
    "~": "like =, but not well aligned vertically",
    "/": "to the right of, and above, the previous locus",
    "!": "refers to text that does not actually exist in the manuscript",
}

#: Paragraphs are defined only by these markers, and only for type-P loci.
#: See section 6.9 of the format definition.
PARAGRAPH_START_MARK = "<%>"
PARAGRAPH_END_MARK = "<$>"


# --------------------------------------------------------------------------
# Options
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ParseOptions:
    """How to resolve every kind of ambiguity in an IVTFF file."""

    #: ``first`` keeps the preferred reading, ``last`` the final alternative,
    #: ``variants`` records every combination, ``drop_line`` removes the line.
    alternates: str = "first"
    #: Cap on combinations generated per line when ``alternates='variants'``.
    max_variants: int = 16
    #: ``keep`` leaves ``?``; ``drop_word`` removes the containing word;
    #: ``drop_line`` removes the line; ``placeholder`` substitutes a character.
    unreadable: str = "keep"
    unreadable_char: str = "?"
    #: ``keep`` preserves ``,``; ``space`` promotes it to a certain space;
    #: ``join`` deletes it so the two halves become one word.
    uncertain_space: str = "keep"
    #: ``keep`` unwraps ``{ck}`` to ``ck``; ``drop`` deletes the whole group.
    ligatures: str = "keep"
    #: ``unicode`` maps ``@253;`` to a single private-use character (recommended),
    #: ``keep`` leaves the literal text, ``drop`` removes it.
    high_ascii: str = "unicode"
    #: Remove EVA filler characters (``!`` and ``%``) in Eva-family alphabets.
    strip_fillers: bool = True

    ALTERNATE_MODES = ("first", "last", "variants", "drop_line")
    UNREADABLE_MODES = ("keep", "drop_word", "drop_line", "placeholder")
    UNCERTAIN_SPACE_MODES = ("keep", "space", "join")
    LIGATURE_MODES = ("keep", "drop")
    HIGH_ASCII_MODES = ("unicode", "keep", "drop")

    def validate(self) -> None:
        checks = [
            ("alternates", self.alternates, self.ALTERNATE_MODES),
            ("unreadable", self.unreadable, self.UNREADABLE_MODES),
            ("uncertain_space", self.uncertain_space, self.UNCERTAIN_SPACE_MODES),
            ("ligatures", self.ligatures, self.LIGATURE_MODES),
            ("high_ascii", self.high_ascii, self.HIGH_ASCII_MODES),
        ]
        for name, value, allowed in checks:
            if value not in allowed:
                raise DataError(
                    f"ambiguity option {name}={value!r} is not recognised",
                    hint="Allowed values: " + ", ".join(allowed),
                )

    def signature(self) -> tuple:
        """A hashable summary, used as part of the parse cache key."""
        return (
            self.alternates,
            self.max_variants,
            self.unreadable,
            self.unreadable_char,
            self.uncertain_space,
            self.ligatures,
            self.high_ascii,
            self.strip_fillers,
        )


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass
class Page:
    """One manuscript page and its IVTFF page variables."""

    folio: str
    key: str
    variables: dict = field(default_factory=dict)

    @property
    def illustration(self) -> str:
        return self.variables.get("I", "")

    @property
    def currier_language(self) -> str:
        return self.variables.get("L", "")

    @property
    def scribe(self) -> str:
        """Lisa Fagin Davis' hand identification (IVTFF variable ``$H``)."""
        return self.variables.get("H", "")

    @property
    def currier_hand(self) -> str:
        """Currier's original hand identification (IVTFF variable ``$C``)."""
        return self.variables.get("C", "")

    @property
    def quire(self) -> str:
        return self.variables.get("Q", "")


@dataclass
class Locus:
    """One transliterated line, with everything known about where it sits."""

    index: int
    folio: str
    key: str
    number: str
    prefix: str
    locus_type: str
    text: str
    raw: str
    para_start: bool = False
    para_end: bool = False
    interrupted: bool = False
    had_alternates: bool = False
    had_unreadable: bool = False
    variants: tuple = ()

    @property
    def kind(self) -> str:
        """``P``, ``L``, ``C``, ``R`` or ``?``."""
        return self.locus_type[0] if self.locus_type else "?"

    @property
    def is_label(self) -> bool:
        return self.kind == "L"

    @property
    def is_paragraph(self) -> bool:
        return self.kind == "P"

    @property
    def locus_id(self) -> str:
        """The canonical IVTFF locus identifier, e.g. ``<f1r.3,+P0>``."""
        pre = f",{self.prefix}{self.locus_type}" if self.locus_type else ""
        return f"<{self.folio}.{self.number}{pre}>"

    def words(self) -> list:
        return [w for w in re.split(r"[.,]", self.text) if w]


@dataclass
class Transliteration:
    """A parsed IVTFF file: its header, its pages and its loci."""

    source: str
    alphabet: str
    version: str
    comment: str
    pages: dict
    loci: list
    dropped: int = 0
    options: ParseOptions = field(default_factory=ParseOptions)

    def __len__(self) -> int:
        return len(self.loci)

    def __iter__(self) -> Iterator:
        return iter(self.loci)

    def page_of(self, locus: Locus):
        return self.pages.get(locus.key)


# --------------------------------------------------------------------------
# Folio identifiers
# --------------------------------------------------------------------------

FOLIO_ALIASES = {
    "rose": "ros",
    "fros": "ros",
}


def normalise_folio(folio: str) -> str:
    """Reduce the many spellings of a folio id to one comparable key.

    ``f1r`` / ``1r`` -> ``1r``; ``fRos`` / ``rose`` -> ``ros``;
    ``101r1-r2`` -> ``101r1`` (compound foldout loci keep their first panel).
    """
    key = folio.strip().lower()
    if "-" in key:
        key = key.split("-", 1)[0]
    if key.startswith("f") and len(key) > 1 and key[1].isdigit():
        key = key[1:]
    elif key in ("fros",):
        key = "ros"
    return FOLIO_ALIASES.get(key, key)


def folio_sort_key(key: str) -> tuple:
    """Sort folio keys the way the manuscript is bound (1r, 1v, 2r, ...)."""
    m = re.match(r"^(\d+)([rv])(\d*)$", key)
    if m:
        return (0, int(m.group(1)), 0 if m.group(2) == "r" else 1, int(m.group(3) or 0), key)
    return (1, 0, 0, 0, key)


# --------------------------------------------------------------------------
# Text resolution
# --------------------------------------------------------------------------


def _expand_alternates(text: str, options: ParseOptions):
    """Return candidate strings for a line and whether alternates were present."""
    matches = list(RE_ALTERNATE.finditer(text))
    if not matches:
        return [text], False

    if options.alternates == "drop_line":
        return [], True

    if options.alternates in ("first", "last"):
        pick = 0 if options.alternates == "first" else -1

        def choose(m):
            parts = m.group(1).split(":")
            return parts[pick] if parts else ""

        return [RE_ALTERNATE.sub(choose, text)], True

    # variants: build every combination, capped by max_variants
    pieces = []
    cursor = 0
    for m in matches:
        pieces.append([text[cursor : m.start()]])
        pieces.append(m.group(1).split(":") or [""])
        cursor = m.end()
    pieces.append([text[cursor:]])
    combos = []
    for combo in itertools.product(*pieces):
        combos.append("".join(combo))
        if len(combos) >= options.max_variants:
            break
    return combos, True


def _apply_ligatures(text: str, options: ParseOptions) -> str:
    if "{" not in text:
        return text
    if options.ligatures == "drop":
        return RE_LIGATURE.sub("", text)
    return RE_LIGATURE.sub(lambda m: m.group(1), text)


def _apply_high_ascii(text: str, options: ParseOptions) -> str:
    if "@" not in text:
        return text
    if options.high_ascii == "keep":
        return text
    if options.high_ascii == "drop":
        return RE_HIGH_ASCII.sub("", text)
    return RE_HIGH_ASCII.sub(lambda m: chr(PUA_BASE + int(m.group(1))), text)


def high_ascii_label(ch: str) -> str:
    """Render a private-use glyph back as its IVTFF ``@nnn;`` code."""
    code = ord(ch)
    if PUA_BASE <= code < PUA_BASE + 4096:
        return "@%d;" % (code - PUA_BASE)
    return ch


def describe_glyph(ch: str) -> str:
    """A printable name for a glyph, used by legends and reports."""
    if ch == " ":
        return "space"
    return high_ascii_label(ch)


def _apply_unreadable(text: str, options: ParseOptions):
    if "?" not in text:
        return text, False
    # A run of question marks means "an unknown number of unreadable
    # characters", so keeping three of them would assert a length the
    # transcriber explicitly did not commit to. One stands for the run.
    text = RE_UNREADABLE_RUN.sub("?", text)
    if options.unreadable == "drop_line":
        return "", True
    if options.unreadable == "placeholder":
        return text.replace("?", options.unreadable_char), True
    if options.unreadable == "drop_word":
        parts = re.split(r"([.,])", text)
        kept = [w for i, w in enumerate(parts) if i % 2 == 1 or "?" not in w]
        out = "".join(kept)
        return re.sub(r"[.,]{2,}", ".", out).strip(".,"), True
    return text, True


def _apply_uncertain_space(text: str, options: ParseOptions) -> str:
    if options.uncertain_space == "space":
        return text.replace(",", ".")
    if options.uncertain_space == "join":
        return text.replace(",", "")
    return text


def _collapse_separators(text: str) -> str:
    return re.sub(r"[.,]{2,}", lambda m: m.group(0)[0], text).strip(".,")


def resolve_text(raw: str, options: ParseOptions, eva_family: bool):
    """Turn one raw locus body into clean text variants.

    Returns ``(variants, had_alternates, had_unreadable)``.  ``variants`` is
    empty when the line was dropped by the chosen ambiguity policy.
    """
    # A drawing interrupting the text implies a word space, so <-> and <~> have
    # to become a separator *before* the general tag strip removes them. Without
    # this the words either side are fused: f1v.1 reads "ol<->o", which is two
    # words, not the single word "olo".
    text = RE_DRAWING_BREAK.sub(".", raw)
    text = RE_INLINE_TAG.sub("", text).strip()
    text = text.replace(" ", "").replace("\t", "")
    # Trailing v101 line markers: '-' line continues, '=' paragraph ends.
    text = text.rstrip("-=")
    if eva_family and options.strip_fillers:
        text = text.replace("!", "").replace("%", "")

    variants, had_alt = _expand_alternates(text, options)
    out = []
    had_unreadable = False
    for candidate in variants:
        candidate = _apply_ligatures(candidate, options)
        candidate = _apply_high_ascii(candidate, options)
        candidate, unread = _apply_unreadable(candidate, options)
        had_unreadable = had_unreadable or unread
        candidate = _apply_uncertain_space(candidate, options)
        candidate = _collapse_separators(candidate)
        if candidate:
            out.append(candidate)
    seen = set()
    unique = [c for c in out if not (c in seen or seen.add(c))]
    return unique, had_alt, had_unreadable


# --------------------------------------------------------------------------
# Native (non-IVTFF) v101 support
# --------------------------------------------------------------------------

_NATIVE_LOCUS_HINTS = (
    ("label", "L0"),
    ("radial", "Ri"),
    ("ring", "Cc"),
    ("circle", "Cc"),
    ("spiral", "Cc"),
    ("center", "Cc"),
    ("quad", "Cc"),
    ("north", "Ro"),
    ("south", "Ro"),
    ("east", "Ro"),
    ("west", "Ro"),
    ("pond", "L0"),
    ("bottom", "Pb"),
)


def _infer_locus_type(number: str) -> str:
    low = number.lower()
    for needle, code in _NATIVE_LOCUS_HINTS:
        if needle in low:
            return code
    return "P0"


# --------------------------------------------------------------------------
# The parser
# --------------------------------------------------------------------------


def parse_text(text: str, source: str = "<memory>", options: ParseOptions = None) -> Transliteration:
    """Parse IVTFF (or the original v101 layout) from a string."""
    options = options or ParseOptions()
    options.validate()

    alphabet, version = "", ""
    pages = {}
    loci = []
    dropped = 0
    comments = []
    index = 0

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue

        if line.startswith("#="):
            m = RE_FILE_HEADER.match(line)
            if m:
                alphabet = m.group("alphabet")
                version = m.group("version")
            continue
        if line.startswith("#"):
            comments.append(line[1:].strip())
            continue

        m = RE_LOCUS.match(line)
        if m:
            folio = m.group("folio")
            key = normalise_folio(folio)
            locus_type = m.group("type") or _infer_locus_type(m.group("num"))
            prefix = m.group("prefix") or ""
            body = m.group("text")
            eva_family = alphabet in EVA_FAMILY
            variants, had_alt, had_unread = resolve_text(body, options, eva_family)
            if not variants:
                dropped += 1
                continue
            if key not in pages:
                pages[key] = Page(folio=folio, key=key)
            loci.append(
                Locus(
                    index=index,
                    folio=folio,
                    key=key,
                    number=m.group("num"),
                    prefix=prefix,
                    locus_type=locus_type,
                    text=variants[0],
                    raw=body,
                    para_start=PARAGRAPH_START_MARK in body,
                    para_end=PARAGRAPH_END_MARK in body,
                    interrupted="<->" in body,
                    had_alternates=had_alt,
                    had_unreadable=had_unread,
                    variants=tuple(variants) if len(variants) > 1 else (),
                )
            )
            index += 1
            continue

        m = RE_PAGE_HEADER.match(line)
        if m:
            folio = m.group("folio")
            key = normalise_folio(folio)
            variables = dict(RE_PAGE_VAR.findall(m.group("tail") or ""))
            page = pages.get(key)
            if page is None:
                pages[key] = Page(folio=folio, key=key, variables=variables)
            else:
                page.variables.update(variables)
            continue

    if not loci:
        raise DataError(
            "no transliteration lines found in %s" % display_path(source),
            hint="The file may be empty, or in a format TVTT does not recognise.",
        )

    return Transliteration(
        source=source,
        alphabet=alphabet or "unknown",
        version=version or "",
        comment="\n".join(comments[:12]),
        pages=pages,
        loci=loci,
        dropped=dropped,
        options=options,
    )


def parse_file(path, options: ParseOptions = None) -> Transliteration:
    """Parse an IVTFF file from disk (encoding is detected automatically)."""
    p = Path(path)
    if not p.exists():
        raise DataError(
            "transcription file not found: %s" % p,
            hint="Run 'tvtt fetch --all' to download the published transcriptions.",
        )
    return parse_text(read_text(p), source=str(p), options=options)


def glyph_inventory(loci: Iterable) -> dict:
    """Count every glyph across a set of loci, ignoring word separators."""
    counter = Counter()
    for locus in loci:
        counter.update(locus.text)
    for sep in (".", ","):
        counter.pop(sep, None)
    return dict(counter)
