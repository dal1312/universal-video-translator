from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PerformanceProfile:
    key: str
    label: str
    whisper_model: str
    frame_seconds: float
    silence_seconds: float
    min_speech_seconds: float
    max_segment_seconds: float
    energy_threshold: float
    beam_size: int
    audio_queue_size: int
    speech_queue_size: int
    ducking_percent: int
    speech_rate_multiplier: float
    max_queue_delay_seconds: float = 6.0


PROFILES = {
    "rapido": PerformanceProfile(
        key="rapido",
        label="Rapido",
        whisper_model="base",
        frame_seconds=0.12,
        silence_seconds=0.24,
        min_speech_seconds=0.24,
        max_segment_seconds=1.8,
        energy_threshold=0.0075,
        beam_size=1,
        audio_queue_size=1,
        speech_queue_size=1,
        ducking_percent=24,
        speech_rate_multiplier=1.12,
        max_queue_delay_seconds=2.5,
    ),
    "bilanciato": PerformanceProfile(
        key="bilanciato",
        label="Bilanciato",
        whisper_model="small",
        frame_seconds=0.18,
        silence_seconds=0.36,
        min_speech_seconds=0.30,
        max_segment_seconds=3.0,
        energy_threshold=0.007,
        beam_size=2,
        audio_queue_size=1,
        speech_queue_size=1,
        ducking_percent=30,
        speech_rate_multiplier=1.06,
        max_queue_delay_seconds=4.0,
    ),
    "qualita": PerformanceProfile(
        key="qualita",
        label="Qualità",
        whisper_model="medium",
        frame_seconds=0.22,
        silence_seconds=0.50,
        min_speech_seconds=0.40,
        max_segment_seconds=4.0,
        energy_threshold=0.006,
        beam_size=3,
        audio_queue_size=1,
        speech_queue_size=1,
        ducking_percent=36,
        speech_rate_multiplier=1.0,
        max_queue_delay_seconds=6.0,
    ),
}

PROFILE_LABELS = tuple(profile.label for profile in PROFILES.values())


def profile_by_key(value: str) -> PerformanceProfile:
    return PROFILES.get(value.casefold(), PROFILES["bilanciato"])


def profile_key_from_label(value: str) -> str:
    normalized = value.strip().casefold()
    for key, profile in PROFILES.items():
        if normalized in {key, profile.label.casefold()}:
            return key
    return "bilanciato"
