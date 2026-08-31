# Commands

[Back to the README](../README.md)

Every command accepts `--help`. Global flags work before or after the command name.

## Contents

- [The commands](#the-commands)
- [Global flags](#global-flags)
- [run](#run)
- [mapping](#mapping)
- [plugins](#plugins)
- [solve](#solve)
- [Looking things up](#looking-things-up)
- [Checking and maintenance](#checking-and-maintenance)

## The commands

```
tvtt init            set up a folder to work in (--advanced for all the options)
tvtt run             transliterate and run whatever features are on
tvtt analyze         run only the measurements, without writing text output
tvtt solve           search for a mapping automatically
tvtt mapping ...     create, inspect, compare, version and share mappings
tvtt plugins ...     see and change which features run
tvtt runs            list past runs and where their results are
tvtt results         rank every recorded run by a metric
tvtt sections        the parts of the manuscript, with folio counts
tvtt sources         the available transcriptions
tvtt folios          every page with its section, language, scribe and quire
tvtt dictionaries    the reference dictionaries and control texts
tvtt fetch           download transcriptions from voynich.nu and verify them
tvtt verify          check the checksums of the files you have
tvtt build-folios    regenerate the folio metadata from a transcription
tvtt doctor          check your folder and report anything wrong
tvtt web             open the mapping editor in your browser
tvtt cache           inspect or clear the cache
```

## Global flags

| Flag | What it does |
|---|---|
| `--workspace DIR` | use a different working folder |
| `--config FILE` | use a specific config file, on its own with no layering |
| `--plugins-file FILE` | use a specific plugins file |
| `--set KEY=VALUE` | override any setting; repeatable |
| `--quiet` | only warnings and errors |
| `--verbose` | debug logging |
| `--json-logs` | one JSON object per log line |
| `--no-progress` | never draw progress bars |
| `--no-cache` | ignore and do not write the cache |

`--set` takes a dotted path. `plugins.<name>.<setting>` reaches a feature's own options;
anything else reaches `config.json`.

```bash
tvtt run --set selection.currier=B --set plugins.entropy.includeSpaces=true
```

## run

```bash
tvtt run [filters] [--plugin NAME ...] [--seed N] [--output DIR]
```

| Flag | Values |
|---|---|
| `--transcription` | `zl`, `v101`, `v101_native`, `takahashi`, `voynichese`, `currier`, `fsg`, `reference`, `reference_basic` |
| `--mapping FILE` | override the mapping |
| `--section` | a name from `tvtt sections`; repeatable |
| `--currier` | `any`, `A`, `B` |
| `--scribe` | 1 to 5; repeatable |
| `--text-class` | `all`, `running`, `labels`, `circular`, `radial` |
| `--lines` | `all`, `first`, `last`, `not_first`, `single` |
| `--words` | `all`, `first`, `not_first`, `last` |
| `--folio` | a folio or range, e.g. `1r-10v`; repeatable |
| `--plugin` | run only these features; repeatable |
| `--all-plugins` | run every feature, ignoring `plugins.json` |
| `--seed` | the random seed |
| `--output DIR` | where results go |

Filters combine. Quires have no flag of their own; use `--set selection.quires=13` (or `=M`).

`tvtt analyze` takes the same filters but skips writing the transliteration, which is useful
when you only want the numbers.

## mapping

```bash
tvtt mapping init my_idea                    # create one, with every glyph listed
tvtt mapping list                            # what you have
tvtt mapping use my_idea                     # point config.json at one
tvtt mapping show                            # print it as a table
tvtt mapping validate                        # collisions and rule conflicts
tvtt mapping diff old_idea my_idea           # what changed
tvtt mapping history my_idea                 # earlier versions
tvtt mapping restore my_idea 20260828-143000 # go back to one
tvtt mapping export-pack my_idea --out my_idea.tvttpack.json
tvtt mapping import-pack someone_elses.tvttpack.json
tvtt mapping gallery                         # how to submit one
```

Both `.json` and version 1 `.txt` mappings work everywhere a mapping is named. See [Writing
a mapping](mappings.md).

## plugins

```bash
tvtt plugins list                    # every feature with its state
tvtt plugins list --enabled          # only the ones that will run
tvtt plugins info entropy            # full explanation and every setting
tvtt plugins enable ngrams
tvtt plugins disable zipf
tvtt plugins set random_controls runs 500
tvtt plugins preset evaluate         # quick, standard, evaluate, search, full
```

`enable`, `disable` and `set` write to `advanced_plugins.json`, leaving your simple
`plugins.json` alone. See [Optional features](plugins.md).

## solve

```bash
tvtt solve --method anneal --fitness quadgram --language latin
```

| Flag | Values |
|---|---|
| `--method` | `hillclimb`, `anneal`, `genetic` |
| `--fitness` | `quadgram`, `trigram`, `bigram`, `dictionary`, `entropy`, `blend` |
| `--language` | a name from `tvtt dictionaries` |
| `--iterations` | candidate evaluations for hillclimb and anneal |
| `--restarts` | random restarts for hill climbing |
| `--positions` | `none` (default), `edges`, `all` — let a glyph differ by position |
| `--lock GLYPH=LETTER` | fix one glyph; repeatable |
| `--swap-only` | only exchange letters between glyphs |
| `--injective` | force every glyph to a different letter |
| `--save-as NAME` | keep the winner as a mapping |

See [Automatic search](solver.md).

## Looking things up

```bash
tvtt sections        # the twelve named sections, with folio counts
tvtt sources         # the nine transcriptions, with line counts
tvtt folios          # all 227 pages: section, Currier language, scribe, hand, quire
tvtt dictionaries    # the eleven dictionaries and control texts
```

## Checking and maintenance

```bash
tvtt doctor          # your folder, your Python, your optional packages, your data
tvtt verify          # checksums of the transcription files on disk
tvtt fetch --all     # download current versions from voynich.nu and compare
tvtt runs            # past runs, with the settings each used
tvtt runs --prune 10 # keep only the newest ten
tvtt results         # every recorded run, ranked; --metric picks the column
tvtt cache           # what is cached and how big it is
tvtt cache clear     # delete it; always safe
```

`tvtt build-folios` rebuilds `data/folios.json` from a transcription's page
variables. The bundled table is generated rather than hand-written, and this is
what generates it. You will not normally need it — it exists for the case where
the file is missing or you want to check the bundled one is reproducible:

```bash
tvtt build-folios                        # from ZL, into data/folios.json here
tvtt build-folios --transcription v101
```

It writes into your working folder, which takes precedence over the bundled
copy, so the installed package is never touched.

`tvtt doctor` is the first thing to run when anything behaves unexpectedly. It checks the
things that are easy to get wrong and hard to notice: a mapping pointing at a file that does
not exist, a selection that matches nothing, a missing optional package, a data file that
does not match its checksum.
