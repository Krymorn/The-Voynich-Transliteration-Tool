"""Sukhotin's vowel detection and a direct alternation test."""

from __future__ import annotations

from ..analysis import vowel_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    profile = vowel_profile(output_words)

    score_rows = [[ch, score] for ch, score in sorted(profile.scores.items(), key=lambda kv: -kv[1])]

    blocks = [
        "Vowel detection",
        "=" * 15,
        "",
        "Sukhotin's algorithm classifies these as vowels:",
        "  " + (" ".join(profile.vowels) or "(none)"),
        "and these as consonants:",
        "  " + (" ".join(profile.consonants) or "(none)"),
        "",
        "Selection order and score",
        "-" * 25,
        table(score_rows, ["character", "adjacency score"]),
        "",
        "Alternation test",
        "-" * 16,
        table(
            [
                ["observed alternation rate", "%.4f" % profile.alternation_rate],
                ["expected if the classes were independent", "%.4f" % profile.expected_alternation],
                ["excess", "%+.4f" % (profile.alternation_rate - profile.expected_alternation)],
            ],
            ["measure", "value"],
        ),
        "",
        "Verdict: " + profile.verdict(),
        "",
        "How Sukhotin's algorithm works, and its limits\n"
        "----------------------------------------------\n"
        "The algorithm needs no knowledge of the language. It counts which characters sit next to\n"
        "which, then repeatedly declares the character with the highest remaining adjacency a\n"
        "vowel, subtracting that vowel's contribution from everything else. The idea is that vowels\n"
        "sit beside consonants and consonants mostly do not sit beside each other.\n\n"
        "It always returns an answer, even for text with no vowels in it, so the classification on\n"
        "its own proves nothing. The alternation test underneath is what makes it useful: it asks\n"
        "whether the two classes actually alternate more than two arbitrary groups of the same\n"
        "sizes would. In a real alphabetic language the excess is large. In Voynichese it is small,\n"
        "which is one more reason to doubt that the glyphs are letters in the ordinary sense.",
    ]
    save_text(ctx, "vowels.txt", "\n".join(blocks) + "\n", "vowel detection and alternation test")

    payload = profile.to_dict()
    payload["verdict"] = profile.verdict()
    payload["scores"] = profile.scores
    return payload


PLUGIN = Plugin(
    name="vowels",
    title="Vowel detection and alternation",
    stage="analyze",
    category="statistics",
    summary="Runs Sukhotin's vowel algorithm and tests whether the classes really alternate.",
    help=(
        "Sukhotin's algorithm guesses which characters are vowels using nothing but which\n"
        "characters sit next to which. It is a classic tool for unknown scripts and it always\n"
        "produces an answer - including for text that has no vowels at all.\n\n"
        "So this plugin does not stop at the classification. It also measures how often the text\n"
        "actually alternates between the two classes, and compares that with what two arbitrary\n"
        "groups of the same sizes would give. In an alphabetic language written with vowels, the\n"
        "excess is unmistakable. If your output shows no excess, then whatever Sukhotin has\n"
        "labelled 'vowels' are not behaving like vowels, and a reading that depends on them\n"
        "being vowels is in trouble."
    ),
    defaults={},
    run=run,
)
