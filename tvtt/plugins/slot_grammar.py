"""Stolfi's crust-mantle-core model: is a word still built from a template?"""

from __future__ import annotations

from ..analysis import slot_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    profile = slot_profile(output_words, ctx.setting("minShare", 0.02))

    non_conforming = [w for w in dict.fromkeys(output_words) if not _fits(w, profile)][:40]

    blocks = [
        "Slot grammar (crust - mantle - core - mantle - crust)",
        "=" * 52,
        "",
        table(
            [
                ["outer prefix (crust)", " ".join(profile.crust_prefix) or "-"],
                ["inner prefix (mantle)", " ".join(profile.mantle_prefix) or "-"],
                ["core", " ".join(profile.core) or "-"],
                ["inner suffix (mantle)", " ".join(profile.mantle_suffix) or "-"],
                ["outer suffix (crust)", " ".join(profile.crust_suffix) or "-"],
            ],
            ["slot", "characters that fill it"],
        ),
        "",
        "template: %s" % profile.template,
        "conforming words: %d of %d (%.1f%%)" % (profile.conforming, profile.total, profile.conformance * 100),
        "",
        "Verdict: " + profile.verdict(),
        "",
        "Words that do not fit the template (a sample): %s" % (" ".join(non_conforming) or "(none)"),
        "",
        "What this is testing\n"
        "--------------------\n"
        "Jorge Stolfi observed that Voynichese words behave less like strings over an alphabet and\n"
        "more like forms filled in: an optional outer layer, an optional inner layer, a core, and\n"
        "the same two layers again in reverse on the way out. Very few characters may appear in\n"
        "more than one slot, and their order is almost never violated.\n\n"
        "Natural languages do not do this. Latin has prefixes and suffixes, but its stems are not\n"
        "restricted to a handful of characters, and its words do not obey a strict positional\n"
        "template.\n\n"
        "So a high conformance in your output is not a success. It means the manuscript's own\n"
        "structure has survived your mapping intact - which it should, because a substitution\n"
        "cannot remove it. The number is here so you can state plainly that your reading has not\n"
        "made the text any more language-like in this respect.",
    ]
    save_text(ctx, "slot_grammar.txt", "\n".join(blocks) + "\n", "slot grammar conformance")

    payload = profile.to_dict()
    payload["verdict"] = profile.verdict()
    payload["sample_non_conforming"] = non_conforming
    return payload


def _fits(word: str, profile) -> bool:
    from ..analysis import _fits_template

    sets = (
        set(profile.crust_prefix),
        set(profile.mantle_prefix),
        set(profile.core),
        set(profile.mantle_suffix),
        set(profile.crust_suffix),
    )
    return _fits_template(word, sets)


PLUGIN = Plugin(
    name="slot_grammar",
    title="Slot grammar (Stolfi's crust-mantle-core)",
    stage="analyze",
    category="statistics",
    summary="Tests whether words still obey a rigid positional template.",
    help=(
        "Voynichese words look assembled rather than spelled. Jorge Stolfi's model describes them as\n"
        "an ordered sequence of slots - crust, mantle, core, mantle, crust - each filled from its own\n"
        "small set of characters, in that order and no other.\n\n"
        "This plugin infers the slots from your output and reports what share of words fit. A high\n"
        "figure means the template is intact. Since a substitution mapping only relabels characters,\n"
        "that is exactly what you should expect, and it is worth saying out loud: whatever else your\n"
        "reading achieves, it has not turned templated word-forms into ordinary morphology."
    ),
    defaults={"minShare": 0.02},
    settings_help={"minShare": "A character must fill a slot in at least this share of words to count."},
    run=run,
)
