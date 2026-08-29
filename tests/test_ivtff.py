"""Tests for the IVTFF parser."""

from __future__ import annotations

import pytest

from tvtt.ivtff import (
    PUA_BASE,
    ParseOptions,
    folio_sort_key,
    high_ascii_label,
    normalise_folio,
    parse_text,
    resolve_text,
)

SAMPLE = """#=IVTFF Eva- 2.0 M 5
# a comment line
<f1r>      <! $Q=A $P=A $F=a $B=1 $I=T $L=A $H=1 $C=1 $X=V>
<f1r.1,@P0>       <%>fachys.ykal.ar.[cth:oto]res.y<!@254;>
<f1r.2,+P0>       sory.ckhar.or,y.{ck}eo
<f1r.3,=Pt>       dchaiin<$>
<f1v>      <! $I=H $L=B $H=2>
<f1v.1,@Lf>       okeo.?ain
"""


def parse(**kwargs):
    return parse_text(SAMPLE, options=ParseOptions(**kwargs))


def test_header_and_counts():
    doc = parse()
    assert doc.alphabet == "Eva-"
    assert doc.version == "2.0"
    assert len(doc.loci) == 4
    assert len(doc.pages) == 2


def test_page_variables_are_read():
    doc = parse()
    page = doc.pages["1r"]
    assert page.illustration == "T"
    assert page.currier_language == "A"
    assert page.scribe == "1"
    assert page.currier_hand == "1"
    assert doc.pages["1v"].currier_language == "B"


def test_locus_metadata():
    doc = parse()
    first, second, third, label = doc.loci
    assert first.locus_id == "<f1r.1,@P0>"
    assert first.para_start and not first.para_end
    assert third.para_end
    assert label.is_label and label.locus_type == "Lf"
    assert second.words() == ["sory", "ckhar", "or", "y", "ckeo"]


def test_inline_markup_is_removed_but_ligature_contents_kept():
    doc = parse()
    assert "<%>" not in doc.loci[0].text
    assert "@254;" not in doc.loci[0].text
    assert "ckeo" in doc.loci[1].text


def test_ligatures_can_be_dropped():
    doc = parse(ligatures="drop")
    assert "eo" in doc.loci[1].text
    assert "ckeo" not in doc.loci[1].text


@pytest.mark.parametrize(
    "mode,expected",
    [("first", "cthres"), ("last", "otores")],
)
def test_alternate_readings(mode, expected):
    doc = parse(alternates=mode)
    assert expected in doc.loci[0].text
    assert doc.loci[0].had_alternates


def test_alternate_variants_are_recorded():
    doc = parse(alternates="variants")
    assert len(doc.loci[0].variants) == 2


def test_alternate_drop_line_removes_the_locus():
    doc = parse(alternates="drop_line")
    assert len(doc.loci) == 3
    assert doc.dropped == 1


def test_uncertain_space_modes():
    assert "or,y" in parse().loci[1].text
    assert "or.y" in parse(uncertain_space="space").loci[1].text
    assert "ory" in parse(uncertain_space="join").loci[1].text


def test_unreadable_modes():
    assert parse().loci[3].had_unreadable
    assert "?ain" in parse().loci[3].text
    assert parse(unreadable="drop_word").loci[3].words() == ["okeo"]
    assert parse(unreadable="placeholder", unreadable_char="*").loci[3].text.endswith("*ain")
    assert len(parse(unreadable="drop_line").loci) == 3


def test_high_ascii_becomes_one_character():
    text, _alt, _unread = resolve_text("ok@253;ar", ParseOptions(), eva_family=True)
    assert len(text[0]) == 5
    assert text[0][2] == chr(PUA_BASE + 253)
    assert high_ascii_label(text[0][2]) == "@253;"


def test_high_ascii_can_be_kept_or_dropped():
    keep, _a, _u = resolve_text("ok@253;ar", ParseOptions(high_ascii="keep"), True)
    drop, _a, _u = resolve_text("ok@253;ar", ParseOptions(high_ascii="drop"), True)
    assert keep[0] == "ok@253;ar"
    assert drop[0] == "okar"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("f1r", "1r"),
        ("1r", "1r"),
        ("F68R2", "68r2"),
        ("fRos", "ros"),
        ("rose", "ros"),
        ("101r1-r2", "101r1"),
    ],
)
def test_folio_normalisation(raw, expected):
    assert normalise_folio(raw) == expected


def test_folio_sort_order():
    keys = ["10r", "2v", "1r", "1v", "2r"]
    assert sorted(keys, key=folio_sort_key) == ["1r", "1v", "2r", "2v", "10r"]


def test_native_v101_layout_is_understood():
    doc = parse_text("<1r.1>fa19s.9,hae-\n<1r.labels_1>2oe=\n")
    assert len(doc.loci) == 2
    assert doc.loci[0].text == "fa19s.9,hae"
    assert doc.loci[1].locus_type == "L0"


def test_empty_input_is_a_clear_error():
    from tvtt.errors import DataError

    with pytest.raises(DataError):
        parse_text("# nothing here\n")
