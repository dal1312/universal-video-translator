from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .cache import TranslationCache
from .downloader import download_video, is_web_url
from .export import export_italian_audio, mux_video_with_italian_audio
from .media_player import MediaPreview
from .ollama import OllamaTranslator
from .player import SubtitlePlayer
from .progressive import ProgressiveDubPlayer
from .transcription import load_cues


@dataclass(frozen=True, slots=True)
class RunSettings:
    source: str
    ollama_model: str
    whisper_model: str
    language: str
    rate: int
    speech_engine: str
    voice: str
    cookies_browser: str | None


@dataclass(frozen=True, slots=True)
class PreparedPlayback:
    player: SubtitlePlayer | None = None
    progressive: ProgressiveDubPlayer | None = None


class TranslationWorkflow:
    """Runs media operations without depending on Tkinter widgets."""

    def __init__(
        self,
        preview: MediaPreview,
        *,
        on_text: Callable[[str], None],
        on_status: Callable[[str], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self.preview = preview
        self.on_text = on_text
        self.on_status = on_status
        self.on_error = on_error
        self._download_directory: tempfile.TemporaryDirectory[str] | None = None

    def prepare(self, settings: RunSettings) -> PreparedPlayback:
        path = self.resolve_input(settings)
        cues = load_cues(path, whisper_model=settings.whisper_model)
        if not cues:
            raise ValueError("Nessuna battuta rilevata.")
        common = {
            "cues": cues,
            "translator": OllamaTranslator(model=settings.ollama_model),
            "cache": TranslationCache(),
            "source_language": settings.language,
            "rate": settings.rate,
            "speech_engine": settings.speech_engine,
            "voice": settings.voice,
            "on_text": self.on_text,
            "on_status": self.on_status,
            "on_error": self.on_error,
        }
        if path.suffix.lower() not in {".srt", ".vtt"}:
            progressive = ProgressiveDubPlayer(
                media=path,
                preview=self.preview,
                **common,
            )
            progressive.prepare()
            return PreparedPlayback(progressive=progressive)

        player = SubtitlePlayer(**common)
        player.prepare()
        return PreparedPlayback(player=player)

    def export_audio(
        self,
        destination: str | Path,
        settings: RunSettings,
        *,
        on_progress: Callable[[int, int], None] | None = None,
        on_warning: Callable[[str], None] | None = None,
    ) -> Path:
        cues = load_cues(
            self.resolve_input(settings),
            whisper_model=settings.whisper_model,
        )
        return export_italian_audio(
            cues,
            destination,
            translator=OllamaTranslator(model=settings.ollama_model),
            cache=TranslationCache(),
            source_language=settings.language,
            rate=settings.rate,
            speech_engine=settings.speech_engine,
            voice=settings.voice,
            on_progress=on_progress,
            on_warning=on_warning,
        )

    def export_video(
        self,
        destination: str | Path,
        settings: RunSettings,
        *,
        on_progress: Callable[[int, int], None] | None = None,
        on_warning: Callable[[str], None] | None = None,
    ) -> Path:
        source = self.resolve_input(settings)
        destination_path = Path(destination)
        with tempfile.TemporaryDirectory(prefix="uvt-video-") as directory:
            audio = Path(directory) / "italiano.wav"
            cues = load_cues(source, whisper_model=settings.whisper_model)
            export_italian_audio(
                cues,
                audio,
                translator=OllamaTranslator(model=settings.ollama_model),
                cache=TranslationCache(),
                source_language=settings.language,
                rate=settings.rate,
                speech_engine=settings.speech_engine,
                voice=settings.voice,
                on_progress=on_progress,
                on_warning=on_warning,
            )
            mux_video_with_italian_audio(source, audio, destination_path)
        return destination_path

    def resolve_input(self, settings: RunSettings) -> Path:
        if not is_web_url(settings.source):
            return Path(settings.source)
        if self._download_directory is None:
            self._download_directory = tempfile.TemporaryDirectory(
                prefix="uvt-url-"
            )
        self.on_status("Download video: avvio…")
        path, has_subtitles = download_video(
            settings.source,
            self._download_directory.name,
            cookies_browser=settings.cookies_browser,
            source_language=settings.language,
            on_progress=self.on_status,
        )
        if not has_subtitles:
            self.on_status(
                "Nessun sottotitolo utilizzabile: verrà usata la "
                "trascrizione locale."
            )
        return path

    def close(self) -> None:
        directory = self._download_directory
        self._download_directory = None
        if directory is not None:
            directory.cleanup()
