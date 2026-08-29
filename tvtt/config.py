"""Reading, validating and merging ``config.json``.

``config.json`` holds the settings that describe *what* to run: which
transcription, which mapping, which part of the manuscript, where output goes.
``plugins.json`` (see :mod:`tvtt.plugins`) holds *which optional features* run.
Keeping them apart means you can share a plugin set-up without also sharing
your file paths.

Every key has a default, so a config file only has to mention what it changes.
Unknown keys are reported by name with a "did you mean" suggestion rather than
silently ignored, because a typo in a settings file is otherwise invisible.
"""

from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigError
from .ivtff import ParseOptions
from .mapping import DEFAULT_PRECEDENCE, Markers
from .paths import data_file, display_path, ws
from .schema import validate
from .util import read_json, read_text, stable_hash, write_json

CONFIG_FILENAME = "config.json"

DEFAULT_CONFIG: dict = {
    "transcription": "zl",
    "mapping": {
        "file": "mappings/identity_eva.json",
        "precedence": list(DEFAULT_PRECEDENCE),
        "unmapped": "keep",
        "placeholder": "?",
        "markers": {
            "startOfWord": "@",
            "endOfWord": "/",
            "occurrence": ["'", '"', ":", ";"],
        },
    },
    "ambiguity": {
        "alternates": "first",
        "maxVariants": 16,
        "unreadable": "keep",
        "unreadableChar": "?",
        "uncertainSpace": "keep",
        "ligatures": "keep",
        "highAscii": "unicode",
        "stripFillers": True,
    },
    "selection": {
        "sections": [],
        "folios": [],
        "excludeFolios": [],
        "currier": "any",
        "scribes": [],
        "currierHands": [],
        "quires": [],
        "locusTypes": [],
        "locusKinds": [],
        "textClass": "all",
        "lines": "all",
        "words": "all",
        "startLine": 1,
        "endLine": -1,
        "minWords": 0,
        "dropAmbiguousLines": False,
        "dropUnreadableLines": False,
    },
    "output": {
        "directory": "output",
        "separateRunFolders": True,
        "runName": "",
        "keepRuns": 0,
        "wordSeparator": " ",
        "uncertainWordSeparator": " ",
        "writeTransliteration": True,
        "writeManifest": True,
        "recordResult": True,
        "encoding": "utf-8",
    },
    "performance": {
        "cache": True,
        "workers": 0,
        "progress": True,
    },
    "logging": {
        "level": "info",
        "format": "text",
    },
    "random": {
        "seed": 20260828,
    },
    "network": {
        "offline": True,
        "userAgent": "TVTT/2.0 (+https://github.com/) transliteration workbench",
        "timeoutSeconds": 60,
    },
    "reference": {
        "language": "latin",
        "folder": "reference_texts",
    },
}


# --------------------------------------------------------------------------
# Config object
# --------------------------------------------------------------------------


