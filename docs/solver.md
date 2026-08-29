# Automatic search

[Back to the README](../README.md)

If you would rather not guess, TVTT can search for a mapping itself, using the same machinery
that breaks ordinary substitution ciphers.

```bash
tvtt solve --method anneal --language latin
```

Read the warning at the bottom of this page before you believe anything it produces.

## Contents

- [Methods](#methods)
- [Fitness functions](#fitness-functions)
- [Constraining the search](#constraining-the-search)
- [Parameter sweeps](#parameter-sweeps)
- [Why a solver always succeeds](#why-a-solver-always-succeeds)

## Methods

```bash
tvtt solve --method hillclimb --restarts 20
tvtt solve --method anneal --iterations 200000
tvtt solve --method genetic
```

| Method | How it works |
|---|---|
| `hillclimb` | change one assignment, keep it if the score improves; restart from scratch repeatedly |
| `anneal` | the same, but accept some worsening moves early on, so it can escape a local peak |
| `genetic` | breed a population of mappings, crossing and mutating the best |

Hill climbing with many restarts is fast and usually enough. Annealing does better on a
rugged landscape. The genetic algorithm is the slow one, and the only part of TVTT that is
deliberately expensive.

## Fitness functions

```bash
tvtt solve --fitness quadgram --language latin
```

| Fitness | What it maximises |
|---|---|
| `quadgram` | how likely the output's four-character sequences are in the target language |
| `trigram`, `bigram` | the same at shorter range; faster, blunter |
| `dictionary` | how many output words are real words |
| `entropy` | how close the output's entropy is to the target language's |
| `blend` | a weighted combination |

`quadgram` is the standard choice for cipher-breaking and the default worth starting with.
`dictionary` sounds more direct but is much easier to overfit, since it rewards any mapping
that manufactures short common words.

## Constraining the search

Constraining is usually worth more than running longer, and it keeps the result recognisably
your idea rather than whatever the optimiser happened to like.

```bash
tvtt solve --lock o=a --lock 9=s    # fix the glyphs you are confident about
tvtt solve --swap-only              # only trade letters between glyphs
tvtt solve --injective              # force every glyph to a different letter
tvtt solve --save-as my_result      # keep the winner as a mapping
```

`--swap-only` starts from your current mapping and only exchanges letters between glyphs,
which preserves the letter frequencies you already chose. `--injective` forbids two glyphs
sharing a letter, which stops the solver from buying dictionary hits by merging glyphs
together — see [roundtrip](plugins.md#checking-the-mapping).

## Parameter sweeps

```bash
tvtt run --plugin sweep
```

Runs the solver once per combination in a parameter grid and ranks the results in a
leaderboard. Useful for finding out whether a result is stable across settings or an artefact
of one particular configuration.

It is the slowest thing in the tool. Configure the grid with
`tvtt plugins info sweep`.

## Why a solver always succeeds

A solver always returns something. Given a free choice of letters, it finds whatever makes
any text score as well as that text can score — message or no message. Run it against
shuffled Voynichese and it will hand you a mapping just as confidently.

**What comes out is a hypothesis, not a finding.** Before believing it:

```bash
tvtt run --plugin random_controls --plugin holdout --plugin corpus_match
```

The third is the one solvers fail most often, and the failure is instructive. Optimising
letter sequences produces text with realistic-looking *spelling* and no realistic
*vocabulary*: it reads like the target language at a glance, and its commonest words are
nothing like the target language's commonest words. The stopword alignment figure shows this
immediately.

See [Checking a mapping honestly](validation.md).
