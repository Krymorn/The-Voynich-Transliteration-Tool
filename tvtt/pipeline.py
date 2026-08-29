"""The run pipeline: config in, outputs and a manifest out.

``tvtt run`` is this module.  It loads the configuration, parses the chosen
transcription, applies the selection, compiles the mapping, transliterates,
runs every enabled plugin in stage order, and writes a manifest recording
exactly what happened.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import cache
from .config import Config, load_config
from .corpus import load_corpus, resolve_transcription
from .errors import ConfigError, TvttError
from .logging_util import configure, get_logger, log
from .manifest import RunManifest
from .mapping import Mapping, identity_mapping
from .paths import display_path, transcription_file
from .plugins import PluginContext, PluginRegistry, build_registry
from .runs import prune, record_latest, write_info
from .transliterate import Result, build_engine, transliterate
from .util import Timer, sha256_file


@dataclass
class RunOutcome:
    """Everything a completed run produced."""

    config: Config
    corpus: object
    result: Result
    results: dict = field(default_factory=dict)
    manifest: RunManifest = None
    outputs: list = field(default_factory=list)
    elapsed: float = 0.0
    output_dir: str = ""

    @property
    def output_label(self) -> str:
        """The output folder, shown relative to the workspace where possible."""
        from .paths import workspace

        try:
            return Path(self.output_dir).resolve().relative_to(workspace().resolve()).as_posix()
        except (ValueError, OSError):
            return self.output_dir

    def summary_lines(self) -> list:
        lines = [
            "transcription : %s (%s)" % (self.corpus.title, self.corpus.alphabet),
            "selection     : %s" % self.corpus.selection.describe(),
            "mapping       : %s" % (self.result.engine.mapping.meta.get("name") or self.config.get("mapping.file")),
            "text          : %s" % self.result.summary(),
            "time          : %.2f s" % self.elapsed,
            "output        : %s" % self.output_label,
        ]
        if self.outputs:
            lines.append("outputs       :")
            for item in self.outputs:
                name = Path(item["path"]).name
                description = item.get("description", "")
                lines.append("    %-26s %s" % (name, description))
        return lines


def prepare(config: Config):
    """Load the corpus and compile the mapping, without running plugins."""
    cache.configure(bool(config.get("performance.cache", True)))

    spec = resolve_transcription(config.get("transcription", "zl"))
    corpus = load_corpus(spec.key, config.parse_options(), config.selection())

    mapping_path = config.mapping_path()
    if mapping_path.exists():
        mapping = Mapping.load(mapping_path, config.markers())
    elif config.names_a_mapping():
        # Falling back to identity here would hand back the manuscript unchanged
        # and call it your result, which is the worst way to learn about a typo.
        raise ConfigError(
            "the mapping file %s does not exist" % display_path(mapping_path),
            hint="Run 'tvtt mapping list' to see what you have, or 'tvtt mapping init <name>' to create one.",
        )
    else:
        mapping = identity_mapping(
            corpus.glyph_counts().keys(),
            meta={
                "name": "identity (no mapping file yet)",
                "alphabet": corpus.alphabet,
                "notes": "Every glyph maps to itself. Run 'tvtt mapping init' to create a real one.",
            },
        )

    engine = build_engine(
        mapping,
        corpus,
        markers=config.markers(),
        precedence=tuple(config.get("mapping.precedence", ("initial", "final", "occurrence", "plain"))),
        unmapped=config.get("mapping.unmapped", "keep"),
        placeholder=config.get("mapping.placeholder", "?"),
    )
    return corpus, mapping, engine


def run(config: Config = None, registry: PluginRegistry = None, only: list = None) -> RunOutcome:
    """Execute a full run and return everything it produced."""
    config = config or load_config()
    configure(
        config.get("logging.level", "info"),
        config.get("logging.format", "text"),
        bool(config.get("performance.progress", True)),
    )
    logger = get_logger("run")

    with Timer() as total:
        corpus, mapping, engine = prepare(config)
        result = transliterate(
            corpus,
            engine,
            config.get("output.wordSeparator", " "),
            config.get("output.uncertainWordSeparator", " "),
        )
        log(
            logger,
            "info",
            "transliterated",
            lines=len(result.lines),
            words=len(result.words()),
            ms=round(result.elapsed * 1000, 1),
        )

        registry = registry or build_registry()
        if only:
            unknown = [name for name in only if name not in registry.plugins]
            if unknown:
                raise TvttError(
                    "unknown plugin(s): " + ", ".join(unknown),
                    hint="Run 'tvtt plugins list' to see the available plugins.",
                )
            for name in registry.enabled:
                registry.enabled[name] = name in only

        spec = resolve_transcription(config.get("transcription", "zl"))
        source_path = transcription_file(spec.filename)
        manifest = RunManifest(
            config=config.data,
            config_sha256=config.signature(),
            transcription=spec.key,
            transcription_file=str(source_path),
            transcription_sha256=corpus.source_sha256 or (sha256_file(source_path) if source_path.exists() else ""),
            mapping_file=str(config.mapping_path()),
            mapping_name=str(mapping.meta.get("name", "")),
            mapping_sha256=mapping.signature(),
            selection=corpus.selection.describe(),
            seed=config.seed(),
        )

        outputs: list = []

        def make_context(plugin, settings):
            return PluginContext(
                config=config,
                corpus=corpus,
                result=result,
                settings=settings,
                results={},
                outputs=outputs,
                registry=registry,
                log=get_logger(plugin.name),
            )

        if corpus.selection.lines in ("first", "last", "single") and corpus.is_empty:
            # Ask the corpus *before* the line filter whether paragraphs exist at
            # all. Asking the filtered one is circular: it is empty precisely
            # because the filter matched nothing, which would have us report that
            # ZL marks no paragraphs when it marks 740 of them.
            from dataclasses import replace as _replace

            spec = resolve_transcription(config.get("transcription", "zl"))
            unfiltered = load_corpus(spec.key, config.parse_options(), _replace(corpus.selection, lines="all"))
            if not unfiltered.paragraph_marks:
                manifest.warn(
                    "This transliteration marks no paragraphs, so selection.lines=%r matches nothing. "
                    "The ZL and v101 files do mark them." % corpus.selection.lines
                )
            else:
                manifest.warn(
                    "No line matches selection.lines=%r here: the selection has %d paragraph(s), "
                    "but none of them fit that description." % (corpus.selection.lines, unfiltered.paragraph_marks)
                )
        if corpus.is_empty:
            manifest.warn("The current selection matches no lines at all.")

        active = registry.active()
        manifest.plugins = [p.name for p in active]
        results = registry.run_all(make_context)
        manifest.timings = results.get("_timings", {})
        manifest.outputs = outputs
        manifest.stats = _headline(result, results)
        _collect_warnings(manifest, results)

    manifest.started = time.time() - total.elapsed
    run_dir = config.output_dir()
    if config.get("output.writeManifest", True):
        path = manifest.write(run_dir)
        outputs.append({"path": str(path), "description": "run manifest for reproducibility"})

    write_info(run_dir, manifest, outputs)
    if config.get("output.recordResult", True):
        _record_result(config, manifest)
    if config.get("output.separateRunFolders", True):
        record_latest(config.output_root(), run_dir)
        prune(config.output_root(), int(config.get("output.keepRuns", 0) or 0))

    return RunOutcome(
        config=config,
        corpus=corpus,
        result=result,
        results=results,
        manifest=manifest,
        outputs=outputs,
        elapsed=total.elapsed,
        output_dir=str(run_dir),
    )


def _record_result(config, manifest: RunManifest) -> None:
    """Append this run to the workspace-wide ``results.json``.

    One row per run, in a shared format, so that a claim can be handed to
    somebody else alongside the mapping and checked. This is the file
    ``tvtt mapping gallery`` asks for when you submit a mapping.
    """
    from .profiles import append_result, result_record

    append_result(
        result_record(
            mapping_name=manifest.mapping_name,
            mapping_signature=manifest.mapping_sha256,
            transcription=manifest.transcription,
            transcription_sha256=manifest.transcription_sha256,
            selection=manifest.selection,
            metrics=manifest.stats,
        )
    )


def _headline(result: Result, results: dict) -> dict:
    words = result.words()
    stats = {
        "lines": len(result.lines),
        "words": len(words),
        "word_types": len(set(words)),
    }
    entropy = results.get("entropy")
    if entropy:
        stats["h1"] = entropy.get("h1_character_bits")
        stats["h2"] = entropy.get("h2_conditional_bits")
    match = results.get("corpus_match")
    if match:
        stats["dictionary_coverage"] = match.get("coverage")
        stats["weighted_coverage"] = match.get("weighted_coverage")
        stats["stopword_coverage"] = match.get("stopword_coverage")
    controls = results.get("random_controls")
    if controls:
        stats["random_control_z"] = controls.get("z_score")
    return stats


def _collect_warnings(manifest: RunManifest, results: dict) -> None:
    for name, reason in (results.get("_skipped") or {}).items():
        manifest.warn("Plugin %r was skipped: %s" % (name, reason))
    roundtrip = results.get("roundtrip")
    if roundtrip and not roundtrip.get("injective", True):
        manifest.warn(
            "The mapping is not injective: %d collision(s). Output cannot be turned back into the source."
            % roundtrip.get("collision_count", 0)
        )
    overfitting = results.get("overfitting")
    if overfitting and overfitting.get("level") in ("high", "severe"):
        manifest.warn("Overfitting risk %s: %s" % (overfitting["level"], overfitting.get("message", "").split("\n")[0]))
    controls = results.get("random_controls")
    if controls and controls.get("z_score", 0) < 2:
        manifest.warn("This mapping does not score clearly above random mappings.")
    holdout = results.get("holdout")
    if holdout and holdout.get("worst_drop", 0) > 0.2:
        manifest.warn("Score drops by %.0f%% on held-out sections." % (holdout["worst_drop"] * 100))
