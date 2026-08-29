# Checking a mapping honestly

[Back to the README](../README.md)

This part of the tool exists because of one uncomfortable fact.

Take a Latin dictionary of thirty thousand words and assign letters to Voynich glyphs at
random. You will match a good fraction of the text — the manuscript's word lengths make
accidental Latin words easy to come by. Do it two hundred times and one attempt will look, to
the eye, like a discovery.

So finding real words proves little on its own. The question is always whether you found
*more* of them than an arbitrary mapping would have.

Concretely: the starter mapping, which is not a hypothesis about anything, matches about
**27%** of the Herbal A pages against a Latin dictionary. That looks like a promising start
until you notice that not one of its commonest words is a common Latin word.

## Contents

- [Running the checks](#running-the-checks)
- [random_controls](#random_controls)
- [match_significance](#match_significance)
- [shuffles](#shuffles)
- [synthetic](#synthetic)
- [language_controls](#language_controls)
- [holdout](#holdout)
- [overfitting](#overfitting)
- [Matching against a real language](#matching-against-a-real-language)
- [What a good result looks like](#what-a-good-result-looks-like)

## Running the checks

```bash
tvtt plugins preset evaluate
tvtt run
```

Seven checks, one to three minutes. Each can also be run on its own with
`tvtt run --plugin <name>`.

| Check | The question it answers |
|---|---|
| `random_controls` | Does your mapping beat mappings that mean nothing? |
| `match_significance` | How many dictionary hits would chance have produced? |
| `shuffles` | Which of your statistics actually detect structure? |
| `synthetic` | Can your statistics tell the manuscript from meaningless imitation? |
| `language_controls` | What do these numbers look like for real languages? |
| `holdout` | Does the result survive on text you did not tune it on? |
| `overfitting` | Are your extra rules earning their keep? |

## random_controls

Scores hundreds of randomly generated mappings exactly the way it scores yours, and shows
where yours falls in that distribution, with a histogram.

**Watch the "best random mapping" line, not the average.** A score comfortably above the mean
means nothing if one lucky random mapping out of five hundred matched just as much — because
you are also one attempt, and you had the advantage of choosing.

```bash
tvtt run --set plugins.random_controls.runs=500
```

More runs give a better-resolved tail and take proportionally longer.

## match_significance

The same idea aimed specifically at dictionary coverage. It reports how many hits random
mappings achieve against the same dictionary, so a raw hit rate can be read as "how much
better than nothing".

This is the check that reframes "I matched 30% of the words" into a number that means
something.

## shuffles

Destroys one kind of structure at a time — shuffling characters within words, words within
lines, lines within the text — and re-runs your statistics on the wreckage.

The logic: if a measure barely moves when you destroy the very thing it supposedly detects,
it was never detecting it.

Two results worth knowing before you rely on either measure:

- **Zipf's law survives almost every shuffle.** A good Zipf fit is close to meaningless as
  evidence.
- **Conditional entropy collapses the moment you anagram the words.** That is why h2 is the
  measure which genuinely separates Voynichese from noise.

## synthetic

Generates fake Voynichese using Torsten Timm and Andreas Schinner's self-citation model,
where every new word is an earlier word copied and slightly changed. There is no grammar in
it, no vocabulary, and no message.

It is unsettling how much of the manuscript's behaviour falls out of copy-and-modify alone:
the word-length distribution, the Zipf fit, the low entropy, the repetition, much of the
apparent structure.

**Anything your mapping "passes" that this text also passes is not evidence of language.**
Use it as the bar to clear.

## language_controls

Runs identical statistics on real texts — Latin, Italian, English, Middle English, Middle
High German, Czech, Occitan, Hebrew, Arabic — so you have something to compare against
without going and finding a corpus yourself.

These are samples of a couple of hundred kilobytes each, not corpora. They tell you whether
a number is in the right neighbourhood. They are not big enough to distinguish reliably
between two languages. See [Bundled reference data](data.md).

## holdout

The standard defence against fooling yourself in every other empirical field, and almost
never applied to Voynich work.

Tell it which section you developed your mapping on. It scores that section and several
others separately.

A mapping that has found something real generalises: it scores about the same everywhere. A
mapping that was tuned until it looked good on Herbal A scores well on Herbal A and falls
apart elsewhere — and that gap is the most honest single number the tool produces.

## overfitting

Scores your mapping, then scores the same mapping stripped back to plain rules with the
positional ones removed, and reports the difference.

Every positional rule is a dial you can turn. Turn enough of them and you can make any text
look like anything. If forty positional rules improve the score by a fraction of a percent,
they are decoration, and the mapping would be more convincing without them.

## Matching against a real language

```bash
tvtt plugins enable corpus_match
tvtt run --set reference.language=latin
```

This compares every output word against a real vocabulary, and reports four numbers rather
than one, because the plain hit rate is the least useful of them:

| Number | What it says |
|---|---|
| coverage | the share of words that matched something |
| weighted coverage | the same, but a rare word counts for more than *et* |
| confidence-weighted | each match discounted by how loosely it was found |
| **stopword alignment** | are your commonest words the language's commonest words? |

**Stopword alignment is the one that matters.** A real reading puts the language's function
words at the top of the frequency list, because function words are common in everything. A
mapping tuned to maximise dictionary hits almost never manages this: it collects a long tail
of rare words while its own commonest words match nothing at all.

Matches are found by several routes, each carrying its own confidence: exact, stemmed,
medieval abbreviation, consonant skeleton, merged, split, phonetic, fuzzy. The permissive
ones are off or discounted by default for good reason.

A useful exercise: turn the permissive routes on one at a time and watch what happens. **If
loosening the matching raises coverage but not alignment, the extra hits are noise.**

## What a good result looks like

There is no threshold that means "solved". But a result worth taking seriously tends to show:

- coverage clearly above what the random controls achieved, including their best case
- **stopword alignment above chance** — the hardest one, and the one solvers fail
- the same scores on sections you did not develop against
- no collapse when ambiguous lines are dropped
- entropy still near the manuscript's value, not near the target language's
- fewer positional rules than you were tempted to write

And a result that fails all of these is still worth publishing, because the space of ideas
that do not work is large and mostly unmapped. Runs that include these checks are far more
interesting than runs that do not.
