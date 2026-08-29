"""Turning results into things you can read: HTML, plots and text.

The HTML report is deliberately a *single self-contained file*.  It embeds its
own CSS, its own JavaScript and, if you ask for one, the Voynich font itself,
so it can be emailed, put on a memory stick or opened years later without a
server or a network connection.  The only thing it loads from outside is the
manuscript's own page images, and only when you switch them on.

Plots use matplotlib when it is installed and Plotly when you ask for an
interactive version; when neither is available the same numbers are still
written out as text and CSV, so a plotting library is never required to get a
result.
"""

from __future__ import annotations

import html as html_lib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .analysis import ZIPF_REFERENCES
from .errors import DependencyError
from .ivtff import describe_glyph
from .util import optional_import, write_text

# --------------------------------------------------------------------------
# Shared HTML furniture
# --------------------------------------------------------------------------

BASE_CSS = """
:root {
  --bg: #faf8f4; --panel: #ffffff; --ink: #1d1a16; --muted: #6b6357;
  --line: #ded7cb; --accent: #7a5c2e; --accent-soft: #f0e7d8;
  --good: #2f6b3a; --warn: #8a6412; --bad: #8c3227;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16140f; --panel: #201d17; --ink: #efe9df; --muted: #a99e8d;
    --line: #3a352c; --accent: #d3ad6b; --accent-soft: #2b261d;
    --good: #7fc08c; --warn: #dcb45a; --bad: #e08b7e;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.6 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
header { background: var(--panel); border-bottom: 1px solid var(--line); padding: 22px 28px; }
header h1 { margin: 0 0 4px; font-size: 22px; letter-spacing: -0.01em; }
header .sub { color: var(--muted); font-size: 13px; }
main { padding: 22px 28px 80px; max-width: 1180px; margin: 0 auto; }
section { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 18px 20px; margin: 0 0 18px; }
section > h2 { margin: 0 0 4px; font-size: 17px; }
section > .why { color: var(--muted); font-size: 13px; margin: 0 0 14px; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line); }
th { font-weight: 600; color: var(--muted); font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.04em; position: sticky; top: 0; background: var(--panel); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.scroll { overflow-x: auto; max-height: 460px; overflow-y: auto; border: 1px solid var(--line);
  border-radius: 8px; }
.pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px;
  background: var(--accent-soft); color: var(--accent); border: 1px solid var(--line); }
.good { color: var(--good); } .warn { color: var(--warn); } .bad { color: var(--bad); }
.grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }
.stat { border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; }
.stat .k { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
.stat .v { font-size: 22px; font-variant-numeric: tabular-nums; margin-top: 2px; }
.stat .n { color: var(--muted); font-size: 12px; }
.controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
input[type=search], select { font: inherit; padding: 7px 10px; border: 1px solid var(--line);
  border-radius: 7px; background: var(--bg); color: var(--ink); }
.line { display: grid; grid-template-columns: 150px 1fr 1fr; gap: 14px; padding: 7px 10px;
  border-bottom: 1px solid var(--line); align-items: start; }
.line .loc { color: var(--muted); font-size: 12px; font-family: ui-monospace, monospace; }
.line .src { font-family: ui-monospace, "Courier New", monospace; font-size: 13px; color: var(--muted); }
.line .out { font-family: ui-monospace, "Courier New", monospace; font-size: 14px; }
.voy { font-family: 'TvttVoynich', ui-monospace, monospace; font-size: 19px; }
mark { background: var(--accent-soft); color: var(--accent); border-radius: 3px; padding: 0 1px; }
.folio { display: grid; grid-template-columns: 260px 1fr; gap: 18px; margin-bottom: 18px;
  border-bottom: 1px solid var(--line); padding-bottom: 18px; }
.folio img { width: 100%; border-radius: 8px; border: 1px solid var(--line); background: var(--accent-soft); }
.folio .links a { margin-right: 10px; font-size: 12px; }
a { color: var(--accent); }
.bar { height: 9px; background: var(--accent-soft); border-radius: 5px; overflow: hidden; }
.bar > i { display: block; height: 100%; background: var(--accent); }
.hm { border-collapse: collapse; font-size: 11px; }
.hm td { padding: 0; width: 15px; height: 15px; border: none; }
.hm th { padding: 1px 3px; font-size: 10px; border: none; text-transform: none; position: static; }
footer { color: var(--muted); font-size: 12px; padding: 24px 28px 60px; max-width: 1180px; margin: 0 auto; }
details > summary { cursor: pointer; color: var(--accent); font-size: 13px; margin-top: 8px; }
"""

