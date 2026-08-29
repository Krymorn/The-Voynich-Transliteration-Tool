"""Type/token ratio, MATTR, hapax legomena and Heaps' law."""

from __future__ import annotations

from ..analysis import vocabulary_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    window = ctx.setting("mattrWindow", 500)
    profile = vocabulary_profile(output_words, window)

    rows = [
        ["tokens", profile.tokens, "total words"],
        ["types", profile.types, "distinct words"],
        ["type/token ratio", "%.4f" % profile.ttr, "types divided by tokens; falls as a text grows"],
        [
            "MATTR (window %d)" % window,
            "%.4f" % profile.mattr,
            "TTR averaged over a sliding window; comparable between texts",
        ],
        ["hapax legomena", profile.hapax, "words that occur exactly once"],
        ["hapax share of types", "%.4f" % profile.hapax_ratio, ""],
        ["dis legomena", profile.dis_legomena, "words that occur exactly twice"],
        ["Heaps k", "%.3f" % profile.heaps_k, "vocabulary = k * tokens ^ beta"],
        ["Heaps beta", "%.4f" % profile.heaps_beta, "how fast new words keep appearing"],
    ]

    comparisons = []
    for language in ctx.setting("compareWith", []):
        try:
            from ..langmodel import control_text
            from ..lexicon import tokenize

            sample = tokenize(control_text(language))[: max(2000, profile.tokens)]
            other = vocabulary_profile(sample, window)
            comparisons.append(
                [
                    language,
                    other.tokens,
                    other.types,
                    "%.4f" % other.ttr,
                    "%.4f" % other.mattr,
                    "%.3f" % other.hapax_ratio,
                    "%.3f" % other.heaps_beta,
                ]
            )
        except Exception as exc:
            ctx.log.warning("could not load control text %r: %s", language, exc)

    blocks = [
        "Vocabulary",
        "=" * 10,
        "",
        table(rows, ["measure", "value", "meaning"]),
        "",
        "Verdict: " + profile.verdict(),
        "",
    ]
    if comparisons:
        blocks.append("The same measures for real languages, sampled to a similar length")
        blocks.append("-" * 64)
        blocks.append(table(comparisons, ["language", "tokens", "types", "ttr", "mattr", "hapax", "heaps beta"]))
        blocks.append("")
    blocks.append(
        "Why MATTR instead of TTR\n"
        "------------------------\n"
        "Plain type/token ratio always falls as a text gets longer, so it cannot be compared\n"
        "between texts of different sizes - which makes it useless for comparing a section of\n"
        "the manuscript with a control text. MATTR measures the same fixed number of tokens\n"
        "everywhere, so the numbers mean the same thing.\n\n"
        "Heaps' beta says how fast new words keep turning up. Natural languages sit around 0.55\n"
        "to 0.8. A beta near 1.0 means almost every word is new, which is what shuffled or\n"
        "randomly generated text looks like."
    )
    save_text(ctx, "vocabulary.txt", "\n".join(blocks) + "\n", "vocabulary growth and richness")

    payload = profile.to_dict()
    payload["verdict"] = profile.verdict()
    payload["comparisons"] = comparisons
    payload["heaps_points"] = profile.heaps_points
    return payload


PLUGIN = Plugin(
    name="vocabulary",
    title="Vocabulary growth (TTR, MATTR, hapax, Heaps)",
    stage="analyze",
    category="statistics",
    summary="Type/token ratio, moving-average TTR, hapax legomena and Heaps' law.",
    help=(
        "How rich the vocabulary is, and how fast it grows.\n\n"
        "  type/token ratio  distinct words divided by total words\n"
        "  MATTR             the same thing measured over a sliding window, so texts of\n"
        "                    different lengths can be compared honestly\n"
        "  hapax legomena    words that appear exactly once - a large share means a big,\n"
        "                    loosely used vocabulary\n"
        "  Heaps' law        vocabulary = k * tokens^beta; beta says how fast new words appear\n\n"
        "These are the measures that expose text with no message in it. A shuffled or randomly\n"
        "generated text has a very high hapax share and a Heaps beta close to 1, because nearly\n"
        "every word it produces is new. The manuscript does not: it repeats itself heavily."
    ),
    defaults={"mattrWindow": 500, "compareWith": ["latin", "italian", "english"]},
    settings_help={
        "mattrWindow": "How many tokens the moving-average TTR window covers.",
        "compareWith": "Control languages to show the same measures for.",
    },
    enabled_by_default=True,
    run=run,
)
