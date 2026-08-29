# Settings

[Back to the README](../README.md)

TVTT has a lot of options, and showing all of them to someone on their first day would be
unhelpful. So there are two layers: a short file with the settings most people change, and
an optional long one with everything else.

## Contents

- [config.json](#configjson)
- [plugins.json](#pluginsjson)
- [Changing something for one run](#changing-something-for-one-run)
- [The advanced files](#the-advanced-files)
- [Mistakes get caught](#mistakes-get-caught)
- [Overriding bundled data](#overriding-bundled-data)

## config.json

Written by `tvtt init`. Ten settings:

```json
{
  "transcription": "zl",
  "mapping": "mappings/identity_zl.json",
  "section": "",
  "currier": "any",
  "scribe": "",
  "textKind": "all",
  "language": "latin",
  "outputFolder": "output",
  "keepEveryRun": true,
  "seed": 20260828
}
```

The real file has an explanation above each line, which is left out here for room:

```json
  "_currier": "Restrict to a Currier language: \"A\", \"B\", or \"any\".",
  "currier": "any",
```

| Setting | What it does |
|---|---|
| `transcription` | which record of the manuscript to read (`tvtt sources`) |
| `mapping` | your mapping file |
| `section` | which part of the book (`tvtt sections`), or `""` for all of it |
| `currier` | `"A"`, `"B"` or `"any"` |
| `scribe` | one scribe, 1 to 5, or `""` for all |
| `textKind` | `"all"`, `"running"` or `"labels"` |
| `language` | the language you are testing against (`tvtt dictionaries`) |
| `outputFolder` | where results go |
| `keepEveryRun` | `true` gives every run its own folder; `false` reuses one and overwrites |
| `seed` | the random seed; the same seed always gives the same results |

Anything left as `""` or `"any"` means "do not restrict".

The keys beginning with an underscore are comments. JSON has no comment syntax, so this is
the usual workaround; TVTT ignores them, and you can delete them if you find them noisy.

## plugins.json

Which features run. Same style, and each switch turns on a related group rather than a
single feature:

```json
{
  "_readableText": "Write the transliterated text and a glyph cheat sheet.",
  "readableText": true,

  "_webReport": "One web page with the text, the manuscript images and the statistics.",
  "webReport": true,

  "_basicStatistics": "The usual measurements: frequencies, entropy, word length, vocabulary, Zipf.",
  "basicStatistics": true,

  "_checkMyMapping": "Check the mapping is reversible and that no two rules contradict each other.",
  "checkMyMapping": true,

  "_deeperStatistics": "The harder measurements: transitions, positions, slot grammar, affixes, repetition, line effects, vowels.",
  "deeperStatistics": false,

  "_comparePartsOfTheBook": "Run everything per manuscript section and show where they differ.",
  "comparePartsOfTheBook": false,

  "_compareWithRealLanguage": "Match the output against a real dictionary, and against real languages.",
  "compareWithRealLanguage": false,

  "_amIFoolingMyself": "The honesty checks: random mappings, shuffles, a null model, held-out text, overfitting.",
  "amIFoolingMyself": false,

  "_pictures": "Charts and a word cloud. Needs matplotlib for the charts.",
  "pictures": false,

  "_findAMappingForMe": "Search automatically for a mapping. Slow, and read the warnings it prints.",
  "findAMappingForMe": false
}
```

Four groups are on to start with, which is ten individual features. The rest are off because
nobody needs all of them at once and some take minutes.

To switch features on and off individually rather than by group:

```bash
tvtt plugins list              # every feature, with its state
tvtt plugins enable ngrams
tvtt plugins disable zipf
tvtt plugins preset evaluate   # a ready-made set
```

See [Optional features](plugins.md).

## Changing something for one run

Every command line flag beats the file, and `--set` reaches any setting at all:

```bash
tvtt run --section herbal_a
tvtt run --set selection.currier=B
tvtt run --set plugins.glyph_heatmap.axis=scribe
tvtt run --set plugins.wordcloud.enabled=true
```

`--set` takes `KEY=VALUE`, is repeatable, and the key is the dotted path to the setting.
`plugins.<name>.<setting>` reaches a feature's own options; everything else reaches
`config.json`. A misspelt setting or feature name is refused with a suggestion rather than
quietly ignored.

Nothing typed on the command line is written back to your files.

## The advanced files

There are far more options than the ten above: how to handle ambiguous readings, which rule
takes precedence over which, and individual settings for all 36 features.

```bash
tvtt init --advanced
```

That writes `advanced_config.json` and `advanced_plugins.json` with every setting spelled
out at its default value.

These are merged **on top of** the simple files, so you only need to keep the lines you
actually change. Delete them and you are back where you started.

The simple names are not a reduced mode. `"section": "herbal_a"` means exactly the same
thing as `"selection": {"sections": ["herbal_a"]}` in the advanced file — it is the same
engine reading the same setting either way. The short file is a smaller vocabulary for the
same language, not a beginner's version of the tool.

Some things only the advanced file can express, because they have no sensible one-line form:

| Block | What it controls |
|---|---|
| `selection` | every filter: several sections at once, folio ranges, quires, locus types |
| `ambiguity` | how uncertain word breaks, unreadable glyphs and alternate readings are resolved |
| `mapping` | rule precedence, the positional markers, what to do with unmapped glyphs |
| `reference` | which language to compare against, and where your own texts live |
| `random` | the seed for everything stochastic |
| `performance` | caching, worker processes, progress bars |
| `output` | run folders, word separators, what gets written |
| `network` | offline mode, timeouts |
| `logging` | how much the tool tells you, and in what format |

Settings that belong to one feature — which matching routes the dictionary comparison uses,
how many random mappings to score, which axis the heatmap groups by — live in
`advanced_plugins.json` rather than here. `tvtt plugins info <name>` prints every setting a
feature has, with an explanation of each.

## Mistakes get caught

Both files are checked when they load, and a typo is named rather than ignored:

```
Error: plugins.json is not valid:
  root: unknown key 'entrpy' (did you mean 'entropy'?)
```

Mixing the simple and advanced styles inside one file is refused rather than half-applied,
because quietly applying some of your settings and not others would be the worst possible
outcome. If you want both, keep them in their two files.

Installing the optional `jsonschema` package makes the checking stricter still; without it
TVTT falls back to its own validation, which catches the same common mistakes.

## Overriding bundled data

TVTT looks in your working folder before it looks inside itself. Put a file at
`data/<name>` in your own folder and it wins over the bundled one:

| Your file | Overrides |
|---|---|
| `data/folios.json` | the page metadata: sections, Currier languages, scribes, quires |
| `data/iiif.json` | where page images are fetched from |
| `data/sources.json` | the transcription list and its checksums |
| `reference_texts/<language>.txt` | a dictionary or control text |
| `transcriptions/<file>.txt` | a transcription |

Nothing in the installed package ever needs editing, which means an update will not throw
your changes away.
