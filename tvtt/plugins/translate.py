"""Optional machine translation of the output. The only plugin that uses the network."""

from __future__ import annotations

from ..errors import PluginError
from . import Plugin, PluginContext
from ._common import save_text, track


def run(ctx: PluginContext) -> dict:
    if ctx.config.offline() and not ctx.setting("allowNetwork", False):
        raise PluginError(
            "translation needs the network, and TVTT is in offline mode",
            hint='Set "network": {"offline": false} in config.json, or set this plugin\'s '
            '"allowNetwork" setting to true, if you are content for your transliteration to be '
            "sent to an external translation service.",
            skippable=True,
        )

    translator_module = ctx.require_module("deep_translator", "machine translation")
    from deep_translator import GoogleTranslator  # noqa: PLC0415 - optional dependency

    source = ctx.setting("sourceLanguage", "la")
    target = ctx.setting("targetLanguage") or ctx.config.get("translationLanguage", "en")
    chunk_size = max(500, min(4500, ctx.setting("chunkSize", 4000)))

    text = " ".join(ctx.result.words())
    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    limit = ctx.setting("maxChunks", 20)
    if len(chunks) > limit:
        ctx.log.warning("truncating to the first %d chunk(s) of %d", limit, len(chunks))
        chunks = chunks[:limit]

    translator = GoogleTranslator(source=source, target=target)
    pieces = []
    for chunk in track(ctx, chunks, "translating"):
        try:
            pieces.append(translator.translate(text=chunk) or "")
        except Exception as exc:
            ctx.log.warning("translation of one chunk failed: %s", exc)
            pieces.append("")

    translated = " ".join(p for p in pieces if p)
    save_text(ctx, ctx.setting("filename", "translated.txt"), translated + "\n", "machine translation of the output")

    return {
        "source": source,
        "target": target,
        "characters_sent": sum(len(c) for c in chunks),
        "chunks": len(chunks),
        "characters_returned": len(translated),
        "library": getattr(translator_module, "__name__", "deep_translator"),
    }


PLUGIN = Plugin(
    name="translate",
    title="Machine translation",
    stage="report",
    category="output",
    summary="Sends the output to Google Translate. Off by default, and requires network access.",
    help=(
        "Runs your transliteration through a machine translator, on the theory that if the mapping\n"
        "were right, the output would be readable.\n\n"
        "Two warnings, both important.\n\n"
        "First, this is the only part of TVTT that touches the network, and it works by sending\n"
        "your text to an external service. That is why offline mode blocks it and why it is\n"
        "disabled by default: nothing leaves your machine unless you say so twice.\n\n"
        "Second, machine translation is spectacularly good at producing confident nonsense from\n"
        "gibberish. Give a translator a string of Latin-looking letters and it will hand back a\n"
        "fluent English sentence, every time, whether or not there was anything there. It is a\n"
        "curiosity, not evidence. Judge a mapping by the statistics and the baselines, not by\n"
        "whether a translator produced something that reads well.\n\n"
        "Needs the optional package deep-translator: pip install deep-translator"
    ),
    defaults={
        "sourceLanguage": "la",
        "targetLanguage": "en",
        "chunkSize": 4000,
        "maxChunks": 20,
        "filename": "translated.txt",
        "allowNetwork": False,
    },
    settings_help={
        "sourceLanguage": "Language code the output is assumed to be in.",
        "targetLanguage": "Language code to translate into.",
        "chunkSize": "Characters per request; the service limits this to about 5000.",
        "maxChunks": "Stop after this many requests, to bound how much text is sent.",
        "filename": "Where to write the translation.",
        "allowNetwork": "Permit this plugin to use the network even when config.json says offline.",
    },
    run=run,
)
