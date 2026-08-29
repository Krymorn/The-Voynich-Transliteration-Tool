"""Small helpers shared across the package: hashing, timing, seeding, IO."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import random
import time
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Hashing / reproducibility
# --------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(obj: Any) -> str:
    """Hash any JSON-serialisable object deterministically."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return sha256_text(blob)


def rng(seed: int | None) -> random.Random:
    """Create a seeded random generator.

    Every stochastic feature in TVTT takes its randomness from here, so a run
    with the same seed produces byte-identical output.
    """
    return random.Random(seed if seed is not None else 0)


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def read_text(path: str | os.PathLike[str]) -> str:
    """Read a text file, trying the encodings transcription files use.

    The historical v101 file is Latin-1 with high-ASCII glyph bytes; the IVTFF
    files are UTF-8.  Trying in order avoids forcing the user to care.
    """
    raw = Path(path).read_bytes()
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def write_text(path: str | os.PathLike[str], text: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def write_json(path: str | os.PathLike[str], obj: Any, indent: int = 2) -> Path:
    return write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False, default=_json_default) + "\n")


def read_json(path: str | os.PathLike[str]) -> Any:
    return json.loads(read_text(path))


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (set, frozenset, tuple)):
        return list(obj)
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


# --------------------------------------------------------------------------
# Optional dependencies
# --------------------------------------------------------------------------

_optional_cache: dict[str, Any] = {}


def optional_import(module: str):
    """Import an optional dependency, returning ``None`` when unavailable."""
    if module in _optional_cache:
        return _optional_cache[module]
    try:
        mod = importlib.import_module(module)
    except Exception:
        mod = None
    _optional_cache[module] = mod
    return mod


def has_module(module: str) -> bool:
    return optional_import(module) is not None


# --------------------------------------------------------------------------
# Timing
# --------------------------------------------------------------------------


class Timer:
    """Context manager measuring wall-clock seconds."""

    def __init__(self) -> None:
        self.elapsed = 0.0
        self._start = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.elapsed = time.perf_counter() - self._start

    def __str__(self) -> str:  # pragma: no cover - display only
        return format_duration(self.elapsed)


def format_duration(seconds: float) -> str:
    if seconds < 1e-3:
        return f"{seconds * 1e6:.0f}us"
    if seconds < 1:
        return f"{seconds * 1e3:.0f}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    return f"{int(seconds // 60)}m{seconds % 60:04.1f}s"


# --------------------------------------------------------------------------
# Numbers / formatting
# --------------------------------------------------------------------------


def pct(part: float, whole: float, digits: int = 2) -> float:
    return round(100.0 * part / whole, digits) if whole else 0.0


def safe_log2(x: float) -> float:
    return math.log2(x) if x > 0 else 0.0


def chunked(seq: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def truncate(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


def table(rows: Iterable[Sequence[Any]], headers: Sequence[str] | None = None) -> str:
    """Render a monospaced text table (used by the CLI and text reports)."""
    body = [[("" if c is None else str(c)) for c in row] for row in rows]
    if headers:
        body.insert(0, list(headers))
    if not body:
        return ""
    widths = [max(len(r[i]) for r in body if i < len(r)) for i in range(max(len(r) for r in body))]
    lines = []
    for idx, row in enumerate(body):
        cells = [row[i].ljust(widths[i]) if i < len(row) else " " * widths[i] for i in range(len(widths))]
        lines.append("  ".join(cells).rstrip())
        if headers and idx == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)
