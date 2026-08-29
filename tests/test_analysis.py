"""Tests for the statistics.

Where a measure has a known correct value on a constructed input, that value is
asserted directly.  Where it does not, the test asserts the *ordering* the
measure exists to detect - which is what the tool actually relies on.
"""

from __future__ import annotations

import random

import pytest

from tvtt import analysis as A
from tvtt import baselines as B


def test_entropy_of_a_uniform_alphabet():
    assert A.shannon_entropy({"a": 1, "b": 1, "c": 1, "d": 1}) == pytest.approx(2.0)
    assert A.shannon_entropy({"a": 1}) == pytest.approx(0.0)


def test_conditional_entropy_is_zero_for_a_perfect_cycle():
    assert A.conditional_entropy("abcabcabcabcabc", 1) == pytest.approx(0.0, abs=1e-9)


def test_conditional_entropy_falls_as_order_rises():
    text = "the quick brown fox jumps over the lazy dog " * 40
    h1 = A.conditional_entropy(text, 0)
    h2 = A.conditional_entropy(text, 1)
    h3 = A.conditional_entropy(text, 2)
    assert h1 > h2 > h3


def test_entropy_profile_shape():
    profile = A.entropy_profile(["abc", "abd", "abc"])
    assert profile.alphabet_size == 4
    assert profile.characters == 9
    assert profile.h0 == pytest.approx(2.0)


def test_word_length_profile_basics():
    profile = A.word_length_profile(["a", "bb", "ccc", "bb"])
    assert profile.total == 4
    assert profile.mean == pytest.approx(2.0)
    assert profile.peak_length == 2
    assert profile.counts == {1: 1, 2: 2, 3: 1}


def test_dispersion_separates_tight_from_spread():
    tight = ["abcde"] * 200 + ["abcd", "abcdef"] * 20
    spread = ["a", "ab", "abcdefghijkl"] * 80
    assert A.word_length_profile(tight).dispersion < A.word_length_profile(spread).dispersion


def test_moving_average_ttr_is_length_independent():
    words = [str(i % 300) for i in range(3000)]
    short = A.moving_average_ttr(words[:1200], 200)
    long = A.moving_average_ttr(words, 200)
    assert short == pytest.approx(long, abs=0.05)


def test_ttr_falls_with_length_but_mattr_does_not():
    words = [str(i % 400) for i in range(4000)]
    assert A.vocabulary_profile(words[:800]).ttr > A.vocabulary_profile(words).ttr


def test_heaps_beta_is_one_when_every_word_is_new():
    words = [str(i) for i in range(2000)]
    _k, beta, _points = A.heaps_law(words)
    assert beta == pytest.approx(1.0, abs=0.05)


def test_hapax_counting():
    profile = A.vocabulary_profile(["a", "a", "b", "c", "c", "c", "d"])
    assert profile.hapax == 2
    assert profile.types == 4
    assert profile.tokens == 7


def test_zipf_recovers_a_planted_exponent():
    words = []
    for rank in range(1, 220):
        words.extend([("w%d" % rank)] * max(1, int(6000 / rank)))
    profile = A.zipf_profile(words)
    assert abs(profile.slope) == pytest.approx(1.0, abs=0.12)
    assert profile.r_squared > 0.95


def test_ngram_profile_counts_boundaries():
    profile = A.ngram_profile(["ab", "ab"], boundary="_")
    assert "_" in profile.alphabet
    pairs = dict(profile.top_bigrams)
    assert pairs["ab"] == 2
    assert pairs["_a"] == 2


def test_ngram_counts_by_order():
    counts = A.ngram_counts(["abcd"], 2)
    assert counts["ab"] == 1 and counts["bc"] == 1 and counts["cd"] == 1


def test_positional_entropy_is_zero_for_a_fixed_position():
    profile = A.positional_profile(["qaaa"] * 40)
    assert profile.entropy["q"] == pytest.approx(0.0)
    assert "q" in profile.initial_only


def test_positional_profile_finds_word_final_glyphs():
    profile = A.positional_profile(["aaan"] * 40)
    assert "n" in profile.final_only


