"""Check that the mapping is reversible, and report where it is not."""

from __future__ import annotations

from ..mapping import round_trip_check
from ..reporting import glyph_label
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    engine = ctx.result.engine
    vocabulary = list(ctx.corpus.word_counts())
    report = round_trip_check(engine, vocabulary)

    rows = []
    for text, sources in sorted(report.collisions.items(), key=lambda kv: -len(kv[1])):
        rows.append(
            [
                text or "(empty)",
                len(sources),
                ", ".join("%s (%s)" % (glyph_label(g), slot) for g, slot in sources),
            ]
        )

    blocks = [report.summary(), ""]
    if rows:
        blocks.append("Collisions: two or more glyphs producing the same letters")
        blocks.append(table(rows, ["becomes", "glyphs", "sources"]))
        blocks.append("")
        blocks.append(
            "Every collision throws information away. Two different glyphs that become the same\n"
            "letter cannot be told apart afterwards, so no reader could ever recover the original\n"
            "text from your output. That may be intentional - many real ciphers are not injective -\n"
            "but it means the output contains less than the manuscript does, and a high dictionary\n"
            "score partly reflects that loss rather than a decipherment."
        )
    if report.unmapped:
        blocks.append("")
        blocks.append(
            "Glyphs with no rule (%d): %s"
            % (len(report.unmapped), " ".join(glyph_label(g) for g in report.unmapped[:80]))
        )
    if report.empty_rules:
        blocks.append("")
        blocks.append(
            "Glyphs mapped to nothing (%d): %s"
            % (len(report.empty_rules), " ".join(glyph_label(g) for g in report.empty_rules[:80]))
        )
    if report.expanding:
        blocks.append("")
        blocks.append(
            "Glyphs that expand into several letters (%d): %s"
            % (len(report.expanding), " ".join(glyph_label(g) for g in report.expanding[:80]))
        )

    save_text(ctx, "roundtrip.txt", "\n".join(blocks) + "\n", "mapping reversibility check")

    if ctx.setting("failOnCollision") and report.collisions:
        ctx.log.warning(
            "mapping is not injective: %d collision(s). Set failOnCollision=false to silence this.",
            len(report.collisions),
        )

    return {
        "injective": report.injective,
        "collision_count": len(report.collisions),
        "collisions": {k: [g for g, _ in v] for k, v in list(report.collisions.items())[:50]},
        "unmapped_glyphs": [glyph_label(g) for g in report.unmapped],
        "empty_rules": [glyph_label(g) for g in report.empty_rules],
        "glyph_coverage": round(report.coverage, 4),
        "words_checked": report.checked_words,
        "words_reversible": report.reversible_words,
        "summary": report.summary(),
    }


PLUGIN = Plugin(
    name="roundtrip",
    title="Round-trip validation",
    stage="analyze",
    category="validation",
    summary="Checks whether the mapping is injective, and lists every collision.",
    help=(
        "A mapping is *injective* when no two glyphs produce the same letters. Only an injective\n"
        "mapping can be undone: run it backwards and you get the manuscript again.\n\n"
        "Non-injective mappings are not forbidden - plenty of real ciphers merge symbols - but they\n"
        "matter for how you read your results. Merging glyphs raises dictionary hit rates for free,\n"
        "because it makes more different Voynich words collapse onto the same output word, and some\n"
        "of those will be real words by accident. This plugin tells you exactly how much of that is\n"
        "going on: which glyphs collide, how many glyphs have no rule at all, and what fraction of a\n"
        "sample of real manuscript words survives a there-and-back trip."
    ),
    defaults={"failOnCollision": True},
    settings_help={"failOnCollision": "Log a warning when the mapping is not injective."},
    enabled_by_default=True,
    run=run,
)
