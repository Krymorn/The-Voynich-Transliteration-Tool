"""Where TVTT looks for files.

Two locations matter:

``workspace``
    The folder you run the tool from (the one holding ``config.json``).
    Anything you create or edit lives here: mappings, outputs, your own
    dictionaries, your own data overrides.

``package data``
    The read-only files that ship with TVTT (``tvtt/data``): transcriptions,
    folio metadata, reference dictionaries, control texts, JSON schemas and
    the Voynich font.

Lookups always try the workspace first, then the package.  That means you can
override any bundled file by dropping a same-named file into ``./data/`` next
to your ``config.json`` -- without editing the installed package.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PACKAGE_DATA = PACKAGE_DIR / "data"

_workspace: Path | None = None


def set_workspace(path: str | os.PathLike[str] | None) -> Path:
    """Pin the workspace directory (called once by the CLI)."""
    global _workspace
    _workspace = Path(path).resolve() if path else Path.cwd().resolve()
    return _workspace


def workspace() -> Path:
    """Return the active workspace, defaulting to the current directory."""
    return _workspace if _workspace is not None else Path.cwd().resolve()


def ws(*parts: str) -> Path:
    """Build a path inside the workspace."""
    return workspace().joinpath(*parts)


def data_file(*parts: str) -> Path:
    """Locate a data file: workspace ``data/`` first, then bundled data.

    Returns the workspace path even when neither exists, so that callers can
    produce a sensible "expected at ..." error message.
    """
    local = workspace().joinpath("data", *parts)
    if local.exists():
        return local
    packaged = PACKAGE_DATA.joinpath(*parts)
    if packaged.exists():
        return packaged
    return local


def data_dirs(*parts: str) -> list[Path]:
    """All existing directories for a data sub-folder, workspace first."""
    out: list[Path] = []
    local = workspace().joinpath("data", *parts)
    if local.is_dir():
        out.append(local)
    packaged = PACKAGE_DATA.joinpath(*parts)
    if packaged.is_dir() and packaged != local:
        out.append(packaged)
    return out


def transcription_file(name: str) -> Path:
    """Find a transcription file by file name."""
    for base in (workspace() / "transcriptions", *data_dirs("transcriptions")):
        candidate = base / name
        if candidate.exists():
            return candidate
    return workspace() / "transcriptions" / name


def output_dir(sub: str = "") -> Path:
    """Return (and create) the output directory."""
    path = ws("output", sub) if sub else ws("output")
    path.mkdir(parents=True, exist_ok=True)
    return path


def display_path(value) -> str:
    """Render a path for display or for a file, never as an absolute one.

    Absolute paths carry the account name of whoever ran the tool, and this
    output gets pasted into bug reports and shared in manifests. Anything
    inside the workspace or the installed package is shown relative to it;
    anything else is reduced to a bare file name.
    """
    if not value:
        return ""
    path = Path(value)
    for base in (workspace(), PACKAGE_DIR):
        try:
            return path.resolve().relative_to(base.resolve()).as_posix()
        except (ValueError, OSError):
            continue
    return path.name


def cache_dir() -> Path:
    path = ws(".tvtt_cache")
    path.mkdir(parents=True, exist_ok=True)
    return path
