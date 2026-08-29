"""Deep links to the manuscript itself.

TVTT never downloads or bundles page images.  It stores the URLs of Yale's
openly published IIIF image service and builds links to the two reference sites
every Voynich researcher uses, so any folio in a report is one click away from
the actual page.

* **Beinecke IIIF** - Yale University, Beinecke Rare Book and Manuscript
  Library, MS 408.  The image service lets you ask for any size, so reports can
  request a small thumbnail and a full-size link from the same base URL.
* **voynichese.com** - Takeshi Takahashi's interactive transcription viewer.
* **voynich.nu** - Rene Zandbergen's reference site, with a page for each folio.

Images load only when somebody opens the report in a browser; nothing here
makes a network request.
"""

from __future__ import annotations

import functools
import re

from .ivtff import normalise_folio
from .paths import data_file
from .util import read_json

BEINECKE_CATALOGUE = "https://collections.library.yale.edu/catalog/2002046"
BEINECKE_MANIFEST = "https://collections.library.yale.edu/manifests/2002046"
VOYNICHESE = "https://voynichese.com/#/folios/f%s"
VOYNICH_NU = "https://www.voynich.nu/f%s/f%s_pics.html"


@functools.lru_cache(maxsize=1)
def _iiif() -> dict:
    path = data_file("iiif.json")
    if not path.exists():
        return {"pages": {}}
    return read_json(path)


def _entry(folio: str) -> dict:
    pages = _iiif().get("pages", {})
    key = normalise_folio(folio)
    if key in pages:
        return pages[key]
    # Foldout panels (68r2) are photographed as one sheet (68r).
    trimmed = re.sub(r"\d$", "", key)
    return pages.get(trimmed, {})


def has_image(folio: str) -> bool:
    return bool(_entry(folio))


def image_url(folio: str, width: int = 0) -> str:
    """A IIIF image URL for a folio; ``width=0`` asks for the full size."""
    entry = _entry(folio)
    if not entry:
        return ""
    size = "full" if not width else "%d," % width
    return "%s/full/%s/0/default.jpg" % (entry["service"], size)


def image_label(folio: str) -> str:
    return _entry(folio).get("label", "")


def beinecke_url(folio: str = "") -> str:
    """The catalogue page for the manuscript (the viewer opens from here)."""
    return BEINECKE_CATALOGUE


def voynichese_url(folio: str) -> str:
    """Open this folio in voynichese.com."""
    return VOYNICHESE % normalise_folio(folio)


def voynich_nu_url(folio: str) -> str:
    """Open Rene Zandbergen's page for the quire containing this folio."""
    key = normalise_folio(folio)
    return VOYNICH_NU % (key, key)


def all_links(folio: str) -> dict:
    """Every link TVTT knows for one folio, ready to drop into a report."""
    return {
        "folio": normalise_folio(folio),
        "image": image_url(folio),
        "thumbnail": image_url(folio, 400),
        "image_label": image_label(folio),
        "beinecke": beinecke_url(folio),
        "voynichese": voynichese_url(folio),
        "voynich_nu": voynich_nu_url(folio),
    }


def attribution() -> str:
    return (
        "Page images: Beinecke Rare Book and Manuscript Library, Yale University, MS 408, "
        "served over IIIF from collections.library.yale.edu and loaded directly by your browser."
    )
