"""Where in a word each character prefers to sit."""

from __future__ import annotations

from collections import Counter

from ..analysis import positional_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    buckets = ctx.setting("buckets", 5)
    profile = positional_profile(output_words, buckets)

    totals = {glyph: sum(dist) for glyph, dist in profile.glyphs.items()}
    minimum = ctx.setting("minCount", 20)
    rows = []
    for glyph in sorted(profile.glyphs, key=lambda g: -totals[g]):
        total = totals[glyph]
        if total < minimum:
            continue
        shares = ["%3.0f%%" % (100 * c / total) for c in profile.glyphs[glyph]]
        rows.append([glyph, total, "%.3f" % profile.entropy[glyph]] + shares)

    headers = ["char", "count", "entropy"] + [
        "%d%%-%d%%" % (i * 100 // buckets, (i + 1) * 100 // buckets) for i in range(buckets)
    ]

    first = Counter(w[0] for w in output_words if w)
    last = Counter(w[-1] for w in output_words if w)
    edge_rows = [
        [ch, first[ch], last[ch]] for ch in sorted(set(first) | set(last), key=lambda c: -(first[c] + last[c]))[:30]
    ]

    blocks = [
        "Positional behaviour of each character",
        "=" * 38,
        "",
        table(rows, headers),
        "",
        "Characters that almost always start a word: %s" % (" ".join(profile.initial_only) or "(none)"),
        "Characters that almost always end a word:   %s" % (" ".join(profile.final_only) or "(none)"),
        "",
        "Word-initial and word-final counts",
        "-" * 34,
        table(edge_rows, ["char", "starts words", "ends words"]),
        "",
        "How to read the entropy column\n"
        "------------------------------\n"
        "Positional entropy is measured over the %d position buckets. A character spread evenly\n"
        "across a word scores near %.2f bits; one that only ever appears in one place scores 0.\n"
        "Voynichese has an unusual number of characters near zero - q almost only starts words,\n"
        "n and m almost only end them. That rigidity is one of the strongest arguments against a\n"
        "simple alphabetic reading, and a mapping cannot remove it." % (buckets, __import__("math").log2(buckets)),
    ]
    save_text(ctx, "positional.txt", "\n".join(blocks) + "\n", "positional entropy per character")

    payload = profile.to_dict()
    payload["buckets"] = buckets
    payload["distribution"] = {g: profile.glyphs[g] for g in profile.glyphs if totals[g] >= minimum}
    payload["word_initial"] = dict(first.most_common(40))
    payload["word_final"] = dict(last.most_common(40))
    return payload


PLUGIN = Plugin(
    name="positional",
    title="Positional entropy per character",
    stage="analyze",
    category="statistics",
    summary="Measures where in a word each character prefers to appear.",
    help=(
        "Each word is divided into equal position buckets and every character's occurrences are\n"
        "counted per bucket. A character that appears anywhere has high positional entropy; one\n"
        "that only ever appears in a single place has close to zero.\n\n"
        "Voynichese is remarkable here. In EVA, q appears at the start of a word and essentially\n"
        "nowhere else; n and m appear at the end and essentially nowhere else; the gallows\n"
        "characters cluster in particular positions. Real alphabets have some of this - English q is\n"
        "nearly always followed by u - but nothing on this scale.\n\n"
        "Because a substitution mapping only renames characters, these numbers are a property of\n"
        "the manuscript that your output inherits. Use them to check the rigidity is still there,\n"
        "and to decide which glyphs deserve positional rules."
    ),
    defaults={"buckets": 5, "minCount": 20},
    settings_help={
        "buckets": "How many equal slices each word is divided into.",
        "minCount": "Ignore characters occurring fewer times than this.",
    },
    run=run,
)
