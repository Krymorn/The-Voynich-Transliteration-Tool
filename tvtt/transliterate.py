"""Running a mapping over a corpus and holding the result.

:class:`Result` is what every plugin receives.  It keeps the selected corpus,
the compiled engine and the mapped text side by side, so an analysis can always
get back from a suspicious output word to the folio and line it came from.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .corpus import Corpus
from .logging_util import get_logger
from .mapping import Mapping, MappingEngine
from .util import Timer

_log = get_logger("transliterate")


@dataclass
class Result:
    """The transliterated text plus everything needed to explain it."""

    corpus: Corpus
    engine: MappingEngine
    lines: list
    word_separator: str = " "
    uncertain_separator: str = " "
    elapsed: float = 0.0
    _words: list = field(default=None, repr=False)
    _counts: Counter = field(default=None, repr=False)

    # -- text views ------------------------------------------------------
    def text(self) -> str:
        """The full transliteration, one manuscript line per output line."""
        return "\n".join(self.lines)

    def words(self) -> list:
        if self._words is None:
            self._words = self.engine.map_words(self.corpus.words())
        return self._words

    def word_counts(self) -> Counter:
        if self._counts is None:
            self._counts = Counter(self.words())
        return self._counts

    def line_words(self) -> list:
        return [self.engine.map_words(words) for words in self.corpus.line_words()]

    def letters(self) -> str:
        """Every output character with word separators removed."""
        return "".join(self.words())

    def letter_counts(self) -> Counter:
        return Counter(self.letters())

    # -- provenance ------------------------------------------------------
    def pairs(self):
        """Yield ``(locus, mapped_line)`` so reports can show both sides."""
        return zip(self.corpus.loci, self.lines)

    def source_words(self) -> list:
        return self.corpus.words()

    def word_pairs(self):
        """Yield ``(source_word, mapped_word)`` for every token."""
        return zip(self.corpus.words(), self.words())

    def summary(self) -> str:
        words = self.words()
        return "%d lines, %d words, %d word types, %d output characters" % (
            len(self.lines),
            len(words),
            len(set(words)),
            sum(len(w) for w in words),
        )


def transliterate(
    corpus: Corpus,
    engine: MappingEngine,
    word_separator: str = " ",
    uncertain_separator: str = " ",
) -> Result:
    """Apply ``engine`` to every selected line of ``corpus``."""
    with Timer() as timer:
        engine.register_vocabulary(set(corpus.words()))
        lines = [engine.map_line(locus.text, word_separator, uncertain_separator) for locus in corpus.loci]
    _log.debug("transliterated %d lines in %.1f ms", len(lines), timer.elapsed * 1000)
    return Result(
        corpus=corpus,
        engine=engine,
        lines=lines,
        word_separator=word_separator,
        uncertain_separator=uncertain_separator,
        elapsed=timer.elapsed,
    )


def build_engine(
    mapping: Mapping,
    corpus: Corpus,
    markers=None,
    precedence=None,
    unmapped: str = "keep",
    placeholder: str = "?",
) -> MappingEngine:
    """Compile a mapping against the glyphs actually present in a corpus."""
    from .mapping import DEFAULT_MARKERS, DEFAULT_PRECEDENCE

    return MappingEngine(
        mapping,
        glyphs=corpus.glyph_counts().keys(),
        markers=markers or DEFAULT_MARKERS,
        precedence=precedence or DEFAULT_PRECEDENCE,
        unmapped=unmapped,
        placeholder=placeholder,
    )
