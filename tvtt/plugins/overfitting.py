"""Warn when a mapping's extra rules are not paying for themselves."""

from __future__ import annotations

from collections import Counter

from ..baselines import OverfittingReport
from ..langmodel import Fitness, FitnessOptions
from ..mapping import SLOT_NAMES, SLOT_PLAIN, Mapping
from ..transliterate import build_engine
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    mapping = ctx.result.engine.mapping
    metric = ctx.setting("metric", "quadgram")
    language = ctx.setting("language") or ctx.config.get("reference.language", "latin")

    vocabulary = Counter(ctx.corpus.words())
    fitness = Fitness(FitnessOptions(function=metric, language=language), vocabulary)

    full_score = fitness.score([ctx.result.engine.map_word(word) for word in fitness.types])

    plain_only = Mapping(
        rules={g: {SLOT_PLAIN: slots[SLOT_PLAIN]} for g, slots in mapping.rules.items() if SLOT_PLAIN in slots},
        meta={"name": "plain rules only"},
    )
    plain_engine = build_engine(
        plain_only,
        ctx.corpus,
        precedence=ctx.result.engine.precedence,
        unmapped=ctx.result.engine.unmapped,
        placeholder=ctx.result.engine.placeholder,
    )
    plain_score = fitness.score([plain_engine.map_word(word) for word in fitness.types])

    report = OverfittingReport(
        rules=mapping.rule_count(),
        extra_rules=mapping.complexity(),
        glyphs=len(mapping.rules),
        baseline_score=plain_score,
        score=full_score,
        tokens=sum(vocabulary.values()),
    )

    breakdown = Counter()
    for slots in mapping.rules.values():
        for slot in slots:
            breakdown[SLOT_NAMES[slot]] += 1

    blocks = [
        "Mapping complexity and overfitting",
        "=" * 34,
        "",
        table(
            [
                ["glyphs with a rule", report.glyphs],
                ["rules in total", report.rules],
                ["extra positional / occurrence rules", report.extra_rules],
                ["score with every rule", "%.5f" % report.score],
                ["score with plain rules only", "%.5f" % report.baseline_score],
                ["gain from the extra rules", "%+.5f" % report.gain],
                ["gain per extra rule", "%+.6f" % report.gain_per_rule],
            ],
            ["measure", "value"],
        ),
        "",
        "Rules by kind",
        "-" * 13,
        table(sorted(breakdown.items()), ["kind", "count"]),
        "",
        "Warning level: %s" % report.level().upper(),
        report.message(),
        "",
        "Why complexity is a cost, not a feature\n"
        "---------------------------------------\n"
        "A plain mapping has one rule per glyph. Every positional or occurrence rule you add is\n"
        "another free parameter - another dial you can turn until the output looks better.\n\n"
        "With enough dials you can make any text produce any output, so a score that only improves\n"
        "because you added rules is not evidence about the manuscript. This plugin compares your\n"
        "full mapping against the same mapping with every extra rule stripped out. If the gain is\n"
        "small, or if the number of extra rules is approaching the number of glyphs, the extra\n"
        "structure is decoration.\n\n"
        "Whatever the level says here, check the 'holdout' plugin too: rules that genuinely help\n"
        "keep helping on text you did not tune them on.",
    ]
    save_text(ctx, "overfitting.txt", "\n".join(blocks) + "\n", "mapping complexity against the gain it buys")

    if report.level() in ("high", "severe"):
        ctx.log.warning("overfitting risk %s: %s", report.level(), report.message().split("\n")[0])

    payload = report.to_dict()
    payload["message"] = report.message()
    payload["rules_by_kind"] = dict(breakdown)
    return payload


PLUGIN = Plugin(
    name="overfitting",
    title="Overfitting warning",
    stage="baseline",
    category="baselines",
    summary="Compares your mapping's score against the same mapping stripped to plain rules.",
    help=(
        "Counts how much freedom your mapping has, and how much of the score that freedom is\n"
        "actually buying.\n\n"
        "The comparison is direct: your mapping is scored, then every positional and occurrence\n"
        "rule is removed and the plain remainder is scored again. If the difference is small, the\n"
        "extra rules are not doing anything. If the number of extra rules is large relative to the\n"
        "number of glyphs, then even a real difference is suspect, because a mapping with that many\n"
        "parameters can fit almost anything.\n\n"
        "The warning level runs none, low, moderate, high, severe. Anything above moderate is worth\n"
        "acting on: try deleting the extra rules and seeing whether you miss them."
    ),
    defaults={"metric": "quadgram", "language": ""},
    settings_help={
        "metric": "Fitness to compare with.",
        "language": "Target language; empty uses reference.language from config.json.",
    },
    run=run,
)
