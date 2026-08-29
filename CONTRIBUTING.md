# Contributing to The Voynich Transliteration Tool (TVTT)

TVTT is developed and maintained by a single author, but suggestions and feedback are very
welcome.

You do not need to be a programmer to contribute. Reports, ideas, documentation fixes and
suggestions are all valuable - and so is telling me that a feature's explanation did not
make sense to you, which is a real bug in a tool meant for non-programmers.

## Before you report anything

Run this and include the output:

```bash
tvtt doctor
```

It reports your workspace state, your selection, whether the bundled data is intact, and
which optional packages are installed. Most problems are visible in it.

## Bug reports

Open an issue with the label **Bug Report**, and include as much of the following as you
can:

- what you expected and what happened instead
- the exact command you ran
- the output of `tvtt doctor`
- your operating system and Python version
- any error message from the terminal, in full
- if the run produced output, the `manifest.json` from its run folder

That manifest is the single most useful attachment. It records the tool version, the
configuration and its hash, the checksum of the transcription used, the mapping hash, the
random seed and every warning raised - which is usually enough to reproduce the problem
exactly.

## Feature and improvement requests

Use the label **Feature / Improvement Request** and include:

- what the feature should do
- why it would be useful
- whether it relates to Voynich research specifically or to general usability

If you are proposing a new statistic or test, it helps enormously to say **what result
would count as negative**. TVTT is built around not fooling ourselves, and a measure that
cannot come out badly is not measuring anything.

## Documentation improvements

The documentation lives in [docs/](docs/), with the front page in `README.md`. If any part
of it is confusing or incomplete, either open an issue saying what should change, or send a
pull request with better wording.

The bar for the built-in help is deliberately high: `tvtt plugins info <name>` should
explain what a feature measures, why that matters for this manuscript specifically, and
how to read the result. If one of them falls short of that, please say so.

## Code contributions

The project is currently maintained by Krymorn alone, and larger code contributions are
not being merged yet. That may change. In the meantime, the notes below apply to forks and
to any future contributions.

### Adding a feature

Almost every feature is a plugin: one file in `tvtt/plugins/`, discovered automatically.
See [docs/extending.md](docs/extending.md) for a complete working example. A plugin
that follows the pattern needs no other wiring - it appears in `tvtt plugins list`, gets a
`plugins.json` entry, and can be switched on immediately.

### Standards

```bash
pip install -e ".[dev]"
pytest
ruff check tvtt tests tools
ruff format tvtt tests tools
```

- **No new required dependencies.** The core runs on a clean Python install, and CI
  enforces this by running the whole test suite before any optional package is installed.
  Anything third-party must be optional, detected at run time, and degrade with a message
  telling the user what to install.
- **Tests for new behaviour.** Where a measure has a known correct value on a constructed
  input, assert that value. Where it does not, assert the *ordering* the measure exists to
  detect - that entropy rises when words are anagrammed, that a planted suffix ranks first.
- **Determinism.** Anything stochastic must draw from the configured seed. Two runs with
  the same seed produce identical output, and the test suite checks it.
- **Explain the why.** Comments should say why a piece of code exists, not restate what it
  does. The same goes for plugin help text.

### Bundled data

`tvtt/data/` holds the transliterations, dictionaries, control texts, folio metadata,
schemas and the two Voynich fonts. Do not edit the generated files by hand:

- reference dictionaries and controls are produced by `tools/build_reference_data.py`
- `folios.json` is produced by extracting the IVTFF page variables
- transcription checksums live in `sources.json` and are checked by `tvtt verify`

If you correct a data file, update the script that generates it in the same change, so the
provenance stays checkable.

## Sharing a mapping rather than code

If what you have is a decipherment idea rather than a code change, the tool has a route
for that:

```bash
tvtt mapping export-pack my_idea --out my_idea.tvttpack.json --author "your name"
```

Send that file, together with the `results.json` from your run so the numbers can be
reproduced, to **cmarbel** in a private message on
[voynich.ninja](https://www.voynich.ninja/). Runs that include the baseline plugins are far
more interesting than runs that do not.

## Appreciation

Thank you for helping improve this project, and for all the support.
