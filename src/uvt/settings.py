from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppSettings:
    ollama_model: str = "translategemma:latest"
    language: str = "auto"
    rate: int = 185
    whisper_model: str = "small"
    speech_engine: str = "kokoro"
    voice: str = "Sara (Kokoro, donna)"
    show_text: bool = True
    live_voice: bool = False
    capture_device: str = "Audio di sistema (predefinito)"
    assistant_provider: str = "Ollama"
    assistant_model: str = ""
    cookies_browser: str = "firefox"
    dark_mode: bool = True
    advanced_visible: bool = False
    minimize_to_tray: bool = True
    window_geometry: str = "1180x720"

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> AppSettings:
        defaults = cls()
        text_fields = (
            "ollama_model",
            "language",
            "whisper_model",
            "speech_engine",
            "voice",
            "capture_device",
            "assistant_provider",
            "assistant_model",
            "cookies_browser",
            "window_geometry",
        )
        bool_fields = (
            "show_text",
            "live_voice",
            "dark_mode",
            "advanced_visible",
            "minimize_to_tray",
        )
        for name in text_fields:
            value = values.get(name)
            if isinstance(value, str) and value.strip():
                setattr(defaults, name, value.strip())
            elif name == "assistant_model" and value == "":
                defaults.assistant_model = ""
        for name in bool_fields:
            value = values.get(name)
            if isinstance(value, bool):
                setattr(defaults, name, value)
        rate = values.get("rate")
        if isinstance(rate, (int, float)) and not isinstance(rate, bool):
            defaults.rate = max(120, min(260, int(rate)))
        if not re.fullmatch(
            r"\d{3,5}x\d{3,5}(?:[+-]\d+){0,2}",
            defaults.window_geometry,
        ):
            defaults.window_geometry = "1180x720"
        return defaults


def default_settings_path() -> Path:
    if os.name == "nt":
        root = Path(
            os.environ.get(
                "LOCALAPPDATA",
                Path.home() / "AppData" / "Local",
            )
        )
    else:
        root = Path(
            os.environ.get(
                "XDG_CONFIG_HOME",
                Path.home() / ".config",
            )
        )
    return root / "UniversalVideoTranslator" / "settings.json"


class ConfigStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_settings_path()

    def load(self) -> AppSettings:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return AppSettings()
        if not isinstance(payload, dict):
            return AppSettings()
        return AppSettings.from_mapping(payload)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="settings-",
            suffix=".json.tmp",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(
                    asdict(settings),
                    stream,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()
