# Getting started

[Back to the README](../README.md)

This walks through the first half hour: installing, running the tool once, understanding
what came out, and making your first real change.

You do not need to know how to program. You edit two small settings files and one mapping
file, all plain text, and type `tvtt run`.

## Contents

- [Installing](#installing)
- [Setting up a folder](#setting-up-a-folder)
- [Your first run](#your-first-run)
- [What you got](#what-you-got)
- [Making a change](#making-a-change)
- [A sensible next step](#a-sensible-next-step)

## Installing

You need Python 3.9 or newer, and nothing else.

```bash
git clone https://github.com/Krymorn/The-Voynich-Transliteration-Tool.git
cd The-Voynich-Transliteration-Tool
pip install -e .
```

`pip install -e .` installs it in place, so if you pull an update later you do not have to
reinstall. You now have a `tvtt` command:

```bash
tvtt --version
```

If your shell reports that `tvtt` is not found, Python installed it somewhere that is not on
your path. Use `python -m tvtt` instead — every example in these documents works the same
way with that prefix.

### Optional extras

The tool runs completely without these. It tells you which one to install if you switch on
something that needs it.

```bash
pip install -e ".[plots]"        # charts as image files (matplotlib)
pip install -e ".[interactive]"  # interactive charts (plotly)
pip install -e ".[progress]"     # progress bars on long runs (tqdm)
pip install -e ".[schema]"       # stricter settings validation (jsonschema)
pip install -e ".[all]"          # all of the above
```

```bash
tvtt doctor
```

`doctor` reports your Python version, which extras you have, whether the bundled data files
are intact, and anything wrong with your working folder. It is the first thing to run when
something behaves strangely.

## Setting up a folder

TVTT keeps your work separate from its own code. Make a folder anywhere you like — it does
not have to be inside the repository — and set it up:

```bash
mkdir my-voynich-work
cd my-voynich-work
tvtt init
```

That creates:

```
config.json                 what to run
plugins.json                which features to run
mappings/identity_zl.json   a starter mapping
```

The starter mapping maps every glyph to itself. It is not a hypothesis about anything; it
is the manuscript unchanged, so you have a baseline to change *from*.

If you would rather see every available option straight away, `tvtt init --advanced` also
writes `advanced_config.json` and `advanced_plugins.json`. Most people should not. See
[Settings](configuration.md).

## Your first run

```bash
tvtt run
```

About a second later:

```
transcription : Zandbergen-Landini (ZL) (Eva-)
selection     : whole manuscript
mapping       : identity_zl
text          : 5374 lines, 39015 words, 8357 word types, 194635 output characters
output        : output/run-001
```

Reading that line by line:

- **transcription** — which record of the manuscript was read. ZL is the default and the
  most complete. There are eight others; see [The transcriptions](transcriptions.md).
- **selection** — which part of the book. The whole thing, here.
- **mapping** — your rules.
- **text** — how much text came out. "Word types" means distinct words: 39,015 words drawn
  from a vocabulary of 8,357.
- **output** — where the results went.

## What you got

```
output/run-001/
  info.txt          what this run was, in plain words
  output.txt        your transliteration, one manuscript line per line
  report.html       the readable version, in your browser
  legend.txt        every glyph and what your mapping does with it
  legend.html       the same, with the Voynich shapes drawn
  frequency.txt     the commonest glyphs, characters and words
  roundtrip.txt     whether your mapping is reversible
  conflicts.txt     which rule wins wherever two overlap
  entropy.txt       how predictable the text is
  ...
  manifest.json     everything needed to reproduce this run
```

One more file is written outside the run folder: `results.json`, in your working folder,
which gains one row per run so you can compare attempts later with `tvtt results`.

**Start with `report.html`.** It opens in any browser and gives you the manuscript line by
line: the original on one side in real Voynich shapes, your transliteration on the other,
with a search box, a filter by section, and the Beinecke Library's photograph of each page.

**Then `legend.html`.** This is the file you keep open while you work. Every glyph in the
manuscript, how often it appears, what your mapping does with it, and — importantly — which
glyphs you have not written a rule for yet.

`info.txt` says in plain words what the run was, in case you come back to it in six months:

```
This folder holds the results of one TVTT run.

when            2026-08-28 14:22:07
transcription   zl (ZL3b-n.txt)
mapping         my_idea
part of the MS  sections=herbal_a
random seed     20260828
TVTT version    2.0.0
```

More on all of these in [Reading the output](output.md).

## Making a change

Open `mappings/identity_zl.json`. It is a long list of rules, one per glyph, each currently
mapping a glyph to itself. Change what `y` and `k` become, and add a rule for the pair `cth`:

```json
"y": "s",
"k": "c",
"cth": "th"
```

`cth` is not in the file to begin with. Adding it is how you say "treat these three EVA
characters as one glyph" — the longest group always wins, so `cth` is matched before the `c`
rule gets a chance.

Save it and run again:

```bash
tvtt run
```

This goes into `output/run-002`. Nothing is overwritten — `run-001` is still there, and
comparing two attempts is most of how this work actually goes.

Open the new `report.html` and the two columns now differ. The first line of f1r reads:

```
fachss scal ar ataiin shol shors thres s cor sholds
```

That is the loop. Edit, run, look, and repeat until you have something worth testing
properly.

## A sensible next step

Not the whole book at once. The manuscript's sections differ enough that a mapping which
looks promising across all of it is usually just averaging over its own failures.

```bash
tvtt mapping init my_idea       # your own mapping, every glyph listed
tvtt mapping use my_idea        # point config.json at it
tvtt run --section herbal_a     # 95 folios, one Currier language, one subject
```

Herbal A is a good place to start: it is large enough to measure, linguistically uniform,
and its illustrations at least tell you what the pages are supposed to be about.

Once you have two mappings, you can compare them directly:

```bash
tvtt mapping diff identity_zl my_idea
tvtt results                        # every run so far, with its numbers
```

From here:

- [Writing a mapping](mappings.md) — the rules in full
- [Choosing what to work on](selections.md) — the other ways to slice the book
- [Checking a mapping honestly](validation.md) — before you believe anything you find
- [Troubleshooting and FAQ](troubleshooting.md) — when something does not behave