def test_slot_profile_detects_a_template():
    templated = ["q" + "o" * n + "y" for n in range(1, 6)] * 40
    free = ["".join(random.Random(i).choice("qoy") for _ in range(5)) for i in range(200)]
    assert A.slot_profile(templated).conformance >= A.slot_profile(free).conformance


def test_affixes_rank_a_planted_suffix_first():
    words = ["chol", "shol", "dol", "kol"] * 60 + ["qqq", "zzz"] * 5
    profile = A.affix_profile(words, sizes=(2,), min_count=5)
    assert profile.suffixes[0]["affix"] == "ol"


def test_repeat_profile_detects_immediate_repetition():
    repeated = ["a", "a", "b", "b", "c", "c"] * 50
    varied = [str(i) for i in range(300)]
    assert A.repeat_profile(repeated).immediate_rate > A.repeat_profile(varied).immediate_rate
    assert A.repeat_profile(repeated).clustering_ratio > 1.5


def test_line_profile_detects_a_restricted_line_start():
    lines = [["START", "a", "b"], ["START", "c", "d"], ["START", "e", "f"]] * 20
    profile = A.line_profile(lines, [True] * len(lines))
    assert profile.laafu_score == pytest.approx(1.0)


def test_sukhotin_finds_the_vowels_of_a_regular_language():
    words = ["kata", "tako", "mira", "nako", "sami", "rota"] * 40
    vowels, consonants, _scores = A.sukhotin_vowels("".join(words))
    assert set("aio") & set(vowels)
    assert len(vowels) < len(consonants)


def test_alternation_excess_is_high_for_strict_cv_text():
    strict = A.vowel_profile(["kataka", "mirami", "nasana"] * 60)
    assert strict.alternation_rate > strict.expected_alternation


def test_stat_bundle_row_matches_headers():
    bundle = A.stat_bundle(["abc", "abd", "abc"], "x")
    assert len(bundle.row()) == len(A.StatBundle.headers())


def test_tokenize_lowercases_and_drops_punctuation():
    assert A.tokenize("Arma virumque, cano!") == ["arma", "virumque", "cano"]


# --------------------------------------------------------------------------
# The measures must actually separate real structure from shuffled text
# --------------------------------------------------------------------------


def test_conditional_entropy_rises_when_words_are_anagrammed():
    words = ["chol", "chor", "shol", "qokeedy", "qokeey", "daiin"] * 200
    rng = random.Random(4)
    shuffled = B.shuffle_within_words(words, rng)
    assert A.entropy_profile(shuffled).h2 > A.entropy_profile(words).h2


def test_shuffling_word_order_leaves_the_vocabulary_alone():
    words = ["a", "bb", "ccc"] * 100
    shuffled = B.shuffle_words(words, random.Random(1))
    assert sorted(shuffled) == sorted(words)


def test_character_shuffle_preserves_word_lengths():
    words = ["abc", "de", "fghi"]
    shuffled = B.shuffle_characters(words, random.Random(2))
    assert [len(w) for w in shuffled] == [len(w) for w in words]


def test_synthetic_text_reuses_the_source_alphabet():
    source = ["chol", "chor", "shol", "daiin", "qokeedy"] * 50
    generated = B.synthetic_voynichese(source, B.SyntheticOptions(length=500), random.Random(3))
    assert len(generated) == 500
    assert set("".join(generated)) <= set("".join(source))


def test_control_distribution_places_an_observation():
    distribution = B.ControlDistribution("m", observed=10.0, scores=[1.0, 2.0, 3.0, 4.0])
    assert distribution.percentile == 100.0
    assert distribution.z_score > 2
    assert "random" in distribution.verdict() or "above" in distribution.verdict()


def test_overfitting_level_rises_with_rule_count():
    low = B.OverfittingReport(rules=30, extra_rules=2, glyphs=28, baseline_score=1.0, score=1.2, tokens=1000)
    high = B.OverfittingReport(rules=90, extra_rules=60, glyphs=28, baseline_score=1.0, score=1.2, tokens=1000)
    assert low.level() in ("low", "moderate")
    assert high.level() == "severe"


