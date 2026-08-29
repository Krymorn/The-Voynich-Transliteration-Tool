# Reading the output

[Back to the README](../README.md)

## Contents

- [Run folders](#run-folders)
- [info.txt](#infotxt)
- [The files you get](#the-files-you-get)
- [The web report](#the-web-report)
- [The Voynich fonts](#the-voynich-fonts)
- [Machine-readable results](#machine-readable-results)

## Run folders

Every run gets its own numbered folder, and nothing is ever overwritten:

```
output/
  run-001/
  run-002/
  run-003/
  latest.txt
```

Comparing two attempts is how this work goes, and losing the previous one each time is how
it gets frustrating.

Deleting a folder does not make the next run reuse its number, so `run-004` always means the
fourth run you did, even if you cleared out the first three.

```bash
tvtt runs                # list past runs with their settings
tvtt runs --prune 10     # keep only the newest ten
```

`latest.txt` always names the newest run, which is useful in scripts and when you have lost
track.

If you would rather have a single folder that gets overwritten each time, set `keepEveryRun`
to `false` in `config.json` (it is `output.separateRunFolders` in the advanced file).

## info.txt

Each folder starts with `info.txt`, which says in plain words what that run was. It exists
because a folder called `run-017` tells you nothing six months later.

```
This folder holds the results of one TVTT run.

when            2026-08-28 14:22:07
transcription   zl (ZL3b-n.txt)
mapping         my_idea
part of the MS  sections=herbal_a
random seed     20260828
TVTT version    2.0.0
```

Below that: the headline numbers, every file with a one-line description of what it is, and
any warnings the run raised.

## The files you get

Which files appear depends on which features are switched on. With the ten that are on out
of the box:

| File | What it is |
|---|---|
| `output.txt` | your transliteration, one manuscript line per line |
| `report.html` | the readable version: source and output side by side, searchable, with page images |
| `legend.txt`, `legend.html` | every glyph and what your mapping does with it |
| `frequency.txt` | which glyphs, characters and words are commonest |
| `entropy.txt` | how predictable the text is, with published reference values |
| `word_length.txt` | the word length distribution |
| `vocabulary.txt` | type/token ratio, hapax legomena, Heaps' law |
| `zipf.txt` | rank against frequency |
| `roundtrip.txt` | whether your mapping is reversible |
| `conflicts.txt` | which rule wins wherever two rules overlap |
| `info.txt` | what this run was, in plain words |
| `manifest.json` | everything needed to reproduce it |

Switching on more features adds more files. `tvtt plugins list` shows what is available and
[Optional features](plugins.md) explains each one.

## The web report

`report.html` is the main thing you look at. It gives you:

- the manuscript line by line, source beside transliteration
- a search box that works across both
- a filter by section, and by Currier language
- a glyph highlighter, so you can see where one glyph falls
- each folio's photograph from the Beinecke Library, beside its text
- links out to the Beinecke viewer, voynichese.com and voynich.nu
- the run's statistics, at the bottom

It is a single file. The styling, the scripts and the Voynich font are all embedded, so you
can email it to someone or keep it for ten years and it will still work. The only thing it
fetches from the network is the page images, which load in your browser when you open the
report rather than during the run. You can switch those off.

`tvtt run --plugin bundle` goes further and gathers every file the run produced into one
self-contained HTML document.

## The Voynich fonts

Where the source text is shown, TVTT draws it in real Voynich shapes rather than in the
transcription's Latin letters.

Which font it uses depends on the alphabet, and this matters more than it sounds. A
transcription alphabet is a naming scheme, not a set of shapes: EVA calls a particular shape
`k`, and v101 calls that same shape `K`. Render EVA text in a v101 font and you get genuine
Voynich shapes that are the wrong ones — which is subtly wrong in a way that is very hard to
notice.

| Alphabet | Font used |
|---|---|
| EVA (`zl`, `takahashi`, `voynichese`, `reference`, `reference_basic`) | Fairfax EVA HD |
| v101 (`v101`, `v101_native`) | Fairfax V101 HD |
| Currier, FSG | none — you see the transcriber's plain letters |

There is deliberately no fallback. If no font matches the alphabet, TVTT shows the plain
letters rather than drawing misleading shapes.

Both fonts come from Rebecca Bettencourt's Voynich Unicode package and are bundled under the
SIL Open Font Licence. They cover every v101 glyph and all but eleven of the rarer extended
EVA ones; anything uncovered falls back to showing its code.

**Glyphs written as `@nnn;`.** Some transcriptions record a rare glyph by number rather than
by letter — `@113;` and so on. These are drawn as their shape, with the code shown beside
them in ordinary monospace type. The code itself is never set in the Voynich font, because
`@`, `1`, `1`, `3` and `;` would each be drawn as an unrelated Voynich glyph.

To use a different font, point a feature's `font` setting at your own `.ttf`. It belongs to
each feature that draws Voynich text rather than to the config file, so:

```bash
tvtt run --set plugins.html_report.font=myfont.ttf
```

`html_report`, `legend` and `comparison` each have one. Setting it to a name that does not
exist is the way to see the transcription's plain letters instead of shapes.

## Machine-readable results

`manifest.json`, in the run folder, records how the run was made: the version, the full configuration and its
hash, the checksum of the transcription file actually used, the hash of the mapping, the
selection, the random seed, which features ran, how long each took, every file produced and
every warning raised. No absolute paths go into it, so it is safe to share.

`results.json`, in your working folder rather than the run folder, gains one row per run:
the mapping, the selection, the transcription checksum and the headline metrics, in a shared
format. It survives pruning old run folders, and it is what `tvtt mapping gallery` asks you
to send when you submit a mapping.

```bash
tvtt results                 # every recorded run, ranked
tvtt results --metric h2     # ranked by one metric
```

Individual features write their own machine-readable files where it makes sense —
`word_frequency.csv`, `glyph_heatmap.csv`, `solver.json`, and `corpus_match.json` if you
switch its `writeJson` setting on.

See [Reproducing a result](reproducibility.md).
