# Coming from version 1

[Back to the README](../README.md)

Version 2 is a rewrite. The old `main.py`, `cleaner.py` and `mapping.py` scripts are gone,
replaced by a single `tvtt` command.

**Your old files still work.** That was a requirement, not an afterthought.

## What still works

**Version 1 config files.** A version 1 `config.json` is detected and translated
automatically. You do not have to do anything.

**Version 1 mappings, both styles.**

The plain text lists used before 1.8:

```
0=f~f
53=9~con
105=4o~d@
7=y~s/
```

and the flat JSON style with markers inside the string:

```json
{ "f": "a", "4o": "d@", "y": "s/" }
```

Put either in `mappings/` and use it exactly as you would a new one:

```bash
tvtt mapping use my_old_mapping
```

The markers mean what they always did — `@` start of word, `/` end of word, `'` `"` `:` `;`
for the first four occurrences within a word. Full details in [Writing a
mapping](mappings.md#mappings-from-version-1).

Nothing is converted on disk. TVTT writes JSON when it saves, so if you edit an old mapping
in `tvtt web` and save it, you get a new `.json` file and your original is left untouched.

## What changed

**`"transliteration": "eva"` is now `"transcription": "zl"`.** The old name still works.

**There is no separate cleaning step.** Version 1 stripped the transcription files down to
bare letters before doing anything. Version 2 reads the IVTFF files directly and keeps the
structure, which is what makes sections, scribes, labels, locus types and the handling of
uncertain readings possible at all.

**Words are separated by spaces, not underscores.** Set `output.wordSeparator` to `"_"` in
`advanced_config.json` for the old look.

**Sections are chosen by name, not by line number.** The old `startLine` and `endLine` still
work, but `--section herbal_a` is both easier and more correct: Currier A and B are not
contiguous, so no single cutoff line can express the split.

**Every measurement is now a feature you switch on.** Version 1 computed everything every
time. Version 2 runs ten by default and has 36 available. See [Optional
features](plugins.md).

**Each run gets its own output folder.** `output/run-001`, `run-002`, and so on. Nothing is
overwritten, and deleting a folder does not make the next run reuse its number. Set
`keepEveryRun` to `false` for the old overwrite-in-place behaviour.

**The bundled font changed.** Version 1 shipped Glen Claston's v101 font and used it for
everything, including EVA text — which drew real Voynich shapes that were the wrong ones,
and drew `@nnn;` codes as five unrelated glyphs. Version 2 picks a font to match the
alphabet, and has no fallback. See [Reading the output](output.md#the-voynich-fonts).

## What is new

Worth knowing about if you are coming back to the tool:

- **Nine transcriptions** instead of one, with checksums and an alignment view
- **Named sections, Currier languages, scribes, quires, labels-versus-running-text**
- **Uncertainty handling** — the transcribers' doubts are preserved and configurable
- **The honesty checks** — random controls, shuffles, a null model, held-out validation.
  This is the part that changes how you read your own results; see [Checking a mapping
  honestly](validation.md)
- **An automatic solver** — hill climbing, annealing, genetic search
- **A browser editor** — `tvtt web`, with live preview
- **Run manifests** — every result reproducible from its recorded inputs
- **No required dependencies** — it runs on a clean Python install

## Getting started again

```bash
pip install -e .
mkdir my-work && cd my-work
tvtt init
cp /wherever/my_old_mapping.txt mappings/
tvtt mapping use my_old_mapping
tvtt run
```

Then read [Getting started](getting-started.md) for what the output files are, and
[Choosing what to work on](selections.md) for the filters that did not exist before.