def test_holdout_drop_is_reported():
    report = B.HoldoutReport("A", "B", fit_score=1.0, holdout_score=0.5, metric="q")
    assert report.drop == pytest.approx(0.5)
    assert "memoris" in report.verdict() or "collapses" in report.verdict()


# --------------------------------------------------------------------------
# Positional search
# --------------------------------------------------------------------------


def _search_problem(positions, min_occurrences=25):
    from collections import Counter

    from tvtt.corpus import Selection, load_corpus
    from tvtt.langmodel import Fitness, FitnessOptions
    from tvtt.mapping import Mapping
    from tvtt.solver import Problem
    from tvtt.transliterate import build_engine

    corpus = load_corpus("zl").select(Selection(sections=("zodiac",)))
    engine = build_engine(Mapping.from_dict({"rules": {}}), corpus)
    vocabulary = Counter(corpus.words())
    fitness = Fitness(FitnessOptions(function="quadgram", language="latin"), vocabulary)
    problem = Problem(vocabulary, engine, fitness, positions=positions, min_occurrences=min_occurrences)
    return corpus, problem


def test_positions_add_searchable_units():
    _, plain = _search_problem("none")
    _, edges = _search_problem("edges")
    _, every = _search_problem("all")
    assert len(plain.units) == len(plain.glyphs)
    assert len(edges.units) > len(plain.units)
    assert len(every.units) > len(edges.units)


def test_a_positional_search_reproduces_the_text_it_scored():
    """The mapping handed back must produce exactly what the search measured."""
    from tvtt.solver import SearchOptions, solve
    from tvtt.transliterate import build_engine

    for positions in ("none", "edges", "all"):
        corpus, problem = _search_problem(positions)
        result = solve(problem, SearchOptions(method="hillclimb", iterations=1500, restarts=1, seed=3))
        scored = problem.render_all(result.best_letters)
        engine = build_engine(result.as_mapping(problem), corpus)
        assert scored == [engine.map_word(w) for w in problem.types], positions


def test_a_rare_position_does_not_become_a_free_parameter():
    _, strict = _search_problem("all", min_occurrences=100000)
    _, loose = _search_problem("all", min_occurrences=1)
    assert len(strict.units) == len(strict.glyphs), "nothing should clear an impossible threshold"
    assert len(loose.units) > len(strict.units)


def test_locking_a_glyph_locks_all_of_its_positions():
    from collections import Counter

    from tvtt.corpus import Selection, load_corpus
    from tvtt.langmodel import Fitness, FitnessOptions
    from tvtt.mapping import Mapping
    from tvtt.solver import Problem, SearchOptions, solve
    from tvtt.transliterate import build_engine

    corpus = load_corpus("zl").select(Selection(sections=("zodiac",)))
    engine = build_engine(Mapping.from_dict({"rules": {}}), corpus)
    vocabulary = Counter(corpus.words())
    fitness = Fitness(FitnessOptions(function="quadgram", language="latin"), vocabulary)
    problem = Problem(vocabulary, engine, fitness, positions="all", locked={"o": "z"})
    assert problem.locked, "the lock was not applied to any unit"
    result = solve(problem, SearchOptions(method="hillclimb", iterations=800, restarts=1, seed=1))
    for index in problem.locked:
        assert result.best_letters[index] == "z"


def test_the_solver_result_carries_structured_rules():
    from tvtt.mapping import SLOT_PLAIN
    from tvtt.solver import SearchOptions, solve

    _, problem = _search_problem("edges")
    result = solve(problem, SearchOptions(method="hillclimb", iterations=1000, restarts=1, seed=2))
    payload = result.to_dict(problem)
    assert payload["positions"] == "edges"
    assert payload["best_rules"], "no structured rules were recorded"
    # At least one glyph should have been given a rule beyond the plain one.
    assert any(isinstance(v, dict) and set(v) - {"plain"} for v in payload["best_rules"].values()) or any(
        isinstance(v, list) for v in payload["best_rules"].values()
    ), payload["best_rules"]
    assert SLOT_PLAIN is not None
