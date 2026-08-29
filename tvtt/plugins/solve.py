"""Search automatically for a mapping that maximises a fitness function."""

from __future__ import annotations

from collections import Counter

from ..langmodel import FITNESS_DESCRIPTIONS, FITNESS_FUNCTIONS, Fitness, FitnessOptions
from ..mapping import LATIN_LOWER, SLOT_NAMES
from ..profiles import save_mapping
from ..reporting import glyph_label
from ..solver import SEARCH_DESCRIPTIONS, SEARCH_METHODS, Problem, SearchOptions, solve
from ..util import table
from . import Plugin, PluginContext
from ._common import save_json, save_text, track


def run(ctx: PluginContext) -> dict:
    method = ctx.setting("method", "hillclimb")
    if method not in SEARCH_METHODS:
        raise ValueError("unknown method %r; use one of %s" % (method, ", ".join(SEARCH_METHODS)))
    function = ctx.setting("fitness", "quadgram")
    if function not in FITNESS_FUNCTIONS:
        raise ValueError("unknown fitness %r; use one of %s" % (function, ", ".join(FITNESS_FUNCTIONS)))

    language = ctx.setting("language") or ctx.config.get("reference.language", "latin")
    alphabet = ctx.setting("alphabet", LATIN_LOWER)
    locked = dict(ctx.setting("lock", {}) or {})

    vocabulary = Counter(ctx.corpus.words())
    fitness_options = FitnessOptions(
        function=function,
        language=language,
        quadgram_weight=ctx.setting("quadgramWeight", 1.0),
        dictionary_weight=ctx.setting("dictionaryWeight", 0.6),
        entropy_weight=ctx.setting("entropyWeight", 0.4),
    )
    fitness = Fitness(fitness_options, vocabulary)
    problem = Problem(
        vocabulary,
        ctx.result.engine,
        fitness,
        alphabet=alphabet,
        locked=locked,
        positions=ctx.setting("positions", "none"),
        min_occurrences=ctx.setting("minOccurrences", 25),
    )

    options = SearchOptions(
        method=method,
        iterations=ctx.setting("iterations", 40000),
        restarts=ctx.setting("restarts", 6),
        population=ctx.setting("population", 40),
        generations=ctx.setting("generations", 120),
        mutation_rate=ctx.setting("mutationRate", 0.12),
        start_temperature=ctx.setting("startTemperature", 1.0),
        end_temperature=ctx.setting("endTemperature", 0.01),
        leaderboard=ctx.setting("leaderboard", 10),
        seed=ctx.config.seed(),
        alphabet=alphabet,
        locked=locked,
        injective=ctx.setting("injective", False),
        swap_only=ctx.setting("swapOnly", False),
    )

    current = fitness.score([ctx.result.engine.map_word(w) for w in problem.types])

    def progress(iterable):
        return track(ctx, iterable, "%s search" % method)

    result = solve(problem, options, progress)

    board_rows = []
    for rank, (score, letters) in enumerate(result.leaderboard, 1):
        sample = " ".join(problem.render(letters, i) for i in range(min(6, len(problem.types))))
        board_rows.append([rank, "%.5f" % score, sample])

    mapping_rows = [
        [
            glyph_label(problem.glyphs[g]),
            SLOT_NAMES.get(slot, "plain"),
            result.best_letters[i],
            "locked" if problem.glyphs[g] in locked else "",
        ]
        for i, (g, slot) in enumerate(problem.units)
    ]

    blocks = [
        "Automated search",
        "=" * 16,
        "",
        "method:  %s - %s" % (method, SEARCH_DESCRIPTIONS[method]),
        "fitness: %s - %s" % (function, FITNESS_DESCRIPTIONS[function]),
        "target:  %s" % language,
        "seed:    %d" % options.seed,
        "",
        table(
            [
                ["your current mapping", "%.5f" % current],
                ["best found", "%.5f" % result.best_score],
                ["improvement", "%+.5f" % (result.best_score - current)],
                ["candidates evaluated", result.evaluations],
                ["time", "%.1f s" % result.elapsed],
                ["glyphs locked", len(locked)],
            ],
            ["measure", "value"],
        ),
        "",
        "Best mapping found",
        "-" * 18,
        table(mapping_rows, ["glyph", "becomes", ""]),
        "",
        "Leaderboard (inspect the near-misses; a solver's second choice is often instructive)",
        "-" * 84,
        table(board_rows, ["rank", "score", "first words"]),
        "",
        _warning(),
    ]
    save_text(ctx, "solver.txt", "\n".join(blocks) + "\n", "automated mapping search")
    save_json(ctx, "solver.json", result.to_dict(problem), "the best mapping and the leaderboard")

    if ctx.setting("saveAs"):
        mapping = result.as_mapping(
            problem,
            meta={
                "name": ctx.setting("saveAs"),
                "alphabet": ctx.corpus.alphabet,
                "language": language,
                "notes": "found by %s search on %s, fitness %s" % (method, ctx.corpus.selection.describe(), function),
                "score": round(result.best_score, 6),
                "score_metric": function,
                "positions": problem.positions,
            },
        )
        path = save_mapping(mapping, ctx.setting("saveAs"), note="solver result")
        ctx.record_output(path, "the mapping found by the solver")

    return {
        "method": method,
        "fitness": function,
        "language": language,
        "current_score": round(current, 6),
        "best_score": round(result.best_score, 6),
        "improvement": round(result.best_score - current, 6),
        "evaluations": result.evaluations,
        "elapsed_seconds": round(result.elapsed, 2),
        "positions": problem.positions,
        "rules_searched": len(problem.units),
        "best_mapping": {glyph_label(problem.unit_label(i)): result.best_letters[i] for i in range(len(problem.units))},
        "leaderboard": [{"rank": i + 1, "score": round(s, 6)} for i, (s, _l) in enumerate(result.leaderboard)],
    }


