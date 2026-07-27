from __future__ import annotations

import argparse
import sys
import time

from .cache import TranslationCache
from .ollama import OllamaError, OllamaTranslator
from .subtitles import load_subtitles


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Traduce sottotitoli e li legge in italiano."
    )
    parser.add_argument("subtitles", help="File .srt o .vtt")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--source-language", default="auto")
    parser.add_argument("--rate", type=int, default=185)
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--show-text", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        import pyttsx3

        cues = load_subtitles(args.subtitles)
        if not cues:
            raise ValueError("Il file non contiene sottotitoli validi.")

        engine = pyttsx3.init()
        engine.setProperty("rate", args.rate)
        translator = OllamaTranslator(model=args.model)
        cache = TranslationCache()
        started = time.monotonic()

        for cue in cues:
            if not args.no_sync:
                delay = cue.start - (time.monotonic() - started)
                if delay > 0:
                    time.sleep(delay)
            translated = cache.get(args.model, args.source_language, cue.text)
            if translated is None:
                translated = translator.translate(cue.text, args.source_language)
                cache.put(args.model, args.source_language, cue.text, translated)
            if args.show_text:
                print(translated, flush=True)
            engine.say(translated)
            engine.runAndWait()
        return 0
    except (OSError, ValueError, OllamaError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
