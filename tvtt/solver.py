"""Automated search for a mapping: hill climbing, annealing and evolution.

This turns the workbench into a cryptanalysis tool.  Instead of hand-writing a
mapping, you state what "good" means - a fitness function over a target
language - and let the search find the mapping that maximises it.

How it stays fast in pure Python
--------------------------------
Every distinct manuscript word is segmented once into a tuple of integers, and
a candidate mapping becomes a flat table of replacement strings.  Scoring a
candidate is then a weighted sum over word *types*, not tokens, and changing
one glyph only invalidates the types that contain it.  A single move therefore
costs a few hundred string joins instead of re-mapping 38,000 tokens, which is
what makes tens of thousands of moves practical without any native extension.

An important warning
--------------------
A solver will always return something.  Given enough freedom it will find a
mapping that scores well on any text at all, including one with no message in
it.  Treat every result as a hypothesis to be checked against the baselines in
:mod:`tvtt.baselines` - especially the random-mapping distribution and the
held-out score - before treating it as a finding.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Callable

from .langmodel import Fitness, FitnessOptions
from .logging_util import get_logger
from .mapping import LATIN_LOWER, SLOT_PLAIN, Mapping, MappingEngine

_log = get_logger("solver")

SEARCH_METHODS = ("hillclimb", "anneal", "genetic")

SEARCH_DESCRIPTIONS = {
    "hillclimb": "Repeatedly swap or change one glyph's letter and keep the change if the score improves. Restarts from a new random mapping when it gets stuck.",
    "anneal": "Like hill climbing, but sometimes accepts a worse mapping early on so it can escape local optima. Slower, usually better.",
    "genetic": "Keeps a population of mappings, breeds the best ones by crossover and mutates the children. Slowest, best at exploring very different mappings.",
}


# --------------------------------------------------------------------------
# The candidate representation
# --------------------------------------------------------------------------


class Candidate:
    """One mapping under test, held as a flat glyph -> letter table."""

    __slots__ = ("letters", "score")

    def __init__(self, letters: list, score: float = -math.inf) -> None:
        self.letters = letters
        self.score = score

    def copy(self) -> Candidate:
        return Candidate(list(self.letters), self.score)

    def as_mapping(self, glyphs: Sequence, meta: dict = None) -> Mapping:
        return Mapping(
            rules={g: {SLOT_PLAIN: self.letters[i]} for i, g in enumerate(glyphs)},
            meta=meta or {},
        )


class Problem:
    """Everything the search needs: a vocabulary, a segmentation and a fitness.

    The segmentation is done once, against the *glyph inventory only*, so it
    stays valid no matter which letters a candidate assigns.
    """

    def __init__(
        self,
        vocabulary: Counter,
        engine: MappingEngine,
        fitness: Fitness,
        alphabet: str = LATIN_LOWER,
        locked: dict = None,
    ) -> None:
        self.vocabulary = vocabulary
        self.fitness = fitness
        self.alphabet = list(alphabet)
        self.glyphs = list(engine.keys)
        self.glyph_index = {g: i for i, g in enumerate(self.glyphs)}
        self.locked = {self.glyph_index[g]: v for g, v in (locked or {}).items() if g in self.glyph_index}
        self.free = [i for i in range(len(self.glyphs)) if i not in self.locked]

        # Word plans: each type becomes a tuple of glyph indices, and we record
        # which types every glyph appears in so a change can be applied locally.
        self.types = list(vocabulary)
        self.counts = [vocabulary[w] for w in self.types]
        self.plans = []
        self.types_using: dict = {i: set() for i in range(len(self.glyphs))}
        for type_index, word in enumerate(self.types):
            plan = tuple(p // 20 for p in engine.segment(word))
            self.plans.append(plan)
            for glyph_index in set(plan):
                self.types_using[glyph_index].add(type_index)
        self.plan_bytes = [bytes(plan) for plan in self.plans] if len(self.glyphs) <= 256 else []

    def render(self, letters: Sequence, type_index: int) -> str:
        # map() over the list's own __getitem__ is measurably faster than a
        # comprehension here, and this runs millions of times in a search.
        return "".join(map(letters.__getitem__, self.plans[type_index]))

    def render_all(self, letters: Sequence) -> list:
        return [self.render(letters, i) for i in range(len(self.types))]

    # -- byte-translation fast path --------------------------------------
    def can_translate(self) -> bool:
        """Whether the whole search can run through ``bytes.translate``.

        When there are at most 256 glyphs and every candidate letter is a
        single Latin-1 character - which covers every ordinary substitution
        search - a word can be mapped by translating a byte string instead of
        joining a Python list.  That moves the innermost loop into C and is
        worth roughly a factor of three on a real run.
        """
        return len(self.glyphs) <= 256 and all(len(c) == 1 and ord(c) < 256 for c in self.alphabet)

    def make_table(self, letters: Sequence) -> bytearray:
        table = bytearray(range(256))
        for i, ch in enumerate(letters):
            table[i] = ord(ch)
        return table

    def render_bytes(self, table: bytes, type_index: int) -> str:
        return self.plan_bytes[type_index].translate(table).decode("latin-1")

    def render_all_bytes(self, table: bytes) -> list:
        translate = bytes.translate
        return [translate(plan, table).decode("latin-1") for plan in self.plan_bytes]

    def score(self, letters: Sequence) -> float:
        return self.fitness.score(self.render_all(letters))

    def random_letters(self, rng: random.Random, injective: bool = False) -> list:
        """A random starting assignment.

        ``injective`` gives every glyph a different letter, which is the right
        starting point when you believe the cipher is a straight one-for-one
        substitution.  It is only possible when there are at least as many
        letters as glyphs; EVA has more distinct glyphs than the Latin
        alphabet has letters, so the option quietly falls back to sampling
        with replacement.
        """
        if injective and len(self.alphabet) >= len(self.glyphs):
            letters = rng.sample(self.alphabet, len(self.glyphs))
        else:
            letters = [rng.choice(self.alphabet) for _ in self.glyphs]
        for index, value in self.locked.items():
            letters[index] = value
        return letters

    def frequency_seed(self, letter_frequencies: Sequence) -> list:
        """Start from the classic guess: commonest glyph -> commonest letter."""
        order = sorted(
            range(len(self.glyphs)),
            key=lambda i: -sum(self.counts[t] * self.plans[t].count(i) for t in self.types_using[i]),
        )
        letters = [self.alphabet[0]] * len(self.glyphs)
        for rank, glyph_index in enumerate(order):
            letters[glyph_index] = letter_frequencies[rank] if rank < len(letter_frequencies) else self.alphabet[0]
        for index, value in self.locked.items():
            letters[index] = value
        return letters


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


@dataclass
class SearchOptions:
    """How hard to search, and how."""

    method: str = "hillclimb"
    iterations: int = 40000
    restarts: int = 6
    population: int = 40
    generations: int = 120
    mutation_rate: float = 0.12
    start_temperature: float = 1.0
    end_temperature: float = 0.01
    leaderboard: int = 10
    seed: int = 0
    alphabet: str = LATIN_LOWER
    #: Glyphs whose letter you are confident about, and which the search will
    #: not touch: {"o": "a", "9": "s"}.
    locked: dict = field(default_factory=dict)
    #: Force every glyph to take a different letter (only possible when there
    #: are at least as many letters as glyphs).
    injective: bool = False
    #: Only swap letters between glyphs, never reassign one freely. Keeps the
    #: letter distribution fixed and stops the search collapsing onto a handful
    #: of very common letters.
    swap_only: bool = False
    max_seconds: float = 0.0


@dataclass
class SolverResult:
    """The best mapping found, plus the near-misses worth inspecting."""

    best_letters: list
    best_score: float
    leaderboard: list
    evaluations: int
    method: str
    fitness: str
    elapsed: float

    def to_dict(self, glyphs: Sequence) -> dict:
        return {
            "method": self.method,
            "fitness": self.fitness,
            "best_score": round(self.best_score, 6),
            "evaluations": self.evaluations,
            "elapsed_seconds": round(self.elapsed, 2),
            "best_mapping": {g: self.best_letters[i] for i, g in enumerate(glyphs)},
            "leaderboard": [
                {"rank": i + 1, "score": round(score, 6), "mapping": {g: letters[j] for j, g in enumerate(glyphs)}}
                for i, (score, letters) in enumerate(self.leaderboard)
            ],
        }


class Leaderboard:
    """Keeps the top N distinct candidates seen."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.entries: list = []
        self._seen: set = set()

    def offer(self, score: float, letters: Sequence) -> None:
        key = "".join(letters)
        if key in self._seen:
            return
        self._seen.add(key)
        self.entries.append((score, list(letters)))
        self.entries.sort(key=lambda pair: -pair[0])
        if len(self.entries) > self.size:
            dropped = self.entries.pop()
            self._seen.discard("".join(dropped[1]))

    def best(self):
        return self.entries[0] if self.entries else None


