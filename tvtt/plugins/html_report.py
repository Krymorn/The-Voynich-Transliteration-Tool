"""The interactive HTML report: search, filter, highlight, page images."""

from __future__ import annotations

from collections import Counter

from ..folios import SECTIONS
from ..fonts import choose_font, display_text, glyph_legend
from ..ivtff import LOCUS_TYPE_NAMES
from ..links import all_links, attribution
from ..reporting import Section, document, esc, heatmap_html, html_table, stat_grid
from ..util import write_text
from . import Plugin, PluginContext
from ._common import verdict_class


def run(ctx: PluginContext) -> dict:
    corpus = ctx.corpus
    result = ctx.result
    results = ctx.results
    font = choose_font(ctx.setting("font", ""), corpus.alphabet)
    show_images = ctx.setting("pageImages", True)
    max_lines = ctx.setting("maxLines", 6000)

    sections = []
    sections.append(_overview(ctx, results))
    if ctx.setting("includeText", True):
        sections.append(_text_section(ctx, max_lines, show_images))
    if ctx.setting("includeFolios", True):
        sections.append(_folio_section(ctx, show_images))
    sections.append(_legend_section(ctx))
    stats = _statistics_sections(ctx, results)
    sections.extend(stats)
    sections.append(_links_section(ctx))

    page = document(
        title="Voynich transliteration report",
        subtitle="%s  |  %s  |  mapping: %s"
        % (
            corpus.title,
            corpus.selection.describe(),
            result.engine.mapping.meta.get("name", "unnamed"),
        ),
        sections=sections,
        extra_css=font.css() + (".voy{font-family:%s}" % font.font_family()),
        extra_js=(
            "tvttFilter('line-search','lines','data-hay');"
            "tvttSelect('section-filter','lines','data-sections');"
            "tvttHighlight('lines');"
            "tvttFilter('folio-search','folios','data-hay');"
        ),
    )
    path = write_text(ctx.output_path(ctx.setting("filename", "report.html")), page)
    ctx.record_output(path, "interactive HTML report")
    return {"path": str(path), "lines": min(len(result.lines), max_lines), "sections": len(sections)}


def _overview(ctx: PluginContext, results: dict) -> Section:
    corpus = ctx.corpus
    result = ctx.result
    words = result.words()
    items = [
        ("lines", len(result.lines), corpus.selection.describe()),
        ("words", len(words), "%d distinct" % len(set(words))),
        ("folios", len(corpus.folio_keys()), "of 227 in the manuscript"),
        ("glyphs", len(corpus.glyph_counts()), corpus.alphabet),
    ]
    entropy = results.get("entropy")
    if entropy:
        items.append(
            ("h2 conditional entropy", "%.3f" % entropy["h2_conditional_bits"], "manuscript sits near 2.0-2.4")
        )
    match = results.get("corpus_match")
    if match:
        items.append(("dictionary coverage", "%.1f%%" % (match["coverage"] * 100), match["language"]))
        items.append(("stopword alignment", "%.1f%%" % (match["stopword_coverage"] * 100), "the test that matters"))

    verdicts = []
    for key, label in (
        ("random_controls", "against random mappings"),
        ("match_significance", "dictionary hits against chance"),
        ("holdout", "on text it was not tuned on"),
        ("overfitting", "mapping complexity"),
        ("roundtrip", "reversibility"),
    ):
        payload = results.get(key)
        if not payload:
            continue
        text = (
            payload.get("verdict") or payload.get("worst_verdict") or payload.get("message") or payload.get("summary")
        )
        if text:
            first = str(text).split("\n")[0]
            verdicts.append(
                "<tr><td>%s</td><td class='%s'>%s</td></tr>" % (esc(label), verdict_class(first), esc(first))
            )

    body = stat_grid(items)
    if verdicts:
        body += (
            "<h3 style='margin:18px 0 6px;font-size:14px'>What the checks say</h3>"
            "<table><tbody>%s</tbody></table>" % "".join(verdicts)
        )
    else:
        body += (
            "<p class='why' style='margin-top:14px'>Enable the baseline plugins "
            "(random_controls, match_significance, holdout, overfitting) to see whether these "
            "numbers mean anything.</p>"
        )
    return Section("Overview", "What was run, and how far the result is from chance.", body)


