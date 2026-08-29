"""Run the solver across a grid of parameters, optionally in parallel."""

from __future__ import annotations

from collections import Counter

from ..langmodel import Fitness, FitnessOptions
from ..mapping import LATIN_LOWER
from ..reporting import write_csv
from ..solver import Problem, SearchOptions, parameter_grid, solve
from ..util import table
from . import Plugin, PluginContext
from ._common import save_json, save_text, track


def run(ctx: PluginContext) -> dict:
    grid = dict(ctx.setting("grid", {}) or {})
    if not grid:
        grid = {"language": ["latin", "italian"], "method": ["hillclimb"]}

    combos = parameter_grid(grid)
    workers = ctx.setting("workers") or ctx.config.get("performance.workers", 0)
    vocabulary = Counter(ctx.corpus.words())
    engine = ctx.result.engine

    base = SearchOptions(
        iterations=ctx.setting("iterations", 12000),
        restarts=ctx.setting("restarts", 3),
        leaderboard=1,
        seed=ctx.config.seed(),
        alphabet=ctx.setting("alphabet", LATIN_LOWER),
    )

    rows = []
    results = []
    for combo in track(ctx, combos, "parameter grid"):
        options = SearchOptions(
            method=combo.get("method", base.method),
            iterations=int(combo.get("iterations", base.iterations)),
            restarts=int(combo.get("restarts", base.restarts)),
            population=int(combo.get("population", base.population)),
            generations=int(combo.get("generations", base.generations)),
            leaderboard=1,
            seed=base.seed,
            alphabet=base.alphabet,
            swap_only=bool(combo.get("swapOnly", False)),
            injective=bool(combo.get("injective", False)),
        )
        fitness = Fitness(
            FitnessOptions(
                function=combo.get("fitness", ctx.setting("fitness", "quadgram")),
                language=combo.get("language", ctx.config.get("reference.language", "latin")),
            ),
            vocabulary,
        )
        problem = Problem(vocabulary, engine, fitness, alphabet=base.alphabet)
        result = solve(problem, options)
        label = ", ".join("%s=%s" % (k, v) for k, v in sorted(combo.items()))
        rows.append([label, "%.5f" % result.best_score, result.evaluations, "%.1f" % result.elapsed])
        results.append(
            {
                "parameters": combo,
                "score": round(result.best_score, 6),
                "evaluations": result.evaluations,
                "elapsed_seconds": round(result.elapsed, 2),
                "mapping": {problem.unit_label(i): result.best_letters[i] for i in range(len(problem.units))},
            }
        )

    rows.sort(key=lambda r: -float(r[1]))
    results.sort(key=lambda r: -r["score"])

    blocks = [
        "Parameter sweep",
        "=" * 15,
        "",
        "%d combination(s) from the grid: %s" % (len(combos), grid),
        "",
        table(rows, ["parameters", "best score", "evaluations", "seconds"]),
        "",
        "Reading a sweep\n"
        "---------------\n"
        "Scores from different fitness functions are on different scales and must not be compared\n"
        "with each other. Compare within a column: which language, which method, which constraint\n"
        "does best for the *same* measure.\n\n"
        "A sweep is also a form of searching, and a large grid will eventually turn up a good score\n"
        "by chance. Treat the winner as a candidate to test, not as a conclusion, and put it\n"
        "through 'random_controls' and 'holdout' before you believe it.",
    ]
    save_text(ctx, "sweep.txt", "\n".join(blocks) + "\n", "solver results across a parameter grid")
    save_json(ctx, "sweep.json", {"grid": grid, "results": results}, "sweep results with every mapping")

    if ctx.setting("writeCsv", True):
        path = write_csv(
            ctx.output_path("sweep.csv"),
            [[r[0], r[1], r[2], r[3]] for r in rows],
            ["parameters", "best_score", "evaluations", "seconds"],
        )
        ctx.record_output(path, "sweep results as CSV")

    return {"grid": grid, "combinations": len(combos), "results": results[:20], "workers": workers}


PLUGIN = Plugin(
    name="sweep",
    title="Parameter sweep",
    stage="search",
    category="search",
    summary="Runs the solver once per combination in a parameter grid and ranks the results.",
    help=(
        "Instead of guessing which target language or search method suits your idea, try them all.\n\n"
        "The 'grid' setting is an object of lists; every combination is run and the results are\n"
        "ranked. For example:\n\n"
        '    "grid": {\n'
        '      "language": ["latin", "italian", "middle_high_german"],\n'
        '      "method": ["hillclimb", "anneal"],\n'
        '      "swapOnly": [true, false]\n'
        "    }\n\n"
        "runs twelve searches. Keep 'iterations' low for a broad sweep and then re-run the winner\n"
        "properly with the 'solve' plugin.\n\n"
        "One caution: scores from different fitness functions live on different scales, so only\n"
        "compare rows that share a fitness. And remember that trying many combinations is itself a\n"
        "search - the best of twelve runs is not twelve times as convincing as one."
    ),
    defaults={
        "grid": {},
        "fitness": "quadgram",
        "iterations": 12000,
        "restarts": 3,
        "alphabet": LATIN_LOWER,
        "workers": 0,
        "writeCsv": True,
    },
    settings_help={
        "grid": "An object of lists; every combination is run. Keys: language, method, fitness, iterations, restarts, swapOnly, injective.",
        "fitness": "Default fitness when the grid does not vary it.",
        "iterations": "Default iterations per run. Keep this small for a broad sweep.",
        "restarts": "Default restarts per run.",
        "alphabet": "The letters the search may assign.",
        "workers": "Reserved for parallel runs; 0 uses this process (deterministic).",
        "writeCsv": "Also write sweep.csv.",
    },
    heavy=True,
    run=run,
)