def _warning() -> str:
    return (
        "Before you believe this\n"
        "-----------------------\n"
        "A solver always returns something. Given a free choice of letters it will find an\n"
        "assignment that makes any text score as well as that text can score, whether or not there\n"
        "is a message in it. The result above is a hypothesis, not a finding.\n\n"
        "Three checks, all one line of configuration each:\n\n"
        "  random_controls    is this score outside the distribution of random mappings?\n"
        "  holdout            does it survive on a section it was not fitted to?\n"
        "  corpus_match       do the commonest output words become the language's function words?\n\n"
        "The third is the one solvers fail most often. Optimising a quadgram score produces text\n"
        "with realistic letter sequences and no realistic vocabulary, and it is obvious the moment\n"
        "you look at the stopword alignment.\n\n"
        'If you are confident about some glyphs, put them in the \'lock\' setting - {"o": "a"} - and\n'
        "let the search fill in only the rest. Constraining the search is usually worth far more\n"
        "than running it for longer."
    )


PLUGIN = Plugin(
    name="solve",
    title="Automated mapping search",
    stage="search",
    category="search",
    summary="Hill climbing, simulated annealing or a genetic algorithm over a fitness function.",
    help=(
        "The standard machinery for breaking a substitution cipher, pointed at the manuscript.\n\n"
        "Methods:\n"
        "  hillclimb  " + SEARCH_DESCRIPTIONS["hillclimb"] + "\n"
        "  anneal     " + SEARCH_DESCRIPTIONS["anneal"] + "\n"
        "  genetic    " + SEARCH_DESCRIPTIONS["genetic"] + "\n\n"
        "Fitness functions:\n"
        + "\n".join("  %-10s %s" % (name, FITNESS_DESCRIPTIONS[name]) for name in FITNESS_FUNCTIONS)
        + "\n\n"
        "Useful constraints:\n"
        '  lock       glyphs you are confident about, as {"o": "a", "9": "s"} - the search will\n'
        "             not touch them, which both speeds it up and keeps your hypothesis intact\n"
        "  swapOnly   only exchange letters between glyphs, never reassign one freely. Keeps the\n"
        "             letter distribution fixed and stops the search collapsing onto three vowels\n"
        "  injective  force every glyph to a different letter (only possible when the alphabet is\n"
        "             at least as large as the glyph inventory)\n\n"
        "Set 'saveAs' to a name and the best mapping is saved as a profile you can run normally.\n\n"
        "This plugin is the slow one. It is also the one whose output you should trust least\n"
        "without the baseline plugins to check it against."
    ),
    defaults={
        "method": "hillclimb",
        "fitness": "quadgram",
        "language": "",
        "iterations": 40000,
        "restarts": 6,
        "population": 40,
        "generations": 120,
        "mutationRate": 0.12,
        "startTemperature": 1.0,
        "endTemperature": 0.01,
        "leaderboard": 10,
        "positions": "none",
        "minOccurrences": 25,
        "alphabet": LATIN_LOWER,
        "lock": {},
        "injective": False,
        "swapOnly": False,
        "quadgramWeight": 1.0,
        "dictionaryWeight": 0.6,
        "entropyWeight": 0.4,
        "saveAs": "",
    },
    settings_help={
        "method": "hillclimb, anneal or genetic.",
        "fitness": "quadgram, trigram, bigram, dictionary, entropy or blend.",
        "language": "Target language; empty uses reference.language.",
        "iterations": "Total candidate evaluations for hillclimb and anneal.",
        "restarts": "How many times hill climbing starts over from a random mapping.",
        "population": "Population size for the genetic algorithm.",
        "generations": "Generations for the genetic algorithm.",
        "mutationRate": "Chance of mutating each glyph in a child mapping.",
        "startTemperature": "Annealing start temperature: higher explores more.",
        "endTemperature": "Annealing end temperature.",
        "leaderboard": "How many near-miss candidates to keep.",
        "positions": (
            "Which positional rules the search may use: 'none' for one letter per glyph, "
            "'edges' to let a glyph differ at the start and end of a word, 'all' to add the "
            "first four occurrences within a word. Voynichese is strongly positional, but "
            "every position added is another free parameter, so check the overfitting report."
        ),
        "minOccurrences": (
            "A position is searched separately only when it covers at least this many "
            "occurrences, which keeps rare positions from becoming free parameters."
        ),
        "alphabet": "The letters the search may assign.",
        "lock": 'Glyphs to fix, as an object: {"o": "a"}.',
        "injective": "Force every glyph to a different letter.",
        "swapOnly": "Only swap letters between glyphs; never reassign one freely.",
        "quadgramWeight": "Weight of the n-gram term when fitness is 'blend'.",
        "dictionaryWeight": "Weight of the dictionary term when fitness is 'blend'.",
        "entropyWeight": "Weight of the entropy term when fitness is 'blend'.",
        "saveAs": "Save the best mapping under this profile name.",
    },
    heavy=True,
    run=run,
)