FILTER_JS = """
function tvttFilter(inputId, containerId, attr) {
  var input = document.getElementById(inputId);
  var container = document.getElementById(containerId);
  if (!input || !container) return;
  input.addEventListener('input', function () {
    var q = input.value.toLowerCase();
    var rows = container.children;
    for (var i = 0; i < rows.length; i++) {
      var hay = (rows[i].getAttribute(attr) || rows[i].textContent).toLowerCase();
      rows[i].style.display = (!q || hay.indexOf(q) >= 0) ? '' : 'none';
    }
  });
}
function tvttSelect(selectId, containerId, attr) {
  var sel = document.getElementById(selectId);
  var container = document.getElementById(containerId);
  if (!sel || !container) return;
  sel.addEventListener('change', function () {
    var v = sel.value;
    var rows = container.children;
    for (var i = 0; i < rows.length; i++) {
      rows[i].style.display = (!v || (rows[i].getAttribute(attr) || '').split(' ').indexOf(v) >= 0) ? '' : 'none';
    }
  });
}
function tvttHighlight(containerId) {
  var input = document.getElementById('glyph-highlight');
  var container = document.getElementById(containerId);
  if (!input || !container) return;
  input.addEventListener('input', function () {
    var g = input.value;
    var cells = container.querySelectorAll('[data-raw]');
    for (var i = 0; i < cells.length; i++) {
      var raw = cells[i].getAttribute('data-raw');
      if (!g) { cells[i].textContent = raw; continue; }
      var parts = raw.split(g);
      cells[i].textContent = '';
      for (var j = 0; j < parts.length; j++) {
        cells[i].appendChild(document.createTextNode(parts[j]));
        if (j < parts.length - 1) {
          var m = document.createElement('mark');
          m.textContent = g;
          cells[i].appendChild(m);
        }
      }
    }
  });
}
"""


def esc(value) -> str:
    return html_lib.escape("" if value is None else str(value))


@dataclass
class Section:
    """One block of an HTML report."""

    title: str
    why: str
    body: str

    def render(self) -> str:
        return "<section><h2>%s</h2><p class='why'>%s</p>%s</section>" % (
            esc(self.title),
            esc(self.why),
            self.body,
        )


def stat_grid(items: list) -> str:
    """A row of headline numbers: ``(label, value, note)`` triples."""
    cells = []
    for label, value, note in items:
        cells.append(
            "<div class='stat'><div class='k'>%s</div><div class='v'>%s</div><div class='n'>%s</div></div>"
            % (esc(label), esc(value), esc(note))
        )
    return "<div class='grid'>%s</div>" % "".join(cells)


def html_table(rows: list, headers: list, numeric: list = (), max_rows: int = 400, voynich_columns: list = ()) -> str:
    """Render a table. ``voynich_columns`` names columns holding Voynich shapes,
    which are given the Voynich font; everything else stays in the body font."""
    numeric_set = set(numeric)
    voynich_set = set(voynich_columns)
    head = "".join("<th class='%s'>%s</th>" % ("num" if h in numeric_set else "", esc(h)) for h in headers)
    body = []
    for row in rows[:max_rows]:
        cells = []
        for i, cell in enumerate(row):
            if i >= len(headers):
                continue
            classes = []
            if headers[i] in numeric_set:
                classes.append("num")
            if headers[i] in voynich_set:
                classes.append("voy")
            cells.append("<td class='%s'>%s</td>" % (" ".join(classes), esc(cell)))
        cells = "".join(cells)
        body.append("<tr>%s</tr>" % cells)
    more = ""
    if len(rows) > max_rows:
        more = "<p class='why'>Showing the first %d of %d rows.</p>" % (max_rows, len(rows))
    return "<div class='scroll'><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>%s" % (
        head,
        "".join(body),
        more,
    )