def _text_section(ctx: PluginContext, max_lines: int, show_images: bool) -> Section:
    corpus = ctx.corpus
    result = ctx.result
    options = ["<option value=''>every section</option>"]
    for name, spec in SECTIONS.items():
        options.append("<option value='%s'>%s</option>" % (esc(name), esc(spec.title)))

    rows = []
    for locus, mapped in list(zip(corpus.loci, result.lines))[:max_lines]:
        info = corpus.folios.get(locus.key)
        section_names = " ".join(info.sections)
        haystack = "%s %s %s" % (locus.locus_id, locus.text, mapped)
        rows.append(
            "<div class='line' data-sections='%s' data-hay='%s'>"
            "<div class='loc'>%s<br><span class='pill'>%s</span></div>"
            "<div class='src voy' data-raw='%s'>%s</div>"
            "<div class='out'>%s</div></div>"
            % (
                esc(section_names),
                esc(haystack),
                esc(locus.locus_id),
                esc(LOCUS_TYPE_NAMES.get(locus.locus_type, locus.locus_type)),
                esc(display_text(locus.text)),
                esc(display_text(locus.text)),
                esc(mapped),
            )
        )

    controls = (
        "<div class='controls'>"
        "<input type='search' id='line-search' placeholder='search source or output text'>"
        "<select id='section-filter'>%s</select>"
        "<input type='search' id='glyph-highlight' placeholder='highlight a glyph, e.g. ch'>"
        "</div>" % "".join(options)
    )
    body = controls + "<div class='scroll' id='lines' style='max-height:640px'>%s</div>" % "".join(rows)
    if len(result.lines) > max_lines:
        body += "<p class='why'>Showing the first %d of %d lines.</p>" % (max_lines, len(result.lines))
    return Section(
        "Line by line",
        "Source on the left, your transliteration on the right. Search, filter by section, or type a "
        "glyph sequence to highlight every occurrence.",
        body,
    )


def _folio_section(ctx: PluginContext, show_images: bool) -> Section:
    corpus = ctx.corpus
    result = ctx.result
    grouped = {}
    for locus, mapped in zip(corpus.loci, result.lines):
        grouped.setdefault(locus.key, []).append((locus, mapped))

    limit = ctx.setting("maxFolios", 40)
    blocks = []
    for key in list(grouped)[:limit]:
        info = corpus.folios.get(key)
        links = all_links(key)
        lines = grouped[key]
        text = "".join(
            "<div class='line' style='grid-template-columns:120px 1fr'>"
            "<div class='loc'>%s</div><div class='out'>%s</div></div>" % (esc(line.locus_id), esc(m))
            for line, m in lines[:24]
        )
        image = ""
        if show_images and links["thumbnail"]:
            # Foldouts are photographed as one sheet, so the picture for f68r2
            # is labelled 68r. Say so rather than letting the folio and its
            # image look like they disagree.
            sheet = links["image_label"]
            caption = ""
            if sheet and sheet.replace(" ", "").lower() != key.lower():
                caption = "<div class='why' style='margin-top:4px'>image sheet: %s</div>" % esc(sheet)
            image = (
                "<a href='%s' target='_blank' rel='noreferrer'>"
                "<img loading='lazy' src='%s' alt='folio %s'></a>%s"
                % (esc(links["image"]), esc(links["thumbnail"]), esc(key), caption)
            )
        meta = "%s &middot; Currier %s &middot; scribe %s &middot; quire %s" % (
            esc(info.illustration_name),
            esc(info.currier or "?"),
            esc(info.scribe or "?"),
            esc(info.quire_name),
        )
        if info.extraneous_name:
            meta += " &middot; %s" % esc(info.extraneous_name)
        blocks.append(
            "<div class='folio' data-hay='%s'><div>%s<div class='links' style='margin-top:8px'>"
            "<a href='%s' target='_blank' rel='noreferrer'>Beinecke</a>"
            "<a href='%s' target='_blank' rel='noreferrer'>voynichese.com</a>"
            "<a href='%s' target='_blank' rel='noreferrer'>voynich.nu</a></div></div>"
            "<div><h3 style='margin:0 0 2px;font-size:15px'>f%s</h3>"
            "<div class='why'>%s</div>%s</div></div>"
            % (
                esc("f%s %s %s" % (key, info.illustration_name, info.currier)),
                image,
                esc(links["beinecke"]),
                esc(links["voynichese"]),
                esc(links["voynich_nu"]),
                esc(key),
                meta,
                text,
            )
        )

    controls = "<div class='controls'><input type='search' id='folio-search' placeholder='find a folio'></div>"
    note = "<p class='why'>%s</p>" % esc(attribution()) if show_images else ""
    more = (
        "<p class='why'>Showing the first %d of %d folios; raise 'maxFolios' to see more.</p>" % (limit, len(grouped))
        if len(grouped) > limit
        else ""
    )
    return Section(
        "Folios",
        "Each page with its transliteration, its metadata and links to the manuscript itself.",
        controls + "<div id='folios'>%s</div>%s%s" % ("".join(blocks), more, note),
    )


