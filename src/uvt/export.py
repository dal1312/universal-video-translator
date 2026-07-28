from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .cache import TranslationCache
from .subtitles import Cue
from .transcription import TranscriptionError, ensure_ffmpeg
from .tts import create_speech_engine

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


def export_italian_audio(
    cues: list[Cue],
    destination: str | Path,
    translator: OllamaTranslator,
    cache: TranslationCache,
    source_language: str = "auto",
    rate: int = 185,
    speech_engine: str = "windows",
    voice: str = "default",
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    if not cues:
        raise ValueError("Nessuna battuta da esportare.")

    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    progress = on_progress or (lambda _current, _total: None)

    with tempfile.TemporaryDirectory(prefix="uvt-export-") as directory:
        temp = Path(directory)
        engine = create_speech_engine(speech_engine, voice, rate)
        segments: list[Path] = []

        for index, cue in enumerate(cues):
            translated = cache.get(
                translator.model, source_language, cue.text
            )
            if translated is None:
                translated = translator.translate(cue.text, source_language)
                cache.put(
                    translator.model, source_language, cue.text, translated
                )
            segment = temp / f"segment-{index:05d}.wav"
            engine.save(translated, segment)
            if not segment.exists():
                raise TranscriptionError(
                    "La voce di sistema non ha generato il file audio."
                )
            segments.append(segment)
            progress(index + 1, len(cues))

        command = [ensure_ffmpeg(), "-v", "error", "-y"]
        for segment in segments:
            command.extend(["-i", str(segment)])

        filters = [
            f"[{index}:a]adelay={max(0, round(cue.start * 1000))}:all=1[a{index}]"
            for index, cue in enumerate(cues)
        ]
        mixed = "".join(f"[a{index}]" for index in range(len(cues)))
        filters.append(
            f"{mixed}amix=inputs={len(cues)}:duration=longest:normalize=0[out]"
        )
        command.extend(["-filter_complex", ";".join(filters), "-map", "[out]"])
        if output.suffix.lower() == ".mp3":
            command.extend(["-codec:a", "libmp3lame", "-q:a", "2"])
        else:
            command.extend(["-codec:a", "pcm_s16le"])
        command.append(str(output))

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or "mix audio non riuscito"
            raise TranscriptionError(f"Errore FFmpeg: {detail}") from exc
    return output


def mux_video_with_italian_audio(
    source_video: str | Path,
    italian_audio: str | Path,
    destination: str | Path,
) -> Path:
    source = Path(source_video)
    audio = Path(italian_audio)
    output = Path(destination)
    if not source.is_file() or not audio.is_file():
        raise ValueError("Video sorgente o traccia italiana non trovati.")
    command = [
        ensure_ffmpeg(),
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-metadata:s:a:0",
        "language=ita",
        "-shortest",
        str(output),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "creazione video non riuscita"
        raise TranscriptionError(f"Errore FFmpeg: {detail}") from exc
    return output
