# Bundled reference data

[Back to the README](../README.md)

Everything TVTT needs is bundled, so a fresh install works on a machine that has never been
online.

## Contents

- [What is included](#what-is-included)
- [Dictionaries and control texts](#dictionaries-and-control-texts)
- [Where they came from](#where-they-came-from)
- [What they are not](#what-they-are-not)
- [Using your own](#using-your-own)
- [The fonts](#the-fonts)

## What is included

| | |
|---|---|
| Nine transcriptions | from voynich.nu, with checksums — see [The transcriptions](transcriptions.md) |
| Page metadata | all 227 folios: section, Currier language, scribe, Currier hand, quire, bifolio, extraneous writing |
| Eleven dictionaries | word frequency lists |
| Eleven control texts | running text in the same languages |
| Two Voynich fonts | Fairfax EVA HD and Fairfax V101 HD |

```bash
tvtt sources         # the transcriptions
tvtt folios          # the page metadata
tvtt dictionaries    # the dictionaries and control texts
```

## Dictionaries and control texts

| Language | Source text |
|---|---|
| Latin | Vergil, Augustine, Linnaeus |
| Italian | Dante |
| English | the King James Bible, Austen |
| Middle English | Chaucer |
| Middle High German | Walther von der Vogelweide |
| Czech | Čapek |
| Occitan | a Gascon text |
| Hebrew | the Torah, consonantal |
| Hebrew in Latin letters | the same, transliterated |
| Arabic | the Quran, consonantal |
| Arabic in Latin letters | the same, transliterated |

A **dictionary** is a word frequency list, used to ask "is this a real word, and how common
is it?". A **control text** is running text, used to compute the same statistics on real
language for comparison.

Hebrew and Arabic appear twice on purpose. A mapping that produces Latin letters needs
something in Latin letters to compare against, so the transliterated versions exist for
exactly that case. Both are stored consonantally, with vowel points stripped, which is also
what the `abjad` matching route in `corpus_match` assumes.

## Where they came from

All public domain, via Project Gutenberg, [Sefaria](https://www.sefaria.org/) for the Torah,
and alquran.cloud for the Quran.

`tools/build_reference_data.py` is the script that produced every one of them, and it is kept
in the repository deliberately. If you want to know how a word list was tokenised, which
edition it came from, or whether some preprocessing step biased it, you can read the code
that made it rather than taking the file on trust.

## What they are not

**These are samples, not corpora.** A couple of hundred kilobytes each.

Use them to see whether a number is in the right neighbourhood — is my output's entropy
nearer Latin's or nearer the manuscript's? They are not large enough to reliably distinguish
between languages, and a result of the form "it matches Occitan better than Italian" cannot
be supported by samples this size.

If you need to make that kind of claim, bring your own corpus.

## Using your own

Drop `.txt` files into `reference_texts/` in your working folder, named after the language:

```
reference_texts/
  latin.txt        replaces the bundled Latin sample
  gallo_italic.txt a language that was not there before
```

They are picked up automatically and appear in `tvtt dictionaries`. Plain running text is
fine — TVTT builds the frequency list itself.

You can also override any bundled data file by putting a replacement in `data/` inside your
working folder. See [Settings](configuration.md#overriding-bundled-data).

## The fonts

Two fonts from Rebecca Bettencourt's Voynich Unicode package, bundled under the SIL Open Font
Licence:

| Font | Covers |
|---|---|
| Fairfax EVA HD | EVA, 102 of 113 glyphs |
| Fairfax V101 HD | v101, all 170 glyphs |

TVTT picks between them by the transcription's alphabet, with no fallback, because rendering
EVA text in a v101 font produces genuine Voynich shapes that are the wrong ones. See [Reading
the output](output.md#the-voynich-fonts).

The licence text is at `tvtt/data/fonts/OFL.txt` and ships with the package, as the OFL
requires. The fonts are not modified.
