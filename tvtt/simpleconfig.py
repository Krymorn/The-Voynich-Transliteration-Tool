"""The beginner-facing settings files, and how they relate to the full ones.

There are two levels, and you only ever need the first:

``config.json`` / ``plugins.json``
    Short, flat, and written in plain words. About ten settings between them.
    This is what ``tvtt init`` creates and what most people will ever edit.

``advanced_config.json`` / ``advanced_plugins.json``
    The complete set: every ambiguity policy, every rule-precedence option,
    every per-plugin setting. Created only when you ask for it with
    ``tvtt init --advanced``, and merged *on top of* the simple file, so an
    advanced file only has to mention what it changes.

The simple files are not a cut-down mode - they are a different vocabulary for
the same engine. ``"section": "herbal_a"`` in the simple file means exactly
what ``"selection": {"sections": ["herbal_a"]}`` means in the advanced one.
Nothing is unreachable from the simple file plus the command line; the advanced
file just stops you having to remember which nested block a setting lives in.
"""

from __future__ import annotations

from pathlib import Path

from .errors import ConfigError
from .paths import ws
from .util import read_json, write_json

SIMPLE_CONFIG = "config.json"
ADVANCED_CONFIG = "advanced_config.json"
SIMPLE_PLUGINS = "plugins.json"
ADVANCED_PLUGINS = "advanced_plugins.json"


# --------------------------------------------------------------------------
# The simple config
# --------------------------------------------------------------------------

#: Each entry maps a friendly top-level key to a dotted path in the full
#: config, with a one-line explanation used when the file is written.
SIMPLE_KEYS = {
    "transcription": (
        "transcription",
        "Which transliteration to read. Run 'tvtt sources' to see them all.",
    ),
    "mapping": (
        "mapping.file",
        "Your mapping file. Run 'tvtt mapping list' to see what you have.",
    ),
    "section": (
        "selection.sections",
        "Which part of the manuscript: one of the names from 'tvtt sections', or \"\" for all of it.",
    ),
    "currier": (
        "selection.currier",
        'Restrict to a Currier language: "A", "B", or "any".',
    ),
    "scribe": (
        "selection.scribes",
        'Restrict to one scribe, 1 to 5, or "" for all of them.',
    ),
    "textKind": (
        "selection.textClass",
        'Which kind of text: "all", "running" (paragraphs) or "labels".',
    ),
    "language": (
        "reference.language",
        "The language you are testing against. Run 'tvtt dictionaries' for the list.",
    ),
    "outputFolder": (
        "output.directory",
        "Where results go. Each run gets its own sub-folder inside it.",
    ),
    "keepEveryRun": (
        "output.separateRunFolders",
        "true keeps every run in its own folder; false reuses one folder and overwrites.",
    ),
    "seed": (
        "random.seed",
        "Random seed. The same seed always gives the same results.",
    ),
}

#: Values written by ``tvtt init``.
SIMPLE_DEFAULTS = {
    "transcription": "zl",
    "mapping": "mappings/identity_zl.json",
    "section": "",
    "currier": "any",
    "scribe": "",
    "textKind": "all",
    "language": "latin",
    "outputFolder": "output",
    "keepEveryRun": True,
    "seed": 20260828,
}

#: Simple keys whose full-config counterpart is a list.
_LIST_KEYS = {"section": "selection.sections", "scribe": "selection.scribes"}


#: Blocks that only ever appear in the full form.
_FULL_ONLY = ("selection", "ambiguity", "performance", "logging", "random", "network", "reference")

#: Simple names with no counterpart in the full form. ``transcription`` is
#: deliberately absent: it is spelled the same in both, so its presence says
#: nothing about which form a file is written in. ``mapping`` is shared too,
#: and is only a simple key when its value is a plain string.
_SIMPLE_ONLY = tuple(k for k in SIMPLE_KEYS if k not in ("transcription", "mapping"))


def _full_keys_present(data: dict) -> list:
    found = [key for key in _FULL_ONLY if key in data]
    if isinstance(data.get("mapping"), dict):
        found.append("mapping")
    if isinstance(data.get("output"), dict):
        found.append("output")
    return found


def _simple_keys_present(data: dict) -> list:
    found = [key for key in _SIMPLE_ONLY if key in data]
    if isinstance(data.get("mapping"), str):
        found.append("mapping")
    return found


def is_simple_config(data: dict) -> bool:
    """True when a document uses the simple vocabulary rather than the full one.

    A document that mixes the two is rejected outright rather than guessed at,
    because silently ignoring half of somebody's settings is the worst possible
    outcome here.
    """
    if not isinstance(data, dict):
        return False
    full = _full_keys_present(data)
    simple = _simple_keys_present(data)
    if full and simple:
        raise ConfigError(
            "config.json mixes the simple settings (%s) with the full ones (%s)."
            % (", ".join(sorted(simple)), ", ".join(sorted(full))),
            hint=(
                "Use one style or the other. Keep the simple names in config.json, and put "
                "full-form settings in advanced_config.json, where they are merged on top. "
                "'tvtt init --advanced' creates that file for you."
            ),
        )
    return bool(simple)


