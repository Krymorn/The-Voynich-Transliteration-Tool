# Optional features

[Back to the README](../README.md)

Almost everything beyond "apply the mapping and write the text" is an optional feature you
switch on. There are 36. Ten are on to start with; the rest are off because nobody needs all
of them at once and some take minutes.

## Contents

- [Switching them on](#switching-them-on)
- [Presets](#presets)
- [Making things readable](#making-things-readable)
- [Checking the mapping](#checking-the-mapping)
- [Measuring the text](#measuring-the-text)
- [Baselines and controls](#baselines-and-controls)
- [Matching and searching](#matching-and-searching)
- [Settings](#settings)

## Switching them on

```bash
tvtt plugins list              # all 36, one line each, with their state
tvtt plugins info entropy      # the full explanation and every setting
tvtt plugins enable ngrams
tvtt plugins disable zipf
```

`tvtt plugins info` is worth using rather than guessing. Each feature explains what it
measures, why that matters for this manuscript specifically, and how to read the result.

For a single run, without changing any file:

```bash
tvtt run --plugin legend --plugin entropy    # only these
tvtt run --all-plugins                       # everything, ignoring plugins.json
tvtt run --set plugins.ngrams.enabled=true   # add one to whatever is already on
```

`plugins.json` groups them for convenience, so `"deeperStatistics": true` switches on seven
related features at once. See [Settings](configuration.md#pluginsjson).

## Presets

```bash
tvtt plugins preset quick       # the basics, a couple of seconds
tvtt plugins preset standard    # the usual statistics plus the web report
tvtt plugins preset evaluate    # everything needed to judge a mapping honestly
tvtt plugins preset search      # automatic search, with the checks that keep it honest
tvtt plugins preset full        # all 36, including the slow ones
```

A preset replaces what is currently on rather than adding to it.

## Making things readable

| Feature | What you get |
|---|---|
| `transliteration` | `output.txt` — your mapping applied |
| `html_report` | the main web page: text, search, section filter, glyph highlighter, page images |
| `legend` | the glyph cheat sheet, in text and HTML |
| `comparison` | a plain two-column view of source against output |
| `wordcloud` | a word frequency table and a browsable cloud |
| `glyph_heatmap` | how glyph frequencies differ between sections, folios or scribes |
| `plots` | Zipf, Heaps, word length and transition charts (needs matplotlib) |
| `bundle` | every file from the run gathered into one self-contained HTML document |
| `translate` | machine translation of your output — off by default, see [the network](reproducibility.md#the-network) |

`glyph_heatmap` is the quickest way to see Currier A and B with your own eyes: several
glyphs are dramatically more common in one than the other, and the split is visible as soon
as the rows are sorted.

## Checking the mapping

| Feature | What it checks |
|---|---|
| `roundtrip` | whether your mapping is reversible, and every collision if not |
| `conflicts` | every place two rules overlap, and which one wins |
| `mapping_diff` | what changed between two mappings, and how the numbers moved |
| `alignment` | where two transcriptions disagree |

`roundtrip` deserves a word. A mapping is *reversible* when no two glyphs produce the same
letters. Non-reversible mappings are perfectly legitimate — plenty of real ciphers merge
symbols — but merging raises dictionary hit rates for free, because more Voynich words
collapse onto the same output word and some of those land on real words by accident. This
tells you how much of that is happening.

## Measuring the text

| Feature | What it measures |
|---|---|
| `frequency` | glyph, character and word counts |
| `entropy` | how predictable the text is, at orders 0 to 3 |
| `word_length` | the length distribution and its shape |
| `vocabulary` | type/token ratio, MATTR, hapax legomena, Heaps' law |
| `zipf` | rank against frequency, with the fitted exponent |
| `ngrams` | which characters follow which |
| `positional` | where in a word each character likes to sit |
| `slot_grammar` | whether words still follow a rigid template |
| `affixes` | prefixes and suffixes, ranked by how surprising they are |
| `repeats` | how much the text repeats itself, and at what distance |
| `line_effects` | line-position effects and the LAAFU test |
| `vowels` | Sukhotin's vowel detection, plus a real test of it |
| `section_report` | all of the above, per section, with the differences |

What the numbers actually mean is in [Measuring the text](analysis.md). `section_report` is
often the single most informative output: Currier's A and B show up immediately, and so does
anything odd about a mapping.

## Baselines and controls

These are the ones that tell you whether a result means anything.

| Feature | The question it answers |
|---|---|
| `random_controls` | Does your mapping beat mappings that mean nothing? |
| `match_significance` | How many dictionary hits would chance have produced? |
| `shuffles` | Which of your statistics actually detect structure? |
| `synthetic` | Can your statistics tell the manuscript from meaningless imitation? |
| `language_controls` | What do these numbers look like for real languages? |
| `holdout` | Does the result survive on text you did not tune it on? |
| `overfitting` | Are your extra rules earning their keep? |

All seven at once:

```bash
tvtt plugins preset evaluate
tvtt run
```

Most are marked slow, and a full evaluation run takes one to three minutes. See [Checking a
mapping honestly](validation.md).

## Matching and searching

| Feature | What it does |
|---|---|
| `corpus_match` | scores the output against a real dictionary, with a confidence per word |
| `solve` | searches for a mapping automatically |
| `sweep` | runs the solver once per combination in a parameter grid and ranks the results |

See [Checking a mapping honestly](validation.md#matching-against-a-real-language) and
[Automatic search](solver.md).

## Settings

Every feature has its own settings, at sensible defaults. To see them:

```bash
tvtt plugins info random_controls
```

To change one:

```bash
tvtt plugins set random_controls runs 500          # written to advanced_plugins.json
tvtt run --set plugins.random_controls.runs=500     # just this run
```

A misspelt setting name is refused with the list of real ones, rather than quietly ignored.

`tvtt init --advanced` writes `advanced_plugins.json` containing every feature with every
setting at its default, if you would rather read them all in one place.
