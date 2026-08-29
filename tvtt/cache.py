"""A tiny on-disk cache so repeated runs are fast.

Anything expensive and deterministic - a parsed transcription, a compiled
dictionary, an n-gram language model, the statistics of a control text - is
stored under ``.tvtt_cache/`` keyed by a hash of everything that went into it.
Change the input and the key changes, so a stale entry can never be served.

The cache is always safe to delete (``tvtt cache clear``).
"""

from __future__ import annotations

import pickle
import shutil
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .logging_util import get_logger
from .paths import cache_dir
from .util import stable_hash

_log = get_logger("cache")
_enabled = True
_memory: dict = {}


def configure(enabled: bool = True) -> None:
    """Turn disk caching on or off for the whole process."""
    global _enabled
    _enabled = enabled


def is_enabled() -> bool:
    return _enabled


def key_for(namespace: str, *parts: Any) -> str:
    return "%s-%s" % (namespace, stable_hash([__version__, namespace, *parts])[:24])


def get_or_compute(namespace: str, parts: list, compute: Callable[[], Any], memory: bool = True) -> Any:
    """Return a cached value, computing and storing it on a miss."""
    key = key_for(namespace, *parts)
    if memory and key in _memory:
        return _memory[key]

    path = cache_dir() / (key + ".pkl")
    if _enabled and path.exists():
        try:
            with open(path, "rb") as fh:
                value = pickle.load(fh)
            if memory:
                _memory[key] = value
            return value
        except Exception:
            path.unlink(missing_ok=True)

    value = compute()
    if memory:
        _memory[key] = value
    if _enabled:
        try:
            with open(path, "wb") as fh:
                pickle.dump(value, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:  # pragma: no cover - disk problems only
            _log.debug("could not write cache entry %s: %s", key, exc)
    return value


def clear() -> int:
    """Delete every cache entry; returns how many files were removed."""
    _memory.clear()
    directory = cache_dir()
    count = sum(1 for _ in directory.glob("*.pkl"))
    shutil.rmtree(directory, ignore_errors=True)
    Path(directory).mkdir(parents=True, exist_ok=True)
    return count


def size_bytes() -> int:
    return sum(p.stat().st_size for p in cache_dir().glob("*.pkl"))
