# Writing a mapping

[Back to the README](../README.md)

A mapping is your hypothesis about what the Voynich glyphs stand for. Everything else in
TVTT exists to apply one, show you the result, or test it.

## Contents

- [The file](#the-file)
- [The four kinds of rule](#the-four-kinds-of-rule)
- [Positional rules](#positional-rules)
- [Which rule wins](#which-rule-wins)
- [Keep the glyph list open](#keep-the-glyph-list-open)
- [A warning about positional rules](#a-warning-about-positional-rules)
- [Checking a mapping](#checking-a-mapping)
- [Versions](#versions)
- [Mappings from version 1](#mappings-from-version-1)
- [Editing in your browser](#editing-in-your-browser)
- [Sharing](#sharing)

## The file

A mapping is a small JSON file in `mappings/`. The glyph is on the left, what it becomes is
on the right:

```json
{
  "meta": {
    "name": "my_idea",
    "language": "latin",
    "notes": "reads the gallows as Latin abbreviations"
  },
  "rules": {
    "o": "o",
    "e": "e",
    "d": "d",
    "y": "s",
    "ch": "th"
  }
}
```

Only `rules` is required. `meta.language` tells the dictionary matching which language to
compare against; `meta.notes` is for you.

Rather than typing the glyphs out, generate the file:

```bash
tvtt mapping init my_idea
```

That writes a mapping listing every glyph that actually appears in your transcription, each
mapped to itself, ordered by frequency. You then edit the right-hand side. Nothing is
missing and nothing is invented.

```bash
tvtt mapping list          # what you have
tvtt mapping use my_idea   # point config.json at one
tvtt mapping show          # print the current one as a table
```

## The four kinds of rule

**One glyph, one letter.** The ordinary case.

```json
"o": "a"
```

**One glyph, several letters.** For a glyph you read as a scribal abbreviation, or a
digraph.

```json
"9": "con"
```

**Several glyphs, one letter.** The group is treated as a single unit.

```json
"ch": "k"
```

The longest group always wins. If you have rules for both `c` and `ch`, then in the text
`chol` the pair `ch` is taken as one glyph and the `c` rule does not apply there. This is
what lets you treat EVA's `ch`, `sh`, `cth`, `ckh` and so on as the single characters many
people believe they are.

**Different letters in different places.** See below.

## Positional rules

Voynichese glyphs are strikingly positional. In EVA, `q` almost only ever starts a word,
`n` almost only ever ends one, and the gallows characters cluster at the start of lines and
paragraphs. A mapping often needs to say "this glyph, but only here":

```json
{
  "rules": {
    "9": { "plain": "n", "final": "s" },
    "o": { "plain": "o", "initial": "u" }
  }
}
```

| Position | When it applies |
|---|---|
| `plain` | anywhere, unless something more specific matches |
| `initial` | only at the start of a word |
| `final` | only at the end of a word |
| `occurrence1` to `occurrence4` | the 1st, 2nd, 3rd or 4th time that glyph appears in the word |

`occurrence` rules are for the case where a repeated glyph is not the same letter each time
— a doubled character standing for something else, for instance.

## Which rule wins

When more than one rule could apply to the same glyph in the same place, the order is:

1. `initial`
2. `final`
3. `occurrence`
4. `plain`

You can change this order in `advanced_config.json`, under `mapping.precedence`. You never
have to guess what happened:

```bash
tvtt mapping validate      # collisions and overlapping rules
tvtt run --plugin conflicts
```

`conflicts.txt` lists every glyph where two rules overlap and says which one won, and where.

## Keep the glyph list open

```bash
tvtt run --plugin legend
```

This writes `legend.txt` and `legend.html`: every glyph in the transcription, drawn in a
Voynich font, with how often it turns up, what your mapping does with it, and which glyphs
have no rule yet. A glyph with no rule passes through unchanged, which is fine while you
work but easy to forget about.

Keep `legend.html` open in a browser tab and refresh it after each run.

## A warning about positional rules

Each positional rule is another dial you can turn. Turn enough of them and you can make any
text look like anything, and the result stops being evidence of anything.

There is a check for this:

```bash
tvtt run --plugin overfitting
```

It scores your mapping, then scores the same mapping stripped back to plain rules, and
tells you how much the extra complexity actually bought. If forty positional rules improve
the score by a fraction of a percent, they are decoration.

See [Checking a mapping honestly](validation.md).

## Checking a mapping

```bash
tvtt mapping validate
```

This reports two things.

**Collisions** — two glyphs producing the same letters. A mapping with no collisions is
*reversible*: you could recover the original glyphs from the output. Non-reversible mappings
are allowed, and plenty of real ciphers merge symbols, but merging raises dictionary hit
rates for free. More Voynich words collapse onto the same output word, and some of those
land on real words by accident. `tvtt run --plugin roundtrip` measures how much of that is
going on.

**Conflicts** — rules that overlap, such as a `ch` rule and a `c` rule, or a `plain` and a
`final` for the same glyph. These are normal and usually intentional. The report is there so
that they are intentional.

## Versions

Every time TVTT saves a mapping, it keeps the previous one:

```bash
tvtt mapping history my_idea
tvtt mapping restore my_idea 20260828-143000
tvtt mapping diff old_idea my_idea
```

`diff` shows which rules changed and, if both mappings have been run, how the numbers moved.
`tvtt run --plugin mapping_diff` does the same as part of a run.

## Mappings from version 1

TVTT reads the plain text mapping lists that versions before 1.8 used, so old work still
runs. Put the `.txt` file in `mappings/` and point at it as normal:

```
0=f~f          glyph f becomes f
53=9~con       glyph 9 becomes the three letters "con"
105=4o~d@      the pair "4o" becomes d, but only at the start of a word
7=y~s/         y becomes s at the end of a word
8=o~u'         o becomes u the first time it appears in a word
```

Each line is `number=glyph~letters`, with the same trailing markers as before:

| Marker | Meaning |
|---|---|
| `@` | at the start of a word |
| `/` | at the end of a word |
| `'` | the first occurrence in a word |
| `"` | the second |
| `:` | the third |
| `;` | the fourth |

The leading number was an internal index in the old tool. It is read and ignored, so it does
not matter whether yours are in order or have gaps. Blank lines and lines beginning with `#`
are skipped. If a line is malformed, the error names its line number.

```bash
tvtt mapping use my_old_mapping     # a .txt file works the same as a .json one
```

Nothing is converted on disk. TVTT writes JSON when it saves, so if you edit the mapping
through `tvtt web` and save it, you get a `.json` copy and your original file is left alone.

The old flat JSON style — `{"f": "a@"}` with the markers inside the string — is also still
read. See [Coming from version 1](migrating-from-v1.md).

## Editing in your browser

```bash
tvtt web
```

Opens a page with the glyphs down the left and the transliterated text on the right. Type a
letter and the text updates as you type. There is a button to recompute the statistics, and
one to save what you have as a named mapping.

It runs on Python's own web server, so there is nothing to install, and it listens only on
your own machine.

## Sharing

```bash
tvtt mapping export-pack my_idea --out my_idea.tvttpack.json --author "your name"
tvtt mapping import-pack someone_elses.tvttpack.json
```

A pack holds one or more mappings with their metadata and version history in a single file.
`tvtt mapping gallery` prints how to submit one to the community gallery.
