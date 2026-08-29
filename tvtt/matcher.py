"""Scoring a transliteration against a real language.

Given the output of a mapping and a reference dictionary, the matcher answers
three separate questions - and keeping them separate is the point:

1. **How much of the text is real words?**  Raw coverage, and coverage weighted
   by how informative each match is, so a page of ``et in et in`` does not look
   like a decipherment.

2. **Do the common words line up?**  If a mapping is right, the words that are
   frequent in your output should be the words that are frequent in the target
   language.  A mapping that finds thousands of rare words but whose commonest
   word is not a function word has almost certainly found them by accident.

3. **How confident is each individual match?**  Every hit carries the route it
   was found by - exact, stemmed, abbreviation-expanded, merged, split,
   phonetic or fuzzy - and a confidence between 0 and 1.

A hit rate on its own means nothing.  :func:`significance` re-runs the same
scoring against random mappings so you can see how many matches pure chance
buys you with the same dictionary and the same text.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .lexicon import (
    Dictionary,
    FuzzyIndex,
    Stemmer,
    abjad_index,
    build_phonetic_index,
    consonant_skeleton,
    expand_abbreviations,
    metaphone,
    similarity,
    soundex,
    split_word,
)

MATCH_ROUTES = (
    "exact",
    "stem",
    "abbreviation",
    "abjad",
    "merge",
    "split",
    "phonetic",
    "fuzzy",
    "none",
)

#: How much to trust each route.  Exact matches are worth full marks; a fuzzy
#: match two edits away is worth much less, and the score should say so.
ROUTE_CONFIDENCE = {
    "exact": 1.00,
    "stem": 0.80,
    "abbreviation": 0.75,
    "abjad": 0.65,
    "merge": 0.60,
    "split": 0.55,
    "phonetic": 0.45,
    "fuzzy": 0.40,
    "none": 0.0,
}


@dataclass
class MatchOptions:
    """Which matching routes to allow, and how permissive to be."""

    language: str = "latin"
    max_edits: int = 1
    allow_stemming: bool = True
    allow_abbreviations: bool = False
    allow_abjad: bool = False
    allow_merge: bool = True
    allow_split: bool = True
    allow_phonetic: bool = False
    allow_fuzzy: bool = True
    phonetic_algorithm: str = "metaphone"
    transpositions: bool = True
    min_length: int = 2
    min_confidence: float = 0.0
    stopword_count: int = 30


@dataclass
class Match:
    """One decision about one output word."""

    source: str
    output: str
    matched: str
    route: str
    distance: int
    confidence: float
    weight: float
    consumed: int = 1

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "output": self.output,
            "matched": self.matched,
            "route": self.route,
            "distance": self.distance,
            "confidence": round(self.confidence, 3),
            "information_bits": round(self.weight, 2),
            "words_consumed": self.consumed,
        }


@dataclass
class MatchReport:
    """The result of scoring a whole text against a dictionary."""

    language: str
    tokens: int
    matches: list
    route_counts: Counter
    coverage: float
    weighted_coverage: float
    confidence_score: float
    information_bits: float
    stopword_coverage: float
    stopword_rows: list
    corrected_text: str
    unmatched_top: list
    matched_top: list

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "tokens": self.tokens,
            "coverage": round(self.coverage, 5),
            "weighted_coverage": round(self.weighted_coverage, 5),
            "confidence_score": round(self.confidence_score, 5),
            "total_information_bits": round(self.information_bits, 1),
            "stopword_coverage": round(self.stopword_coverage, 4),
            "routes": dict(self.route_counts),
            "most_common_matches": self.matched_top[:25],
            "most_common_misses": self.unmatched_top[:25],
            "stopword_alignment": self.stopword_rows,
        }

    def headline(self) -> str:
        return (
            "%.1f%% of words matched %s (%.1f%% weighted by rarity, "
            "confidence-weighted %.1f%%, stopword alignment %.1f%%)"
            % (
                self.coverage * 100,
                self.language,
                self.weighted_coverage * 100,
                self.confidence_score * 100,
                self.stopword_coverage * 100,
            )
        )


class Matcher:
    """Reusable matching machinery for one dictionary and one option set."""

    def __init__(self, dictionary: Dictionary, options: MatchOptions = None) -> None:
        self.dictionary = dictionary
        self.options = options or MatchOptions()
        self.vocabulary = dictionary.words
        self.stemmer = Stemmer(self.options.language)
        self._stem_index = None
        self._abjad_index = None
        self._phonetic_index = None
        self._fuzzy = None
        self._cache: dict = {}

    # -- lazily built indexes -------------------------------------------
    @property
    def stem_index(self) -> dict:
        if self._stem_index is None:
            self._stem_index = self.stemmer.index(self.vocabulary)
        return self._stem_index

    @property
    def abjad(self) -> dict:
        if self._abjad_index is None:
            self._abjad_index = abjad_index(self.vocabulary)
        return self._abjad_index

    @property
    def phonetic(self) -> dict:
        if self._phonetic_index is None:
            self._phonetic_index = build_phonetic_index(self.vocabulary, self.options.phonetic_algorithm)
        return self._phonetic_index

    @property
    def fuzzy(self) -> FuzzyIndex:
        if self._fuzzy is None:
            self._fuzzy = FuzzyIndex(sorted(self.vocabulary), transpositions=self.options.transpositions)
        return self._fuzzy

    # -- single-word matching -------------------------------------------
    def match_word(self, word: str) -> Match:
        """Try every enabled route in order of decreasing trustworthiness."""
        cached = self._cache.get(word)
        if cached is not None:
            return cached
        opts = self.options
        result = None

        if word in self.vocabulary:
            result = self._make(word, word, "exact", 0)
        elif len(word) < opts.min_length:
            result = self._make(word, "", "none", 0)
        else:
            if result is None and opts.allow_stemming:
                forms = self.stem_index.get(self.stemmer.stem(word))
                if forms:
                    result = self._make(word, forms[0], "stem", 0)
            if result is None and opts.allow_abbreviations:
                for candidate in expand_abbreviations(word)[1:]:
                    if candidate in self.vocabulary:
                        result = self._make(word, candidate, "abbreviation", 0)
                        break
            if result is None and opts.allow_abjad:
                forms = self.abjad.get(consonant_skeleton(word))
                if forms:
                    result = self._make(word, forms[0], "abjad", 0)
            if result is None and opts.allow_phonetic:
                forms = self.phonetic.get(self._encode(word))
                if forms:
                    result = self._make(word, forms[0], "phonetic", 0)
            if result is None and opts.allow_fuzzy and opts.max_edits > 0:
                hit = self.fuzzy.best(word, opts.max_edits)
                if hit:
                    result = self._make(word, hit[0], "fuzzy", hit[1])
            if result is None and opts.allow_split:
                parts = split_word(word, self.vocabulary)
                if parts:
                    result = self._make(word, " ".join(parts), "split", 0)

        if result is None:
            result = self._make(word, "", "none", 0)
        self._cache[word] = result
        return result

    def _encode(self, word: str) -> str:
        return metaphone(word) if self.options.phonetic_algorithm == "metaphone" else soundex(word)

    def _make(self, word: str, matched: str, route: str, distance: int) -> Match:
        base = ROUTE_CONFIDENCE[route]
        if route == "fuzzy" and matched:
            base *= similarity(word, matched, distance)
        elif route == "split" and matched:
            base *= min(1.0, 0.5 + 0.1 * len(matched.split()))
        weight = 0.0
        if matched:
            weight = sum(self.dictionary.weight(part) for part in matched.split()) or 0.0
        return Match(
            source=word,
            output=word,
            matched=matched,
            route=route,
            distance=distance,
            confidence=base,
            weight=weight,
        )

    # -- whole-text matching ---------------------------------------------
    def match_text(self, words: Sequence, source_words: Sequence = ()) -> MatchReport:
        opts = self.options
        matches: list = []
        corrected: list = []
        i = 0
        total = len(words)
        sources = list(source_words) if source_words else list(words)

        while i < total:
            word = words[i]
            candidate = self.match_word(word)

            # Merging is tried when the word alone matched nothing, and also
            # when it only matched weakly but the pair matches exactly: an
            # exact two-word reading beats a stemmed guess at one of them.
            merge_worth_trying = opts.allow_merge and i + 1 < total and candidate.route != "exact"
            if merge_worth_trying:
                joined = word + words[i + 1]
                merged = self.match_word(joined)
                accept = merged.route == "exact" or (
                    candidate.route == "none" and merged.route in ("stem", "abbreviation")
                )
                if accept:
                    merged = Match(
                        source=sources[i] + "+" + sources[i + 1],
                        output=joined,
                        matched=merged.matched,
                        route="merge",
                        distance=merged.distance,
                        confidence=ROUTE_CONFIDENCE["merge"],
                        weight=merged.weight,
                        consumed=2,
                    )
                    matches.append(merged)
                    corrected.append(merged.matched)
                    i += 2
                    continue

            candidate.source = sources[i] if i < len(sources) else word
            if candidate.confidence < opts.min_confidence:
                candidate = self._make(word, "", "none", 0)
                candidate.source = sources[i] if i < len(sources) else word
            matches.append(candidate)
            corrected.append(candidate.matched or word)
            i += 1

        return self._summarise(words, matches, corrected)

    def _summarise(self, words: Sequence, matches: list, corrected: list) -> MatchReport:
        tokens = len(words)
        routes = Counter(m.route for m in matches)
        hits = [m for m in matches if m.route != "none"]
        covered = sum(m.consumed for m in hits)
        coverage = covered / tokens if tokens else 0.0

        # A real text of this language carries roughly `mean_weight` bits per
        # word, so that is the fair denominator for "how much of the expected
        # information did we actually account for".
        expected = tokens * (self.dictionary.mean_weight() or 1.0)
        weighted = sum(m.weight for m in hits) / expected if expected else 0.0
        confidence_score = sum(m.confidence * m.consumed for m in hits) / tokens if tokens else 0.0
        information = sum(m.weight * m.confidence for m in hits)

        stopword_rows, stopword_coverage = self._stopword_alignment(words)

        matched_counts = Counter(m.matched for m in hits if m.matched)
        missed_counts = Counter(m.output for m in matches if m.route == "none")

        return MatchReport(
            language=self.dictionary.name,
            tokens=tokens,
            matches=matches,
            route_counts=routes,
            coverage=coverage,
            weighted_coverage=min(1.0, weighted),
            confidence_score=confidence_score,
            information_bits=information,
            stopword_coverage=stopword_coverage,
            stopword_rows=stopword_rows,
            corrected_text=" ".join(corrected),
            unmatched_top=missed_counts.most_common(60),
            matched_top=matched_counts.most_common(60),
        )

    def _stopword_alignment(self, words: Sequence) -> tuple:
        """Do the commonest output words map onto the commonest real words?

        This is the test most decipherment claims quietly fail.  A real
        substitution of a real language puts function words at the top of the
        frequency list; a mapping tuned to maximise dictionary hits usually
        does not.
        """
        n = self.options.stopword_count
        target = self.dictionary.stopwords(n)
        target_set = set(target)
        output_common = [w for w, _ in Counter(words).most_common(n)]

        rows = []
        aligned = 0
        for rank, word in enumerate(output_common, 1):
            match = self.match_word(word)
            hit = match.matched in target_set if match.matched else False
            if hit:
                aligned += 1
            rows.append(
                {
                    "rank": rank,
                    "output_word": word,
                    "matched": match.matched,
                    "route": match.route,
                    "is_target_stopword": hit,
                    "target_rank": self.dictionary.rank(match.matched) if match.matched else 0,
                }
            )
        return rows, (aligned / len(output_common) if output_common else 0.0)


# --------------------------------------------------------------------------
# Significance
# --------------------------------------------------------------------------


@dataclass
class SignificanceReport:
    """Where the real score falls in the distribution of random scores."""

    observed: float
    mean: float
    stdev: float
    z_score: float
    percentile: float
    samples: list
    metric: str

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "observed": round(self.observed, 5),
            "random_mean": round(self.mean, 5),
            "random_stdev": round(self.stdev, 5),
            "z_score": round(self.z_score, 3),
            "percentile": round(self.percentile, 2),
            "random_samples": len(self.samples),
        }

    def verdict(self) -> str:
        if self.z_score >= 4:
            return "far outside the random distribution: this is a real effect"
        if self.z_score >= 2:
            return "outside the random distribution, but not dramatically"
        if self.z_score >= 1:
            return "only slightly better than a random mapping"
        return "no better than a random mapping; the score is measuring the text, not the idea"


def significance(observed: float, random_scores: Sequence, metric: str = "coverage") -> SignificanceReport:
    """Compare one score against a sample of random-mapping scores."""
    samples = list(random_scores)
    if not samples:
        return SignificanceReport(observed, 0.0, 0.0, 0.0, 100.0, [], metric)
    mean = sum(samples) / len(samples)
    variance = sum((s - mean) ** 2 for s in samples) / len(samples)
    stdev = math.sqrt(variance)
    z = (observed - mean) / stdev if stdev else 0.0
    percentile = 100.0 * sum(1 for s in samples if s <= observed) / len(samples)
    return SignificanceReport(observed, mean, stdev, z, percentile, samples, metric)
