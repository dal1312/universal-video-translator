from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .subtitles import Cue


class TranscriptionError(RuntimeError):
    pass


def ensure_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise TranscriptionError(
            "FFmpeg non trovato. Installalo e aggiungilo alla variabile PATH."
        )
    return executable


def transcribe_media(
    path: str | Path,
    model: str = "small",
    language: str | None = None,
) -> list[Cue]:
    source = Path(path)
    if not source.is_file():
        raise TranscriptionError(f"File non trovato: {source}")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "Whisper non installato. Esegui: pip install -e .[audio]"
        ) from exc

    with tempfile.TemporaryDirectory(prefix="uvt-") as directory:
        audio = Path(directory) / "audio.wav"
        command = [
            ensure_ffmpeg(),
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or "estrazione audio non riuscita"
            raise TranscriptionError(f"Errore FFmpeg: {detail}") from exc

        try:
            whisper = WhisperModel(model, device="auto", compute_type="int8")
            segments, _info = whisper.transcribe(
                str(audio),
                language=None if language in {None, "", "auto"} else language,
                vad_filter=True,
            )
            return [
                Cue(float(segment.start), float(segment.end), segment.text.strip())
                for segment in segments
                if segment.text.strip()
            ]
        except Exception as exc:
            raise TranscriptionError(f"Trascrizione Whisper fallita: {exc}") from exc


def load_cues(path: str | Path, whisper_model: str = "small") -> list[Cue]:
    source = Path(path)
    if source.suffix.lower() in {".srt", ".vtt"}:
        from .subtitles import load_subtitles

        return load_subtitles(source)
    return transcribe_media(source, model=whisper_model)
