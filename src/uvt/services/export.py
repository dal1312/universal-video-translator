"""Service layer for audio export operations."""

from __future__ import annotations

from pathlib import Path

from ..cache import TranslationCache
from ..export import export_italian_audio, mux_video_with_italian_audio
from ..ollama import OllamaTranslator
from ..transcription import load_cues


class ExportService:
    """Servizio per l'esportazione di audio e video."""

    def __init__(
        self,
        ollama_model: str = "translategemma:latest",
        cache: TranslationCache | None = None,
    ) -> None:
        self._ollama_model = ollama_model
        self._cache = cache or TranslationCache()

    def export_audio(
        self,
        source: str | Path,
        destination: str | Path,
        whisper_model: str = "small",
        source_language: str = "auto",
        rate: int = 185,
        speech_engine: str = "kokoro",
        voice: str = "if_sara",
        on_progress: callable | None = None,
    ) -> Path:
        """Esporta l'audio italiano da un file multimediale."""
        cues = load_cues(source, whisper_model=whisper_model)
        output = export_italian_audio(
            cues,
            destination,
            translator=OllamaTranslator(model=self._ollama_model),
            cache=self._cache,
            source_language=source_language,
            rate=rate,
            speech_engine=speech_engine,
            voice=voice,
            on_progress=on_progress,
        )
        return output

    def export_video(
        self,
        source: str | Path,
        destination: str | Path,
        whisper_model: str = "small",
        source_language: str = "auto",
        rate: int = 185,
        speech_engine: str = "kokoro",
        voice: str = "if_sara",
        on_progress: callable | None = None,
    ) -> Path:
        """Crea un video con audio italiano."""
        import tempfile

        with tempfile.TemporaryDirectory(prefix="uvt-video-") as directory:
            audio = Path(directory) / "italiano.wav"
            cues = load_cues(source, whisper_model=whisper_model)
            export_italian_audio(
                cues,
                audio,
                translator=OllamaTranslator(model=self._ollama_model),
                cache=self._cache,
                source_language=source_language,
                rate=rate,
                speech_engine=speech_engine,
                voice=voice,
                on_progress=on_progress,
            )
            mux_video_with_italian_audio(source, audio, destination)

        return Path(destination)
