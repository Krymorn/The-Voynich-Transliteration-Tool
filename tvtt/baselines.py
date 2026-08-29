"""Baselines: the tools that stop you fooling yourself.

Every number a decipherment workbench produces needs something to be compared
against.  On its own, "my mapping matches 23% of Latin words" is not a result -
it is a number waiting for a control.  This module supplies four kinds:

**Random mappings.**  Score N random glyph-to-letter mappings the same way you
score yours.  If yours sits in the middle of that distribution, the score is
measuring the manuscript and the dictionary, not your hypothesis.

**Shuffled text.**  Destroy one kind of structure at a time - characters within
words, word order within lines, line order - and see which statistics survive.
A statistic that is unchanged by shuffling was never measuring what you thought.

**Synthetic Voynichese.**  Timm and Schinner showed that a simple
"copy an earlier word and change it slightly" process reproduces a great many
Voynich statistics.  Text generated that way is the strongest null hypothesis
available: if your mapping cannot tell the manuscript from this, it is not
detecting language.

**Held-out validation.**  Fit on one section, score on another.  A mapping with
enough positional and occurrence rules can be tuned to fit any text; the only
way to catch that is to score it on text it was not tuned on.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Callable

from .analysis import StatBundle, stat_bundle

# --------------------------------------------------------------------------
# Shuffles
# --------------------------------------------------------------------------

SHUFFLE_MODES = ("characters", "within_words", "words", "lines", "word_lengths")

SHUFFLE_DESCRIPTIONS = {
    "characters": "All characters shuffled globally, word lengths preserved. Destroys everything except the letter frequencies.",
    "within_words": "Each word is anagrammed. Destroys glyph order inside words but keeps the vocabulary's shape.",
    "words": "Word order shuffled. Destroys repetition and line effects but keeps the vocabulary exactly.",
    "lines": "Line order shuffled. Destroys section structure but keeps every line intact.",
    "word_lengths": "Words replaced by random strings of the same length over the same alphabet.",
}


def shuffle_characters(words: Sequence, rng: random.Random) -> list:
    """Reshuffle every character, keeping the sequence of word lengths."""
    pool = [ch for word in words for ch in word]
    rng.shuffle(pool)
    out = []
    i = 0
    for word in words:
        out.append("".join(pool[i : i + len(word)]))
        i += len(word)
    return out


def shuffle_within_words(words: Sequence, rng: random.Random) -> list:
    out = []
    for word in words:
        chars = list(word)
        rng.shuffle(chars)
        out.append("".join(chars))
    return out


def shuffle_words(words: Sequence, rng: random.Random) -> list:
    out = list(words)
    rng.shuffle(out)
    return out


def shuffle_lines(line_words: Sequence, rng: random.Random) -> list:
    lines = [list(line) for line in line_words]
    rng.shuffle(lines)
    return [word for line in lines for word in line]


def random_words_of_same_length(words: Sequence, rng: random.Random) -> list:
    alphabet = list({ch for word in words for ch in word}) or ["a"]
    return ["".join(rng.choice(alphabet) for _ in word) for word in words]


def shuffled_baseline(words: Sequence, mode: str, rng: random.Random, line_words: Sequence = ()) -> list:
    if mode == "characters":
        return shuffle_characters(words, rng)
    if mode == "within_words":
        return shuffle_within_words(words, rng)
    if mode == "words":
        return shuffle_words(words, rng)
    if mode == "lines":
        return shuffle_lines(line_words or [list(words)], rng)
    if mode == "word_lengths":
        return random_words_of_same_length(words, rng)
    raise ValueError("unknown shuffle mode %r" % mode)


# --------------------------------------------------------------------------
# Synthetic Voynichese (Timm and Schinner's self-citation model)
# --------------------------------------------------------------------------


@dataclass
class SyntheticOptions:
    """Parameters of the self-citation generator."""

    #: How many tokens to generate.
    length: int = 20000
    #: Chance of copying an earlier word unchanged rather than modifying it.
    copy_probability: float = 0.62
    #: How far back the generator may reach for a word to copy. 0 means anywhere.
    lookback: int = 250
    #: How many seed words to start from.
    seed_words: int = 60
    #: Chance of applying a second modification after the first.
    second_edit_probability: float = 0.10
    #: How often a modification swaps a whole prefix or suffix rather than one
    #: character.  Affix swaps are what keep synthetic words looking like real
    #: Voynichese instead of like noise.
    affix_edit_probability: float = 0.85
    #: How many prefixes and suffixes to harvest from the seed text.
    affix_pool: int = 24


def _affix_pools(words: Sequence, pool: int) -> tuple:
    prefixes: Counter = Counter()
    suffixes: Counter = Counter()
    for word in words:
        for size in (1, 2, 3):
            if len(word) > size + 1:
                prefixes[word[:size]] += 1
                suffixes[word[-size:]] += 1
    top_prefixes = [p for p, _ in prefixes.most_common(pool)]
    top_suffixes = [s for s, _ in suffixes.most_common(pool)]
    return top_prefixes or [""], top_suffixes or [""]


def _bigram_table(words: Sequence) -> dict:
    """p(next character | current character), as (choices, weights) pairs."""
    following: dict = {}
    for word in words:
        for a, b in zip(word, word[1:]):
            following.setdefault(a, Counter())[b] += 1
    return {ch: (list(counter), list(counter.values())) for ch, counter in following.items()}


def synthetic_voynichese(
    source_words: Sequence,
    options: SyntheticOptions = None,
    rng: random.Random = None,
) -> list:
    """Generate text by copying and lightly modifying earlier words.

    This is the Timm and Schinner self-citation model.  It has no grammar, no
    meaning and no cipher, yet it reproduces Voynichese word-length
    distributions, Zipf behaviour, low conditional entropy and the tendency of
    words to cluster near similar words.  That is exactly why it belongs in a
    decipherment workbench: any statistic your mapping "passes" that synthetic
    text also passes is not evidence of language.

    Two details make the imitation close rather than merely suggestive.
    Modifications swap whole prefixes and suffixes most of the time, because
    that is how the manuscript's word forms actually differ from each other;
    and when a single character does change, its replacement is drawn from
    what really follows its neighbour.

    With the default settings the output lands close to the manuscript on word
    count, type count, type/token ratio, Zipf exponent, repetition rate and
    word length, and roughly half way to it on second-order entropy (about 3.0
    bits against the manuscript's 2.4 and a shuffled text's 3.9).  Treat it as
    a strong null hypothesis, not as an exact forgery: a statistic where your
    mapping beats *this* is worth more than one where it merely beats noise.
    """
    options = options or SyntheticOptions()
    rng = rng or random.Random(0)
    if not source_words:
        return []

    counts = Counter(ch for w in source_words for ch in w)
    alphabet = list(counts)
    weights = list(counts.values())
    if not alphabet:
        return []
    prefixes, suffixes = _affix_pools(source_words, options.affix_pool)
    bigrams = _bigram_table(source_words)

    seeds = list(source_words[: options.seed_words]) or [source_words[0]]
    text = list(seeds)

    def pick_char(after: str = "") -> str:
        table = bigrams.get(after)
        if table:
            return rng.choices(table[0], weights=table[1], k=1)[0]
        return rng.choices(alphabet, weights=weights, k=1)[0]

    sorted_suffixes = sorted((s for s in suffixes if s), key=len, reverse=True)
    sorted_prefixes = sorted((p for p in prefixes if p), key=len, reverse=True)
    target_length = sum(len(w) for w in source_words) / len(source_words)

    def _pick_affix(pool, size: int, junction: str, at_start: bool, bias: int = 0) -> str:
        """Choose a replacement affix of similar length that joins plausibly.

        Picking a replacement at random lengthens words and invents letter
        pairs the manuscript never uses, which is what pushed the imitation's
        entropy above the real text's.  Candidates of a similar length whose
        junction bigram is attested keep both in range.
        """
        wanted = max(1, size + bias)
        similar = [a for a in pool if a and abs(len(a) - wanted) <= 1] or [a for a in pool if a]
        best = None
        for _ in range(6):
            candidate = rng.choice(similar)
            if not junction:
                return candidate
            pair = (junction + candidate[0]) if not at_start else (candidate[-1] + junction)
            table = bigrams.get(pair[0])
            if table and pair[1] in table[0]:
                return candidate
            best = best or candidate
        return best or similar[0]

    def swap_affix(word: str):
        """Replace a matching prefix or suffix. Returns None if none matched."""
        # Pull word length back towards the source mean, so repeated editing
        # does not make every word longer than anything in the manuscript.
        bias = -1 if len(word) > target_length + 0.5 else (1 if len(word) < target_length - 0.5 else 0)
        if rng.random() < 0.5:
            for suffix in sorted_suffixes:
                if word.endswith(suffix) and len(word) > len(suffix) + 1:
                    stem = word[: -len(suffix)]
                    return stem + _pick_affix(suffixes, len(suffix), stem[-1], False, bias)
        for prefix in sorted_prefixes:
            if word.startswith(prefix) and len(word) > len(prefix) + 1:
                stem = word[len(prefix) :]
                return _pick_affix(prefixes, len(prefix), stem[0], True, bias) + stem
        return None

    def modify(word: str) -> str:
        if not word:
            return pick_char()
        if rng.random() < options.affix_edit_probability:
            swapped = swap_affix(word)
            if swapped is not None:
                return swapped
        # Bias single-character edits so that word length stays near the source
        # mean instead of drifting upward with every insertion.
        grow = 0.25 if len(word) > target_length else 0.45
        choice = rng.random()
        pos = rng.randrange(len(word))
        before = word[pos - 1] if pos else ""
        if choice < 0.40:
            return word[:pos] + pick_char(before) + word[pos + 1 :]
        if choice < 0.40 + grow:
            return word[:pos] + pick_char(before) + word[pos:]
        if len(word) > 2:
            return word[:pos] + word[pos + 1 :]
        if len(word) > 1:
            j = min(len(word) - 1, pos + 1)
            chars = list(word)
            chars[pos], chars[j] = chars[j], chars[pos]
            return "".join(chars)
        return word + pick_char(word[-1])

    while len(text) < options.length:
        window = text[-options.lookback :] if options.lookback else text
        word = rng.choice(window)
        if rng.random() >= options.copy_probability:
            word = modify(word)
            if rng.random() < options.second_edit_probability:
                word = modify(word)
        text.append(word)
    return text[: options.length]


# --------------------------------------------------------------------------
# Random-mapping control runs
# --------------------------------------------------------------------------


@dataclass
class ControlDistribution:
    """Where an observed score falls among control scores."""

    metric: str
    observed: float
    scores: list
    mean: float = 0.0
    stdev: float = 0.0
    z_score: float = 0.0
    percentile: float = 0.0
    best_random: float = 0.0

    def __post_init__(self) -> None:
        if not self.scores:
            return
        self.mean = sum(self.scores) / len(self.scores)
        variance = sum((s - self.mean) ** 2 for s in self.scores) / len(self.scores)
        self.stdev = math.sqrt(variance)
        self.z_score = (self.observed - self.mean) / self.stdev if self.stdev else 0.0
        self.percentile = 100.0 * sum(1 for s in self.scores if s <= self.observed) / len(self.scores)
        self.best_random = max(self.scores)

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "observed": round(self.observed, 5),
            "random_mean": round(self.mean, 5),
            "random_stdev": round(self.stdev, 5),
            "random_best": round(self.best_random, 5),
            "z_score": round(self.z_score, 3),
            "percentile": round(self.percentile, 2),
            "control_runs": len(self.scores),
        }

    def verdict(self) -> str:
        if not self.scores:
            return "no control runs"
        if self.observed <= self.best_random:
            return "at least one random mapping scored as well as yours: this result is not distinguishable from chance"
        if self.z_score >= 4:
            return "far above every random mapping tried"
        if self.z_score >= 2:
            return "above the random distribution, but within reach of a lucky mapping"
        return "inside the random distribution: no evidence of a real effect"

    def histogram(self, width: int = 40, buckets: int = 12) -> str:
        """A text histogram with your score marked."""
        if not self.scores:
            return ""
        low = min(min(self.scores), self.observed)
        high = max(max(self.scores), self.observed)
        if high <= low:
            return "all control scores identical (%.4f)" % low
        step = (high - low) / buckets
        counts = [0] * buckets
        for score in self.scores:
            counts[min(buckets - 1, int((score - low) / step))] += 1
        peak = max(counts) or 1
        marker = min(buckets - 1, int((self.observed - low) / step))
        lines = []
        for i, count in enumerate(counts):
            bar = "#" * int(width * count / peak)
            flag = "  <-- your mapping" if i == marker else ""
            lines.append("%8.4f | %-*s %d%s" % (low + i * step, width, bar, count, flag))
        return "\n".join(lines)


def score_random_mappings(
    glyphs: Sequence,
    scorer: Callable[[dict], float],
    runs: int = 200,
    alphabet: str = "abcdefghijklmnopqrstuvwxyz",
    rng: random.Random = None,
    progress: Callable = None,
) -> list:
    """Score ``runs`` random glyph-to-letter mappings with the same scorer."""
    rng = rng or random.Random(0)
    glyph_list = list(glyphs)
    scores = []
    iterator = range(runs)
    if progress is not None:
        iterator = progress(iterator)
    for _ in iterator:
        table = {g: rng.choice(alphabet) for g in glyph_list}
        scores.append(scorer(table))
    return scores


# --------------------------------------------------------------------------
# Held-out validation
# --------------------------------------------------------------------------


@dataclass
class HoldoutReport:
    """A score on the data a mapping was tuned on, and on data it was not."""

    fit_label: str
    holdout_label: str
    fit_score: float
    holdout_score: float
    metric: str

    @property
    def drop(self) -> float:
        if not self.fit_score:
            return 0.0
        return (self.fit_score - self.holdout_score) / self.fit_score

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "fit_on": self.fit_label,
            "fit_score": round(self.fit_score, 5),
            "held_out": self.holdout_label,
            "holdout_score": round(self.holdout_score, 5),
            "relative_drop": round(self.drop, 4),
        }

    def verdict(self) -> str:
        drop = self.drop
        if drop <= 0.05:
            return "holds up on unseen text: the mapping generalises"
        if drop <= 0.20:
            return "some loss on unseen text, within reason"
        if drop <= 0.45:
            return "a large drop on unseen text: the mapping is partly fitted to its training section"
        return "collapses on unseen text: this mapping is memorising, not deciphering"


# --------------------------------------------------------------------------
# Overfitting
# --------------------------------------------------------------------------


@dataclass
class OverfittingReport:
    """Whether a mapping's extra rules are paying for themselves."""

    rules: int
    extra_rules: int
    glyphs: int
    baseline_score: float
    score: float
    tokens: int

    @property
    def gain(self) -> float:
        return self.score - self.baseline_score

    @property
    def gain_per_rule(self) -> float:
        return self.gain / self.extra_rules if self.extra_rules else 0.0

    @property
    def free_parameters_per_token(self) -> float:
        return self.rules / self.tokens if self.tokens else 0.0

    def to_dict(self) -> dict:
        return {
            "total_rules": self.rules,
            "extra_positional_rules": self.extra_rules,
            "glyphs": self.glyphs,
            "plain_only_score": round(self.baseline_score, 5),
            "full_score": round(self.score, 5),
            "gain_from_extra_rules": round(self.gain, 5),
            "gain_per_extra_rule": round(self.gain_per_rule, 6),
            "level": self.level(),
        }

    def level(self) -> str:
        if self.extra_rules == 0:
            return "none"
        if self.extra_rules > self.glyphs:
            return "severe"
        if self.gain_per_rule <= 0:
            return "severe"
        if self.extra_rules > self.glyphs * 0.5:
            return "high"
        if self.extra_rules > self.glyphs * 0.2:
            return "moderate"
        return "low"

    def message(self) -> str:
        level = self.level()
        if level == "none":
            return "No positional or occurrence rules: nothing to overfit with."
        if level == "severe":
            if self.gain_per_rule <= 0:
                return (
                    "%d extra rules and they do not improve the score at all. "
                    "Remove them: they are decoration, not decipherment." % self.extra_rules
                )
            return (
                "%d extra rules for %d glyphs. With more rules than glyphs you can fit almost any text; "
                "the result carries very little evidence." % (self.extra_rules, self.glyphs)
            )
        if level == "high":
            return (
                "%d extra rules for %d glyphs. That is a lot of freedom - check the held-out score before "
                "believing the gain." % (self.extra_rules, self.glyphs)
            )
        if level == "moderate":
            return "%d extra rules for %d glyphs: worth watching, but not alarming." % (self.extra_rules, self.glyphs)
        return "%d extra rules for %d glyphs: a modest amount of extra freedom." % (self.extra_rules, self.glyphs)


# --------------------------------------------------------------------------
# Language controls
# --------------------------------------------------------------------------


@dataclass
class ControlCorpus:
    """A real-language sample with its statistics already computed."""

    name: str
    title: str
    words: list
    bundle: StatBundle = field(default=None)

    def compute(self) -> StatBundle:
        if self.bundle is None:
            self.bundle = stat_bundle(self.words, self.title)
        return self.bundle
