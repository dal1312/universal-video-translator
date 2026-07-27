from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from .cache import TranslationCache

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


class LiveCaptureError(RuntimeError):
    pass


class LiveTranslator:
    def __init__(
        self,
        translator: OllamaTranslator,
        cache: TranslationCache,
        whisper_model: str = "small",
        source_language: str = "auto",
        rate: int = 185,
        chunk_seconds: int = 6,
        on_text: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.translator = translator
        self.cache = cache
        self.whisper_model = whisper_model
        self.source_language = source_language
        self.rate = rate
        self.chunk_seconds = chunk_seconds
        self.on_text = on_text or (lambda _text: None)
        self.on_status = on_status or (lambda _text: None)
        self.on_error = on_error or (lambda _error: None)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            import numpy as np
            import pyttsx3
            import soundcard as sc
            from faster_whisper import WhisperModel

            speaker = sc.default_speaker()
            if speaker is None:
                raise LiveCaptureError("Nessuna uscita audio predefinita.")
            microphone = sc.get_microphone(
                id=str(speaker.name), include_loopback=True
            )
            whisper = WhisperModel(
                self.whisper_model, device="auto", compute_type="int8"
            )
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            sample_rate = 16000
            language_codes = {
                "inglese": "en",
                "spagnolo": "es",
                "francese": "fr",
                "tedesco": "de",
            }
            language = language_codes.get(self.source_language)
            self.on_status("Live: ascolto audio di sistema")

            with microphone.recorder(samplerate=sample_rate) as recorder:
                while not self._stop.is_set():
                    audio = recorder.record(
                        numframes=sample_rate * self.chunk_seconds
                    )
                    mono = np.asarray(audio, dtype=np.float32)
                    if mono.ndim > 1:
                        mono = mono.mean(axis=1)
                    if float(np.max(np.abs(mono))) < 0.005:
                        continue
                    segments, _info = whisper.transcribe(
                        mono, language=language, vad_filter=True
                    )
                    original = " ".join(
                        segment.text.strip()
                        for segment in segments
                        if segment.text.strip()
                    ).strip()
                    if not original or self._stop.is_set():
                        continue
                    translated = self.cache.get(
                        self.translator.model, self.source_language, original
                    )
                    if translated is None:
                        translated = self.translator.translate(
                            original, self.source_language
                        )
                        self.cache.put(
                            self.translator.model,
                            self.source_language,
                            original,
                            translated,
                        )
                    self.on_text(translated)
                    engine.say(translated)
                    engine.runAndWait()
            self.on_status("Live interrotto")
        except Exception as exc:
            self.on_error(exc)
            self.on_status("Errore live")
