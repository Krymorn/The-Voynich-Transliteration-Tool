# The Voynich Transliteration Tool

**Version 2.0.0** · Python 3.9 or newer · no required dependencies · MIT

Make your own transliteration of the Voynich Manuscript.

You decide what each Voynich glyph stands for. TVTT applies that to a real transcription of
the manuscript and hands the text back to you, page by page. When you want to know whether
your idea holds up, the same tool will measure it.

```
fachys.ykal.ar.ataiin.shol.shory.cthres.y.kor.sholdy    the first line of f1r
fachss scal ar ataiin shol shors thres s cor sholds     one guess at reading it
```

That reads `y` as *s*, `k` as *c* and `cth` as *th*, and leaves the rest alone. It is not a
good guess. Making better ones is the point.

---

## Install

```bash
git clone https://github.com/Krymorn/The-Voynich-Transliteration-Tool.git
cd The-Voynich-Transliteration-Tool
pip install -e .
```

That gives you a `tvtt` command. If your system does not put it on the path, use
`python -m tvtt` instead — the two are identical. Nothing else is required: the
transcriptions, dictionaries and fonts are all bundled, so it works with no internet.

Optional extras add charts and a few conveniences. `pip install -e ".[all]"` gets them, and
`tvtt doctor` reports what you have.

## Try it

```bash
mkdir my-voynich-work
cd my-voynich-work
tvtt init
tvtt run
```

`tvtt run` takes about a second and tells you where it put things:

```
transcription : Zandbergen-Landini (ZL) (Eva-)
selection     : whole manuscript
mapping       : identity_zl
text          : 5374 lines, 39015 words, 8357 word types, 194635 output characters
output        : output/run-001
```

Open `output/run-001/report.html` and you get the manuscript line by line, with a search
box, a section filter and the page images.

The two columns match, because `tvtt init` gives you a starter mapping that leaves every
glyph alone — the manuscript before you have changed anything. So change something. Open
`mappings/identity_zl.json`, change what `y` and `k` become, and add a rule for the pair
`cth`:

```json
"y": "s",
"k": "c",
"cth": "th"
```

Run `tvtt run` again and the first line of f1r is the guess at the top of this page. It
writes `output/run-002`, and `run-001` is still there to compare against.

That is the whole loop: edit, run, look.

The [getting started guide](docs/getting-started.md) covers the same ground more slowly and
explains each file you end up with.

---

## Writing a mapping

A mapping is a small JSON file. The glyph is on the left, what it becomes is on the right:

```json
{
  "meta": { "name": "my_idea", "language": "latin" },
  "rules": {
    "o": "o",
    "y": "s",
    "ch": "th",
    "9": { "plain": "n", "final": "s" }
  }
}
```

`tvtt mapping init my_idea` writes one out with every glyph in the manuscript already
listed, so you never have to hunt for them. There are four kinds of rule:

| Rule | Example | What it does |
|---|---|---|
| one glyph, one letter | `"o": "a"` | the ordinary case |
| one glyph, several letters | `"9": "con"` | for a glyph read as a scribal abbreviation |
| several glyphs, one letter | `"ch": "k"` | `ch` is taken as a single unit; the longest group wins |
| different letters in different places | `"9": {"plain": "n", "final": "s"}` | for a glyph that behaves differently at the start or end of a word |

That last kind matters more than you might expect. Voynichese glyphs are fussy about
position: in EVA, `q` nearly always starts a word and `n` nearly always ends one.

Mapping files from TVTT 1.x still work. Put the old `.txt` list in `mappings/` and point at
it as normal. Rule precedence, the version 1 format and mapping versioning are all in the
[mapping guide](docs/mappings.md).

While you edit, keep the glyph list open:

```bash
tvtt run --plugin legend
```

That writes a cheat sheet of every glyph, how often it appears, what your mapping does with
it, and which glyphs you have not covered yet. Or edit in a browser, with the text updating
as you type:

```bash
tvtt web
```

## Working on one part of the book

The manuscript is not uniform. In the 1970s Prescott Currier showed that two statistically
distinct "languages", A and B, run through it, and the sections differ in vocabulary and
word length too. A mapping that suits the herbal pages may fall apart on the bathing-nymph
quire, and working on the whole book at once hides that.

```bash
tvtt run --section herbal_a      # the Herbal A pages
tvtt run --currier B             # everything in Currier language B
tvtt run --scribe 2              # one scribe's hand
tvtt run --text-class labels     # labels only, no running text
tvtt run --folio 1r-10v          # a range of folios
```

These combine, and all of them can go in `config.json` instead of being typed each time.
`tvtt sections` lists the twelve named sections with their sizes. See [choosing what to
work on](docs/selections.md).

