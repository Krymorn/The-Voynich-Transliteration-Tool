"""Glyph frequency by folio or by section, as a heatmap."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from ..folios import SECTIONS
from ..ivtff import folio_sort_key
from ..reporting import Section, document, heatmap_html, write_csv
from ..util import table, write_text
from . import Plugin, PluginContext
from ._common import save_text, track


def run(ctx: PluginContext) -> dict:
    axis = ctx.setting("axis", "section")
    top = ctx.setting("topGlyphs", 30)
    normalise = ctx.setting("normalise", True)

    overall = ctx.corpus.glyph_counts()
    glyphs = [g for g, _ in overall.most_common(top)]

    groups = _groups(ctx, axis)
    matrix = []
    labels = []
    raw = {}
    for label, counts in track(ctx, groups, "groups"):
        total = sum(counts.values()) or 1
        row = [(counts.get(g, 0) / total if normalise else counts.get(g, 0)) for g in glyphs]
        matrix.append(row)
        labels.append(label)
        raw[label] = {g: counts.get(g, 0) for g in glyphs}

    display = [_display(g) for g in glyphs]

    text_rows = []
    for label, row in zip(labels, matrix):
        text_rows.append([label] + ["%.3f" % v if normalise else "%d" % v for v in row])
    blocks = [
        "Glyph frequency by %s" % axis,
        "=" * (21 + len(axis)),
        "",
        table(text_rows, [axis] + display),
        "",
        "Values are %s." % ("shares of that group's glyphs" if normalise else "raw counts"),
        "",
        "What to look for\n"
        "----------------\n"
        "Currier's A and B 'languages' show up here immediately: several glyphs are far more common\n"
        "in one than the other. If a glyph's frequency varies wildly between sections, a single\n"
        "mapping rule for it is doing different work in different places, and that is worth knowing\n"
        "before you trust an overall score.",
    ]
    save_text(ctx, "glyph_heatmap.txt", "\n".join(blocks) + "\n", "glyph frequency by %s" % axis)

    if ctx.setting("html", True):
        section = Section(
            "Glyph frequency by %s" % axis,
            "Darker means the glyph makes up a larger share of that group's text.",
            heatmap_html(matrix, labels, display, "%d glyphs, %d groups" % (len(glyphs), len(labels))),
        )
        page = document("Glyph heatmap", "%s  |  %s" % (ctx.corpus.title, axis), [section])
        path = write_text(ctx.output_path("glyph_heatmap.html"), page)
        ctx.record_output(path, "glyph frequency heatmap")

    if ctx.setting("writeCsv", True):
        path = write_csv(
            ctx.output_path("glyph_heatmap.csv"),
            [[label] + [round(v, 6) for v in row] for label, row in zip(labels, matrix)],
            [axis] + display,
        )
        ctx.record_output(path, "glyph frequency matrix as CSV")

    return {"axis": axis, "glyphs": display, "groups": labels, "matrix": matrix, "counts": raw}


def _groups(ctx: PluginContext, axis: str) -> list:
    if axis == "folio":
        grouped = {}
        for locus in ctx.corpus.loci:
            grouped.setdefault(locus.key, Counter()).update(locus.text)
        for counts in grouped.values():
            counts.pop(".", None)
            counts.pop(",", None)
        limit = ctx.setting("maxGroups", 80)
        keys = sorted(grouped, key=folio_sort_key)[:limit]
        return [("f%s" % k, grouped[k]) for k in keys]

    if axis == "scribe":
        grouped = {}
        for locus in ctx.corpus.loci:
            scribe = ctx.corpus.folios.get(locus.key).scribe or "?"
            grouped.setdefault("scribe " + scribe, Counter()).update(locus.text)
        for counts in grouped.values():
            counts.pop(".", None)
            counts.pop(",", None)
        return sorted(grouped.items())

    groups = []
    for name, spec in SECTIONS.items():
        if name in ("herbal", "currier_a", "currier_b") and ctx.setting("skipOverlapping", True):
            continue
        sub = ctx.corpus.select(replace(ctx.corpus.selection, sections=(name,)))
        if sub.is_empty:
            continue
        groups.append((spec.title, sub.glyph_counts()))
    return groups


def _display(glyph: str) -> str:
    from ..ivtff import high_ascii_label

    label = high_ascii_label(glyph)
    return label if len(label) <= 6 else label[:6]


PLUGIN = Plugin(
    name="glyph_heatmap",
    title="Glyph frequency heatmap",
    stage="report",
    category="output",
    summary="Shows how glyph frequencies differ between folios, sections or scribes.",
    help=(
        "The manuscript is not statistically uniform, and this is the quickest way to see it. Each\n"
        "row is a folio, a section or a scribe; each column is a glyph; the shade is how much of\n"
        "that group's text the glyph makes up.\n\n"
        "Currier's A and B 'languages' are visible at a glance, and so are the sections where one\n"
        "or two glyphs dominate. That matters for mapping design: a glyph whose frequency swings\n"
        "between sections is doing different work in different places, and a single rule for it is\n"
        "an averaging over things that may not belong together.\n\n"
        "Set 'axis' to 'section', 'folio' or 'scribe'."
    ),
    defaults={
        "axis": "section",
        "topGlyphs": 30,
        "maxGroups": 80,
        "normalise": True,
        "skipOverlapping": True,
        "html": True,
        "writeCsv": True,
    },
    settings_help={
        "axis": "'section', 'folio' or 'scribe'.",
        "topGlyphs": "How many of the commonest glyphs to include as columns.",
        "maxGroups": "Cap on rows when the axis is 'folio'.",
        "normalise": "Show shares rather than raw counts.",
        "skipOverlapping": "Leave out the sections that contain other sections (herbal, currier_a, currier_b).",
        "html": "Write glyph_heatmap.html.",
        "writeCsv": "Write glyph_heatmap.csv.",
    },
    run=run,
)
