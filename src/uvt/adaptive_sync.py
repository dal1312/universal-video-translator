from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AdaptiveSyncController:
    """Smoothly accelerates speech when translated audio falls behind."""

    base_rate: int
    maximum_multiplier: float = 1.45
    smoothing: float = 0.35
    _multiplier: float = field(init=False, default=1.0)

    def __post_init__(self) -> None:
        self.base_rate = max(80, int(self.base_rate))
        self._multiplier = 1.0

    def next_rate(
        self,
        *,
        queue_ms: float,
        text: str,
        source_duration_seconds: float,
    ) -> int:
        words = max(1, len(text.split()))
        estimated_seconds = words / 2.7
        duration_ratio = (
            estimated_seconds / source_duration_seconds
            if source_duration_seconds > 0.2
            else 1.0
        )
        queue_boost = 1.0 + min(0.35, max(0.0, queue_ms) / 12000.0)
        target = min(
            self.maximum_multiplier,
            max(1.0, duration_ratio, queue_boost),
        )
        self._multiplier += (target - self._multiplier) * self.smoothing
        return round(self.base_rate * self._multiplier)

    @property
    def multiplier(self) -> float:
        return self._multiplier

    @staticmethod
    def offset_ms(
        *, queue_ms: float, speech_ms: float, source_duration_seconds: float
    ) -> float:
        return max(
            0.0,
            queue_ms + speech_ms - max(0.0, source_duration_seconds) * 1000,
        )
