"""End-to-end tests: config, plugins, the run pipeline, profiles and the CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tvtt.cli import main
from tvtt.config import DEFAULT_CONFIG, Config, load_config, migrate_legacy, write_default_config
from tvtt.errors import ConfigError, PluginError
from tvtt.paths import set_workspace
from tvtt.plugins import PluginRegistry, build_registry, default_document


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_workspace(tmp_path)
    yield tmp_path
    set_workspace(None)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


def test_defaults_are_valid_against_the_schema(workspace):
    config = load_config()
    assert config.get("transcription") == "zl"
    assert config.get("output.wordSeparator") == " "


def test_unknown_config_key_is_reported_with_a_suggestion(workspace):
    (workspace / "config.json").write_text(json.dumps({"transcripton": "zl"}), encoding="utf-8")
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    assert "transcripton" in str(excinfo.value)


def test_invalid_enum_value_is_rejected(workspace):
    (workspace / "config.json").write_text(json.dumps({"ambiguity": {"alternates": "sometimes"}}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config()


def test_broken_json_names_the_line(workspace):
    (workspace / "config.json").write_text('{"transcription": "zl"\n"x": 1}', encoding="utf-8")
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    assert "line" in str(excinfo.value)


def test_version_one_config_is_migrated():
    legacy = {
        "transliteration": "eva",
        "spaceDelimiter": "_",
        "ambiguousSpaceDelimiter": "-",
        "startLine": 5,
        "endLine": 40,
        "enableAnalysis": True,
        "toleranceLevel": 2,
        "outputPath": "output.txt",
    }
    migrated = migrate_legacy(legacy)
    assert migrated["transcription"] == "zl"
    assert migrated["selection"]["startLine"] == 5
    assert migrated["output"]["wordSeparator"] == "_"


def test_command_line_overrides_win(workspace):
    write_default_config()
    config = load_config(overrides={"selection": {"currier": "B"}})
    assert config.get("selection.currier") == "B"


def test_config_signature_changes_with_content():
    a = Config(data=dict(DEFAULT_CONFIG))
    b = Config(data={**DEFAULT_CONFIG, "transcription": "v101"})
    assert a.signature() != b.signature()


# --------------------------------------------------------------------------
# Plugins
# --------------------------------------------------------------------------


def test_every_plugin_declares_its_contract():
    registry = PluginRegistry().discover()
    assert len(registry.plugins) >= 25
    for name, plugin in registry.plugins.items():
        assert plugin.name == name
        assert plugin.summary and plugin.summary[0].isupper(), name
        assert plugin.summary.endswith("."), name
        assert len(plugin.help) > 200, name
        assert callable(plugin.run), name
        for key in plugin.defaults:
            assert key in plugin.settings_help or not plugin.defaults, (name, key)


def test_default_document_lists_every_plugin():
    registry = PluginRegistry().discover()
    document = default_document(registry)
    assert set(document["plugins"]) == set(registry.plugins)


def test_unknown_plugin_name_is_rejected_with_a_suggestion():
    registry = PluginRegistry().discover()
    with pytest.raises(PluginError) as excinfo:
        registry.configure({"plugins": {"entrpy": {"enabled": True}}})
    assert "entropy" in str(excinfo.value)


def test_unknown_plugin_setting_is_rejected():
    registry = PluginRegistry().discover()
    with pytest.raises(PluginError) as excinfo:
        registry.configure({"plugins": {"entropy": {"settings": {"nope": 1}}}})
    assert "nope" in str(excinfo.value)


def test_dependencies_are_pulled_in_and_ordered():
    registry = PluginRegistry().discover()
    registry.configure({"plugins": {"html_report": {"enabled": True}, "entropy": {"enabled": True}}})
    order = [p.name for p in registry.active()]
    assert "entropy" in order
    assert order.index("entropy") < order.index("html_report")


def test_report_plugins_run_after_analysis_plugins():
    registry = PluginRegistry().discover()
    registry.configure({"plugins": {name: {"enabled": True} for name in registry.plugins}})
    stages = [p.stage for p in registry.active()]
    from tvtt.plugins import STAGES

    assert stages == sorted(stages, key=STAGES.index)


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


def _prepare(workspace, plugins: dict):
    from tvtt.util import write_json

    write_default_config()
    registry = PluginRegistry().discover()
    document = default_document(registry)
    for name, entry in document["plugins"].items():
        entry["enabled"] = name in plugins
        if name in plugins:
            entry.setdefault("settings", {}).update(plugins[name])
    write_json(workspace / "plugins.json", document)


def test_a_minimal_run_produces_text_and_a_manifest(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}})
    outcome = run(load_config(overrides={"selection": {"sections": ["zodiac"]}}), build_registry())

    run_dir = Path(outcome.output_dir)
    assert (run_dir / "output.txt").exists()
    assert (run_dir / "manifest.json").exists()
    assert outcome.result.lines
    assert (run_dir / "output.txt").read_text(encoding="utf-8").strip()


def test_the_manifest_records_everything_needed_to_reproduce(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}})
    outcome = run(load_config(overrides={"selection": {"sections": ["zodiac"]}}), build_registry())

    manifest = json.loads((Path(outcome.output_dir) / "manifest.json").read_text(encoding="utf-8"))
    inputs = manifest["inputs"]
    assert manifest["version"] == "2.0.0"
    assert len(inputs["transcription_sha256"]) == 64
    assert len(inputs["mapping_sha256"]) == 64
    assert inputs["seed"] == DEFAULT_CONFIG["random"]["seed"]
    assert manifest["outputs"]
    assert "tvtt run" in manifest["reproduce"]


def test_a_run_is_reproducible(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}, "synthetic": {"length": 400}})
    overrides = {"selection": {"sections": ["zodiac"]}}
    first = run(load_config(overrides=overrides), build_registry())
    second = run(load_config(overrides=overrides), build_registry())
    assert first.results["synthetic"]["sample"] == second.results["synthetic"]["sample"]
    assert first.manifest.signature() == second.manifest.signature()


def test_the_seed_actually_changes_stochastic_output(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"synthetic": {"length": 400}})
    base = {"selection": {"sections": ["zodiac"]}}
    a = run(load_config(overrides={**base, "random": {"seed": 1}}), build_registry())
    b = run(load_config(overrides={**base, "random": {"seed": 2}}), build_registry())
    assert a.results["synthetic"]["sample"] != b.results["synthetic"]["sample"]


def test_warnings_surface_a_non_injective_mapping(workspace):
    from tvtt.mapping import SLOT_PLAIN, Mapping
    from tvtt.pipeline import run
    from tvtt.profiles import save_mapping

    _prepare(workspace, {"roundtrip": {}})
    corpus_glyphs = list("aeoqrsdlchkty9")
    collapsing = Mapping(rules={g: {SLOT_PLAIN: "x"} for g in corpus_glyphs}, meta={"name": "collapsing"})
    save_mapping(collapsing, "collapsing")

    outcome = run(
        load_config(overrides={"selection": {"sections": ["zodiac"]}, "mapping": {"file": "mappings/collapsing.json"}}),
        build_registry(),
    )
    assert not outcome.results["roundtrip"]["injective"]
    assert any("not injective" in w for w in outcome.manifest.warnings)


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------


def test_saving_a_mapping_keeps_the_previous_version(workspace):
    from tvtt.mapping import SLOT_PLAIN, Mapping
    from tvtt.profiles import history, restore, save_mapping

    save_mapping(Mapping(rules={"a": {SLOT_PLAIN: "x"}}), "idea", note="first")
    save_mapping(Mapping(rules={"a": {SLOT_PLAIN: "y"}}), "idea", note="second")

    versions = history("idea")
    assert len(versions) == 1
    restore("idea", versions[0]["version"])
    assert Mapping.load(workspace / "mappings" / "idea.json").rules["a"][SLOT_PLAIN] == "x"


def test_packs_round_trip(workspace):
    from tvtt.mapping import SLOT_PLAIN, Mapping
    from tvtt.profiles import export_pack, import_pack, save_mapping

    save_mapping(Mapping(rules={"a": {SLOT_PLAIN: "x"}}, meta={"language": "latin"}), "mine")
    pack = export_pack(["mine"], workspace / "share", title="t", author="a")
    import_pack(pack, prefix="copy_")
    assert Mapping.load(workspace / "mappings" / "copy_mine.json").rules["a"][SLOT_PLAIN] == "x"


def test_results_are_ranked(workspace):
    from tvtt.profiles import append_result, rank_results, result_record

    for name, score in (("low", 0.1), ("high", 0.9), ("mid", 0.5)):
        append_result(result_record(name, "sig", "zl", "abc", "all", {"coverage": score}))
    assert [r["mapping"] for r in rank_results()] == ["high", "mid", "low"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_init_then_run(workspace, capsys):
    assert main(["init"]) == 0
    assert (workspace / "config.json").exists()
    assert (workspace / "plugins.json").exists()
    assert (workspace / "mappings" / "identity_zl.json").exists()

    capsys.readouterr()
    assert main(["run", "--section", "zodiac", "--no-progress", "--quiet"]) == 0
    latest = (workspace / "output" / "latest.txt").read_text(encoding="utf-8").strip()
    assert (workspace / "output" / latest / "output.txt").exists()


def test_global_flags_work_before_and_after_the_command(workspace):
    main(["init"])
    assert main(["--quiet", "run", "--section", "zodiac", "--no-progress"]) == 0
    assert main(["run", "--section", "zodiac", "--no-progress", "--quiet"]) == 0


def test_set_override_reaches_the_run(workspace, capsys):
    main(["init"])
    capsys.readouterr()
    main(["run", "--set", "selection.currier=B", "--plugin", "transliteration", "--no-progress", "--quiet"])
    assert "Currier B" in capsys.readouterr().out


def test_errors_are_reported_without_a_traceback(workspace, capsys):
    main(["init"])
    code = main(["run", "--plugin", "does_not_exist", "--quiet"])
    assert code == 2
    assert "does_not_exist" in capsys.readouterr().err


def test_info_commands_run(workspace, capsys):
    for argv in (["sections"], ["sources"], ["dictionaries"], ["plugins", "list"], ["plugins", "info", "entropy"]):
        assert main(argv) == 0
        assert capsys.readouterr().out.strip()


def test_doctor_reports_a_clean_workspace(workspace, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["doctor"]) == 0
    assert "No problems found" in capsys.readouterr().out


def test_plugins_enable_disable_and_set(workspace, capsys):
    """Per-plugin edits belong in the advanced file, not the simple one."""
    main(["init"])
    advanced = workspace / "advanced_plugins.json"

    main(["plugins", "enable", "ngrams"])
    document = json.loads(advanced.read_text(encoding="utf-8"))
    assert document["plugins"]["ngrams"]["enabled"] is True

    main(["plugins", "set", "ngrams", "topN", "12"])
    document = json.loads(advanced.read_text(encoding="utf-8"))
    assert document["plugins"]["ngrams"]["settings"]["topN"] == 12

    main(["plugins", "disable", "ngrams"])
    document = json.loads(advanced.read_text(encoding="utf-8"))
    assert document["plugins"]["ngrams"]["enabled"] is False


def test_plugins_preset(workspace):
    main(["init"])
    main(["plugins", "preset", "quick"])
    document = json.loads((workspace / "advanced_plugins.json").read_text(encoding="utf-8"))
    enabled = {n for n, e in document["plugins"].items() if e["enabled"]}
    assert enabled == {"transliteration", "frequency", "entropy", "legend"}


def test_a_named_mapping_that_is_missing_is_an_error(tmp_path, monkeypatch):
    """Falling back to identity would present the manuscript as your result."""
    import pytest

    from tvtt.cli import main
    from tvtt.errors import ConfigError
    from tvtt.paths import set_workspace

    monkeypatch.chdir(tmp_path)
    set_workspace(tmp_path)
    main(["init"])
    with pytest.raises(ConfigError) as excinfo:
        from tvtt.config import load_config
        from tvtt.pipeline import prepare

        prepare(load_config(overrides={"mapping": {"file": "mappings/typo.json"}}))
    assert "mappings/typo.json" in str(excinfo.value)
    assert "does not exist" in str(excinfo.value)


def test_an_unconfigured_folder_still_runs(tmp_path, monkeypatch):
    """Before 'tvtt init' there is no mapping, and identity is the right default."""
    from tvtt.config import load_config
    from tvtt.paths import set_workspace
    from tvtt.pipeline import prepare

    monkeypatch.chdir(tmp_path)
    set_workspace(tmp_path)
    corpus, mapping, engine = prepare(load_config(overrides={"selection": {"sections": ["zodiac"]}}))
    assert len(corpus.loci) > 0
    assert "no mapping file yet" in mapping.meta["name"]
    # The identity fallback really does leave the text alone.
    assert engine.map_words(["chol"]) == ["chol"]


def test_holdout_scores_sections_outside_the_selection(tmp_path, monkeypatch):
    """It used to re-filter inside the selection, so every held-out section was empty."""
    from tvtt.config import load_config
    from tvtt.paths import set_workspace
    from tvtt.pipeline import run as run_pipeline
    from tvtt.plugins import build_registry

    monkeypatch.chdir(tmp_path)
    set_workspace(tmp_path)
    config = load_config(
        overrides={
            "selection": {"sections": ["herbal_a"]},
            "logging": {"level": "error"},
        }
    )
    registry = build_registry()
    outcome = run_pipeline(config, registry, ["holdout"])
    report = outcome.results["holdout"]
    assert "error" not in report, report
    assert report["fit_on"] == "herbal_a"
    held = report["held_out"]
    assert len(held) >= 3, "nothing outside herbal_a was scored: %s" % held
    for row in held:
        assert row["holdout_score"] != 0, "%r scored on no words" % row["held_out"]
    assert {r["held_out"] for r in held} != {"Herbal A"}


def test_a_plugin_that_does_nothing_is_reported(tmp_path, monkeypatch):
    """mapping_diff returns a reason; it used to be swallowed."""
    from tvtt.config import load_config
    from tvtt.paths import set_workspace
    from tvtt.pipeline import run as run_pipeline
    from tvtt.plugins import build_registry

    monkeypatch.chdir(tmp_path)
    set_workspace(tmp_path)
    config = load_config(
        overrides={
            "selection": {"sections": ["zodiac"]},
            "logging": {"level": "error"},
        }
    )
    outcome = run_pipeline(config, build_registry(), ["mapping_diff"])
    assert "mapping_diff" in outcome.results["_skipped"]
    assert any("mapping_diff" in w for w in outcome.manifest.warnings), outcome.manifest.warnings


def test_an_empty_line_mode_is_explained_accurately(tmp_path, monkeypatch):
    """The old message claimed ZL marks no paragraphs. It marks 740."""
    from tvtt.config import load_config
    from tvtt.paths import set_workspace
    from tvtt.pipeline import run as run_pipeline
    from tvtt.plugins import build_registry

    monkeypatch.chdir(tmp_path)
    set_workspace(tmp_path)
    config = load_config(
        overrides={
            "selection": {"lines": "single"},
            "logging": {"level": "error"},
        }
    )
    outcome = run_pipeline(config, build_registry(), ["transliteration"])
    warnings = " ".join(outcome.manifest.warnings)
    assert "740 paragraph" in warnings, warnings
    assert "marks no paragraphs" not in warnings, warnings


def test_holdout_keeps_glyphs_that_only_exist_outside_the_selection():
    """Its engine must know the whole alphabet, or held-out words lose glyphs."""
    from tvtt.corpus import Selection, load_corpus
    from tvtt.mapping import Mapping
    from tvtt.transliterate import build_engine

    zl = load_corpus("zl")
    herbal_a = zl.select(Selection(sections=("herbal_a",)))
    assert "x" not in herbal_a.glyph_counts(), "this test needs a glyph absent from herbal_a"
    assert "x" in zl.glyph_counts()

    rules = {"rules": {"o": "o", "e": "e"}}
    narrow = build_engine(Mapping.from_dict(rules), herbal_a)
    wide = build_engine(Mapping.from_dict(rules), zl)
    # An engine that has never seen 'x' drops it; the one holdout builds keeps it.
    assert narrow.map_word("xoex") == "oe"
    assert wide.map_word("xoex") == "xoex"
