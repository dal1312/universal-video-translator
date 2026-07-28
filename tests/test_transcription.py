from pathlib import Path

import pytest

from uvt.transcription import TranscriptionError, load_cues


def test_load_cues_uses_subtitle_parser(tmp_path: Path) -> None:
    source = tmp_path / "sample.srt"
    source.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8"
    )
    cues = load_cues(source)
    assert cues[0].text == "Hello"


def test_missing_media_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TranscriptionError, match="File non trovato"):
        load_cues(tmp_path / "missing.mp4")


def test_media_prefers_vtt_sidecar(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"placeholder")
    sidecar = tmp_path / "video.en.vtt"
    sidecar.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n",
        encoding="utf-8",
    )
    cues = load_cues(media)
    assert cues[0].text == "Hello"
