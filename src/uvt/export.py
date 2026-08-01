from __future__ import annotations

import subprocess
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .cache import TranslationCache
from .subtitles import Cue
from .transcription import TranscriptionError, ensure_ffmpeg
from .tts import create_speech_engine

if TYPE_CHECKING:
    from .ollama import OllamaTranslator


TRANSLATION_BATCH_SIZE = 12
VOICE_GAP_SECONDS = 0.08
MIN_VOICE_SLOT_SECONDS = 0.25


def _audio_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as audio:
            rate = audio.getframerate()
            return audio.getnframes() / rate if rate else None
    except (OSError, EOFError, wave.Error):
        return None


def _voice_slot(cues: list[Cue], index: int) -> float:
    cue = cues[index]
    end = cue.end
    if index + 1 < len(cues):
        end = min(end, cues[index + 1].start - VOICE_GAP_SECONDS)
    return max(MIN_VOICE_SLOT_SECONDS, end - cue.start)


def _atempo_filters(speed: float) -> list[str]:
    filters: list[str] = []
    while speed > 2.0:
        filters.append("atempo=2")
        speed /= 2.0
    if speed > 1.001:
        filters.append(f"atempo={speed:.6f}")
    return filters


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
    on_warning: Callable[[str], None] | None = None,
) -> Path:
    if not cues:
        raise ValueError("Nessuna battuta da esportare.")

    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    progress = on_progress or (lambda _current, _total: None)
    warning = on_warning or (lambda _message: None)

    with tempfile.TemporaryDirectory(prefix="uvt-export-") as directory:
        temp = Path(directory)
        engine = create_speech_engine(speech_engine, voice, rate)
        segments: list[Path] = []
        translated_by_text: dict[str, str] = {}
        missing: list[str] = []
        missing_seen: set[str] = set()
        failed_segments = 0

        for cue in cues:
            if cue.text in translated_by_text:
                continue
            try:
                translated = cache.get(
                    getattr(translator, "cache_key", translator.model),
                    source_language,
                    cue.text,
                )
            except Exception:
                translated = None
            if translated is not None:
                translated_by_text[cue.text] = translated
            elif cue.text not in missing_seen:
                missing.append(cue.text)
                missing_seen.add(cue.text)

        for offset in range(0, len(missing), TRANSLATION_BATCH_SIZE):
            texts = missing[offset : offset + TRANSLATION_BATCH_SIZE]
            translations = translator.translate_many(texts, source_language)
            if len(translations) < len(texts):
                translations.extend(texts[len(translations) :])
            elif len(translations) > len(texts):
                translations = translations[: len(texts)]
            translated_by_text.update(zip(texts, translations))
            reported_failures = getattr(
                translator, "last_failed_indices", None
            )
            failed = (
                set(reported_failures)
                if reported_failures is not None
                else {
                    index
                    for index, (text, translated) in enumerate(
                        zip(texts, translations)
                    )
                    if translated == text
                }
            )
            failed_segments += len(failed)
            cacheable = [
                (text, translated)
                for text, translated in zip(texts, translations)
                if translated != text
            ]
            try:
                cache.put_many(
                    [
                        (
                            getattr(translator, "cache_key", translator.model),
                            source_language,
                            text,
                            translated,
                        )
                        for text, translated in cacheable
                    ]
                )
            except Exception:
                pass

        for index, cue in enumerate(cues):
            translated = translated_by_text[cue.text]
            segment = temp / f"segment-{index:05d}.wav"
            engine.save(translated, segment)
            if not segment.exists():
                raise TranscriptionError(
                    "La voce di sistema non ha generato il file audio."
                )
            segments.append(segment)
            progress(index + 1, len(cues))

        if failed_segments:
            warning(
                f"{failed_segments} segmenti non sono stati tradotti e "
                "rimangono nella lingua originale."
            )

        command = [ensure_ffmpeg(), "-v", "error", "-y"]
        for segment in segments:
            command.extend(["-i", str(segment)])

        filters: list[str] = []
        for index, (cue, segment) in enumerate(zip(cues, segments)):
            slot = _voice_slot(cues, index)
            duration = _audio_duration(segment)
            audio_filters: list[str] = []
            if duration is not None and duration > slot:
                audio_filters.extend(_atempo_filters(duration / slot))
            audio_filters.extend(
                [
                    f"atrim=duration={slot:.6f}",
                    f"adelay={max(0, round(cue.start * 1000))}:all=1",
                ]
            )
            filters.append(
                f"[{index}:a]{','.join(audio_filters)}[a{index}]"
            )
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
        str(output),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "creazione video non riuscita"
        raise TranscriptionError(f"Errore FFmpeg: {detail}") from exc
    return output
