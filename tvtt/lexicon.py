"""Reference vocabularies and the string tools used to match against them.

This module supplies the "is that a real word?" half of the workbench:

* :class:`Dictionary` - a word list with frequencies, so a match on a rare word
  can be worth more than a match on ``et``.
* :func:`expand_abbreviations` - medieval Latin scribal abbreviations, because
  a fifteenth-century text writes ``dñs`` for ``dominus`` and ``9`` for ``-us``.
* :class:`Stemmer` - light suffix stripping so inflected forms still count.
* :func:`consonant_skeleton` - abjad mode, for mappings that produce consonants
  only.
* :func:`levenshtein`, :func:`damerau_levenshtein`, :func:`metaphone` - the
  distance and phonetic measures the matcher can choose between.
* :class:`FuzzyIndex` - a trigram index that finds near-matches in a 40,000
  word dictionary fast enough to run over the whole manuscript.

Bundled dictionaries live in ``tvtt/data/dictionaries`` as ``word<TAB>count``
files with a comment header naming their source.  Drop your own ``.txt`` files
into ``reference_texts/`` and they are picked up as plain prose and tokenised.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .errors import DataError
from .paths import data_dirs, data_file, ws
from .util import read_text

# --------------------------------------------------------------------------
# Dictionaries
# --------------------------------------------------------------------------

TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

BUNDLED_LANGUAGES = (
    "latin",
    "italian",
    "english",
    "middle_english",
    "middle_high_german",
    "czech",
    "occitan",
    "hebrew",
    "hebrew_latin",
    "arabic",
    "arabic_latin",
)

LANGUAGE_TITLES = {
    "latin": "Latin (Vergil, Augustine, Linnaeus)",
    "italian": "Italian (Dante)",
    "english": "English (King James Bible, Austen)",
    "middle_english": "Middle English (Chaucer)",
    "middle_high_german": "Middle High German (Walther von der Vogelweide)",
    "czech": "Czech (Capek)",
    "occitan": "Occitan / Gascon",
    "hebrew": "Hebrew, consonantal (Torah)",
    "hebrew_latin": "Hebrew in Latin letters, consonantal",
    "arabic": "Arabic, consonantal (Quran)",
    "arabic_latin": "Arabic in Latin letters, consonantal",
}


def tokenize(text: str) -> list:
    """Split prose into lowercase word tokens."""
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


@dataclass
class Dictionary:
    """A word list with frequencies and derived scoring weights."""

    name: str
    counts: Counter
    description: str = ""
    total: int = 0
    _weights: dict = field(default=None, repr=False)
    _ranks: dict = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.total:
            self.total = sum(self.counts.values())

    def __contains__(self, word: str) -> bool:
        return word in self.counts

    def __len__(self) -> int:
        return len(self.counts)

    @property
    def words(self) -> set:
        return set(self.counts)

    def frequency(self, word: str) -> float:
        return self.counts.get(word, 0) / self.total if self.total else 0.0

    def rank(self, word: str) -> int:
        if self._ranks is None:
            self._ranks = {w: i + 1 for i, (w, _) in enumerate(self.counts.most_common())}
        return self._ranks.get(word, 0)

    def weight(self, word: str) -> float:
        """Information content in bits: how surprising this word is.

        Matching ``et`` in Latin proves almost nothing because ``et`` is
        everywhere.  Matching ``pharmacum`` is real evidence.  Weighting every
        hit by -log2(probability) makes the score reflect that.
        """
        if self._weights is None:
            self._weights = {}
        cached = self._weights.get(word)
        if cached is not None:
            return cached
        count = self.counts.get(word, 0)
        value = math.log2(self.total / count) if count else 0.0
        self._weights[word] = value
        return value

    def mean_weight(self) -> float:
        """Average information per word in this language, in bits.

        This is the unigram entropy of the dictionary, and it is the natural
        denominator for weighted coverage: it says how many bits a real text of
        this language carries per word, so the score becomes "what fraction of
        the expected information did the matches actually account for".
        """
        if not self.total:
            return 0.0
        cached = getattr(self, "_mean_weight", None)
        if cached is None:
            cached = sum(
                (count / self.total) * math.log2(self.total / count) for count in self.counts.values() if count
            )
            object.__setattr__(self, "_mean_weight", cached)
        return cached

    def stopwords(self, n: int = 40) -> list:
        return [w for w, _ in self.counts.most_common(n)]

    def most_common(self, n: int = 20) -> list:
        return self.counts.most_common(n)

    def subset(self, predicate) -> Dictionary:
        return Dictionary(
            name=self.name,
            counts=Counter({w: c for w, c in self.counts.items() if predicate(w)}),
            description=self.description,
        )


def _parse_frequency_file(text: str, name: str) -> Dictionary:
    counts: Counter = Counter()
    description = ""
    for line in text.splitlines():
        if line.startswith("#"):
            if not description:
                description = line.lstrip("# ").strip()
            continue
        if not line.strip():
            continue
        parts = line.split("\t")
        word = parts[0].strip()
        if not word:
            continue
        counts[word] += int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 1
    return Dictionary(name=name, counts=counts, description=description)


def available_dictionaries() -> list:
    """Every dictionary TVTT can load: bundled ones plus your own files."""
    found = {}
    for directory in data_dirs("dictionaries"):
        for path in sorted(directory.glob("*.txt")):
            found.setdefault(path.stem, str(path))
    reference = ws("reference_texts")
    if reference.is_dir():
        for path in sorted(reference.glob("*.txt")):
            found.setdefault(path.stem, str(path))
    return sorted(found.items())


def load_dictionary(name: str, folder: str = "reference_texts") -> Dictionary:
    """Load a bundled dictionary by language name, or any ``.txt`` by path."""
    candidate = Path(name)
    if candidate.exists() and candidate.is_file():
        return _load_path(candidate)

    local = ws(folder, name if name.endswith(".txt") else name + ".txt")
    if local.exists():
        return _load_path(local)

    bundled = data_file("dictionaries", name + ".txt")
    if bundled.exists():
        return _load_path(bundled)

    raise DataError(
        "no dictionary called %r" % name,
        hint="Bundled: %s. You can also put a .txt file in %s/." % (", ".join(BUNDLED_LANGUAGES), folder),
    )


def _load_path(path: Path) -> Dictionary:
    text = read_text(path)
    head = text[:400]
    if "\t" in head or head.startswith("#"):
        return _parse_frequency_file(text, path.stem)
    return Dictionary(name=path.stem, counts=Counter(tokenize(text)), description="user text: %s" % path.name)


def load_reference_folder(folder: str = "reference_texts") -> Dictionary:
    """Merge every ``.txt`` in the user's reference folder into one dictionary."""
    directory = ws(folder)
    if not directory.is_dir():
        raise DataError(
            "reference folder %s does not exist" % directory,
            hint="Create it and drop dictionary or prose .txt files inside, or set reference.language "
            "in config.json to use a bundled dictionary instead.",
        )
    files = sorted(directory.glob("*.txt"))
    if not files:
        raise DataError(
            "no .txt files in %s" % directory,
            hint="Add a word list or a body of prose in the target language.",
        )
    counts: Counter = Counter()
    for path in files:
        counts.update(_load_path(path).counts)
    return Dictionary(name=folder, counts=counts, description="merged from %d file(s) in %s" % (len(files), folder))


