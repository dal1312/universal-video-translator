from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .paths import app_paths


SETTINGS_SCHEMA_VERSION = 1
_LANGUAGES = {"auto", "inglese", "spagnolo", "francese", "tedesco"}
_WHISPER_MODELS = {"tiny", "base", "small", "medium"}
_SPEECH_ENGINES = {"kokoro", "windows"}
_BROWSERS = {"firefox", "chrome", "edge", "nessuno"}
_PERFORMANCE_PROFILES = {"rapido", "bilanciato", "qualita"}


@dataclass(frozen=True, slots=True)
class AppSettings:
    schema_version: int = SETTINGS_SCHEMA_VERSION
    ollama_model: str = "translategemma:latest"
    language: str = "auto"
    rate: int = 185
    whisper_model: str = "small"
    speech_engine: str = "kokoro"
    voice: str = "Sara (Kokoro, donna)"
    show_text: bool = True
    live_voice: bool = True
    capture_device: str = ""
    cookies_browser: str = "nessuno"
    routing_browser: str = "firefox"
    performance_profile: str = "rapido"
    auto_ducking: bool = True
    dark_mode: bool = True
    advanced_visible: bool = False
    window_geometry: str = "1240x780"
    overlay_geometry: str = "1000x150+160+650"
    overlay_alpha: float = 0.88
    overlay_font_size: int = 20

    @classmethod
    def from_mapping(cls, value: Any) -> AppSettings:
        if not isinstance(value, dict):
            return cls()
        if value.get("schema_version", SETTINGS_SCHEMA_VERSION) != SETTINGS_SCHEMA_VERSION:
            return cls()
        defaults = cls()
        allowed = {field.name for field in fields(cls)}
        data = {key: item for key, item in value.items() if key in allowed}
        data["schema_version"] = SETTINGS_SCHEMA_VERSION
        candidate = cls(**{**asdict(defaults), **data})
        return cls(
            ollama_model=_text(candidate.ollama_model, defaults.ollama_model, 200),
            language=(candidate.language if candidate.language in _LANGUAGES else defaults.language),
            rate=_integer(candidate.rate, 120, 260, defaults.rate),
            whisper_model=(
                candidate.whisper_model
                if candidate.whisper_model in _WHISPER_MODELS
                else defaults.whisper_model
            ),
            speech_engine=(
                candidate.speech_engine
                if candidate.speech_engine in _SPEECH_ENGINES
                else defaults.speech_engine
            ),
            voice=_text(candidate.voice, defaults.voice, 200),
            show_text=bool(candidate.show_text),
            live_voice=bool(candidate.live_voice),
            capture_device=_text(candidate.capture_device, "", 500),
            cookies_browser=(
                candidate.cookies_browser
                if candidate.cookies_browser in _BROWSERS
                else defaults.cookies_browser
            ),
            routing_browser=(
                candidate.routing_browser
                if candidate.routing_browser in _BROWSERS - {"nessuno"}
                else defaults.routing_browser
            ),
            performance_profile=(
                candidate.performance_profile
                if candidate.performance_profile in _PERFORMANCE_PROFILES
                else defaults.performance_profile
            ),
            auto_ducking=bool(candidate.auto_ducking),
            dark_mode=bool(candidate.dark_mode),
            advanced_visible=bool(candidate.advanced_visible),
            window_geometry=_text(candidate.window_geometry, defaults.window_geometry, 100),
            overlay_geometry=_text(candidate.overlay_geometry, defaults.overlay_geometry, 100),
            overlay_alpha=_number(candidate.overlay_alpha, 0.45, 1.0, defaults.overlay_alpha),
            overlay_font_size=_integer(
                candidate.overlay_font_size, 12, 42, defaults.overlay_font_size
            ),
        )


class SettingsStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else app_paths().settings

    def load(self) -> AppSettings:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return AppSettings()
        return AppSettings.from_mapping(raw)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(asdict(settings), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise


def _text(value: Any, default: str, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else default


def _integer(value: Any, minimum: int, maximum: int, default: int) -> int:
    return value if isinstance(value, int) and minimum <= value <= maximum else default


def _number(value: Any, minimum: float, maximum: float, default: float) -> float:
    if isinstance(value, (int, float)) and minimum <= float(value) <= maximum:
        return float(value)
    return default
