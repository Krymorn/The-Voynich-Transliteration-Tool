# Choosing what to work on

[Back to the README](../README.md)

The manuscript is not one uniform text. In the 1970s Prescott Currier showed that two
statistically distinct "languages", A and B, run through it, differing in vocabulary, word
length and glyph frequencies. The sections differ from each other too, and five different
hands wrote it.

A mapping that suits the herbal pages may fall apart on the bathing-nymph quire. Working on
the whole book at once hides that, so nearly every serious attempt starts by narrowing down.

## Contents

- [The filters](#the-filters)
- [The named sections](#the-named-sections)
- [Currier languages and scribes](#currier-languages-and-scribes)
- [Labels against running text](#labels-against-running-text)
- [Line and word position](#line-and-word-position)
- [Folios and quires](#folios-and-quires)
- [Where the metadata comes from](#where-the-metadata-comes-from)

## The filters

```bash
tvtt run --section herbal_a      # a named section
tvtt run --currier B             # a Currier language
tvtt run --scribe 2              # one scribe's hand
tvtt run --text-class labels     # labels only, no running text
tvtt run --lines first           # only the first line of each paragraph
tvtt run --words first           # only the first word of each line
tvtt run --folio 1r-10v          # a folio or range
```

They combine, and the repeatable ones can be given more than once:

```bash
tvtt run --section herbal_a --section herbal_b --text-class running
```

Anything you would otherwise type every time belongs in `config.json`:

```json
"section": "herbal_a",
"currier": "A"
```

`tvtt doctor` warns you if a combination selects nothing, which usually means two filters
that cannot both be true — asking for running text in a section that is almost all labels,
for instance.

## The named sections

```bash
tvtt sections
```

| Name | What it is | Folios | Words |
|---|---|---|---|
| `herbal_a` | herbal pages in Currier language A | 95 | 8,063 |
| `herbal_b` | herbal pages in Currier language B | 32 | 3,477 |
| `herbal` | both of the above together | 129 | 11,588 |
| `astronomical` | circular astronomical diagrams | 8 | 883 |
| `zodiac` | the zodiac roundels and their nymph labels | 12 | 1,316 |
| `biological` | the bathing-nymph quire, dense Currier B | 19 | 6,377 |
| `cosmological` | cosmological diagrams, including the rosettes foldout | 11 | 2,254 |
| `pharmaceutical` | container and root-and-leaf pages | 16 | 2,589 |
| `recipes` | the short star-marked paragraphs of Quire 20 | 25 | 11,646 |
| `text_only` | pages with writing and no picture | 7 | 2,362 |
| `currier_a` | every page in Currier language A | 114 | 11,620 |
| `currier_b` | every page in Currier language B | 83 | 24,059 |

Word counts are for the default ZL transcription with default settings; they will differ
slightly on another transcription.

`herbal_a` is the usual starting point. It is large enough to measure, linguistically
uniform, and the illustrations at least suggest what the pages are about.

`recipes` and `biological` are the two densest bodies of Currier B, and the place a mapping
developed on Herbal A most often falls over.

## Currier languages and scribes

```bash
tvtt run --currier A
tvtt run --scribe 1
```

Currier A and B are not contiguous — they interleave through the book — so no range of
folios or line numbers can express the split. That is why sections are named rather than
numbered.

Scribe numbers 1 to 5 follow Lisa Fagin Davis' attribution of the manuscript to five hands.
Scribe and Currier language correlate but are not the same thing, and comparing the two
groupings is a reasonable experiment in itself:

```bash
tvtt run --plugin glyph_heatmap --set analysis.heatmapBy=scribe
```

## Labels against running text

```bash
tvtt run --text-class labels
```

The options are `all`, `running`, `labels`, `circular` and `radial`.

Labels — the words written beside plants, stars, containers and zodiac nymphs — are much
shorter than running text and draw on a different vocabulary. Mixing them into a statistical
measurement of running text muddies both. If you have a theory that the labels are names,
this is how you test it against the labels alone.

`circular` and `radial` are text written around or radiating from a diagram, which has its
own layout constraints.

## Line and word position

```bash
tvtt run --lines first      # all, first, last, not_first, single
tvtt run --words first      # all, first, not_first, last
```

In ordinary writing, where a word falls on the page tells you nothing about which word it
is. In the Voynich Manuscript it does. Line-initial words draw on a restricted vocabulary,
first lines of paragraphs behave differently from the rest, and certain glyphs cluster at
line beginnings.

This is the LAAFU effect — "line as a functional unit" — and one of the odder facts about
the text. `--words first` isolates it so you can look at it directly, and
`tvtt run --plugin line_effects` measures it.

Any mapping that produces plausible language has to explain this, because no natural
language does it.

## Folios and quires

```bash
tvtt run --folio f1r
tvtt run --folio 1r-10v
tvtt run --folio 1r-10v --folio 100r-105v
tvtt folios                  # every page with its section, language, scribe and quire
```

Quires are shown by number. The underlying data stores them as a letter from A to T standing
for quires 1 to 20, with P and R skipped because those quires do not exist. What the file
calls `M` is therefore displayed as `13 (M)`, which is what everyone actually calls it. Both
`--quire 13` and `--quire M` work.

## Where the metadata comes from

From the transcription itself. The ZL file records, for every page, which kind of
illustration it has, which Currier language, which scribe, which quire, which bifolio, and
whether the page carries extraneous writing.

TVTT reads those out into `tvtt/data/folios.json` and applies them to any transcription by
folio — so even the original v101 file, which carries no metadata of its own, gets the same
section and language information.

It is a plain JSON file covering all 227 folios. If you disagree with an attribution, put a
corrected copy at `data/folios.json` inside your own working folder and it takes precedence
over the bundled one, with no need to edit the installed package.
