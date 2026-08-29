# Writing your own feature

[Back to the README](../README.md)

A feature is one file. Drop it in `tvtt/plugins/` and it is found automatically — there is
no registry to edit and nothing else to wire up.

## Contents

- [A complete example](#a-complete-example)
- [The context object](#the-context-object)
- [Stages](#stages)
- [Settings](#settings)
- [Depending on another feature](#depending-on-another-feature)
- [Project layout](#project-layout)
- [Tests](#tests)

## A complete example

Create `tvtt/plugins/my_idea.py`:

```python
from . import Plugin, PluginContext


def run(ctx: PluginContext) -> dict:
    words = ctx.result.words()
    longest = max(words, key=len)
    path = ctx.output_path("my_idea.txt")
    path.write_text(longest, encoding="utf-8")
    ctx.record_output(path, "the longest word in the output")
    return {"longest_word": longest}


PLUGIN = Plugin(
    name="my_idea",
    title="My idea",
    stage="analyze",
    category="statistics",
    summary="Finds the longest word.",
    help="A longer explanation, shown by 'tvtt plugins info my_idea'.",
    defaults={},
    run=run,
)
```

That is all of it. The feature now appears in `tvtt plugins list` and can be switched on with
`tvtt plugins enable my_idea`.

Two conventions worth following:

- **`record_output`** is what puts your file in `info.txt` and the manifest with a
  description. Skip it and the file still gets written, but nobody knows what it is.
- **Return a dict of plain values.** Later features read it through `ctx.results["my_idea"]`,
  and the headline entries reach the manifest, so keep it JSON-safe and stable between runs.

If your feature produces numbers somebody might want to parse, write them out yourself as
JSON or CSV alongside the text — that is what `glyph_heatmap`, `solve` and `corpus_match`
do.

## The context object

`ctx` gives you everything the run has produced so far:

| Attribute | What it is |
|---|---|
| `ctx.corpus` | the selected lines, with their folio metadata |
| `ctx.result` | the mapped text: `.text()`, `.words()`, `.lines`, `.word_counts()`, `.letters()` |
| `ctx.settings` | your feature's settings, merged over its defaults |
| `ctx.results` | what earlier features returned, keyed by name |
| `ctx.config` | the whole configuration |
| `ctx.log` | the logger |
| `ctx.output_path(name)` | a path inside this run's folder |
| `ctx.record_output(path, description)` | register a file you wrote |
| `ctx.setting(key, default)` | one setting, with a fallback |

`ctx.corpus.loci` is the list of lines. Each locus carries its folio, line number, locus
type, section, Currier language, scribe and quire, so filtering inside a feature is
straightforward.

## Stages

Features run in stage order, so a feature can rely on earlier ones having finished.

| Stage | For |
|---|---|
| `prepare` | anything that must happen before the mapping is applied |
| `analyze` | measurements |
| `baseline` | controls and null models |
| `search` | solvers |
| `report` | anything that reads other features' results and writes a document |

Within a stage the order is not guaranteed. If you need another feature's output, declare it
rather than assuming.

## Settings

```python
PLUGIN = Plugin(
    name="my_idea",
    ...
    defaults={"topN": 10, "writeCsv": False},
    settings_help={
        "topN": "How many words to list.",
        "writeCsv": "Also write my_idea.csv.",
    },
    run=run,
)
```

`defaults` defines both the values and the set of valid names — a setting not in `defaults`
is refused with a suggestion, wherever it was set. `settings_help` is what
`tvtt plugins info my_idea` prints.

Read them with `ctx.setting("topN", 10)` or `ctx.settings["topN"]`.

## Depending on another feature

```python
PLUGIN = Plugin(
    name="my_report",
    ...
    requires=["frequency"],
    optional_requires=["entropy"],
    run=run,
)
```

`requires` means the run fails with a clear message if that feature is off.
`optional_requires` means "use it if it ran": check `ctx.results.get("entropy")` and carry on
without it if it is not there.

Mark a slow feature with `heavy=True` so `tvtt plugins list` shows it as slow and the quick
presets leave it out.

## Project layout

```
tvtt/
  cli.py            the command line
  pipeline.py       a run, start to finish
  ivtff.py          reads the transcription files
  corpus.py         picking part of the manuscript
  folios.py         sections, Currier languages, scribes, quires
  mapping.py        the mapping engine
  fonts.py          picking a Voynich font to match the alphabet
  analysis.py       every measurement
  baselines.py      shuffles, synthetic text, controls
  lexicon.py        dictionaries, abbreviations, stemming, fuzzy search
  matcher.py        scoring against a real language
  langmodel.py      n-gram models and fitness functions
  solver.py         hill climbing, annealing, genetic search
  reporting.py      HTML, charts and text output
  profiles.py       mapping profiles, versions, packs
  simpleconfig.py   the plain-language settings
  runs.py           numbered output folders
  manifest.py       the run manifest
  webapp/           the browser editor
  plugins/          36 features, one file each
  data/             transcriptions, dictionaries, controls, schemas, fonts
tests/              225 tests
tools/              the script that built the bundled reference data
```

And in your own working folder:

```
config.json              what to run
plugins.json             which features run
advanced_*.json          optional: everything else
mappings/                your mappings, with earlier versions kept
output/run-001, ...      one folder per run
reference_texts/         your own dictionaries and control texts
data/                    optional overrides of any bundled data file
```

## Tests

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

The suite runs in about seven seconds and does not touch the network. If you add a feature,
a test that runs it on a small selection and checks the shape of what it returns is enough.

Determinism is worth testing explicitly if your feature uses randomness: run it twice with
the same seed and assert the results match.
