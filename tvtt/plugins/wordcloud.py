"""Word frequency table and a word cloud you can open in a browser."""

from __future__ import annotations

import math
from collections import Counter

from ..reporting import Section, document, esc, write_csv
from ..util import table, write_text
from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    counts = ctx.result.word_counts()
    total = sum(counts.values()) or 1
    top = ctx.setting("topN", 150)
    entries = counts.most_common(top)

    rows = [[rank, word, count, "%.3f%%" % (100 * count / total)] for rank, (word, count) in enumerate(entries, 1)]
    save_text(
        ctx,
        "word_frequency.txt",
        "Word frequency\n==============\n\n"
        + table(rows, ["rank", "word", "count", "share"])
        + "\n\n%d word types, %d tokens.\n" % (len(counts), total),
        "word frequency table",
    )

    if ctx.setting("writeCsv", True):
        path = write_csv(
            ctx.output_path("word_frequency_full.csv"),
            [[w, c, round(c / total, 8)] for w, c in counts.most_common()],
            ["word", "count", "share"],
        )
        ctx.record_output(path, "every word type with its frequency")

    if ctx.setting("html", True):
        path = write_text(ctx.output_path("wordcloud.html"), _cloud(ctx, entries, counts, total))
        ctx.record_output(path, "word cloud")

    return {
        "types": len(counts),
        "tokens": total,
        "top": [[w, c] for w, c in entries[:60]],
    }


def _cloud(ctx: PluginContext, entries: list, counts: Counter, total: int) -> str:
    """A word cloud built from sized spans; no drawing library involved."""
    if not entries:
        body = "<p class='why'>No words to show.</p>"
    else:
        biggest = entries[0][1]
        smallest = entries[-1][1]
        span = math.log(biggest) - math.log(smallest) or 1.0
        pieces = []
        for word, count in entries:
            scale = (math.log(count) - math.log(smallest)) / span
            size = 12 + scale * 46
            weight = 400 + int(scale * 3) * 100
            opacity = 0.55 + 0.45 * scale
            pieces.append(
                "<span style='font-size:%.1fpx;font-weight:%d;opacity:%.2f;margin:0 10px;"
                "display:inline-block;line-height:1.35' title='%s'>%s</span>"
                % (size, weight, opacity, esc("%s: %d (%.3f%%)" % (word, count, 100 * count / total)), esc(word))
            )
        body = "<div style='text-align:center;padding:20px 6px'>%s</div>" % "".join(pieces)

    rows = "".join(
        "<tr><td class='num'>%d</td><td>%s</td><td class='num'>%d</td><td class='num'>%.3f%%</td></tr>"
        % (rank, esc(word), count, 100 * count / total)
        for rank, (word, count) in enumerate(entries[:80], 1)
    )
    table_html = (
        "<div class='scroll'><table><thead><tr><th class='num'>rank</th><th>word</th>"
        "<th class='num'>count</th><th class='num'>share</th></tr></thead><tbody>%s</tbody></table></div>" % rows
    )

    return document(
        "Word cloud",
        "%s  |  %d word types, %d tokens" % (ctx.corpus.title, len(counts), total),
        [
            Section("Word cloud", "Size follows the logarithm of frequency. Hover for exact counts.", body),
            Section("Frequency table", "The same words as numbers.", table_html),
        ],
    )


PLUGIN = Plugin(
    name="wordcloud",
    title="Word cloud and frequency table",
    stage="report",
    category="output",
    summary="Writes a word frequency table and a browsable word cloud.",
    help=(
        "A quick visual sense of what your mapping produces most often, plus the same information\n"
        "as an exact table and a complete CSV export.\n\n"
        "The cloud is plain HTML - words sized by the logarithm of their frequency - so it needs no\n"
        "drawing library and opens anywhere. Hover over a word for its exact count.\n\n"
        "Look at the largest words first. In a real language the commonest words are function words:\n"
        "et, in, non, che, the. If the biggest words in your cloud are long and unfamiliar, the\n"
        "mapping is not producing a language, whatever the dictionary hit rate says."
    ),
    defaults={"topN": 150, "html": True, "writeCsv": True},
    settings_help={
        "topN": "How many words to include in the cloud and the printed table.",
        "html": "Write wordcloud.html.",
        "writeCsv": "Write the complete frequency list as CSV.",
    },
    run=run,
)
