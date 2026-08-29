"""Show which rule wins wherever two rules could both apply."""

from __future__ import annotations

from . import Plugin, PluginContext
from ._common import save_text


def run(ctx: PluginContext) -> dict:
    engine = ctx.result.engine
    conflicts = engine.conflicts()

    lines = [
        "Rule precedence in force: %s" % " > ".join(engine.precedence),
        "",
    ]
    if not conflicts:
        lines.append("No overlapping rules. Every glyph has exactly one rule that can apply.")
    else:
        lines.append("%d place(s) where more than one rule could apply:" % len(conflicts))
        lines.append("")
        for item in conflicts:
            lines.append("  %s  (%s)" % (item["glyph"], item["kind"]))
            for name, value in item["rules"].items():
                marker = "  <- wins" if name == item["winner"] else ""
                lines.append("      %-14s %s%s" % (name, value, marker))
            lines.append("      %s" % item["explanation"])
            lines.append("")

    lines.append(
        "How precedence works\n"
        "--------------------\n"
        "  1. Longer glyph groups always match before shorter ones. If you define both '4' and\n"
        "     '4o', the sequence 4o is read as one unit and the rule for '4' never applies there.\n"
        "  2. Within one glyph, positional and occurrence rules are tried in the order set by\n"
        "     mapping.precedence in config.json (currently %s).\n"
        "  3. A one-letter word is both word-initial and word-final, so precedence decides.\n"
        "  4. A glyph with no matching rule falls back to its plain rule, and a glyph with no\n"
        "     plain rule falls back to mapping.unmapped ('%s')." % (" > ".join(engine.precedence), engine.unmapped)
    )

    save_text(ctx, "conflicts.txt", "\n".join(lines) + "\n", "which mapping rule wins where rules overlap")
    return {"count": len(conflicts), "precedence": list(engine.precedence), "conflicts": conflicts}


PLUGIN = Plugin(
    name="conflicts",
    title="Rule conflict detection",
    stage="analyze",
    category="validation",
    summary="Lists every glyph where two rules overlap, and says which one wins.",
    help=(
        "Positional rules, occurrence rules and multi-glyph groups can all fire on the same piece of\n"
        "text. This plugin finds every such overlap and states the outcome, so a mapping never does\n"
        "something you did not intend without telling you.\n\n"
        "Two kinds of overlap are reported. A *position* conflict is one glyph carrying several\n"
        "rules - a word-initial rule and a word-final rule, say, which both apply to a one-letter\n"
        "word. A *group* conflict is one glyph sequence being a prefix of another, where the longer\n"
        "group always wins.\n\n"
        "The order rules are tried in is yours to set, with mapping.precedence in config.json."
    ),
    defaults={},
    enabled_by_default=True,
    run=run,
)
