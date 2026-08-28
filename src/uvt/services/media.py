"""Service layer for media operations."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..downloader import download_video, is_web_url
from ..transcription import load_cues


class MediaService:
    """Servizio per la gestione di file multimediali e download."""

    def __init__(self, download_directory: str | None = None) -> None:
        self._download_directory = download_directory

    def resolve_input(
        self,
        source: str,
        cookies_browser: str | None = None,
        source_language: str = "auto",
        status_callback: callable | None = None,
    ) -> Path:
        """Risolve l'input: se è un URL, lo scarica; altrimenti restituisce il path."""
        if not is_web_url(source):
            return Path(source)

        if self._download_directory is None:
            import tempfile
            self._download_directory = tempfile.mkdtemp(prefix="uvt-url-")

        if status_callback:
            status_callback("Download video…")

        return download_video(
            source,
            self._download_directory,
            cookies_browser=cookies_browser,
            source_language=source_language,
        )

    def load_media_cues(
        self,
        source: str | Path,
        whisper_model: str = "small",
    ) -> list:
        """Carica i cue da un file multimediale o sottotitoli."""
        return load_cues(source, whisper_model=whisper_model)

    def cleanup(self) -> None:
        """Pulisce le directory temporanee."""
        if self._download_directory:
            import shutil
            try:
                shutil.rmtree(self._download_directory)
            except (OSError, FileNotFoundError):
                pass
            self._download_directory = None
