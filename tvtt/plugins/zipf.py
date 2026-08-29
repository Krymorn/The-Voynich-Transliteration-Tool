"""Zipf's law: word rank against frequency, with reference slopes."""

from __future__ import annotations

from ..analysis import ZIPF_REFERENCES, vocabulary_profile, zipf_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    profile = zipf_profile(output_words)

    rows = [[rank, word, count, "%.3f%%" % share] for rank, (word, count, share) in enumerate(profile.top[:30], 1)]

    blocks = [
        "Zipf's law",
        "=" * 10,
        "",
        "fitted exponent %.4f (natural languages sit between about 0.9 and 1.2)" % abs(profile.slope),
        "goodness of fit  r squared = %.4f" % profile.r_squared,
        "",
        "Verdict: " + profile.verdict(),
        "",
        "Reference exponents",
        "-" * 19,
        table([[name, "%.2f" % slope] for name, slope in ZIPF_REFERENCES], ["language", "exponent"]),
        "",
        "Most frequent words",
        "-" * 19,
        table(rows, ["rank", "word", "count", "share"]),
        "",
        "What this does and does not show\n"
        "--------------------------------\n"
        "Voynichese follows Zipf's law closely, which is one of the reasons it is hard to dismiss\n"
        "as meaningless scribbling. But a good Zipf fit is a weak test: shuffled text, randomly\n"
        "generated text and the synthetic self-citation model all pass it. Use it to rule things\n"
        "out, not to rule anything in - and check it against the baselines plugins.",
    ]
    save_text(ctx, "zipf.txt", "\n".join(blocks) + "\n", "Zipf's law fit and the most frequent words")

    payload = profile.to_dict()
    payload["verdict"] = profile.verdict()
    if ctx.setting("includeHeaps", True):
        vocabulary = vocabulary_profile(output_words)
        payload["heaps_k"] = round(vocabulary.heaps_k, 4)
        payload["heaps_beta"] = round(vocabulary.heaps_beta, 4)
        payload["heaps_points"] = vocabulary.heaps_points
    payload["ranks"] = profile.ranks[:5000]
    payload["frequencies"] = profile.frequencies[:5000]
    return payload


PLUGIN = Plugin(
    name="zipf",
    title="Zipf's law",
    stage="analyze",
    category="statistics",
    summary="Fits rank against frequency and compares the exponent with real languages.",
    help=(
        "In every natural language, the second commonest word appears about half as often as the\n"
        "commonest, the third about a third as often, and so on. Plotted on log-log axes that is a\n"
        "straight line, and its slope is the Zipf exponent - close to 1.0 for most languages.\n\n"
        "The manuscript fits this well. So, unfortunately, does a great deal of meaningless text,\n"
        "which is why this plugin prints a warning alongside the number. Treat a good Zipf fit as a\n"
        "necessary condition, never a sufficient one.\n\n"
        "Enable the 'plots' plugin to get a picture, with reference slopes and Heaps' law drawn\n"
        "alongside."
    ),
    defaults={"includeHeaps": True},
    settings_help={"includeHeaps": "Also compute Heaps' law points so the plots plugin can draw both."},
    enabled_by_default=True,
    run=run,
)
