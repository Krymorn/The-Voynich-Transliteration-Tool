"""Structured logging and progress bars.

Logging has two shapes:

* ``text``  - friendly, colour-free lines meant for humans.
* ``json``  - one JSON object per line, meant for scripts and CI.

Progress bars use ``tqdm`` when it is installed and fall back to a tiny
stderr bar otherwise, so long runs always show something.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterable, Iterator
from typing import Any, TypeVar

from .util import optional_import

T = TypeVar("T")

LOGGER_NAME = "tvtt"
_configured = False
_show_progress = True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False, default=str)


class _TextFormatter(logging.Formatter):
    _MARK = {
        "DEBUG": "  .",
        "INFO": "  -",
        "WARNING": "  !",
        "ERROR": "  x",
        "CRITICAL": " xx",
    }

    def format(self, record: logging.LogRecord) -> str:
        mark = self._MARK.get(record.levelname, "  -")
        msg = record.getMessage()
        extra = getattr(record, "fields", None)
        if extra:
            msg += "  " + " ".join(f"{k}={v}" for k, v in extra.items())
        return f"{mark} {msg}"


def configure(level: str = "info", fmt: str = "text", progress: bool = True) -> logging.Logger:
    """Set up the ``tvtt`` logger.  Safe to call more than once."""
    global _configured, _show_progress
    _show_progress = progress
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter() if fmt == "json" else _TextFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    _configured = True
    return logger


def get_logger(name: str = "") -> logging.Logger:
    if not _configured:
        configure()
    return logging.getLogger(LOGGER_NAME + ("." + name if name else ""))


def log(logger: logging.Logger, level: str, message: str, **fields: Any) -> None:
    """Log with structured fields attached."""
    logger.log(getattr(logging, level.upper(), logging.INFO), message, extra={"fields": fields})


# --------------------------------------------------------------------------
# Progress
# --------------------------------------------------------------------------


class _MiniBar:
    """A dependency-free progress bar written to stderr."""

    def __init__(self, total: int | None, desc: str) -> None:
        self.total = total
        self.desc = desc
        self.n = 0
        self._last = 0.0
        self._start = time.perf_counter()

    def update(self, step: int = 1) -> None:
        self.n += step
        now = time.perf_counter()
        if now - self._last < 0.1 and (self.total is None or self.n < self.total):
            return
        self._last = now
        if self.total:
            frac = min(1.0, self.n / self.total)
            filled = int(28 * frac)
            bar = "#" * filled + "." * (28 - filled)
            sys.stderr.write(f"\r  {self.desc:<26} [{bar}] {frac * 100:5.1f}%")
        else:
            sys.stderr.write(f"\r  {self.desc:<26} {self.n} items")
        sys.stderr.flush()

    def close(self) -> None:
        if self.n:
            sys.stderr.write(f"\r  {self.desc:<26} done ({self.n}) in {time.perf_counter() - self._start:.2f}s\n")
            sys.stderr.flush()


def progress(iterable: Iterable[T], desc: str = "working", total: int | None = None) -> Iterator[T]:
    """Wrap an iterable in a progress bar (no-op when progress is disabled)."""
    if not _show_progress or not sys.stderr.isatty():
        yield from iterable
        return
    if total is None:
        try:
            total = len(iterable)  # type: ignore[arg-type]
        except TypeError:
            total = None
    tqdm = optional_import("tqdm")
    if tqdm is not None:
        yield from tqdm.tqdm(iterable, desc=f"  {desc}", total=total, leave=False, ncols=78)
        return
    bar = _MiniBar(total, desc)
    try:
        for item in iterable:
            yield item
            bar.update()
    finally:
        bar.close()