# --------------------------------------------------------------------------
# Medieval Latin abbreviations
# --------------------------------------------------------------------------

#: Scribal shorthand a fifteenth-century Latin text is full of.  Each entry is
#: (pattern, replacements): the pattern is what appears on the page, the
#: replacements are what it may stand for.
LATIN_ABBREVIATIONS = (
    ("9", ("us", "con")),
    ("~", ("m", "n")),
    ("=", ("m", "n")),
    ("̄", ("m", "n")),
    ("̅", ("m", "n")),
    ("q;", ("que",)),
    ("q3", ("que",)),
    ("p̄", ("pre", "prae")),
    ("ꝑ", ("per", "par")),
    ("ꝓ", ("pro",)),
    ("ꝗ", ("qui",)),
    ("&", ("et",)),
    ("ā", ("am", "an")),
    ("ē", ("em", "en")),
    ("ī", ("im", "in")),
    ("ō", ("om", "on")),
    ("ū", ("um", "un")),
    ("ñ", ("non", "nn")),
    ("ħ", ("hab",)),
    ("ꝯ", ("con", "com", "us")),
)

#: Contractions written with a suspension stroke over the whole word.
LATIN_CONTRACTIONS = {
    "dns": "dominus",
    "dni": "domini",
    "dno": "domino",
    "ds": "deus",
    "di": "dei",
    "do": "deo",
    "xps": "christus",
    "xpi": "christi",
    "spu": "spiritu",
    "sps": "spiritus",
    "scs": "sanctus",
    "sci": "sancti",
    "nr": "noster",
    "nri": "nostri",
    "oms": "omnes",
    "oia": "omnia",
    "epc": "episcopus",
    "gra": "gratia",
    "mia": "misericordia",
    "hoc": "hoc",
    "ihs": "iesus",
    "aia": "anima",
    "aiam": "animam",
}


