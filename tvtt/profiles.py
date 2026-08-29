"""Mapping profiles: named presets, version history and shareable packs.

A decipherment attempt is not one mapping; it is dozens of variations on an
idea.  This module keeps them organised.

**Profiles** are named mappings in ``mappings/``.  ``tvtt mapping use herbal_b``
switches config.json to that file; ``tvtt mapping list`` shows them all with
their scores if any have been recorded.

**Versions** are automatic.  Every time a mapping is saved through TVTT the
previous contents are copied into ``mappings/.history/<name>/`` with a
timestamp and a note, so you can look at what a hypothesis was three ideas ago
and go back to it.

**Packs** are single ``.tvttpack.json`` files bundling one or more mappings
with their metadata and recorded scores.  That is the unit you share: it is one
file, it is plain JSON, and it carries enough context for somebody else to
reproduce your numbers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .errors import MappingError
from .mapping import Mapping, mapping_diff
from .paths import display_path, ws
from .util import read_json, write_json

MAPPINGS_DIR = "mappings"
HISTORY_DIR = ".history"
PACK_SUFFIX = ".tvttpack.json"
PACK_FORMAT = 1


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------


@dataclass
class Profile:
    """One named mapping on disk."""

    name: str
    path: Path
    meta: dict = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.meta.get("name", self.name)

    @property
    def language(self) -> str:
        return self.meta.get("language", "")

    @property
    def score(self):
        return self.meta.get("score")

    def load(self) -> Mapping:
        return Mapping.load(self.path)

    def row(self) -> list:
        return [
            self.name,
            self.meta.get("alphabet", ""),
            self.language,
            self.meta.get("version", ""),
            "" if self.score is None else round(float(self.score), 4),
            self.meta.get("notes", "")[:60],
        ]


def profiles_dir() -> Path:
    path = ws(MAPPINGS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_profiles() -> list:
    """Every mapping in ``mappings/``.

    Both formats count: the JSON files TVTT writes, and the plain ``.txt``
    lists that versions before 1.8 used.
    """
    out = []
    paths = sorted(profiles_dir().glob("*.json")) + sorted(profiles_dir().glob("*.txt"))
    for path in paths:
        if path.name.startswith("."):
            continue
        meta = {}
        if path.suffix == ".json":
            try:
                data = read_json(path)
                meta = data.get("meta", {}) if isinstance(data, dict) else {}
            except Exception:
                meta = {"notes": "could not be read"}
        else:
            meta = {"notes": "version 1 mapping list"}
        out.append(Profile(name=path.stem, path=path, meta=meta))
    return out


def find_profile(name: str) -> Profile:
    candidates = {p.name: p for p in list_profiles()}
    if name in candidates:
        return candidates[name]
    path = Path(name)
    if path.exists():
        data = read_json(path)
        return Profile(name=path.stem, path=path, meta=data.get("meta", {}) if isinstance(data, dict) else {})
    raise MappingError(
        "no mapping profile called %r" % name,
        hint="Available: " + (", ".join(sorted(candidates)) or "(none yet - run 'tvtt mapping init')"),
    )


# --------------------------------------------------------------------------
# Versioning
# --------------------------------------------------------------------------


def history_dir(name: str) -> Path:
    path = profiles_dir() / HISTORY_DIR / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot(path, note: str = "") -> Path:
    """Copy the current contents of a mapping into its history folder.

    Two saves in the same second must not land on the same file, or the
    earlier version is silently lost; a suffix is added until the name is free.
    """
    source = Path(path)
    if not source.exists():
        return source
    name = source.stem
    stamp = time.strftime("%Y%m%d-%H%M%S")
    directory = history_dir(name)
    target = directory / ("%s.json" % stamp)
    counter = 1
    while target.exists():
        target = directory / ("%s-%d.json" % (stamp, counter))
        counter += 1
    target.write_bytes(source.read_bytes())
    log = history_dir(name) / "changelog.md"
    entry = "- %s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), note or "saved")
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(entry)
    return target


def history(name: str) -> list:
    """Every saved version of a mapping, newest first."""
    directory = profiles_dir() / HISTORY_DIR / name
    if not directory.is_dir():
        return []
    versions = sorted(directory.glob("*.json"), reverse=True)
    notes = {}
    log = directory / "changelog.md"
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.startswith("- "):
                parts = line[2:].split("  ", 1)
                if len(parts) == 2:
                    notes[parts[0].strip()] = parts[1].strip()
    rows = []
    for path in versions:
        stamp = path.stem
        readable = "%s-%s-%s %s:%s:%s" % (stamp[0:4], stamp[4:6], stamp[6:8], stamp[9:11], stamp[11:13], stamp[13:15])
        rows.append({"version": stamp, "when": readable, "note": notes.get(readable, ""), "path": str(path)})
    return rows


def restore(name: str, version: str) -> Path:
    """Bring an older version of a mapping back as the current one."""
    directory = profiles_dir() / HISTORY_DIR / name
    source = directory / ("%s.json" % version)
    if not source.exists():
        raise MappingError(
            "no version %r of mapping %r" % (version, name),
            hint="Run 'tvtt mapping history %s' to see the versions available." % name,
        )
    target = profiles_dir() / ("%s.json" % name)
    # Read the old version before snapshotting: the snapshot lands in the same
    # folder, and must not be able to overwrite the file being restored.
    payload = source.read_bytes()
    snapshot(target, note="before restoring %s" % version)
    target.write_bytes(payload)
    return target


def save_mapping(mapping: Mapping, name: str, note: str = "", meta: dict = None) -> Path:
    """Save a mapping as a named profile, keeping the previous version."""
    target = profiles_dir() / ("%s.json" % name)
    if target.exists():
        snapshot(target, note=note)
        try:
            previous = Mapping.load(target)
            changes = mapping_diff(previous, mapping)
            note = note or ("%d rule(s) changed" % len(changes))
        except Exception:
            pass
    payload = dict(mapping.meta)
    payload.update(meta or {})
    payload.setdefault("name", name)
    payload["saved"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    payload["tvtt_version"] = __version__
    mapping.meta = payload
    return mapping.save(target)


# --------------------------------------------------------------------------
# Packs
# --------------------------------------------------------------------------


def export_pack(names: list, path, title: str = "", author: str = "", notes: str = "") -> Path:
    """Bundle one or more mappings into a single shareable file."""
    entries = []
    for name in names:
        profile = find_profile(name)
        mapping = profile.load()
        entries.append(
            {
                "name": profile.name,
                "meta": mapping.meta,
                "rules": mapping.to_dict(structured=True)["rules"],
                "signature": mapping.signature(),
            }
        )
    payload = {
        "format": PACK_FORMAT,
        "tool": "The Voynich Transliteration Tool",
        "tvtt_version": __version__,
        "exported": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "title": title or ("%d mapping(s)" % len(entries)),
        "author": author,
        "notes": notes,
        "mappings": entries,
    }
    target = Path(path)
    if not target.name.endswith(PACK_SUFFIX):
        target = target.with_name(target.stem + PACK_SUFFIX)
    return write_json(target, payload)


def import_pack(path, prefix: str = "", overwrite: bool = False) -> list:
    """Unpack a shared mapping pack into ``mappings/``."""
    source = Path(path)
    if not source.exists():
        raise MappingError(
            "no such file: %s" % display_path(source),
            hint="Check the path to the .tvttpack.json file you were sent.",
        )
    try:
        payload = read_json(source)
    except json.JSONDecodeError as exc:
        raise MappingError(
            "%s is not valid JSON (line %d, column %d)" % (display_path(source), exc.lineno, exc.colno),
            hint="Packs are produced by 'tvtt mapping export-pack'.",
        ) from exc
    if not isinstance(payload, dict):
        raise MappingError(
            "%s is not a TVTT mapping pack" % display_path(source),
            hint="Packs are produced by 'tvtt mapping export-pack'.",
        )
    if payload.get("format") != PACK_FORMAT:
        raise MappingError(
            "%s is not a TVTT mapping pack (format %r)" % (display_path(path), payload.get("format")),
            hint="Packs are produced by 'tvtt mapping export-pack'.",
        )
    written = []
    for entry in payload.get("mappings", []):
        name = (prefix + entry["name"]) if prefix else entry["name"]
        target = profiles_dir() / ("%s.json" % name)
        if target.exists() and not overwrite:
            raise MappingError(
                "mapping %r already exists" % name,
                hint="Pass --overwrite, or --prefix to import under different names.",
            )
        mapping = Mapping.from_dict({"meta": entry.get("meta", {}), "rules": entry.get("rules", {})})
        mapping.meta.setdefault("imported_from", str(path))
        written.append(save_mapping(mapping, name, note="imported from %s" % Path(path).name))
    return written


def record_score(name: str, metric: str, value: float, details: dict = None) -> Path:
    """Store a score in a mapping's metadata so profiles can be ranked."""
    profile = find_profile(name)
    mapping = profile.load()
    scores = mapping.meta.setdefault("scores", {})
    scores[metric] = {"value": round(float(value), 6), "when": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if details:
        scores[metric]["details"] = details
    mapping.meta["score"] = round(float(value), 6)
    mapping.meta["score_metric"] = metric
    return mapping.save(profile.path)


# --------------------------------------------------------------------------
# The standardised results format
# --------------------------------------------------------------------------

RESULT_FORMAT = 1


def result_record(
    mapping_name: str,
    mapping_signature: str,
    transcription: str,
    transcription_sha256: str,
    selection: str,
    metrics: dict,
    author: str = "",
    notes: str = "",
) -> dict:
    """One row of the shared results format.

    Everybody's mapping is scored differently unless the score carries its own
    context.  A result record pins down which transcription, which slice of it,
    which mapping and which numbers, so two people's claims can be put side by
    side and compared honestly.
    """
    return {
        "format": RESULT_FORMAT,
        "tool": "The Voynich Transliteration Tool",
        "tvtt_version": __version__,
        "recorded": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mapping": mapping_name,
        "mapping_signature": mapping_signature,
        "transcription": transcription,
        "transcription_sha256": transcription_sha256,
        "selection": selection,
        "author": author,
        "notes": notes,
        "metrics": metrics,
    }


def append_result(record: dict, path=None) -> Path:
    """Append a result record to the workspace results file."""
    target = Path(path) if path else ws("results.json")
    existing = []
    if target.exists():
        try:
            payload = read_json(target)
            existing = payload.get("results", []) if isinstance(payload, dict) else []
        except Exception:
            existing = []
    existing.append(record)
    return write_json(target, {"format": RESULT_FORMAT, "results": existing})


def rank_results(path=None, metric: str = "") -> list:
    """Sort recorded results by a metric, for a leaderboard."""
    target = Path(path) if path else ws("results.json")
    if not target.exists():
        return []
    payload = read_json(target)
    rows = payload.get("results", []) if isinstance(payload, dict) else []

    def value(row):
        metrics = row.get("metrics", {})
        if metric:
            return metrics.get(metric, 0) or 0
        for key in ("weighted_coverage", "coverage", "score"):
            if key in metrics:
                return metrics[key] or 0
        return 0

    return sorted(rows, key=value, reverse=True)


GALLERY_NOTE = (
    "To add a mapping to the community gallery, export it with\n"
    "    tvtt mapping export-pack <name> --out my_idea.tvttpack.json\n"
    "and send the file to cmarbel in a private message on voynich.ninja, together with\n"
    "the results.json produced by your run so the numbers can be reproduced."
)
