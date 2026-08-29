# Reproducing a result

[Back to the README](../README.md)

## Contents

- [The manifest](#the-manifest)
- [Seeds](#seeds)
- [Why this matters](#why-this-matters)
- [Speed](#speed)
- [Caching](#caching)
- [The network](#the-network)

## The manifest

Every run writes `manifest.json`, recording:

- the TVTT version
- the full configuration, and a hash of it
- the SHA-256 of the transcription file actually used
- a hash of the mapping
- the selection
- the random seed
- which features ran, and how long each took
- every file produced
- every warning raised

No absolute paths go into it, so it is safe to share as it stands.

## Seeds

Everything random draws from a single seed set in your config: the control mappings, the
shuffles, the synthetic generator, the solver's starting points.

```json
"seed": 20260828
```

Two runs with the same seed produce identical output, byte for byte. The test suite checks
this rather than assuming it.

If you want to know whether a result is stable or an accident of one particular seed, change
it and run again. A finding that moves when the seed moves is not a finding.

## Why this matters

"23% Latin coverage" is an anecdote. Somebody reading it cannot check it, cannot reproduce
it, and cannot tell whether it is good.

```
23% Latin coverage
ZL3b-n.txt  sha256 bf5b6d4a...
mapping     sha256 91c2...
seed        20260828
TVTT        2.0.0
```

That is a claim. Anyone can run it and get the same number, and if a corrected transcription
later moves it, the checksum says exactly why.

This is the whole reason the manifest exists, and why `tvtt mapping gallery` asks for
`results.json` alongside the mapping when you submit one.

## Speed

On the full manuscript — 5,374 lines, 39,015 words, 8,357 distinct words — on an ordinary
laptop:

| Operation | Time |
|---|---|
| Read a transcription | about 50 ms |
| Apply a mapping to every word | about 65 ms, or 5 ms from cache |
| A normal run, ten features, whole book | **about 1 second** |
| All the statistics with every honesty check | 1 to 3 minutes |
| Dictionary matching, whole vocabulary | about 1.5 seconds |
| The solver | roughly 1,200 candidate mappings a second |

The mapping engine is why the rest is quick. Applying a mapping the obvious way means a
function call per character. Instead, each distinct word is broken up once into a list of
small integers that already encode whether each glyph starts a word, ends one, and which
occurrence of that glyph it is. After that, applying a mapping is a table lookup.

Changing one rule re-does only the words containing that glyph, which is what makes the
solver and the live browser editor practical.

If a run is slow, it is almost always the enabled features rather than the engine:

```bash
tvtt plugins list --enabled
```

The baselines and the solver are the slow ones, and they are marked as such.

## Caching

Parsed transcriptions, language models and control statistics are cached in `.tvtt_cache/`,
keyed by a hash of their inputs. A cached entry is only reused when its inputs hash the
same, so it cannot go stale.

```bash
tvtt cache            # what is in it, and how big
tvtt cache clear      # delete it
tvtt run --no-cache   # ignore it for one run
```

It is always safe to delete. The only cost is that the next run is slower.

## The network

**TVTT does not use the internet unless you ask it to.** Everything needed to run — the nine
transcriptions, eleven dictionaries, eleven control texts, the page metadata, the fonts — is
bundled. A fresh install works on a machine that has never been online.

Two things can reach the network, and both are explicit:

- **`tvtt fetch`** downloads transcriptions from voynich.nu. You run it deliberately.
- **The `translate` feature** sends your output text to Google Translate. It is off by
  default *and* blocked by offline mode, so enabling it takes two deliberate steps.

The web report links to page images from Yale's IIIF service. Those load in your browser when
you open the report, not during the run, and you can switch them off.

To be certain nothing reaches out:

```json
"network": { "offline": true }
```

**A word about translation.** Machine translators are extremely good at producing confident
nonsense from gibberish. Give one a string of Latin-looking letters and it will hand back a
fluent English sentence every time, whether or not there was anything there to translate.
Treat it as a curiosity, never as evidence.