def _legend_section(ctx: PluginContext) -> Section:
    counts = ctx.corpus.glyph_counts()
    total = sum(counts.values()) or 1
    rows = glyph_legend(ctx.result.engine, counts)[: ctx.setting("legendRows", 120)]
    body = html_table(
        [
            [
                r["rendered"],
                r["display"],
                r["count"],
                "%.2f%%" % (100 * r["count"] / total),
                r["plain"] or "-",
                ", ".join("%s=%s" % (k, v) for k, v in r["rules"].items() if k != "plain") or "-",
            ]
            for r in rows
        ],
        ["shape", "written as", "count", "share", "becomes", "positional rules"],
        numeric=["count", "share"],
        voynich_columns=["shape"],
    )
    return Section(
        "Glyph legend",
        "The shape as it appears in the manuscript, how the transcription writes it, "
        "and what your mapping turns it into.",
        body,
    )


def _statistics_sections(ctx: PluginContext, results: dict) -> list:
    out = []

    entropy = results.get("entropy")
    if entropy:
        out.append(
            Section(
                "Entropy",
                "How predictable the text is. The manuscript's h2 sits near 2.0-2.4 bits; European "
                "languages sit near 3.0-3.5.",
                html_table(
                    [[k.replace("_", " "), v] for k, v in entropy.items() if isinstance(v, (int, float))],
                    ["measure", "value"],
                    numeric=["value"],
                )
                + "<p class='why'>%s</p>" % esc(entropy.get("interpretation", "")),
            )
        )

    lengths = results.get("word_length")
    if lengths:
        distribution = lengths.get("distribution", {})
        total = lengths.get("total_words", 1) or 1
        rows = [
            [k, v, "%.2f%%" % (100 * v / total)] for k, v in sorted(distribution.items(), key=lambda kv: int(kv[0]))
        ]
        out.append(
            Section(
                "Word length",
                lengths.get("verdict", ""),
                html_table(rows, ["characters", "words", "share"], numeric=["words", "share"]),
            )
        )

    ngrams = results.get("ngrams")
    if ngrams and ngrams.get("matrix"):
        alphabet = ngrams["alphabet"]
        out.append(
            Section(
                "Character transitions",
                "Row: the character. Column: what follows it. Darker means more frequent.",
                heatmap_html(
                    ngrams["matrix"],
                    alphabet,
                    alphabet,
                    "conditional entropy %.3f bits" % ngrams.get("conditional_entropy_bits", 0.0),
                ),
            )
        )

    sections = results.get("section_report")
    if sections:
        out.append(
            Section(
                "By section",
                "The same statistics computed separately for each part of the manuscript.",
                html_table(sections["table"], sections["headers"], numeric=sections["headers"][1:]),
            )
        )

    controls = results.get("language_controls")
    if controls:
        out.append(
            Section(
                "Real-language controls",
                "The identical statistics on samples of real languages, so the numbers have context.",
                html_table(controls["table"], controls["headers"], numeric=controls["headers"][1:]),
            )
        )

    random_controls = results.get("random_controls")
    if random_controls:
        out.append(
            Section(
                "Against random mappings",
                "Where your score falls among mappings that mean nothing.",
                html_table(
                    [[k.replace("_", " "), v] for k, v in random_controls.items() if isinstance(v, (int, float, str))],
                    ["measure", "value"],
                )
                + "<p class='%s'>%s</p>"
                % (verdict_class(random_controls.get("verdict", "")), esc(random_controls.get("verdict", ""))),
            )
        )

    match = results.get("corpus_match")
    if match:
        rows = [
            [r["rank"], r["output_word"], r["matched"] or "-", r["route"], "yes" if r["is_target_stopword"] else "no"]
            for r in match.get("stopword_alignment", [])
        ]
        out.append(
            Section(
                "Dictionary match",
                match.get("headline", ""),
                html_table(rows, ["rank", "your word", "matched", "route", "is a stopword"], numeric=["rank"]),
            )
        )

    return out


