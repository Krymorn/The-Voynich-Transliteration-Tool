"""Build the bundled control texts and reference dictionaries.

This script is how ``tvtt/data/controls`` and ``tvtt/data/dictionaries`` were
produced.  It is kept in the repository so the provenance of every bundled word
list is checkable and reproducible, not so that users have to run it.

Sources (all public domain):

* Project Gutenberg, via https://gutendex.com  - Latin, Italian, English,
  Middle English, Middle High German, Czech, Occitan.
* Sefaria (https://www.sefaria.org/api) - the Hebrew Torah, consonantal after
  the vowel points and cantillation marks are stripped.
* alquran.cloud - the Arabic text of the Quran, consonantal after diacritics
  are stripped.

Run with::

    python tools/build_reference_data.py --download --build
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".work" / "gutenberg"
CONTROLS = ROOT / "tvtt" / "data" / "controls"
DICTIONARIES = ROOT / "tvtt" / "data" / "dictionaries"

USER_AGENT = {"User-Agent": "TVTT/2.0 reference-data-builder"}

GUTENBERG = {
    "latin": [
        (227, "Vergil, Aeneid"),
        (33849, "Augustine, Confessiones"),
        (27049, "Linnaeus, Species Plantarum IV-V"),
    ],
    "italian": [(1012, "Dante, La Divina Commedia")],
    "english": [(1342, "Austen, Pride and Prejudice"), (10, "The King James Bible")],
    "middle_english": [(2383, "Chaucer, The Canterbury Tales")],
    "middle_high_german": [(35795, "Walther von der Vogelweide, Gedichte und Sprueche")],
    "czech": [(13083, "Capek, R.U.R.")],
    "occitan": [(17544, "Lou catounet gascoun")],
}

#: Several Gutenberg editions print an original next to a modern translation or
#: an editor's introduction.  A line is dropped when too many of its words are
#: function words of the contaminating language, which removes the apparatus
#: without touching the text itself.
CONTAMINANTS = {
    "latin": "the of and to in a is that it was he for on with as his be by not are this",
    "middle_english": "",
    "middle_high_german": (
        "und der die das ist nicht auch aber eine einen einem dem den des wird wurde "
        "haben hat sich schon nach uber durch dieser diese dieses"
    ),
    "occitan": (
        "le la les des du de et il elle nous vous ils elles dans pour avec sur que qui "
        "est sont etait cette ces mais tout tous"
    ),
    "czech": "",
    "italian": "",
    "english": "",
}
CONTAMINANT_SHARE = 0.34

#: Maximum characters kept in a bundled control sample.
CONTROL_LIMIT = 220_000
#: Maximum entries kept in a bundled frequency dictionary.
DICT_LIMIT = 30_000

START_MARKERS = ("*** START OF TH", "*** START OF THE PROJECT GUTENBERG")
END_MARKERS = ("*** END OF TH", "End of the Project Gutenberg", "End of Project Gutenberg")

HEBREW_LETTERS = {chr(c) for c in range(0x05D0, 0x05EB)}
ARABIC_LETTERS = {chr(c) for c in range(0x0621, 0x064B)} | {"ٱ"}

HEBREW_TRANSLITERATION = {
    "א": "'",
    "ב": "b",
    "ג": "g",
    "ד": "d",
    "ה": "h",
    "ו": "w",
    "ז": "z",
    "ח": "x",
    "ט": "T",
    "י": "y",
    "ך": "k",
    "כ": "k",
    "ל": "l",
    "ם": "m",
    "מ": "m",
    "ן": "n",
    "נ": "n",
    "ס": "s",
    "ע": "`",
    "ף": "p",
    "פ": "p",
    "ץ": "c",
    "צ": "c",
    "ק": "q",
    "ר": "r",
    "ש": "$",
    "ת": "t",
}

ARABIC_TRANSLITERATION = {
    "ء": "'",
    "آ": "a",
    "أ": "'",
    "ؤ": "'",
    "إ": "'",
    "ئ": "'",
    "ا": "a",
    "ب": "b",
    "ة": "t",
    "ت": "t",
    "ث": "v",
    "ج": "j",
    "ح": "H",
    "خ": "x",
    "د": "d",
    "ذ": "V",
    "ر": "r",
    "ز": "z",
    "س": "s",
    "ش": "$",
    "ص": "S",
    "ض": "D",
    "ط": "T",
    "ظ": "Z",
    "ع": "`",
    "غ": "g",
    "ف": "f",
    "ق": "q",
    "ك": "k",
    "ل": "l",
    "م": "m",
    "ن": "n",
    "ه": "h",
    "و": "w",
    "ى": "y",
    "ي": "y",
    "ٱ": "a",
}


def fetch(url: str, timeout: int = 90) -> bytes:
    request = urllib.request.Request(url, headers=USER_AGENT)
    return urllib.request.urlopen(request, timeout=timeout).read()


def download_all() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    for language, books in GUTENBERG.items():
        for book_id, title in books:
            target = WORK / ("%s_%d.txt" % (language, book_id))
            if target.exists():
                print("have", target.name)
                continue
            for pattern in (
                "https://www.gutenberg.org/cache/epub/%d/pg%d.txt" % (book_id, book_id),
                "https://www.gutenberg.org/files/%d/%d-0.txt" % (book_id, book_id),
            ):
                try:
                    target.write_bytes(fetch(pattern))
                    print("downloaded", target.name, title)
                    break
                except Exception as exc:
                    last = exc
            else:
                print("FAILED", language, book_id, last, file=sys.stderr)

    hebrew = WORK / "hebrew_torah.txt"
    if not hebrew.exists():
        verses = []
        for book, chapters in (("Genesis", 50), ("Exodus", 40), ("Leviticus", 27)):
            for chapter in range(1, chapters + 1):
                try:
                    payload = json.loads(
                        fetch("https://www.sefaria.org/api/texts/%s.%d?context=0" % (book, chapter)).decode()
                    )
                except Exception:
                    continue
                value = payload.get("he") or []
                verses.extend([value] if isinstance(value, str) else value)
        hebrew.write_text("\n".join(re.sub(r"<[^>]*>", "", v) for v in verses), encoding="utf-8")
        print("downloaded", hebrew.name, len(verses), "verses")

    arabic = WORK / "arabic_quran.txt"
    if not arabic.exists():
        payload = json.loads(fetch("https://api.alquran.cloud/v1/quran/quran-simple").decode())
        lines = [a["text"] for s in payload["data"]["surahs"] for a in s["ayahs"]]
        arabic.write_text("\n".join(lines), encoding="utf-8")
        print("downloaded", arabic.name, len(lines), "verses")


def strip_gutenberg(text: str) -> str:
    lowered = text
    start = 0
    for marker in START_MARKERS:
        idx = lowered.find(marker)
        if idx >= 0:
            start = lowered.find("\n", idx) + 1
            break
    end = len(lowered)
    for marker in END_MARKERS:
        idx = lowered.find(marker, start)
        if idx > 0:
            end = idx
            break
    return text[start:end]


def clean_latin_script(text: str) -> str:
    text = re.sub(r"\[[^\]]{0,80}\]", " ", text)
    text = re.sub(r"[_*#]", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def drop_contaminated_lines(text: str, contaminants: str) -> str:
    """Remove lines that are mostly written in another language."""
    stop = set(contaminants.split())
    if not stop:
        return text
    kept = []
    for line in text.splitlines():
        tokens = tokenize(line)
        if len(tokens) >= 4:
            share = sum(1 for t in tokens if t in stop) / len(tokens)
            if share >= CONTAMINANT_SHARE:
                continue
        kept.append(line)
    return "\n".join(kept)


def _keep_letters(text: str, letters: set) -> str:
    """Keep the consonants and the word breaks; delete everything else.

    Vowel points and cantillation marks sit *between* consonants, so they must
    be deleted rather than replaced by a space, or every word falls apart into
    single letters.
    """
    newline = chr(10)
    out = []
    for ch in text:
        if ch in letters:
            out.append(ch)
        elif unicodedata.category(ch).startswith("M"):
            # A combining mark: a vowel point or cantillation sign. Delete it
            # without leaving a gap, or every word breaks into single letters.
            continue
        elif ch.isspace():
            out.append(newline if ch == newline else " ")
        elif out and out[-1] not in (" ", newline):
            out.append(" ")
    return "".join(out)


def strip_hebrew(text: str) -> str:
    return _keep_letters(text, HEBREW_LETTERS)


def strip_arabic(text: str) -> str:
    return _keep_letters(unicodedata.normalize("NFKD", text), ARABIC_LETTERS)


def transliterate(text: str, table: dict) -> str:
    return "".join(table.get(ch, " " if not ch.isspace() else ch) for ch in text)


TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def tokenize(text: str) -> list:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def tokenize_symbols(text: str) -> list:
    return [t for t in re.split(r"\s+", text) if t]


def write_control(name: str, text: str) -> None:
    CONTROLS.mkdir(parents=True, exist_ok=True)
    trimmed = text.strip()[:CONTROL_LIMIT]
    (CONTROLS / (name + ".txt")).write_text(trimmed, encoding="utf-8")
    print("control  %-22s %7d chars" % (name, len(trimmed)))


def write_dictionary(name: str, tokens: list, description: str) -> None:
    DICTIONARIES.mkdir(parents=True, exist_ok=True)
    counts = Counter(tokens)
    lines = ["# %s" % description, "# word<TAB>count, most frequent first"]
    for word, count in counts.most_common(DICT_LIMIT):
        if len(word) > 1 or word in ("a", "e", "i", "o", "u", "y", "à", "è", "é", "ó", "ù"):
            lines.append("%s\t%d" % (word, count))
    (DICTIONARIES / (name + ".txt")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("dict     %-22s %7d types from %d tokens" % (name, len(counts), len(tokens)))


def build_all() -> None:
    for language, books in GUTENBERG.items():
        chunks = []
        for book_id, _title in books:
            path = WORK / ("%s_%d.txt" % (language, book_id))
            if not path.exists():
                continue
            raw = path.read_bytes()
            for encoding in ("utf-8", "cp1252", "latin-1"):
                try:
                    decoded = raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            chunks.append(clean_latin_script(strip_gutenberg(decoded)))
        if not chunks:
            print("skipping", language, "(no source)", file=sys.stderr)
            continue
        text = drop_contaminated_lines("\n\n".join(chunks), CONTAMINANTS.get(language, ""))
        write_control(language, text)
        titles = "; ".join(t for _i, t in books)
        write_dictionary(
            language,
            tokenize(text),
            "%s word frequencies from: %s (Project Gutenberg, public domain)" % (language, titles),
        )

    hebrew = WORK / "hebrew_torah.txt"
    if hebrew.exists():
        raw = hebrew.read_text(encoding="utf-8")
        consonantal = strip_hebrew(raw)
        write_control("hebrew", consonantal)
        write_dictionary(
            "hebrew",
            tokenize_symbols(consonantal),
            "Consonantal Hebrew word frequencies from the Torah (Sefaria, public domain)",
        )
        latinised = transliterate(consonantal, HEBREW_TRANSLITERATION)
        write_control("hebrew_latin", latinised)
        write_dictionary(
            "hebrew_latin",
            tokenize_symbols(latinised),
            "The same Hebrew vocabulary in a one-to-one Latin transliteration, for consonant-only mappings",
        )

    arabic = WORK / "arabic_quran.txt"
    if arabic.exists():
        raw = arabic.read_text(encoding="utf-8")
        consonantal = strip_arabic(raw)
        write_control("arabic", consonantal)
        write_dictionary(
            "arabic",
            tokenize_symbols(consonantal),
            "Consonantal Arabic word frequencies from the Quran (alquran.cloud, public domain)",
        )
        latinised = transliterate(consonantal, ARABIC_TRANSLITERATION)
        write_control("arabic_latin", latinised)
        write_dictionary(
            "arabic_latin",
            tokenize_symbols(latinised),
            "The same Arabic vocabulary in a one-to-one Latin transliteration, for consonant-only mappings",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="fetch the source texts")
    parser.add_argument("--build", action="store_true", help="build controls and dictionaries")
    args = parser.parse_args()
    if args.download:
        download_all()
    if args.build or not args.download:
        build_all()


if __name__ == "__main__":
    main()
