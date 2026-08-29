"""Repetition, repeat distance and autocorrelation."""

from __future__ import annotations

from ..analysis import repeat_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import bar, save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    max_lag = ctx.setting("maxLag", 12)
    profile = repeat_profile(output_words, max_lag)

    peak = max((abs(v) for v in profile.autocorrelation), default=1) or 1
    lag_rows = [
        [lag, "%+.5f" % value, bar(abs(value), peak, 28)] for lag, value in enumerate(profile.autocorrelation, 1)
    ]

    blocks = [
        "Repetition and clustering",
        "=" * 25,
        "",
        "immediate repeats (a word followed by itself): %d, %.3f%% of positions"
        % (profile.immediate, profile.immediate_rate * 100),
        "the same rate by chance, given this vocabulary: %.4f%%" % (profile.chance_level * 100),
        "clustering ratio (observed / chance at lag 1): %.2f" % profile.clustering_ratio,
        "mean distance between repeats of the same word: %.1f words" % profile.mean_repeat_distance,
        "",
        "Verdict: " + profile.verdict(),
        "",
        "Autocorrelation by lag (excess probability that the word k positions later is the same)",
        "-" * 86,
        table(lag_rows, ["lag", "excess", ""]),
        "",
        "Words repeated back to back",
        "-" * 27,
        table(profile.top_repeated[:20], ["word", "times"]),
        "",
        "A word reappearing within the next N words",
        "-" * 42,
        table(sorted(profile.near_repeats.items()), ["window", "occurrences"]),
        "",
        "Why this matters\n"
        "----------------\n"
        "Voynichese repeats itself far more than any natural language. Sequences such as\n"
        "'qokeedy qokeedy qokedy' are common, and similar words cluster together over short\n"
        "spans. In Latin or Italian, an immediate repetition is rare and usually deliberate.\n\n"
        "A substitution mapping preserves repetition exactly, so a big change here means your\n"
        "mapping is merging different words into the same output word - which inflates every\n"
        "dictionary score you will get later. The clustering ratio is the number to watch: it\n"
        "compares the observed repeat rate with what this vocabulary would produce by chance.",
    ]
    save_text(ctx, "repeats.txt", "\n".join(blocks) + "\n", "repetition and autocorrelation")

    payload = profile.to_dict()
    payload["verdict"] = profile.verdict()
    return payload


PLUGIN = Plugin(
    name="repeats",
    title="Repetition and autocorrelation",
    stage="analyze",
    category="statistics",
    summary="Measures how much the text repeats itself, and at what distance.",
    help=(
        "One of the manuscript's most distinctive habits is repeating a word immediately, or\n"
        "repeating something very close to it a few words later. This plugin measures three\n"
        "aspects of that:\n\n"
        "  immediate repeats  how often a word is followed by itself\n"
        "  autocorrelation    the excess chance that the word k positions later is the same word\n"
        "  repeat distance    how far apart occurrences of the same word typically fall\n\n"
        "Each is compared with what the same vocabulary would produce by chance, because a text\n"
        "with a small vocabulary repeats a lot without any of it meaning anything.\n\n"
        "A substitution mapping cannot change the repetition structure; if yours does, it is\n"
        "collapsing distinct words together."
    ),
    defaults={"maxLag": 12},
    settings_help={"maxLag": "How many word positions ahead to measure autocorrelation for."},
    run=run,
)
