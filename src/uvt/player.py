from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from .cache import TranslationCache
from .subtitles import Cue
from .tts import create_speech_engine

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


class SubtitlePlayer:
    def __init__(
        self,
        cues: list[Cue],
        translator: OllamaTranslator,
        cache: TranslationCache,
        source_language: str = "auto",
        rate: int = 185,
        speech_engine: str = "windows",
        voice: str = "default",
        sync: bool = True,
        on_text: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.cues = cues
        self.translator = translator
        self.cache = cache
        self.source_language = source_language
        self.rate = rate
        self.speech_engine = speech_engine
        self.voice = voice
        self.sync = sync
        self.on_text = on_text or (lambda _text: None)
        self.on_status = on_status or (lambda _status: None)
        self.on_error = on_error or (lambda _error: None)
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: threading.Thread | None = None
        self._engine = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._pause.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _translate(self, text: str, position: int | None = None) -> str:
        try:
            translated = self.cache.get(
                self.translator.model, self.source_language, text
            )
            if translated is None:
                translated = self.translator.translate(text, self.source_language)
                self.cache.put(
                    self.translator.model,
                    self.source_language,
                    text,
                    translated,
            )
            return translated
        except Exception as exc:
            if position is not None:
                self.on_status(
                    f"Fallback originale per battuta {position}: {exc!s}"
                )
            return text

    def prepare(self) -> None:
        if self._engine is None:
            self.on_status("Caricamento motore voce…")
            self._engine = create_speech_engine(
                self.speech_engine, self.voice, self.rate
            )
        total = len(self.cues)
        first_translation: str | None = None
        for position, cue in enumerate(self.cues, start=1):
            if self._stop.is_set():
                return
            translated = self._translate(cue.text, position)
            self.on_status(f"Pretraduzione {position}/{total}")
            if first_translation is None:
                first_translation = translated
        if first_translation and hasattr(self._engine, "prewarm"):
            self.on_status("Preparazione prima battuta…")
            self._engine.prewarm(first_translation)
        self.on_status("Pronto alla riproduzione")

    def toggle_pause(self) -> bool:
        if self._pause.is_set():
            self._pause.clear()
            self.on_status("Riproduzione")
        else:
            self._pause.set()
            self.on_status("In pausa")
        return self._pause.is_set()

    def stop(self) -> None:
        self._stop.set()
        self._pause.clear()
        if self._engine is not None:
            try:
                self._engine.stop()
            except RuntimeError:
                pass

    def _wait_until(self, deadline: float) -> bool:
        while not self._stop.is_set():
            if self._pause.is_set():
                paused_at = time.monotonic()
                while self._pause.is_set() and not self._stop.wait(0.05):
                    pass
                deadline += time.monotonic() - paused_at
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            self._stop.wait(min(remaining, 0.05))
        return False

    def _run(self) -> None:
        try:
            if self._engine is None:
                self._engine = create_speech_engine(
                    self.speech_engine, self.voice, self.rate
                )
            started = time.monotonic()
            self.on_status("Riproduzione")

            for position, cue in enumerate(self.cues, start=1):
                if self.sync and not self._wait_until(started + cue.start):
                    break
                if self._stop.is_set():
                    break
                translated = self._translate(cue.text, position)
                self.on_text(translated)
                self.on_status(f"Battuta {position}/{len(self.cues)}")
                self._engine.speak(translated)

            self.on_status("Interrotto" if self._stop.is_set() else "Completato")
        except Exception as exc:
            self.on_error(exc)
            self.on_status("Errore")
        finally:
            self._engine = None
