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
        return "tvtt run --transcription %s --mapping %s --seed %d" % (
            self.transcription or "zl",
            _tidy_path(self.mapping_file) or "<mapping>",
            self.seed,
        )

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