def expand_abbreviations(word: str, limit: int = 24) -> list:
    """Every reading a medieval abbreviation could stand for.

    ``natu9`` expands to ``natuus`` and ``natucon``; ``dns`` to ``dominus``.
    The list always contains the original spelling first, so a caller can treat
    expansion as purely additive.
    """
    results = [word]
    if word in LATIN_CONTRACTIONS:
        results.append(LATIN_CONTRACTIONS[word])

    frontier = [word]
    for pattern, replacements in LATIN_ABBREVIATIONS:
        if not any(pattern in candidate for candidate in frontier):
            continue
        grown = []
        for candidate in frontier:
            if pattern in candidate:
                for replacement in replacements:
                    grown.append(candidate.replace(pattern, replacement, 1))
            else:
                grown.append(candidate)
        frontier = grown[:limit]
        results.extend(frontier)

    seen = set()
    unique = []
    for item in results:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
        if len(unique) >= limit:
            break
    return unique


# --------------------------------------------------------------------------
# Stemming
# --------------------------------------------------------------------------

#: Deliberately light suffix lists: enough to fold inflection, not enough to
#: start matching unrelated words to each other.
STEM_SUFFIXES = {
    "latin": (
        "ibus",
        "orum",
        "arum",
        "atis",
        "itis",
        "erunt",
        "isse",
        "ere",
        "are",
        "ire",
        "que",
        "ium",
        "ius",
        "ibi",
        "am",
        "as",
        "em",
        "es",
        "im",
        "is",
        "om",
        "os",
        "um",
        "us",
        "ae",
        "is",
        "it",
        "at",
        "et",
        "ur",
        "or",
        "a",
        "e",
        "i",
        "o",
        "u",
        "m",
        "s",
    ),
    "italian": (
        "issimo",
        "issima",
        "mente",
        "zione",
        "ando",
        "endo",
        "are",
        "ere",
        "ire",
        "ato",
        "ata",
        "ite",
        "iti",
        "o",
        "a",
        "e",
        "i",
    ),
    "english": ("ational", "ization", "ing", "edly", "ness", "ment", "ed", "es", "ly", "s"),
    "middle_english": ("eth", "est", "ing", "en", "es", "ed", "e", "s"),
    "middle_high_german": ("ent", "est", "et", "en", "er", "es", "e"),
    "czech": ("ovat", "ymi", "ami", "ich", "em", "ou", "ym", "y", "u", "e", "a", "i", "o"),
    "occitan": ("ament", "ada", "ats", "ar", "er", "ir", "as", "os", "a", "e", "o", "s"),
    "hebrew": (),
    "hebrew_latin": (),
    "arabic": (),
    "arabic_latin": (),
}


