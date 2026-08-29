"""Tests for per-run output folders and the simple settings files."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from tvtt.cli import main
from tvtt.config import load_config, write_default_config
from tvtt.errors import ConfigError
from tvtt.paths import set_workspace
from tvtt.plugins import PluginRegistry, build_registry, default_document


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_workspace(tmp_path)
    yield tmp_path
    set_workspace(None)


def _prepare(workspace, plugins: dict):
    from tvtt.util import write_json

    write_default_config(workspace / "advanced_config.json")
    registry = PluginRegistry().discover()
    document = default_document(registry)
    for name, entry in document["plugins"].items():
        entry["enabled"] = name in plugins
        if name in plugins:
            entry.setdefault("settings", {}).update(plugins[name])
    write_json(workspace / "advanced_plugins.json", document)


# --------------------------------------------------------------------------
# Each run keeps its own results
# --------------------------------------------------------------------------


def test_runs_do_not_overwrite_each_other(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}})
    first = run(load_config(overrides={"selection": {"sections": ["zodiac"]}}), build_registry())
    second = run(load_config(overrides={"selection": {"sections": ["herbal_a"]}}), build_registry())

    assert first.output_dir != second.output_dir
    assert Path(first.output_dir).exists() and Path(second.output_dir).exists()
    a = (Path(first.output_dir) / "output.txt").read_text(encoding="utf-8")
    b = (Path(second.output_dir) / "output.txt").read_text(encoding="utf-8")
    assert a != b


def test_run_folders_are_numbered_and_carry_an_info_file(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}})
    first = run(load_config(overrides={"selection": {"sections": ["zodiac"]}}), build_registry())
    second = run(load_config(overrides={"selection": {"sections": ["herbal_a"]}}), build_registry())

    assert Path(first.output_dir).name == "run-001"
    assert Path(second.output_dir).name == "run-002"

    # The folder name is short; what the run did is written inside it.
    info = (Path(second.output_dir) / "info.txt").read_text(encoding="utf-8")
    assert "herbal_a" in info
    assert "random seed" in info
    assert "ZL3b-n.txt" in info
    assert "run" in info.splitlines()[0]


def test_numbering_does_not_reuse_a_deleted_folder(workspace):
    import shutil

    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}})
    overrides = {"selection": {"sections": ["zodiac"]}}
    run(load_config(overrides=overrides), build_registry())
    second = run(load_config(overrides=overrides), build_registry())
    shutil.rmtree(second.output_dir)

    third = run(load_config(overrides=overrides), build_registry())
    assert Path(third.output_dir).name == "run-003", "must not reuse run-002"


def test_the_manifest_records_no_absolute_paths(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}})
    outcome = run(load_config(overrides={"selection": {"sections": ["zodiac"]}}), build_registry())
    manifest = json.loads((Path(outcome.output_dir) / "manifest.json").read_text(encoding="utf-8"))
    blob = json.dumps(manifest)
    assert str(workspace) not in blob, "a shared manifest must not carry anyone's home directory"
    assert not manifest["inputs"]["mapping_file"].startswith(("/", "C:", "c:"))
    assert not Path(manifest["inputs"]["transcription_file"]).is_absolute()


def test_two_runs_in_the_same_second_get_different_folders(workspace):
    from tvtt.config import _unique_run_dir

    root = workspace / "output"
    root.mkdir(parents=True, exist_ok=True)
    first = _unique_run_dir(root, "same-label")
    first.mkdir()
    second = _unique_run_dir(root, "same-label")
    assert first != second


def test_a_custom_run_name_is_used(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}})
    outcome = run(
        load_config(overrides={"selection": {"sections": ["zodiac"]}, "output": {"runName": "my experiment"}}),
        build_registry(),
    )
    assert Path(outcome.output_dir).name == "my-experiment"


def test_separate_folders_can_be_switched_off(workspace):
    from tvtt.pipeline import run

    _prepare(workspace, {"transliteration": {}})
    overrides = {"selection": {"sections": ["zodiac"]}, "output": {"separateRunFolders": False}}
    first = run(load_config(overrides=overrides), build_registry())
    second = run(load_config(overrides=overrides), build_registry())
    assert first.output_dir == second.output_dir == str(workspace / "output")


def test_latest_points_at_the_newest_run(workspace):
    from tvtt.pipeline import run
    from tvtt.runs import latest_run

    _prepare(workspace, {"transliteration": {}})
    run(load_config(overrides={"selection": {"sections": ["zodiac"]}}), build_registry())
    newest = run(load_config(overrides={"selection": {"sections": ["herbal_a"]}}), build_registry())
    assert latest_run(workspace / "output") == Path(newest.output_dir)


def test_keep_runs_prunes_the_oldest(workspace):
    from tvtt.runs import list_run_dirs, prune

    root = workspace / "output"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("a", "b", "c", "d"):
        (root / name).mkdir()
        time.sleep(0.01)
    removed = prune(root, 2)
    assert set(removed) == {"a", "b"}
    assert [p.name for p in list_run_dirs(root)] == ["c", "d"]


def test_runs_command_lists_them(workspace, capsys):
    main(["init"])
    main(["run", "--section", "zodiac", "--no-progress", "--quiet"])
    capsys.readouterr()
    assert main(["runs"]) == 0
    out = capsys.readouterr().out
    assert "zodiac" in out
    assert "1 run(s)" in out


# --------------------------------------------------------------------------
# The simple settings files
# --------------------------------------------------------------------------


def test_simple_config_expands_to_the_full_one():
    from tvtt.simpleconfig import expand_simple_config

    full = expand_simple_config(
        {
            "transcription": "v101",
            "mapping": "mappings/mine.json",
            "section": "herbal_b",
            "currier": "B",
            "scribe": "2",
            "textKind": "running",
            "language": "italian",
            "keepEveryRun": False,
            "seed": 7,
        }
    )
    assert full["transcription"] == "v101"
    assert full["mapping"]["file"] == "mappings/mine.json"
    assert full["selection"]["sections"] == ["herbal_b"]
    assert full["selection"]["currier"] == "B"
    assert full["selection"]["scribes"] == ["2"]
    assert full["selection"]["textClass"] == "running"
    assert full["reference"]["language"] == "italian"
    assert full["output"]["separateRunFolders"] is False
    assert full["random"]["seed"] == 7


def test_blank_simple_values_mean_do_not_restrict():
    from tvtt.simpleconfig import expand_simple_config

    full = expand_simple_config({"section": "", "scribe": "", "currier": "any"})
    assert "sections" not in full.get("selection", {})
    assert "scribes" not in full.get("selection", {})


def test_a_typo_in_the_simple_config_is_caught_with_a_suggestion():
    from tvtt.simpleconfig import expand_simple_config

    with pytest.raises(ConfigError) as excinfo:
        expand_simple_config({"trancsription": "zl"})
    assert "transcription" in str(excinfo.value)


def test_simple_plugins_expand_to_plugin_names():
    from tvtt.simpleconfig import expand_simple_plugins

    document = expand_simple_plugins({"basicStatistics": True, "amIFoolingMyself": False})
    enabled = {k for k, v in document["plugins"].items() if v["enabled"]}
    assert {"entropy", "word_length", "vocabulary", "zipf", "frequency"} <= enabled
    assert not any(document["plugins"].get(n, {}).get("enabled") for n in ("random_controls", "holdout"))


def test_a_typo_in_the_simple_plugins_is_caught():
    from tvtt.simpleconfig import expand_simple_plugins

    with pytest.raises(ConfigError) as excinfo:
        expand_simple_plugins({"basicStatstics": True})
    assert "basicStatistics" in str(excinfo.value)


def test_simple_files_are_written_and_load_back(workspace):
    from tvtt.simpleconfig import write_simple_config, write_simple_plugins

    write_simple_config(mapping="mappings/identity_zl.json")
    write_simple_plugins()
    config = load_config()
    assert config.get("transcription") == "zl"
    assert config.get("mapping.file") == "mappings/identity_zl.json"
    registry = build_registry()
    assert registry.enabled["entropy"] is True
    assert registry.enabled["solve"] is False


def test_the_advanced_file_is_merged_over_the_simple_one(workspace):
    from tvtt.util import write_json

    write_json(workspace / "config.json", {"transcription": "zl", "section": "zodiac", "seed": 1})
    write_json(workspace / "advanced_config.json", {"selection": {"sections": ["herbal_a"]}})
    config = load_config()
    assert config.get("selection.sections") == ["herbal_a"]
    assert config.get("random.seed") == 1


def test_advanced_plugins_override_simple_features(workspace):
    from tvtt.util import write_json

    write_json(workspace / "plugins.json", {"basicStatistics": True})
    write_json(workspace / "advanced_plugins.json", {"plugins": {"entropy": {"enabled": False}}})
    registry = build_registry()
    assert registry.enabled["entropy"] is False
    assert registry.enabled["zipf"] is True


def test_init_writes_simple_files_and_advanced_on_request(workspace):
    assert main(["init"]) == 0
    assert (workspace / "config.json").exists()
    assert (workspace / "plugins.json").exists()
    assert not (workspace / "advanced_config.json").exists()

    assert main(["init", "--advanced", "--force"]) == 0
    assert (workspace / "advanced_config.json").exists()
    assert (workspace / "advanced_plugins.json").exists()


def test_the_simple_config_written_by_init_is_short(workspace):
    main(["init"])
    data = json.loads((workspace / "config.json").read_text(encoding="utf-8"))
    settings = [k for k in data if not k.startswith("_") and k != "note"]
    assert len(settings) <= 12, "the simple config must stay small enough to read at a glance"

    plugins = json.loads((workspace / "plugins.json").read_text(encoding="utf-8"))
    features = [k for k in plugins if not k.startswith("_") and k != "note"]
    assert len(features) <= 12, "the simple plugin switches must stay small enough to read at a glance"


def test_a_full_config_in_the_simple_slot_still_works(workspace):
    """Someone may paste the advanced form into config.json; accept it."""
    from tvtt.util import write_json

    write_json(workspace / "config.json", {"transcription": "v101", "selection": {"sections": ["zodiac"]}})
    config = load_config()
    assert config.get("transcription") == "v101"
    assert config.get("selection.sections") == ["zodiac"]


def test_plugin_edits_go_to_the_advanced_file_and_keep_what_was_on(workspace):
    """Writing a per-plugin block into the simple file would break it."""
    main(["init"])
    before = {n for n, on in build_registry().enabled.items() if on}

    main(["plugins", "enable", "ngrams"])
    assert (workspace / "advanced_plugins.json").exists()

    simple = json.loads((workspace / "plugins.json").read_text(encoding="utf-8"))
    assert "plugins" not in simple, "the simple file must stay in the simple form"

    after = {n for n, on in build_registry().enabled.items() if on}
    assert after == before | {"ngrams"}


def test_plugin_set_and_disable_round_trip(workspace):
    main(["init"])
    main(["plugins", "set", "ngrams", "topN", "12"])
    main(["plugins", "enable", "ngrams"])
    registry = build_registry()
    assert registry.enabled["ngrams"] is True
    assert registry.settings["ngrams"]["topN"] == 12

    main(["plugins", "disable", "ngrams"])
    assert build_registry().enabled["ngrams"] is False


def test_preset_writes_to_the_advanced_file(workspace):
    main(["init"])
    main(["plugins", "preset", "quick"])
    enabled = {n for n, on in build_registry().enabled.items() if on}
    assert enabled == {"transliteration", "frequency", "entropy", "legend"}


def test_mixing_the_two_plugin_styles_is_rejected(workspace):
    from tvtt.util import write_json

    write_json(workspace / "plugins.json", {"basicStatistics": True, "plugins": {"entropy": {"enabled": False}}})
    with pytest.raises(ConfigError) as excinfo:
        build_registry()
    assert "advanced_plugins.json" in str(excinfo.value)


def test_init_honours_an_explicit_config_path(workspace):
    assert main(["init", "--config", "custom.json", "--plugins-file", "custom_plugins.json"]) == 0
    assert (workspace / "custom.json").exists()
    assert (workspace / "custom_plugins.json").exists()
    assert not (workspace / "config.json").exists()


# --------------------------------------------------------------------------
# "--set" reaching the things it names
# --------------------------------------------------------------------------


def test_a_single_value_is_accepted_where_a_list_is_expected(workspace):
    """'--set selection.scribes=2' used to raise TypeError on an int."""
    from tvtt.corpus import selection_from_dict

    assert selection_from_dict({"scribes": 2}).scribes == ("2",)
    assert selection_from_dict({"quires": 13}).quires == ("13",)
    assert selection_from_dict({"sections": "herbal_a"}).sections == ("herbal_a",)
    assert selection_from_dict({"scribes": [1, 2]}).scribes == ("1", "2")
    assert selection_from_dict({"scribes": ""}).scribes == ()


def test_a_quire_is_selectable_by_number_or_by_letter(workspace):
    from tvtt.corpus import load_corpus, selection_from_dict

    by_number = load_corpus("zl").select(selection_from_dict({"quires": 13}))
    by_letter = load_corpus("zl").select(selection_from_dict({"quires": "M"}))
    assert len(by_number.loci) == len(by_letter.loci) > 0


def test_set_reaches_a_plugin_setting(workspace):
    """'--set plugins.<name>.<key>' used to be swallowed by config.json."""
    main(["init"])
    registry = build_registry(None, {"glyph_heatmap": {"axis": "scribe"}})
    assert registry.settings["glyph_heatmap"]["axis"] == "scribe"


def test_set_can_switch_a_plugin_on(workspace):
    main(["init"])
    assert build_registry().enabled["wordcloud"] is False
    assert build_registry(None, {"wordcloud": {"enabled": True}}).enabled["wordcloud"] is True


def test_set_names_an_unknown_plugin_setting(workspace):
    from tvtt.plugins import PluginError

    main(["init"])
    with pytest.raises(PluginError) as excinfo:
        build_registry(None, {"glyph_heatmap": {"axsi": "scribe"}})
    assert "axsi" in str(excinfo.value)


def test_set_names_an_unknown_plugin_and_suggests_one(workspace):
    from tvtt.plugins import PluginError

    main(["init"])
    with pytest.raises(PluginError) as excinfo:
        build_registry(None, {"heatmap": {"axis": "scribe"}})
    message = str(excinfo.value)
    assert "no such plugin" in message and "glyph_heatmap" in message


def test_plugin_overrides_stay_out_of_the_config_hash(workspace):
    """They belong to the registry, so they must not move the manifest hash."""
    import argparse

    from tvtt.cli import _config_for

    def args(overrides):
        return argparse.Namespace(
            overrides=overrides,
            config=None,
            no_cache=False,
            no_progress=False,
            quiet=False,
            verbose=False,
            json_logs=False,
        )

    main(["init"])
    plain = _config_for(args([]))
    tweaked = _config_for(args(["plugins.glyph_heatmap.axis=scribe"]))
    assert "plugins" not in tweaked.data
    assert plain.data == tweaked.data


def test_listings_never_print_an_absolute_path(workspace, capsys):
    """These get pasted into bug reports, so they must not carry a user name."""
    main(["init"])
    for command in (["dictionaries"], ["runs"], ["cache"], ["sources"], ["verify"]):
        main(command)
        out = capsys.readouterr().out
        assert str(workspace) not in out, "%s printed an absolute path" % command[0]


# --------------------------------------------------------------------------
# results.json, the shared results format
# --------------------------------------------------------------------------


def test_a_run_records_a_result(workspace):
    """'tvtt mapping gallery' asks for this file, so a run has to produce it."""
    main(["init"])
    main(["run", "--section", "zodiac", "--plugin", "transliteration", "--no-progress", "--quiet"])
    payload = json.loads((workspace / "results.json").read_text(encoding="utf-8"))
    assert payload["format"] == 1
    record = payload["results"][0]
    assert record["mapping"] == "identity_zl"
    assert record["selection"] == "sections=zodiac"
    assert len(record["transcription_sha256"]) == 64
    assert record["metrics"]["words"] > 0


def test_results_accumulate_across_runs(workspace):
    main(["init"])
    main(["run", "--section", "zodiac", "--plugin", "transliteration", "--no-progress", "--quiet"])
    main(["run", "--section", "herbal_a", "--plugin", "transliteration", "--no-progress", "--quiet"])
    payload = json.loads((workspace / "results.json").read_text(encoding="utf-8"))
    assert [r["selection"] for r in payload["results"]] == ["sections=zodiac", "sections=herbal_a"]


def test_recording_a_result_can_be_switched_off(workspace):
    main(["init"])
    main(
        [
            "run",
            "--section",
            "zodiac",
            "--plugin",
            "transliteration",
            "--set",
            "output.recordResult=false",
            "--no-progress",
            "--quiet",
        ]
    )
    assert not (workspace / "results.json").exists()


def test_results_command_ranks_by_a_metric(workspace, capsys):
    main(["init"])
    main(["run", "--section", "zodiac", "--plugin", "transliteration", "--no-progress", "--quiet"])
    main(["run", "--plugin", "transliteration", "--no-progress", "--quiet"])
    capsys.readouterr()
    assert main(["results", "--metric", "words"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if "identity_zl" in line]
    assert "whole manuscript" in lines[0], "the larger selection should rank first"


def test_results_command_names_an_unknown_metric(workspace, capsys):
    main(["init"])
    main(["run", "--section", "zodiac", "--plugin", "transliteration", "--no-progress", "--quiet"])
    capsys.readouterr()
    assert main(["results", "--metric", "nope"]) != 0
    assert "Recorded metrics" in capsys.readouterr().err


def test_results_command_with_nothing_recorded(workspace, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["results"]) == 0
    assert "No results recorded yet" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Things that used to fail silently
# --------------------------------------------------------------------------


def test_mapping_use_keeps_the_simple_config(workspace):
    """It used to write the whole expanded schema back over the simple file."""
    main(["init"])
    main(["mapping", "init", "trial"])
    main(["mapping", "use", "trial"])
    raw = json.loads((workspace / "config.json").read_text(encoding="utf-8"))
    assert raw["mapping"] == "mappings/trial.json"
    assert "section" in raw and "selection" not in raw, "the simple vocabulary was replaced"
    assert sum(1 for k in raw if k.startswith("_")) >= 8, "the explanations were thrown away"


def test_mapping_use_edits_an_advanced_config_in_place(workspace):
    main(["init", "--advanced"])
    main(["mapping", "init", "trial"])
    main(["mapping", "use", "trial"])
    raw = json.loads((workspace / "config.json").read_text(encoding="utf-8"))
    assert raw["mapping"] == "mappings/trial.json"
    # The advanced file also named a mapping, so it had to be updated too.
    adv = json.loads((workspace / "advanced_config.json").read_text(encoding="utf-8"))
    assert adv["mapping"]["file"] == "mappings/trial.json"


def test_an_advanced_file_that_cancels_the_simple_one_says_so(workspace, caplog):
    import logging

    main(["init"])
    raw = json.loads((workspace / "config.json").read_text(encoding="utf-8"))
    raw["section"] = "zodiac"
    (workspace / "config.json").write_text(json.dumps(raw), encoding="utf-8")
    (workspace / "advanced_config.json").write_text(json.dumps({"selection": {"sections": []}}), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        config = load_config()
    assert config.get("selection.sections") == []
    assert any("overrides" in r.getMessage() for r in caplog.records), "the silent override was not reported"


def test_no_override_warning_when_the_files_agree(workspace, caplog):
    import logging

    main(["init"])
    (workspace / "advanced_config.json").write_text(json.dumps({"performance": {"workers": 2}}), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        load_config()
    assert not [r for r in caplog.records if "overrides" in r.getMessage()]


def test_error_messages_never_carry_an_absolute_path(workspace, capsys):
    """These get pasted into bug reports, so they must not name the account."""
    home = "C:" + chr(92) + "Users"
    main(["init"])
    (workspace / "mappings" / "identity_zl.json").unlink()
    (workspace / "broken.json").write_text("{ not json", encoding="utf-8")
    cases = [
        ["doctor"],
        ["run", "--no-progress"],
        ["mapping", "show"],
        ["mapping", "use", "nosuch"],
        ["mapping", "import-pack", "nosuch.json"],
        ["run", "--config", "broken.json", "--no-progress"],
    ]
    for args in cases:
        capsys.readouterr()
        main(args)
        captured = capsys.readouterr()
        blob = captured.out + captured.err
        assert str(workspace) not in blob, "%s leaked the workspace path" % args
        assert home not in blob, "%s leaked a home directory" % args
        assert "/Users/" not in blob, "%s leaked a home directory" % args


def test_init_advanced_does_not_break_an_existing_workspace(workspace):
    """It used to write the built-in defaults, which pointed at identity_eva."""
    main(["init"])
    main(["init", "--advanced"])
    advanced = json.loads((workspace / "advanced_config.json").read_text(encoding="utf-8"))
    assert advanced["mapping"]["file"] == "mappings/identity_zl.json"
    assert (workspace / advanced["mapping"]["file"]).exists()
    # Adding the advanced file must not change what the run resolves to.
    assert load_config().get("mapping.file") == "mappings/identity_zl.json"


def test_init_advanced_preserves_edits_to_the_simple_file(workspace):
    main(["init"])
    raw = json.loads((workspace / "config.json").read_text(encoding="utf-8"))
    raw["section"] = "herbal_a"
    raw["currier"] = "A"
    (workspace / "config.json").write_text(json.dumps(raw), encoding="utf-8")
    main(["init", "--advanced"])
    advanced = json.loads((workspace / "advanced_config.json").read_text(encoding="utf-8"))
    assert advanced["selection"]["sections"] == ["herbal_a"]
    assert advanced["selection"]["currier"] == "A"


def test_init_advanced_from_scratch_points_at_the_starter_mapping(workspace):
    main(["init", "--advanced"])
    advanced = json.loads((workspace / "advanced_config.json").read_text(encoding="utf-8"))
    assert (workspace / advanced["mapping"]["file"]).exists()
