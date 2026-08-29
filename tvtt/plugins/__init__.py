"""The plugin system.

Almost every feature in TVTT is a plugin: a single Python file in
``tvtt/plugins/`` that declares what it does, what settings it takes, and one
function that does the work.  Which plugins run is decided entirely by
``plugins.json``::

    {
      "plugins": {
        "entropy":  { "enabled": true },
        "zipf":     { "enabled": true, "settings": { "referenceLines": true } },
        "solver":   { "enabled": false }
      }
    }

Why plugins
-----------
The feature list is long, but nobody needs all of it at once.  A first run
should be small and fast; a serious evaluation can switch on twenty analyses
and go and make coffee.  Plugins make that a one-line change instead of a code
change, and ``tvtt plugins list`` prints every one with a plain-English
description of what it measures and why it matters.

Writing one
-----------
Create ``tvtt/plugins/my_idea.py`` with a module-level ``PLUGIN``::

    from . import Plugin, PluginContext

    def run(ctx: PluginContext) -> dict:
        return {"words": len(ctx.result.words())}

    PLUGIN = Plugin(
        name="my_idea",
        title="My idea",
        stage="analyze",
        summary="Counts words.",
        help="A longer explanation shown by 'tvtt plugins info my_idea'.",
        defaults={},
        run=run,
    )

It is discovered automatically, appears in ``tvtt plugins list``, and can be
switched on from ``plugins.json`` with no other wiring.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..errors import DependencyError, PluginError
from ..logging_util import get_logger
from ..paths import display_path, ws
from ..schema import validate
from ..util import Timer, read_json, write_json

_log = get_logger("plugins")

PLUGINS_FILENAME = "plugins.json"

#: Plugins run in stage order.  ``analyze`` plugins compute numbers; ``report``
#: plugins turn numbers (their own or another plugin's) into files.
STAGES = ("prepare", "analyze", "baseline", "search", "report")


@dataclass
class Plugin:
    """Everything TVTT needs to know about one optional feature."""

    name: str
    title: str
    stage: str
    summary: str
    help: str
    run: Callable[[PluginContext], Any]
    defaults: dict = field(default_factory=dict)
    settings_help: dict = field(default_factory=dict)
    requires: tuple = ()
    optional_requires: tuple = ()
    needs: tuple = ()
    heavy: bool = False
    category: str = "analysis"
    enabled_by_default: bool = False

    def describe_settings(self) -> list:
        rows = []
        for key, value in self.defaults.items():
            rows.append((key, value, self.settings_help.get(key, "")))
        return rows


@dataclass
class PluginContext:
    """What a plugin is handed when it runs."""

    config: Any
    corpus: Any
    result: Any
    settings: dict
    results: dict
    outputs: list
    registry: PluginRegistry
    log: Any

    def setting(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def output_path(self, filename: str) -> Path:
        path = self.config.output_dir() / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def record_output(self, path, description: str = "") -> Path:
        self.outputs.append({"path": str(path), "description": description})
        return path

    def need(self, name: str) -> Any:
        """Fetch another plugin's result, raising a clear error if it is off."""
        if name not in self.results:
            raise PluginError(
                "this feature needs the %r plugin, which is not enabled" % name,
                hint='Set "%s": {"enabled": true} in plugins.json.' % name,
            )
        return self.results[name]

    def require_module(self, module: str, purpose: str = "") -> Any:
        from ..errors import DependencyError
        from ..util import optional_import

        mod = optional_import(module)
        if mod is None:
            raise DependencyError(
                "the optional package %r is not installed%s"
                % (module, (" (needed for %s)" % purpose) if purpose else ""),
                hint="Install it with: pip install %s" % module,
            )
        return mod


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


