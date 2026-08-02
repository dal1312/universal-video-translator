from __future__ import annotations

import queue
import re
import sys
import threading
import time
import warnings
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from .cache import TranslationCache
from .adaptive_sync import AdaptiveSyncController
from .latency import LatencyTracker
from .profiles import PerformanceProfile, profile_by_key
from .runtime import RuntimeSupervisor
from .tts import create_speech_engine
from .vad import SpeechSegmenter

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


_WORD = re.compile(r"\w+(?:['’]\w+)*", re.UNICODE)
_END = object()


@dataclass(frozen=True, slots=True)
class _AudioPacket:
    samples: object
    duration_seconds: float
    ready_at: float


@dataclass(frozen=True, slots=True)
class _SpeechItem:
    text: str
    queued_at: float
    source_duration_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class _TranscriptionItem:
    text: str
    capture_ms: float
    queue_ms: float
    transcribe_ms: float


class LiveCaptureError(RuntimeError):
    pass


def _normalized_words(text: str) -> list[str]:
    return [item.casefold() for item in _WORD.findall(text)]


def compact_speech_text(text: str, max_words: int) -> str:
    """Shorten delayed speech without another model call."""
    words = text.split()
    if len(words) <= max_words:
        return text
    first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    sentence_words = first_sentence.split()
    selected = sentence_words if len(sentence_words) <= max_words else words
    return " ".join(selected[:max_words]).rstrip(" ,;:-") + "…"


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
        chunk_seconds: float | None = None,
        profile: str = "rapido",
        speech_engine: str = "kokoro",
        voice: str = "if_sara",
        speak: bool = False,
        capture_device: str | None = None,
        on_text: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_metrics: Callable[[dict[str, float | int]], None] | None = None,
        volume_ducker=None,
    ) -> None:
        self.translator = translator
        self.cache = cache
        self.whisper_model = whisper_model
        self.source_language = source_language
        self.profile: PerformanceProfile = profile_by_key(profile)
        self.rate = round(rate * self.profile.speech_rate_multiplier)
        self._adaptive_sync = AdaptiveSyncController(self.rate)
        selected_chunk = (
            self.profile.max_segment_seconds
            if chunk_seconds is None
            else float(chunk_seconds)
        )
        self.chunk_seconds = max(1.5, min(8.0, selected_chunk))
        self.speech_engine = speech_engine
        self.voice = voice
        self.speak = speak
        self.capture_device = capture_device
        self.on_text = on_text or (lambda _text: None)
        self.on_status = on_status or (lambda _text: None)
        self.on_error = on_error or (lambda _error: None)
        self.on_metrics = on_metrics or (lambda _metrics: None)
        self.volume_ducker = volume_ducker
        self.latency = LatencyTracker()
        self._stop = threading.Event()
        self._audio_queue: queue.Queue = queue.Queue(
            maxsize=self.profile.audio_queue_size
        )
        self._speech_queue: queue.Queue = queue.Queue(
            maxsize=self.profile.speech_queue_size
        )
        self._translation_queue: queue.Queue = queue.Queue(
            maxsize=self.profile.audio_queue_size
        )
        self._spoken_history: deque[str] = deque(maxlen=5)
        self._thread: threading.Thread | None = None
        self._capture_thread: threading.Thread | None = None
        self._speech_thread: threading.Thread | None = None
        self._translation_thread: threading.Thread | None = None
        self._warmup_thread: threading.Thread | None = None
        self._warmup_complete = threading.Event()
        self._engine = None
        self._runtime = RuntimeSupervisor()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._audio_queue = queue.Queue(maxsize=self.profile.audio_queue_size)
        self._speech_queue = queue.Queue(maxsize=self.profile.speech_queue_size)
        self._translation_queue = queue.Queue(maxsize=self.profile.audio_queue_size)
        self._spoken_history.clear()
        self._adaptive_sync = AdaptiveSyncController(self.rate)
        self._warmup_complete.clear()
        if self._runtime.closing:
            self._runtime = RuntimeSupervisor()
        self._thread = self._runtime.start(self._run, name="uvt-live-main")

    def stop(self, timeout: float | None = None) -> bool:
        self._stop.set()
        self._runtime.begin_shutdown()
        put_latest(self._audio_queue, _END)
        put_latest(self._speech_queue, _END)
        put_latest(self._translation_queue, _END)
        if self._engine is not None:
            try:
                self._engine.stop()
            except RuntimeError:
                pass
        deadline = None
        if timeout is not None:
            deadline = time.monotonic() + max(0.0, timeout)
        elif self._thread is not None:
            deadline = time.monotonic() + self.chunk_seconds + 1.0
        current = threading.current_thread()
        threads = (
            self._capture_thread,
            self._speech_thread,
            self._translation_thread,
            self._warmup_thread,
            self._thread,
        )
        for thread in threads:
            if thread is None or thread is current:
                continue
            remaining = max(0.0, deadline - time.monotonic()) if deadline else None
            thread.join(remaining)
        stopped = all(
            thread is None or thread is current or not thread.is_alive()
            for thread in threads
        )
        if stopped:
            self._capture_thread = None
            self._speech_thread = None
            self._translation_thread = None
            self._warmup_thread = None
            self._thread = None
        return stopped

    def _warmup_translator(self) -> None:
        try:
            warmup = getattr(self.translator, "warmup", None)
            if warmup is not None:
                warmup()
        except Exception as exc:
            self.on_status(f"Warm-up traduzione non disponibile: {exc}")
        finally:
            self._warmup_complete.set()

    def _capture(self, sample_rate: int) -> None:
        com_initialized = False
        try:
            import soundcard as sc

            warning_category = getattr(sc, "SoundcardRuntimeWarning", None)
            if (
                isinstance(warning_category, type)
                and issubclass(warning_category, Warning)
            ):
                warnings.filterwarnings(
                    "ignore",
                    message="data discontinuity in recording",
                    category=warning_category,
                )

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

            frames = round(sample_rate * self.profile.frame_seconds)
            segmenter = SpeechSegmenter(
                sample_rate,
                silence_seconds=self.profile.silence_seconds,
                min_speech_seconds=self.profile.min_speech_seconds,
                max_segment_seconds=self.chunk_seconds,
                energy_threshold=self.profile.energy_threshold,
            )
            with microphone.recorder(samplerate=sample_rate) as recorder:
                self.on_status(
                    f"Overlay OS: ascolto {microphone.name} · "
                    f"profilo {self.profile.label}"
                )
                while not self._stop.is_set():
                    frame = recorder.record(numframes=frames)
                    if self._stop.is_set():
                        break
                    chunk = segmenter.push(frame)
                    if chunk is not None:
                        put_latest(
                            self._audio_queue,
                            _AudioPacket(
                                chunk.samples,
                                chunk.duration_seconds,
                                time.monotonic(),
                            ),
                        )
                trailing = segmenter.flush()
                if trailing is not None:
                    put_latest(
                        self._audio_queue,
                        _AudioPacket(
                            trailing.samples,
                            trailing.duration_seconds,
                            time.monotonic(),
                        ),
                    )
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(LiveCaptureError(f"Cattura audio fallita: {exc}"))
                self._stop.set()
                put_latest(self._audio_queue, _END)
        finally:
            if com_initialized:
                uninitialize_windows_com()

    def _translate_stream(self) -> None:
        try:
            while True:
                item = self._translation_queue.get()
                if item is _END:
                    return
                if not isinstance(item, _TranscriptionItem):
                    continue
                original = item.text
                translated = None
                translate_started = time.monotonic()
                if not self._warmup_complete.is_set():
                    self.on_status("Overlay OS: preparazione traduzione…")
                    self._warmup_complete.wait(timeout=60.0)
                try:
                    translated = self.cache.get(
                        getattr(self.translator, "cache_key", self.translator.model),
                        self.source_language,
                        original,
                    )
                except Exception as exc:
                    self.on_status(f"Cache traduzione non disponibile: {exc}")
                if translated is None:
                    try:
                        if (
                            self.profile.key == "rapido"
                            and hasattr(self.translator, "translate_realtime")
                        ):
                            translated = self.translator.translate_realtime(
                                original, self.source_language
                            )
                        elif hasattr(self.translator, "translate_many"):
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
                        failures = getattr(self.translator, "last_failed_indices", None)
                        failed = bool(failures) if failures is not None else translated == original
                        if failed:
                            self.on_status("Segmento non tradotto; uso testo originale")
                        try:
                            self.cache.put(
                                getattr(self.translator, "cache_key", self.translator.model),
                                self.source_language,
                                original,
                                translated,
                            )
                        except Exception as exc:
                            self.on_status(f"Cache traduzione non aggiornata: {exc}")
                translate_ms = (time.monotonic() - translate_started) * 1000
                self.on_text(translated)
                total_ms = item.capture_ms + item.queue_ms + item.transcribe_ms + translate_ms
                self.on_metrics(
                    self.latency.record(
                        capture_ms=item.capture_ms,
                        transcribe_ms=item.transcribe_ms,
                        translate_ms=translate_ms,
                        queue_ms=item.queue_ms,
                        total_ms=total_ms,
                    )
                )
                if self.speak:
                    put_latest(
                        self._speech_queue,
                        _SpeechItem(translated, time.monotonic(), item.capture_ms / 1000),
                    )
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(exc)
                self._stop.set()
                put_latest(self._audio_queue, _END)

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
                speech_item = (
                    item
                    if isinstance(item, _SpeechItem)
                    else _SpeechItem(str(item), time.monotonic())
                )
                text = speech_item.text
                queue_ms = (time.monotonic() - speech_item.queued_at) * 1000
                compressed = False
                if queue_ms > 1800:
                    word_budget = max(
                        6,
                        round(speech_item.source_duration_seconds * 3.0),
                    )
                    compacted = compact_speech_text(text, word_budget)
                    compressed = compacted != text
                    text = compacted
                self._spoken_history.append(text)
                adaptive_rate = self._adaptive_sync.next_rate(
                    queue_ms=queue_ms,
                    text=text,
                    source_duration_seconds=speech_item.source_duration_seconds,
                )
                set_rate = getattr(self._engine, "set_rate", None)
                if set_rate is not None:
                    set_rate(adaptive_rate)
                self.on_metrics(
                    {
                        "speech_queue_ms": round(queue_ms, 1),
                        "adaptive_rate": adaptive_rate,
                        "adaptive_speed": round(
                            self._adaptive_sync.multiplier, 2
                        ),
                        "speech_compressed": int(compressed),
                    }
                )
                ducked = bool(
                    self.volume_ducker and self.volume_ducker.duck()
                )
                try:
                    speech_started = time.monotonic()
                    self._engine.speak(text)
                    speech_ms = (time.monotonic() - speech_started) * 1000
                    self.on_metrics(
                        {
                            "speech_ms": round(speech_ms, 1),
                            "sync_offset_ms": round(
                                self._adaptive_sync.offset_ms(
                                    queue_ms=queue_ms,
                                    speech_ms=speech_ms,
                                    source_duration_seconds=(
                                        speech_item.source_duration_seconds
                                    ),
                                ),
                                1,
                            ),
                        }
                    )
                finally:
                    if ducked:
                        self.volume_ducker.restore()
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

            self._warmup_thread = self._runtime.start(
                self._warmup_translator,
                name="uvt-live-translation-warmup",
            )
            if self.speak:
                self.on_status("Overlay OS: caricamento voce…")
                self._speech_thread = self._runtime.start(
                    self._speak,
                    name="uvt-live-speech",
                )
            self.on_status("Overlay OS: caricamento Whisper…")
            model_name = self.whisper_model or self.profile.whisper_model
            whisper = WhisperModel(
                model_name, device="auto", compute_type="int8"
            )

            sample_rate = 16000
            language_codes = {
                "inglese": "en",
                "spagnolo": "es",
                "francese": "fr",
                "tedesco": "de",
            }
            language = language_codes.get(self.source_language)
            self._capture_thread = self._runtime.start(
                self._capture,
                sample_rate,
                name="uvt-live-capture",
            )
            self._translation_thread = self._runtime.start(
                self._translate_stream,
                name="uvt-live-translation",
            )
            dropped_segments = 0

            while not self._stop.is_set():
                audio = self._audio_queue.get()
                if audio is _END:
                    break
                if isinstance(audio, _AudioPacket):
                    samples = audio.samples
                    capture_ms = audio.duration_seconds * 1000
                    queue_ms = (time.monotonic() - audio.ready_at) * 1000
                    if queue_ms > self.profile.max_queue_delay_seconds * 1000:
                        dropped_segments += 1
                        self.on_metrics(
                            {
                                "queue_ms": round(queue_ms, 1),
                                "dropped_segments": dropped_segments,
                            }
                        )
                        self.on_status(
                            "Overlay OS: recupero ritardo, segmento vecchio scartato"
                        )
                        continue
                else:
                    samples = audio
                    capture_ms = 0.0
                    queue_ms = 0.0
                mono = np.asarray(samples, dtype=np.float32)
                if mono.ndim > 1:
                    mono = mono.mean(axis=1)
                if not len(mono) or float(np.max(np.abs(mono))) < 0.005:
                    continue
                transcribe_started = time.monotonic()
                segments, _info = whisper.transcribe(
                    mono,
                    language=language,
                    vad_filter=True,
                    condition_on_previous_text=False,
                    beam_size=self.profile.beam_size,
                    best_of=1,
                )
                transcribe_ms = (time.monotonic() - transcribe_started) * 1000
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
                put_latest(
                    self._translation_queue,
                    _TranscriptionItem(original, capture_ms, queue_ms, transcribe_ms),
                )
            self._translation_queue.put(_END)
            if self._translation_thread is not None:
                self._translation_thread.join(timeout=60.0)
            self.on_status("Overlay OS interrotto")
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(exc)
            self.on_status("Errore Overlay OS")
        finally:
            self._stop.set()
            put_latest(self._translation_queue, _END)
            put_latest(self._speech_queue, _END)
