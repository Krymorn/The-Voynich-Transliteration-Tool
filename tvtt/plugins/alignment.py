"""Line up two transcriptions and report where the transcribers disagree."""

from __future__ import annotations

import difflib
from collections import Counter

from ..corpus import TRANSCRIPTION_KEYS, load_corpus
from ..reporting import write_csv
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, track


def run(ctx: PluginContext) -> dict:
    other_key = ctx.setting("against", "v101")
    if other_key not in TRANSCRIPTION_KEYS:
        ctx.log.warning("unknown transcription %r; using v101", other_key)
        other_key = "v101"

    other = load_corpus(other_key, ctx.config.parse_options())
    mine = ctx.corpus

    mine_by_locus = {(locus.key, locus.number): locus for locus in mine.loci}
    other_by_locus = {(locus.key, locus.number): locus for locus in other.loci}
    shared = [k for k in mine_by_locus if k in other_by_locus]
    shared.sort(key=lambda k: mine_by_locus[k].index)

    only_mine = len(mine_by_locus) - len(shared)
    only_other = len(other_by_locus) - len(shared)

    agree_lines = 0
    agree_words = 0
    total_words = 0
    disagreements = []
    pair_counts: Counter = Counter()

    for key in track(ctx, shared, "aligning loci"):
        a_words = mine_by_locus[key].words()
        b_words = other_by_locus[key].words()
        if len(a_words) == len(b_words):
            agree_lines += 1
        matcher = difflib.SequenceMatcher(a=a_words, b=b_words, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            span = max(i2 - i1, j2 - j1)
            total_words += span
            if tag == "equal":
                agree_words += i2 - i1
                continue
            left = " ".join(a_words[i1:i2]) or "(nothing)"
            right = " ".join(b_words[j1:j2]) or "(nothing)"
            pair_counts[(left, right)] += 1
            if len(disagreements) < ctx.setting("maxRows", 400):
                disagreements.append([mine_by_locus[key].locus_id, tag, left, right])

    word_agreement = agree_words / total_words if total_words else 0.0

    blocks = [
        "Cross-transcription alignment",
        "=" * 29,
        "",
        "comparing %s (%s) with %s (%s)" % (mine.title, mine.alphabet, other.title, other.alphabet),
        "",
        table(
            [
                ["loci in both", len(shared)],
                ["loci only in %s" % mine.key, only_mine],
                ["loci only in %s" % other.key, only_other],
                ["loci with the same number of words", agree_lines],
                ["word positions compared", total_words],
                ["word positions where they agree", agree_words],
                ["word agreement", "%.2f%%" % (word_agreement * 100)],
            ],
            ["measure", "value"],
        ),
        "",
        "Most frequent disagreements",
        "-" * 27,
        table(
            [[left, right, count] for (left, right), count in pair_counts.most_common(40)],
            ["%s reads" % mine.key, "%s reads" % other.key, "times"],
        ),
        "",
        "Disagreements by locus (first %d)" % len(disagreements),
        "-" * 40,
        table(disagreements, ["locus", "kind", mine.key, other.key]),
        "",
        "Why this matters\n"
        "----------------\n"
        "Every transliteration is an interpretation. Two experienced transcribers looking at the\n"
        "same stroke can disagree about whether it is one glyph or two, and the alphabets differ in\n"
        "how much detail they record - v101 distinguishes far more shapes than EVA does.\n\n"
        "The places where they disagree are exactly the places where a mapping's behaviour is least\n"
        "trustworthy, because you are reading a decision rather than a fact. If a striking result\n"
        "rests on words in this list, it rests on one transcriber's judgement.\n\n"
        "Note that comparing across alphabets compares different notations, so the word agreement\n"
        "figure is only meaningful between transcriptions using the same alphabet. Across alphabets,\n"
        "read the alignment for where the *segmentation* differs, not the spelling.",
    ]
    save_text(ctx, "alignment.txt", "\n".join(blocks) + "\n", "where two transcriptions disagree")

    if ctx.setting("writeCsv", True):
        rows = [[left, right, count] for (left, right), count in pair_counts.most_common()]
        path = write_csv(ctx.output_path("alignment.csv"), rows, [mine.key, other.key, "count"])
        ctx.record_output(path, "every transcriber disagreement with its frequency")

    return {
        "against": other_key,
        "alphabets": [mine.alphabet, other.alphabet],
        "shared_loci": len(shared),
        "only_in_primary": only_mine,
        "only_in_other": only_other,
        "word_agreement": round(word_agreement, 5),
        "top_disagreements": [[locus, r, c] for (locus, r), c in pair_counts.most_common(40)],
    }


PLUGIN = Plugin(
    name="alignment",
    title="Cross-transcription alignment",
    stage="analyze",
    category="validation",
    summary="Lines up two transcriptions locus by locus and reports where they differ.",
    help=(
        "Reads a second transliteration and aligns it against yours, one locus at a time, then one\n"
        "word at a time within each locus.\n\n"
        "The output is a word-agreement figure and a ranked list of the disagreements: which\n"
        "reading each transcriber gave, and how often. Comparing EVA against v101 mostly shows\n"
        "where the alphabets record different amounts of detail; comparing two EVA transcriptions -\n"
        "ZL against Takahashi, say - shows genuine disagreement about what is on the page.\n\n"
        "Use it to find out whether a result depends on a contested reading. Available\n"
        "transcriptions: " + ", ".join(TRANSCRIPTION_KEYS) + "."
    ),
    defaults={"against": "v101", "maxRows": 400, "writeCsv": True},
    settings_help={
        "against": "Which transcription to compare with.",
        "maxRows": "How many individual disagreements to list.",
        "writeCsv": "Write alignment.csv with every disagreement.",
    },
    heavy=True,
    run=run,
)
