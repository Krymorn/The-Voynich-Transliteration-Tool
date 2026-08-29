"""The run manifest: what produced this output, and can it be reproduced.

Every run writes ``manifest.json`` next to its results, recording the TVTT
version, the exact configuration, the checksum of the input transcription, the
checksum of the mapping, the random seed, the plugins that ran and how long
each took, and every file produced.

This is what makes a result citable.  "23% Latin coverage" is an anecdote;
"23% Latin coverage, ZL3b-n.txt sha256 bf5b6d4a..., mapping sha256 91c2..., seed
20260828, TVTT 2.0.0" is a claim somebody else can check.
"""

from __future__ import annotations

import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .util import stable_hash, write_json

MANIFEST_FILENAME = "manifest.json"


#: Selection settings that have a command line flag of their own. Anything not
#: listed here is reproduced with "--set", which reaches every setting.
_LIST_FLAGS = (("sections", "--section"), ("folios", "--folio"), ("scribes", "--scribe"))
_VALUE_FLAGS = (
    ("currier", "--currier", "any"),
    ("textClass", "--text-class", "all"),
    ("lines", "--lines", "all"),
    ("words", "--words", "all"),
)
_NO_FLAG_DEFAULTS = {
    "excludeFolios": [],
    "currierHands": [],
    "quires": [],
    "locusTypes": [],
    "locusKinds": [],
    "startLine": 1,
    "endLine": -1,
    "minWords": 0,
    "dropAmbiguousLines": False,
    "dropUnreadableLines": False,
}


def _selection_flags(selection: dict) -> list:
    """Turn a selection back into the arguments that would recreate it."""
    out = []
    for key, flag in _LIST_FLAGS:
        for value in selection.get(key) or ():
            out.append("%s %s" % (flag, value))
    for key, flag, default in _VALUE_FLAGS:
        value = selection.get(key, default)
        if value and value != default:
            out.append("%s %s" % (flag, value))
    for key, default in _NO_FLAG_DEFAULTS.items():
        value = selection.get(key, default)
        if value != default:
            rendered = ",".join(str(v) for v in value) if isinstance(value, list) else value
            out.append("--set selection.%s=%s" % (key, rendered))
    return out


def _tidy_path(value) -> str:
    """Record a path relative to the workspace, never an absolute one."""
    from .paths import display_path

    return display_path(value)


@dataclass
class RunManifest:
    """A record of one run, written alongside its outputs."""

    started: float = field(default_factory=time.time)
    version: str = __version__
    config: dict = field(default_factory=dict)
    config_sha256: str = ""
    transcription: str = ""
    transcription_file: str = ""
    transcription_sha256: str = ""
    mapping_file: str = ""
    mapping_name: str = ""
    mapping_sha256: str = ""
    selection: str = ""
    seed: int = 0
    plugins: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)
    outputs: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def add_output(self, path, description: str = "") -> None:
        self.outputs.append({"path": str(path), "description": description})

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def to_dict(self) -> dict:
        return {
            "tool": "The Voynich Transliteration Tool",
            "version": self.version,
            "run": {
                "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.started)),
                "duration_seconds": round(time.time() - self.started, 3),
                "python": sys.version.split()[0],
                "platform": platform.system(),
            },
            "inputs": {
                "transcription": self.transcription,
                "transcription_file": _tidy_path(self.transcription_file),
                "transcription_sha256": self.transcription_sha256,
                "mapping_file": _tidy_path(self.mapping_file),
                "mapping_name": self.mapping_name,
                "mapping_sha256": self.mapping_sha256,
                "selection": self.selection,
                "seed": self.seed,
            },
            "config_sha256": self.config_sha256,
            "config": self.config,
            "plugins": self.plugins,
            "timings_seconds": {k: round(v, 4) for k, v in sorted(self.timings.items())},
            "statistics": self.stats,
            "outputs": [
                {"path": _tidy_path(item["path"]), "description": item.get("description", "")} for item in self.outputs
            ],
            "warnings": self.warnings,
            "reproduce": self.command_hint(),
        }

    def command_hint(self) -> str:
        """A command line that actually reproduces this run.

        It has to carry the selection. Without it, a run over one section
        replays as a run over the whole manuscript, and a field called
        "reproduce" that does not reproduce is worse than no field at all.
        """
        parts = [
            "tvtt run",
            "--transcription %s" % (self.transcription or "zl"),
            "--mapping %s" % (_tidy_path(self.mapping_file) or "<mapping>"),
        ]
        parts.extend(_selection_flags(self.config.get("selection") or {}))
        parts.append("--seed %d" % self.seed)
        return " ".join(parts)

    def write(self, directory) -> Path:
        return write_json(Path(directory) / MANIFEST_FILENAME, self.to_dict())

    def signature(self) -> str:
        """A single hash identifying this run's inputs."""
        return stable_hash(
            [
                self.version,
                self.config_sha256,
                self.transcription_sha256,
                self.mapping_sha256,
                self.selection,
                self.seed,
            ]
        )