class PluginRegistry:
    """Discovers plugin modules and applies the ``plugins.json`` settings."""

    def __init__(self) -> None:
        self.plugins: dict = {}
        self.settings: dict = {}
        self.enabled: dict = {}

    # -- discovery -------------------------------------------------------
    def discover(self) -> PluginRegistry:
        for info in pkgutil.iter_modules(__path__):
            if info.name.startswith("_"):
                continue
            module = importlib.import_module("%s.%s" % (__name__, info.name))
            plugin = getattr(module, "PLUGIN", None)
            if plugin is None:
                continue
            if not isinstance(plugin, Plugin):
                raise PluginError("%s.PLUGIN is not a Plugin instance" % module.__name__)
            if plugin.stage not in STAGES:
                raise PluginError(
                    "plugin %r declares unknown stage %r" % (plugin.name, plugin.stage),
                    hint="Valid stages: " + ", ".join(STAGES),
                )
            self.plugins[plugin.name] = plugin
        return self

    # -- configuration ---------------------------------------------------
    def configure(self, document: dict) -> PluginRegistry:
        entries = document.get("plugins", {})
        unknown = [name for name in entries if name not in self.plugins]
        if unknown:
            import difflib

            hints = []
            for name in unknown:
                near = difflib.get_close_matches(name, list(self.plugins), n=1, cutoff=0.6)
                hints.append("%s%s" % (name, (" (did you mean %r?)" % near[0]) if near else ""))
            raise PluginError(
                "plugins.json mentions unknown plugins: " + ", ".join(hints),
                hint="Run 'tvtt plugins list' to see every available plugin.",
            )
        for name, plugin in self.plugins.items():
            entry = entries.get(name, {})
            self.enabled[name] = bool(entry.get("enabled", plugin.enabled_by_default))
            merged = dict(plugin.defaults)
            merged.update(entry.get("settings", {}) or {})
            unknown_settings = [k for k in merged if k not in plugin.defaults]
            if unknown_settings:
                raise PluginError(
                    "plugin %r has no setting(s) named %s" % (name, ", ".join(sorted(unknown_settings))),
                    hint="Known settings: " + (", ".join(plugin.defaults) or "(none)"),
                )
            self.settings[name] = merged
        return self

    # -- queries ---------------------------------------------------------
    def active(self) -> list:
        """Enabled plugins in stage order, with dependencies pulled in first."""
        wanted = {name for name, on in self.enabled.items() if on}
        # Pull in hard dependencies.
        changed = True
        while changed:
            changed = False
            for name in list(wanted):
                for dep in self.plugins[name].requires:
                    if dep not in self.plugins:
                        raise PluginError(
                            "plugin %r requires unknown plugin %r" % (name, dep),
                        )
                    if dep not in wanted:
                        wanted.add(dep)
                        changed = True
        ordered = []
        seen = set()

        def visit(name: str, trail: tuple) -> None:
            if name in seen:
                return
            if name in trail:
                raise PluginError("plugins form a dependency cycle: " + " -> ".join(trail + (name,)))
            for dep in self.plugins[name].requires:
                visit(dep, trail + (name,))
            for dep in self.plugins[name].optional_requires:
                if dep in wanted:
                    visit(dep, trail + (name,))
            seen.add(name)
            ordered.append(name)

        for stage in STAGES:
            for name in sorted(wanted):
                if self.plugins[name].stage == stage:
                    visit(name, ())
        return [self.plugins[n] for n in ordered]

    def by_category(self) -> dict:
        out: dict = {}
        for plugin in self.plugins.values():
            out.setdefault(plugin.category, []).append(plugin)
        for items in out.values():
            items.sort(key=lambda p: p.name)
        return dict(sorted(out.items()))

    def get(self, name: str) -> Plugin:
        plugin = self.plugins.get(name)
        if plugin is None:
            raise PluginError(
                "unknown plugin %r" % name,
                hint="Run 'tvtt plugins list' to see every available plugin.",
            )
        return plugin

    # -- execution -------------------------------------------------------
    def run_all(self, context_factory: Callable[[Plugin, dict], PluginContext]) -> dict:
        """Run every enabled plugin, collecting results, timings and skips.

        A plugin that needs an optional package which is not installed is
        skipped with a warning rather than failing the run. Losing one picture
        should not throw away the twenty analyses that already succeeded, and
        the warning appears in the run summary and the manifest so the omission
        is never silent.
        """
        results: dict = {}
        timings: dict = {}
        skipped: dict = {}
        for plugin in self.active():
            settings = self.settings.get(plugin.name, dict(plugin.defaults))
            ctx = context_factory(plugin, settings)
            ctx.results = results
            _log.info("running plugin: %s", plugin.title)
            try:
                with Timer() as timer:
                    value = plugin.run(ctx)
            except (DependencyError, PluginError) as exc:
                if not getattr(exc, "skippable", False):
                    raise
                skipped[plugin.name] = str(exc.message)
                _log.warning("skipping %s: %s", plugin.name, exc.message)
                continue
            except Exception as exc:  # pragma: no cover - plugin bugs
                raise PluginError(
                    "plugin %r failed: %s" % (plugin.name, exc),
                    hint="Disable it in plugins.json to continue without it.",
                ) from exc
            timings[plugin.name] = timer.elapsed
            if value is not None:
                results[plugin.name] = value
                # A plugin that decided it had nothing to do has to say so out
                # loud. Returning a reason nobody reads is the same as silence.
                if isinstance(value, dict):
                    reason = value.get("skipped") or value.get("error")
                    if reason:
                        skipped[plugin.name] = str(reason)
                        _log.warning("%s did nothing: %s", plugin.name, reason)
        results.setdefault("_timings", timings)
        results.setdefault("_skipped", skipped)
        return results


