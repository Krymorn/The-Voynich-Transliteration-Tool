"""Held-out validation: score on text the mapping was not tuned on."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from ..baselines import HoldoutReport
from ..corpus import Selection
from ..folios import SECTIONS
from ..langmodel import Fitness, FitnessOptions
from ..transliterate import build_engine, transliterate
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    metric = ctx.setting("metric", "quadgram")
    language = ctx.setting("language") or ctx.config.get("reference.language", "latin")
    fit_on = ctx.setting("fitOn", "herbal_a")
    held_out = ctx.setting("heldOut") or []
    # Compile the mapping against the whole manuscript's glyphs, not just the
    # selection's. A glyph that appears only in a held-out section would
    # otherwise be unknown to the engine and silently dropped from the very
    # words we are scoring.
    current = ctx.result.engine
    engine = build_engine(
        current.mapping,
        _whole_manuscript(ctx),
        markers=current.markers,
        precedence=current.precedence,
        unmapped=current.unmapped,
        placeholder=current.placeholder,
    )

    if fit_on not in SECTIONS:
        ctx.log.warning("fitOn=%r is not a section name; falling back to herbal_a", fit_on)
        fit_on = "herbal_a"
    if not held_out:
        held_out = [name for name in ("herbal_b", "biological", "recipes", "pharmaceutical") if name != fit_on]

    fit_score, fit_words = _score_section(ctx, engine, fit_on, metric, language)
    if fit_score is None:
        return {"error": "no words in section %r" % fit_on}

    reports = []
    rows = [[SECTIONS[fit_on].title + "  (fitted on)", fit_words, "%.5f" % fit_score, "", ""]]
    for name in held_out:
        if name not in SECTIONS:
            ctx.log.warning("unknown section %r in heldOut, skipping", name)
            continue
        score, count = _score_section(ctx, engine, name, metric, language)
        if score is None:
            continue
        report = HoldoutReport(SECTIONS[fit_on].title, SECTIONS[name].title, fit_score, score, metric)
        reports.append(report)
        rows.append([SECTIONS[name].title, count, "%.5f" % score, "%+.1f%%" % (-report.drop * 100), report.verdict()])

    worst = max(reports, key=lambda r: r.drop) if reports else None

    blocks = [
        "Held-out validation",
        "=" * 19,
        "",
        "fitness: %s over %s" % (metric, language),
        "",
        table(rows, ["section", "words", "score", "change", "verdict"]),
        "",
    ]
    if worst:
        blocks.append("Worst case: " + worst.verdict())
        blocks.append("")
    blocks.append(
        "Why hold text back\n"
        "------------------\n"
        "Every rule you add to a mapping is a free parameter, and free parameters let you fit\n"
        "anything. Positional rules and occurrence rules are especially powerful: with enough of\n"
        "them you can make almost any text produce almost any output.\n\n"
        "The only defence is to score the mapping on text it was never adjusted against. If the\n"
        "score holds up on a section you did not look at while designing the rules, the mapping is\n"
        "capturing something general. If it falls away, the rules were describing one section's\n"
        "quirks.\n\n"
        "This is only honest if you really did design the mapping against 'fitOn'. The plugin\n"
        "cannot know which text you were looking at - set fitOn to whatever you actually worked on."
    )
    save_text(ctx, "holdout.txt", "\n".join(blocks) + "\n", "scores on sections the mapping was not tuned on")

    return {
        "metric": metric,
        "language": language,
        "fit_on": fit_on,
        "fit_score": round(fit_score, 6),
        "held_out": [r.to_dict() for r in reports],
        "worst_verdict": worst.verdict() if worst else "",
        "worst_drop": round(worst.drop, 4) if worst else 0.0,
    }


def _whole_manuscript(ctx):
    """The complete text, not the current selection.

    Held-out validation exists to score sections you did *not* work on, so it
    has to look outside the selection. Selecting within an already-filtered
    corpus finds nothing, which is how this silently reported no words at all.
    The load is cached, so asking for it again is cheap.
    """
    from ..corpus import load_corpus, resolve_transcription

    spec = resolve_transcription(ctx.config.get("transcription", "zl"))
    return load_corpus(spec.key, ctx.config.parse_options(), Selection())


def _score_section(ctx, engine, section: str, metric: str, language: str):
    # Keep the user's other filters (text class, Currier, scribe) but drop the
    # ones that would pin us to the section we are trying to look beyond.
    base = replace(ctx.corpus.selection, sections=(section,), folios=(), exclude_folios=())
    sub = _whole_manuscript(ctx).select(base)
    if sub.is_empty:
        return None, 0
    mapped = transliterate(sub, engine, ctx.result.word_separator, ctx.result.uncertain_separator)
    source_vocabulary = Counter(sub.words())
    fitness = Fitness(FitnessOptions(function=metric, language=language), source_vocabulary)
    rendered = [engine.map_word(word) for word in fitness.types]
    return fitness.score(rendered), len(mapped.words())


PLUGIN = Plugin(
    name="holdout",
    title="Held-out validation",
    stage="baseline",
    category="baselines",
    summary="Scores the mapping on sections it was not designed against, to catch overfitting.",
    help=(
        "Tell it which section you actually developed your mapping on, and it scores that section\n"
        "and several others with the same measure.\n\n"
        "A mapping that generalises scores about the same everywhere. A mapping that has been\n"
        "tuned - consciously or not - to the section in front of you scores well there and worse\n"
        "elsewhere, and the size of that drop is a direct measure of how much of your result is\n"
        "fitting rather than reading.\n\n"
        "This is the standard defence against overfitting in every other empirical field, and it is\n"
        "almost never applied to Voynich decipherments. It costs one setting."
    ),
    defaults={"metric": "quadgram", "language": "", "fitOn": "herbal_a", "heldOut": []},
    settings_help={
        "metric": "Fitness to score with: quadgram, trigram, bigram, dictionary or blend.",
        "language": "Target language; empty uses reference.language from config.json.",
        "fitOn": "The section you developed the mapping against.",
        "heldOut": "Sections to test on; empty picks a sensible set.",
    },
    heavy=True,
    run=run,
)
