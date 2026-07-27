from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .cache import TranslationCache
from .subtitles import Cue
from .transcription import TranscriptionError, ensure_ffmpeg

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


def export_italian_audio(
    cues: list[Cue],
    destination: str | Path,
    translator: OllamaTranslator,
    cache: TranslationCache,
    source_language: str = "auto",
    rate: int = 185,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    if not cues:
        raise ValueError("Nessuna battuta da esportare.")

    try:
        import pyttsx3
    except ImportError as exc:
        raise TranscriptionError("pyttsx3 non installato.") from exc

    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    progress = on_progress or (lambda _current, _total: None)

    with tempfile.TemporaryDirectory(prefix="uvt-export-") as directory:
        temp = Path(directory)
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
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
            engine.save_to_file(translated, str(segment))
            engine.runAndWait()
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
