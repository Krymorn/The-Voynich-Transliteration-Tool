"""Line-position effects and the LAAFU test."""

from __future__ import annotations

from collections import Counter

from ..analysis import EVA_GALLOWS, line_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    line_words = ctx.result.line_words()
    flags = [locus.para_start for locus in ctx.corpus.loci]
    profile = line_profile(line_words, flags)

    first_words = Counter(line[0] for line in line_words if line)
    other_words = Counter(w for line in line_words for w in line[1:])
    last_words = Counter(line[-1] for line in line_words if line)

    position_rows = [
        [("%d" % (k + 1)) if k < 9 else "10+", "%.3f" % v] for k, v in sorted(profile.length_by_position.items())
    ]

    gallows_note = "gallows characters counted: %s (EVA). For other alphabets this row is not meaningful." % " ".join(
        sorted(EVA_GALLOWS)
    )

    blocks = [
        "Line-position effects",
        "=" * 21,
        "",
        "distinct words used as the first word of a line: %d" % profile.first_word_types,
        "distinct words used anywhere else:               %d" % profile.other_word_types,
        "share of first-word types that also occur elsewhere: %.1f%%" % (profile.first_word_overlap * 100),
        "LAAFU score (1 minus that overlap): %.3f" % profile.laafu_score,
        "",
        "Verdict: " + profile.verdict(),
        "",
        "Gallows characters per character of text",
        "-" * 40,
        table(
            [
                ["first line of a paragraph", "%.4f" % profile.gallows_first_line_rate],
                ["every other line", "%.4f" % profile.gallows_other_line_rate],
                [
                    "ratio",
                    "%.2f"
                    % (
                        profile.gallows_first_line_rate / profile.gallows_other_line_rate
                        if profile.gallows_other_line_rate
                        else 0.0
                    ),
                ],
            ],
            ["where", "rate"],
        ),
        gallows_note,
        "",
        "Mean word length by position in the line",
        "-" * 40,
        table(position_rows, ["position", "mean length"]),
        "",
        "Commonest first word of a line",
        "-" * 30,
        table(first_words.most_common(20), ["word", "count"]),
        "",
        "Commonest last word of a line",
        "-" * 29,
        table(last_words.most_common(20), ["word", "count"]),
        "",
        "Commonest word anywhere else",
        "-" * 28,
        table(other_words.most_common(20), ["word", "count"]),
        "",
        "The line as a functional unit\n"
        "-----------------------------\n"
        "In ordinary writing, where a word falls on the page tells you nothing about which word it\n"
        "is: a line break is a fact about the parchment, not about the language. In the Voynich\n"
        "manuscript it is not so. The first word of a line is drawn from a noticeably different set\n"
        "than the rest, first lines of paragraphs carry more gallows characters, and word length\n"
        "varies systematically across the line.\n\n"
        "This is called the LAAFU effect - line as a functional unit - and it is a serious problem\n"
        "for any reading of the text as ordinary language. The score above is the share of\n"
        "line-initial word types that never appear elsewhere: the higher it is, the more the line\n"
        "boundary behaves like part of the writing system.\n\n"
        "To study the effect directly, set selection.words to 'first' in config.json and rerun;\n"
        "every analysis will then see only the first word of each line.",
    ]
    save_text(ctx, "line_effects.txt", "\n".join(blocks) + "\n", "line-position effects and the LAAFU test")

    payload = profile.to_dict()
    payload["verdict"] = profile.verdict()
    payload["first_words"] = dict(first_words.most_common(30))
    payload["last_words"] = dict(last_words.most_common(30))
    return payload


PLUGIN = Plugin(
    name="line_effects",
    title="Line-position effects (LAAFU)",
    stage="analyze",
    category="statistics",
    summary="Tests whether the line, not the sentence, is the unit of the writing.",
    help=(
        "Voynichese behaves differently at the start of a line than in the middle of one. The first\n"
        "word comes from a restricted vocabulary, first lines of paragraphs are richer in gallows\n"
        "characters, and word length changes systematically along the line.\n\n"
        "That pattern - the 'line as a functional unit', or LAAFU - is very hard to reconcile with\n"
        "the text being ordinary prose that happens to be laid out in lines. Any decipherment has to\n"
        "account for it, and any mapping inherits it unchanged.\n\n"
        "This plugin measures the effect on your output. To isolate it further, set\n"
        "selection.words to 'first' or 'not_first' in config.json and rerun the whole analysis on\n"
        "just those words."
    ),
    defaults={},
    run=run,
)
