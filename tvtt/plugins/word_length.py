"""Word length distribution, and how binomial it is."""

from __future__ import annotations

from ..analysis import word_length_profile
from ..langmodel import available_controls
from ..util import table
from . import Plugin, PluginContext
from ._common import bar, save_text, words


def run(ctx: PluginContext) -> dict:
    profile = word_length_profile(words(ctx))
    total = profile.total or 1

    peak = max(profile.counts.values()) if profile.counts else 1
    rows = [
        [length, count, "%.2f%%" % (100 * count / total), bar(count, peak, 34)]
        for length, count in sorted(profile.counts.items())
    ]

    comparisons = []
    for language in ctx.setting("compareWith", []):
        try:
            from ..langmodel import control_text
            from ..lexicon import tokenize

            other = word_length_profile(tokenize(control_text(language)))
            comparisons.append(
                [
                    language,
                    "%.2f" % other.mean,
                    "%.3f" % other.dispersion,
                    "%.3f" % other.short_share,
                    other.peak_length,
                    "%.3f" % other.binomial_fit_error,
                ]
            )
        except Exception as exc:
            ctx.log.warning("could not load control text %r: %s", language, exc)

    blocks = [
        "Word length distribution",
        "=" * 24,
        "",
        table(rows, ["characters", "words", "share", ""]),
        "",
        "mean %.3f, variance %.3f, dispersion %.3f, peak at %d characters"
        % (profile.mean, profile.variance, profile.dispersion, profile.peak_length),
        "share of 1-2 letter words %.1f%%, share of 9+ letter words %.1f%%"
        % (profile.short_share * 100, profile.long_share * 100),
        "best binomial fit n=%d p=%.3f, total variation distance %.3f"
        % (profile.binomial_n, profile.binomial_p, profile.binomial_fit_error),
        "",
        "Verdict: " + profile.verdict(),
        "",
    ]
    if comparisons:
        blocks.append("The same measures for real languages")
        blocks.append("-" * 36)
        blocks.append(table(comparisons, ["language", "mean", "dispersion", "short share", "peak", "binom error"]))
        blocks.append("")
    blocks.append(
        "What to look for\n"
        "----------------\n"
        "The manuscript's word lengths are unusually tight: a sharp peak at five glyphs,\n"
        "hardly any one or two letter words, and a fast-decaying tail. Dispersion (variance\n"
        "divided by mean) is about 0.76; European languages sit above 1.0 because their\n"
        "function words are short and their compounds are long.\n\n"
        "A substitution mapping barely changes any of this, so a large shift means your\n"
        "mapping is expanding or merging glyphs rather than substituting them."
    )
    save_text(ctx, "word_length.txt", "\n".join(blocks) + "\n", "word length distribution")

    payload = profile.to_dict()
    payload["verdict"] = profile.verdict()
    payload["comparisons"] = comparisons
    return payload


PLUGIN = Plugin(
    name="word_length",
    title="Word length distribution",
    stage="analyze",
    category="statistics",
    summary="Word lengths against the manuscript's unusually tight binomial-like curve.",
    help=(
        "Voynichese word lengths are one of its strangest features. They cluster tightly around\n"
        "five glyphs and are well described by a binomial curve, while every European language has\n"
        "a spike of very short function words and a long tail of long ones.\n\n"
        "This plugin reports the full distribution, the best-fitting binomial, and three shape\n"
        "measures that separate the manuscript from natural language more cleanly than the binomial\n"
        "fit alone: dispersion, the share of one and two letter words, and where the peak sits.\n\n"
        "Set 'compareWith' to a list of bundled control languages to print their numbers alongside.\n"
        "Available: " + ", ".join(available_controls()) + "."
    ),
    defaults={"compareWith": ["latin", "italian", "english"]},
    settings_help={"compareWith": "Control languages to show the same measures for."},
    enabled_by_default=True,
    run=run,
)
