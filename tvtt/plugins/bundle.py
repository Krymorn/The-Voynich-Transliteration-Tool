"""Gather every output into one single-file report."""

from __future__ import annotations

import json
from pathlib import Path

from ..reporting import Section, document, esc
from ..util import read_text, write_text
from . import Plugin, PluginContext

TEXT_SUFFIXES = {".txt", ".csv", ".json", ".md"}


def run(ctx: PluginContext) -> dict:
    directory = ctx.config.output_dir()
    skip = set(ctx.setting("skip", ["bundle.html"]))
    limit = ctx.setting("maxBytesPerFile", 300000)

    files = sorted(p for p in directory.iterdir() if p.is_file() and p.name not in skip)
    sections = [_summary(ctx, files)]

    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = read_text(path)
        except Exception as exc:
            ctx.log.warning("could not read %s: %s", path.name, exc)
            continue
        truncated = ""
        if len(content) > limit:
            content = content[:limit]
            truncated = "<p class='why'>Truncated at %d characters; the full file is %s.</p>" % (limit, esc(path.name))
        sections.append(
            Section(
                path.name,
                _describe(path.name),
                "<details open><summary>%s</summary><pre style='white-space:pre-wrap;font-size:12.5px;"
                "overflow-x:auto'>%s</pre></details>%s" % (esc(path.name), esc(content), truncated),
            )
        )

    images = [p for p in files if p.suffix.lower() in (".png", ".jpg", ".svg")]
    if images and ctx.setting("embedImages", True):
        sections.append(_images(images))

    page = document(
        "TVTT run report",
        "%s  |  %s  |  mapping: %s"
        % (
            ctx.corpus.title,
            ctx.corpus.selection.describe(),
            ctx.result.engine.mapping.meta.get("name", "unnamed"),
        ),
        sections,
    )
    path = write_text(ctx.output_path(ctx.setting("filename", "bundle.html")), page)
    ctx.record_output(path, "every output gathered into one file")
    return {"path": str(path), "files_included": len(sections) - 1}


def _summary(ctx: PluginContext, files: list) -> Section:
    manifest_path = ctx.config.output_dir() / "manifest.json"
    body = ""
    if manifest_path.exists():
        try:
            manifest = json.loads(read_text(manifest_path))
            inputs = manifest.get("inputs", {})
            rows = [
                ("transcription", inputs.get("transcription")),
                ("transcription checksum", (inputs.get("transcription_sha256") or "")[:24]),
                ("mapping", inputs.get("mapping_file")),
                ("mapping checksum", (inputs.get("mapping_sha256") or "")[:24]),
                ("selection", inputs.get("selection")),
                ("random seed", inputs.get("seed")),
                ("TVTT version", manifest.get("version")),
            ]
            body += "<table><tbody>%s</tbody></table>" % "".join(
                "<tr><td>%s</td><td>%s</td></tr>" % (esc(k), esc(v)) for k, v in rows
            )
        except Exception:
            pass
    listing = "".join("<li>%s</li>" % esc(p.name) for p in files)
    body += "<h3 style='font-size:14px;margin:16px 0 6px'>Files in this run</h3><ul>%s</ul>" % listing
    return Section("This run", "Everything needed to reproduce these results.", body)


def _images(images: list) -> Section:
    import base64

    blocks = []
    for path in images:
        try:
            payload = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        except OSError:
            continue
        mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
        blocks.append(
            "<figure style='margin:0 0 18px'><img style='max-width:100%%;border-radius:8px' "
            "src='data:%s;base64,%s' alt='%s'><figcaption class='why'>%s</figcaption></figure>"
            % (mime, payload, esc(path.name), esc(path.name))
        )
    return Section("Plots", "Images from this run, embedded so the file stays self-contained.", "".join(blocks))


def _describe(name: str) -> str:
    return {
        "entropy.txt": "Conditional character entropy.",
        "word_length.txt": "Word length distribution.",
        "vocabulary.txt": "Vocabulary growth and richness.",
        "zipf.txt": "Zipf's law fit.",
        "ngrams.txt": "Character transitions.",
        "positional.txt": "Where each character sits in a word.",
        "slot_grammar.txt": "Slot grammar conformance.",
        "affixes.txt": "Prefixes and suffixes by surprise.",
        "repeats.txt": "Repetition and clustering.",
        "line_effects.txt": "Line-position effects.",
        "vowels.txt": "Vowel detection and alternation.",
        "sections.txt": "Statistics per manuscript section.",
        "random_controls.txt": "Your score against random mappings.",
        "shuffles.txt": "Statistics under shuffled baselines.",
        "synthetic.txt": "Your text against a self-citation null model.",
        "language_controls.txt": "The same statistics on real languages.",
        "holdout.txt": "Scores on text the mapping was not tuned on.",
        "overfitting.txt": "Mapping complexity against the gain it buys.",
        "corpus_match.txt": "Dictionary matching.",
        "match_significance.txt": "Whether the hit rate beats chance.",
        "alignment.txt": "Where transcribers disagree.",
        "roundtrip.txt": "Whether the mapping is reversible.",
        "conflicts.txt": "Which rule wins where rules overlap.",
        "solver.txt": "Automated search results.",
        "manifest.json": "The full run record.",
    }.get(name, "")


PLUGIN = Plugin(
    name="bundle",
    title="Consolidated report",
    stage="report",
    category="output",
    summary="Gathers every file this run produced into one self-contained HTML document.",
    help=(
        "Collects every text, CSV and image output from the run into a single HTML file, with the\n"
        "run manifest at the top so the whole thing is reproducible from what is inside it.\n\n"
        "This is the file to send somebody, or to keep. Images are embedded as data URIs and text\n"
        "files are included verbatim, so nothing is lost if the output folder is deleted later.\n\n"
        "It runs last, after every other plugin has written its output. If you want a PDF, open the\n"
        "bundle in a browser and print to PDF - the layout is designed to survive that, and it\n"
        "avoids making a PDF library a dependency for everyone."
    ),
    defaults={"filename": "bundle.html", "skip": ["bundle.html"], "maxBytesPerFile": 300000, "embedImages": True},
    settings_help={
        "filename": "Name of the bundled file.",
        "skip": "Files to leave out.",
        "maxBytesPerFile": "Truncate any single file longer than this.",
        "embedImages": "Embed PNG and SVG plots as data URIs.",
    },
    run=run,
)
