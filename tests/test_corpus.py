"""Tests for corpus loading, selection and folio metadata.

These run against the bundled ZL transliteration, so they also serve as a check
that the shipped data files are intact.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from tvtt.corpus import Selection, load_corpus, resolve_transcription, selection_from_dict
from tvtt.errors import ConfigError
from tvtt.folios import SECTION_NAMES, load_folios, parse_folio_range


@pytest.fixture(scope="module")
def corpus():
    return load_corpus("zl")


def test_the_whole_manuscript_is_present(corpus):
    assert len(corpus.loci) == 5374
    assert len(corpus.pages) == 227
    assert corpus.alphabet == "Eva-"
    assert len(corpus.words()) == 39015


def test_a_drawing_interruption_is_a_word_break(corpus):
    """``<->`` implies a word space; stripping it silently fuses two words."""
    line = next(locus for locus in corpus.loci if locus.locus_id == "<f1v.1,@P0>")
    assert "ol.o" in line.text
    assert "olo" not in line.text
    assert line.interrupted


def test_paragraph_marks_come_from_the_markers_not_the_locator(corpus):
    """The locator character is spatial; only <%> and <$> define paragraphs."""
    starts = [locus for locus in corpus.loci if locus.para_start]
    ends = [locus for locus in corpus.loci if locus.para_end]
    assert len(starts) == len(ends) == 740
    assert all("<%>" in locus.raw for locus in starts)
    assert all("<$>" in locus.raw for locus in ends)
    # '=' is "on the same line as the previous item", not "end of paragraph".
    same_line = [locus for locus in corpus.loci if locus.prefix == "=" and not locus.para_end]
    assert same_line


def test_a_run_of_question_marks_is_one_unknown_length(corpus):
    """``???`` means an unknown number of characters, not exactly three."""
    assert not any("??" in locus.text for locus in corpus.loci)


def test_legacy_transcription_names_still_resolve():
    assert resolve_transcription("eva").key == "zl"
    assert resolve_transcription("v121").key == "v101"


def test_unknown_transcription_lists_the_alternatives():
    with pytest.raises(ConfigError) as excinfo:
        resolve_transcription("nope")
    assert "zl" in str(excinfo.value)


def test_folio_metadata_covers_every_page():
    folios = load_folios()
    assert len(folios) == 227
    assert folios.get("f1r").illustration == "T"
    assert folios.get("1v").illustration_name == "herbal"
    assert folios.get("1r").currier == "A"


def test_every_named_section_is_non_empty():
    folios = load_folios()
    for name in SECTION_NAMES:
        assert folios.in_section(name), name


def test_scribe_attribution_is_present():
    folios = load_folios()
    assigned = sum(len(folios.by_scribe(s)) for s in "12345")
    assert assigned > 200


def test_section_selection_is_a_subset(corpus):
    herbal = corpus.select(Selection(sections=("herbal_a",)))
    assert 0 < len(herbal.loci) < len(corpus.loci)
    assert all(locus.key in corpus.folios.in_section("herbal_a") for locus in herbal.loci)


def test_currier_split_is_disjoint(corpus):
    a = corpus.select(Selection(currier="A"))
    b = corpus.select(Selection(currier="B"))
    assert set(a.folio_keys()).isdisjoint(b.folio_keys())
    assert len(a.loci) + len(b.loci) <= len(corpus.loci)


def test_currier_a_is_not_a_contiguous_line_range(corpus):
    """The A/B split is per folio, which a single cutoff line cannot express."""
    a_keys = set(corpus.select(Selection(currier="A")).folio_keys())
    indices = [i for i, locus in enumerate(corpus.loci) if locus.key in a_keys]
    assert indices[-1] - indices[0] + 1 > len(indices)


def test_labels_and_running_text_are_different(corpus):
    labels = corpus.select(Selection(text_class="labels"))
    running = corpus.select(Selection(text_class="running"))
    assert all(locus.is_label for locus in labels.loci)
    assert all(locus.is_paragraph for locus in running.loci)
    label_words = labels.words()
    running_words = running.words()
    assert sum(map(len, label_words)) / len(label_words) != sum(map(len, running_words)) / len(running_words)


def test_first_line_and_first_word_selection(corpus):
    first_lines = corpus.select(Selection(lines="first"))
    assert all(locus.para_start for locus in first_lines.loci)

    first_words = corpus.select(Selection(words="first", text_class="running"))
    assert all(len(locus.words()) == 1 for locus in first_words.loci)


def test_scribe_and_quire_filters(corpus):
    scribe2 = corpus.select(Selection(scribes=("2",)))
    assert scribe2.loci
    assert all(corpus.folios.get(locus.key).scribe == "2" for locus in scribe2.loci)

    quire = corpus.select(Selection(quires=("A",)))
    assert all(corpus.folios.get(locus.key).quire == "A" for locus in quire.loci)


def test_locus_type_filter(corpus):
    zodiac = corpus.select(Selection(locus_types=("Lz",)))
    assert zodiac.loci
    assert all(locus.locus_type == "Lz" for locus in zodiac.loci)


def test_folio_range_selection(corpus):
    subset = corpus.select(Selection(folios=("1r-2v",)))
    assert set(subset.folio_keys()) <= {"1r", "1v", "2r", "2v"}


def test_folio_range_expansion():
    assert parse_folio_range("1r-2r") == ["1r", "1v", "2r"]
    assert parse_folio_range("f68r2") == ["68r2"]


def test_filters_combine_with_and(corpus):
    combined = corpus.select(Selection(sections=("herbal_b",), text_class="running", currier="B"))
    assert combined.loci
    assert all(locus.is_paragraph for locus in combined.loci)


def test_line_range_still_works(corpus):
    subset = corpus.select(Selection(start_line=10, end_line=20))
    assert len(subset.loci) == 11
    assert subset.loci[0].text == corpus.loci[9].text


def test_selection_from_config_dict():
    selection = selection_from_dict({"sections": ["herbal_a"], "currier": "A", "textClass": "running", "scribes": [1]})
    assert selection.sections == ("herbal_a",)
    assert selection.scribes == ("1",)


def test_invalid_selection_is_reported_clearly():
    with pytest.raises(ConfigError) as excinfo:
        selection_from_dict({"sections": ["not_a_section"]})
    assert "herbal_a" in str(excinfo.value)


def test_split_sections_produces_non_empty_parts(corpus):
    parts = corpus.split_sections(("herbal_a", "biological"))
    assert set(parts) == {"herbal_a", "biological"}
    assert all(not part.is_empty for part in parts.values())


def test_ambiguity_flags_are_recorded(corpus):
    assert any(locus.had_alternates for locus in corpus.loci)
    dropped = corpus.select(replace(corpus.selection, drop_ambiguous=True))
    assert len(dropped.loci) < len(corpus.loci)


@pytest.mark.parametrize("key", ["v101", "takahashi", "currier", "fsg", "reference"])
def test_every_bundled_transcription_parses(key):
    other = load_corpus(key)
    assert other.loci
    assert other.words()


def test_quire_numbers_match_the_literature():
    """Everyone cites 'Quire 13' and 'Quire 20'; $Q stores them as M and T."""
    from tvtt.folios import quire_label, quire_number

    folios = load_folios()
    assert quire_number("A") == 1
    assert quire_number("M") == 13
    assert quire_number("T") == 20
    # Quires 16 and 18 do not exist, so P and R are skipped.
    assert quire_number("O") == 15
    assert quire_number("Q") == 17
    assert quire_number("S") == 19
    quires_present = {folios.get(k).quire for k in folios.keys()}  # noqa: SIM118
    assert "P" not in quires_present
    assert "R" not in quires_present
    # The bathing-nymphs quire and the recipes quire.
    assert folios.get("75r").quire_number == 13
    assert folios.get("103r").quire_number == 20
    assert quire_label("M") == "13 (M)"


def test_a_quire_can_be_selected_by_number_or_letter():
    folios = load_folios()
    assert folios.by_quire("13") == folios.by_quire("M")
    assert folios.by_quire("20") == folios.by_quire("T")


def test_locus_type_names_match_where_they_actually_occur():
    """Lf and Lp were once the wrong way round; the data settles it."""
    from collections import Counter

    from tvtt.ivtff import LOCUS_TYPE_NAMES

    corpus = load_corpus("zl")
    sections = {}
    for locus in corpus.loci:
        sections.setdefault(locus.locus_type, Counter())[corpus.folios.get(locus.key).illustration] += 1

    # Every one of these is 100% confined to the section its name claims.
    assert set(sections["Lf"]) == {"P"}, "Lf is a pharmaceutical label"
    assert set(sections["Lc"]) == {"P"}, "Lc is a pharmaceutical container label"
    assert set(sections["Lp"]) == {"H"}, "Lp is a herbal plant label"
    assert set(sections["Ln"]) == {"B"}, "Ln is a biological nymph label"
    assert set(sections["Lt"]) == {"B"}, "Lt is a biological tube label"
    assert set(sections["Lz"]) == {"Z"}, "Lz is a zodiac label"
    assert set(sections["Ls"]) == {"A"}, "Ls is a star label"

    assert "pharmaceutical" in LOCUS_TYPE_NAMES["Lf"]
    assert "herbal" in LOCUS_TYPE_NAMES["Lp"]
    assert "biological" in LOCUS_TYPE_NAMES["Lt"]


def test_illustration_and_extraneous_names_follow_the_specification():
    from tvtt.folios import EXTRANEOUS_NAMES, ILLUSTRATION_NAMES

    assert ILLUSTRATION_NAMES["S"] == "marginal stars only"
    assert ILLUSTRATION_NAMES["A"] == "astronomical (excluding zodiac)"
    assert "sequence" in EXTRANEOUS_NAMES["S"]
    assert "deprecated" in EXTRANEOUS_NAMES["V"]
