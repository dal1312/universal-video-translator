from __future__ import annotations

import queue
import re
import sys
import threading
from collections import deque
from collections.abc import Callable, Iterable
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from .cache import TranslationCache
from .tts import create_speech_engine

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


_WORD = re.compile(r"\w+(?:['’]\w+)*", re.UNICODE)
_END = object()


class LiveCaptureError(RuntimeError):
    pass


def _normalized_words(text: str) -> list[str]:
    return [item.casefold() for item in _WORD.findall(text)]


def is_probable_echo(text: str, spoken_history: list[str]) -> bool:
    words = _normalized_words(text)
    if len(words) < 2:
        return False
    normalized = " ".join(words)
    word_set = set(words)
    for spoken in spoken_history:
        spoken_words = _normalized_words(spoken)
        if not spoken_words:
            continue
        spoken_normalized = " ".join(spoken_words)
        sequence = SequenceMatcher(
            None, normalized, spoken_normalized
        ).ratio()
        overlap = len(word_set.intersection(spoken_words)) / min(
            len(word_set), len(set(spoken_words))
        )
        if sequence >= 0.72 or overlap >= 0.82:
            return True
    return False


def put_latest(target: queue.Queue, item: object) -> None:
    try:
        target.put_nowait(item)
        return
    except queue.Full:
        pass
    try:
        target.get_nowait()
    except queue.Empty:
        pass
    try:
        target.put_nowait(item)
    except queue.Full:
        pass


def initialize_windows_com() -> bool:
    if sys.platform != "win32":
        return False
    import ctypes

    result = ctypes.windll.ole32.CoInitializeEx(None, 0)
    code = result & 0xFFFFFFFF
    if code in {0, 1}:
        return True
    if code == 0x80010106:
        return False
    raise OSError(f"Impossibile inizializzare COM: 0x{code:08X}")


def uninitialize_windows_com() -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.ole32.CoUninitialize()


def capture_device_names() -> list[str]:
    try:
        import soundcard as sc

        return sorted(
            {
                str(device.name)
                for device in sc.all_microphones(include_loopback=True)
                if device.name
            },
            key=str.casefold,
        )
    except Exception as error:
        raise LiveCaptureError("Impossibile rilevare i dispositivi audio.") from error


def preferred_cable_output(devices: Iterable[str]) -> str | None:
    return next(
        (device for device in devices if "cable output" in device.casefold()),
        None,
    )


