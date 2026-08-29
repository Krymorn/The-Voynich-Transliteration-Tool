"""Tests for the mapping engine.

Longest-match precedence and the occurrence rules are the two places where a
mapping most easily does something other than what its author intended, so
they get the most attention here.
"""

from __future__ import annotations

import pytest

from tvtt.errors import MappingError
from tvtt.mapping import (
    DEFAULT_MARKERS,
    SLOT_FINAL,
    SLOT_INITIAL,
    SLOT_OCC1,
    SLOT_OCC2,
    SLOT_PLAIN,
    Mapping,
    MappingEngine,
    identity_mapping,
    mapping_diff,
    random_mapping,
    round_trip_check,
)

GLYPHS = list("abcdefgho9'")


def engine_for(rules: dict, glyphs=GLYPHS, **kwargs) -> MappingEngine:
    return MappingEngine(Mapping(rules=rules), glyphs=glyphs, **kwargs)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def test_legacy_flat_format_reads_marker_suffixes():
    mapping = Mapping.from_dict({"f": "a@", "9": "b/", "o": "c'", "e": "d"})
    assert mapping.rules["f"] == {SLOT_INITIAL: "a"}
    assert mapping.rules["9"] == {SLOT_FINAL: "b"}
    assert mapping.rules["o"] == {SLOT_OCC1: "c"}
    assert mapping.rules["e"] == {SLOT_PLAIN: "d"}


def test_structured_format_takes_strings_literally():
    mapping = Mapping.from_dict({"rules": {"'": "'", "f": "a@"}})
    assert mapping.rules["'"] == {SLOT_PLAIN: "'"}
    assert mapping.rules["f"] == {SLOT_PLAIN: "a@"}


def test_a_bare_marker_is_kept_as_a_value():
    """The apostrophe is both a real EVA glyph and the occurrence marker."""
    mapping = Mapping.from_dict({"'": "'"})
    assert mapping.rules["'"] == {SLOT_PLAIN: "'"}


def test_structured_positions():
    mapping = Mapping.from_dict({"rules": {"9": {"plain": "n", "final": "s"}}})
    assert mapping.rules["9"] == {SLOT_PLAIN: "n", SLOT_FINAL: "s"}


def test_unknown_position_is_rejected_clearly():
    with pytest.raises(MappingError) as excinfo:
        Mapping.from_dict({"rules": {"a": {"middle": "x"}}})
    assert "middle" in str(excinfo.value)


def test_trailing_commas_are_tolerated(tmp_path):
    path = tmp_path / "m.json"
    path.write_text('{\n  "a": "x",\n  "b": "y",\n}\n', encoding="utf-8")
    assert Mapping.load(path).rules["b"] == {SLOT_PLAIN: "y"}


def test_broken_json_names_the_line(tmp_path):
    path = tmp_path / "m.json"
    path.write_text('{\n  "a": "x"\n  "b": "y"\n}\n', encoding="utf-8")
    with pytest.raises(MappingError) as excinfo:
        Mapping.load(path)
    assert "line" in str(excinfo.value)


def test_round_trip_through_both_formats():
    mapping = Mapping.from_dict({"rules": {"9": {"plain": "n", "final": "s"}, "a": "x"}})
    again = Mapping.from_dict(mapping.to_dict(structured=True))
    assert again.rules == mapping.rules
    flat = Mapping.from_dict(mapping.to_dict(structured=False, markers=DEFAULT_MARKERS))
    assert flat.rules == mapping.rules


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------


def test_plain_substitution():
    engine = engine_for({"a": {SLOT_PLAIN: "X"}})
    assert engine.map_word("abc") == "Xbc"


def test_longest_match_wins():
    engine = engine_for({"c": {SLOT_PLAIN: "1"}, "ch": {SLOT_PLAIN: "K"}}, glyphs=list("abch"))
    assert engine.map_word("chch") == "KK"
    assert engine.map_word("cach") == "1aK"


def test_three_way_longest_match():
    engine = engine_for(
        {"c": {SLOT_PLAIN: "1"}, "ch": {SLOT_PLAIN: "2"}, "cha": {SLOT_PLAIN: "3"}},
        glyphs=list("abch"),
    )
    assert engine.map_word("cha") == "3"
    assert engine.map_word("ch") == "2"
    assert engine.map_word("c") == "1"
    assert engine.map_word("chab") == "3b"
    assert engine.map_word("chbcha") == "2b3"


def test_one_glyph_to_many_letters():
    engine = engine_for({"9": {SLOT_PLAIN: "con"}}, glyphs=list("9a"))
    assert engine.map_word("9a9") == "conacon"


def test_word_initial_and_final_rules():
    engine = engine_for({"a": {SLOT_PLAIN: "m", SLOT_INITIAL: "I", SLOT_FINAL: "F"}})
    assert engine.map_word("aba") == "IbF"
    assert engine.map_word("bab") == "bmb"


def test_single_letter_word_uses_precedence():
    rules = {"a": {SLOT_PLAIN: "m", SLOT_INITIAL: "I", SLOT_FINAL: "F"}}
    assert engine_for(rules).map_word("a") == "I"
    assert engine_for(rules, precedence=("final", "initial", "occurrence", "plain")).map_word("a") == "F"


