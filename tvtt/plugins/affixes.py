"""Prefixes and suffixes ranked by statistical surprise."""

from __future__ import annotations

from ..analysis import affix_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    sizes = tuple(ctx.setting("sizes", [1, 2, 3, 4]))
    profile = affix_profile(output_words, sizes, ctx.setting("minCount", 10))
    limit = ctx.setting("topN", 25)

    def render(rows, heading):
        body = [
            [r["affix"], r["count"], "%.2f%%" % (r["share"] * 100), "%.2f" % r["lift"], "%.0f" % r["surprise_bits"]]
            for r in rows[:limit]
        ]
        return [heading, "-" * len(heading), table(body, ["affix", "count", "share", "lift", "surprise (bits)"]), ""]

    blocks = ["Affixes ranked by surprise", "=" * 26, ""]
    blocks += render(profile.prefixes, "Prefixes")
    blocks += render(profile.suffixes, "Suffixes")
    blocks += [
        "Most frequent internal sequences",
        "-" * 32,
        table([[r["affix"], r["count"]] for r in profile.infixes[:limit]], ["sequence", "count"]),
        "",
    ]
    blocks.append(
        "Why surprise instead of raw counts\n"
        "----------------------------------\n"
        "Counting affixes naively just rediscovers the commonest letters: the top suffix will\n"
        "always be whatever single character is most frequent. Each candidate here is compared\n"
        "with how often its letters would land together by chance, given how common those\n"
        "letters are on their own.\n\n"
        "  lift            observed count divided by chance expectation\n"
        "  surprise        count multiplied by log2(lift), in bits - a real amount of evidence\n\n"
        "On EVA this correctly puts -aiin, -edy and -dy at the top, which is where a Voynich\n"
        "researcher would expect them. If your mapping is meaningful, the top suffixes should\n"
        "start looking like the inflections of your target language instead."
    )
    save_text(ctx, "affixes.txt", "\n".join(blocks) + "\n", "prefixes and suffixes with significance")

    return {
        "prefixes": profile.prefixes[:limit],
        "suffixes": profile.suffixes[:limit],
        "infixes": profile.infixes[:limit],
        "sizes": list(sizes),
    }


PLUGIN = Plugin(
    name="affixes",
    title="Prefix and suffix extraction",
    stage="analyze",
    category="statistics",
    summary="Finds prefixes and suffixes and ranks them by surprise, not raw count.",
    help=(
        "Voynichese has strikingly regular word endings - -aiin, -dy, -edy, -ol - and equally\n"
        "regular beginnings. Finding them is easy; ranking them honestly is not, because a naive\n"
        "count is dominated by whichever letters happen to be common.\n\n"
        "Every candidate affix is scored against what its own letters would produce by chance. The\n"
        "'lift' column is how many times more often it occurs than expected, and the 'surprise'\n"
        "column converts that into bits of evidence, weighted by how often the affix actually\n"
        "appears - so a strong pattern seen twenty times outranks a stronger one seen twice.\n\n"
        "If your mapping is a real substitution of a real language, the top suffixes should become\n"
        "that language's inflections."
    ),
    defaults={"sizes": [1, 2, 3, 4], "minCount": 10, "topN": 25},
    settings_help={
        "sizes": "Affix lengths to consider.",
        "minCount": "Ignore affixes seen fewer times than this.",
        "topN": "How many rows to show per table.",
    },
    run=run,
)