@dataclass
class Config:
    """Loaded settings with convenient typed accessors."""

    data: dict
    path: str = ""
    #: Chosen on first use so every plugin in a run writes to the same folder.
    _run_dir: Path = None

    # -- generic access --------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def section(self, name: str) -> dict:
        value = self.data.get(name, {})
        return value if isinstance(value, dict) else {}

    # -- derived objects -------------------------------------------------
    def parse_options(self) -> ParseOptions:
        amb = self.section("ambiguity")
        options = ParseOptions(
            alternates=amb.get("alternates", "first"),
            max_variants=int(amb.get("maxVariants", 16)),
            unreadable=amb.get("unreadable", "keep"),
            unreadable_char=amb.get("unreadableChar", "?"),
            uncertain_space=amb.get("uncertainSpace", "keep"),
            ligatures=amb.get("ligatures", "keep"),
            high_ascii=amb.get("highAscii", "unicode"),
            strip_fillers=bool(amb.get("stripFillers", True)),
        )
        options.validate()
        return options

    def markers(self) -> Markers:
        raw = self.get("mapping.markers", {}) or {}
        return Markers(
            start_of_word=raw.get("startOfWord", "@"),
            end_of_word=raw.get("endOfWord", "/"),
            occurrence=tuple(raw.get("occurrence", ["'", '"', ":", ";"])),
        )

    def selection(self):
        from .corpus import selection_from_dict

        return selection_from_dict(self.section("selection"))

    def mapping_path(self) -> Path:
        raw = self.get("mapping.file", "mappings/identity_eva.json")
        path = Path(raw)
        return path if path.is_absolute() else ws(raw)

    def names_a_mapping(self) -> bool:
        """True when the user actually chose a mapping, rather than defaulting.

        An unconfigured folder falls back to the identity mapping so that
        ``tvtt run`` does something useful before ``tvtt init``. Once a mapping
        has been named, a missing file is a mistake and has to be reported.
        """
        chosen = self.get("mapping.file", "") != DEFAULT_CONFIG["mapping"]["file"]
        return chosen or bool(self.path and Path(self.path).exists())

    def output_root(self) -> Path:
        """The folder that holds every run's results."""
        directory = self.get("output.directory", "output")
        path = Path(directory)
        return path if path.is_absolute() else ws(directory)

    def output_dir(self) -> Path:
        """Where this run writes, creating the folder if needed.

        Runs are numbered: run-001, run-002, and so on. The folder name stays
        short and sortable; what the run actually did goes in the info.txt file
        inside it. The number is chosen once and reused for the rest of the run.
        """
        if self._run_dir is not None:
            self._run_dir.mkdir(parents=True, exist_ok=True)
            return self._run_dir

        root = self.output_root()
        if not self.get("output.separateRunFolders", True):
            self._run_dir = root
        else:
            self._run_dir = _unique_run_dir(root, self.run_label())
        self._run_dir.mkdir(parents=True, exist_ok=True)
        return self._run_dir

    def run_label(self) -> str:
        """The folder name for this run: a name you chose, or the next number."""
        custom = self.get("output.runName", "")
        if custom:
            return _slug(str(custom))
        return _next_run_number(self.output_root())

    def seed(self) -> int:
        return int(self.get("random.seed", 0) or 0)

    def offline(self) -> bool:
        return bool(self.get("network.offline", True))

    def signature(self) -> str:
        """A hash of the whole config, recorded in the run manifest."""
        return stable_hash(self.data)

    def to_json(self) -> str:
        return json.dumps(self.data, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(text: str) -> str:
    """Make a string safe to use as a folder name on every platform."""
    return _SLUG_RE.sub("-", str(text)).strip("-.") or "run"


def _unique_run_dir(root: Path, label: str) -> Path:
    """Pick a folder name that does not already exist.

    Two runs started in the same second must not land in the same folder, or
    the second silently overwrites the first - which is the whole problem this
    is here to solve.
    """
    candidate = root / label
    if not candidate.exists():
        return candidate
    for n in range(2, 1000):
        candidate = root / ("%s-%d" % (label, n))
        if not candidate.exists():
            return candidate
    return root / ("%s-%d" % (label, int(time.time())))


RUN_PREFIX = "run-"
RUN_COUNTER = ".run-counter"
_RUN_NUMBER = re.compile(r"^run-(\d+)$")


def _next_run_number(root: Path) -> str:
    """The next ``run-NNN`` name, never one that has been used before.

    The highest number issued so far is remembered in a small counter file, not
    just inferred from the folders present. Otherwise deleting run-002 would
    make the next run claim that name, and any note referring to "run-002"
    would silently start pointing at different results.
    """
    highest = 0
    if root.is_dir():
        for path in root.iterdir():
            match = _RUN_NUMBER.match(path.name)
            if match and path.is_dir():
                highest = max(highest, int(match.group(1)))

    counter = root / RUN_COUNTER
    try:
        highest = max(highest, int(counter.read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        pass

    number = highest + 1
    try:
        root.mkdir(parents=True, exist_ok=True)
        counter.write_text("%d\n" % number, encoding="utf-8")
    except OSError:  # pragma: no cover - read-only output directory
        pass
    return "%s%03d" % (RUN_PREFIX, number)


def deep_merge(base: dict, override: dict) -> dict:
    """Merge ``override`` into a copy of ``base``, recursing into dicts."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_schema(name: str) -> dict:
    path = data_file("schema", name)
    if not path.exists():
        return {}
    return json.loads(read_text(path))


def migrate_legacy(raw: dict) -> dict:
    """Translate a version 1.x flat config into the version 2 layout."""
    if not any(k in raw for k in ("enableAnalysis", "outputPath", "spaceDelimiter", "toleranceLevel")):
        return raw
    out: dict = {}
    trans = raw.get("transliteration", "zl")
    out["transcription"] = {"eva": "zl", "v101": "v101"}.get(trans, trans)
    out["mapping"] = {
        "file": "mappings/%s.json" % ("identity_eva" if trans == "eva" else "identity_v101"),
        "markers": {
            "startOfWord": raw.get("startOfWordMarker", "@"),
            "endOfWord": raw.get("endOfWordMarker", "/"),
            "occurrence": [
                raw.get("firstOccuranceMarker", "'"),
                raw.get("secondOccuranceMarker", '"'),
                raw.get("thirdOccuranceMarker", ":"),
                raw.get("fourthOccuranceMarker", ";"),
            ],
        },
    }
    out["selection"] = {
        "startLine": int(raw.get("startLine", 1)),
        "endLine": int(raw.get("endLine", -1)),
    }
    out["output"] = {
        "wordSeparator": raw.get("spaceDelimiter", " "),
        "uncertainWordSeparator": raw.get("ambiguousSpaceDelimiter", " "),
    }
    out["reference"] = {"folder": raw.get("referenceFolder", "reference_texts")}
    return out


def load_config(path=None, overrides: dict = None) -> Config:
    """Load the settings, in layers, and validate the result.

    The layers, each merged over the one before:

    1. the built-in defaults,
    2. ``config.json`` - which may use either the simple vocabulary or the full
       one, whichever it happens to contain,
    3. ``advanced_config.json``, if it exists,
    4. anything given on the command line with ``--set``.

    A version 1.x config is detected and translated before any of that.
    """
    from .simpleconfig import (
        ADVANCED_CONFIG,
        expand_simple_config,
        is_simple_config,
        load_layer,
        strip_comment_keys,
    )

    target = Path(path) if path else ws(CONFIG_FILENAME)
    advanced = target.parent / ADVANCED_CONFIG

    try:
        if path:
            # An explicit --config file is used on its own, with no layering.
            raw = read_json(target) if target.exists() else {}
            raw.pop("$schema", None)
            if is_simple_config(raw):
                raw = expand_simple_config(strip_comment_keys(raw))
            sources = [str(target)] if target.exists() else []
        else:
            raw, sources = load_layer(target, advanced, expand_simple_config, is_simple_config, "config")
    except json.JSONDecodeError as exc:
        raise ConfigError(
            "%s is not valid JSON (line %d, column %d): %s" % (display_path(target), exc.lineno, exc.colno, exc.msg),
            hint="Check for a missing comma or an unclosed quote near that line.",
        ) from exc

    raw = migrate_legacy(raw)

    merged = deep_merge(DEFAULT_CONFIG, raw)
    schema = load_schema("config.schema.json")
    if schema:
        validate(merged, schema, source=" and ".join(sources) if sources else "built-in defaults")
    if overrides:
        merged = deep_merge(merged, overrides)
    return Config(data=merged, path=str(target))


def write_default_config(path=None, force: bool = False, base: dict = None) -> Path:
    """Write ``advanced_config.json``: every setting, at its current value.

    ``base`` is the configuration already in force. Writing the built-in
    defaults instead would have this file silently override the simple one the
    moment it is created -- including pointing ``mapping.file`` at a starter
    mapping that does not exist under that name. Seeded from the effective
    settings, adding this file changes nothing until you edit it.
    """
    from .simpleconfig import ADVANCED_CONFIG

    target = Path(path) if path else ws(ADVANCED_CONFIG)
    if target.exists() and not force:
        raise ConfigError(
            "%s already exists" % display_path(target),
            hint="Pass --force to overwrite it.",
        )
    payload = {
        "note": (
            "The complete set of settings. This file is merged on top of config.json, "
            "so you only need to keep the lines you actually change. Delete it to go "
            "back to the simple settings alone."
        ),
    }
    payload.update(copy.deepcopy(base if base is not None else DEFAULT_CONFIG))
    payload.pop("$schema", None)
    return write_json(target, payload)