def bar_row(label: str, value: float, maximum: float, note: str = "") -> str:
    width = 0 if not maximum else max(0.0, min(100.0, 100.0 * value / maximum))
    return (
        "<tr><td>%s</td><td class='num'>%s</td><td style='width:45%%'>"
        "<div class='bar'><i style='width:%.1f%%'></i></div></td><td class='n'>%s</td></tr>"
        % (esc(label), esc(value), width, esc(note))
    )


def document(title: str, subtitle: str, sections: list, extra_css: str = "", extra_js: str = "") -> str:
    """Assemble a complete, self-contained HTML page."""
    body = "".join(s.render() if isinstance(s, Section) else str(s) for s in sections)
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>%s</title><style>%s\n%s</style></head><body>"
        "<header><h1>%s</h1><div class='sub'>%s</div></header><main>%s</main>"
        "<footer>Generated by The Voynich Transliteration Tool %s. "
        "This file is self-contained: everything except the manuscript page images is embedded.</footer>"
        "<script>%s\n%s</script></body></html>"
        % (
            esc(title),
            BASE_CSS,
            extra_css,
            esc(title),
            esc(subtitle),
            body,
            esc(__version__),
            FILTER_JS,
            extra_js,
        )
    )


# --------------------------------------------------------------------------
# Heatmaps in pure HTML
# --------------------------------------------------------------------------


def heatmap_html(matrix: list, row_labels: list, column_labels: list, title: str = "") -> str:
    """A coloured grid drawn with table cells, so no plotting library is needed."""
    peak = max((max(row) if row else 0) for row in matrix) if matrix else 0
    head = "".join("<th>%s</th>" % esc(c) for c in column_labels)
    rows = []
    for label, row in zip(row_labels, matrix):
        cells = []
        for value in row:
            intensity = 0.0 if not peak else (value / peak) ** 0.45
            colour = "rgba(122, 92, 46, %.3f)" % intensity
            cells.append("<td style='background:%s' title='%s'></td>" % (colour, esc("%s: %s" % (label, value))))
        rows.append("<tr><th>%s</th>%s</tr>" % (esc(label), "".join(cells)))
    caption = "<p class='why'>%s</p>" % esc(title) if title else ""
    return (
        "%s<div class='scroll'><table class='hm'><thead><tr><th></th>%s</tr></thead><tbody>%s</tbody></table></div>"
        % (
            caption,
            head,
            "".join(rows),
        )
    )


# --------------------------------------------------------------------------
# Plots
# --------------------------------------------------------------------------


