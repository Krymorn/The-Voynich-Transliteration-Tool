"""A local web app for editing a mapping and seeing the result immediately.

``tvtt web`` starts a small server on your own machine and opens a page with
the mapping on the left and the transliterated text on the right.  Change a
rule and the text updates as you type; the statistics recompute when you ask.

It is built on Python's own ``http.server``, so there is nothing to install -
no Flask, no Node, no build step.  Nothing is sent anywhere: the server binds
to localhost, and the only outbound requests the page can make are for the
manuscript's page images, which you can switch off.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from ..analysis import entropy_profile, stat_bundle, vocabulary_profile, word_length_profile
from ..config import Config
from ..corpus import load_corpus
from ..fonts import choose_font
from ..logging_util import get_logger
from ..mapping import SLOT_BY_NAME, SLOT_NAMES, SLOT_PLAIN, Mapping
from ..profiles import list_profiles, save_mapping
from ..transliterate import build_engine, transliterate

_log = get_logger("web")


class _State:
    """Everything the server keeps between requests."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.corpus = load_corpus(config.get("transcription", "zl"), config.parse_options(), config.selection())
        path = config.mapping_path()
        self.mapping = Mapping.load(path, config.markers()) if path.exists() else Mapping()
        self.lock = threading.Lock()

    def engine(self, rules: dict = None):
        mapping = self.mapping
        if rules is not None:
            mapping = Mapping(rules=_decode_rules(rules), meta=dict(self.mapping.meta))
        return build_engine(
            mapping,
            self.corpus,
            markers=self.config.markers(),
            precedence=tuple(self.config.get("mapping.precedence", ("initial", "final", "occurrence", "plain"))),
            unmapped=self.config.get("mapping.unmapped", "keep"),
            placeholder=self.config.get("mapping.placeholder", "?"),
        )


def _decode_rules(rules: dict) -> dict:
    out = {}
    for glyph, slots in rules.items():
        if isinstance(slots, str):
            out[glyph] = {SLOT_PLAIN: slots}
            continue
        decoded = {}
        for name, value in slots.items():
            slot = SLOT_BY_NAME.get(name)
            if slot is not None and value != "":
                decoded[slot] = value
        if decoded:
            out[glyph] = decoded
    return out


def _encode_rules(mapping: Mapping) -> dict:
    return {glyph: {SLOT_NAMES[slot]: text for slot, text in slots.items()} for glyph, slots in mapping.rules.items()}


class _Handler(BaseHTTPRequestHandler):
    state: _State = None
    server_version = "TVTT"

    def log_message(self, fmt, *args):  # noqa: A003 - silence the default logging
        _log.debug(fmt, *args)

    # -- routing ---------------------------------------------------------
    def do_GET(self):  # noqa: N802 - http.server API
        route = urlparse(self.path).path
        if route in ("/", "/index.html"):
            return self._send_html(_page(self.state))
        if route == "/api/state":
            return self._send_json(self._state_payload())
        if route == "/api/profiles":
            return self._send_json({"profiles": [p.name for p in list_profiles()]})
        return self._send_json({"error": "not found"}, status=404)

    def do_POST(self):  # noqa: N802 - http.server API
        route = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid JSON"}, status=400)

        if route == "/api/preview":
            return self._send_json(self._preview(body))
        if route == "/api/stats":
            return self._send_json(self._stats(body))
        if route == "/api/save":
            return self._send_json(self._save(body))
        return self._send_json({"error": "not found"}, status=404)

    # -- handlers --------------------------------------------------------
    def _state_payload(self) -> dict:
        state = self.state
        counts = state.corpus.glyph_counts()
        total = sum(counts.values()) or 1
        from ..fonts import display_text, is_code_glyph

        glyphs = [
            {
                "glyph": glyph,
                # What the Voynich font can actually draw.
                "rendered": display_text(glyph),
                # The @nnn; code, shown as ordinary text beside it.
                "code": _display(glyph) if is_code_glyph(glyph) else "",
                "count": count,
                "share": round(100 * count / total, 3),
            }
            for glyph, count in counts.most_common()
        ]
        return {
            "transcription": state.corpus.title,
            "alphabet": state.corpus.alphabet,
            "selection": state.corpus.selection.describe(),
            "lines": len(state.corpus.loci),
            "words": len(state.corpus.words()),
            "glyphs": glyphs,
            "rules": _encode_rules(state.mapping),
            "meta": state.mapping.meta,
            "slots": list(SLOT_BY_NAME),
            "mappingFile": str(state.config.mapping_path()),
        }

    def _preview(self, body: dict) -> dict:
        from ..fonts import display_text

        state = self.state
        limit = int(body.get("limit", 60))
        with state.lock:
            engine = state.engine(body.get("rules"))
            separator = state.config.get("output.wordSeparator", " ")
            uncertain = state.config.get("output.uncertainWordSeparator", " ")
            rows = []
            for locus in state.corpus.loci[:limit]:
                rows.append(
                    {
                        "locus": locus.locus_id,
                        "source": display_text(locus.text),
                        "output": engine.map_line(locus.text, separator, uncertain),
                    }
                )
            collisions = engine.collisions()
        return {
            "lines": rows,
            "collisions": {k: [g for g, _ in v] for k, v in list(collisions.items())[:30]},
            "injective": not collisions,
        }

    def _stats(self, body: dict) -> dict:
        state = self.state
        with state.lock:
            engine = state.engine(body.get("rules"))
            result = transliterate(state.corpus, engine)
            words = result.words()
            bundle = stat_bundle(words, "current")
            entropy = entropy_profile(words)
            lengths = word_length_profile(words)
            vocabulary = vocabulary_profile(words)
            top = Counter(words).most_common(25)
        return {
            "headline": bundle.to_dict(),
            "entropy": entropy.to_dict(),
            "wordLength": {
                "mean": round(lengths.mean, 3),
                "dispersion": round(lengths.dispersion, 3),
                "verdict": lengths.verdict(),
            },
            "vocabulary": vocabulary.to_dict(),
            "topWords": top,
        }

    def _save(self, body: dict) -> dict:
        state = self.state
        name = (body.get("name") or "").strip()
        rules = _decode_rules(body.get("rules") or {})
        if not name:
            return {"error": "give the mapping a name"}
        with state.lock:
            mapping = Mapping(rules=rules, meta=dict(state.mapping.meta))
            mapping.meta["name"] = name
            path = save_mapping(mapping, name, note=body.get("note", "saved from the web app"))
            state.mapping = mapping
        return {"saved": str(path), "rules": len(rules)}

    # -- plumbing --------------------------------------------------------
    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _display(glyph: str) -> str:
    from ..ivtff import high_ascii_label

    return high_ascii_label(glyph) if len(glyph) == 1 else glyph


