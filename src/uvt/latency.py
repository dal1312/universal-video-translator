from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median

from .diagnostics import logger


@dataclass(frozen=True, slots=True)
class LatencySample:
    capture_ms: float
    transcribe_ms: float
    translate_ms: float
    queue_ms: float
    total_ms: float
    recorded_at: float


class LatencyTracker:
    def __init__(self, maximum_samples: int = 120) -> None:
        self._samples: deque[LatencySample] = deque(maxlen=maximum_samples)
        self._lock = threading.Lock()

    def record(
        self,
        *,
        capture_ms: float,
        transcribe_ms: float,
        translate_ms: float,
        queue_ms: float,
        total_ms: float,
    ) -> dict[str, float | int]:
        sample = LatencySample(
            capture_ms=max(0.0, capture_ms),
            transcribe_ms=max(0.0, transcribe_ms),
            translate_ms=max(0.0, translate_ms),
            queue_ms=max(0.0, queue_ms),
            total_ms=max(0.0, total_ms),
            recorded_at=time.time(),
        )
        with self._lock:
            self._samples.append(sample)
        snapshot = self.snapshot()
        logger("latency").info(
            "event=sample capture_ms=%.0f transcribe_ms=%.0f "
            "translate_ms=%.0f queue_ms=%.0f total_ms=%.0f",
            sample.capture_ms,
            sample.transcribe_ms,
            sample.translate_ms,
            sample.queue_ms,
            sample.total_ms,
        )
        return snapshot

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            samples = tuple(self._samples)
        if not samples:
            return {"samples": 0, "current_ms": 0.0, "median_ms": 0.0}
        return {
            "samples": len(samples),
            "current_ms": round(samples[-1].total_ms, 1),
            "median_ms": round(median(item.total_ms for item in samples), 1),
            "capture_ms": round(samples[-1].capture_ms, 1),
            "transcribe_ms": round(samples[-1].transcribe_ms, 1),
            "translate_ms": round(samples[-1].translate_ms, 1),
            "queue_ms": round(samples[-1].queue_ms, 1),
        }

    def export(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = [asdict(sample) for sample in self._samples]
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination
