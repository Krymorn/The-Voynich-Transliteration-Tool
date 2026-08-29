"""Showing Voynichese in Voynich shapes, and the glyph legend.

Reports and the browser editor can render the source text in a Voynich font, so
what you see beside your transliteration looks like the manuscript rather than
like the transcriber's ASCII stand-ins.

Which font, and why it matters
------------------------------
A transcription alphabet is a naming scheme, not a set of shapes. EVA calls a
particular shape ``k``; v101 calls the same shape ``K``. So a font is only
correct for the alphabet it was drawn for: rendering EVA text in a v101 font
produces real Voynich shapes that are the *wrong* ones.

TVTT therefore picks the font from the transcription's alphabet:

===============  ==========================
Alphabet         Font
===============  ==========================
``Eva-``, ``EvaT``   Fairfax EVA HD
``v101``             Fairfax V101 HD
anything else        none; plain monospace
===============  ==========================

Currier and FSG have no Voynich font here, so their text is shown as the plain
letters the transcriber wrote. That is honest: inventing shapes for them would
be worse than showing none.

Both fonts are from Rebecca Bettencourt's Voynich Unicode package at
kreativekorp.com, under the SIL Open Font License (see ``OFL.txt`` beside
them). They encode their alphabet twice: once at the ASCII codepoints, and once
at ``U+F020`` to ``U+F0FF``. That second range is what makes the high-ASCII
glyphs work - see :func:`display_text`.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from .errors import DataError
from .ivtff import PUA_BASE, high_ascii_label
from .paths import data_dirs, data_file, ws

EVA_FONT = "FairfaxEVAHD.ttf"
V101_FONT = "FairfaxV101HD.ttf"

#: Which font suits which transcription alphabet. An alphabet that is absent
#: gets no Voynich font at all.
FONT_FOR_ALPHABET = {
    "Eva-": EVA_FONT,
    "EvaT": EVA_FONT,
    "Eva": EVA_FONT,
    "EVA": EVA_FONT,
    "v101": V101_FONT,
}

#: The fonts repeat their alphabet at U+F020-U+F0FF. TVTT holds a ``@nnn;``
#: glyph internally as ``chr(PUA_BASE + nnn)``, so shifting it into that range
#: is all it takes to render one. Going through U+F0xx rather than the bare
#: byte value also avoids the C1 control characters at U+0080-U+009F, which
#: browsers will not draw.
FONT_PUA_BASE = 0xF000


@dataclass
class FontChoice:
    """Which font to render source text in, and how to embed it."""

    name: str
    path: Path = None
    available: bool = False

    def css(self) -> str:
        """A ``@font-face`` rule with the font embedded as a data URI."""
        if not self.available or self.path is None:
            return ""
        try:
            payload = base64.b64encode(self.path.read_bytes()).decode("ascii")
        except OSError:
            return ""
        suffix = self.path.suffix.lower()
        fmt = "opentype" if suffix == ".otf" else "truetype"
        mime = "font/otf" if suffix == ".otf" else "font/ttf"
        return (
            "@font-face { font-family: 'TvttVoynich'; "
            "src: url('data:%s;base64,%s') format('%s'); font-display: swap; }" % (mime, payload, fmt)
        )

    def font_family(self) -> str:
        return "'TvttVoynich', monospace" if self.available else "monospace"


def display_text(text: str) -> str:
    """Rewrite text so a Voynich font can draw every glyph in it.

    Only the ``@nnn;`` glyphs need anything done to them: internally they are
    private-use characters, and the font expects them 0x1000 further along.
    Everything else is already at the codepoint the font uses.
    """
    if not text:
        return text
    out = []
    for ch in text:
        code = ord(ch)
        out.append(chr(FONT_PUA_BASE + code - PUA_BASE) if code >= PUA_BASE else ch)
    return "".join(out)


def is_code_glyph(glyph: str) -> bool:
    """True for a ``@nnn;`` glyph, which needs its code shown as well."""
    return len(glyph) == 1 and ord(glyph) >= PUA_BASE


def available_fonts() -> list:
    """Every font file TVTT can find, workspace first."""
    found = {}
    for directory in [ws("fonts"), *data_dirs("fonts")]:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.[to]tf")):
            found.setdefault(path.name, str(path))
    return sorted(found.items())


def choose_font(name: str = "", alphabet: str = "") -> FontChoice:
    """Pick a font by explicit name, else by alphabet, else none.

    There is deliberately no catch-all fallback: a font that does not match the
    alphabet draws the wrong shapes, which is worse than drawing none.
    """
    candidates = []
    if name:
        candidates.append(name)
    elif alphabet in FONT_FOR_ALPHABET:
        candidates.append(FONT_FOR_ALPHABET[alphabet])

    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return FontChoice(name=path.name, path=path, available=True)
        local = ws("fonts", candidate)
        if local.exists():
            return FontChoice(name=candidate, path=local, available=True)
        bundled = data_file("fonts", candidate)
        if bundled.exists():
            return FontChoice(name=candidate, path=bundled, available=True)
    return FontChoice(name=name or "none", available=False)


def require_font(name: str) -> FontChoice:
    choice = choose_font(name)
    if not choice.available:
        raise DataError(
            "font %r not found" % name,
            hint="Put the .ttf or .otf in a 'fonts' folder next to config.json. Available: "
            + (", ".join(n for n, _ in available_fonts()) or "(none)"),
        )
    return choice


# --------------------------------------------------------------------------
# Glyph legend
# --------------------------------------------------------------------------


def glyph_legend(engine, counts: dict = None) -> list:
    """Build the cheat sheet for the active mapping.

    One row per glyph: how it is written in the transcription, how often it
    occurs, and what your mapping turns it into in each position. This is the
    single most useful thing to have open while editing a mapping by hand.
    """
    from .mapping import SLOT_NAMES, SLOT_PLAIN

    counts = counts or {}
    rows = []
    for glyph in engine.keys:
        slots = engine.mapping.rules.get(glyph, {})
        rows.append(
            {
                "glyph": glyph,
                "display": high_ascii_label(glyph) if len(glyph) == 1 else glyph,
                "rendered": display_text(glyph),
                "is_code": is_code_glyph(glyph),
                "count": counts.get(glyph, 0),
                "plain": slots.get(SLOT_PLAIN, ""),
                "rules": {SLOT_NAMES[s]: t for s, t in sorted(slots.items())},
                "mapped": bool(slots),
            }
        )
    rows.sort(key=lambda r: (-r["count"], r["glyph"]))
    return rows


def legend_text(rows: list) -> str:
    """Render the legend as a plain-text table."""
    from .util import table

    body = []
    for row in rows:
        positions = ", ".join("%s=%s" % (name, value) for name, value in row["rules"].items() if name != "plain")
        body.append([row["display"], row["count"], row["plain"] or "-", positions])
    return table(body, ["glyph", "count", "becomes", "positional rules"])
