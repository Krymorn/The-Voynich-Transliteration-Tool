"""How many dictionary hits would a random mapping have produced?"""

from __future__ import annotations

from collections import Counter

from ..baselines import ControlDistribution
from ..lexicon import load_dictionary
from ..mapping import LATIN_LOWER
from ..matcher import Matcher, MatchOptions
from ..util import table
from . import Plugin, PluginContext
from ._common import rng, save_text, track


def run(ctx: PluginContext) -> dict:
    observed_report = ctx.results.get("corpus_match")
    language = ctx.setting("language") or ctx.config.get("reference.language", "latin")
    runs = ctx.setting("runs", 60)
    alphabet = ctx.setting("alphabet", LATIN_LOWER)

    dictionary = load_dictionary(language, ctx.config.get("reference.folder", "reference_texts"))
    options = MatchOptions(
        language=language,
        max_edits=ctx.setting("maxEdits", 1),
        allow_stemming=ctx.setting("stemming", True),
        allow_merge=False,
        allow_split=False,
        allow_fuzzy=ctx.setting("maxEdits", 1) > 0,
    )

    engine = ctx.result.engine
    glyphs = list(engine.keys)
    source_types = Counter(ctx.corpus.words())
    types = list(source_types)
    counts = [source_types[t] for t in types]
    total = sum(counts) or 1
    plans = [engine.segment(word) for word in types]

    matcher = Matcher(dictionary, options)
    observed = _coverage(matcher, [engine.map_word(w) for w in types], counts, total)

    generator = rng(ctx)
    scores = []
    for _ in track(ctx, range(runs), "random mappings"):
        table_letters = {i: generator.choice(alphabet) for i in range(len(glyphs))}
        rendered = ["".join(table_letters[p // 20] for p in plan) for plan in plans]
        control = Matcher(dictionary, options)
        scores.append(_coverage(control, rendered, counts, total))

    distribution = ControlDistribution(metric="dictionary coverage (%s)" % language, observed=observed, scores=scores)

    blocks = [
        "Significance of the dictionary hit rate",
        "=" * 39,
        "",
        "dictionary: %s (%d word types)" % (dictionary.name, len(dictionary)),
        "matching:   exact%s%s"
        % (
            " + stem" if options.allow_stemming else "",
            " + fuzzy<=%d" % options.max_edits if options.allow_fuzzy else "",
        ),
        "",
        table(
            [
                ["your mapping", "%.2f%%" % (distribution.observed * 100)],
                ["best random mapping", "%.2f%%" % (distribution.best_random * 100)],
                ["mean random mapping", "%.2f%%" % (distribution.mean * 100)],
                ["standard deviation", "%.2f%%" % (distribution.stdev * 100)],
                ["z-score", "%+.2f" % distribution.z_score],
                ["percentile", "%.1f" % distribution.percentile],
            ],
            ["measure", "value"],
        ),
        "",
        "Verdict: " + distribution.verdict(),
        "",
        "Distribution of random hit rates",
        "-" * 32,
        distribution.histogram(),
        "",
        "Why a hit rate needs a control\n"
        "------------------------------\n"
        "A Latin dictionary contains tens of thousands of words, many of them two or three letters\n"
        "long. Any assignment of letters to glyphs will hit some of them, and Voynichese word\n"
        "lengths make it easier than you would guess. Published 'solutions' routinely quote hit\n"
        "rates that a coin toss would have produced.\n\n"
        "This runs the same matcher over randomly relabelled versions of the same text and shows\n"
        "the distribution. Note the 'best random mapping' row in particular: if even one arbitrary\n"
        "mapping matched as much as yours, the hit rate is not evidence.\n\n"
        "Merging and splitting are switched off for both sides here, because they raise everyone's\n"
        "hit rate and would only add noise to the comparison.",
    ]
    save_text(ctx, "match_significance.txt", "\n".join(blocks) + "\n", "dictionary hit rate against random mappings")

    payload = distribution.to_dict()
    payload["verdict"] = distribution.verdict()
    payload["language"] = language
    payload["runs"] = runs
    if observed_report:
        payload["reported_coverage"] = observed_report.get("coverage")
    return payload


def _coverage(matcher: Matcher, rendered: list, counts: list, total: int) -> float:
    hits = 0
    for word, count in zip(rendered, counts):
        if matcher.match_word(word).route != "none":
            hits += count
    return hits / total


PLUGIN = Plugin(
    name="match_significance",
    title="Significance of dictionary hits",
    stage="baseline",
    category="baselines",
    summary="Compares your dictionary hit rate with what random mappings achieve.",
    help=(
        "Takes the dictionary hit rate seriously by asking what it would be for nothing.\n\n"
        "The same text is relabelled with random glyph-to-letter mappings, matched with the same\n"
        "dictionary and the same settings, and the distribution of hit rates is reported. Your\n"
        "score is placed in that distribution as a z-score and a percentile, with a histogram.\n\n"
        "Pay attention to the 'best random mapping' line. A z-score can look impressive while a\n"
        "single lucky random mapping still matched as much as yours, and when that happens the hit\n"
        "rate is not evidence of anything.\n\n"
        "This plugin reads better alongside 'corpus_match', which produces the number being tested."
    ),
    defaults={"language": "", "runs": 60, "maxEdits": 1, "stemming": True, "alphabet": LATIN_LOWER},
    settings_help={
        "language": "Dictionary to use; empty uses reference.language.",
        "runs": "How many random mappings to score.",
        "maxEdits": "Fuzzy matching distance, applied to both your mapping and the controls.",
        "stemming": "Whether stemmed matches count, for both sides.",
        "alphabet": "The letters random mappings may use.",
    },
    optional_requires=("corpus_match",),
    heavy=True,
    run=run,
)
