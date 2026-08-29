# Troubleshooting and FAQ

[Back to the README](../README.md)

When anything behaves unexpectedly, start here:

```bash
tvtt doctor
```

It checks your Python version, your optional packages, your working folder, whether your
mapping file exists, whether your selection matches anything, and whether the bundled data
files match their checksums.

## Contents

- [Common problems](#common-problems)
- [Questions people ask](#questions-people-ask)

## Common problems

**`tvtt: command not found`.** Python installed the command somewhere that is not on your
path. Use `python -m tvtt` instead — it is identical in every way.

**"The report looks unchanged."** Check you are opening the newest run. `tvtt runs` lists
them and `output/latest.txt` names the most recent. If you are on the right file, your
browser has cached it: hard-refresh with `Ctrl+F5`, or `Cmd+Shift+R` on a Mac.

**"Nothing matched my selection."** Usually two filters that cannot both be true, such as
asking for running text in a section that is almost entirely labels. `tvtt doctor` says which
combination emptied it.

**"A feature was skipped."** It needed an optional package, or offline mode blocked it. The
warning names which, and the rest of the run carries on normally.

**"My mapping file will not load."** The error names the line and column. It is nearly always
a missing comma, or a stray one after the last entry — though TVTT forgives the trailing
comma that version 1 used to write.

**"My old `.txt` mapping is not recognised."** The format is `number=glyph~letters`, one per
line. If a line is malformed the error names its line number. See [Mappings from version
1](mappings.md#mappings-from-version-1).

**"Everything is slow."** See what is switched on with `tvtt plugins list --enabled`. The
baselines and the solver are the slow ones and are marked as such. A normal run of the
default features takes about a second on the whole manuscript.

**"It used 3 GB of memory."** That should not happen. If it does, please open an issue with
your mapping file attached — that is a bug, not a configuration problem.

**"The numbers changed after I updated."** Run `tvtt verify`. If a transcription was
corrected upstream, your results will move. Each run's manifest records exactly which bytes
that run used, so you can always tell which version produced a given number.

**"The Voynich text shows as empty boxes."** Eleven rare extended EVA glyphs are not in the
bundled font. Everything else should render. If nothing at all renders, your browser may be
blocking the embedded font; try a different browser.

**"A setting I passed did nothing."** It should not be possible any more — a misspelt setting
or feature name is refused with a suggestion. Remember that a feature's own settings need the
`plugins.` prefix: `--set plugins.entropy.includeSpaces=true`, not `--set entropy.includeSpaces=true`.

## Questions people ask

**Do I need to know how to program?** No. You edit two small settings files and one mapping
file, all plain text, and type `tvtt run`. `tvtt plugins info <name>` explains every feature
in ordinary English.

**Can I map several glyphs to one letter?** Yes — `"ch": "k"`. The longest group always
matches first.

**Can one glyph become several letters?** Yes — `"9": "con"`.

**What are Currier A and B?** Two statistically distinct "languages" running through the
manuscript, identified by Prescott Currier in the 1970s. They differ in vocabulary, word
length and glyph frequency enough that a mapping suiting one often fails the other. See
[Choosing what to work on](selections.md).

**Which transcription should I use?** `zl` unless you have a reason not to. It is the most
complete and the best maintained. Use `v101` if your hypothesis depends on distinctions that
EVA deliberately collapses.

**Why does the tool keep telling me my result is not significant?** Because for most mappings
it is not, and saying so is the most useful thing a tool like this can do. If it were easy,
somebody would have managed it in the last hundred years.

**Is my mapping wrong if the entropy does not change?** No — the opposite. Swapping letters
around cannot change entropy much. If yours does change a lot, something is expanding glyphs
and adding information the manuscript never had. See [Measuring the
text](analysis.md#entropy).

**My mapping matched 30% of the words against Latin. Is that good?** Not on its own. A random
mapping does about 27% on Herbal A. Run `tvtt run --plugin random_controls --plugin
match_significance` to find out what your number is worth. See [Checking a mapping
honestly](validation.md).

**Can I use my own dictionary?** Yes. Put a `.txt` file in `reference_texts/` named after the
language and it is picked up automatically.

**Where can I find transliteration charts?** [voynich.nu](https://www.voynich.nu/transcr.html)
has excellent ones, and is the source of all nine bundled files.

**Can I see the actual page?** Yes. The web report shows each folio's photograph beside its
transliteration, with links to Yale's Beinecke library, voynichese.com and voynich.nu.

**Does it phone home?** No. Nothing reaches the network unless you run `tvtt fetch` or
deliberately enable the translation feature. See [The
network](reproducibility.md#the-network).

**How do I report a bug or ask for a feature?** Open an issue on
[GitHub](https://github.com/Krymorn/The-Voynich-Transliteration-Tool/issues). Attaching the
`manifest.json` from the run makes it much easier to reproduce.
