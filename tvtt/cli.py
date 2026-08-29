"""The command line interface.

Everything TVTT does is reachable from ``tvtt <command>``.  Start with::

    tvtt init            create config.json, plugins.json and a starter mapping
    tvtt run             transliterate and run whatever plugins are enabled
    tvtt plugins list    see every optional feature and what it measures

Every command prints something useful with ``--help``, every error explains
what to do about it, and any configuration value can be overridden on the
command line with ``--set key=value`` without editing a file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, cache
from .config import deep_merge, load_config, write_default_config
from .corpus import TRANSCRIPTIONS, load_corpus, resolve_transcription
from .errors import TvttError
from .logging_util import configure, get_logger
from .paths import display_path, set_workspace, transcription_file, ws
from .plugins import PluginRegistry, build_registry, write_plugins_document
from .util import table

PROGRAM = "tvtt"


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------


def _global_options(parser: argparse.ArgumentParser, suppress: bool = False) -> None:
    """Add the options that make sense for every command.

    They are attached both to the top-level parser and to every subcommand, so
    ``tvtt --quiet run`` and ``tvtt run --quiet`` both work. On the subcommand
    copies the defaults are suppressed, so a flag given before the command is
    not silently reset by the subparser's default.
    """
    kwargs = {"default": argparse.SUPPRESS} if suppress else {}
    parser.add_argument(
        "--workspace", metavar="DIR", help="folder holding config.json (default: the current one)", **kwargs
    )
    parser.add_argument("--config", metavar="FILE", help="use a specific config file", **kwargs)
    parser.add_argument("--plugins-file", metavar="FILE", help="use a specific plugins file", **kwargs)
    parser.add_argument("--quiet", action="store_true", help="only show warnings and errors", **kwargs)
    parser.add_argument("--verbose", action="store_true", help="show debug logging", **kwargs)
    parser.add_argument("--json-logs", action="store_true", help="emit one JSON object per log line", **kwargs)
    parser.add_argument("--no-progress", action="store_true", help="never draw progress bars", **kwargs)
    parser.add_argument("--no-cache", action="store_true", help="ignore and do not write the on-disk cache", **kwargs)
    parser.add_argument(
        "--set",
        metavar="KEY=VALUE",
        action="append",
        dest="overrides",
        help="override any config value, e.g. --set selection.currier=B (repeatable)",
        **({"default": argparse.SUPPRESS} if suppress else {"default": []}),
    )


def _common_parent() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    _global_options(parent, suppress=True)
    return parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="The Voynich Transliteration Tool: build, test and stress-test mappings for the Voynich Manuscript.",
        epilog="Start with 'tvtt init', then 'tvtt run'. 'tvtt plugins list' shows every optional feature.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    _global_options(parser)

    common = _common_parent()
    sub = parser.add_subparsers(dest="command", metavar="<command>", parser_class=_subparser_factory(common))

    _add_init(sub)
    _add_run(sub)
    _add_analyze(sub)
    _add_solve(sub)
    _add_mapping(sub)
    _add_plugins(sub)
    _add_info(sub)
    _add_fetch(sub)
    _add_web(sub)
    _add_cache(sub)
    return parser


def _subparser_factory(common: argparse.ArgumentParser):
    """Make every subparser inherit the global options automatically."""

    class _Sub(argparse.ArgumentParser):
        def __init__(self, *args, **kwargs):
            parents = list(kwargs.pop("parents", []))
            if common not in parents:
                parents.append(common)
            kwargs["parents"] = parents
            super().__init__(*args, **kwargs)

    return _Sub


def _add_init(sub) -> None:
    p = sub.add_parser("init", help="create config.json, plugins.json and a starter mapping")
    p.add_argument("--force", action="store_true", help="overwrite files that already exist")
    p.add_argument(
        "--advanced",
        action="store_true",
        help="also write advanced_config.json and advanced_plugins.json with every option",
    )
    p.add_argument(
        "--transcription", default="zl", choices=sorted(TRANSCRIPTIONS), help="which transliteration to set up for"
    )
    p.set_defaults(func=cmd_init)


def _add_run(sub) -> None:
    p = sub.add_parser("run", help="transliterate and run the enabled plugins")
    p.add_argument("--transcription", choices=sorted(TRANSCRIPTIONS), help="override the transcription")
    p.add_argument("--mapping", metavar="FILE", help="override the mapping file")
    p.add_argument("--section", action="append", default=[], help="restrict to a named section (repeatable)")
    p.add_argument("--currier", choices=["any", "A", "B"], help="restrict to a Currier language")
    p.add_argument("--scribe", action="append", default=[], help="restrict to a scribe, 1 to 5 (repeatable)")
    p.add_argument(
        "--text-class", choices=["all", "running", "labels", "circular", "radial"], help="restrict to a kind of text"
    )
    p.add_argument(
        "--lines", choices=["all", "first", "last", "not_first", "single"], help="restrict to a kind of line"
    )
    p.add_argument("--words", choices=["all", "first", "not_first", "last"], help="restrict to a position in the line")
    p.add_argument(
        "--folio", action="append", default=[], help="restrict to a folio or range, e.g. 1r-10v (repeatable)"
    )
    p.add_argument("--seed", type=int, help="random seed for anything stochastic")
    p.add_argument("--output", metavar="DIR", help="where to write results")
    p.add_argument("--plugin", action="append", default=[], help="run only these plugins (repeatable)")
    p.add_argument("--all-plugins", action="store_true", help="run every plugin, ignoring plugins.json")
    p.set_defaults(func=cmd_run)


def _add_analyze(sub) -> None:
    p = sub.add_parser("analyze", help="run only the analysis plugins, without writing text output")
    p.add_argument("--plugin", action="append", default=[], help="run only these plugins (repeatable)")
    p.add_argument("--section", action="append", default=[], help="restrict to a named section")
    p.add_argument("--currier", choices=["any", "A", "B"], help="restrict to a Currier language")
    p.add_argument("--compare-sections", action="store_true", help="shortcut for enabling section_report")
    p.set_defaults(func=cmd_analyze)


def _add_solve(sub) -> None:
    p = sub.add_parser("solve", help="search automatically for a mapping")
    p.add_argument("--method", choices=["hillclimb", "anneal", "genetic"], default="hillclimb")
    p.add_argument(
        "--fitness", choices=["quadgram", "trigram", "bigram", "dictionary", "entropy", "blend"], default="quadgram"
    )
    p.add_argument("--language", help="target language (default: reference.language from config)")
    p.add_argument("--iterations", type=int, help="candidate evaluations for hillclimb and anneal")
    p.add_argument("--restarts", type=int, help="random restarts for hill climbing")
    p.add_argument(
        "--lock", action="append", default=[], metavar="GLYPH=LETTER", help="fix a glyph's letter (repeatable)"
    )
    p.add_argument(
        "--positions",
        choices=["none", "edges", "all"],
        help="let a glyph take a different letter by position: 'edges' for word start and end, "
        "'all' also for the first four occurrences within a word",
    )
    p.add_argument("--swap-only", action="store_true", help="only exchange letters between glyphs")
    p.add_argument("--injective", action="store_true", help="force every glyph to a different letter")
    p.add_argument("--save-as", metavar="NAME", help="save the best mapping as a profile")
    p.add_argument("--seed", type=int, help="random seed")
    p.set_defaults(func=cmd_solve)


def _add_mapping(sub) -> None:
    p = sub.add_parser("mapping", help="create, inspect, compare and share mappings")
    m = p.add_subparsers(dest="action", metavar="<action>")

    q = m.add_parser("init", help="create a mapping listing every glyph in a transcription")
    q.add_argument("name", nargs="?", default="", help="profile name (default: identity_<transcription>)")
    q.add_argument("--transcription", choices=sorted(TRANSCRIPTIONS), help="which alphabet to build for")
    q.add_argument(
        "--frequency-seed",
        metavar="LANGUAGE",
        help="seed by matching glyph frequency to this language's letter frequency",
    )
    q.add_argument("--force", action="store_true", help="overwrite an existing profile")
    q.set_defaults(func=cmd_mapping_init)

    q = m.add_parser("list", help="list the mapping profiles in mappings/")
    q.set_defaults(func=cmd_mapping_list)

    q = m.add_parser("use", help="point config.json at a mapping profile")
    q.add_argument("name")
    q.set_defaults(func=cmd_mapping_use)

    q = m.add_parser("show", help="print a mapping as a table")
    q.add_argument("name", nargs="?", default="")
    q.set_defaults(func=cmd_mapping_show)

    q = m.add_parser("validate", help="check a mapping for collisions and conflicts")
    q.add_argument("name", nargs="?", default="")
    q.set_defaults(func=cmd_mapping_validate)

    q = m.add_parser("diff", help="compare two mappings")
    q.add_argument("left")
    q.add_argument("right")
    q.set_defaults(func=cmd_mapping_diff)

    q = m.add_parser("history", help="list the saved versions of a mapping")
    q.add_argument("name")
    q.set_defaults(func=cmd_mapping_history)

    q = m.add_parser("restore", help="bring back an older version of a mapping")
    q.add_argument("name")
    q.add_argument("version")
    q.set_defaults(func=cmd_mapping_restore)

    q = m.add_parser("export-pack", help="bundle mappings into one shareable file")
    q.add_argument("names", nargs="+")
    q.add_argument("--out", required=True, metavar="FILE")
    q.add_argument("--title", default="")
    q.add_argument("--author", default="")
    q.add_argument("--notes", default="")
    q.set_defaults(func=cmd_mapping_export)

    q = m.add_parser("import-pack", help="unpack a shared mapping pack")
    q.add_argument("path")
    q.add_argument("--prefix", default="", help="prefix imported names to avoid clashes")
    q.add_argument("--overwrite", action="store_true")
    q.set_defaults(func=cmd_mapping_import)

    q = m.add_parser("gallery", help="how to submit a mapping to the community gallery")
    q.set_defaults(func=cmd_mapping_gallery)

    p.set_defaults(func=lambda args: _print_subhelp(p))


def _add_plugins(sub) -> None:
    p = sub.add_parser("plugins", help="see and change which optional features run")
    m = p.add_subparsers(dest="action", metavar="<action>")

    q = m.add_parser("list", help="list every plugin with a one-line description")
    q.add_argument("--category", help="only show one category")
    q.add_argument("--enabled", action="store_true", help="only show enabled plugins")
    q.set_defaults(func=cmd_plugins_list)

    q = m.add_parser("info", help="explain one plugin fully, with its settings")
    q.add_argument("name")
    q.set_defaults(func=cmd_plugins_info)

    q = m.add_parser("enable", help="switch plugins on in plugins.json")
    q.add_argument("names", nargs="+")
    q.set_defaults(func=cmd_plugins_enable)

    q = m.add_parser("disable", help="switch plugins off in plugins.json")
    q.add_argument("names", nargs="+")
    q.set_defaults(func=cmd_plugins_disable)

    q = m.add_parser("set", help="change one plugin setting")
    q.add_argument("name")
    q.add_argument("key")
    q.add_argument("value")
    q.set_defaults(func=cmd_plugins_set)

    q = m.add_parser("preset", help="switch on a ready-made set of plugins")
    q.add_argument("name", nargs="?", default="", choices=["", "quick", "standard", "full", "evaluate", "search"])
    q.set_defaults(func=cmd_plugins_preset)

    p.set_defaults(func=lambda args: _print_subhelp(p))


def _add_info(sub) -> None:
    p = sub.add_parser("sections", help="list the manuscript sections and how big each is")
    p.set_defaults(func=cmd_sections)

    p = sub.add_parser("sources", help="list the available transliterations")
    p.set_defaults(func=cmd_sources)

    p = sub.add_parser("folios", help="list folios with their section, language and scribe")
    p.add_argument("--section", help="only folios in this section")
    p.add_argument("--currier", choices=["A", "B"])
    p.add_argument("--scribe")
    p.set_defaults(func=cmd_folios)

    p = sub.add_parser("build-folios", help="regenerate the folio metadata from a transcription")
    p.add_argument("--transcription", default="zl", help="which transliteration to read it from")
    p.add_argument("--out", default="", help="where to write it (default: data/folios.json here)")
    p.set_defaults(func=cmd_build_folios)

    p = sub.add_parser("dictionaries", help="list the reference dictionaries and control texts")
    p.set_defaults(func=cmd_dictionaries)

    p = sub.add_parser("verify", help="check the checksums of the transcription files on disk")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("doctor", help="check the workspace and report anything that looks wrong")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("runs", help="list previous runs and where their results are")
    p.add_argument("--limit", type=int, default=25, help="how many runs to show")
    p.add_argument("--prune", type=int, metavar="KEEP", help="delete all but the newest KEEP runs")
    p.set_defaults(func=cmd_runs)

    p = sub.add_parser("results", help="rank the runs recorded in results.json")
    p.add_argument("--metric", default="", help="which metric to sort by (default: the best available)")
    p.add_argument("--limit", type=int, default=25, help="how many to show")
    p.set_defaults(func=cmd_results)


def _add_fetch(sub) -> None:
    p = sub.add_parser("fetch", help="download transliterations from voynich.nu and verify them")
    p.add_argument("name", nargs="?", default="", help="which transcription to fetch")
    p.add_argument("--all", action="store_true", help="fetch every transcription")
    p.add_argument("--force", action="store_true", help="download again even if the local copy matches")
    p.set_defaults(func=cmd_fetch)


def _add_web(sub) -> None:
    p = sub.add_parser("web", help="open a local web app for editing a mapping with live preview")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    p.set_defaults(func=cmd_web)


def _add_cache(sub) -> None:
    p = sub.add_parser("cache", help="inspect or clear the on-disk cache")
    p.add_argument("action", nargs="?", default="info", choices=["info", "clear"])
    p.set_defaults(func=cmd_cache)


# --------------------------------------------------------------------------
# Overrides
# --------------------------------------------------------------------------


def _parse_overrides(pairs: list) -> dict:
    out: dict = {}
    for pair in pairs:
        if "=" not in pair:
            raise TvttError(
                "--set expects KEY=VALUE, got %r" % pair,
                hint="For example: --set selection.currier=B",
            )
        key, raw = pair.split("=", 1)
        node = out
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = _coerce(raw)
    return out


def _coerce(raw: str):
    lowered = raw.strip().lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "none"):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    if raw.startswith("[") or raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    if "," in raw:
        return [piece.strip() for piece in raw.split(",") if piece.strip()]
    return raw


def _config_for(args, extra: dict = None):
    overrides = _parse_overrides(args.overrides)
    # "plugins.*" belongs to the plugin registry, not to config.json. Leaving it
    # here would do nothing except change the manifest's configuration hash.
    overrides.pop("plugins", None)
    if extra:
        overrides = deep_merge(overrides, extra)
    config = load_config(args.config, overrides)
    if args.no_cache:
        config.set("performance.cache", False)
    if args.no_progress:
        config.set("performance.progress", False)
    if args.quiet:
        config.set("logging.level", "warning")
    if args.verbose:
        config.set("logging.level", "debug")
    if args.json_logs:
        config.set("logging.format", "json")
    cache.configure(bool(config.get("performance.cache", True)))
    configure(
        config.get("logging.level", "info"),
        config.get("logging.format", "text"),
        bool(config.get("performance.progress", True)),
    )
    return config


def _plugin_overrides(args) -> dict:
    """The ``plugins.*`` part of ``--set``, which the registry owns rather than config."""
    return _parse_overrides(args.overrides).get("plugins", {}) if args.overrides else {}


def _selection_overrides(args) -> dict:
    selection = {}
    if getattr(args, "section", None):
        selection["sections"] = list(args.section)
    if getattr(args, "currier", None):
        selection["currier"] = args.currier
    if getattr(args, "scribe", None):
        selection["scribes"] = list(args.scribe)
    if getattr(args, "text_class", None):
        selection["textClass"] = args.text_class
    if getattr(args, "lines", None):
        selection["lines"] = args.lines
    if getattr(args, "words", None):
        selection["words"] = args.words
    if getattr(args, "folio", None):
        selection["folios"] = list(args.folio)
    extra = {"selection": selection} if selection else {}
    if getattr(args, "transcription", None):
        extra["transcription"] = args.transcription
    if getattr(args, "mapping", None):
        extra.setdefault("mapping", {})["file"] = args.mapping
    if getattr(args, "seed", None) is not None:
        extra["random"] = {"seed": args.seed}
    if getattr(args, "output", None):
        extra["output"] = {"directory": args.output}
    return extra


def _relative(path) -> str:
    """Show a path relative to the workspace, with forward slashes.

    Printed paths end up in bug reports and forum posts, so they must never
    carry the account name of whoever ran the command.
    """
    try:
        return Path(path).resolve().relative_to(ws().resolve()).as_posix()
    except (ValueError, OSError):
        return Path(path).as_posix()


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_init(args) -> int:
    from .mapping import identity_mapping
    from .profiles import profiles_dir, save_mapping
    from .simpleconfig import write_simple_config, write_simple_plugins

    created = []
    registry = PluginRegistry().discover()

    for name in ("mappings", "output", "reference_texts", "transcriptions"):
        ws(name).mkdir(parents=True, exist_ok=True)

    # The starter mapping first, so the config can point at it.
    profile_name = "identity_%s" % args.transcription
    corpus = load_corpus(args.transcription)
    target = profiles_dir() / ("%s.json" % profile_name)
    if not target.exists() or args.force:
        mapping = identity_mapping(
            corpus.glyph_counts().keys(),
            meta={
                "name": profile_name,
                "alphabet": corpus.alphabet,
                "notes": "Every glyph maps to itself. Edit the 'rules' block to build your hypothesis.",
            },
        )
        created.append(save_mapping(mapping, profile_name, note="created by tvtt init"))

    mapping_path = "mappings/%s.json" % profile_name

    simple_config = Path(args.config) if args.config else ws("config.json")
    if simple_config.exists() and not args.force:
        print("  config.json already exists, leaving it alone")
    else:
        created.append(write_simple_config(simple_config, mapping=mapping_path, transcription=args.transcription))

    simple_plugins = Path(args.plugins_file) if args.plugins_file else ws("plugins.json")
    if simple_plugins.exists() and not args.force:
        print("  plugins.json already exists, leaving it alone")
    else:
        created.append(write_simple_plugins(simple_plugins))

    if args.advanced:
        try:
            # Seed it from what is already in force, so creating it is a no-op.
            created.append(write_default_config(None, args.force, load_config(args.config).data))
        except TvttError as exc:
            print("  advanced_config.json: %s" % exc.message)
        try:
            created.append(write_plugins_document(registry, None, args.force))
        except TvttError as exc:
            print("  advanced_plugins.json: %s" % exc.message)

    print("Workspace ready in %s/" % ws().name)
    for path in created:
        print("  created %s" % Path(path).name)
    print()
    print("You have two settings files, both short:")
    print("  config.json     what to run: transcription, mapping, which part of the book")
    print("  plugins.json    which features to switch on")
    if args.advanced:
        print("  advanced_config.json / advanced_plugins.json")
        print("                  every option, merged on top of the two above")
    else:
        print()
        print("Run 'tvtt init --advanced' later if you want every option spelled out.")
    print()
    print("Next steps:")
    print("  1. tvtt run                    transliterate and produce a report")
    print("  2. tvtt plugins list           see every feature and what it measures")
    print("  3. edit %s   build your hypothesis" % display_path(mapping_path))
    return 0


def cmd_run(args) -> int:
    from .pipeline import run as run_pipeline

    config = _config_for(args, _selection_overrides(args))
    registry = build_registry(args.plugins_file, _plugin_overrides(args))
    if args.all_plugins:
        for name in registry.enabled:
            registry.enabled[name] = True
    outcome = run_pipeline(config, registry, args.plugin or None)
    print()
    for line in outcome.summary_lines():
        print(line)
    warnings = outcome.manifest.warnings if outcome.manifest else []
    if warnings:
        print()
        print("Warnings:")
        for warning in warnings:
            print("  ! %s" % warning)
    return 0


def cmd_analyze(args) -> int:
    from .pipeline import run as run_pipeline

    extra = _selection_overrides(args)
    config = _config_for(args, extra)
    registry = build_registry(args.plugins_file, _plugin_overrides(args))
    if args.plugin:
        chosen = args.plugin
    else:
        chosen = [
            name
            for name, plugin in registry.plugins.items()
            if plugin.stage == "analyze" and registry.enabled.get(name)
        ]
        if args.compare_sections and "section_report" not in chosen:
            chosen.append("section_report")
    outcome = run_pipeline(config, registry, chosen)
    print()
    for line in outcome.summary_lines():
        print(line)
    return 0


def cmd_solve(args) -> int:
    from .pipeline import run as run_pipeline

    locked = {}
    for pair in args.lock:
        if "=" not in pair:
            raise TvttError("--lock expects GLYPH=LETTER, got %r" % pair)
        glyph, letter = pair.split("=", 1)
        locked[glyph] = letter

    settings = {
        "method": args.method,
        "fitness": args.fitness,
        "lock": locked,
        "swapOnly": args.swap_only,
        "injective": args.injective,
    }
    if args.language:
        settings["language"] = args.language
    if args.iterations:
        settings["iterations"] = args.iterations
    if args.restarts:
        settings["restarts"] = args.restarts
    if args.positions:
        settings["positions"] = args.positions
    if args.save_as:
        settings["saveAs"] = args.save_as

    extra = {}
    if args.seed is not None:
        extra["random"] = {"seed": args.seed}
    config = _config_for(args, extra)

    registry = build_registry(args.plugins_file, _plugin_overrides(args))
    registry.enabled["solve"] = True
    registry.settings["solve"].update(settings)
    outcome = run_pipeline(config, registry, ["solve"])
    payload = outcome.results.get("solve", {})
    print()
    print(
        "best score %.5f after %d evaluations in %.1f s"
        % (payload.get("best_score", 0), payload.get("evaluations", 0), payload.get("elapsed_seconds", 0))
    )
    print("your current mapping scored %.5f" % payload.get("current_score", 0))
    print()
    # Name the files that were actually written, and check the mapping that
    # was actually found: without --mapping these plugins would score whatever
    # config.json still points at, which is not what the solver just produced.
    run_dir = display_path(outcome.output_dir)
    checks = "tvtt run --plugin random_controls --plugin holdout --plugin corpus_match"
    if args.save_as:
        print("saved as mappings/%s.json" % args.save_as)
        target = "--mapping mappings/%s.json" % args.save_as
    else:
        target = "--mapping %s/solver.json" % run_dir
    print("Read %s/solver.txt before believing this, and run:" % run_dir)
    print("  %s %s" % (checks, target))
    if not args.save_as:
        print()
        print("Pass --save-as <name> next time to keep it as a mapping you can edit.")
    return 0


def cmd_mapping_init(args) -> int:
    from .mapping import frequency_matched_mapping, identity_mapping
    from .profiles import profiles_dir, save_mapping

    config = _config_for(args)
    transcription = args.transcription or config.get("transcription", "zl")
    corpus = load_corpus(transcription, config.parse_options(), config.selection())
    name = args.name or ("identity_%s" % transcription)

    target = profiles_dir() / ("%s.json" % name)
    if target.exists() and not args.force:
        raise TvttError("mapping %r already exists" % name, hint="Pass --force to overwrite it.")

    if args.frequency_seed:
        from collections import Counter

        from .langmodel import control_text
        from .lexicon import tokenize

        letters = Counter("".join(tokenize(control_text(args.frequency_seed))))
        mapping = frequency_matched_mapping(
            corpus.glyph_counts(),
            letters.most_common(),
            meta={
                "name": name,
                "alphabet": corpus.alphabet,
                "language": args.frequency_seed,
                "notes": "Seeded by matching glyph frequency to %s letter frequency." % args.frequency_seed,
            },
        )
    else:
        mapping = identity_mapping(
            corpus.glyph_counts().keys(),
            meta={
                "name": name,
                "alphabet": corpus.alphabet,
                "notes": "Every glyph maps to itself. Edit the 'rules' block to build your hypothesis.",
            },
        )

    path = save_mapping(mapping, name, note="created by tvtt mapping init")
    print("wrote %s with %d glyphs" % (_relative(path), len(mapping.rules)))
    print("point config.json at it with: tvtt mapping use %s" % name)
    return 0


def cmd_mapping_list(args) -> int:
    from .profiles import list_profiles

    profiles = list_profiles()
    if not profiles:
        print("No mappings yet. Create one with 'tvtt mapping init'.")
        return 0
    print(table([p.row() for p in profiles], ["name", "alphabet", "language", "version", "score", "notes"]))
    return 0


def cmd_mapping_use(args) -> int:
    """Point the settings at a mapping, editing the file in place.

    Writing the whole merged configuration back would expand a beginner's
    ten-line config.json into the full schema and throw away the explanatory
    comments with it. Only the one key changes, in whatever vocabulary that
    file already uses.
    """
    from .profiles import find_profile
    from .simpleconfig import ADVANCED_CONFIG, is_simple_config
    from .util import read_json, write_json

    profile = find_profile(args.name)
    try:
        relative = profile.path.relative_to(ws())
    except ValueError:
        relative = profile.path
    value = str(relative).replace("\\", "/")

    def point_at(target: Path) -> None:
        raw = read_json(target) if target.exists() else {}
        if not isinstance(raw, dict):
            raw = {}
        if raw and not is_simple_config(raw):
            block = raw.get("mapping")
            raw["mapping"] = {**block, "file": value} if isinstance(block, dict) else {"file": value}
        else:
            raw["mapping"] = value
        write_json(target, raw)

    target = Path(args.config) if args.config else ws("config.json")
    point_at(target)
    # An advanced file layers on top, so leaving its mapping in place would
    # quietly override the change we just announced.
    advanced = target.parent / ADVANCED_CONFIG
    if not args.config and advanced.exists():
        raw = read_json(advanced)
        if isinstance(raw, dict) and isinstance(raw.get("mapping"), dict) and raw["mapping"].get("file"):
            point_at(advanced)

    print("%s now uses %s" % (target.name, _relative(profile.path)))
    return 0


def cmd_mapping_show(args) -> int:
    from .fonts import legend_text
    from .profiles import find_profile

    config = _config_for(args)
    corpus = load_corpus(config.get("transcription", "zl"), config.parse_options(), config.selection())
    if args.name:
        mapping = find_profile(args.name).load()
    else:
        from .mapping import Mapping

        mapping = Mapping.load(config.mapping_path(), config.markers())
    from .fonts import glyph_legend
    from .transliterate import build_engine

    engine = build_engine(mapping, corpus, markers=config.markers())
    print(legend_text(glyph_legend(engine, corpus.glyph_counts())))
    return 0


def cmd_mapping_validate(args) -> int:
    from .mapping import Mapping, round_trip_check
    from .profiles import find_profile
    from .transliterate import build_engine

    config = _config_for(args)
    corpus = load_corpus(config.get("transcription", "zl"), config.parse_options(), config.selection())
    mapping = find_profile(args.name).load() if args.name else Mapping.load(config.mapping_path(), config.markers())
    engine = build_engine(mapping, corpus, markers=config.markers())

    report = round_trip_check(engine, list(corpus.word_counts()))
    print(report.summary())
    if report.collisions:
        print()
        print("Collisions:")
        for text, sources in list(report.collisions.items())[:20]:
            print("  %-10s <- %s" % (text or "(empty)", ", ".join("%s (%s)" % s for s in sources)))
    conflicts = engine.conflicts()
    if conflicts:
        print()
        print("Overlapping rules (%d):" % len(conflicts))
        for item in conflicts[:20]:
            print("  %-8s %-8s winner: %s" % (item["glyph"], item["kind"], item["winner"]))
    return 0 if report.injective else 1


def cmd_mapping_diff(args) -> int:
    from .mapping import mapping_diff
    from .profiles import find_profile

    left = find_profile(args.left).load()
    right = find_profile(args.right).load()
    rows = mapping_diff(left, right)
    if not rows:
        print("The two mappings are identical.")
        return 0
    print(
        table(
            [[r["glyph"], r["position"], r["before"] or "-", r["after"] or "-", r["change"]] for r in rows],
            ["glyph", "position", args.left, args.right, "change"],
        )
    )
    print()
    print("%d rule difference(s). To see how the statistics move, enable the mapping_diff plugin:" % len(rows))
    print("  tvtt plugins set mapping_diff against %s && tvtt run --plugin mapping_diff" % args.left)
    return 0


def cmd_mapping_history(args) -> int:
    from .profiles import history

    rows = history(args.name)
    if not rows:
        print("No saved versions of %r yet. Versions are kept whenever TVTT saves a mapping." % args.name)
        return 0
    print(table([[r["version"], r["when"], r["note"]] for r in rows], ["version", "when", "note"]))
    print()
    print("Restore one with: tvtt mapping restore %s <version>" % args.name)
    return 0


def cmd_mapping_restore(args) -> int:
    from .profiles import restore

    path = restore(args.name, args.version)
    print("restored %s from version %s" % (_relative(path), args.version))
    return 0


def cmd_mapping_export(args) -> int:
    from .profiles import export_pack

    path = export_pack(args.names, args.out, args.title, args.author, args.notes)
    print("wrote %s containing %d mapping(s)" % (_relative(path), len(args.names)))
    return 0


def cmd_mapping_import(args) -> int:
    from .profiles import import_pack

    written = import_pack(args.path, args.prefix, args.overwrite)
    for path in written:
        print("imported %s" % Path(path).name)
    return 0


def cmd_mapping_gallery(args) -> int:
    from .profiles import GALLERY_NOTE

    print(GALLERY_NOTE)
    return 0


PRESETS = {
    "quick": ["transliteration", "frequency", "entropy", "legend"],
    "standard": [
        "transliteration",
        "frequency",
        "entropy",
        "word_length",
        "vocabulary",
        "zipf",
        "repeats",
        "legend",
        "roundtrip",
        "conflicts",
        "html_report",
    ],
    "full": None,
    "evaluate": [
        "transliteration",
        "entropy",
        "word_length",
        "vocabulary",
        "corpus_match",
        "random_controls",
        "match_significance",
        "shuffles",
        "synthetic",
        "language_controls",
        "holdout",
        "overfitting",
        "roundtrip",
        "html_report",
    ],
    "search": ["solve", "random_controls", "holdout", "corpus_match", "overfitting"],
}

PRESET_NOTES = {
    "quick": "the basics, a couple of seconds",
    "standard": "the usual statistics plus an HTML report",
    "full": "every plugin, including the slow ones",
    "evaluate": "the honest evaluation: statistics plus every baseline",
    "search": "automated search with the checks that keep it honest",
}


def cmd_plugins_list(args) -> int:
    registry = build_registry(args.plugins_file, _plugin_overrides(args))
    grouped = registry.by_category()
    for category, plugins in grouped.items():
        if args.category and category != args.category:
            continue
        rows = []
        for plugin in plugins:
            enabled = registry.enabled.get(plugin.name, False)
            if args.enabled and not enabled:
                continue
            rows.append(
                [
                    "on" if enabled else "-",
                    plugin.name,
                    "slow" if plugin.heavy else "",
                    plugin.summary,
                ]
            )
        if not rows:
            continue
        print()
        print(category.upper())
        print(table(rows, ["run", "name", "speed", "what it does"]))
    print()
    print("'tvtt plugins info <name>' explains one fully. 'tvtt plugins enable <name>' switches it on.")
    print("Presets: " + ", ".join("%s (%s)" % (k, v) for k, v in PRESET_NOTES.items()))
    return 0


def cmd_plugins_info(args) -> int:
    registry = build_registry(args.plugins_file, _plugin_overrides(args))
    plugin = registry.get(args.name)
    enabled = registry.enabled.get(plugin.name, False)
    settings = registry.settings.get(plugin.name, dict(plugin.defaults))

    print(plugin.title)
    print("=" * len(plugin.title))
    print()
    print("name      %s" % plugin.name)
    print("stage     %s" % plugin.stage)
    print("category  %s" % plugin.category)
    print("enabled   %s" % ("yes" if enabled else "no"))
    if plugin.heavy:
        print("note      this one can take a while")
    if plugin.requires:
        print("requires  %s" % ", ".join(plugin.requires))
    if plugin.optional_requires:
        print("uses      %s (if enabled)" % ", ".join(plugin.optional_requires))
    print()
    print(plugin.help)
    if plugin.defaults:
        print()
        print("Settings")
        print("--------")
        rows = [
            [key, json.dumps(settings.get(key, value)), plugin.settings_help.get(key, "")]
            for key, value in plugin.defaults.items()
        ]
        print(table(rows, ["setting", "current", "meaning"]))
        print()
        print("Change one with: tvtt plugins set %s <setting> <value>" % plugin.name)
    return 0


def _edit_plugins(path, mutate) -> Path:
    """Apply a per-plugin edit to ``advanced_plugins.json``.

    These commands work on individual plugins, which is the advanced file's
    vocabulary. Writing a ``plugins`` block into the simple ``plugins.json``
    would produce a file that mixes the two styles and no longer loads, so the
    edit goes to the advanced file - created from the current effective
    settings the first time, so nothing you had switched on is lost.
    """
    from .plugins import default_document
    from .simpleconfig import ADVANCED_PLUGINS
    from .util import read_json, write_json

    target = Path(path) if path else ws(ADVANCED_PLUGINS)

    if target.exists():
        document = read_json(target)
        document.pop("$schema", None)
    else:
        # Start from what is in force right now, so switching one plugin on
        # does not silently reset the others.
        registry = build_registry()
        document = default_document(registry)
        for name, entry in document["plugins"].items():
            entry["enabled"] = registry.enabled.get(name, False)
            settings = registry.settings.get(name)
            if settings:
                entry["settings"] = dict(settings)

    document.setdefault("plugins", {})
    mutate(document["plugins"])
    write_json(target, document)
    return target


def cmd_plugins_enable(args) -> int:
    registry = PluginRegistry().discover()
    for name in args.names:
        registry.get(name)
    target = _edit_plugins(
        args.plugins_file, lambda plugins: [plugins.setdefault(n, {}).update({"enabled": True}) for n in args.names]
    )
    print("enabled: %s" % ", ".join(args.names))
    print("  written to %s" % target.name)
    return 0


def cmd_plugins_disable(args) -> int:
    registry = PluginRegistry().discover()
    for name in args.names:
        registry.get(name)
    target = _edit_plugins(
        args.plugins_file, lambda plugins: [plugins.setdefault(n, {}).update({"enabled": False}) for n in args.names]
    )
    print("disabled: %s" % ", ".join(args.names))
    print("  written to %s" % target.name)
    return 0


def cmd_plugins_set(args) -> int:
    registry = PluginRegistry().discover()
    plugin = registry.get(args.name)
    if args.key not in plugin.defaults:
        raise TvttError(
            "plugin %r has no setting %r" % (args.name, args.key),
            hint="Known settings: " + (", ".join(plugin.defaults) or "(none)"),
        )
    value = _coerce(args.value)

    def mutate(plugins):
        entry = plugins.setdefault(args.name, {})
        entry.setdefault("settings", {})[args.key] = value

    target = _edit_plugins(args.plugins_file, mutate)
    print("%s.%s = %s" % (args.name, args.key, json.dumps(value)))
    print("  written to %s" % target.name)
    return 0


def cmd_plugins_preset(args) -> int:
    if not args.name:
        print(table([[k, v] for k, v in PRESET_NOTES.items()], ["preset", "what it turns on"]))
        return 0
    registry = PluginRegistry().discover()
    chosen = PRESETS[args.name]
    names = list(registry.plugins) if chosen is None else chosen

    def mutate(plugins):
        for name in registry.plugins:
            plugins.setdefault(name, {})["enabled"] = name in names

    target = _edit_plugins(args.plugins_file, mutate)
    print("preset %r applied: %d plugin(s) enabled" % (args.name, len(names)))
    print("  written to %s" % target.name)
    print("  " + ", ".join(sorted(names)))
    return 0


def cmd_sections(args) -> int:
    from .folios import load_folios

    rows = [[name, title, count, description] for name, title, count, description in load_folios().summary()]
    print(table(rows, ["name", "section", "folios", "what it is"]))
    print()
    print("Use one with: tvtt run --section herbal_b")
    return 0


def cmd_sources(args) -> int:
    from .download import describe_sources

    print(table(describe_sources(), ["name", "alphabet", "file", "where", "description"]))
    print()
    print("Choose one with: tvtt run --transcription takahashi")
    print("Update them with: tvtt fetch --all")
    return 0


def cmd_folios(args) -> int:
    from .folios import load_folios

    folios = load_folios()
    keys = folios.keys()
    if args.section:
        keys = [k for k in keys if k in folios.in_section(args.section)]
    if args.currier:
        keys = [k for k in keys if folios.get(k).currier == args.currier]
    if args.scribe:
        keys = [k for k in keys if folios.get(k).scribe == str(args.scribe)]
    rows = []
    for key in keys:
        info = folios.get(key)
        rows.append(
            [
                "f" + key,
                info.illustration_name,
                info.currier or "-",
                info.scribe or "-",
                info.currier_hand or "-",
                info.quire_name,
            ]
        )
    print(table(rows, ["folio", "section", "Currier language", "scribe", "Currier hand", "quire"]))
    print()
    print("%d folio(s)." % len(rows))
    return 0


def cmd_build_folios(args) -> int:
    """Rebuild data/folios.json from a transcription's page variables.

    The bundled file is generated, not hand-written, and an error elsewhere
    tells you to run this when it is missing. It writes into the workspace,
    which takes precedence over the bundled copy, so the installed package is
    never touched.
    """
    from .corpus import resolve_transcription
    from .folios import build_folio_table
    from .ivtff import parse_file
    from .util import write_json

    spec = resolve_transcription(args.transcription)
    document = parse_file(transcription_file(spec.filename))
    payload = build_folio_table(document.pages.values())
    target = Path(args.out) if args.out else ws("data", "folios.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, payload)
    print("wrote %s: %d folios from %s" % (display_path(target), len(payload["folios"]), spec.filename))
    return 0


def cmd_dictionaries(args) -> int:
    from .langmodel import available_controls
    from .lexicon import LANGUAGE_TITLES, available_dictionaries
    from .paths import display_path

    rows = [[name, LANGUAGE_TITLES.get(name, ""), display_path(path)] for name, path in available_dictionaries()]
    print("Dictionaries")
    print(table(rows, ["name", "what it is", "file"]))
    print()
    print("Control texts: " + ", ".join(available_controls()))
    print()
    print("Add your own by putting .txt files in reference_texts/.")
    return 0


def cmd_verify(args) -> int:
    from .download import verify_local

    rows = verify_local()
    print(table(rows, ["name", "file", "state", "sha256"]))
    bad = [r for r in rows if r[2] not in ("ok",)]
    if bad:
        print()
        print("A file that differs from the release checksum is usually an upstream correction,")
        print("not a problem. Run 'tvtt fetch --all' to get the current versions.")
    return 0


def cmd_doctor(args) -> int:
    from .download import verify_local
    from .folios import load_folios
    from .util import has_module

    config = _config_for(args)
    problems = []
    notes = []

    for name in ("config.json", "plugins.json"):
        if not ws(name).exists():
            problems.append("%s is missing. Run 'tvtt init'." % name)

    mapping_path = config.mapping_path()
    if not mapping_path.exists():
        problems.append("mapping file %s does not exist. Run 'tvtt mapping init'." % display_path(mapping_path))

    try:
        spec = resolve_transcription(config.get("transcription", "zl"))
        corpus = load_corpus(spec.key, config.parse_options(), config.selection())
        if corpus.is_empty:
            problems.append("the current selection matches no lines. Check the 'selection' block in config.json.")
        else:
            notes.append("selection: %s" % corpus.stats_line())
    except TvttError as exc:
        problems.append(str(exc))

    try:
        notes.append("folio metadata: %d pages" % len(load_folios()))
    except TvttError as exc:
        problems.append(str(exc))

    for name, purpose in (
        ("matplotlib", "image plots"),
        ("plotly", "interactive plots"),
        ("deep_translator", "machine translation"),
        ("numpy", "faster numeric work"),
        ("tqdm", "nicer progress bars"),
        ("jsonschema", "stricter config validation"),
    ):
        notes.append("optional %-16s %s (%s)" % (name, "installed" if has_module(name) else "not installed", purpose))

    for row in verify_local():
        if row[2] not in ("ok",):
            notes.append("transcription %s: %s" % (row[1], row[2]))

    print("Workspace: %s/" % ws().name)
    print()
    if problems:
        print("Problems")
        for item in problems:
            print("  ! %s" % item)
        print()
    print("Notes")
    for item in notes:
        print("  - %s" % item)
    print()
    print("No problems found." if not problems else "%d problem(s) to fix." % len(problems))
    return 1 if problems else 0


def cmd_runs(args) -> int:
    from .paths import display_path
    from .runs import describe_runs, latest_run, prune

    config = _config_for(args)
    root = config.output_root()

    if args.prune is not None:
        removed = prune(root, args.prune)
        print("removed %d old run folder(s)" % len(removed))
        for name in removed:
            print("  %s" % name)
        if not removed:
            print("  nothing to remove")
        return 0

    rows = describe_runs(root)
    if not rows:
        print("No runs yet in %s/. Run 'tvtt run' to make one." % display_path(root))
        return 0
    print(table(rows[: args.limit], ["folder", "started", "mapping", "selection", "words", "warnings"]))
    print()
    print("%d run(s) in %s" % (len(rows), _relative(root)))
    newest = latest_run(root)
    if newest:
        print("most recent: %s" % _relative(newest))
    print()
    print("Each run has its own folder so nothing is overwritten.")
    print("Set output.separateRunFolders to false for the old single-folder behaviour,")
    print("or output.keepRuns to a number to discard the oldest automatically.")
    return 0


def cmd_fetch(args) -> int:
    from .download import fetch

    config = _config_for(args)
    if not args.all and not args.name:
        raise TvttError("say which transcription to fetch, or pass --all", hint="Run 'tvtt sources' to list them.")
    results = fetch(
        args.name,
        args.all,
        user_agent=config.get("network.userAgent", "TVTT/2.0"),
        timeout=int(config.get("network.timeoutSeconds", 60)),
        force=args.force,
    )
    for result in results:
        print("  " + result.message())
    return 0


def cmd_web(args) -> int:
    from .webapp.server import serve

    config = _config_for(args)
    serve(config, host=args.host, port=args.port, open_browser=not args.no_browser)
    return 0


def cmd_results(args) -> int:
    """Show results.json as a leaderboard.

    Every run appends one row, so this survives pruning the output folders and
    is what lets two attempts be compared long after the runs themselves.
    """
    from .profiles import rank_results

    rows = rank_results(metric=args.metric)
    if not rows:
        print("No results recorded yet. Run 'tvtt run' to record one.")
        return 0

    metrics = []
    for row in rows:
        for key in row.get("metrics", {}):
            if key not in metrics:
                metrics.append(key)
    if args.metric and args.metric not in metrics:
        raise TvttError(
            "no result has a metric called %r" % args.metric,
            hint="Recorded metrics: " + ", ".join(metrics),
        )
    shown = [args.metric] if args.metric else metrics[:5]

    header = ["recorded", "mapping", "selection"] + shown
    table_rows = []
    for row in rows[: args.limit]:
        values = row.get("metrics", {})
        table_rows.append(
            [row.get("recorded", "")[:16].replace("T", " "), row.get("mapping", ""), row.get("selection", "")]
            + [("%g" % values[k]) if isinstance(values.get(k), (int, float)) else "-" for k in shown]
        )
    print(table(table_rows, header))
    print()
    print("%d result(s) in results.json. Sort by any of: %s" % (len(rows), ", ".join(metrics)))
    return 0


def cmd_cache(args) -> int:
    if args.action == "clear":
        removed = cache.clear()
        print("removed %d cache file(s)" % removed)
        return 0
    from .paths import cache_dir, display_path

    size = cache.size_bytes()
    print("cache directory : %s/" % display_path(cache_dir()))
    print("entries         : %d" % len(list(cache_dir().glob("*.pkl"))))
    print("size            : %.1f MB" % (size / 1048576))
    print()
    print("Clear it with 'tvtt cache clear'. It is always safe to delete.")
    return 0


def _print_subhelp(parser) -> int:
    parser.print_help()
    return 0


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: list = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    set_workspace(args.workspace)

    if not getattr(args, "func", None):
        parser.print_help()
        print()
        print("Quick start:")
        print("  tvtt init          set up this folder")
        print("  tvtt run           transliterate and report")
        print("  tvtt plugins list  see every optional feature")
        return 0

    try:
        return args.func(args) or 0
    except TvttError as exc:
        logger = get_logger("cli")
        print()
        print("Error: %s" % exc.message, file=sys.stderr)
        if exc.hint:
            print("  %s" % exc.hint, file=sys.stderr)
        logger.debug("failure detail", exc_info=True)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
