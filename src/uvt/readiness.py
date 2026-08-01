from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    key: str
    label: str
    available: bool
    required_for: str


@dataclass(frozen=True, slots=True)
class SystemReadiness:
    components: tuple[ComponentStatus, ...]

    @property
    def missing(self) -> tuple[ComponentStatus, ...]:
        return tuple(item for item in self.components if not item.available)

    @property
    def core_ready(self) -> bool:
        required = {"ollama", "ffmpeg"}
        return all(
            item.available for item in self.components if item.key in required
        )

    def available(self, key: str) -> bool:
        return any(item.key == key and item.available for item in self.components)

    def summary(self) -> str:
        if not self.missing:
            return "Sistema pronto"
        labels = ", ".join(item.label for item in self.missing)
        if not self.core_ready:
            return f"Configurazione incompleta: {labels}"
        return f"Componenti opzionali mancanti: {labels}"


def detect_system_readiness() -> SystemReadiness:
    specifications = (
        ("ollama", "Ollama", bool(shutil.which("ollama")), "traduzione"),
        ("ffmpeg", "FFmpeg", bool(shutil.which("ffmpeg")), "media"),
        (
            "faster_whisper",
            "Faster-Whisper",
            _module_available("faster_whisper"),
            "trascrizione",
        ),
        ("kokoro", "Kokoro", _module_available("kokoro"), "voce neurale"),
        (
            "soundcard",
            "SoundCard",
            _module_available("soundcard"),
            "audio live",
        ),
    )
    return SystemReadiness(
        tuple(ComponentStatus(*specification) for specification in specifications)
    )


def select_available_model(
    models: list[str] | tuple[str, ...],
    preferred: str,
) -> str | None:
    available = tuple(dict.fromkeys(model.strip() for model in models if model.strip()))
    if not available:
        return None
    lookup = {model.casefold(): model for model in available}
    candidates = (
        preferred,
        _with_latest(preferred),
        "translategemma:latest",
        "translategemma",
        "qwen3:4b",
    )
    for candidate in candidates:
        if candidate.casefold() in lookup:
            return lookup[candidate.casefold()]
    return sorted(available, key=str.casefold)[0]


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _with_latest(model: str) -> str:
    return model if ":" in model else f"{model}:latest"
