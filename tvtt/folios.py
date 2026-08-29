"""Folio metadata: sections, Currier languages, scribes, quires.

The manuscript is not one book.  Different sections use noticeably different
vocabulary, and Prescott Currier showed in the 1970s that two statistically
distinct "languages" (A and B) run through it.  Testing a mapping against the
whole manuscript at once therefore averages away the very signal you are
looking for.

Where this data comes from
--------------------------
The ZL transliteration records, for every page, a set of IVTFF *page
variables*::

    $I  illustration type   A B C H P S T Z  (see ILLUSTRATION_NAMES)
    $L  Currier language    A or B
    $H  scribe              1-5, Lisa Fagin Davis' hand identification
    $C  Currier hand        Currier's own, earlier attribution
    $Q  quire               a letter A-T standing for quire 1-20
    $P  page within quire   a letter A-X
    $B  bifolio             1-6, counted outside to inside
    $X  extraneous writing  (see EXTRANEOUS_NAMES)

The meanings are those given in Table 6 of the IVTFF format definition, at
https://www.voynich.nu/software/ivtt/IVTFF_format.pdf .

``tvtt/data/folios.json`` is generated from those variables (see
``tvtt build-folios``) so that transcriptions which carry no metadata of their
own - the original ``voyn_101.txt``, for instance - get the same section,
language and scribe information keyed by folio.

Because it is a plain JSON file you can correct it: drop a copy into
``./data/folios.json`` in your workspace and it takes precedence over the
bundled one.
"""

from __future__ import annotations

import functools
from collections.abc import Iterable
from dataclasses import dataclass

from .errors import DataError
from .ivtff import folio_sort_key, normalise_folio
from .paths import data_file, display_path
from .util import read_json

# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

#: Illustration types, quoted from Table 6 of the IVTFF format definition.
ILLUSTRATION_NAMES = {
    "A": "astronomical (excluding zodiac)",
    "B": "biological",
    "C": "cosmological",
    "H": "herbal",
    "P": "pharmaceutical",
    "S": "marginal stars only",
    "T": "text-only page (no illustrations)",
    "Z": "zodiac",
}

#: Extraneous writing, from the same table. These were previously guessed:
#: V is the deprecated "various" value, not "non-Voynich writing", and S is a
#: sequence of characters or numbers, not a signature.
EXTRANEOUS_NAMES = {
    "C": "a colour annotation",
    "M": "a month name",
    "O": "other",
    "S": "a sequence of characters or numbers",
    "V": "various, a combination of the above (deprecated)",
}

#: ``$Q`` is a letter, but everybody refers to these as "Quire 13" and
#: "Quire 20". The letters run A=1 to T=20 with P (16) and R (18) unused,
#: because those two quires do not exist.
_QUIRE_LETTERS = "ABCDEFGHIJKLMNO_Q_ST"


def quire_number(letter: str):
    """Turn the ``$Q`` letter into the quire number people actually cite."""
    if not letter:
        return None
    index = _QUIRE_LETTERS.find(letter.upper()[:1])
    return index + 1 if index >= 0 else None


def quire_label(letter: str) -> str:
    """``M`` becomes ``13 (M)``, so both notations are readable."""
    number = quire_number(letter)
    if number is None:
        return letter or "-"
    return "%d (%s)" % (number, letter.upper())


@dataclass(frozen=True)
class SectionSpec:
    """A named part of the manuscript, defined by page-variable tests."""

    name: str
    title: str
    description: str
    illustration: tuple = ()
    currier: tuple = ()

    def matches(self, info: FolioInfo) -> bool:
        if self.illustration and info.illustration not in self.illustration:
            return False
        return not (self.currier and info.currier not in self.currier)


#: The manuscript divisions people actually talk about.
SECTIONS: dict = {
    s.name: s
    for s in (
        SectionSpec("herbal_a", "Herbal A", "Herbal pages written in Currier language A.", ("H",), ("A",)),
        SectionSpec("herbal_b", "Herbal B", "Herbal pages written in Currier language B.", ("H",), ("B",)),
        SectionSpec("herbal", "Herbal", "All herbal pages, both languages.", ("H",)),
        SectionSpec("astronomical", "Astronomical", "Circular astronomical diagrams.", ("A",)),
        SectionSpec("zodiac", "Zodiac", "The zodiac roundels with their nymph labels.", ("Z",)),
        SectionSpec(
            "biological",
            "Biological / Balneological",
            "The 'bathing nymphs' quire, densely written Currier B.",
            ("B",),
        ),
        SectionSpec("cosmological", "Cosmological", "Cosmological diagrams including the rosettes foldout.", ("C",)),
        SectionSpec("pharmaceutical", "Pharmaceutical", "Container and root-and-leaf pages with labels.", ("P",)),
        SectionSpec("recipes", "Recipes / Stars", "The short star-marked paragraphs of Quire 20.", ("S",)),
        SectionSpec("text_only", "Text only", "Pages with writing and no illustration.", ("T",)),
        SectionSpec("currier_a", "Currier A", "Every page in Currier language A.", (), ("A",)),
        SectionSpec("currier_b", "Currier B", "Every page in Currier language B.", (), ("B",)),
    )
}

SECTION_NAMES = tuple(SECTIONS)


