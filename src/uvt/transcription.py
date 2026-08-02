from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .executables import find_executable
from .subtitles import Cue, collapse_rolling_cues


class TranscriptionError(RuntimeError):
    pass


def find_media_tool(name: str) -> str | None:
    return find_executable(name)


def ensure_ffmpeg() -> str:
    executable = find_media_tool("ffmpeg")
    if executable:
        return executable
    raise TranscriptionError(
        "FFmpeg non trovato. Installalo o ricostruisci l'app con "
        "BUILD_EXE_WINDOWS.bat."
    )


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
            cues = [
                Cue(float(segment.start), float(segment.end), segment.text.strip())
                for segment in segments
                if segment.text.strip()
            ]
            if cues:
                return cues
            segments, _info = whisper.transcribe(
                str(audio),
                language=None if language in {None, "", "auto"} else language,
                vad_filter=False,
                condition_on_previous_text=False,
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

        cues = load_subtitles(source)
        return collapse_rolling_cues(cues) if source.suffix.lower() == ".vtt" else cues
    sidecars = sorted(source.parent.glob(f"{source.stem}*.vtt"))
    for sidecar in sidecars:
        from .subtitles import load_subtitles

        cues = load_subtitles(sidecar)
        if cues:
            return collapse_rolling_cues(cues)
    return transcribe_media(source, model=whisper_model)
