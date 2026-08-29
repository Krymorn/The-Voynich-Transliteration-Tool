"""Character n-gram language models, and the fitness functions built on them.

Solving a substitution cipher automatically needs one thing above all: a fast,
honest answer to "how much does this text look like Latin?".  The standard
answer is a quadgram log-likelihood score - add up the log probability of every
four-character sequence under a model built from real text.  Wrong mappings
produce sequences the model has never seen and are punished heavily; right ones
are not.

Models are built from the bundled control texts (or any text you supply),
cached on disk, and scored word by word so that word boundaries count as real
context.  Scoring is deliberately additive over word types, which is what lets
the solver re-score only the words a changed rule actually touched.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from . import cache
from .errors import DataError
from .lexicon import Dictionary, load_dictionary, tokenize
from .paths import data_dirs, data_file, ws
from .util import read_text, sha256_text

BOUNDARY = "_"

FITNESS_FUNCTIONS = ("quadgram", "trigram", "bigram", "dictionary", "entropy", "blend")

FITNESS_DESCRIPTIONS = {
    "quadgram": "Log-likelihood of every 4-character sequence under a model of the target language. The standard measure for substitution ciphers.",
    "trigram": "The same, using 3-character sequences. Faster and less brittle on small models.",
    "bigram": "The same, using character pairs. Very fast, much weaker.",
    "dictionary": "The fraction of output words found in the target dictionary, weighted by how informative each word is.",
    "entropy": "How close the output's conditional entropy is to the target language's. Rewards realistic structure rather than realistic words.",
    "blend": "A weighted mix of quadgram, dictionary and entropy scores.",
}


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------


@dataclass
class NgramModel:
    """Log probabilities of character n-grams in a target language."""

    order: int
    language: str
    logs: dict
    floor: float
    total: int
    alphabet: str

    def score_word(self, word: str) -> float:
        """Log-likelihood of one word, padded with word boundaries.

        This is the innermost loop of the solver, called hundreds of thousands
        of times a second, so it is written flat: locals instead of attribute
        lookups, and a list comprehension inside ``sum`` rather than a Python
        loop with an accumulator.
        """
        token = BOUNDARY + word + BOUNDARY
        n = self.order
        length = len(token) - n + 1
        if length < 1:
            return self.floor
        get = self.logs.get
        floor = self.floor
        return sum([get(token[i : i + n], floor) for i in range(length)])

    def score_words(self, words: Iterable) -> float:
        return sum(self.score_word(word) for word in words)

    def score_text(self, text: str) -> float:
        n = self.order
        logs = self.logs
        floor = self.floor
        return sum(logs.get(text[i : i + n], floor) for i in range(len(text) - n + 1))

    def normalised(self, words: Sequence) -> float:
        """Score per character, so texts of different lengths compare."""
        characters = sum(len(w) + 1 for w in words) or 1
        return self.score_words(words) / characters


def build_model(words: Sequence, order: int = 4, language: str = "") -> NgramModel:
    """Count n-grams in a word list and turn them into log probabilities."""
    counts: Counter = Counter()
    for word in words:
        token = BOUNDARY + word + BOUNDARY
        for i in range(len(token) - order + 1):
            counts[token[i : i + order]] += 1
    total = sum(counts.values())
    if not total:
        raise DataError(
            "cannot build a language model from an empty text",
            hint="Check that the control text or dictionary you pointed at has content.",
        )
    logs = {gram: math.log10(count / total) for gram, count in counts.items()}
    # Unseen n-grams get a probability an order of magnitude below the rarest
    # observed one: harsh enough to punish nonsense, not so harsh that one
    # unlucky sequence dominates the score.
    floor = math.log10(0.1 / total)
    alphabet = "".join(sorted({ch for word in words for ch in word}))
    return NgramModel(order=order, language=language, logs=logs, floor=floor, total=total, alphabet=alphabet)


def control_text(language: str) -> str:
    """Load a bundled or user-supplied control text by language name."""
    local = ws("reference_texts", language + ".txt")
    if local.exists():
        return read_text(local)
    path = data_file("controls", language + ".txt")
    if not path.exists():
        raise DataError(
            "no control text for %r" % language,
            hint="Available: " + ", ".join(available_controls()),
        )
    return read_text(path)


def available_controls() -> list:
    names = set()
    for directory in data_dirs("controls"):
        names.update(p.stem for p in directory.glob("*.txt"))
    return sorted(names)


def load_model(language: str = "latin", order: int = 4, from_dictionary: bool = False) -> NgramModel:
    """Load (and cache) an n-gram model for a target language.

    By default the model is built from the bundled running text, which carries
    real word-boundary statistics.  ``from_dictionary=True`` builds it from the
    frequency list instead, which is the right choice when you only have a word
    list for a language.
    """

    def build():
        if from_dictionary:
            dictionary = load_dictionary(language)
            words = [w for w, count in dictionary.counts.items() for _ in range(min(count, 50))]
        else:
            words = tokenize(control_text(language))
        return build_model(words, order=order, language=language)

    key_source = language + ("|dict" if from_dictionary else "|text")
    return cache.get_or_compute("ngram", [key_source, order], build)


def language_reference(language: str = "latin") -> dict:
    """Headline statistics of a control language, used as comparison targets."""

    def build():
        from .analysis import stat_bundle

        return stat_bundle(tokenize(control_text(language)), language).to_dict()

    return cache.get_or_compute("langref", [language], build)


# --------------------------------------------------------------------------
# Fitness
# --------------------------------------------------------------------------


@dataclass
class FitnessOptions:
    """Which measure the solver is trying to maximise."""

    function: str = "quadgram"
    language: str = "latin"
    order: int = 4
    from_dictionary: bool = False
    #: Weights used when ``function='blend'``.
    quadgram_weight: float = 1.0
    dictionary_weight: float = 0.6
    entropy_weight: float = 0.4

    def validate(self) -> None:
        if self.function not in FITNESS_FUNCTIONS:
            raise DataError(
                "unknown fitness function %r" % self.function,
                hint="Available: " + ", ".join(FITNESS_FUNCTIONS),
            )


class Fitness:
    """Scores a bag of mapped words, cheaply and repeatedly.

    The solver calls this tens of thousands of times, so the score is defined
    as a sum of per-word contributions::

        score = sum(count[type] * contribution(mapped[type])) / normaliser

    Written that way, changing one glyph only requires re-computing the
    contributions of the word types that contain it, and every contribution is
    cached by its mapped spelling.  A single move then costs a few dozen
    lookups rather than a full pass over the vocabulary, which is the
    difference between a solver that takes minutes and one that takes hours.

    Only the ``entropy`` fitness is not decomposable this way; it declares
    itself non-incremental and is re-scored in full.
    """

    def __init__(self, options: FitnessOptions, vocabulary: Counter) -> None:
        options.validate()
        self.options = options
        self.vocabulary = vocabulary
        self.types = list(vocabulary)
        self.counts = [vocabulary[w] for w in self.types]
        self.tokens = sum(self.counts) or 1
        self.characters = sum((len(w) + 1) * vocabulary[w] for w in self.types) or 1

        self.model = None
        self.dictionary: Dictionary = None
        self.target_entropy = 0.0
        if options.function in ("quadgram", "trigram", "bigram", "blend"):
            order = {"quadgram": 4, "trigram": 3, "bigram": 2}.get(options.function, options.order)
            self.model = load_model(options.language, order, options.from_dictionary)
        if options.function in ("dictionary", "blend"):
            self.dictionary = load_dictionary(options.language)
        if options.function in ("entropy", "blend"):
            self.target_entropy = language_reference(options.language)["h2"]

        self.incremental = options.function != "entropy"
        self.normaliser = self._normaliser()
        self._cache: dict = {}

    def _normaliser(self) -> float:
        function = self.options.function
        if function in ("quadgram", "trigram", "bigram"):
            return float(self.characters)
        if function == "dictionary":
            return float(self.tokens * (self.dictionary.mean_weight() or 1.0))
        return 1.0

    # -- per-word scoring -------------------------------------------------
    def contribution(self, mapped: str) -> float:
        """The score one occurrence of this mapped word adds."""
        cached = self._cache.get(mapped)
        if cached is not None:
            return cached
        function = self.options.function
        if function in ("quadgram", "trigram", "bigram"):
            value = self.model.score_word(mapped)
        elif function == "dictionary":
            value = self.dictionary.weight(mapped)
        elif function == "blend":
            opts = self.options
            quad = self.model.score_word(mapped) / self.characters
            weight = self.dictionary.weight(mapped)
            hit = weight / (self.tokens * (self.dictionary.mean_weight() or 1.0))
            value = opts.quadgram_weight * quad + opts.dictionary_weight * 10.0 * hit
        else:
            value = 0.0
        self._cache[mapped] = value
        return value

    def contributions(self, mapped_types: Sequence) -> list:
        """Weighted contribution of every vocabulary type, ready to sum."""
        contribution = self.contribution
        return [contribution(word) * count for word, count in zip(mapped_types, self.counts)]

    # -- whole-candidate scoring -----------------------------------------
    def score(self, mapped_types: Sequence) -> float:
        """Score a candidate given the mapped form of each vocabulary type."""
        if self.options.function == "entropy":
            from .analysis import conditional_entropy

            text = BOUNDARY.join(word for word, count in zip(mapped_types, self.counts) for _ in range(min(count, 4)))
            return -abs(conditional_entropy(text, 1) - self.target_entropy)
        return sum(self.contributions(mapped_types)) / self.normaliser

    def describe(self) -> str:
        return "%s over %s (%d word types, %d tokens)" % (
            self.options.function,
            self.options.language,
            len(self.types),
            self.tokens,
        )


def signature(options: FitnessOptions, vocabulary: Counter) -> str:
    return sha256_text("%s|%s|%d|%d" % (options.function, options.language, options.order, len(vocabulary)))
