from __future__ import annotations

import argparse
import sys
import time

from .cache import TranslationCache
from .ollama import OllamaError
from .subtitles import load_subtitles
from .translation import ArgosError, create_translator
from .tts import create_speech_engine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Traduce sottotitoli e li legge in italiano."
    )
    parser.add_argument("subtitles", help="File .srt o .vtt")
    parser.add_argument("--model", default="translategemma:latest")
    parser.add_argument("--source-language", default="auto")
    parser.add_argument("--rate", type=int, default=185)
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--show-text", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cues = load_subtitles(args.subtitles)
        if not cues:
            raise ValueError("Il file non contiene sottotitoli validi.")

        engine = create_speech_engine(
            engine="kokoro", voice="Sara (Kokoro, donna)", rate=args.rate
        )
        translator = create_translator(args.model)
        cache = TranslationCache()
        started = time.monotonic()

        for cue in cues:
            if not args.no_sync:
                delay = cue.start - (time.monotonic() - started)
                if delay > 0:
                    time.sleep(delay)
            try:
                translated = cache.get(
                    args.model, args.source_language, cue.text
                )
            except OSError:
                translated = None
            if translated is None:
                translated = translator.translate_many(
                    [cue.text], args.source_language
                )[0]
                if translator.last_failed_indices:
                    print(
                        "Avviso: segmento non tradotto; uso testo originale.",
                        file=sys.stderr,
                    )
                else:
                    try:
                        cache.put(
                            args.model,
                            args.source_language,
                            cue.text,
                            translated,
                        )
                    except OSError:
                        pass
            if args.show_text:
                print(translated, flush=True)
            engine.speak(translated)
        return 0
    except (OSError, RuntimeError, ValueError, OllamaError, ArgosError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