## Checking whether it means anything

Here is the uncomfortable fact this tool is built around.

Take a Latin dictionary of thirty thousand words and assign letters to Voynich glyphs at
random. You will match a good fraction of the text — the manuscript's word lengths make
accidental Latin words easy to come by. Do it two hundred times and one attempt will look,
to the eye, like a discovery.

So finding real words proves little on its own. The question is whether you found *more* of
them than an arbitrary mapping would have, and TVTT can answer it:

```bash
tvtt plugins preset evaluate
tvtt run
```

That scores your mapping against hundreds of random ones, against shuffled text, against
meaningless text generated to imitate Voynichese, and against sections you did not tune it
on. [Checking a mapping honestly](docs/validation.md) explains what each test is for and
how to read the result.

---

## Documentation

**Using the tool**

- [Getting started](docs/getting-started.md) — install, the first run, and the files you get
- [Writing a mapping](docs/mappings.md) — every kind of rule, precedence, versions, the version 1 format
- [Choosing what to work on](docs/selections.md) — sections, Currier languages, scribes, labels, folio ranges
- [Reading the output](docs/output.md) — run folders, the web report, the Voynich fonts
- [Settings](docs/configuration.md) — `config.json`, `plugins.json` and the advanced files
- [Commands](docs/commands.md) — the full command line reference

**Going further**

- [Optional features](docs/plugins.md) — all 36, and what each one is for
- [Measuring the text](docs/analysis.md) — entropy, word length, slot grammar, and what the numbers mean
- [Checking a mapping honestly](docs/validation.md) — controls, shuffles, null models, held-out text
- [Automatic search](docs/solver.md) — hill climbing, annealing and genetic search
- [The transcriptions](docs/transcriptions.md) — the nine bundled files, and how they record doubt
- [Bundled reference data](docs/data.md) — dictionaries, control texts, and where they came from

**Reference**

- [Reproducing a result](docs/reproducibility.md) — manifests, seeds, caching, speed, offline use
- [Writing your own feature](docs/extending.md) — the plugin API and the project layout
- [Troubleshooting and FAQ](docs/troubleshooting.md)
- [Coming from version 1](docs/migrating-from-v1.md)

## Commands at a glance

```
tvtt init            set up a folder to work in
tvtt run             transliterate and run whatever features are on
tvtt mapping ...     create, inspect, compare, version and share mappings
tvtt plugins ...     see and change which features run
tvtt web             edit a mapping in your browser
tvtt sections        the parts of the manuscript, with folio counts
tvtt runs            list past runs
tvtt results         compare every run you have done
tvtt doctor          check your folder and report anything wrong
```

When something looks wrong, `tvtt doctor` is the place to start. The full list is in
[Commands](docs/commands.md).

---

## Sharing your work

```bash
tvtt mapping export-pack my_idea --out my_idea.tvttpack.json --author "your name"
```

To submit one to the community gallery, send that file — with the `results.json` from your
run, so the numbers can be checked — to **cmarbel** in a private message on
[voynich.ninja](https://www.voynich.ninja/). Runs that include the honesty checks are far
more interesting than runs that do not.

## Credits

The transcriptions, the page metadata and the format specification are other people's work,
freely published for research. TVTT would not exist without them.

**René Zandbergen** and **Gabriel Landini** for the ZL transliteration, the IVTFF format and
the reference material at [voynich.nu](https://www.voynich.nu/), the source of all nine
bundled transcriptions. **Glen Claston** for the v101 transliteration and alphabet.
**Takeshi Takahashi** and **Jorge Stolfi** for the interlinear file and the
crust-mantle-core word model. **Prescott Currier** and **Mary D'Imperio** for the Currier
transliteration and the A/B distinction. **The Friedman First Study Group** for FSG. **Lisa
Fagin Davis** for the five-scribe attribution. **Torsten Timm** and **Andreas Schinner** for
the self-citation model used as a null hypothesis. **Boris Sukhotin** for the
vowel-detection algorithm. **Rebecca Bettencourt (Kreative Software)** for the Voynich
Unicode fonts. **The Beinecke Rare Book and Manuscript Library, Yale University** for MS 408
and for publishing the page images openly. **Project Gutenberg**, **Sefaria** and
**alquran.cloud** for the public-domain texts behind the bundled dictionaries.

To cite the tool itself, see `CITATION.cff`.

## Licence

MIT — see `LICENSE`.

The bundled transliterations remain the work of their authors. The bundled reference texts
are public domain. The two bundled fonts are under the SIL Open Font Licence, whose text is
in `tvtt/data/fonts/OFL.txt`. The manuscript page images are published openly by the
Beinecke Library; TVTT stores only their web addresses, never the images themselves.