def expand_simple_config(data: dict) -> dict:
    """Turn the simple vocabulary into a full config document."""
    unknown = [k for k in data if k not in SIMPLE_KEYS and not k.startswith("$") and k != "note"]
    if unknown:
        import difflib

        hints = []
        for key in unknown:
            near = difflib.get_close_matches(key, list(SIMPLE_KEYS), n=1, cutoff=0.6)
            hints.append("%s%s" % (key, (" (did you mean %r?)" % near[0]) if near else ""))
        raise ConfigError(
            "config.json has setting(s) TVTT does not recognise: " + ", ".join(hints),
            hint="The simple settings are: %s. For the full set, run 'tvtt init --advanced'." % ", ".join(SIMPLE_KEYS),
        )

    out: dict = {}
    for key, value in data.items():
        if key not in SIMPLE_KEYS:
            continue
        dotted, _help = SIMPLE_KEYS[key]
        if key in _LIST_KEYS:
            if value in ("", None, []):
                continue
            value = [str(v) for v in value] if isinstance(value, list) else [str(value)]
        if value == "" and key in ("mapping", "transcription"):
            continue
        _assign(out, dotted, value)
    return out


def _assign(target: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    node = target
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def write_simple_config(path=None, mapping: str = "", transcription: str = "zl") -> Path:
    """Write the short, friendly ``config.json``."""
    target = Path(path) if path else ws(SIMPLE_CONFIG)
    payload = {
        "note": (
            'The everyday settings. Anything left as "" or "any" means \'do not restrict\'. '
            "Run 'tvtt init --advanced' if you need the full set of options."
        )
    }
    values = dict(SIMPLE_DEFAULTS)
    values["transcription"] = transcription
    if mapping:
        values["mapping"] = mapping
    for key, value in values.items():
        payload["_" + key] = SIMPLE_KEYS[key][1]
        payload[key] = value
    # The "_key" comment lines are stripped back out before validation.
    return write_json(target, payload)


def strip_comment_keys(data: dict) -> dict:
    """Remove the ``_key`` explanation lines the simple file carries."""
    return {k: v for k, v in data.items() if not k.startswith("_") and k != "note"}


# --------------------------------------------------------------------------
# The simple plugins file
# --------------------------------------------------------------------------

#: Friendly names for the things a beginner actually wants to switch on,
#: each standing for one or more plugins.
SIMPLE_FEATURES = {
    "readableText": (
        ["transliteration", "legend"],
        "Write the transliterated text and a glyph cheat sheet.",
    ),
    "webReport": (
        ["html_report"],
        "One web page with the text, the manuscript images and the statistics.",
    ),
    "basicStatistics": (
        ["frequency", "entropy", "word_length", "vocabulary", "zipf"],
        "The usual measurements: frequencies, entropy, word length, vocabulary, Zipf.",
    ),
    "checkMyMapping": (
        ["roundtrip", "conflicts"],
        "Check the mapping is reversible and that no two rules contradict each other.",
    ),
    "deeperStatistics": (
        ["ngrams", "positional", "slot_grammar", "affixes", "repeats", "line_effects", "vowels"],
        "The harder measurements: transitions, positions, slot grammar, affixes, repetition, line effects, vowels.",
    ),
    "comparePartsOfTheBook": (
        ["section_report", "glyph_heatmap"],
        "Run everything per manuscript section and show where they differ.",
    ),
    "compareWithRealLanguage": (
        ["corpus_match", "language_controls"],
        "Match the output against a real dictionary, and against real languages.",
    ),
    "amIFoolingMyself": (
        ["random_controls", "match_significance", "shuffles", "synthetic", "holdout", "overfitting"],
        "The honesty checks: random mappings, shuffles, a null model, held-out text, overfitting.",
    ),
    "pictures": (
        ["plots", "wordcloud"],
        "Charts and a word cloud. Needs matplotlib for the charts.",
    ),
    "findAMappingForMe": (
        ["solve"],
        "Search automatically for a mapping. Slow, and read the warnings it prints.",
    ),
}

SIMPLE_PLUGIN_DEFAULTS = {
    "readableText": True,
    "webReport": True,
    "basicStatistics": True,
    "checkMyMapping": True,
    "deeperStatistics": False,
    "comparePartsOfTheBook": False,
    "compareWithRealLanguage": False,
    "amIFoolingMyself": False,
    "pictures": False,
    "findAMappingForMe": False,
}


def is_simple_plugins(data: dict) -> bool:
    """True for the friendly feature switches, False for the per-plugin form."""
    if not isinstance(data, dict):
        return False
    simple = [key for key in data if key in SIMPLE_FEATURES]
    if "plugins" in data and simple:
        raise ConfigError(
            "plugins.json mixes the simple feature switches (%s) with a 'plugins' block." % ", ".join(sorted(simple)),
            hint=(
                "Use one style or the other. Keep the feature switches in plugins.json, and "
                "put the per-plugin block in advanced_plugins.json, where it is merged on top. "
                "'tvtt init --advanced' creates that file for you."
            ),
        )
    if "plugins" in data:
        return False
    return bool(simple)


def expand_simple_plugins(data: dict, known: set = None) -> dict:
    """Turn the friendly feature switches into a full plugins document."""
    unknown = [k for k in data if k not in SIMPLE_FEATURES and not k.startswith("$") and k != "note"]
    if unknown:
        import difflib

        hints = []
        for key in unknown:
            near = difflib.get_close_matches(key, list(SIMPLE_FEATURES), n=1, cutoff=0.6)
            hints.append("%s%s" % (key, (" (did you mean %r?)" % near[0]) if near else ""))
        raise ConfigError(
            "plugins.json has feature(s) TVTT does not recognise: " + ", ".join(hints),
            hint="The simple features are: %s. For per-plugin control, run 'tvtt init --advanced'."
            % ", ".join(SIMPLE_FEATURES),
        )

    entries: dict = {}
    for feature, wanted in data.items():
        if feature not in SIMPLE_FEATURES:
            continue
        names, _help = SIMPLE_FEATURES[feature]
        for name in names:
            if known is not None and name not in known:
                continue
            entries.setdefault(name, {})["enabled"] = bool(wanted) or entries.get(name, {}).get("enabled", False)
    return {"plugins": entries}


def write_simple_plugins(path=None) -> Path:
    """Write the short, friendly ``plugins.json``."""
    target = Path(path) if path else ws(SIMPLE_PLUGINS)
    payload = {
        "note": (
            "Switch features on and off. Each one turns on a group of plugins. "
            "Run 'tvtt plugins list' to see the individual plugins, or "
            "'tvtt init --advanced' to control them one by one."
        )
    }
    for feature, value in SIMPLE_PLUGIN_DEFAULTS.items():
        payload["_" + feature] = SIMPLE_FEATURES[feature][1]
        payload[feature] = value
    return write_json(target, payload)


# --------------------------------------------------------------------------
# Loading, with the advanced file layered on top
# --------------------------------------------------------------------------


def load_layer(simple_path: Path, advanced_path: Path, expand, is_simple, label: str):
    """Read the simple file, then merge the advanced one over it.

    Returns ``(document, sources)`` where ``document`` is in full form and
    ``sources`` names the files that contributed, for error messages.
    """
    from .config import deep_merge

    document: dict = {}
    sources: list = []

    if simple_path.exists():
        raw = read_json(simple_path)
        raw.pop("$schema", None)
        if is_simple(raw) or not raw:
            raw = expand(strip_comment_keys(raw))
        document = deep_merge(document, raw)
        sources.append(str(simple_path))

    if advanced_path.exists():
        raw = read_json(advanced_path)
        raw.pop("$schema", None)
        raw.pop("note", None)
        if is_simple(raw):
            raw = expand(strip_comment_keys(raw))
        _warn_about_overrides(document, raw, simple_path, advanced_path)
        document = deep_merge(document, raw)
        sources.append(str(advanced_path))

    return document, sources


def _flatten(document: dict, prefix: str = "") -> dict:
    """Every leaf setting as a dotted path, for comparing two documents."""
    flat: dict = {}
    for key, value in document.items():
        path = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        else:
            flat[path] = value
    return flat


def _warn_about_overrides(simple: dict, advanced: dict, simple_path: Path, advanced_path: Path) -> None:
    """Say when the advanced file is quietly cancelling the simple one.

    ``tvtt init --advanced`` writes every setting at its default, so an
    untouched advanced file overrides everything the simple file says. Someone
    who then edits config.json sees no effect and no explanation, which is the
    same silent-mismatch failure the mixed-plugin-style check exists to
    prevent.
    """
    if not simple:
        return
    from .logging_util import get_logger

    lhs, rhs = _flatten(simple), _flatten(advanced)
    clashes = sorted(key for key, value in lhs.items() if key in rhs and rhs[key] != value)
    if not clashes:
        return
    shown = ", ".join(clashes[:4]) + (", ..." if len(clashes) > 4 else "")
    get_logger("config").warning(
        "%s overrides %s for: %s. The advanced file wins; delete those lines from it to let %s take effect.",
        advanced_path.name,
        simple_path.name,
        shown,
        simple_path.name,
    )