@dataclass(frozen=True)
class FolioInfo:
    """Everything known about one manuscript page."""

    key: str
    folio: str
    illustration: str = ""
    currier: str = ""
    scribe: str = ""
    currier_hand: str = ""
    quire: str = ""
    page_in_quire: str = ""
    bifolio: str = ""
    extraneous: str = ""

    @property
    def illustration_name(self) -> str:
        return ILLUSTRATION_NAMES.get(self.illustration, "unknown")

    @property
    def quire_number(self):
        """The quire as the number people cite, e.g. 13 rather than 'M'."""
        return quire_number(self.quire)

    @property
    def quire_name(self) -> str:
        return quire_label(self.quire)

    @property
    def extraneous_name(self) -> str:
        return EXTRANEOUS_NAMES.get(self.extraneous, "") if self.extraneous else ""

    @property
    def sections(self) -> tuple:
        return tuple(name for name, spec in SECTIONS.items() if spec.matches(self))

    def to_dict(self) -> dict:
        return {
            "folio": self.folio,
            "I": self.illustration,
            "L": self.currier,
            "H": self.scribe,
            "C": self.currier_hand,
            "Q": self.quire,
            "P": self.page_in_quire,
            "B": self.bifolio,
            "X": self.extraneous,
        }


class FolioTable:
    """Lookup table of :class:`FolioInfo`, keyed by normalised folio id."""

    def __init__(self, entries: dict) -> None:
        self.entries = entries

    def __contains__(self, key: str) -> bool:
        return normalise_folio(key) in self.entries

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, key: str) -> FolioInfo:
        norm = normalise_folio(key)
        info = self.entries.get(norm)
        if info is not None:
            return info
        return FolioInfo(key=norm, folio=key)

    def keys(self) -> list:
        return sorted(self.entries, key=folio_sort_key)

    def in_section(self, section: str) -> set:
        spec = SECTIONS.get(section)
        if spec is None:
            raise DataError(
                "unknown section %r" % section,
                hint="Known sections: " + ", ".join(SECTION_NAMES),
            )
        return {k for k, info in self.entries.items() if spec.matches(info)}

    def known_scribes(self) -> list:
        """Every scribe the metadata actually attributes a page to."""
        return sorted({info.scribe for info in self.entries.values() if info.scribe})

    def known_quires(self) -> list:
        """Every quire, as the numbers people cite them by."""
        numbers = {quire_number(info.quire) for info in self.entries.values() if info.quire}
        return [str(n) for n in sorted(n for n in numbers if n)]

    def by_scribe(self, scribe: str) -> set:
        return {k for k, info in self.entries.items() if info.scribe == str(scribe)}

    def by_currier(self, language: str) -> set:
        return {k for k, info in self.entries.items() if info.currier == language.upper()}

    def by_quire(self, quire: str) -> set:
        """Select a quire by its number (``13``) or its ``$Q`` letter (``M``).

        People cite quires by number, so accepting both is the difference
        between ``--quire 13`` working and quietly matching nothing.
        """
        wanted = str(quire).strip().upper()
        if wanted.isdigit():
            number = int(wanted)
            return {k for k, info in self.entries.items() if quire_number(info.quire) == number}
        return {k for k, info in self.entries.items() if info.quire == wanted}

    def summary(self) -> list:
        """Counts per section, for ``tvtt sections``."""
        rows = []
        for name, spec in SECTIONS.items():
            keys = self.in_section(name)
            rows.append((name, spec.title, len(keys), spec.description))
        return rows


@functools.lru_cache(maxsize=4)
def load_folios(path: str = "") -> FolioTable:
    """Load ``data/folios.json`` (workspace copy wins over the bundled one)."""
    target = path or str(data_file("folios.json"))
    try:
        raw = read_json(target)
    except FileNotFoundError as exc:
        raise DataError(
            "folio metadata file not found: %s" % display_path(target),
            hint="Run 'tvtt build-folios' to regenerate it from a transcription.",
        ) from exc
    entries = {}
    for key, value in raw.get("folios", {}).items():
        entries[key] = FolioInfo(
            key=key,
            folio=value.get("folio", key),
            illustration=value.get("I", ""),
            currier=value.get("L", ""),
            scribe=value.get("H", ""),
            currier_hand=value.get("C", ""),
            quire=value.get("Q", ""),
            page_in_quire=value.get("P", ""),
            bifolio=value.get("B", ""),
            extraneous=value.get("X", ""),
        )
    return FolioTable(entries)


def build_folio_table(pages: Iterable) -> dict:
    """Build the JSON payload for ``folios.json`` from parsed IVTFF pages."""
    out = {}
    for page in pages:
        if not page.variables:
            continue
        out[page.key] = {
            "folio": page.folio,
            "I": page.variables.get("I", ""),
            "L": page.variables.get("L", ""),
            "H": page.variables.get("H", ""),
            "C": page.variables.get("C", ""),
            "Q": page.variables.get("Q", ""),
            "P": page.variables.get("P", ""),
            "B": page.variables.get("B", ""),
            "X": page.variables.get("X", ""),
        }
    return {
        "note": (
            "Per-page metadata extracted from the IVTFF page variables of the ZL "
            "transliteration. $I illustration type, $L Currier language, $H scribe "
            "(Lisa Fagin Davis), $C Currier hand, $Q quire, $P page in quire, "
            "$B bifolio, $X extraneous writing."
        ),
        "folios": {k: out[k] for k in sorted(out, key=folio_sort_key)},
    }


def parse_folio_range(spec: str) -> list:
    """Expand ``1r-5v`` into every folio key in between.

    Single ids (``f68r2``) pass through unchanged.  Ranges are inclusive and
    follow binding order, so ``1r-2r`` gives ``1r``, ``1v``, ``2r``.
    """
    spec = spec.strip()
    if "-" not in spec:
        return [normalise_folio(spec)]
    start, end = (normalise_folio(p) for p in spec.split("-", 1))
    table = load_folios()
    ordered = table.keys()
    if start not in ordered or end not in ordered:
        low, high = folio_sort_key(start), folio_sort_key(end)
        return [k for k in ordered if low <= folio_sort_key(k) <= high]
    i, j = ordered.index(start), ordered.index(end)
    if i > j:
        i, j = j, i
    return ordered[i : j + 1]
