"""Match the transliteration against a real dictionary, with per-word confidence."""

from __future__ import annotations

from collections import Counter

from ..lexicon import available_dictionaries, load_dictionary, load_reference_folder
from ..matcher import ROUTE_CONFIDENCE, Matcher, MatchOptions
from ..reporting import write_csv
from ..util import table
from . import Plugin, PluginContext
from ._common import save_json, save_text, track


def run(ctx: PluginContext) -> dict:
    language = ctx.setting("language") or ctx.config.get("reference.language", "latin")
    source = ctx.setting("source", "bundled")

    if source == "folder":
        dictionary = load_reference_folder(ctx.config.get("reference.folder", "reference_texts"))
    else:
        dictionary = load_dictionary(language, ctx.config.get("reference.folder", "reference_texts"))

    options = MatchOptions(
        language=language,
        max_edits=ctx.setting("maxEdits", 1),
        allow_stemming=ctx.setting("stemming", True),
        allow_abbreviations=ctx.setting("abbreviations", False),
        allow_abjad=ctx.setting("abjad", False),
        allow_merge=ctx.setting("merge", True),
        allow_split=ctx.setting("split", True),
        allow_phonetic=ctx.setting("phonetic", False),
        allow_fuzzy=ctx.setting("fuzzy", True),
        phonetic_algorithm=ctx.setting("phoneticAlgorithm", "metaphone"),
        transpositions=ctx.setting("transpositions", True),
        min_length=ctx.setting("minLength", 2),
        min_confidence=ctx.setting("minConfidence", 0.0),
        stopword_count=ctx.setting("stopwordCount", 30),
    )

    matcher = Matcher(dictionary, options)
    output_words = ctx.result.words()
    source_words = ctx.corpus.words()

    # Warm the per-word cache with a progress bar, then match in one pass.
    for word in track(ctx, sorted(set(output_words)), "matching words"):
        matcher.match_word(word)
    report = matcher.match_text(output_words, source_words)

    route_rows = [
        [
            route,
            count,
            "%.1f%%" % (100 * count / report.tokens if report.tokens else 0),
            "%.2f" % ROUTE_CONFIDENCE.get(route, 0.0),
        ]
        for route, count in report.route_counts.most_common()
    ]

    stopword_rows = [
        [
            r["rank"],
            r["output_word"],
            r["matched"] or "-",
            r["route"],
            "yes" if r["is_target_stopword"] else "no",
            r["target_rank"] or "-",
        ]
        for r in report.stopword_rows
    ]

    blocks = [
        "Corpus match against %s" % dictionary.name,
        "=" * (21 + len(dictionary.name)),
        "",
        dictionary.description,
        "%d word types, %d tokens in the dictionary." % (len(dictionary), dictionary.total),
        "",
        report.headline(),
        "",
        "Matches by route",
        "-" * 16,
        table(route_rows, ["route", "words", "share", "confidence"]),
        "",
        "Stopword alignment: do your commonest words map to the language's commonest words?",
        "-" * 82,
        table(stopword_rows, ["rank", "your word", "matched", "route", "is a stopword", "its rank"]),
        "",
        "Most frequent matches",
        "-" * 21,
        table(report.matched_top[:30], ["dictionary word", "times"]),
        "",
        "Most frequent misses",
        "-" * 20,
        table(report.unmatched_top[:30], ["output word", "times"]),
        "",
        _explainer(),
    ]
    save_text(ctx, "corpus_match.txt", "\n".join(blocks) + "\n", "dictionary match report")

    if ctx.setting("writeCorrectedText", True):
        save_text(
            ctx,
            "output_matched.txt",
            report.corrected_text + "\n",
            "the transliteration with every match substituted in",
        )

    if ctx.setting("writeCsv", True):
        rows = []
        seen = Counter()
        for match in report.matches:
            if match.route == "none":
                continue
            key = (match.output, match.matched)
            seen[key] += 1
        for (output, matched), count in seen.most_common():
            example = matcher.match_word(output)
            rows.append(
                [
                    output,
                    matched,
                    example.route,
                    example.distance,
                    round(example.confidence, 3),
                    round(example.weight, 2),
                    count,
                ]
            )
        path = write_csv(
            ctx.output_path("matches.csv"),
            rows,
            ["output_word", "matched", "route", "distance", "confidence", "information_bits", "count"],
        )
        ctx.record_output(path, "every match with its confidence")

    payload = report.to_dict()
    payload["dictionary_size"] = len(dictionary)
    payload["dictionary_description"] = dictionary.description
    payload["headline"] = report.headline()
    if ctx.setting("writeJson", False):
        save_json(ctx, "corpus_match.json", payload, "dictionary match report as JSON")
    return payload