class LiveTranslator:
    def __init__(
        self,
        translator: OllamaTranslator,
        cache: TranslationCache,
        whisper_model: str = "small",
        source_language: str = "auto",
        rate: int = 185,
        chunk_seconds: float = 4.0,
        speech_engine: str = "kokoro",
        voice: str = "if_sara",
        speak: bool = False,
        capture_device: str | None = None,
        on_text: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.translator = translator
        self.cache = cache
        self.whisper_model = whisper_model
        self.source_language = source_language
        self.rate = rate
        self.chunk_seconds = max(2.0, min(8.0, float(chunk_seconds)))
        self.speech_engine = speech_engine
        self.voice = voice
        self.speak = speak
        self.capture_device = capture_device
        self.on_text = on_text or (lambda _text: None)
        self.on_status = on_status or (lambda _text: None)
        self.on_error = on_error or (lambda _error: None)
        self._stop = threading.Event()
        self._audio_queue: queue.Queue = queue.Queue(maxsize=3)
        self._speech_queue: queue.Queue = queue.Queue(maxsize=4)
        self._spoken_history: deque[str] = deque(maxlen=5)
        self._thread: threading.Thread | None = None
        self._capture_thread: threading.Thread | None = None
        self._speech_thread: threading.Thread | None = None
        self._engine = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._audio_queue = queue.Queue(maxsize=3)
        self._speech_queue = queue.Queue(maxsize=4)
        self._spoken_history.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        put_latest(self._audio_queue, _END)
        put_latest(self._speech_queue, _END)
        if self._engine is not None:
            try:
                self._engine.stop()
            except RuntimeError:
                pass

    def _capture(self, sample_rate: int) -> None:
        com_initialized = False
        try:
            import soundcard as sc

            # SoundCard performs its own first COM initialization at import.
            com_initialized = initialize_windows_com()
            if self.capture_device:
                microphone = next(
                    (
                        device
                        for device in sc.all_microphones(include_loopback=True)
                        if str(device.name).casefold()
                        == self.capture_device.casefold()
                    ),
                    None,
                )
                if microphone is None:
                    raise LiveCaptureError(
                        f"Ingresso audio non trovato: {self.capture_device}"
                    )
            else:
                speaker = sc.default_speaker()
                if speaker is None:
                    raise LiveCaptureError("Nessuna uscita audio predefinita.")
                microphone = sc.get_microphone(
                    id=str(speaker.name), include_loopback=True
                )

            frames = round(sample_rate * self.chunk_seconds)
            with microphone.recorder(samplerate=sample_rate) as recorder:
                self.on_status(f"Overlay OS: ascolto {microphone.name}")
                while not self._stop.is_set():
                    audio = recorder.record(numframes=frames)
                    if self._stop.is_set():
                        return
                    put_latest(self._audio_queue, audio)
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(LiveCaptureError(f"Cattura audio fallita: {exc}"))
                self._stop.set()
                put_latest(self._audio_queue, _END)
        finally:
            if com_initialized:
                uninitialize_windows_com()

    def _speak(self) -> None:
        com_initialized = False
        try:
            if self.speech_engine == "kokoro":
                import soundcard  # noqa: F401
            com_initialized = initialize_windows_com()
            self._engine = create_speech_engine(
                self.speech_engine, self.voice, self.rate
            )
            while not self._stop.is_set():
                item = self._speech_queue.get()
                if item is _END:
                    return
                text = str(item)
                self._spoken_history.append(text)
                self._engine.speak(text)
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(exc)
                self._stop.set()
                put_latest(self._audio_queue, _END)
        finally:
            if self._engine is not None:
                try:
                    self._engine.stop()
                except RuntimeError:
                    pass
                self._engine = None
            if com_initialized:
                uninitialize_windows_com()

    def _run(self) -> None:
        try:
            import numpy as np
            from faster_whisper import WhisperModel

            self.on_status("Overlay OS: caricamento Whisper…")
            whisper = WhisperModel(
                self.whisper_model, device="auto", compute_type="int8"
            )
            if self.speak:
                self.on_status("Overlay OS: caricamento voce…")
                self._speech_thread = threading.Thread(
                    target=self._speak, daemon=True
                )
                self._speech_thread.start()

            sample_rate = 16000
            language_codes = {
                "inglese": "en",
                "spagnolo": "es",
                "francese": "fr",
                "tedesco": "de",
            }
            language = language_codes.get(self.source_language)
            self._capture_thread = threading.Thread(
                target=self._capture,
                args=(sample_rate,),
                daemon=True,
            )
            self._capture_thread.start()

            while not self._stop.is_set():
                audio = self._audio_queue.get()
                if audio is _END:
                    break
                mono = np.asarray(audio, dtype=np.float32)
                if mono.ndim > 1:
                    mono = mono.mean(axis=1)
                if not len(mono) or float(np.max(np.abs(mono))) < 0.005:
                    continue
                segments, _info = whisper.transcribe(
                    mono,
                    language=language,
                    vad_filter=True,
                    condition_on_previous_text=False,
                )
                original = " ".join(
                    segment.text.strip()
                    for segment in segments
                    if segment.text.strip()
                ).strip()
                if (
                    not original
                    or self._stop.is_set()
                    or is_probable_echo(
                        original, list(self._spoken_history)
                    )
                ):
                    continue
                translated = None
                try:
                    translated = self.cache.get(
                        self.translator.model,
                        self.source_language,
                        original,
                    )
                except Exception as exc:
                    self.on_status(f"Cache traduzione non disponibile: {exc}")
                if translated is None:
                    try:
                        if hasattr(self.translator, "translate_many"):
                            translated = self.translator.translate_many(
                                [original], self.source_language
                            )[0]
                        else:
                            translated = self.translator.translate(
                                original, self.source_language
                            )
                    except Exception as exc:
                        self.on_status(f"Fallback originale: {exc}")
                        translated = original
                    else:
                        reported_failures = getattr(
                            self.translator,
                            "last_failed_indices",
                            None,
                        )
                        failed = (
                            bool(reported_failures)
                            if reported_failures is not None
                            else translated == original
                        )
                        if failed:
                            self.on_status(
                                "Segmento non tradotto; uso testo originale"
                            )
                        try:
                            self.cache.put(
                                self.translator.model,
                                self.source_language,
                                original,
                                translated,
                            )
                        except Exception as exc:
                            self.on_status(
                                f"Cache traduzione non aggiornata: {exc}"
                            )
                self.on_text(translated)
                if self.speak:
                    put_latest(self._speech_queue, translated)
            self.on_status("Overlay OS interrotto")
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(exc)
            self.on_status("Errore Overlay OS")
        finally:
            self._stop.set()
            put_latest(self._speech_queue, _END)
