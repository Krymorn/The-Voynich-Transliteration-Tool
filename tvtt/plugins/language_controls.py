"""Run the same statistics on real languages, so the numbers have context."""

from __future__ import annotations

from ..analysis import StatBundle, stat_bundle
from ..langmodel import available_controls, control_text
from ..lexicon import tokenize
from ..reporting import write_csv
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, track, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    requested = ctx.setting("languages") or available_controls()
    sample = ctx.setting("sampleTokens", 0) or len(output_words)

    rows = [stat_bundle(output_words, "your transliteration").row()]
    details = {}

    for language in track(ctx, requested, "control languages"):
        try:
            tokens = tokenize(control_text(language))
        except Exception as exc:
            ctx.log.warning("skipping control %r: %s", language, exc)
            continue
        if len(tokens) < 500:
            continue
        bundle = stat_bundle(tokens[:sample], language)
        rows.append(bundle.row())
        details[language] = bundle.to_dict()

    nearest = _nearest(rows)

    blocks = [
        "Real-language controls",
        "=" * 22,
        "",
        "Every text sampled to %d tokens so the length-sensitive measures compare fairly." % sample,
        "",
        table(rows, StatBundle.headers()),
        "",
        "Closest control language by each measure",
        "-" * 41,
        table(nearest, ["measure", "your value", "closest language", "its value", "gap"]),
        "",
        "About these samples\n"
        "-------------------\n"
        "The bundled control texts are public-domain works, trimmed to a couple of hundred\n"
        "kilobytes each: Vergil, Augustine and Linnaeus for Latin; Dante for Italian; Chaucer for\n"
        "Middle English; the King James Bible and Austen for English; Walther von der Vogelweide\n"
        "for Middle High German; Capek for Czech; a Gascon text for Occitan; and the consonantal\n"
        "Torah and Quran, both also supplied in Latin transliteration for consonant-only mappings.\n\n"
        "They are samples, not corpora. Use them to see whether a number is in the right\n"
        "neighbourhood, not to make fine distinctions between languages. To use your own text\n"
        "instead, drop it in reference_texts/ under the language name.",
    ]
    save_text(ctx, "language_controls.txt", "\n".join(blocks) + "\n", "the same statistics for real languages")

    if ctx.setting("writeCsv", True):
        path = write_csv(ctx.output_path("language_controls.csv"), rows, StatBundle.headers())
        ctx.record_output(path, "control-language statistics as CSV")

    return {"table": rows, "headers": StatBundle.headers(), "languages": details, "nearest": nearest}


def _nearest(rows: list) -> list:
    headers = StatBundle.headers()
    if len(rows) < 2:
        return []
    out = []
    for index in range(3, len(headers)):
        try:
            base = float(rows[0][index])
        except (TypeError, ValueError):
            continue
        best = None
        for row in rows[1:]:
            try:
                value = float(row[index])
            except (TypeError, ValueError):
                continue
            gap = abs(value - base)
            if best is None or gap < best[2]:
                best = (row[0], value, gap)
        if best:
            out.append([headers[index], "%.4f" % base, best[0], "%.4f" % best[1], "%.4f" % best[2]])
    return out


PLUGIN = Plugin(
    name="language_controls",
    title="Real-language controls",
    stage="baseline",
    category="baselines",
    summary="Runs identical statistics on Latin, Italian, Hebrew, English and more.",
    help=(
        "A statistic with no comparison is not a result. This plugin computes exactly the same\n"
        "measures on bundled samples of real languages, sampled to the same number of tokens as\n"
        "your text so that length-sensitive measures compare fairly.\n\n"
        "Bundled: " + ", ".join(available_controls()) + ".\n\n"
        "The second table names, for each measure, the control language your output is closest to.\n"
        "It is worth reading carefully. Voynichese usually lands near a real language on word\n"
        "length and Zipf exponent, and nowhere near any of them on conditional entropy - and it is\n"
        "the second fact, not the first, that a decipherment has to explain.\n\n"
        "To use your own control text, put it in reference_texts/ named after the language."
    ),
    defaults={"languages": [], "sampleTokens": 0, "writeCsv": True},
    settings_help={
        "languages": "Which control languages to run; empty means all bundled ones.",
        "sampleTokens": "How many tokens of each control to use; 0 matches your text's length.",
        "writeCsv": "Also write language_controls.csv.",
    },
    heavy=True,
    run=run,
)
