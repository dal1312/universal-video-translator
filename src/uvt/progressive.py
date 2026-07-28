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
from .subtitles import Cue
from .tts import create_speech_engine

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


SAMPLE_RATE = 24000
CHUNK_SECONDS = 15
INITIAL_BUFFER_SECONDS = 30
TRANSLATION_BATCH_SIZE = 12
VOICE_GAP_SECONDS = 0.08
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
        self.on_text = on_text or (lambda _text: None)
        self.on_status = on_status or (lambda _status: None)
        self.on_error = on_error or (lambda _error: None)

        self._stop = threading.Event()
        self._pause = threading.Event()
        self._queue: queue.Queue = queue.Queue(maxsize=4)
        self._initial: list[object] = []
        self._translations: dict[str, str] = {}
        self._engine = None
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
        self._engine = create_speech_engine(
            self.speech_engine, self.voice, self.rate
        )
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
        if self._engine is None:
            self.prepare()
        for chunk in self._initial:
            self._queue.put(chunk)
        self._initial.clear()
        self._stream = self.preview.open_pcm_stream(self.media, SAMPLE_RATE)
        self._writer = threading.Thread(target=self._write_audio, daemon=True)
        self._producer = threading.Thread(target=self._produce, daemon=True)
        self._text_thread = threading.Thread(target=self._show_text, daemon=True)
        self._monitor = threading.Thread(target=self._monitor_player, daemon=True)
        self._writer.start()
        self._producer.start()
        self._text_thread.start()
        self._monitor.start()
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

    def stop(self) -> None:
        self._stop.set()
        self._pause.clear()
        self.preview.stop()
        if self._engine is not None:
            try:
                self._engine.stop()
            except RuntimeError:
                pass
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

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
            translated = self.cache.get(
                self.translator.model, self.source_language, cue.text
            )
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
            if len(translations) != len(texts):
                raise RuntimeError("Ollama ha saltato alcune traduzioni.")
            self._translations.update(zip(texts, translations))
            self.cache.put_many(
                [
                    (
                        self.translator.model,
                        self.source_language,
                        text,
                        translated,
                    )
                    for text, translated in zip(texts, translations)
                ]
            )

    def _render(self, text: str, index: int):
        import numpy as np

        if hasattr(self._engine, "render"):
            audio, samplerate = self._engine.render(text)
            samples = np.asarray(audio, dtype=np.float32)
        else:
            import soundfile as sf

            destination = Path(self._temporary.name) / f"cue-{index:06d}.wav"
            self._engine.save(text, destination)
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
        return samples

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
            audio = self._render(self._translations[cue.text], index)
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
