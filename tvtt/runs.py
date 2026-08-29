"""Numbered output folders, so a run never overwrites the one before it.

Results go into ``output/run-001``, ``output/run-002`` and so on. The folder
name stays short; what the run actually did is written inside it, in
``info.txt``::

    output/
      run-001/
        info.txt
        output.txt
        report.html
        ...
      run-002/
      latest.txt

Numbering continues from the highest folder present, so deleting one does not
cause the next run to reuse its name.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .logging_util import get_logger
from .manifest import MANIFEST_FILENAME
from .util import read_json, write_text

_log = get_logger("runs")

LATEST_POINTER = "latest.txt"
INFO_FILENAME = "info.txt"


def _mapping_line(inputs: dict) -> str:
    name = (inputs.get("mapping_name") or "").strip()
    filename = Path(inputs.get("mapping_file", "")).name
    if not name:
        return filename or "(none)"
    if name.startswith("identity (no mapping file"):
        return "none yet, so every glyph maps to itself"
    stem = Path(filename).stem
    return name if (not filename or name == stem) else "%s  [%s]" % (name, filename)


def write_info(run_dir: Path, manifest, outputs: list) -> Path:
    """Write the human-readable summary of a run."""
    inputs = manifest.to_dict()["inputs"]
    lines = [
        "This folder holds the results of one TVTT run.",
        "",
        "when            %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(manifest.started)),
        "transcription   %s (%s)" % (inputs["transcription"], Path(inputs["transcription_file"]).name),
        "mapping         %s" % _mapping_line(inputs),
        "part of the MS  %s" % (inputs["selection"] or "whole manuscript"),
        "random seed     %s" % inputs["seed"],
        "TVTT version    %s" % manifest.version,
        "",
    ]

    stats = manifest.stats or {}
    if stats:
        lines.append("What was read")
        lines.append("-------------")
        for key, label in (
            ("lines", "lines"),
            ("words", "words"),
            ("word_types", "distinct words"),
            ("h1", "character entropy h1"),
            ("h2", "conditional entropy h2"),
            ("dictionary_coverage", "dictionary coverage"),
            ("stopword_coverage", "stopword alignment"),
            ("random_control_z", "z-score against random mappings"),
        ):
            if stats.get(key) is not None:
                lines.append("  %-32s %s" % (label, stats[key]))
        lines.append("")

    if outputs:
        lines.append("Files")
        lines.append("-----")
        for item in outputs:
            name = Path(item["path"]).name
            lines.append("  %-28s %s" % (name, item.get("description", "")))
        lines.append("")

    if manifest.warnings:
        lines.append("Warnings")
        lines.append("--------")
        for warning in manifest.warnings:
            lines.append("  - %s" % warning)
        lines.append("")

    lines.append("manifest.json in this folder has the full record, including the")
    lines.append("checksums needed to reproduce these results exactly.")
    return write_text(run_dir / INFO_FILENAME, "\n".join(lines) + "\n")


def record_latest(root: Path, run_dir: Path) -> Path:
    """Write the pointer naming the most recent run."""
    try:
        relative = run_dir.relative_to(root)
    except ValueError:
        relative = run_dir
    return write_text(root / LATEST_POINTER, "%s\n" % relative.as_posix())


def latest_run(root: Path):
    """The most recent run folder, from the pointer or the folder times."""
    pointer = root / LATEST_POINTER
    if pointer.exists():
        name = pointer.read_text(encoding="utf-8").strip()
        candidate = root / name
        if candidate.is_dir():
            return candidate
    runs = list_run_dirs(root)
    return runs[-1] if runs else None


def list_run_dirs(root: Path) -> list:
    """Every run folder, oldest first."""
    if not root.is_dir():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    return sorted(dirs, key=lambda p: (p.stat().st_mtime, p.name))


def describe_runs(root: Path) -> list:
    """Rows for ``tvtt runs``, read back from each run's manifest."""
    rows = []
    for path in reversed(list_run_dirs(root)):
        manifest = path / MANIFEST_FILENAME
        started = mapping = selection = ""
        words = warnings = ""
        if manifest.exists():
            try:
                data = read_json(manifest)
                started = data.get("run", {}).get("started", "").replace("T", " ")
                inputs = data.get("inputs", {})
                mapping = _mapping_line(inputs)
                selection = inputs.get("selection", "")
                stats = data.get("statistics", {})
                words = stats.get("words", "")
                count = len(data.get("warnings", []))
                warnings = str(count) if count else ""
            except Exception:
                started = "(unreadable manifest)"
        rows.append([path.name, started, mapping, selection, words, warnings])
    return rows


def prune(root: Path, keep: int) -> list:
    """Delete the oldest run folders beyond ``keep``. ``keep=0`` keeps all."""
    if keep <= 0:
        return []
    runs = list_run_dirs(root)
    doomed = runs[: max(0, len(runs) - keep)]
    removed = []
    for path in doomed:
        try:
            shutil.rmtree(path)
            removed.append(path.name)
            _log.info("removed old run folder %s", path.name)
        except OSError as exc:  # pragma: no cover - permissions only
            _log.warning("could not remove %s: %s", path, exc)
    return removed