def _pyplot():
    matplotlib = optional_import("matplotlib")
    if matplotlib is None:
        raise DependencyError(
            "matplotlib is not installed, so image plots cannot be drawn",
            hint="Install it with: pip install matplotlib   (or set the plugin's 'format' to 'html')",
        )
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def zipf_plot(profile, path, references: bool = True, label: str = "your transliteration", overlays: list = ()):
    """Log-log rank against frequency, with reference slopes."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.loglog(profile.ranks, profile.frequencies, ".", markersize=5, alpha=0.75, label=label)
    if profile.frequencies:
        top = profile.frequencies[0]
        if references:
            for name, slope in ZIPF_REFERENCES:
                ax.loglog(
                    profile.ranks,
                    [top / (r**slope) for r in profile.ranks],
                    linewidth=1.1,
                    alpha=0.55,
                    linestyle="--",
                    label="%s (s=%.2f)" % (name, slope),
                )
    for name, ranks, freqs in overlays:
        ax.loglog(ranks, freqs, ".", markersize=3, alpha=0.5, label=name)
    ax.set_title("Zipf's law: word rank against frequency")
    ax.set_xlabel("rank (log scale)")
    ax.set_ylabel("frequency (log scale)")
    ax.grid(True, which="both", alpha=0.2)
    ax.legend(fontsize=9, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def heaps_plot(points, k: float, beta: float, path, label: str = "your transliteration"):
    """Vocabulary growth: how fast new word types appear."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(11, 6.5))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs, ys, ".", markersize=5, label=label)
    if xs:
        ax.plot(xs, [k * (x**beta) for x in xs], "-", linewidth=1.4, label="Heaps fit: %.2f n^%.3f" % (k, beta))
    ax.set_title("Heaps' law: vocabulary growth")
    ax.set_xlabel("tokens read")
    ax.set_ylabel("distinct word types")
    ax.grid(True, alpha=0.2)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def word_length_plot(profile, path, references: dict = None):
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(11, 6.5))
    total = profile.total or 1
    xs = sorted(profile.counts)
    ax.bar(xs, [profile.counts[x] / total for x in xs], alpha=0.7, label="your transliteration")
    n, p = profile.binomial_n, profile.binomial_p
    if n:
        fit = [math.comb(n, k) * p**k * (1 - p) ** (n - k) if k <= n else 0 for k in xs]
        ax.plot(xs, fit, "-", linewidth=1.6, label="binomial fit (n=%d, p=%.3f)" % (n, p))
    for name, dist in (references or {}).items():
        ref_total = sum(dist.values()) or 1
        ax.plot(sorted(dist), [dist[k] / ref_total for k in sorted(dist)], "--", linewidth=1.1, alpha=0.7, label=name)
    ax.set_title("Word length distribution")
    ax.set_xlabel("characters per word")
    ax.set_ylabel("share of words")
    ax.grid(True, alpha=0.2)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def matrix_plot(matrix, row_labels, column_labels, path, title: str = ""):
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(max(7, len(column_labels) * 0.32), max(6, len(row_labels) * 0.32)))
    image = ax.imshow(matrix, aspect="auto", cmap="magma")
    ax.set_xticks(range(len(column_labels)))
    ax.set_xticklabels(column_labels, fontsize=7, rotation=90)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=7)
    ax.set_title(title or "transition matrix")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plotly_zipf(profile, path, label: str = "your transliteration") -> str:
    """An interactive Zipf plot, when Plotly is installed."""
    plotly = optional_import("plotly")
    if plotly is None:
        raise DependencyError(
            "plotly is not installed, so interactive plots cannot be produced",
            hint="Install it with: pip install plotly   (or set the plugin's 'interactive' setting to false)",
        )
    import plotly.graph_objects as go

    figure = go.Figure()
    figure.add_trace(go.Scatter(x=profile.ranks, y=profile.frequencies, mode="markers", name=label, marker={"size": 4}))
    if profile.frequencies:
        top = profile.frequencies[0]
        for name, slope in ZIPF_REFERENCES:
            figure.add_trace(
                go.Scatter(
                    x=profile.ranks,
                    y=[top / (r**slope) for r in profile.ranks],
                    mode="lines",
                    name="%s (s=%.2f)" % (name, slope),
                    line={"dash": "dash", "width": 1},
                )
            )
    figure.update_layout(
        title="Zipf's law: word rank against frequency",
        xaxis={"type": "log", "title": "rank"},
        yaxis={"type": "log", "title": "frequency"},
        template="plotly_white",
    )
    figure.write_html(str(path), include_plotlyjs=True, full_html=True)
    return str(path)


# --------------------------------------------------------------------------
# Text and CSV
# --------------------------------------------------------------------------


def write_csv(path, rows: list, headers: list) -> Path:
    import csv

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return target


def write_report(path, title: str, blocks: list) -> Path:
    """A plain-text report: a list of ``(heading, body)`` pairs."""
    lines = [title, "=" * len(title), ""]
    for heading, body in blocks:
        lines.append(heading)
        lines.append("-" * len(heading))
        lines.append(body if isinstance(body, str) else json.dumps(body, indent=2, ensure_ascii=False))
        lines.append("")
    return write_text(path, "\n".join(lines))


def glyph_label(glyph: str) -> str:
    return describe_glyph(glyph) if len(glyph) == 1 else glyph