@dataclass
class Stemmer:
    """Strip inflectional endings so related forms compare equal."""

    language: str = "latin"
    min_stem: int = 3

    def __post_init__(self) -> None:
        self.suffixes = tuple(sorted(STEM_SUFFIXES.get(self.language, STEM_SUFFIXES["latin"]), key=len, reverse=True))

    def stem(self, word: str) -> str:
        for suffix in self.suffixes:
            if len(word) - len(suffix) >= self.min_stem and word.endswith(suffix):
                return word[: -len(suffix)]
        return word

    def index(self, words: Iterable) -> dict:
        """Map each stem to the full forms that share it."""
        out: dict = {}
        for word in words:
            out.setdefault(self.stem(word), []).append(word)
        return out


# --------------------------------------------------------------------------
# Abjad mode
# --------------------------------------------------------------------------

DEFAULT_VOWELS = "aeiouyāēīōūàèéìòùâêîôû"


def consonant_skeleton(word: str, vowels: str = DEFAULT_VOWELS) -> str:
    """Drop the vowels, the way an abjad writes.

    If your mapping produces consonants only - as it must for a Hebrew or
    Arabic hypothesis - then the fair comparison is against the consonant
    skeleton of the dictionary, not its full spelling.
    """
    vowel_set = set(vowels)
    return "".join(ch for ch in word if ch not in vowel_set)


def abjad_index(words: Iterable, vowels: str = DEFAULT_VOWELS) -> dict:
    out: dict = {}
    for word in words:
        out.setdefault(consonant_skeleton(word, vowels), []).append(word)
    return out


# --------------------------------------------------------------------------
# Edit distances
# --------------------------------------------------------------------------


def levenshtein(a: str, b: str, limit: int = 99) -> int:
    """Edit distance with early exit once ``limit`` is exceeded."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    if len(a) > len(b):
        a, b = b, a
    previous = list(range(len(a) + 1))
    for j, cb in enumerate(b, 1):
        current = [j]
        best = j
        for i, ca in enumerate(a, 1):
            value = min(previous[i] + 1, current[i - 1] + 1, previous[i - 1] + (ca != cb))
            current.append(value)
            if value < best:
                best = value
        if best > limit:
            return limit + 1
        previous = current
    return previous[-1]


def damerau_levenshtein(a: str, b: str, limit: int = 99) -> int:
    """Edit distance that also counts a swap of two neighbours as one edit.

    Transpositions matter here: a mapping that gets two glyphs the right
    letters but the wrong way round is much closer to correct than one that
    got both wrong, and plain Levenshtein charges it two edits.
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        row_best = limit + 1
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            value = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                value = min(value, d[i - 2][j - 2] + 1)
            d[i][j] = value
            if value < row_best:
                row_best = value
        if row_best > limit:
            return limit + 1
    return d[la][lb]


def similarity(a: str, b: str, distance: int = None) -> float:
    """Turn an edit distance into a 0-1 similarity."""
    if distance is None:
        distance = levenshtein(a, b)
    longest = max(len(a), len(b)) or 1
    return max(0.0, 1.0 - distance / longest)


# --------------------------------------------------------------------------
# Phonetic matching
# --------------------------------------------------------------------------

_METAPHONE_VOWELS = "AEIOU"


