"""Character transition matrices and n-gram counts."""

from __future__ import annotations

from ..analysis import ngram_counts, ngram_profile
from ..reporting import write_csv
from ..util import table
from . import Plugin, PluginContext
from ._common import save_json, save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    profile = ngram_profile(output_words, boundary=ctx.setting("boundaryCharacter", "_"))

    blocks = [
        "Character transitions",
        "=" * 21,
        "",
        "alphabet (%d symbols, '%s' is the word boundary): %s"
        % (len(profile.alphabet), ctx.setting("boundaryCharacter", "_"), " ".join(profile.alphabet)),
        "conditional entropy of the transition model: %.4f bits" % profile.conditional_entropy,
        "",
        "Most frequent transitions",
        "-" * 25,
        table(
            [[pair, count] for pair, count in profile.top_bigrams[: ctx.setting("topN", 40)]],
            ["pair", "count"],
        ),
        "",
    ]

    for order in ctx.setting("orders", [2, 3, 4]):
        counts = ngram_counts(output_words, order, boundary=ctx.setting("boundaryCharacter", "_"))
        blocks.append("Most frequent %d-grams" % order)
        blocks.append("-" * 22)
        blocks.append(table(counts.most_common(ctx.setting("topN", 40)), ["n-gram", "count"]))
        blocks.append("")

    blocks.append(
        "Reading the matrix\n"
        "------------------\n"
        "Row i, column j counts how often character j follows character i. The rows involving the\n"
        "word-boundary symbol are the interesting ones for Voynichese: they say which characters\n"
        "may start a word and which may end one, and those constraints are far tighter than in any\n"
        "alphabet. Enable the 'plots' or 'html_report' plugin to see it as a heatmap."
    )
    save_text(ctx, "ngrams.txt", "\n".join(blocks) + "\n", "character transitions and n-gram counts")

    if ctx.setting("writeMatrixCsv", True):
        header = ["from"] + profile.alphabet
        rows = [[profile.alphabet[i]] + row for i, row in enumerate(profile.matrix)]
        path = write_csv(ctx.output_path("transition_matrix.csv"), rows, header)
        ctx.record_output(path, "character transition counts as a matrix")

    payload = profile.to_dict()
    payload["matrix"] = profile.matrix
    payload["row_totals"] = profile.row_totals
    if ctx.setting("writeJson"):
        save_json(ctx, "ngrams.json", payload, "n-gram statistics")
    return payload


PLUGIN = Plugin(
    name="ngrams",
    title="Character n-grams and transition matrix",
    stage="analyze",
    category="statistics",
    summary="Builds the character transition matrix and lists the commonest n-grams.",
    help=(
        "Which characters follow which, counted as a matrix, with the word boundary treated as a\n"
        "real symbol so that word-initial and word-final constraints show up.\n\n"
        "This is the raw material behind conditional entropy, and it is worth looking at directly:\n"
        "Voynichese has extremely sparse transitions. Most character pairs never occur at all, and\n"
        "a handful of pairs carry most of the text. Natural languages have sparse matrices too, but\n"
        "nothing like this sparse.\n\n"
        "The matrix is written as CSV and, if the 'plots' or 'html_report' plugin is on, drawn as a\n"
        "heatmap."
    ),
    defaults={"orders": [2, 3, 4], "topN": 40, "boundaryCharacter": "_", "writeMatrixCsv": True, "writeJson": False},
    settings_help={
        "orders": "Which n-gram sizes to tabulate.",
        "topN": "How many rows per table.",
        "boundaryCharacter": "Symbol standing for the space between words.",
        "writeMatrixCsv": "Write transition_matrix.csv.",
        "writeJson": "Also write the whole profile as JSON.",
    },
    run=run,
)
