"""Configuration and settings management."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunSettings:
    """Impostazioni di esecuzione per la traduzione."""

    source: str
    ollama_model: str
    whisper_model: str
    language: str
    rate: int
    speech_engine: str
    voice: str
    cookies_browser: str | None


DEFAULT_SETTINGS = {
    "ollama_model": "translategemma:latest",
    "whisper_model": "small",
    "language": "auto",
    "rate": 185,
    "speech_engine": "kokoro",
    "cookies_browser": "firefox",
}

SUPPORTED_LANGUAGES = ("auto", "inglese", "spagnolo", "francese", "tedesco")
SUPPORTED_BROWSERS = ("firefox", "chrome", "edge", "nessuno")
WHISPER_MODELS = ("tiny", "base", "small", "medium")