def serve(config: Config, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Start the local editor and block until interrupted."""
    state = _State(config)
    handler = type("Handler", (_Handler,), {"state": state})
    httpd = ThreadingHTTPServer((host, port), handler)
    url = "http://%s:%d/" % (host, port)
    print("TVTT mapping editor running at %s" % url)
    print("  transcription : %s" % state.corpus.title)
    print("  selection     : %s" % state.corpus.selection.describe())
    print("  mapping       : %s" % config.mapping_path())
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------


def _page(state: _State) -> str:
    from ..reporting import BASE_CSS, esc

    font = choose_font("", state.corpus.alphabet)
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TVTT mapping editor</title>
<style>%s
%s
.voy { font-family: %s; }
.editor { display: grid; grid-template-columns: minmax(320px, 420px) 1fr; gap: 18px; align-items: start; }
@media (max-width: 900px) { .editor { grid-template-columns: 1fr; } }
.rule { display: grid; grid-template-columns: 74px 58px 1fr; gap: 8px; align-items: center;
  padding: 4px 6px; border-bottom: 1px solid var(--line); }
.rule input { width: 100%%; font: inherit; padding: 4px 7px; border: 1px solid var(--line);
  border-radius: 6px; background: var(--bg); color: var(--ink); }
.rule .g { font-size: 19px; line-height: 1.1; }
.rule .g .code { font-family: ui-monospace, monospace; font-size: 10px;
  color: var(--muted); letter-spacing: 0; }
.rule .c { color: var(--muted); font-size: 12px; text-align: right; }
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
button { font: inherit; padding: 7px 13px; border-radius: 7px; border: 1px solid var(--line);
  background: var(--accent-soft); color: var(--accent); cursor: pointer; }
button:hover { filter: brightness(1.06); }
#status { color: var(--muted); font-size: 13px; }
details.adv { margin-top: 4px; }
</style></head><body>
<header><h1>TVTT mapping editor</h1>
<div class="sub">%s &middot; %s &middot; %d lines, %d words &middot; editing %s</div></header>
<main>
<div class="toolbar">
  <input type="search" id="glyph-filter" placeholder="filter glyphs">
  <input type="text" id="save-name" placeholder="save as (profile name)" value="%s">
  <button id="save">Save mapping</button>
  <button id="stats">Recompute statistics</button>
  <span id="status">ready</span>
</div>
<div class="editor">
  <section><h2>Rules</h2><p class="why">Type a replacement next to a glyph. The preview updates as you type. Open the arrow for positional rules.</p><div id="rules" class="scroll" style="max-height:70vh"></div></section>
  <div>
    <section><h2>Preview</h2><p class="why">Source on the left, your mapping on the right.</p><div id="preview" class="scroll" style="max-height:44vh"></div></section>
    <section><h2>Statistics</h2><p class="why">Press "Recompute statistics" after a change; they are computed over the whole selection.</p><div id="statistics"><p class="why">Not computed yet.</p></div></section>
  </div>
</div>
</main>
<script>
const SLOTS = ["plain","initial","final","occurrence1","occurrence2","occurrence3","occurrence4"];
let STATE = null, RULES = {}, timer = null;

function setStatus(text) { document.getElementById('status').textContent = text; }

async function load() {
  STATE = await (await fetch('/api/state')).json();
  RULES = STATE.rules || {};
  renderRules();
  preview();
}

function renderRules() {
  const filter = (document.getElementById('glyph-filter').value || '').toLowerCase();
  const host = document.getElementById('rules');
  host.innerHTML = '';
  for (const g of STATE.glyphs) {
    var hay = ((g.code || '') + ' ' + g.glyph).toLowerCase();
    if (filter && hay.indexOf(filter) < 0) continue;
    const row = document.createElement('div');
    row.className = 'rule';
    const label = document.createElement('div');
    label.className = 'g voy';
    label.textContent = g.rendered;
    if (g.code) {
      // A @nnn; glyph: draw the shape, and show its code as ordinary text.
      // Putting the code itself in the Voynich font would render '@', '1',
      // '1', '3', ';' as five unrelated Voynich glyphs.
      const code = document.createElement('div');
      code.className = 'code';
      code.textContent = g.code;
      label.appendChild(code);
    }
    const count = document.createElement('div');
    count.className = 'c';
    count.textContent = g.count;
    const box = document.createElement('div');
    const input = document.createElement('input');
    input.value = (RULES[g.glyph] && RULES[g.glyph].plain) || '';
    input.placeholder = 'becomes';
    input.addEventListener('input', () => { setRule(g.glyph, 'plain', input.value); schedule(); });
    box.appendChild(input);
    const adv = document.createElement('details');
    adv.className = 'adv';
    const sum = document.createElement('summary');
    sum.textContent = 'positional rules';
    adv.appendChild(sum);
    for (const slot of SLOTS.slice(1)) {
      const sub = document.createElement('input');
      sub.style.marginTop = '5px';
      sub.placeholder = slot;
      sub.value = (RULES[g.glyph] && RULES[g.glyph][slot]) || '';
      sub.addEventListener('input', () => { setRule(g.glyph, slot, sub.value); schedule(); });
      adv.appendChild(sub);
    }
    box.appendChild(adv);
    row.appendChild(label); row.appendChild(count); row.appendChild(box);
    host.appendChild(row);
  }
}

function setRule(glyph, slot, value) {
  if (!RULES[glyph]) RULES[glyph] = {};
  if (value === '') delete RULES[glyph][slot]; else RULES[glyph][slot] = value;
  if (Object.keys(RULES[glyph]).length === 0) delete RULES[glyph];
}

function schedule() { clearTimeout(timer); timer = setTimeout(preview, 1000); }

async function preview() {
  setStatus('updating preview...');
  const res = await (await fetch('/api/preview', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({rules: RULES, limit: 10000})})).json();
  const host = document.getElementById('preview');
  host.innerHTML = '';
  for (const line of res.lines) {
    const row = document.createElement('div');
    row.className = 'line';
    row.innerHTML = '<div class="loc"></div><div class="src voy"></div><div class="out"></div>';
    row.children[0].textContent = line.locus;
    row.children[1].textContent = line.source;
    row.children[2].textContent = line.output;
    host.appendChild(row);
  }
  const collisions = Object.keys(res.collisions || {}).length;
  setStatus(res.injective ? 'preview updated - mapping is reversible'
                          : 'preview updated - ' + collisions + ' collision(s): the mapping is not reversible');
}

async function stats() {
  setStatus('computing statistics...');
  const res = await (await fetch('/api/stats', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({rules: RULES})})).json();
  const h = res.headline;
  const cells = [
    ['h2 conditional entropy', h.h2, 'manuscript sits near 2.0-2.4'],
    ['mean word length', h.mean_word_length, res.wordLength.verdict],
    ['word types', h.types, h.tokens + ' tokens'],
    ['MATTR', h.mattr, 'type richness'],
    ['Zipf exponent', h.zipf_slope, 'languages sit near 1.0'],
    ['repeat rate', h.immediate_repeat_rate, 'words followed by themselves']
  ];
  let html = '<div class="grid">';
  for (const [k, v, n] of cells) {
    html += '<div class="stat"><div class="k">' + k + '</div><div class="v">' + v + '</div><div class="n">' + n + '</div></div>';
  }
  html += '</div><div class="scroll" style="margin-top:14px"><table><thead><tr><th>word</th><th class="num">count</th></tr></thead><tbody>';
  for (const [w, c] of res.topWords) html += '<tr><td>' + w + '</td><td class="num">' + c + '</td></tr>';
  html += '</tbody></table></div>';
  document.getElementById('statistics').innerHTML = html;
  setStatus('statistics updated');
}

async function save() {
  const name = document.getElementById('save-name').value.trim();
  if (!name) { setStatus('give the mapping a name first'); return; }
  const res = await (await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({rules: RULES, name: name})})).json();
  setStatus(res.error ? res.error : ('saved ' + res.rules + ' rule(s) to ' + res.saved));
}

document.getElementById('glyph-filter').addEventListener('input', renderRules);
document.getElementById('save').addEventListener('click', save);
document.getElementById('stats').addEventListener('click', stats);
load();
</script></body></html>""" % (
        BASE_CSS,
        font.css(),
        font.font_family(),
        esc(state.corpus.title),
        esc(state.corpus.selection.describe()),
        len(state.corpus.loci),
        len(state.corpus.words()),
        esc(state.mapping.meta.get("name", "a new mapping")),
        esc(state.mapping.meta.get("name", "my_mapping")),
    )
