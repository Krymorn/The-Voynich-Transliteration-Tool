"""Score N random mappings and show where yours falls."""

from __future__ import annotations

from collections import Counter

from ..baselines import ControlDistribution
from ..langmodel import Fitness, FitnessOptions
from ..mapping import LATIN_LOWER
from ..solver import Problem
from ..util import table
from . import Plugin, PluginContext
from ._common import rng, save_text, track

METRICS = ("quadgram", "dictionary", "blend")


def run(ctx: PluginContext) -> dict:
    metric = ctx.setting("metric", "quadgram")
    language = ctx.setting("language") or ctx.config.get("reference.language", "latin")
    runs = ctx.setting("runs", 200)
    alphabet = ctx.setting("alphabet", LATIN_LOWER)

    vocabulary = Counter(ctx.corpus.words())
    fitness = Fitness(FitnessOptions(function=metric, language=language), vocabulary)
    problem = Problem(vocabulary, ctx.result.engine, fitness, alphabet=alphabet)

    observed = fitness.score(ctx.result.engine.map_words(problem.types))

    generator = rng(ctx)
    scores = []
    for _ in track(ctx, range(runs), "random mappings"):
        letters = [generator.choice(alphabet) for _ in problem.glyphs]
        scores.append(problem.score(letters))

    distribution = ControlDistribution(metric="%s (%s)" % (metric, language), observed=observed, scores=scores)

    blocks = [
        "Random-mapping control run",
        "=" * 26,
        "",
        "fitness: %s over %s" % (metric, language),
        "%d random mappings scored against the same text with the same measure." % runs,
        "",
        table(
            [
                ["your mapping", "%.5f" % distribution.observed],
                ["best random mapping", "%.5f" % distribution.best_random],
                ["mean of random mappings", "%.5f" % distribution.mean],
                ["standard deviation", "%.5f" % distribution.stdev],
                ["z-score", "%+.2f" % distribution.z_score],
                ["percentile", "%.1f" % distribution.percentile],
            ],
            ["measure", "value"],
        ),
        "",
        "Verdict: " + distribution.verdict(),
        "",
        "Distribution of random scores",
        "-" * 29,
        distribution.histogram(),
        "",
        "How to read this\n"
        "----------------\n"
        "Any mapping applied to the manuscript produces some Latin-looking output, because the\n"
        "manuscript has language-like statistics and Latin has a lot of short words. The question\n"
        "is never 'does my mapping score well' but 'does it score better than an arbitrary one'.\n\n"
        "If your score sits inside the cloud above, the number you were pleased with is a\n"
        "property of the text and the dictionary, not of your idea. If it sits several standard\n"
        "deviations clear of the best random mapping, you have something worth investigating -\n"
        "and the next question is whether it survives the 'holdout' test.",
    ]
    save_text(ctx, "random_controls.txt", "\n".join(blocks) + "\n", "your score against random mappings")

    payload = distribution.to_dict()
    payload["verdict"] = distribution.verdict()
    payload["runs"] = runs
    payload["language"] = language
    return payload


PLUGIN = Plugin(
    name="random_controls",
    title="Random-mapping control runs",
    stage="baseline",
    category="baselines",
    summary="Scores hundreds of random mappings so your score has something to beat.",
    help=(
        "The most important plugin in the tool.\n\n"
        "It generates random glyph-to-letter mappings, scores each one exactly as it scores yours,\n"
        "and reports where yours falls in the resulting distribution - as a z-score, a percentile,\n"
        "and a histogram with your result marked.\n\n"
        "Almost every published Voynich 'solution' would fail this test, because almost none of\n"
        "them ran it. A mapping that produces recognisable words is unremarkable if a random\n"
        "mapping produces just as many; the manuscript's word lengths and letter frequencies make\n"
        "accidental matches easy. Beating the best of two hundred random mappings is the minimum\n"
        "bar for a claim to be interesting at all.\n\n"
        "Choose the measure with 'metric': quadgram log-likelihood, dictionary coverage weighted by\n"
        "word rarity, or a blend of both."
    ),
    defaults={"metric": "quadgram", "language": "", "runs": 200, "alphabet": LATIN_LOWER},
    settings_help={
        "metric": "Which fitness to compare on: quadgram, dictionary or blend.",
        "language": "Target language; empty uses reference.language from config.json.",
        "runs": "How many random mappings to score. More is slower and more reliable.",
        "alphabet": "The letters random mappings may use.",
    },
    heavy=True,
    run=run,
)