def solve(problem: Problem, options: SearchOptions, progress: Callable = None) -> SolverResult:
    """Run the chosen search and return the best mapping found."""
    import time

    start = time.perf_counter()
    rng = random.Random(options.seed)
    board = Leaderboard(options.leaderboard)

    if options.method == "genetic":
        best_letters, best_score, evaluations = _genetic(problem, options, rng, board, progress)
    elif options.method == "anneal":
        best_letters, best_score, evaluations = _anneal(problem, options, rng, board, progress)
    else:
        best_letters, best_score, evaluations = _hillclimb(problem, options, rng, board, progress)

    return SolverResult(
        best_letters=best_letters,
        best_score=best_score,
        leaderboard=board.entries,
        evaluations=evaluations,
        method=options.method,
        fitness=problem.fitness.describe(),
        elapsed=time.perf_counter() - start,
    )


def _neighbour(problem: Problem, letters: list, rng: random.Random, swap_only: bool = False) -> tuple:
    """Propose a single change: swap two glyphs' letters, or reassign one."""
    free = problem.free
    if not free:
        return letters, ()
    if len(free) > 1 and (swap_only or rng.random() < 0.5):
        i, j = rng.sample(free, 2)
        letters[i], letters[j] = letters[j], letters[i]
        return letters, (i, j)
    i = rng.choice(free)
    old = letters[i]
    new = rng.choice(problem.alphabet)
    while new == old and len(problem.alphabet) > 1:
        new = rng.choice(problem.alphabet)
    letters[i] = new
    return letters, (i,)


