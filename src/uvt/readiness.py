from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass

from .paths import app_paths
from .translation import ArgosTranslator


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
        return self.available("ffmpeg") and (
            self.available("ollama") or self.available("argos")
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
            "piper",
            "Piper opzionale",
            _piper_available(),
            "voce leggera",
        ),
        (
            "argos",
            "Argos opzionale",
            ArgosTranslator.available(),
            "traduzione fallback",
        ),
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


def _piper_available() -> bool:
    runtime = app_paths().piper_runtime
    return (runtime / "Scripts" / "python.exe").is_file() or (
        runtime / "bin" / "python"
    ).is_file()


def _with_latest(model: str) -> str:
    return model if ":" in model else f"{model}:latest"
