from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SpeechChunk:
    samples: Any
    duration_seconds: float


class SpeechSegmenter:
    def __init__(
        self,
        sample_rate: int,
        *,
        silence_seconds: float,
        min_speech_seconds: float,
        max_segment_seconds: float,
        energy_threshold: float,
    ) -> None:
        self.sample_rate = sample_rate
        self.silence_seconds = silence_seconds
        self.min_speech_seconds = min_speech_seconds
        self.max_segment_seconds = max_segment_seconds
        self.energy_threshold = energy_threshold
        self._frames: list[Any] = []
        self._speech_seconds = 0.0
        self._silence_seconds = 0.0

    def push(self, frame: Any) -> SpeechChunk | None:
        import numpy as np

        mono = np.asarray(frame, dtype=np.float32)
        if mono.ndim > 1:
            mono = mono.mean(axis=1)
        if not len(mono):
            return None
        duration = len(mono) / self.sample_rate
        energy = float(np.sqrt(np.mean(np.square(mono))))
        speaking = energy >= self.energy_threshold
        if speaking:
            self._frames.append(mono)
            self._speech_seconds += duration
            self._silence_seconds = 0.0
        elif self._frames:
            self._frames.append(mono)
            self._silence_seconds += duration
            if (
                self._speech_seconds < self.min_speech_seconds
                and self._silence_seconds >= self.silence_seconds
            ):
                self._reset()
                return None
        should_flush = self._speech_seconds >= self.max_segment_seconds or (
            self._speech_seconds >= self.min_speech_seconds
            and self._silence_seconds >= self.silence_seconds
        )
        return self.flush() if should_flush else None

    def flush(self) -> SpeechChunk | None:
        import numpy as np

        if not self._frames or self._speech_seconds < self.min_speech_seconds:
            self._reset()
            return None
        samples = np.concatenate(self._frames)
        duration = len(samples) / self.sample_rate
        self._reset()
        return SpeechChunk(samples=samples, duration_seconds=duration)

    def _reset(self) -> None:
        self._frames = []
        self._speech_seconds = 0.0
        self._silence_seconds = 0.0
