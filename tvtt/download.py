"""Fetching transliterations from voynich.nu, with checksum verification.

TVTT ships a copy of every published transliteration so that a fresh install
works offline.  Those copies age: Rene Zandbergen revises the files as
corrections come in.  ``tvtt fetch`` downloads the current version, checks it
against the checksum recorded when this release was built, and tells you
plainly whether you now have something different from what the release was
tested against.

A changed checksum is reported, not treated as an error.  An upstream
correction is a normal event, and refusing to accept it would be worse than
noting it.  What matters is that you *know* which bytes you are working from -
which is also why the checksum of whatever you actually used is written into
every run manifest.

Network use is opt-in.  With ``network.offline`` true in config.json (the
default) nothing here will make a request unless you explicitly run ``fetch``.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .errors import DataError
from .logging_util import get_logger
from .paths import data_file, ws
from .util import read_json, sha256_bytes, sha256_file

_log = get_logger("download")


@dataclass
class FetchResult:
    """What happened when one file was fetched."""

    key: str
    filename: str
    url: str
    path: str
    downloaded: bool
    bytes: int
    sha256: str
    expected: str
    status: str

    @property
    def verified(self) -> bool:
        return self.status == "verified"

    def message(self) -> str:
        if self.status == "verified":
            return "%s: verified (%d bytes)" % (self.filename, self.bytes)
        if self.status == "changed":
            return (
                "%s: downloaded, but the checksum differs from the bundled copy.\n"
                "    bundled  %s\n    upstream %s\n"
                "    This normally means voynich.nu has published a correction. "
                "The new file is in place; re-run your analyses to pick it up."
                % (self.filename, self.expected[:32], self.sha256[:32])
            )
        if self.status == "unchanged":
            return "%s: already up to date" % self.filename
        if self.status == "unknown":
            return "%s: downloaded (%d bytes); no reference checksum to compare against" % (self.filename, self.bytes)
        return "%s: %s" % (self.filename, self.status)


def load_sources() -> dict:
    path = data_file("sources.json")
    if not path.exists():
        raise DataError(
            "sources.json is missing",
            hint="Reinstall TVTT, or create data/sources.json listing the transliterations you use.",
        )
    return read_json(path)


def describe_sources() -> list:
    """Rows for ``tvtt sources``."""
    document = load_sources()
    rows = []
    for key, entry in document.get("sources", {}).items():
        local = ws("transcriptions", entry["file"])
        bundled = data_file("transcriptions", entry["file"])
        where = "workspace" if local.exists() else ("bundled" if bundled.exists() else "missing")
        rows.append((key, entry["alphabet"], entry["file"], where, entry["title"]))
    return rows


def fetch(
    key: str = "",
    all_sources: bool = False,
    destination: str = "transcriptions",
    user_agent: str = "TVTT/2.0",
    timeout: int = 60,
    force: bool = False,
) -> list:
    """Download one transliteration, or every one, into the workspace."""
    document = load_sources()
    sources = document.get("sources", {})
    if not all_sources:
        if key not in sources:
            raise DataError(
                "unknown transcription %r" % key,
                hint="Available: " + ", ".join(sources),
            )
        wanted = {key: sources[key]}
    else:
        wanted = sources

    target_dir = ws(destination)
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for name, entry in wanted.items():
        url = entry.get("url", "")
        path = target_dir / entry["file"]
        expected = entry.get("sha256", "")

        if path.exists() and not force:
            digest = sha256_file(path)
            if digest == expected:
                results.append(
                    FetchResult(
                        name, entry["file"], url, str(path), False, path.stat().st_size, digest, expected, "unchanged"
                    )
                )
                continue

        if not url:
            results.append(FetchResult(name, entry["file"], "", str(path), False, 0, "", expected, "no download url"))
            continue

        try:
            request = urllib.request.Request(url, headers={"User-Agent": user_agent})
            payload = urllib.request.urlopen(request, timeout=timeout).read()
        except urllib.error.HTTPError as exc:
            results.append(
                FetchResult(name, entry["file"], url, str(path), False, 0, "", expected, "HTTP %s" % exc.code)
            )
            continue
        except Exception as exc:
            results.append(FetchResult(name, entry["file"], url, str(path), False, 0, "", expected, "failed: %s" % exc))
            continue

        digest = sha256_bytes(payload)
        path.write_bytes(payload)
        status = "verified" if digest == expected else ("changed" if expected else "unknown")
        results.append(FetchResult(name, entry["file"], url, str(path), True, len(payload), digest, expected, status))
        _log.info("fetched %s (%d bytes, %s)", entry["file"], len(payload), status)

    return results


def verify_local() -> list:
    """Check the checksums of the copies already on disk."""
    document = load_sources()
    rows = []
    for key, entry in document.get("sources", {}).items():
        local = ws("transcriptions", entry["file"])
        path = local if local.exists() else data_file("transcriptions", entry["file"])
        if not Path(path).exists():
            rows.append((key, entry["file"], "missing", ""))
            continue
        digest = sha256_file(path)
        state = "ok" if digest == entry.get("sha256") else "differs from release checksum"
        rows.append((key, entry["file"], state, digest[:16]))
    return rows
