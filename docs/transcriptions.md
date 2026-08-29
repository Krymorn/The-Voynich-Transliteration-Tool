# The transcriptions

[Back to the README](../README.md)

Nobody works from the manuscript itself. Everybody works from a *transcription*: somebody's
careful, page-by-page record of which shapes appear where.

That record involves judgement at every step. Is a particular mark one glyph or two? Is that
a word break or a gap in the ink? Different transcribers answered differently, which is why
there is more than one file and why a result that only holds on one of them is worth a
second look.

## Contents

- [The nine bundled files](#the-nine-bundled-files)
- [Alphabets](#alphabets)
- [Checksums and updates](#checksums-and-updates)
- [Comparing two transcriptions](#comparing-two-transcriptions)
- [How the files record doubt](#how-the-files-record-doubt)
- [Choosing how to resolve it](#choosing-how-to-resolve-it)
- [Two that are easy to get wrong](#two-that-are-easy-to-get-wrong)

## The nine bundled files

All of them come from René Zandbergen's [voynich.nu](https://www.voynich.nu/).

| Name | Alphabet | By |
|---|---|---|
| `zl` *(default)* | EVA | Zandbergen and Landini. The most complete: all 5,374 lines. |
| `v101` | v101 | Glen Claston. Distinguishes many more glyph shapes than EVA. |
| `v101_native` | v101 | The original v101 file, kept for older work. |
| `takahashi` | EVA | Takeshi Takahashi, from Stolfi's 1999 interlinear file. |
| `voynichese` | EVA | The Takahashi text as used by voynichese.com. |
| `currier` | Currier | Prescott Currier and Mary D'Imperio. Covers about half the book. |
| `fsg` | FSG | The Friedman First Study Group — the oldest machine-readable one. |
| `reference` | EVA | An automatic merge of the v101 and ZL readings. |
| `reference_basic` | EVA | The same, reduced to basic EVA. |

```bash
tvtt sources                          # list them, with their line counts
tvtt run --transcription takahashi    # use a different one
```

**Start with `zl`.** It is the most complete, the most carefully maintained, and the only one
carrying the page metadata that everything else in TVTT relies on.

**Use `v101` when the glyph distinctions matter.** EVA deliberately treats several visually
distinct shapes as the same letter. If your hypothesis turns on whether two similar-looking
glyphs are really the same, EVA has already made that decision for you and v101 has not.

## Alphabets

An alphabet is a naming scheme for shapes, not a set of shapes. EVA calls a particular shape
`k`; v101 calls the same shape `K`. Neither is more correct — they are different ways of
writing down the same manuscript.

This matters in two places:

- **A mapping is written for one alphabet.** Rules for EVA `ch` mean nothing against a v101
  file. `tvtt mapping init` builds the mapping from the transcription you are actually using,
  which avoids the problem.
- **The fonts.** TVTT picks a font to match the alphabet, because drawing EVA text in a v101
  font produces real Voynich shapes that are the wrong ones. See [Reading the
  output](output.md#the-voynich-fonts).

The page metadata — sections, Currier languages, scribes, quires — is read out of the ZL
file and applied to every transcription by folio, so even the v101 file, which carries no
metadata of its own, can be filtered by section.

## Checksums and updates

Every bundled file has its SHA-256 recorded:

```bash
tvtt verify        # check what you have against the release checksums
tvtt fetch --all   # download current versions from voynich.nu and compare
```

A file that has changed upstream is **reported, not treated as an error**. Transcriptions get
corrected over time, and that is a good thing. The point is that you know which version
produced your numbers — the checksum of the file actually used goes into every run's
manifest.

## Comparing two transcriptions

```bash
tvtt run --plugin alignment
```

This lines two transcriptions up locus by locus and lists every place they disagree. Those
spots are exactly where your mapping rests on somebody's judgement rather than on the page,
and they are worth knowing about before you build an argument on one.

## How the files record doubt

The bundled files are in IVTFF, the Intermediate Voynich Transliteration File Format. It
does not just record letters; it records how sure the transcriber was. TVTT reads all of it
rather than throwing it away.

A line from f1r:

```
<f1r.1,@P0>   <%>fachys.ykal.ar.[cth:oto]res.y.kor.sholdy<!@254;>
```

| In the file | Means | What TVTT does |
|---|---|---|
| `.` | a definite word break | word separator |
| `,` | an **uncertain** word break | kept separate; you choose how to treat it |
| `[cth:oto]` | two transcribers read this differently | you choose which reading to take |
| `{ck}` | two glyphs written as one | contents kept |
| `@254;` | a glyph outside the alphabet, given by number | held as one character |
| `?` | one unreadable glyph | you choose |
| `???` | an unknown number of unreadable glyphs | one placeholder, not three |
| `<%>` `<$>` | paragraph start and end | this is what defines a paragraph |
| `<->` | a drawing interrupts the line | **a word break** |

The `<f1r.1,@P0>` at the start is the locus identifier: folio 1r, line 1, with a locus type
saying what kind of text it is — a paragraph, a label, a circular inscription, and so on.
That is where `--text-class labels` gets its information.

Every code here is quoted from the [IVTFF format
definition](https://www.voynich.nu/software/ivtt/IVTFF_format.pdf) rather than guessed,
including the locus types, where `Lf` is a herb fragment in the pharmaceutical section and
`Lp` is a plant in the herbal section. Having those two the wrong way round would make every
report describe the wrong pages.

## Choosing how to resolve it

The `ambiguity` block in `advanced_config.json` controls all of it. Alternate readings can
resolve to the first choice — the transcriber's preferred one — or the last, or every
combination, or you can drop those lines entirely.

Every line remembers whether it was ambiguous, so you can ask directly how much of a result
depends on uncertain readings:

```bash
tvtt run --set selection.dropAmbiguousLines=true
```

If a finding disappears when you do that, it was never about the manuscript.

## Two that are easy to get wrong

**`<->` implies a word space.** It marks text interrupted by a drawing. Treat it as markup
and delete it, and the words on either side fuse together — which invents 764 words that are
not in the ZL file, and changes every word-length and vocabulary statistic downstream.

**`???` means an unknown number of characters.** Writing three placeholders would claim a
length the transcriber specifically refused to commit to. TVTT writes one.

Neither is a subtle theoretical point. Both change the numbers.
