from __future__ import annotations

import numpy as np

from uvt.latency import LatencyTracker
from uvt.profiles import PROFILE_LABELS, profile_by_key, profile_key_from_label
from uvt.vad import SpeechSegmenter


def test_performance_profiles_map_labels_and_change_pipeline() -> None:
    assert PROFILE_LABELS == ("Rapido", "Bilanciato", "Qualità")
    assert profile_key_from_label("Qualità") == "qualita"
    assert profile_by_key("rapido").max_segment_seconds < profile_by_key(
        "qualita"
    ).max_segment_seconds
    assert profile_by_key("rapido").beam_size < profile_by_key(
        "qualita"
    ).beam_size
    assert profile_by_key("rapido").max_segment_seconds == 1.8
    assert profile_by_key("qualita").audio_queue_size == 1


def test_vad_emits_incrementally_after_a_pause() -> None:
    segmenter = SpeechSegmenter(
        100,
        silence_seconds=0.2,
        min_speech_seconds=0.2,
        max_segment_seconds=2.0,
        energy_threshold=0.01,
    )
    speech = np.full(20, 0.2, dtype=np.float32)
    silence = np.zeros(20, dtype=np.float32)

    assert segmenter.push(speech) is None
    chunk = segmenter.push(silence)

    assert chunk is not None
    assert chunk.duration_seconds == 0.4
    assert len(chunk.samples) == 40


def test_vad_ignores_short_noise_and_limits_long_segments() -> None:
    segmenter = SpeechSegmenter(
        100,
        silence_seconds=0.2,
        min_speech_seconds=0.2,
        max_segment_seconds=0.4,
        energy_threshold=0.01,
    )

    assert segmenter.push(np.full(10, 0.2, dtype=np.float32)) is None
    assert segmenter.push(np.zeros(30, dtype=np.float32)) is None
    assert segmenter.push(np.full(40, 0.2, dtype=np.float32)) is not None


def test_latency_tracker_reports_current_and_median(tmp_path) -> None:
    tracker = LatencyTracker(maximum_samples=3)
    tracker.record(
        capture_ms=100,
        transcribe_ms=20,
        translate_ms=30,
        queue_ms=10,
        total_ms=160,
    )
    result = tracker.record(
        capture_ms=200,
        transcribe_ms=30,
        translate_ms=40,
        queue_ms=20,
        total_ms=290,
    )

    assert result["samples"] == 2
    assert result["current_ms"] == 290
    assert result["median_ms"] == 225
    assert tracker.export(tmp_path / "latency.json").is_file()
