"""The statistics that decide whether a mapping behaves like a language.

Everything here works on plain Python lists of words and strings, so the same
functions run on the manuscript, on your transliteration, on a shuffled
baseline and on a Latin control text without any special-casing.

The measurements, and what each is for
--------------------------------------
``entropy_profile``
    Character entropy at orders 0, 1 and 2.  The second-order conditional
    entropy h2 is the single most cited Voynich statistic: the manuscript sits
    near 2.0 bits, while European languages sit near 3.0-3.5.  A mapping is a
    one-for-one substitution, so it *cannot* change h2 much - if your output
    suddenly looks like Latin, something in the pipeline is adding or removing
    information.

``word_length_profile``
    Voynichese word lengths follow an unusually tight, almost binomial curve
    centred near five glyphs, with far fewer very short and very long words
    than any natural language.

``vocabulary_profile``
    Type/token ratio, moving-average TTR, hapax legomena and Heaps' law.  Heaps
    describes how fast new word types appear as you read on.

``zipf_profile``
    Rank against frequency.  Voynichese follows Zipf's law closely, which is
    one reason it is hard to dismiss as random.

``ngram_profile``
    Character transition counts and the conditional entropy that follows from
    them, plus the matrix a heatmap is drawn from.

``positional_profile``
    Where in a word each glyph prefers to sit.  Voynichese glyphs are strongly
    positional: q almost only starts words, n almost only ends them.

``slot_profile``
    Jorge Stolfi's crust-mantle-core model: Voynichese words look like they are
    built from an ordered template rather than freely combined.  If your output
    still obeys a rigid template, it has not become a normal language.

``affix_profile``
    Prefixes and suffixes, scored by how surprising they are rather than by raw
    count, so that common letters do not dominate the list.

``repeat_profile``
    Immediate repetition, repeat distances and autocorrelation.  Voynichese
    words cluster near themselves far more than natural language words do.

``line_profile``
    Line-position effects: the first word and first glyph of a line come from a
    restricted set (the "line as a functional unit", LAAFU, effect), and
    gallows characters concentrate in first lines.

``vowel_profile``
    Sukhotin's vowel-detection algorithm plus a direct test of how strictly the
    text alternates between the two classes it finds.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .util import pct, safe_log2

# --------------------------------------------------------------------------
# Entropy
# --------------------------------------------------------------------------


def shannon_entropy(counts: Counter) -> float:
    """Entropy in bits of a symbol distribution."""
    total = sum(counts.values())
    if not total:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts.values() if c)


def conditional_entropy(text: str, order: int = 1) -> float:
    """H(next character | previous ``order`` characters), in bits.

    ``order=0`` is the plain character entropy h1 in Bennett's notation;
    ``order=1`` gives h2, the number quoted for the Voynich manuscript.
    """
    if order <= 0:
        return shannon_entropy(Counter(text))
    if len(text) <= order:
        return 0.0
    context_counts: Counter = Counter()
    joint_counts: Counter = Counter()
    for i in range(len(text) - order):
        context = text[i : i + order]
        context_counts[context] += 1
        joint_counts[context + text[i + order]] += 1
    total = sum(context_counts.values())
    entropy = 0.0
    for gram, count in joint_counts.items():
        p_joint = count / total
        p_cond = count / context_counts[gram[:-1]]
        entropy -= p_joint * math.log2(p_cond)
    return entropy


@dataclass
class EntropyProfile:
    """Character entropy at increasing orders, with reference values."""

    h0: float
    h1: float
    h2: float
    h3: float
    alphabet_size: int
    characters: int
    per_word_h1: float

    def to_dict(self) -> dict:
        return {
            "h0_alphabet_bits": round(self.h0, 4),
            "h1_character_bits": round(self.h1, 4),
            "h2_conditional_bits": round(self.h2, 4),
            "h3_conditional_bits": round(self.h3, 4),
            "alphabet_size": self.alphabet_size,
            "characters": self.characters,
            "word_entropy_bits": round(self.per_word_h1, 4),
        }


#: Published reference values, for orientation only.  Exact numbers depend on
#: the transcription alphabet and on whether spaces are counted, so treat these
#: as "the neighbourhood", not as targets to hit.
ENTROPY_REFERENCES = {
    "Voynich (EVA, no spaces)": {"h1": 3.85, "h2": 2.10},
    "Latin (classical prose)": {"h1": 4.00, "h2": 3.35},
    "Italian": {"h1": 3.98, "h2": 3.30},
    "English": {"h1": 4.10, "h2": 3.40},
    "Hebrew (consonantal)": {"h1": 4.20, "h2": 3.60},
    "Random uniform (24 letters)": {"h1": 4.58, "h2": 4.58},
}


def entropy_profile(words: Sequence, joiner: str = "") -> EntropyProfile:
    text = joiner.join(words)
    counts = Counter(text)
    return EntropyProfile(
        h0=safe_log2(len(counts)),
        h1=shannon_entropy(counts),
        h2=conditional_entropy(text, 1),
        h3=conditional_entropy(text, 2),
        alphabet_size=len(counts),
        characters=len(text),
        per_word_h1=shannon_entropy(Counter(words)),
    )


# --------------------------------------------------------------------------
# Word length
# --------------------------------------------------------------------------


@dataclass
class WordLengthProfile:
    counts: dict
    mean: float
    variance: float
    binomial_n: int
    binomial_p: float
    binomial_fit_error: float
    total: int
    dispersion: float = 0.0
    short_share: float = 0.0
    long_share: float = 0.0
    peak_length: int = 0

    def to_dict(self) -> dict:
        return {
            "distribution": self.counts,
            "mean": round(self.mean, 4),
            "variance": round(self.variance, 4),
            "dispersion": round(self.dispersion, 4),
            "peak_length": self.peak_length,
            "share_1_to_2_letters": round(self.short_share, 4),
            "share_9_plus_letters": round(self.long_share, 4),
            "binomial_n": self.binomial_n,
            "binomial_p": round(self.binomial_p, 4),
            "binomial_fit_error": round(self.binomial_fit_error, 5),
            "total_words": self.total,
        }

    def verdict(self) -> str:
        """Describe the shape in the terms that actually separate Voynichese.

        The manuscript's word lengths are unusually *tight*: a sharp peak near
        five glyphs, hardly any one or two letter words, and a fast-decaying
        tail.  European languages spike at two or three letters because of
        their function words, and spread further at the top.
        """
        bits = []
        if self.binomial_fit_error < 0.06:
            bits.append("closely binomial")
        elif self.binomial_fit_error < 0.11:
            bits.append("roughly binomial")
        else:
            bits.append("not binomial")
        if self.dispersion < 0.85:
            bits.append("tightly clustered around the mean, as in the manuscript")
        elif self.dispersion < 1.1:
            bits.append("moderately spread")
        else:
            bits.append("widely spread, as in a language with many short function words")
        if self.short_share < 0.12:
            bits.append("very few one or two letter words")
        elif self.short_share > 0.2:
            bits.append("many short words")
        return "; ".join(bits)


def word_length_profile(words: Sequence, max_n: int = 60) -> WordLengthProfile:
    """Word lengths, plus the best-fitting binomial curve.

    The binomial is fitted by searching for the ``n`` whose curve is closest to
    the observed distribution, rather than by matching moments.  Moment
    matching degenerates whenever the variance approaches the mean, which is
    exactly what happens for natural languages, and it then reports a
    meaningless fit instead of a bad one.
    """
    lengths = [len(w) for w in words if w]
    total = len(lengths)
    counts = Counter(lengths)
    if not total:
        return WordLengthProfile({}, 0.0, 0.0, 0, 0.0, 0.0, 0)
    mean = sum(lengths) / total
    variance = sum((x - mean) ** 2 for x in lengths) / total
    observed = {k: counts.get(k, 0) / total for k in range(0, max(counts) + 1)}

    best_error = 1.0
    best_n, best_p = 1, 0.5
    for n in range(max(1, int(mean)), max_n + 1):
        p = mean / n
        if not 0 < p < 1:
            continue
        error = 0.0
        log_choose = 0.0
        for k in range(0, n + 1):
            if k:
                log_choose += math.log((n - k + 1) / k)
            expected = math.exp(log_choose + k * math.log(p) + (n - k) * math.log(1 - p))
            error += abs(observed.get(k, 0.0) - expected)
        for k in observed:
            if k > n:
                error += observed[k]
        error /= 2
        if error < best_error:
            best_error, best_n, best_p = error, n, p

    short = sum(counts.get(k, 0) for k in (1, 2)) / total
    long = sum(c for k, c in counts.items() if k >= 9) / total
    peak = max(counts, key=lambda k: counts[k])

    return WordLengthProfile(
        counts={k: counts[k] for k in sorted(counts)},
        mean=mean,
        variance=variance,
        binomial_n=best_n,
        binomial_p=best_p,
        binomial_fit_error=best_error,
        total=total,
        dispersion=variance / mean if mean else 0.0,
        short_share=short,
        long_share=long,
        peak_length=peak,
    )


# --------------------------------------------------------------------------
# Vocabulary growth
# --------------------------------------------------------------------------


@dataclass
class VocabularyProfile:
    tokens: int
    types: int
    ttr: float
    mattr: float
    hapax: int
    hapax_ratio: float
    dis_legomena: int
    heaps_k: float
    heaps_beta: float
    heaps_points: list

    def to_dict(self) -> dict:
        return {
            "tokens": self.tokens,
            "types": self.types,
            "type_token_ratio": round(self.ttr, 5),
            "mattr": round(self.mattr, 5),
            "hapax_legomena": self.hapax,
            "hapax_ratio": round(self.hapax_ratio, 5),
            "dis_legomena": self.dis_legomena,
            "heaps_k": round(self.heaps_k, 4),
            "heaps_beta": round(self.heaps_beta, 4),
        }

    def verdict(self) -> str:
        if self.heaps_beta < 0.55:
            return "vocabulary grows slowly; a small, highly repetitive lexicon"
        if self.heaps_beta < 0.75:
            return "vocabulary growth in the range typical of natural language"
        return "vocabulary grows very fast; close to every word being new"


def moving_average_ttr(words: Sequence, window: int = 500) -> float:
    """Type/token ratio averaged over a sliding window.

    Plain TTR falls as a text gets longer, so it cannot be compared between
    texts of different sizes.  MATTR fixes that by always measuring the same
    number of tokens.
    """
    if len(words) < window:
        return len(set(words)) / len(words) if words else 0.0
    counts: Counter = Counter(words[:window])
    distinct = len(counts)
    total = distinct
    steps = 1
    for i in range(window, len(words)):
        outgoing = words[i - window]
        counts[outgoing] -= 1
        if counts[outgoing] == 0:
            del counts[outgoing]
            distinct -= 1
        incoming = words[i]
        if counts[incoming] == 0:
            distinct += 1
        counts[incoming] += 1
        total += distinct
        steps += 1
    return (total / steps) / window


def heaps_law(words: Sequence, points: int = 60) -> tuple:
    """Fit ``types = k * tokens ** beta`` by least squares in log space."""
    if len(words) < 20:
        return 1.0, 1.0, []
    step = max(1, len(words) // points)
    seen: set = set()
    samples = []
    for i, word in enumerate(words, 1):
        seen.add(word)
        if i % step == 0:
            samples.append((i, len(seen)))
    if len(samples) < 3:
        return 1.0, 1.0, samples
    xs = [math.log(n) for n, _ in samples]
    ys = [math.log(v) for _, v in samples]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom if denom else 1.0
    k = math.exp(my - beta * mx)
    return k, beta, samples


def vocabulary_profile(words: Sequence, mattr_window: int = 500) -> VocabularyProfile:
    counts = Counter(words)
    tokens = len(words)
    types = len(counts)
    hapax = sum(1 for c in counts.values() if c == 1)
    dis = sum(1 for c in counts.values() if c == 2)
    k, beta, samples = heaps_law(words)
    return VocabularyProfile(
        tokens=tokens,
        types=types,
        ttr=types / tokens if tokens else 0.0,
        mattr=moving_average_ttr(words, mattr_window),
        hapax=hapax,
        hapax_ratio=hapax / types if types else 0.0,
        dis_legomena=dis,
        heaps_k=k,
        heaps_beta=beta,
        heaps_points=samples,
    )


# --------------------------------------------------------------------------
# Zipf
# --------------------------------------------------------------------------


@dataclass
class ZipfProfile:
    slope: float
    intercept: float
    r_squared: float
    ranks: list
    frequencies: list
    top: list

    def to_dict(self) -> dict:
        return {
            "slope": round(self.slope, 4),
            "intercept": round(self.intercept, 4),
            "r_squared": round(self.r_squared, 4),
            "top_words": self.top[:25],
        }

    def verdict(self) -> str:
        if 0.85 <= abs(self.slope) <= 1.35 and self.r_squared > 0.9:
            return "follows Zipf's law about as closely as a natural language"
        if self.r_squared > 0.9:
            return "a clean power law, but with an unusual exponent"
        return "a poor fit to Zipf's law"


#: Typical Zipf exponents, used as reference lines in the plot.
ZIPF_REFERENCES = (
    ("Modern English", 1.00),
    ("Middle High German", 1.03),
    ("Old French / Italian", 1.06),
    ("Old English", 1.08),
    ("Latin", 1.15),
)


def zipf_profile(words: Sequence) -> ZipfProfile:
    counts = Counter(words)
    ordered = counts.most_common()
    if not ordered:
        return ZipfProfile(0.0, 0.0, 0.0, [], [], [])
    freqs = [c for _, c in ordered]
    ranks = list(range(1, len(freqs) + 1))
    xs = [math.log(r) for r in ranks]
    ys = [math.log(f) for f in freqs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom if denom else 0.0
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    total = sum(freqs)
    top = [(w, c, pct(c, total, 3)) for w, c in ordered[:60]]
    return ZipfProfile(slope=slope, intercept=intercept, r_squared=r2, ranks=ranks, frequencies=freqs, top=top)


# --------------------------------------------------------------------------
# N-grams and transition matrices
# --------------------------------------------------------------------------


@dataclass
class NgramProfile:
    order: int
    alphabet: list
    matrix: list
    row_totals: list
    top_bigrams: list
    conditional_entropy: float

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "alphabet": self.alphabet,
            "top_transitions": self.top_bigrams[:40],
            "conditional_entropy_bits": round(self.conditional_entropy, 4),
        }

    def probability_matrix(self) -> list:
        out = []
        for row, total in zip(self.matrix, self.row_totals):
            out.append([(c / total if total else 0.0) for c in row])
        return out


def ngram_profile(words: Sequence, boundary: str = "_", top: int = 60) -> NgramProfile:
    """Character transition counts, with word boundaries as a real symbol.

    Treating the word boundary as a character is important for Voynichese,
    where the strongest regularities are about what may start or end a word.
    """
    padded = boundary.join([""] + list(words) + [""])
    alphabet = sorted(set(padded))
    index = {ch: i for i, ch in enumerate(alphabet)}
    size = len(alphabet)
    matrix = [[0] * size for _ in range(size)]
    for a, b in zip(padded, padded[1:]):
        matrix[index[a]][index[b]] += 1
    row_totals = [sum(row) for row in matrix]
    pairs = []
    for i, row in enumerate(matrix):
        for j, count in enumerate(row):
            if count:
                pairs.append((alphabet[i] + alphabet[j], count))
    pairs.sort(key=lambda kv: -kv[1])
    return NgramProfile(
        order=2,
        alphabet=alphabet,
        matrix=matrix,
        row_totals=row_totals,
        top_bigrams=pairs[:top],
        conditional_entropy=conditional_entropy(padded, 1),
    )


def ngram_counts(words: Sequence, n: int, boundary: str = "") -> Counter:
    counter: Counter = Counter()
    for word in words:
        token = boundary + word + boundary if boundary else word
        for i in range(len(token) - n + 1):
            counter[token[i : i + n]] += 1
    return counter


# --------------------------------------------------------------------------
# Positional behaviour
# --------------------------------------------------------------------------


@dataclass
class PositionalProfile:
    glyphs: dict
    entropy: dict
    initial_only: list
    final_only: list

    def to_dict(self) -> dict:
        return {
            "positional_entropy": {g: round(v, 4) for g, v in sorted(self.entropy.items(), key=lambda kv: kv[1])},
            "almost_always_initial": self.initial_only,
            "almost_always_final": self.final_only,
        }


def positional_profile(words: Sequence, buckets: int = 5) -> PositionalProfile:
    """For each glyph, how its position within a word is distributed.

    A glyph that appears everywhere has high positional entropy; one that only
    ever starts words has close to zero.  Voynichese is full of the latter,
    which is one of the reasons it does not behave like an alphabet.
    """
    per_glyph: dict = defaultdict(lambda: [0] * buckets)
    initial: Counter = Counter()
    final: Counter = Counter()
    totals: Counter = Counter()
    for word in words:
        length = len(word)
        if not length:
            continue
        for i, ch in enumerate(word):
            slot = min(buckets - 1, int(i * buckets / length))
            per_glyph[ch][slot] += 1
            totals[ch] += 1
        initial[word[0]] += 1
        final[word[-1]] += 1

    entropy = {}
    for glyph, dist in per_glyph.items():
        entropy[glyph] = shannon_entropy(Counter({i: c for i, c in enumerate(dist) if c}))

    initial_only = sorted(
        (g for g in totals if totals[g] >= 20 and initial[g] / totals[g] > 0.9),
        key=lambda g: -totals[g],
    )
    final_only = sorted(
        (g for g in totals if totals[g] >= 20 and final[g] / totals[g] > 0.9),
        key=lambda g: -totals[g],
    )
    return PositionalProfile(
        glyphs={g: list(d) for g, d in sorted(per_glyph.items())},
        entropy=entropy,
        initial_only=initial_only,
        final_only=final_only,
    )


# --------------------------------------------------------------------------
# Slot grammar (Stolfi's crust-mantle-core)
# --------------------------------------------------------------------------


@dataclass
class SlotProfile:
    crust_prefix: list
    mantle_prefix: list
    core: list
    mantle_suffix: list
    crust_suffix: list
    conforming: int
    total: int
    template: str

    @property
    def conformance(self) -> float:
        return self.conforming / self.total if self.total else 0.0

    def to_dict(self) -> dict:
        return {
            "template": self.template,
            "conforming_words": self.conforming,
            "total_words": self.total,
            "conformance": round(self.conformance, 4),
            "crust_prefix": self.crust_prefix,
            "mantle_prefix": self.mantle_prefix,
            "core": self.core,
            "mantle_suffix": self.mantle_suffix,
            "crust_suffix": self.crust_suffix,
        }

    def verdict(self) -> str:
        if self.conformance > 0.85:
            return "words still obey a rigid slot template, as Voynichese does"
        if self.conformance > 0.6:
            return "partly templated"
        return "no strong slot structure; words look freely combined"


def slot_profile(words: Sequence, min_share: float = 0.02) -> SlotProfile:
    """Test whether words are built from an ordered template.

    Jorge Stolfi observed that Voynichese words look like a fixed sequence of
    optional parts - an outer "crust", a "mantle", and a "core" - rather than
    free strings over an alphabet.  A real language rarely does this, so if
    your output still conforms, it has kept the manuscript's structure rather
    than acquiring a language's.
    """
    total = len(words)
    if not total:
        return SlotProfile([], [], [], [], [], 0, 0, "")

    first: Counter = Counter(w[0] for w in words if w)
    second: Counter = Counter(w[1] for w in words if len(w) > 1)
    middle: Counter = Counter(ch for w in words for ch in w[2:-2])
    penult: Counter = Counter(w[-2] for w in words if len(w) > 1)
    last: Counter = Counter(w[-1] for w in words if w)

    def common(counter: Counter, denominator: int) -> list:
        return [ch for ch, n in counter.most_common() if denominator and n / denominator >= min_share]

    crust_prefix = common(first, total)
    mantle_prefix = common(second, total)
    core = common(middle, max(1, sum(middle.values())))
    mantle_suffix = common(penult, total)
    crust_suffix = common(last, total)

    sets = (set(crust_prefix), set(mantle_prefix), set(core), set(mantle_suffix), set(crust_suffix))
    conforming = 0
    for word in words:
        if _fits_template(word, sets):
            conforming += 1

    template = " ".join("[%s]" % "".join(sorted(s)[:12]) for s in sets)
    return SlotProfile(
        crust_prefix=crust_prefix,
        mantle_prefix=mantle_prefix,
        core=core,
        mantle_suffix=mantle_suffix,
        crust_suffix=crust_suffix,
        conforming=conforming,
        total=total,
        template=template,
    )


def _fits_template(word: str, sets: tuple) -> bool:
    """Greedy check that a word can be read as crust-mantle-core-mantle-crust."""
    i, j = 0, len(word)
    if i < j and word[i] in sets[0]:
        i += 1
    if i < j and word[i] in sets[1]:
        i += 1
    if j > i and word[j - 1] in sets[4]:
        j -= 1
    if j > i and word[j - 1] in sets[3]:
        j -= 1
    return all(ch in sets[2] for ch in word[i:j])


# --------------------------------------------------------------------------
# Affixes
# --------------------------------------------------------------------------


@dataclass
class AffixProfile:
    prefixes: list
    suffixes: list
    infixes: list

    def to_dict(self) -> dict:
        return {
            "prefixes": self.prefixes[:40],
            "suffixes": self.suffixes[:40],
            "infixes": self.infixes[:40],
        }


def affix_profile(words: Sequence, sizes: Sequence = (1, 2, 3, 4), min_count: int = 10) -> AffixProfile:
    """Prefixes and suffixes ranked by surprise, not by raw count.

    Counting affixes naively just rediscovers the commonest letters.  Each
    candidate is instead scored by log-likelihood ratio against what its
    letters would produce independently, so ``-aiin`` outranks ``-n``.
    """
    letters = Counter(ch for word in words for ch in word)
    letter_total = sum(letters.values()) or 1
    total_words = len(words) or 1

    def score_group(extract) -> list:
        rows = []
        for size in sizes:
            counts: Counter = Counter()
            for word in words:
                piece = extract(word, size)
                if piece is not None and len(piece) == size:
                    counts[piece] += 1
            for piece, count in counts.items():
                if count < min_count:
                    continue
                expected = total_words
                for ch in piece:
                    expected *= letters.get(ch, 1) / letter_total
                if expected <= 0:
                    continue
                lift = count / expected
                surprise = count * math.log2(lift) if lift > 0 else 0.0
                rows.append(
                    {
                        "affix": piece,
                        "count": count,
                        "share": round(count / total_words, 5),
                        "expected": round(expected, 2),
                        "lift": round(lift, 3),
                        "surprise_bits": round(surprise, 1),
                    }
                )
        rows.sort(key=lambda r: -r["surprise_bits"])
        return rows

    prefixes = score_group(lambda w, n: w[:n] if len(w) >= n else None)
    suffixes = score_group(lambda w, n: w[-n:] if len(w) >= n else None)

    infix_rows = []
    for size in sizes:
        counts = Counter()
        for word in words:
            for i in range(1, len(word) - size):
                counts[word[i : i + size]] += 1
        for piece, count in counts.most_common(60):
            if count >= min_count:
                infix_rows.append({"affix": piece, "count": count})
    return AffixProfile(prefixes=prefixes, suffixes=suffixes, infixes=infix_rows)


# --------------------------------------------------------------------------
# Repetition and autocorrelation
# --------------------------------------------------------------------------


@dataclass
class RepeatProfile:
    immediate: int
    immediate_rate: float
    near_repeats: dict
    autocorrelation: list
    top_repeated: list
    mean_repeat_distance: float
    chance_level: float = 0.0

    @property
    def clustering_ratio(self) -> float:
        """How many times more likely a repeat at lag 1 is than by chance."""
        if not self.chance_level:
            return 0.0
        return (self.autocorrelation[0] + self.chance_level) / self.chance_level if self.autocorrelation else 0.0

    def to_dict(self) -> dict:
        return {
            "immediate_repeats": self.immediate,
            "immediate_repeat_rate": round(self.immediate_rate, 5),
            "chance_repeat_rate": round(self.chance_level, 6),
            "clustering_ratio": round(self.clustering_ratio, 2),
            "near_repeat_counts": self.near_repeats,
            "autocorrelation": [round(v, 5) for v in self.autocorrelation],
            "mean_repeat_distance": round(self.mean_repeat_distance, 2),
            "most_repeated_pairs": self.top_repeated[:20],
        }

    def verdict(self) -> str:
        ratio = self.clustering_ratio
        if ratio >= 4:
            return "words cluster near themselves far more than chance, as in the manuscript"
        if ratio >= 2:
            return "a clear clustering tendency"
        if ratio >= 1.2:
            return "mild clustering"
        return "no clustering beyond chance"


def repeat_profile(words: Sequence, max_lag: int = 12) -> RepeatProfile:
    """How often words repeat, and at what distance.

    Voynichese repeats itself over short spans far more than any natural
    language: ``qokeedy qokeedy qokedy`` sequences are common.  Autocorrelation
    at lag k is the excess probability that the word k positions later is the
    same word.
    """
    total = len(words)
    if total < 2:
        return RepeatProfile(0, 0.0, {}, [], [], 0.0)

    counts = Counter(words)
    baseline = sum((c / total) ** 2 for c in counts.values())

    autocorrelation = []
    for lag in range(1, max_lag + 1):
        if total <= lag:
            autocorrelation.append(0.0)
            continue
        same = sum(1 for i in range(total - lag) if words[i] == words[i + lag])
        autocorrelation.append(same / (total - lag) - baseline)

    immediate_pairs = [words[i] for i in range(total - 1) if words[i] == words[i + 1]]
    near = {}
    for window in (2, 3, 5, 10):
        hits = 0
        for i in range(total - window):
            if words[i] in words[i + 1 : i + 1 + window]:
                hits += 1
        near[window] = hits

    positions: dict = defaultdict(list)
    for i, word in enumerate(words):
        positions[word].append(i)
    distances = []
    for spots in positions.values():
        distances.extend(b - a for a, b in zip(spots, spots[1:]))
    mean_distance = sum(distances) / len(distances) if distances else 0.0

    return RepeatProfile(
        immediate=len(immediate_pairs),
        immediate_rate=len(immediate_pairs) / (total - 1),
        near_repeats=near,
        autocorrelation=autocorrelation,
        top_repeated=Counter(immediate_pairs).most_common(20),
        mean_repeat_distance=mean_distance,
        chance_level=baseline,
    )


# --------------------------------------------------------------------------
# Line effects
# --------------------------------------------------------------------------

#: EVA gallows characters.  These cluster in the first line of a paragraph.
EVA_GALLOWS = set("kltpfKLTPF")


@dataclass
class LineProfile:
    first_word_types: int
    other_word_types: int
    first_word_overlap: float
    first_glyph_counts: dict
    other_glyph_counts: dict
    gallows_first_line_rate: float
    gallows_other_line_rate: float
    length_by_position: dict
    laafu_score: float

    def to_dict(self) -> dict:
        return {
            "first_word_types": self.first_word_types,
            "other_word_types": self.other_word_types,
            "first_word_vocabulary_overlap": round(self.first_word_overlap, 4),
            "gallows_rate_first_lines": round(self.gallows_first_line_rate, 5),
            "gallows_rate_other_lines": round(self.gallows_other_line_rate, 5),
            "mean_word_length_by_line_position": {k: round(v, 3) for k, v in self.length_by_position.items()},
            "laafu_score": round(self.laafu_score, 4),
        }

    def verdict(self) -> str:
        if self.laafu_score > 0.25:
            return "strong line-as-a-functional-unit effect: line starts use their own vocabulary"
        if self.laafu_score > 0.1:
            return "a measurable line-start effect"
        return "line position barely affects vocabulary"


def line_profile(line_words: Sequence, first_line_flags: Sequence = ()) -> LineProfile:
    """Measure how much a word's position in the line changes its behaviour."""
    first_words = [w[0] for w in line_words if w]
    other_words = [w for line in line_words for w in line[1:]]
    first_types = set(first_words)
    other_types = set(other_words)
    overlap = len(first_types & other_types) / len(first_types) if first_types else 0.0

    first_glyphs = Counter(w[0] for w in first_words if w)
    other_glyphs = Counter(w[0] for w in other_words if w)

    flags = list(first_line_flags) or [False] * len(line_words)
    gallows_first = gallows_other = chars_first = chars_other = 0
    for line, is_first in zip(line_words, flags):
        text = "".join(line)
        gallows = sum(1 for ch in text if ch in EVA_GALLOWS)
        if is_first:
            gallows_first += gallows
            chars_first += len(text)
        else:
            gallows_other += gallows
            chars_other += len(text)

    by_position: dict = defaultdict(list)
    for line in line_words:
        for i, word in enumerate(line):
            by_position[min(i, 9)].append(len(word))
    length_by_position = {k: sum(v) / len(v) for k, v in sorted(by_position.items()) if v}

    return LineProfile(
        first_word_types=len(first_types),
        other_word_types=len(other_types),
        first_word_overlap=overlap,
        first_glyph_counts=dict(first_glyphs.most_common(20)),
        other_glyph_counts=dict(other_glyphs.most_common(20)),
        gallows_first_line_rate=gallows_first / chars_first if chars_first else 0.0,
        gallows_other_line_rate=gallows_other / chars_other if chars_other else 0.0,
        length_by_position=length_by_position,
        laafu_score=1.0 - overlap,
    )


