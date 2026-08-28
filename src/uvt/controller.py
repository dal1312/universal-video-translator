"""Controller per la gestione della logica applicativa."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from .config import RunSettings
from .services import ExportService, MediaService, TranslationService


class AppController:
    """Controller che gestisce la logica applicativa separata dalla GUI."""

    def __init__(
        self,
        ollama_model: str = "translategemma:latest",
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_text: Callable[[str], None] | None = None,
    ) -> None:
        self.translation_service = TranslationService(model=ollama_model)
        self.media_service = MediaService()
        self.export_service = ExportService(ollama_model=ollama_model)
        
        self._on_status = on_status or (lambda _text: None)
        self._on_error = on_error or (lambda _error: None)
        self._on_text = on_text or (lambda _text: None)
        
        self._download_directory: tempfile.TemporaryDirectory | None = None
        self._preview_directory: tempfile.TemporaryDirectory | None = None

    def set_callbacks(
        self,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_text: Callable[[str], None] | None = None,
    ) -> None:
        """Imposta i callback per status, errori e testo."""
        if on_status:
            self._on_status = on_status
        if on_error:
            self._on_error = on_error
        if on_text:
            self._on_text = on_text

    def resolve_input(
        self,
        source: str,
        cookies_browser: str | None = None,
        source_language: str = "auto",
    ) -> Path:
        """Risolve l'input (URL o file locale)."""
        return self.media_service.resolve_input(
            source,
            cookies_browser=cookies_browser,
            source_language=source_language,
            status_callback=self._on_status,
        )

    def load_cues(self, source: str | Path, whisper_model: str = "small") -> list:
        """Carica i cue da un file."""
        return self.media_service.load_media_cues(source, whisper_model=whisper_model)

    def pretranslate_cues(
        self,
        cues: list,
        source_language: str,
    ) -> dict[str, str]:
        """Pre-traduce tutti i cue."""
        return self.translation_service.pretranslate_cues(
            cues, source_language, on_progress=lambda c, t: self._on_status(f"Pretraduzione {c}/{t}")
        )

    def export_audio(
        self,
        source: str | Path,
        destination: str | Path,
        whisper_model: str = "small",
        source_language: str = "auto",
        rate: int = 185,
        speech_engine: str = "kokoro",
        voice: str = "if_sara",
    ) -> Path:
        """Esporta audio italiano."""
        return self.export_service.export_audio(
            source,
            destination,
            whisper_model=whisper_model,
            source_language=source_language,
            rate=rate,
            speech_engine=speech_engine,
            voice=voice,
            on_progress=lambda c, t: self._on_status(f"Esportazione {c}/{t}"),
        )

    def export_video(
        self,
        source: str | Path,
        destination: str | Path,
        whisper_model: str = "small",
        source_language: str = "auto",
        rate: int = 185,
        speech_engine: str = "kokoro",
        voice: str = "if_sara",
    ) -> Path:
        """Crea video con audio italiano."""
        return self.export_service.export_video(
            source,
            destination,
            whisper_model=whisper_model,
            source_language=source_language,
            rate=rate,
            speech_engine=speech_engine,
            voice=voice,
            on_progress=lambda c, t: self._on_status(f"Creazione video {c}/{t}"),
        )

    def cleanup(self) -> None:
        """Pulisce le risorse temporanee."""
        self.media_service.cleanup()
        if self._download_directory:
            self._download_directory.cleanup()
            self._download_directory = None
        if self._preview_directory:
            self._preview_directory.cleanup()
            self._preview_directory = None

    def list_models(self) -> list[str]:
        """Restituisce la lista dei modelli Ollama disponibili."""
        return self.translation_service.list_models()
