"""Helpers shared by the bundled plugins.

Plugins are meant to be short and readable, so anything more than two of them
need lives here rather than being copied around.
"""

from __future__ import annotations

import random
from collections import Counter

from ..logging_util import progress
from ..util import table, write_json, write_text


def words(ctx) -> list:
    """The transliterated word list (the thing almost every analysis wants)."""
    return ctx.result.words()


def source_words(ctx) -> list:
    return ctx.corpus.words()


def line_words(ctx) -> list:
    return ctx.result.line_words()


def rng(ctx) -> random.Random:
    """A generator seeded from config, so runs are reproducible."""
    return random.Random(ctx.config.seed())


def save_json(ctx, filename: str, payload, description: str = ""):
    path = write_json(ctx.output_path(filename), payload)
    ctx.record_output(path, description)
    return path


def save_text(ctx, filename: str, text: str, description: str = ""):
    path = write_text(ctx.output_path(filename), text)
    ctx.record_output(path, description)
    return path


def save_table(ctx, filename: str, rows: list, headers: list, description: str = "", title: str = ""):
    body = (title + "\n" + "=" * len(title) + "\n\n") if title else ""
    return save_text(ctx, filename, body + table(rows, headers) + "\n", description)


def bar(value: float, maximum: float, width: int = 24) -> str:
    if not maximum:
        return ""
    filled = int(round(width * max(0.0, min(1.0, value / maximum))))
    return "#" * filled + "." * (width - filled)


def counts_table(counter: Counter, limit: int = 40, label: str = "item") -> list:
    total = sum(counter.values()) or 1
    rows = []
    peak = counter.most_common(1)[0][1] if counter else 1
    for item, count in counter.most_common(limit):
        rows.append([item, count, "%.3f%%" % (100 * count / total), bar(count, peak)])
    return rows


def track(ctx, iterable, description: str, total: int = None):
    """Wrap an iterable in a progress bar when progress is switched on."""
    if not ctx.config.get("performance.progress", True):
        return iterable
    return progress(iterable, description, total)


def verdict_class(text: str) -> str:
    """Map a verdict sentence to a CSS class for the HTML report."""
    lowered = text.lower()
    if any(w in lowered for w in ("no evidence", "not distinguishable", "collapses", "no better", "severe")):
        return "bad"
    if any(w in lowered for w in ("only slightly", "within reach", "some loss", "watch", "mild", "partly")):
        return "warn"
    return "good"