def metaphone(word: str) -> str:
    """A compact Metaphone implementation for Latin-script words.

    Phonetic keys catch the case where a mapping produces a plausible *sound*
    with an implausible spelling - ``ph`` for ``f``, ``c`` for ``k`` - which
    edit distance alone treats as a miss.
    """
    text = re.sub(r"[^A-Z]", "", word.upper())
    if not text:
        return ""
    if text[:2] in ("AE", "GN", "KN", "PN", "WR"):
        text = text[1:]
    elif text[:1] == "X":
        text = "S" + text[1:]
    elif text[:2] == "WH":
        text = "W" + text[2:]

    out = []
    i = 0
    n = len(text)
    while i < n and len(out) < 12:
        ch = text[i]
        prev = text[i - 1] if i else ""
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == prev and ch != "C":
            i += 1
            continue
        if ch in _METAPHONE_VOWELS:
            if i == 0:
                out.append(ch)
        elif ch == "B":
            if not (i == n - 1 and prev == "M"):
                out.append("B")
        elif ch == "C":
            if nxt == "I" and text[i + 2 : i + 3] == "A":
                out.append("X")
            elif nxt == "H":
                out.append("X")
                i += 1
            elif nxt in "IEY":
                out.append("S")
            else:
                out.append("K")
        elif ch == "D":
            if nxt == "G" and text[i + 2 : i + 3] in "EYI":
                out.append("J")
                i += 2
            else:
                out.append("T")
        elif ch == "G":
            if nxt == "H":
                if not (i + 2 >= n or text[i + 2] in _METAPHONE_VOWELS):
                    i += 1
                else:
                    out.append("K")
                    i += 1
            elif nxt == "N":
                pass
            elif nxt in "IEY":
                out.append("J")
            else:
                out.append("K")
        elif ch == "H":
            if prev in _METAPHONE_VOWELS and nxt not in _METAPHONE_VOWELS:
                pass
            else:
                out.append("H")
        elif ch in "FJLMNR":
            out.append(ch)
        elif ch == "K":
            if prev != "C":
                out.append("K")
        elif ch == "P":
            if nxt == "H":
                out.append("F")
                i += 1
            else:
                out.append("P")
        elif ch == "Q":
            out.append("K")
        elif ch == "S":
            if nxt == "H":
                out.append("X")
                i += 1
            elif nxt == "I" and text[i + 2 : i + 3] in "OA":
                out.append("X")
            else:
                out.append("S")
        elif ch == "T":
            if nxt == "H":
                out.append("0")
                i += 1
            elif nxt == "I" and text[i + 2 : i + 3] in "OA":
                out.append("X")
            else:
                out.append("T")
        elif ch == "V":
            out.append("F")
        elif ch == "W" or ch == "Y":
            if nxt in _METAPHONE_VOWELS:
                out.append(ch)
        elif ch == "X":
            out.append("KS")
        elif ch == "Z":
            out.append("S")
        i += 1
    return "".join(out)


def soundex(word: str) -> str:
    """The classic Soundex key, offered as a cheaper phonetic alternative."""
    text = re.sub(r"[^A-Z]", "", word.upper())
    if not text:
        return ""
    codes = {
        **dict.fromkeys("BFPV", "1"),
        **dict.fromkeys("CGJKQSXZ", "2"),
        **dict.fromkeys("DT", "3"),
        "L": "4",
        **dict.fromkeys("MN", "5"),
        "R": "6",
    }
    out = text[0]
    last = codes.get(text[0], "")
    for ch in text[1:]:
        code = codes.get(ch, "")
        if code and code != last:
            out += code
        if ch not in "HW":
            last = code
        if len(out) == 4:
            break
    return out.ljust(4, "0")


# --------------------------------------------------------------------------
# Fast fuzzy lookup
# --------------------------------------------------------------------------