# --------------------------------------------------------------------------
# Vowels
# --------------------------------------------------------------------------


@dataclass
class VowelProfile:
    vowels: list
    consonants: list
    scores: dict
    alternation_rate: float
    expected_alternation: float

    def to_dict(self) -> dict:
        return {
            "vowels": self.vowels,
            "consonants": self.consonants,
            "alternation_rate": round(self.alternation_rate, 4),
            "expected_if_independent": round(self.expected_alternation, 4),
            "alternation_excess": round(self.alternation_rate - self.expected_alternation, 4),
        }

    def verdict(self) -> str:
        excess = self.alternation_rate - self.expected_alternation
        if excess > 0.12:
            return (
                "letters alternate between the two classes much more than chance: consistent with vowels and consonants"
            )
        if excess > 0.04:
            return "a mild alternation tendency"
        return "no real alternation; the two classes do not behave like vowels and consonants"


def sukhotin_vowels(text: str) -> tuple:
    """Sukhotin's algorithm: find the letters that most often sit beside others.

    It needs no knowledge of the language.  Build a symmetric adjacency matrix,
    take each letter's row sum, and repeatedly declare the highest remaining
    score a vowel - subtracting twice that vowel's adjacency from every other
    score, because a letter next to a known vowel is evidence for a consonant.
    The process stops when no score is positive.
    """
    letters = [ch for ch in text if ch.isalnum()]
    alphabet = sorted(set(letters))
    n = len(alphabet)
    if n < 2:
        return [], alphabet, {}
    index = {ch: i for i, ch in enumerate(alphabet)}
    matrix = [[0] * n for _ in range(n)]
    for a, b in zip(letters, letters[1:]):
        if a == b:
            continue
        i, j = index[a], index[b]
        matrix[i][j] += 1
        matrix[j][i] += 1

    sums = [sum(row) for row in matrix]
    is_vowel = [False] * n
    scores: dict = {}
    while True:
        best = -1
        best_score = 0
        for i in range(n):
            if not is_vowel[i] and sums[i] > best_score:
                best_score, best = sums[i], i
        if best < 0:
            break
        is_vowel[best] = True
        scores[alphabet[best]] = best_score
        for j in range(n):
            if not is_vowel[j]:
                sums[j] -= 2 * matrix[j][best]
    vowels = [alphabet[i] for i in range(n) if is_vowel[i]]
    consonants = [alphabet[i] for i in range(n) if not is_vowel[i]]
    return vowels, consonants, scores