def _links_section(ctx: PluginContext) -> Section:
    counts = Counter(locus.key for locus in ctx.corpus.loci)
    rows = []
    for key, count in counts.most_common(200):
        links = all_links(key)
        info = ctx.corpus.folios.get(key)
        rows.append(
            [
                "f%s" % key,
                count,
                info.illustration_name,
                info.currier or "-",
                info.scribe or "-",
                "<a href='%s' target='_blank' rel='noreferrer'>image</a> "
                "<a href='%s' target='_blank' rel='noreferrer'>voynichese</a> "
                "<a href='%s' target='_blank' rel='noreferrer'>voynich.nu</a>"
                % (links["image"], links["voynichese"], links["voynich_nu"]),
            ]
        )
    head = "".join("<th>%s</th>" % h for h in ["folio", "lines", "section", "Currier", "scribe", "links"])
    body = "".join(
        "<tr><td>%s</td><td class='num'>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (esc(r[0]), esc(r[1]), esc(r[2]), esc(r[3]), esc(r[4]), r[5])
        for r in rows
    )
    return Section(
        "Folio index",
        "Every folio in this selection, with links to the page image and the two reference sites.",
        "<div class='scroll'><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>" % (head, body),
    )


PLUGIN = Plugin(
    name="html_report",
    title="Interactive HTML report",
    stage="report",
    category="output",
    summary="One self-contained web page with the text, the statistics and the manuscript images.",
    help=(
        "The main output most people will look at. A single HTML file, openable in any browser,\n"
        "with no server and no installation.\n\n"
        "It contains the source text and your transliteration line by line, with a search box, a\n"
        "filter by manuscript section, and a highlighter that marks every occurrence of a glyph\n"
        "sequence you type. Below that: a folio-by-folio view with the actual manuscript page\n"
        "alongside its transliteration, the glyph legend, and whichever statistics you had enabled\n"
        "on this run, including the transition heatmap and the section comparison.\n\n"
        "The page images come from Yale's IIIF service and load from the web when you open the\n"
        "report. Set 'pageImages' to false for a report that works with no network at all.\n\n"
        "Everything else - the CSS, the JavaScript, the Voynich font - is embedded, so the file\n"
        "keeps working when it is emailed or archived."
    ),
    defaults={
        "filename": "report.html",
        "includeText": True,
        "includeFolios": True,
        "pageImages": True,
        "maxLines": 6000,
        "maxFolios": 40,
        "legendRows": 120,
        "font": "",
    },
    settings_help={
        "filename": "Name of the report file.",
        "includeText": "Include the line-by-line source and output view.",
        "includeFolios": "Include the folio-by-folio view.",
        "pageImages": "Show manuscript page images from Yale's IIIF service.",
        "maxLines": "How many lines to include in the line view.",
        "maxFolios": "How many folios to include in the folio view.",
        "legendRows": "How many glyphs to show in the embedded legend.",
        "font": "Font file for the source text; empty picks one to suit the alphabet.",
    },
    optional_requires=(
        "entropy",
        "word_length",
        "ngrams",
        "section_report",
        "language_controls",
        "random_controls",
        "corpus_match",
    ),
    enabled_by_default=True,
    run=run,
)
