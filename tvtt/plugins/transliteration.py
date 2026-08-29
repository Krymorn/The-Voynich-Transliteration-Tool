"""Write the transliterated text out."""

from __future__ import annotations

from ..ivtff import high_ascii_label
from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    result = ctx.result
    lines = result.lines

    if ctx.setting("includeLocus"):
        width = ctx.setting("locusWidth", 18)
        body = "\n".join("%-*s %s" % (width, locus.locus_id, text) for locus, text in zip(ctx.corpus.loci, lines))
    else:
        body = "\n".join(lines)
    save_text(ctx, ctx.setting("filename", "output.txt"), body + "\n", "the transliterated text")

    if ctx.setting("writeSource"):
        source = "\n".join(_render_source(locus.text, result.word_separator) for locus in ctx.corpus.loci)
        save_text(ctx, "source.txt", source + "\n", "the selected source text, ambiguity already resolved")

    if ctx.setting("writeWordList"):
        counts = result.word_counts()
        listing = "\n".join("%s\t%d" % (word, count) for word, count in counts.most_common())
        save_text(ctx, "output_words.txt", listing + "\n", "every output word type with its count")

    return {
        "lines": len(lines),
        "words": len(result.words()),
        "word_types": len(result.word_counts()),
        "characters": sum(len(w) for w in result.words()),
    }


def _render_source(text: str, separator: str) -> str:
    out = []
    for ch in text:
        if ch in ".,":
            out.append(separator)
        else:
            out.append(high_ascii_label(ch))
    return "".join(out)


PLUGIN = Plugin(
    name="transliteration",
    title="Transliterated text",
    stage="report",
    category="output",
    summary="Writes the transliterated text to output.txt.",
    help=(
        "The basic output: your mapping applied to the selected part of the manuscript, one\n"
        "manuscript line per output line.\n\n"
        "Turn on 'includeLocus' to prefix each line with its IVTFF locus identifier, such as\n"
        "<f1r.3,+P0>, so you can find any line in the original file or on the page itself.\n"
        "Turn on 'writeSource' to get the matching source text with ambiguity already resolved,\n"
        "which is what the analyses actually saw."
    ),
    defaults={
        "filename": "output.txt",
        "includeLocus": False,
        "locusWidth": 18,
        "writeSource": False,
        "writeWordList": True,
    },
    settings_help={
        "filename": "Name of the output file inside the output directory.",
        "includeLocus": "Prefix every line with its <folio.line,type> identifier.",
        "locusWidth": "Column width for the locus prefix.",
        "writeSource": "Also write the source text the mapping was applied to.",
        "writeWordList": "Also write every output word type with its frequency.",
    },
    enabled_by_default=True,
    run=run,
)
