"""A plain side-by-side view of source and transliteration."""

from __future__ import annotations

from ..fonts import choose_font, display_text
from ..ivtff import LOCUS_TYPE_NAMES
from ..reporting import Section, document, esc
from ..util import write_text
from . import Plugin, PluginContext


def run(ctx: PluginContext) -> dict:
    corpus = ctx.corpus
    result = ctx.result
    limit = ctx.setting("maxLines", 8000)
    font = choose_font(ctx.setting("font", ""), corpus.alphabet)

    rows = []
    for locus, mapped in list(zip(corpus.loci, result.lines))[:limit]:
        rows.append(
            "<div class='line'><div class='loc'>%s<br><span class='pill'>%s</span></div>"
            "<div class='src voy'>%s</div><div class='out'>%s</div></div>"
            % (
                esc(locus.locus_id),
                esc(LOCUS_TYPE_NAMES.get(locus.locus_type, locus.locus_type)),
                esc(display_text(locus.text)),
                esc(mapped),
            )
        )

    section = Section(
        "Source and transliteration",
        "%d lines from %s. Left: the transcription as TVTT read it, after resolving ambiguity. "
        "Right: your mapping applied." % (min(limit, len(result.lines)), corpus.title),
        "<div class='controls'><input type='search' id='line-search' placeholder='search'></div>"
        "<div id='lines'>%s</div>" % "".join(rows),
    )
    page = document(
        "Comparison",
        "%s  |  %s" % (corpus.title, corpus.selection.describe()),
        [section],
        extra_css=font.css() + (".voy{font-family:%s}" % font.font_family()),
        extra_js="tvttFilter('line-search','lines','data-hay');",
    )
    path = write_text(ctx.output_path(ctx.setting("filename", "comparison.html")), page)
    ctx.record_output(path, "side-by-side source and transliteration")

    if ctx.setting("alsoText", False):
        text = "\n".join(
            "%-18s %s\n%-18s %s\n" % (locus.locus_id, locus.text, "", mapped)
            for locus, mapped in list(zip(corpus.loci, result.lines))[:limit]
        )
        write_text(ctx.output_path("comparison.txt"), text)
        ctx.record_output(ctx.output_path("comparison.txt"), "side-by-side comparison as plain text")

    return {"path": str(path), "lines": min(limit, len(result.lines))}


PLUGIN = Plugin(
    name="comparison",
    title="Side-by-side comparison",
    stage="report",
    category="output",
    summary="A simple two-column view of the source text and your transliteration.",
    help=(
        "The straightforward view: every line of the transcription next to what your mapping made\n"
        "of it, with the locus identifier so you can find it in the original file.\n\n"
        "The source column is rendered in a Voynich font when one is available, which makes it much\n"
        "easier to see what the glyph groups actually are. If you would rather see the plain\n"
        "transcription letters, put a font name that does not exist in the 'font' setting.\n\n"
        "For search, filtering and page images, use 'html_report' instead - this plugin is the\n"
        "small, fast version for when you just want to read the text."
    ),
    defaults={"filename": "comparison.html", "maxLines": 8000, "font": "", "alsoText": False},
    settings_help={
        "filename": "Name of the comparison file.",
        "maxLines": "How many lines to include.",
        "font": "Font for the source column; empty picks one to suit the alphabet.",
        "alsoText": "Also write a plain-text version.",
    },
    run=run,
)