class FuzzyIndex:
    """Find dictionary words within a small edit distance, quickly and completely.

    A naive search compares every query against every dictionary entry, which
    is tens of millions of comparisons for one run.  Instead words are indexed
    by their character q-grams and filtered by the standard q-gram counting
    bound: a string of length n has n - q + 1 q-grams, one edit disturbs at
    most q of them, so two strings within k edits must share at least
    ``(n - q + 1) - k * q``.  Anything below that cannot be close enough and is
    never compared properly.

    The bound only helps while it stays above zero.  For short words and a
    generous edit budget it goes negative and the filter stops guaranteeing
    anything: ``aenea`` and ``arena`` are two edits apart and share no trigram
    at all.  So the index keeps both a trigram and a bigram table, uses the
    largest q that is still sound for the query at hand, and falls back to
    scanning the words of a compatible length when neither is.  That keeps the
    results identical to a brute-force search while doing a small fraction of
    the work.
    """

    __slots__ = ("words", "indexes", "by_length", "grams", "distance_fn", "_length_keys")

    def __init__(self, words: Iterable, grams: Sequence = (3, 2), transpositions: bool = True) -> None:
        self.grams = tuple(sorted(grams, reverse=True))
        self.words = list(words)
        self.distance_fn = damerau_levenshtein if transpositions else levenshtein
        self.indexes = {q: {} for q in self.grams}
        self.by_length: dict = {}
        for i, word in enumerate(self.words):
            self.by_length.setdefault(len(word), []).append(i)
            for q in self.grams:
                index = self.indexes[q]
                for piece in self._grams(word, q):
                    index.setdefault(piece, []).append(i)
        self._length_keys = sorted(self.by_length)

    def _grams(self, word: str, q: int) -> set:
        padded = "^" + word + "$"
        if len(padded) <= q:
            return {padded}
        return {padded[i : i + q] for i in range(len(padded) - q + 1)}

    def _sound_gram_size(self, word: str, max_edits: int) -> int:
        """The largest q whose counting bound still excludes anything."""
        for q in self.grams:
            count = max(1, len(word) + 2 - q + 1)
            if count - max_edits * q >= 1:
                return q
        return 0

    def candidates(self, word: str, max_edits: int) -> list:
        """Every word that could be within ``max_edits`` edits of ``word``."""
        if not max_edits:
            q = self.grams[0]
            grams = self._grams(word, q)
            hits: Counter = Counter()
            for piece in grams:
                for i in self.indexes[q].get(piece, ()):
                    hits[i] += 1
            return [i for i, count in hits.items() if count >= len(grams)]

        q = self._sound_gram_size(word, max_edits)
        if not q:
            # No q-gram filter is sound here, so take every word whose length
            # is compatible. For the short words this happens to, that band is
            # small, and correctness matters more than the saving.
            out = []
            for length in range(len(word) - max_edits, len(word) + max_edits + 1):
                out.extend(self.by_length.get(length, ()))
            return out

        grams = self._grams(word, q)
        hits = Counter()
        index = self.indexes[q]
        for piece in grams:
            for i in index.get(piece, ()):  # noqa: PLC0206 - hot loop
                hits[i] += 1
        threshold = max(1, len(grams) - max_edits * q)
        return [i for i, count in hits.items() if count >= threshold]

    def search(self, word: str, max_edits: int = 2, limit: int = 5) -> list:
        """Return ``(word, distance)`` pairs sorted by distance."""
        best = []
        for i in self.candidates(word, max_edits):
            candidate = self.words[i]
            if abs(len(candidate) - len(word)) > max_edits:
                continue
            distance = self.distance_fn(word, candidate, max_edits)
            if distance <= max_edits:
                best.append((candidate, distance))
        best.sort(key=lambda pair: (pair[1], len(pair[0]), pair[0]))
        return best[:limit]

    def best(self, word: str, max_edits: int = 2):
        """The closest word within ``max_edits``, or ``None``.

        The search escalates: distance 0 first, then 1, and so on. A nearer
        match always wins anyway, and the cheap sound filters at low distances
        answer most queries, so the expensive wide search only has to run for
        words that really do have no close neighbour.
        """
        for budget in range(max_edits + 1):
            hits = self.search(word, budget, limit=1)
            if hits:
                return hits[0]
        return None


def build_phonetic_index(words: Iterable, algorithm: str = "metaphone") -> dict:
    encode = metaphone if algorithm == "metaphone" else soundex
    out: dict = {}
    for word in words:
        out.setdefault(encode(word), []).append(word)
    return out


# --------------------------------------------------------------------------
# Word splitting
# --------------------------------------------------------------------------


def split_word(word: str, vocabulary: set, min_part: int = 2, max_parts: int = 3) -> list:
    """Break a long unknown word into known ones.

    The inverse of merging: Voynich word boundaries are not reliable, so a
    single token may be two words run together, or one word split in two.
    """
    n = len(word)
    if n < min_part * 2:
        return []

    best: list = []

    def walk(start: int, parts: list) -> None:
        nonlocal best
        if best:
            return
        if start == n:
            if len(parts) > 1:
                best = list(parts)
            return
        if len(parts) >= max_parts:
            return
        for end in range(n, start + min_part - 1, -1):
            piece = word[start:end]
            if piece in vocabulary:
                parts.append(piece)
                walk(end, parts)
                parts.pop()
                if best:
                    return

    walk(0, [])
    return best
