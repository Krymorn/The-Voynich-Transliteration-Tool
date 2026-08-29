"""Conditional character entropy: h0, h1, h2 and h3."""

from __future__ import annotations

from ..analysis import ENTROPY_REFERENCES, conditional_entropy, entropy_profile
from ..util import table
from . import Plugin, PluginContext
from ._common import save_text, words


def run(ctx: PluginContext) -> dict:
    output_words = words(ctx)
    profile = entropy_profile(output_words)

    with_spaces = 0.0
    if ctx.setting("includeSpaces"):
        joined = " ".join(output_words)
        with_spaces = conditional_entropy(joined, 1)

    rows = [
        ["h0  alphabet size", "%.3f" % profile.h0, "log2 of the number of distinct characters"],
        ["h1  character entropy", "%.3f" % profile.h1, "how unpredictable a character is on its own"],
        ["h2  conditional entropy", "%.3f" % profile.h2, "how unpredictable a character is given the one before"],
        ["h3  second-order", "%.3f" % profile.h3, "given the two before"],
    ]
    if with_spaces:
        rows.append(["h2 including spaces", "%.3f" % with_spaces, "word boundaries counted as a character"])

    reference_rows = [
        [name, "%.2f" % values["h1"], "%.2f" % values["h2"]] for name, values in ENTROPY_REFERENCES.items()
    ]

    blocks = [
        "Character entropy of your transliteration",
        "=" * 41,
        "",
        table(rows, ["measure", "bits", "meaning"]),
        "",
        "Published reference values",
        "-" * 26,
        table(reference_rows, ["text", "h1", "h2"]),
        "",
        _interpretation(profile.h2),
        "",
        "%d characters over an alphabet of %d." % (profile.characters, profile.alphabet_size),
    ]
    save_text(ctx, "entropy.txt", "\n".join(blocks) + "\n", "conditional character entropy")

    payload = profile.to_dict()
    payload["h2_with_spaces"] = round(with_spaces, 4) if with_spaces else None
    payload["interpretation"] = _interpretation(profile.h2)
    return payload


def _interpretation(h2: float) -> str:
    if h2 < 2.6:
        return (
            "h2 = %.2f bits. This is in the manuscript's own range and far below any European\n"
            "language, which sit near 3.0 to 3.5. That is expected: a one-for-one substitution\n"
            "cannot change conditional entropy much, so a mapping should land here. If a\n"
            "substitution mapping ever produced a language-like h2, something in the pipeline\n"
            "would be adding information that was not in the manuscript." % h2
        )
    if h2 < 3.0:
        return (
            "h2 = %.2f bits. Higher than the manuscript's usual 2.1 to 2.4. Something in your\n"
            "settings is adding variety - expanding glyphs into several letters, or a mapping\n"
            "that splits one glyph across different positions." % h2
        )
    return (
        "h2 = %.2f bits, in the range of a natural language. For a plain substitution that is a\n"
        "red flag rather than a success: check whether glyphs are being expanded into several\n"
        "letters, or whether the selection is so small that the estimate is unreliable." % h2
    )


PLUGIN = Plugin(
    name="entropy",
    title="Conditional entropy (h1, h2)",
    stage="analyze",
    category="statistics",
    summary="Character entropy at orders 0 to 3, with published reference values.",
    help=(
        "The single most cited Voynich statistic, and the one most decipherment claims fail.\n\n"
        "h1 is how unpredictable a character is on its own; h2 is how unpredictable it is once you\n"
        "know the character before it. The manuscript's h2 sits around 2.0 to 2.4 bits depending on\n"
        "the transcription alphabet. Latin, Italian, English and Hebrew all sit near 3.0 to 3.5.\n"
        "That gap is the central fact about Voynichese: it is far more predictable than any European\n"
        "language.\n\n"
        "Read this plugin as a *sanity check on your pipeline*, not as a target. A substitution\n"
        "mapping is a relabelling, and relabelling cannot change entropy much. If your output's h2\n"
        "suddenly looks like Latin, the extra bits came from your mapping expanding glyphs, not from\n"
        "the manuscript, and any decipherment built on it is partly your own writing."
    ),
    defaults={"includeSpaces": True},
    settings_help={"includeSpaces": "Also report h2 with word boundaries counted as a character."},
    enabled_by_default=True,
    run=run,
)
