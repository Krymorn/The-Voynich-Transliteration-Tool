"""The glyph cheat sheet for the active mapping."""

from __future__ import annotations

from ..fonts import choose_font, glyph_legend
from ..reporting import Section, document, esc, html_table
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    engine = ctx.result.engine
    counts = ctx.corpus.glyph_counts()
    rows = glyph_legend(engine, counts)
    total = sum(counts.values()) or 1

    text_rows = []
    for row in rows:
        positions = ", ".join("%s=%s" % (name, value) for name, value in row["rules"].items() if name != "plain")
        text_rows.append(
            [
                row["display"],
                row["count"],
                "%.2f%%" % (100 * row["count"] / total),
                row["plain"] or ("(unmapped)" if not row["mapped"] else "(nothing)"),
                positions,
            ]
        )

    unmapped = [r["display"] for r in rows if not r["mapped"] and r["count"]]
    blocks = [
        "Glyph legend for mapping: %s" % (engine.mapping.meta.get("name", "unnamed")),
        "=" * 60,
        "",
        table(text_rows, ["glyph", "count", "share", "becomes", "positional rules"]),
        "",
        "%d glyphs in this selection, %d with a rule, %d without."
        % (len(rows), sum(1 for r in rows if r["mapped"]), len(unmapped)),
    ]
    if unmapped:
        blocks.append("Glyphs with no rule: " + " ".join(unmapped))
    blocks.append("")
    blocks.append(
        "Glyphs written as @nnn; are the IVTFF codes for shapes outside the basic alphabet.\n"
        "Inside TVTT each is held as a single character so it behaves like any other glyph,\n"
        "and you can write a rule for it using the @nnn; form."
    )
    save_text(ctx, "legend.txt", "\n".join(blocks) + "\n", "glyph cheat sheet for the active mapping")

    if ctx.setting("html", True):
        font = choose_font(ctx.setting("font", ""), ctx.corpus.alphabet)
        html_rows = [
            [
                r["rendered"],
                r["display"],
                r["count"],
                "%.2f%%" % (100 * r["count"] / total),
                r["plain"] or "-",
                ", ".join("%s=%s" % (k, v) for k, v in r["rules"].items() if k != "plain") or "-",
            ]
            for r in rows
        ]
        section = Section(
            "Glyph legend",
            "Every glyph in this selection, how often it occurs, and what your mapping turns it into.",
            "<div class='voy' style='font-size:26px;margin:6px 0 14px'>%s</div>%s"
            % (
                esc("".join(r["rendered"] for r in rows[:60])),
                html_table(
                    html_rows,
                    ["shape", "written as", "count", "share", "becomes", "positional rules"],
                    numeric=["count", "share"],
                    max_rows=400,
                    voynich_columns=["shape"],
                ),
            ),
        )
        page = document(
            "Glyph legend",
            "mapping: %s, transcription: %s" % (engine.mapping.meta.get("name", "unnamed"), ctx.corpus.title),
            [section],
            extra_css=font.css() + (".voy{font-family:%s}" % font.font_family()),
        )
        from ..util import write_text

        path = write_text(ctx.output_path("legend.html"), page)
        ctx.record_output(path, "glyph cheat sheet as a web page")

    return {
        "glyphs": len(rows),
        "mapped": sum(1 for r in rows if r["mapped"]),
        "unmapped": unmapped,
        "legend": [
            {"glyph": r["display"], "count": r["count"], "becomes": r["plain"], "rules": r["rules"]} for r in rows
        ],
    }


PLUGIN = Plugin(
    name="legend",
    title="Glyph legend",
    stage="report",
    category="output",
    summary="Generates a cheat sheet of every glyph and what your mapping does with it.",
    help=(
        "One row per glyph: how it is written in the transcription, how often it occurs in the part\n"
        "of the manuscript you selected, what your mapping turns it into, and any positional or\n"
        "occurrence rules attached to it.\n\n"
        "This is the single most useful thing to have open while editing a mapping by hand. It also\n"
        "answers the question people ask most often when they start: which glyphs are common enough\n"
        "to be worth thinking about, and which have no rule at all yet."
    ),
    defaults={"html": True, "font": ""},
    settings_help={
        "html": "Also write legend.html with the glyphs rendered in a Voynich font.",
        "font": "Font file to use; empty picks one to suit the transcription alphabet.",
    },
    enabled_by_default=True,
    run=run,
)
