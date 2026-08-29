"""Draw the plots: Zipf, Heaps, word length and the transition matrix."""

from __future__ import annotations

from ..analysis import ngram_profile, vocabulary_profile, word_length_profile, zipf_profile
from ..errors import DependencyError
from ..langmodel import control_text
from ..lexicon import tokenize
from ..util import has_module
from . import Plugin, PluginContext


def run(ctx: PluginContext) -> dict:
    from .. import reporting

    if not has_module("matplotlib") and not (ctx.setting("interactive") and has_module("plotly")):
        raise DependencyError(
            "no plotting library is installed",
            hint="Install one with: pip install matplotlib   (or: pip install plotly, then set "
            "the plugin's 'interactive' setting to true). Every number these plots show is also "
            "written as text and CSV by the other plugins, so you can also just disable this one.",
        )

    words = ctx.result.words()
    written = []
    wanted = set(ctx.setting("plots", ["zipf", "heaps", "word_length", "transitions"]))

    if "zipf" in wanted:
        profile = zipf_profile(words)
        overlays = []
        for language in ctx.setting("overlayLanguages", []):
            try:
                other = zipf_profile(tokenize(control_text(language))[: len(words)])
                overlays.append((language, other.ranks, other.frequencies))
            except Exception as exc:
                ctx.log.warning("could not overlay %r: %s", language, exc)
        if ctx.setting("interactive") and has_module("plotly"):
            path = reporting.plotly_zipf(profile, ctx.output_path("zipf.html"))
            written.append(("zipf", str(path)))
            ctx.record_output(path, "interactive Zipf plot")
        else:
            path = reporting.zipf_plot(
                profile, ctx.output_path("zipf.png"), ctx.setting("referenceLines", True), overlays=overlays
            )
            written.append(("zipf", str(path)))
            ctx.record_output(path, "Zipf plot")

    if "heaps" in wanted:
        vocabulary = vocabulary_profile(words)
        path = reporting.heaps_plot(
            vocabulary.heaps_points, vocabulary.heaps_k, vocabulary.heaps_beta, ctx.output_path("heaps.png")
        )
        written.append(("heaps", str(path)))
        ctx.record_output(path, "Heaps' law plot")

    if "word_length" in wanted:
        references = {}
        for language in ctx.setting("overlayLanguages", []):
            try:
                references[language] = word_length_profile(tokenize(control_text(language))).counts
            except Exception:
                continue
        path = reporting.word_length_plot(word_length_profile(words), ctx.output_path("word_length.png"), references)
        written.append(("word_length", str(path)))
        ctx.record_output(path, "word length distribution plot")

    if "transitions" in wanted:
        profile = ngram_profile(words)
        path = reporting.matrix_plot(
            profile.probability_matrix(),
            profile.alphabet,
            profile.alphabet,
            ctx.output_path("transitions.png"),
            "character transition probabilities",
        )
        written.append(("transitions", str(path)))
        ctx.record_output(path, "character transition heatmap")

    return {"plots": dict(written)}


PLUGIN = Plugin(
    name="plots",
    title="Plots",
    stage="report",
    category="output",
    summary="Draws Zipf, Heaps, word length and transition-matrix plots as images.",
    help=(
        "Four pictures, each of a statistic another plugin has already computed:\n\n"
        "  zipf          rank against frequency on log-log axes, with reference slopes for real\n"
        "                languages and, if you ask, real languages plotted alongside\n"
        "  heaps         vocabulary growth, with the fitted curve\n"
        "  word_length   the length distribution against its best binomial fit\n"
        "  transitions   the character transition matrix as a heatmap\n\n"
        "matplotlib is needed for the images. If you would rather have an interactive Zipf plot you\n"
        "can zoom and hover, install plotly and set 'interactive' to true.\n\n"
        "Neither library is required to use TVTT: every number in these plots is also written out\n"
        "as text and CSV. If you have no plotting library, disable this plugin and nothing else\n"
        "changes."
    ),
    defaults={
        "plots": ["zipf", "heaps", "word_length", "transitions"],
        "referenceLines": True,
        "overlayLanguages": [],
        "interactive": False,
    },
    settings_help={
        "plots": "Which plots to draw.",
        "referenceLines": "Draw reference Zipf slopes for real languages.",
        "overlayLanguages": "Plot these control languages on the same axes, e.g. ['latin','italian'].",
        "interactive": "Use Plotly for an interactive Zipf plot instead of a PNG.",
    },
    run=run,
)