def _explainer() -> str:
    return (
        "Reading these numbers\n"
        "---------------------\n"
        "  coverage            the plain share of words that matched something\n"
        "  weighted coverage   the same, but each match counts for how informative the word is,\n"
        "                      so matching 'et' is worth far less than matching 'pharmacum'\n"
        "  confidence-weighted coverage\n"
        "                      each match discounted by how it was found: an exact hit counts\n"
        "                      fully, a two-edit fuzzy hit counts for very little\n"
        "  stopword alignment  the share of your commonest words that are the target language's\n"
        "                      commonest words\n\n"
        "The last one is the test that matters. A real substitution of a real language puts that\n"
        "language's function words at the top of the frequency list, because function words are\n"
        "frequent in every text. A mapping tuned to maximise dictionary hits almost never does:\n"
        "it collects a long tail of rare words while its own commonest words match nothing.\n\n"
        "None of these numbers means anything on its own. Enable 'match_significance' to see how\n"
        "many matches a random mapping buys on the same text with the same dictionary."
    )


PLUGIN = Plugin(
    name="corpus_match",
    title="Corpus matching",
    stage="analyze",
    category="matching",
    summary="Scores the output against a reference dictionary, with a confidence per word.",
    help=(
        "Compares every output word with a reference vocabulary and reports how much of the text is\n"
        "real words - by four different measures, because the plain hit rate is the least\n"
        "informative of them.\n\n"
        "Matches are found by a series of routes, tried in decreasing order of trustworthiness, and\n"
        "each route carries its own confidence:\n\n"
        "  exact          the word is in the dictionary\n"
        "  stem           it matches after light suffix stripping, so inflected forms count\n"
        "  abbreviation   it matches after expanding medieval Latin shorthand (9 for -us, and so on)\n"
        "  abjad          its consonant skeleton matches, for consonant-only mappings\n"
        "  merge          it plus the next word form a real word\n"
        "  split          it breaks into two real words\n"
        "  phonetic       it sounds like a real word (Metaphone or Soundex)\n"
        "  fuzzy          it is within a small Damerau-Levenshtein distance of one\n\n"
        "Bundled dictionaries: " + ", ".join(n for n, _ in available_dictionaries()) + ".\n"
        "Set 'source' to 'folder' to use everything in your reference_texts/ folder instead.\n\n"
        "Turn the permissive routes on one at a time and watch what happens to the stopword\n"
        "alignment. If loosening the matching raises coverage but not alignment, the extra hits\n"
        "are noise."
    ),
    defaults={
        "language": "",
        "source": "bundled",
        "maxEdits": 1,
        "stemming": True,
        "abbreviations": False,
        "abjad": False,
        "merge": True,
        "split": True,
        "phonetic": False,
        "fuzzy": True,
        "phoneticAlgorithm": "metaphone",
        "transpositions": True,
        "minLength": 2,
        "minConfidence": 0.0,
        "stopwordCount": 30,
        "writeCorrectedText": True,
        "writeCsv": True,
        "writeJson": False,
    },
    settings_help={
        "language": "Which dictionary to match against; empty uses reference.language.",
        "source": "'bundled' for a shipped dictionary, 'folder' for your reference_texts folder.",
        "maxEdits": "Maximum edit distance for a fuzzy match. 0 disables fuzzy matching; 1 is the default; 2 is very permissive and roughly ten times slower.",
        "stemming": "Allow a match after stripping inflectional endings.",
        "abbreviations": "Expand medieval Latin scribal abbreviations before matching.",
        "abjad": "Match on consonant skeletons, for mappings that produce no vowels.",
        "merge": "Allow two adjacent output words to be joined into one dictionary word.",
        "split": "Allow one output word to be split into two dictionary words.",
        "fuzzy": "Allow a match within maxEdits of a dictionary word. Turn off for exact matching only.",
        "phonetic": "Allow a match on phonetic key rather than spelling.",
        "phoneticAlgorithm": "'metaphone' or 'soundex'.",
        "transpositions": "Count a swap of two neighbouring letters as one edit (Damerau-Levenshtein).",
        "minLength": "Ignore output words shorter than this.",
        "minConfidence": "Discard matches below this confidence.",
        "stopwordCount": "How many top words to use for the stopword alignment test.",
        "writeCorrectedText": "Write the text with matches substituted in.",
        "writeCsv": "Write matches.csv with every match and its confidence.",
        "writeJson": "Also write the report as JSON.",
    },
    heavy=True,
    run=run,
)
