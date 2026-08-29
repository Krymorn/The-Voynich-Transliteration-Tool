"""Compare the current mapping with another one, and show how the statistics moved."""

from __future__ import annotations

from ..analysis import StatBundle, stat_bundle
from ..mapping import Mapping, mapping_diff
from ..profiles import find_profile
from ..transliterate import build_engine, transliterate
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    against = ctx.setting("against", "")
    if not against:
        return {"skipped": "set the 'against' setting to a mapping profile name or file path"}

    profile = find_profile(against)
    other: Mapping = profile.load()
    current: Mapping = ctx.result.engine.mapping

    changes = mapping_diff(other, current)

    other_engine = build_engine(
        other,
        ctx.corpus,
        precedence=ctx.result.engine.precedence,
        unmapped=ctx.result.engine.unmapped,
        placeholder=ctx.result.engine.placeholder,
    )
    other_result = transliterate(ctx.corpus, other_engine, ctx.result.word_separator, ctx.result.uncertain_separator)

    before = stat_bundle(other_result.words(), profile.name)
    after = stat_bundle(ctx.result.words(), current.meta.get("name", "current"))

    moves = _moves(before, after)

    samples = []
    for source, mine in list(zip(ctx.corpus.words(), ctx.result.words()))[: ctx.setting("sampleWords", 4000)]:
        theirs = other_engine.map_word(source)
        if theirs != mine:
            samples.append([source, theirs, mine])
        if len(samples) >= ctx.setting("maxSamples", 40):
            break

    blocks = [
        "Mapping diff: %s -> %s" % (profile.name, current.meta.get("name", "current")),
        "=" * 60,
        "",
        "%d rule difference(s)." % len(changes),
        "",
        table(
            [[c["glyph"], c["position"], c["before"] or "-", c["after"] or "-", c["change"]] for c in changes],
            ["glyph", "position", "before", "after", "change"],
        ),
        "",
        "How the statistics moved",
        "-" * 24,
        table([before.row(), after.row()], StatBundle.headers()),
        "",
        table(moves, ["measure", "before", "after", "change", "relative"]),
        "",
        "Words that came out differently",
        "-" * 31,
        table(samples, ["source", profile.name, "current"]),
        "",
        "Why compare mappings rather than just look at one\n"
        "-------------------------------------------------\n"
        "Changing a mapping changes every number downstream, and it is easy to convince yourself a\n"
        "change helped when it moved one figure and quietly worsened three others. This puts the two\n"
        "versions side by side and orders the measures by how much they actually moved, so the real\n"
        "effect of an edit is the first thing you see.\n\n"
        "Every mapping saved through TVTT keeps its previous versions, so you can diff against your\n"
        "own history: 'tvtt mapping history <name>' lists them.",
    ]
    save_text(ctx, "mapping_diff.txt", "\n".join(blocks) + "\n", "difference between two mappings")

    return {
        "against": profile.name,
        "rule_changes": changes,
        "before": before.to_dict(),
        "after": after.to_dict(),
        "moves": moves,
        "changed_word_samples": samples,
    }


def _moves(before: StatBundle, after: StatBundle) -> list:
    fields = [
        "types",
        "h1",
        "h2",
        "mean_word_length",
        "ttr",
        "mattr",
        "hapax_ratio",
        "zipf_slope",
        "heaps_beta",
        "immediate_repeat_rate",
        "binomial_fit_error",
        "slot_conformance",
    ]
    rows = []
    for field in fields:
        a = getattr(before, field)
        b = getattr(after, field)
        relative = abs(b - a) / abs(a) if a else 0.0
        rows.append([field, "%.4f" % a, "%.4f" % b, "%+.4f" % (b - a), "%.1f%%" % (relative * 100)])
    rows.sort(key=lambda r: -float(r[4].rstrip("%")))
    return rows


PLUGIN = Plugin(
    name="mapping_diff",
    title="Mapping diff",
    stage="analyze",
    category="validation",
    summary="Compares the current mapping with another and shows exactly what changed.",
    help=(
        "Set 'against' to the name of another mapping profile, or a path to a mapping file, and this\n"
        "plugin reports three things:\n\n"
        "  - every rule that differs, with what it was and what it became\n"
        "  - how each headline statistic moved, ordered by how much it moved\n"
        "  - a sample of source words that now come out differently\n\n"
        "It is easy to change a mapping, see one number improve, and not notice that three others\n"
        "got worse. Ordering the table by size of movement puts the real effect of an edit first.\n\n"
        "Because TVTT keeps a version history of every mapping it saves, you can also compare\n"
        "against your own earlier thinking: run 'tvtt mapping history <name>' to see the versions,\n"
        "and 'tvtt mapping restore <name> <version>' to go back to one."
    ),
    defaults={"against": "", "sampleWords": 4000, "maxSamples": 40},
    settings_help={
        "against": "Mapping profile name or file path to compare with.",
        "sampleWords": "How many words to scan for differences.",
        "maxSamples": "How many differing words to list.",
    },
    run=run,
)
