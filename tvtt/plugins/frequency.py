"""Character and word frequency tables."""

from __future__ import annotations

from collections import Counter

from ..reporting import glyph_label, write_csv
from ..util import table
from . import Plugin, PluginContext
from ._common import counts_table, save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    letters = Counter("".join(output_words))
    word_counts = Counter(output_words)
    source_glyphs = ctx.corpus.glyph_counts()

    limit = ctx.setting("topN", 40)
    blocks = []

    blocks.append("Source glyph frequency")
    blocks.append("-" * 22)
    glyph_rows = [
        [glyph_label(g), c, "%.3f%%" % (100 * c / (sum(source_glyphs.values()) or 1)), ""]
        for g, c in source_glyphs.most_common(limit)
    ]
    blocks.append(table(glyph_rows, ["glyph", "count", "share", ""]))
    blocks.append("")

    blocks.append("Output character frequency")
    blocks.append("-" * 26)
    blocks.append(table(counts_table(letters, limit), ["character", "count", "share", ""]))
    blocks.append("")

    blocks.append("Most common output words")
    blocks.append("-" * 24)
    blocks.append(table(counts_table(word_counts, limit), ["word", "count", "share", ""]))

    save_text(ctx, "frequency.txt", "\n".join(blocks) + "\n", "character and word frequency tables")

    if ctx.setting("writeCsv"):
        total_words = sum(word_counts.values()) or 1
        rows = [[w, c, round(c / total_words, 6)] for w, c in word_counts.most_common()]
        path = write_csv(ctx.output_path("word_frequency.csv"), rows, ["word", "count", "share"])
        ctx.record_output(path, "every output word type with its frequency")

    return {
        "output_characters": dict(letters.most_common(limit)),
        "output_words": dict(word_counts.most_common(limit)),
        "source_glyphs": {glyph_label(g): c for g, c in source_glyphs.most_common(limit)},
        "distinct_characters": len(letters),
        "distinct_words": len(word_counts),
    }


PLUGIN = Plugin(
    name="frequency",
    title="Frequency tables",
    stage="analyze",
    category="statistics",
    summary="Counts source glyphs, output characters and output words.",
    help=(
        "The starting point for any mapping: what is actually in the text.\n\n"
        "Three tables are produced. The source glyph counts tell you which shapes the manuscript\n"
        "uses most, which is what a frequency-matched first guess is built from. The output\n"
        "character counts show what your mapping turned those into - compare them with real letter\n"
        "frequencies for your target language. The word counts show whether your commonest output\n"
        "words look like a language's function words or like nothing at all."
    ),
    defaults={"topN": 40, "writeCsv": True},
    settings_help={
        "topN": "How many rows to show in each table.",
        "writeCsv": "Also write word_frequency.csv with the complete list.",
    },
    enabled_by_default=True,
    run=run,
)