def vowel_profile(words: Sequence) -> VowelProfile:
    text = "".join(words)
    vowels, consonants, scores = sukhotin_vowels(text)
    vowel_set = set(vowels)
    transitions = 0
    alternations = 0
    for word in words:
        for a, b in zip(word, word[1:]):
            transitions += 1
            if (a in vowel_set) != (b in vowel_set):
                alternations += 1
    rate = alternations / transitions if transitions else 0.0
    counts = Counter(text)
    total = sum(counts.values()) or 1
    p_vowel = sum(counts[v] for v in vowels) / total
    expected = 2 * p_vowel * (1 - p_vowel)
    return VowelProfile(
        vowels=vowels,
        consonants=consonants,
        scores=scores,
        alternation_rate=rate,
        expected_alternation=expected,
    )


# --------------------------------------------------------------------------
# One-shot bundle
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def tokenize(text: str) -> list:
    """Split arbitrary text into lowercase word tokens (for control corpora)."""
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


@dataclass
class StatBundle:
    """The headline numbers, used for comparing texts side by side."""

    label: str
    tokens: int
    types: int
    h1: float
    h2: float
    mean_word_length: float
    ttr: float
    mattr: float
    hapax_ratio: float
    zipf_slope: float
    heaps_beta: float
    immediate_repeat_rate: float
    binomial_fit_error: float
    slot_conformance: float = 0.0

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "tokens": self.tokens,
            "types": self.types,
            "h1": round(self.h1, 4),
            "h2": round(self.h2, 4),
            "mean_word_length": round(self.mean_word_length, 3),
            "ttr": round(self.ttr, 5),
            "mattr": round(self.mattr, 5),
            "hapax_ratio": round(self.hapax_ratio, 4),
            "zipf_slope": round(self.zipf_slope, 4),
            "heaps_beta": round(self.heaps_beta, 4),
            "immediate_repeat_rate": round(self.immediate_repeat_rate, 5),
            "binomial_fit_error": round(self.binomial_fit_error, 5),
            "slot_conformance": round(self.slot_conformance, 4),
        }

    @staticmethod
    def headers() -> list:
        return [
            "label",
            "tokens",
            "types",
            "h1",
            "h2",
            "mean_len",
            "ttr",
            "mattr",
            "hapax",
            "zipf",
            "heaps",
            "repeat",
            "binom_err",
            "slots",
        ]

    def row(self) -> list:
        return [
            self.label,
            self.tokens,
            self.types,
            round(self.h1, 3),
            round(self.h2, 3),
            round(self.mean_word_length, 2),
            round(self.ttr, 4),
            round(self.mattr, 4),
            round(self.hapax_ratio, 3),
            round(self.zipf_slope, 3),
            round(self.heaps_beta, 3),
            round(self.immediate_repeat_rate, 4),
            round(self.binomial_fit_error, 3),
            round(self.slot_conformance, 3),
        ]


def stat_bundle(words: Sequence, label: str = "", with_slots: bool = True) -> StatBundle:
    """Compute the comparison headline numbers for a word list."""
    words = list(words)
    entropy = entropy_profile(words)
    lengths = word_length_profile(words)
    vocab = vocabulary_profile(words)
    zipf = zipf_profile(words)
    repeats = repeat_profile(words, max_lag=3)
    slots = slot_profile(words) if with_slots else None
    return StatBundle(
        label=label,
        tokens=len(words),
        types=vocab.types,
        h1=entropy.h1,
        h2=entropy.h2,
        mean_word_length=lengths.mean,
        ttr=vocab.ttr,
        mattr=vocab.mattr,
        hapax_ratio=vocab.hapax_ratio,
        zipf_slope=zipf.slope,
        heaps_beta=vocab.heaps_beta,
        immediate_repeat_rate=repeats.immediate_rate,
        binomial_fit_error=lengths.binomial_fit_error,
        slot_conformance=slots.conformance if slots else 0.0,
    )


def compare_bundles(bundles: Iterable) -> list:
    """Turn several :class:`StatBundle` objects into printable table rows."""
    return [b.row() for b in bundles]
