"""Tests for the dictionary tools and the matcher."""

from __future__ import annotations

import pytest

from tvtt import lexicon as L
from tvtt.matcher import Matcher, MatchOptions, significance


@pytest.fixture(scope="module")
def latin():
    return L.load_dictionary("latin")


# --------------------------------------------------------------------------
# Distances and phonetics
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b,expected",
    [("kitten", "sitting", 3), ("abc", "abc", 0), ("", "abc", 3), ("ab", "ba", 2)],
)
def test_levenshtein(a, b, expected):
    assert L.levenshtein(a, b) == expected


def test_damerau_counts_a_transposition_as_one_edit():
    assert L.damerau_levenshtein("ab", "ba") == 1
    assert L.levenshtein("ab", "ba") == 2


def test_distance_limit_short_circuits():
    assert L.levenshtein("abcdefgh", "zzzzzzzz", limit=2) > 2


def test_metaphone_matches_sound_not_spelling():
    assert L.metaphone("philosophia") == L.metaphone("filosofia")
    assert L.metaphone("christus") != L.metaphone("kristus")


def test_soundex_basics():
    assert L.soundex("Robert") == L.soundex("Rupert")
    assert len(L.soundex("Tymczak")) == 4


def test_consonant_skeleton_drops_vowels():
    assert L.consonant_skeleton("dominus") == "dmns"
    assert L.consonant_skeleton("aeiou") == ""


def test_abjad_index_groups_by_skeleton():
    index = L.abjad_index(["dominus", "domnus", "amare"])
    assert set(index["dmns"]) == {"dominus", "domnus"}


# --------------------------------------------------------------------------
# Abbreviations and stemming
# --------------------------------------------------------------------------


def test_abbreviation_expansion_keeps_the_original_first():
    expansions = L.expand_abbreviations("natu9")
    assert expansions[0] == "natu9"
    assert "natuus" in expansions


def test_known_contraction_is_expanded():
    assert "dominus" in L.expand_abbreviations("dns")


def test_stemmer_folds_inflections():
    stemmer = L.Stemmer("latin")
    assert stemmer.stem("dominus") == stemmer.stem("dominorum")


def test_stemmer_keeps_a_minimum_stem():
    stemmer = L.Stemmer("latin", min_stem=3)
    assert stemmer.stem("est") == "est"


# --------------------------------------------------------------------------
# Fuzzy index
# --------------------------------------------------------------------------


def test_fuzzy_index_finds_near_matches():
    index = L.FuzzyIndex(["dominus", "domino", "amare", "virum", "aeneas"])
    hit = index.best("dominos", 1)
    # Both 'dominus' and 'domino' are one edit away; either is a correct answer.
    assert hit is not None and hit[1] == 1 and hit[0] in ("dominus", "domino")
    assert index.best("zzzzzz", 1) is None


def test_fuzzy_index_recall_matches_a_brute_force_search():
    """The trigram filter must never discard a word that is genuinely close."""
    words = sorted(L.load_dictionary("latin").words)[:4000]
    index = L.FuzzyIndex(words)
    probes = ["dominos", "amaret", "virrum", "aenea", "foliis", "temp", "quibusdm"]
    for probe in probes:
        brute = {w for w in words if L.damerau_levenshtein(probe, w, 2) <= 2}
        found = {w for w, _d in index.search(probe, 2, limit=len(words))}
        assert brute == found, probe


def test_fuzzy_index_returns_exact_matches_first():
    index = L.FuzzyIndex(["amare", "amarem", "amaret"])
    assert index.search("amare", 2)[0] == ("amare", 0)


def test_split_word_recovers_two_known_words():
    vocabulary = {"dominus", "deus", "et"}
    assert L.split_word("dominusdeus", vocabulary) == ["dominus", "deus"]
    assert L.split_word("zzzzzz", vocabulary) == []


# --------------------------------------------------------------------------
# Dictionaries
# --------------------------------------------------------------------------


def test_bundled_latin_dictionary_loads(latin):
    assert len(latin) > 10000
    assert "et" in latin
    assert latin.stopwords(5)[0] == "et"


def test_rare_words_weigh_more_than_common_ones(latin):
    assert latin.weight("et") < latin.weight("foliis")


def test_mean_weight_is_the_unigram_entropy(latin):
    assert 5 < latin.mean_weight() < 20


def test_every_bundled_dictionary_loads():
    for name in L.BUNDLED_LANGUAGES:
        dictionary = L.load_dictionary(name)
        assert len(dictionary) > 100, name


def test_unknown_dictionary_lists_the_alternatives():
    from tvtt.errors import DataError

    with pytest.raises(DataError) as excinfo:
        L.load_dictionary("klingon")
    assert "latin" in str(excinfo.value)


# --------------------------------------------------------------------------
# Matcher
# --------------------------------------------------------------------------


def test_real_latin_scores_near_perfect(latin):
    from tvtt.langmodel import control_text

    words = L.tokenize(control_text("latin"))[:3000]
    report = Matcher(latin, MatchOptions(max_edits=0, allow_fuzzy=False)).match_text(words)
    assert report.coverage > 0.95
    assert report.route_counts["exact"] > 2500


def test_nonsense_scores_far_lower(latin):
    import random

    rng = random.Random(9)
    words = ["".join(rng.choice("qxzjkwy") for _ in range(6)) for _ in range(1500)]
    report = Matcher(latin, MatchOptions(max_edits=0, allow_fuzzy=False, allow_split=False)).match_text(words)
    assert report.coverage < 0.05


def test_routes_are_tried_in_order_of_trust(latin):
    matcher = Matcher(latin, MatchOptions(max_edits=1))
    assert matcher.match_word("et").route == "exact"
    assert matcher.match_word("zzzzzzzzzz").route == "none"


def test_confidence_falls_with_edit_distance(latin):
    matcher = Matcher(latin, MatchOptions(max_edits=2))
    exact = matcher.match_word("dominus")
    fuzzy = matcher.match_word("dominux")
    assert exact.confidence == 1.0
    assert 0 < fuzzy.confidence < exact.confidence


def test_stopword_alignment_is_high_for_real_text_and_low_for_noise(latin):
    from tvtt.langmodel import control_text

    real = L.tokenize(control_text("latin"))[:4000]
    good = Matcher(latin, MatchOptions(max_edits=0, allow_fuzzy=False)).match_text(real)

    import random

    rng = random.Random(3)
    noise = ["".join(rng.choice("abcdefg") for _ in range(5)) for _ in range(4000)]
    bad = Matcher(latin, MatchOptions(max_edits=0, allow_fuzzy=False)).match_text(noise)

    assert good.stopword_coverage > bad.stopword_coverage


def test_merge_route_joins_two_words(latin):
    matcher = Matcher(latin, MatchOptions(max_edits=0, allow_fuzzy=False, allow_split=False))
    report = matcher.match_text(["aene", "as"])
    merged = [m for m in report.matches if m.route == "merge"]
    assert merged and merged[0].matched == "aeneas" and merged[0].consumed == 2


def test_a_word_that_stands_alone_is_not_merged_away(latin):
    """'domi' is a real Latin word, so it must not be swallowed by a merge."""
    matcher = Matcher(latin, MatchOptions(max_edits=0, allow_fuzzy=False, allow_split=False))
    report = matcher.match_text(["domi", "et"])
    assert [m.route for m in report.matches] == ["exact", "exact"]


def test_significance_report():
    result = significance(0.5, [0.1, 0.12, 0.09, 0.11], "coverage")
    assert result.z_score > 4
    assert result.percentile == 100.0
