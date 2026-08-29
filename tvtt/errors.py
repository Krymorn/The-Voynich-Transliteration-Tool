"""Error types used throughout TVTT.

Every error carries a human-readable explanation.  The CLI catches
:class:`TvttError` and prints ``message`` plus ``hint`` without a traceback,
so that a non-programmer sees something actionable instead of a stack dump.
"""

from __future__ import annotations


class TvttError(Exception):
    """Base class for every expected (non-bug) failure.

    ``skippable`` marks a failure that should not bring down a whole run: a
    missing optional package, or a feature blocked by a deliberate policy such
    as offline mode. The pipeline records these as warnings and carries on.
    """

    def __init__(self, message: str, hint: str = "", skippable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.skippable = skippable

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message if not self.hint else f"{self.message}\n  Hint: {self.hint}"


class ConfigError(TvttError):
    """config.json / plugins.json is missing a key, or a value is invalid."""


class MappingError(TvttError):
    """A mapping file is malformed, or its rules contradict each other."""


class DataError(TvttError):
    """A transcription, dictionary or bundled data file could not be used."""


class PluginError(TvttError):
    """A plugin is unknown, misconfigured, or failed while running."""


class DependencyError(TvttError):
    """An optional third-party package is needed but not installed."""

    def __init__(self, message: str, hint: str = "", skippable: bool = True) -> None:
        super().__init__(message, hint, skippable)