def _undo(letters: list, change: tuple, previous: list) -> None:
    for index in change:
        letters[index] = previous[index]


class _Scorer:
    """Incremental scoring: only re-score the word types a change touched.

    Keeping a running total and a per-type contribution turns each move from a
    pass over the whole vocabulary into a handful of dictionary lookups.  On
    the Herbal A section that is the difference between roughly three
    milliseconds and roughly thirty microseconds per move.
    """

    __slots__ = (
        "problem",
        "rendered",
        "parts",
        "total",
        "evaluations",
        "fast",
        "table",
        "_undo_parts",
        "_undo_rendered",
        "_undo_table",
    )

    def __init__(self, problem: Problem) -> None:
        self.problem = problem
        self.rendered: list = []
        self.parts: list = []
        self.total = 0.0
        self.evaluations = 0
        self.fast = problem.can_translate()
        self.table = bytearray(range(256))
        self._undo_parts: list = []
        self._undo_rendered: list = []
        self._undo_table: list = []

    def full(self, letters: Sequence) -> float:
        problem = self.problem
        fitness = problem.fitness
        if self.fast:
            self.table = problem.make_table(letters)
            self.rendered = problem.render_all_bytes(bytes(self.table))
        else:
            self.rendered = problem.render_all(letters)
        if fitness.incremental:
            self.parts = fitness.contributions(self.rendered)
            self.total = sum(self.parts) / fitness.normaliser
        else:
            self.parts = []
            self.total = fitness.score(self.rendered)
        self.evaluations += 1
        return self.total

    def _touched(self, change: tuple) -> set:
        using = self.problem.types_using
        touched: set = set()
        for index in change:
            touched |= using[index]
        return touched

    def _sync_table(self, letters: Sequence, change: tuple) -> bytes:
        table = self.table
        for index in change:
            table[index] = ord(letters[index])
        return bytes(table)

    def after_change(self, letters: Sequence, change: tuple) -> float:
        problem = self.problem
        fitness = problem.fitness
        self.evaluations += 1
        touched = self._touched(change)

        if self.fast:
            table = self._sync_table(letters, change)
            translate = bytes.translate
            plan_bytes = problem.plan_bytes

            def render(i, _t=table, _p=plan_bytes, _tr=translate):
                return _tr(_p[i], _t).decode("latin-1")
        else:

            def render(i, _l=letters):
                return problem.render(_l, i)

        if not fitness.incremental:
            self._undo_rendered = [(i, self.rendered[i]) for i in touched]
            for i in touched:
                self.rendered[i] = render(i)
            self.total = fitness.score(self.rendered)
            return self.total

        contribution = fitness.contribution
        counts = problem.counts
        rendered = self.rendered
        parts = self.parts
        undo_parts = []
        undo_rendered = []
        delta = 0.0
        for i in touched:
            undo_parts.append((i, parts[i]))
            undo_rendered.append((i, rendered[i]))
            word = render(i)
            rendered[i] = word
            value = contribution(word) * counts[i]
            delta += value - parts[i]
            parts[i] = value
        self._undo_parts = undo_parts
        self._undo_rendered = undo_rendered
        self.total += delta / fitness.normaliser
        return self.total

    def restore(self, letters: Sequence, change: tuple) -> None:
        """Undo the last :meth:`after_change` exactly, without re-rendering."""
        fitness = self.problem.fitness
        if self.fast:
            table = self.table
            for index in change:
                table[index] = ord(letters[index])
        if not fitness.incremental:
            for i, word in self._undo_rendered:
                self.rendered[i] = word
            self.total = fitness.score(self.rendered)
            return
        delta = 0.0
        for (i, part), (_j, word) in zip(self._undo_parts, self._undo_rendered):
            delta += part - self.parts[i]
            self.parts[i] = part
            self.rendered[i] = word
        self.total += delta / fitness.normaliser


