"""Run every headline statistic once per manuscript section and diff them."""

from __future__ import annotations

from dataclasses import replace

from ..analysis import StatBundle, stat_bundle
from ..folios import SECTIONS
from ..reporting import write_csv
from ..transliterate import transliterate
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, track


def run(ctx: PluginContext) -> dict:
    wanted = ctx.setting("sections") or list(SECTIONS)
    minimum = ctx.setting("minWords", 400)
    engine = ctx.result.engine

    bundles = []
    rows = []
    details = {}

    whole = stat_bundle(ctx.result.words(), "whole selection")
    bundles.append(whole)

    for name in track(ctx, wanted, "sections"):
        if name not in SECTIONS:
            ctx.log.warning("unknown section %r, skipping", name)
            continue
        sub = ctx.corpus.select(replace(ctx.corpus.selection, sections=(name,)))
        if sub.is_empty:
            continue
        mapped = transliterate(sub, engine, ctx.result.word_separator, ctx.result.uncertain_separator)
        sub_words = mapped.words()
        if len(sub_words) < minimum:
            continue
        bundle = stat_bundle(sub_words, SECTIONS[name].title)
        bundles.append(bundle)
        details[name] = bundle.to_dict()

    for bundle in bundles:
        rows.append(bundle.row())

    spread = _spread(bundles[1:])

    blocks = [
        "Statistics by manuscript section",
        "=" * 32,
        "",
        table(rows, StatBundle.headers()),
        "",
        "Spread across sections (largest minus smallest)",
        "-" * 47,
        table(spread, ["measure", "lowest", "highest", "range", "section with the lowest", "section with the highest"]),
        "",
        "Why compare sections\n"
        "--------------------\n"
        "The manuscript is not one homogeneous text. Currier showed in the 1970s that two\n"
        "statistically distinct 'languages', A and B, run through it, and the sections differ\n"
        "further in vocabulary and word length. Averaging everything together hides exactly the\n"
        "structure you are trying to explain.\n\n"
        "A mapping that is genuinely reading the text should behave consistently across sections,\n"
        "or should differ in a way you can explain. A mapping that scores well on one section and\n"
        "badly on the rest has been fitted to that section - which the 'holdout' plugin measures\n"
        "directly.",
    ]
    save_text(ctx, "sections.txt", "\n".join(blocks) + "\n", "every statistic computed per section")

    if ctx.setting("writeCsv", True):
        path = write_csv(ctx.output_path("sections.csv"), rows, StatBundle.headers())
        ctx.record_output(path, "section statistics as CSV")

    return {"sections": details, "table": rows, "headers": StatBundle.headers(), "spread": spread}


def _spread(bundles: list) -> list:
    if len(bundles) < 2:
        return []
    fields = [
        "h1",
        "h2",
        "mean_word_length",
        "ttr",
        "mattr",
        "hapax_ratio",
        "zipf_slope",
        "heaps_beta",
        "immediate_repeat_rate",
        "slot_conformance",
    ]
    rows = []
    for field in fields:
        pairs = [(getattr(b, field), b.label) for b in bundles]
        low = min(pairs)
        high = max(pairs)
        rows.append([field, "%.4f" % low[0], "%.4f" % high[0], "%.4f" % (high[0] - low[0]), low[1], high[1]])
    return rows


PLUGIN = Plugin(
    name="section_report",
    title="Cross-section comparison",
    stage="analyze",
    category="statistics",
    summary="Computes every headline statistic per section and shows how much they differ.",
    help=(
        "Runs the same set of measurements over each named part of the manuscript - Herbal A,\n"
        "Herbal B, Astronomical, Zodiac, Biological, Cosmological, Pharmaceutical, Recipes - and\n"
        "prints them side by side, with a table of how far each measure ranges across sections.\n\n"
        "This is often the most informative single output in the tool. Currier's A and B\n"
        "'languages' show up immediately, and so does anything odd about a mapping: a reading that\n"
        "works on the herbal pages and collapses on the balneological ones is telling you\n"
        "something, whether or not you like what it says."
    ),
    defaults={"sections": [], "minWords": 400, "writeCsv": True},
    settings_help={
        "sections": "Which sections to include; empty means all of them.",
        "minWords": "Skip sections with fewer words than this, where statistics are unreliable.",
        "writeCsv": "Also write sections.csv.",
    },
    run=run,
)