# --------------------------------------------------------------------------
# plugins.json
# --------------------------------------------------------------------------


def default_document(registry: PluginRegistry) -> dict:
    """The ``plugins.json`` that ``tvtt init`` writes: every plugin listed."""
    entries = {}
    for name in sorted(registry.plugins):
        plugin = registry.plugins[name]
        entry: dict = {"enabled": plugin.enabled_by_default}
        if plugin.defaults:
            entry["settings"] = dict(plugin.defaults)
        entries[name] = entry
    return {
        "note": (
            "Set enabled to true to switch a feature on. "
            "Run 'tvtt plugins list' for a one-line description of each, or "
            "'tvtt plugins info <name>' for the full explanation and settings."
        ),
        "plugins": entries,
    }


def load_plugins_document(path=None, known: set = None) -> dict:
    """Read plugins.json, then merge advanced_plugins.json over it.

    Either file may use the simple feature vocabulary or the full per-plugin
    form; whichever it contains is detected and expanded.
    """
    from ..config import deep_merge, load_schema
    from ..simpleconfig import (
        ADVANCED_PLUGINS,
        expand_simple_plugins,
        is_simple_plugins,
        strip_comment_keys,
    )

    target = Path(path) if path else ws(PLUGINS_FILENAME)
    advanced = target.parent / ADVANCED_PLUGINS

    def read(candidate: Path) -> dict:
        raw = read_json(candidate)
        raw.pop("$schema", None)
        if is_simple_plugins(raw) or not any(k for k in raw if not k.startswith(("_", "$")) and k != "note"):
            return expand_simple_plugins(strip_comment_keys(raw), known)
        raw.pop("note", None)
        return raw

    document: dict = {}
    sources = []
    if target.exists():
        document = deep_merge(document, read(target))
        sources.append(str(target))
    if not path and advanced.exists():
        document = deep_merge(document, read(advanced))
        sources.append(str(advanced))
    if not document:
        return {"plugins": {}}

    schema = load_schema("plugins.schema.json")
    if schema:
        validate(document, schema, source=" and ".join(sources))
    return document


def write_plugins_document(registry: PluginRegistry, path=None, force: bool = False) -> Path:
    """Write ``advanced_plugins.json``: every plugin, with all its settings."""
    from ..simpleconfig import ADVANCED_PLUGINS

    target = Path(path) if path else ws(ADVANCED_PLUGINS)
    if target.exists() and not force:
        raise PluginError("%s already exists" % display_path(target), hint="Pass --force to overwrite it.")
    document = default_document(registry)
    document["note"] = (
        "Every plugin with all of its settings. This file is merged on top of plugins.json, "
        "so you only need to keep the entries you actually change. Delete it to go back to "
        "the simple feature switches alone."
    )
    return write_json(target, document)


def merge_plugin_overrides(document: dict, overrides: dict, known) -> dict:
    """Fold ``--set plugins.<name>.<key>=<value>`` into the plugins document.

    ``enabled`` is the one key that lives beside a plugin's settings rather than
    inside them; everything else is a setting. Unknown names are refused here
    rather than in :meth:`PluginRegistry.configure`, so that the error blames
    the command line instead of plugins.json.
    """
    import difflib

    document = dict(document)
    entries = {name: dict(entry) for name, entry in document.get("plugins", {}).items()}
    for name, values in overrides.items():
        if name not in known:
            near = difflib.get_close_matches(name, sorted(known), n=1, cutoff=0.6)
            raise PluginError(
                "--set plugins.%s: no such plugin%s" % (name, (" (did you mean %r?)" % near[0]) if near else ""),
                hint="Run 'tvtt plugins list' to see every available plugin.",
            )
        if not isinstance(values, dict):
            raise PluginError(
                "--set plugins.%s needs a setting to change" % name,
                hint="For example: --set plugins.%s.enabled=true" % name,
            )
        entry = entries.setdefault(name, {})
        settings = dict(entry.get("settings", {}) or {})
        for key, value in values.items():
            if key == "enabled":
                entry["enabled"] = bool(value)
            else:
                settings[key] = value
        entry["settings"] = settings
    document["plugins"] = entries
    return document


def build_registry(path=None, overrides: dict = None) -> PluginRegistry:
    """Discover plugins and apply the plugin settings files."""
    registry = PluginRegistry().discover()
    document = load_plugins_document(path, known=set(registry.plugins))
    if overrides:
        document = merge_plugin_overrides(document, overrides, set(registry.plugins))
    registry.configure(document)
    return registry
