from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .subtitles import Cue


class DiarizationError(RuntimeError):
    """Raised when the optional speaker diarization engine is unavailable."""


@dataclass(frozen=True, slots=True)
class SpeakerSpan:
    start: float
    end: float
    speaker: str


def diarization_available() -> bool:
    try:
        import pyannote.audio  # noqa: F401
    except ImportError:
        return False
    return True


def diarize_audio(
    path: str | Path,
    *,
    num_speakers: int | None = None,
) -> list[SpeakerSpan]:
    """Run the optional local pyannote diarization pipeline.

    The dependency is deliberately optional: the normal Whisper pipeline keeps
    working on Windows without PyTorch/pyannote.  Users can select a model and
    Hugging Face token through environment variables when they want labels.
    """
    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise DiarizationError(
            "Diarizzazione non installata. Installa l'extra "
            "'diarization' e configura UVT_HF_TOKEN."
        ) from exc

    source = Path(path)
    if not source.is_file():
        raise DiarizationError(f"Audio non trovato: {source}")

    model_name = os.environ.get(
        "UVT_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"
    ).strip()
    token = (
        os.environ.get("UVT_HF_TOKEN", "").strip()
        or os.environ.get("HF_TOKEN", "").strip()
        or os.environ.get("HUGGINGFACE_TOKEN", "").strip()
    )
    try:
        kwargs = {"token": token} if token else {}
        try:
            pipeline = Pipeline.from_pretrained(model_name, **kwargs)
        except TypeError:
            # Older pyannote releases used the previous parameter name.
            legacy = {"use_auth_token": token} if token else {}
            pipeline = Pipeline.from_pretrained(model_name, **legacy)
        if pipeline is None:
            raise RuntimeError("pipeline non disponibile")
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
        call_kwargs = {}
        if num_speakers is not None:
            call_kwargs["num_speakers"] = num_speakers
        annotation = pipeline(str(source), **call_kwargs)
        annotation = getattr(annotation, "speaker_diarization", annotation)
        spans = [
            SpeakerSpan(float(start), float(end), str(label))
            for segment, _track, label in annotation.itertracks(
                yield_label=True
            )
            for start, end in [(segment.start, segment.end)]
            if end > start
        ]
    except Exception as exc:
        raise DiarizationError(f"Diarizzazione fallita: {exc}") from exc
    return sorted(spans, key=lambda item: (item.start, item.end, item.speaker))


def assign_speakers(
    cues: list[Cue], spans: list[SpeakerSpan], *, nearest_seconds: float = 0.35
) -> list[Cue]:
    """Attach the speaker with the largest temporal overlap to each cue."""
    if not cues or not spans:
        return list(cues)

    labelled: list[Cue] = []
    for cue in cues:
        overlaps: dict[str, float] = {}
        for span in spans:
            overlap = max(0.0, min(cue.end, span.end) - max(cue.start, span.start))
            if overlap:
                overlaps[span.speaker] = overlaps.get(span.speaker, 0.0) + overlap
        speaker: str | None = None
        if overlaps:
            speaker = max(overlaps, key=overlaps.get)
        else:
            nearest = min(
                spans,
                key=lambda item: min(
                    abs(cue.start - item.end), abs(item.start - cue.end)
                ),
            )
            distance = min(abs(cue.start - nearest.end), abs(nearest.start - cue.end))
            if distance <= nearest_seconds:
                speaker = nearest.speaker
        labelled.append(Cue(cue.start, cue.end, cue.text, speaker))
    return labelled
