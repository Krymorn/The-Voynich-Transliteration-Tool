"""Shuffled-text baselines: which statistics actually measure structure."""

from __future__ import annotations

from ..analysis import StatBundle, stat_bundle
from ..baselines import SHUFFLE_DESCRIPTIONS, SHUFFLE_MODES, shuffled_baseline
from ..util import table
from . import Plugin, PluginContext
from ._common import rng, save_text, track, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    line_words = ctx.result.line_words()
    modes = [m for m in ctx.setting("modes", list(SHUFFLE_MODES)) if m in SHUFFLE_MODES]
    repeats = max(1, ctx.setting("repeats", 1))

    rows = [stat_bundle(output_words, "your transliteration").row()]
    details = {}

    for mode in track(ctx, modes, "shuffles"):
        bundles = []
        for i in range(repeats):
            generator = rng(ctx)
            generator.seed(ctx.config.seed() + i)
            shuffled = shuffled_baseline(output_words, mode, generator, line_words)
            bundles.append(stat_bundle(shuffled, "shuffle: " + mode))
        averaged = _average(bundles, "shuffle: " + mode)
        rows.append(averaged.row())
        details[mode] = {"description": SHUFFLE_DESCRIPTIONS[mode], **averaged.to_dict()}

    changes = _sensitivity(rows[0], rows[1:], [r[0] for r in rows[1:]])

    blocks = [
        "Shuffled-text baselines",
        "=" * 23,
        "",
        table(rows, StatBundle.headers()),
        "",
        "What each shuffle destroys",
        "-" * 26,
        table([[m, SHUFFLE_DESCRIPTIONS[m]] for m in modes], ["shuffle", "what it destroys"]),
        "",
        "How much each measure moves when structure is destroyed",
        "-" * 55,
        table(changes, ["measure", "your text", "most affected by", "value there", "change"]),
        "",
        "How to use this\n"
        "---------------\n"
        "Each shuffle removes exactly one kind of structure and leaves the rest alone. If a\n"
        "measure hardly changes when the structure it supposedly detects is destroyed, then that\n"
        "measure was never detecting it.\n\n"
        "Two examples worth knowing. Zipf's law survives every shuffle that keeps the vocabulary,\n"
        "so a good Zipf fit says almost nothing. Conditional entropy collapses the moment you\n"
        "anagram the words, which is why it is the statistic that actually distinguishes\n"
        "Voynichese from noise.",
    ]
    save_text(ctx, "shuffles.txt", "\n".join(blocks) + "\n", "statistics under shuffled baselines")

    return {"table": rows, "headers": StatBundle.headers(), "baselines": details, "sensitivity": changes}


def _average(bundles: list, label: str) -> StatBundle:
    if len(bundles) == 1:
        return bundles[0]
    fields = [
        "tokens",
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
    values = {f: sum(getattr(b, f) for b in bundles) / len(bundles) for f in fields}
    values["tokens"] = int(values["tokens"])
    values["types"] = int(values["types"])
    return StatBundle(label=label, **values)


def _sensitivity(base_row: list, other_rows: list, labels: list) -> list:
    headers = StatBundle.headers()
    out = []
    for index in range(3, len(headers)):
        try:
            base = float(base_row[index])
        except (TypeError, ValueError):
            continue
        worst = None
        for label, row in zip(labels, other_rows):
            try:
                value = float(row[index])
            except (TypeError, ValueError):
                continue
            delta = abs(value - base)
            if worst is None or delta > worst[2]:
                worst = (label, value, delta)
        if worst:
            out.append([headers[index], "%.4f" % base, worst[0], "%.4f" % worst[1], "%+.4f" % (worst[1] - base)])
    return out


PLUGIN = Plugin(
    name="shuffles",
    title="Shuffled-text baselines",
    stage="baseline",
    category="baselines",
    summary="Destroys one kind of structure at a time to see which statistics notice.",
    help=(
        "Five baselines, each removing exactly one thing:\n\n"
        "  characters     every character reshuffled globally, word lengths kept\n"
        "  within_words   each word anagrammed, so the vocabulary shape survives but order dies\n"
        "  words          word order shuffled, vocabulary untouched\n"
        "  lines          line order shuffled, every line intact\n"
        "  word_lengths   words replaced by random strings of the same length\n\n"
        "Running your statistics over each one tells you what those statistics are really\n"
        "sensitive to. A measure that barely moves when you destroy the structure it claims to\n"
        "detect is not evidence of anything, and there are more of those than people expect."
    ),
    defaults={"modes": list(SHUFFLE_MODES), "repeats": 1},
    settings_help={
        "modes": "Which shuffles to run.",
        "repeats": "Average over this many shuffles per mode (slower, less noisy).",
    },
    heavy=True,
    run=run,
)