def _hillclimb(problem: Problem, options: SearchOptions, rng, board: Leaderboard, progress):
    best_letters = None
    best_score = -math.inf
    evaluations = 0
    per_restart = max(1, options.iterations // max(1, options.restarts))
    scorer = _Scorer(problem)

    restarts = range(options.restarts)
    if progress is not None:
        restarts = progress(restarts)

    for restart in restarts:
        letters = problem.random_letters(rng, options.injective)
        current = scorer.full(letters)
        stall = 0
        for _ in range(per_restart):
            previous = list(letters)
            letters, change = _neighbour(problem, letters, rng, options.swap_only)
            if not change:
                break
            candidate = scorer.after_change(letters, change)
            if candidate > current:
                current = candidate
                stall = 0
            else:
                _undo(letters, change, previous)
                scorer.restore(letters, change)
                current = scorer.total
                stall += 1
                if stall > 400 * max(1, len(problem.free) // 20):
                    break
        board.offer(current, letters)
        if current > best_score:
            best_score, best_letters = current, list(letters)
        _log.debug("restart %d finished at %.5f (best %.5f)", restart, current, best_score)
    evaluations = scorer.evaluations
    return best_letters or problem.random_letters(rng), best_score, evaluations


def _anneal(problem: Problem, options: SearchOptions, rng, board: Leaderboard, progress):
    scorer = _Scorer(problem)
    letters = problem.random_letters(rng, options.injective)
    current = scorer.full(letters)
    best_letters, best_score = list(letters), current

    steps = max(1, options.iterations)
    t0, t1 = options.start_temperature, max(1e-6, options.end_temperature)
    iterator = range(steps)
    if progress is not None:
        iterator = progress(iterator)

    for step in iterator:
        temperature = t0 * (t1 / t0) ** (step / steps)
        previous = list(letters)
        letters, change = _neighbour(problem, letters, rng, options.swap_only)
        if not change:
            break
        candidate = scorer.after_change(letters, change)
        delta = candidate - current
        if delta >= 0 or rng.random() < math.exp(delta / temperature):
            current = candidate
            if current > best_score:
                best_score, best_letters = current, list(letters)
                board.offer(current, letters)
        else:
            _undo(letters, change, previous)
            scorer.restore(letters, change)
            current = scorer.total
    board.offer(best_score, best_letters)
    return best_letters, best_score, scorer.evaluations


def _crossover(a: Sequence, b: Sequence, rng: random.Random) -> list:
    """Uniform crossover: each glyph takes its letter from one parent."""
    return [a[i] if rng.random() < 0.5 else b[i] for i in range(len(a))]


def _genetic(problem: Problem, options: SearchOptions, rng, board: Leaderboard, progress):
    size = max(4, options.population)
    population = [problem.random_letters(rng, options.injective) for _ in range(size)]
    scored = [(problem.score(letters), letters) for letters in population]
    evaluations = size
    scored.sort(key=lambda pair: -pair[0])

    generations = range(options.generations)
    if progress is not None:
        generations = progress(generations)

    for _ in generations:
        elite = scored[: max(2, size // 5)]
        children = [list(letters) for _score, letters in elite]
        while len(children) < size:
            a = _tournament(scored, rng)
            b = _tournament(scored, rng)
            child = _crossover(a, b, rng)
            for i in problem.free:
                if rng.random() < options.mutation_rate:
                    child[i] = rng.choice(problem.alphabet)
            for index, value in problem.locked.items():
                child[index] = value
            children.append(child)
        scored = [(problem.score(letters), letters) for letters in children]
        evaluations += len(children)
        scored.sort(key=lambda pair: -pair[0])
        for score, letters in scored[:5]:
            board.offer(score, letters)

    best_score, best_letters = scored[0]
    return best_letters, best_score, evaluations


def _tournament(scored: Sequence, rng: random.Random, size: int = 3) -> list:
    picks = [rng.choice(scored) for _ in range(size)]
    picks.sort(key=lambda pair: -pair[0])
    return picks[0][1]


# --------------------------------------------------------------------------
# Parameter sweeps
# --------------------------------------------------------------------------


def parameter_grid(grid: dict) -> list:
    """Expand ``{"language": ["latin","italian"], "method": ["anneal"]}``."""
    import itertools

    if not grid:
        return [{}]
    keys = list(grid)
    values = [grid[k] if isinstance(grid[k], list) else [grid[k]] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def run_sweep(
    build_problem: Callable[[dict], Problem],
    grid: dict,
    base_options: SearchOptions,
    workers: int = 0,
    progress: Callable = None,
) -> list:
    """Run the solver once per combination in a parameter grid.

    Sweeps are embarrassingly parallel, so they use a process pool when
    ``workers`` is more than one.  With ``workers=0`` everything runs in this
    process, which keeps output deterministic and is usually fast enough.
    """
    combos = parameter_grid(grid)
    results = []
    iterator = combos
    if progress is not None:
        iterator = progress(combos)

    if workers and workers > 1:
        try:
            from concurrent.futures import ProcessPoolExecutor

            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_sweep_one, build_problem, combo, base_options) for combo in combos]
                for future in futures:
                    results.append(future.result())
            return results
        except Exception as exc:  # pragma: no cover - platform dependent
            _log.warning("parallel sweep unavailable (%s); running in this process", exc)

    for combo in iterator:
        results.append(_sweep_one(build_problem, combo, base_options))
    return results


def _sweep_one(build_problem, combo: dict, base_options: SearchOptions) -> dict:
    from dataclasses import replace

    options = replace(base_options, **{k: v for k, v in combo.items() if hasattr(base_options, k)})
    problem = build_problem(combo)
    result = solve(problem, options)
    return {
        "parameters": combo,
        "score": result.best_score,
        "evaluations": result.evaluations,
        "elapsed": result.elapsed,
        "mapping": {g: result.best_letters[i] for i, g in enumerate(problem.glyphs)},
    }


def default_fitness(language: str = "latin", function: str = "quadgram") -> FitnessOptions:
    return FitnessOptions(function=function, language=language)