def test_occurrence_rules_count_within_the_word():
    engine = engine_for({"o": {SLOT_PLAIN: "z", SLOT_OCC1: "1", SLOT_OCC2: "2"}})
    assert engine.map_word("ooo") == "12z"
    assert engine.map_word("obo") == "1b2"


def test_occurrence_counter_resets_each_word():
    engine = engine_for({"o": {SLOT_PLAIN: "z", SLOT_OCC1: "1"}})
    assert engine.map_line("o.o", " ", " ") == "1 1"


def test_fifth_occurrence_falls_back_to_plain():
    engine = engine_for({"o": {SLOT_PLAIN: "z", SLOT_OCC1: "1", SLOT_OCC2: "2"}})
    assert engine.map_word("ooooo") == "12zzz"


def test_unmapped_glyph_policies():
    assert engine_for({"a": {SLOT_PLAIN: "X"}}, unmapped="keep").map_word("ab") == "Xb"
    assert engine_for({"a": {SLOT_PLAIN: "X"}}, unmapped="drop").map_word("ab") == "X"
    assert engine_for({"a": {SLOT_PLAIN: "X"}}, unmapped="placeholder", placeholder="#").map_word("ab") == "X#"


def test_separators_are_preserved():
    engine = engine_for({"a": {SLOT_PLAIN: "X"}})
    assert engine.map_line("ab.ab,ab", "_", "-") == "Xb_Xb-Xb"


def test_word_cache_is_invalidated_on_rule_change():
    engine = engine_for({"a": {SLOT_PLAIN: "X"}})
    engine.register_vocabulary(["ab", "ba"])
    assert engine.map_word("ab") == "Xb"
    engine.set_rule("a", "Y")
    assert engine.map_word("ab") == "Yb"
    assert engine.map_word("ba") == "bY"


def test_segmentation_is_independent_of_the_replacement():
    engine = engine_for({"ch": {SLOT_PLAIN: "K"}}, glyphs=list("abch"))
    before = engine.segment("chab")
    engine.set_rule("ch", "Z")
    assert engine.segment("chab") == before


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------


def test_collisions_are_detected():
    engine = engine_for({"a": {SLOT_PLAIN: "x"}, "b": {SLOT_PLAIN: "x"}})
    collisions = engine.collisions()
    assert "x" in collisions
    assert {g for g, _slot in collisions["x"]} == {"a", "b"}


def test_round_trip_reports_injectivity():
    good = engine_for({g: {SLOT_PLAIN: g.upper()} for g in "abc"}, glyphs=list("abc"))
    assert round_trip_check(good, ["abc", "cab"]).injective

    bad = engine_for({"a": {SLOT_PLAIN: "x"}, "b": {SLOT_PLAIN: "x"}}, glyphs=list("ab"))
    assert not round_trip_check(bad, ["ab"]).injective


def test_round_trip_terminates_with_an_empty_replacement():
    """Regression: an empty replacement once made the reverse walk loop forever."""
    engine = engine_for({"a": {SLOT_PLAIN: ""}, "b": {SLOT_PLAIN: "B"}}, glyphs=list("ab"))
    report = round_trip_check(engine, ["abab", "ba"])
    assert report.empty_rules == ["a"]


def test_conflicts_explain_the_winner():
    engine = engine_for(
        {"a": {SLOT_PLAIN: "m", SLOT_INITIAL: "I"}, "c": {SLOT_PLAIN: "1"}, "ch": {SLOT_PLAIN: "2"}},
        glyphs=list("abch"),
    )
    kinds = {c["kind"] for c in engine.conflicts()}
    assert kinds == {"position", "group"}
    group = next(c for c in engine.conflicts() if c["kind"] == "group")
    assert group["winner"] == "ch"


def test_complexity_counts_only_the_extra_rules():
    mapping = Mapping.from_dict({"rules": {"a": {"plain": "x", "final": "y"}, "b": "z"}})
    assert mapping.rule_count() == 3
    assert mapping.complexity() == 1


def test_identity_and_random_mappings():
    identity = identity_mapping("abc")
    assert identity.is_identity()
    import random

    generated = random_mapping("abcdef", rng=random.Random(1), injective=True)
    letters = [next(iter(s.values())) for s in generated.rules.values()]
    assert len(set(letters)) == len(letters)


def test_mapping_diff_lists_every_change():
    left = Mapping.from_dict({"rules": {"a": "x", "b": "y"}})
    right = Mapping.from_dict({"rules": {"a": "z", "c": "w"}})
    changes = {(c["glyph"], c["change"]) for c in mapping_diff(left, right)}
    assert ("a", "changed") in changes
    assert ("b", "removed") in changes
    assert ("c", "added") in changes


def test_signature_is_stable_and_sensitive():
    a = Mapping.from_dict({"rules": {"a": "x", "b": "y"}})
    b = Mapping.from_dict({"rules": {"b": "y", "a": "x"}})
    c = Mapping.from_dict({"rules": {"a": "x", "b": "z"}})
    assert a.signature() == b.signature()
    assert a.signature() != c.signature()
