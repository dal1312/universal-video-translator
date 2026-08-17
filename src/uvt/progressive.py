from __future__ import annotations

import math
import queue
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .cache import TranslationCache
from .media_player import MediaPreview
from .runtime import RuntimeSupervisor
from .subtitles import Cue
from .tts import create_speech_engine

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


SAMPLE_RATE = 24000
CHUNK_SECONDS = 15
INITIAL_BUFFER_SECONDS = 30
TRANSLATION_BATCH_SIZE = 12
VOICE_GAP_SECONDS = 0.08
MIN_VOICE_SLOT_SECONDS = 0.25
_END = object()


class ProgressiveDubPlayer:
    def __init__(
        self,
        media: str | Path,
        cues: list[Cue],
        preview: MediaPreview,
        translator: OllamaTranslator,
        cache: TranslationCache,
        source_language: str = "auto",
        rate: int = 185,
        speech_engine: str = "kokoro",
        voice: str = "if_sara",
        speaker_voices: tuple[str, ...] = (),
        on_text: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.media = Path(media)
        self.cues = sorted(cues, key=lambda cue: cue.start)
        self.preview = preview
        self.translator = translator
        self.cache = cache
        self.source_language = source_language
        self.rate = rate
        self.speech_engine = speech_engine
        self.voice = voice
        self.speaker_voices = speaker_voices
        self.on_text = on_text or (lambda _text: None)
        self.on_status = on_status or (lambda _status: None)
        self.on_error = on_error or (lambda _error: None)

        self._stop = threading.Event()
        self._pause = threading.Event()
        self._queue: queue.Queue = queue.Queue(maxsize=4)
        self._initial: list[object] = []
        self._translations: dict[str, str] = {}
        self._engine = None
        self._engines: dict[str, object] = {}
        self._speaker_order: dict[str, int] = {}
        self._temporary: tempfile.TemporaryDirectory | None = None
        self._cue_index = 0
        self._chunk_start = 0.0
        self._voice_cursor_samples = 0
        self._carry = None
        self._stream = None
        self._producer: threading.Thread | None = None
        self._writer: threading.Thread | None = None
        self._text_thread: threading.Thread | None = None
        self._monitor: threading.Thread | None = None
        self._runtime = RuntimeSupervisor()

    @property
    def running(self) -> bool:
        return bool(self._monitor and self._monitor.is_alive())

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    def _has_more(self) -> bool:
        carry_size = 0 if self._carry is None else len(self._carry)
        return self._cue_index < len(self.cues) or carry_size > 0

    def prepare(self) -> None:
        import numpy as np

        self._stop.clear()
        self._pause.clear()
        self._temporary = tempfile.TemporaryDirectory(prefix="uvt-buffer-")
        self.on_status("Caricamento motore voce…")
        self._engine = self._engine_for(None)
        self._voice_cursor_samples = 0
        self._carry = np.zeros(0, dtype=np.float32)
        required = math.ceil(INITIAL_BUFFER_SECONDS / CHUNK_SECONDS)
        for index in range(required):
            if not self._has_more():
                break
            self._initial.append(self._build_next_chunk())
            buffered = min((index + 1) * CHUNK_SECONDS, INITIAL_BUFFER_SECONDS)
            self.on_status(
                f"Buffer iniziale {buffered}/{INITIAL_BUFFER_SECONDS} secondi"
            )
        self.on_status("Buffer pronto")

    def start(self) -> None:
        if self.running:
            return
        if self._runtime.closing:
            self._runtime = RuntimeSupervisor()
        if self._engine is None:
            self.prepare()
        for chunk in self._initial:
            self._queue.put(chunk)
        self._initial.clear()
        self._stream = self.preview.open_pcm_stream(self.media, SAMPLE_RATE)
        self._writer = self._runtime.start(
            self._write_audio, name="uvt-progressive-writer"
        )
        self._producer = self._runtime.start(
            self._produce, name="uvt-progressive-producer"
        )
        self._text_thread = self._runtime.start(
            self._show_text, name="uvt-progressive-text"
        )
        self._monitor = self._runtime.start(
            self._monitor_player, name="uvt-progressive-monitor"
        )
        self.on_status("Riproduzione con buffer")

    def toggle_pause(self) -> bool:
        if self._pause.is_set():
            self._pause.clear()
            self.preview.toggle_pause()
            self.on_status("Riproduzione con buffer")
        else:
            self._pause.set()
            self.preview.toggle_pause()
            self.on_status("In pausa")
        return self._pause.is_set()

    def stop(self, timeout: float = 3.0) -> bool:
        self._stop.set()
        self._pause.clear()
        self._runtime.begin_shutdown()
        try:
            self._queue.put_nowait(_END)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(_END)
            except queue.Full:
                pass
        self.preview.stop()
        if self._engine is not None:
            try:
                self._engine.stop()
            except RuntimeError:
                pass
        for engine in self._engines.values():
            if engine is self._engine:
                continue
            try:
                engine.stop()
            except (AttributeError, RuntimeError):
                pass
        deadline = time.monotonic() + max(0.0, timeout)
        current = threading.current_thread()
        threads = (
            self._producer,
            self._writer,
            self._text_thread,
            self._monitor,
        )
        for thread in threads:
            if thread is None or thread is current:
                continue
            thread.join(max(0.0, deadline - time.monotonic()))
        stopped = all(
            thread is None or thread is current or not thread.is_alive()
            for thread in threads
        )
        if stopped and self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
        if stopped:
            self._producer = None
            self._writer = None
            self._text_thread = None
            self._monitor = None
        return stopped

    def _put(self, item: object) -> bool:
        while not self._stop.is_set():
            try:
                self._queue.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def _produce(self) -> None:
        try:
            while not self._stop.is_set() and self._has_more():
                if not self._put(self._build_next_chunk()):
                    return
            self._put(_END)
        except Exception as exc:
            self.on_error(exc)
            self._stop.set()
            self.preview.stop()

    def _write_audio(self) -> None:
        try:
            while not self._stop.is_set():
                item = self._queue.get()
                if item is _END:
                    break
                data = item.astype("<f4", copy=False).tobytes()
                view = memoryview(data)
                while view and not self._stop.is_set():
                    written = self._stream.write(view)
                    if not written:
                        raise BrokenPipeError("Player audio chiuso.")
                    view = view[written:]
            if self._stream is not None:
                self._stream.close()
        except (BrokenPipeError, OSError):
            if not self._stop.is_set():
                self._stop.set()

    def _monitor_player(self) -> None:
        self.preview.wait()
        self.on_status("Interrotto" if self._stop.is_set() else "Completato")

    def _show_text(self) -> None:
        started = time.monotonic()
        pause_total = 0.0
        for cue in self.cues:
            while not self._stop.is_set():
                if self._pause.is_set():
                    paused_at = time.monotonic()
                    while self._pause.is_set() and not self._stop.wait(0.05):
                        pass
                    pause_total += time.monotonic() - paused_at
                remaining = cue.start - (
                    time.monotonic() - started - pause_total
                )
                if remaining <= 0:
                    break
                self._stop.wait(min(remaining, 0.05))
            if self._stop.is_set():
                return
            translated = self._translations.get(cue.text)
            if translated:
                self.on_text(translated)

    def _translate_cues(self, cues: list[Cue]) -> None:
        missing: list[str] = []
        seen: set[str] = set()
        for cue in cues:
            if cue.text in self._translations or cue.text in seen:
                continue
            try:
                translated = self.cache.get(
                    getattr(self.translator, "cache_key", self.translator.model),
                    self.source_language,
                    cue.text,
                )
            except Exception as exc:
                translated = None
                self.on_status(f"Cache traduzione non disponibile: {exc!s}")
            if translated is not None:
                self._translations[cue.text] = translated
            else:
                missing.append(cue.text)
                seen.add(cue.text)

        for offset in range(0, len(missing), TRANSLATION_BATCH_SIZE):
            texts = missing[offset : offset + TRANSLATION_BATCH_SIZE]
            translations = self.translator.translate_many(
                texts, self.source_language
            )
            if len(translations) < len(texts):
                translations.extend(texts[len(translations) :])
            elif len(translations) > len(texts):
                translations = translations[: len(texts)]
            self._translations.update(zip(texts, translations))
            reported_failures = getattr(
                self.translator, "last_failed_indices", None
            )
            failed = (
                set(reported_failures)
                if reported_failures is not None
                else {
                    index
                    for index, (text, translated) in enumerate(
                        zip(texts, translations)
                    )
                    if translated == text
                }
            )
            if failed:
                self.on_status(
                    f"{len(failed)} segmenti non tradotti; uso testo originale"
                )
            cacheable = [
                (text, translated)
                for text, translated in zip(texts, translations)
                if translated != text
            ]
            try:
                self.cache.put_many(
                    [
                        (
                            getattr(
                                self.translator,
                                "cache_key",
                                self.translator.model,
                            ),
                            self.source_language,
                            text,
                            translated,
                        )
                        for text, translated in cacheable
                    ]
                )
            except Exception as exc:
                self.on_status(f"Cache traduzione non aggiornata: {exc!s}")

    def _engine_for(self, cue: Cue | None):
        selected = self.voice
        if cue is not None and cue.speaker:
            index = self._speaker_order.setdefault(
                cue.speaker, len(self._speaker_order)
            )
            if index < len(self.speaker_voices) and self.speaker_voices[index].strip():
                selected = self.speaker_voices[index].strip()
        if selected not in self._engines:
            self._engines[selected] = create_speech_engine(
                self.speech_engine, selected, self.rate
            )
        return self._engines[selected]

    def _render(self, text: str, index: int, max_duration: float, cue: Cue):
        import numpy as np

        engine = self._engine_for(cue)
        if hasattr(engine, "render_to_duration"):
            audio, samplerate = engine.render_to_duration(
                text, max_duration
            )
            samples = np.asarray(audio, dtype=np.float32)
        elif hasattr(engine, "render"):
            audio, samplerate = engine.render(text)
            samples = np.asarray(audio, dtype=np.float32)
        else:
            import soundfile as sf

            destination = Path(self._temporary.name) / f"cue-{index:06d}.wav"
            engine.save(text, destination)
            samples, samplerate = sf.read(
                destination, dtype="float32", always_2d=False
            )
            samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        if samplerate != SAMPLE_RATE and len(samples):
            target_size = round(len(samples) * SAMPLE_RATE / samplerate)
            positions = np.linspace(0, len(samples) - 1, target_size)
            samples = np.interp(
                positions, np.arange(len(samples)), samples
            ).astype(np.float32)
        maximum_samples = max(1, round(max_duration * SAMPLE_RATE))
        if len(samples) > maximum_samples:
            positions = np.linspace(0, len(samples) - 1, maximum_samples)
            samples = np.interp(
                positions, np.arange(len(samples)), samples
            ).astype(np.float32)
        return samples

    def _voice_slot(self, index: int, cue: Cue) -> float:
        end = cue.end
        if index + 1 < len(self.cues):
            end = min(end, self.cues[index + 1].start - VOICE_GAP_SECONDS)
        return max(MIN_VOICE_SLOT_SECONDS, end - cue.start)

    def _build_next_chunk(self):
        import numpy as np

        chunk_samples = CHUNK_SECONDS * SAMPLE_RATE
        chunk_start_sample = round(self._chunk_start * SAMPLE_RATE)
        chunk_end_sample = chunk_start_sample + chunk_samples
        chunk = np.zeros(chunk_samples, dtype=np.float32)
        if len(self._carry):
            copied = min(len(self._carry), chunk_samples)
            chunk[:copied] += self._carry[:copied]
            self._carry = self._carry[copied:].copy()

        chunk_end = self._chunk_start + CHUNK_SECONDS
        selected: list[tuple[int, Cue]] = []
        while (
            self._cue_index < len(self.cues)
            and self.cues[self._cue_index].start < chunk_end
        ):
            selected.append((self._cue_index, self.cues[self._cue_index]))
            self._cue_index += 1
        self._translate_cues([cue for _index, cue in selected])

        for index, cue in selected:
            audio = self._render(
                self._translations[cue.text],
                index,
                self._voice_slot(index, cue),
                cue,
            )
            cue_start_sample = max(0, round(cue.start * SAMPLE_RATE))
            gap_samples = (
                round(VOICE_GAP_SECONDS * SAMPLE_RATE)
                if self._voice_cursor_samples
                else 0
            )
            speech_start_sample = max(
                cue_start_sample,
                self._voice_cursor_samples + gap_samples,
            )
            self._voice_cursor_samples = speech_start_sample + len(audio)

            offset = speech_start_sample - chunk_start_sample
            audio_offset = 0
            if offset < 0:
                audio_offset = min(len(audio), -offset)
                offset = 0
            available = max(0, chunk_samples - offset)
            copied = min(len(audio) - audio_offset, available)
            if copied:
                chunk[offset : offset + copied] += audio[
                    audio_offset : audio_offset + copied
                ]
            remainder_start = audio_offset + copied
            remainder = audio[remainder_start:]
            if len(remainder):
                remainder_absolute = speech_start_sample + remainder_start
                carry_offset = max(0, remainder_absolute - chunk_end_sample)
                required = carry_offset + len(remainder)
                if len(self._carry) < required:
                    self._carry = np.pad(
                        self._carry, (0, required - len(self._carry))
                    )
                self._carry[
                    carry_offset : carry_offset + len(remainder)
                ] += remainder

        np.clip(chunk, -1.0, 1.0, out=chunk)
        self._chunk_start = chunk_end
        return chunk
