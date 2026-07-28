from pathlib import Path

import numpy as np

from uvt.progressive import (
    CHUNK_SECONDS,
    INITIAL_BUFFER_SECONDS,
    SAMPLE_RATE,
    ProgressiveDubPlayer,
)
from uvt.subtitles import Cue


class Translator:
    model = "test"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def translate_many(
        self, texts: list[str], _language: str
    ) -> list[str]:
        self.calls.append(texts)
        return [f"IT {text}" for text in texts]


class Cache:
    def get(self, _model: str, _language: str, _text: str):
        return None

    def put_many(self, _translations) -> None:
        return


class Preview:
    def stop(self) -> None:
        return


class Engine:
    def render(self, _text: str):
        return np.ones(SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE

    def stop(self) -> None:
        return


def test_initial_buffer_prepares_only_first_window(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "uvt.progressive.create_speech_engine", lambda *_args: Engine()
    )
    translator = Translator()
    player = ProgressiveDubPlayer(
        media=tmp_path / "video.mp4",
        cues=[
            Cue(1.0, 2.0, "uno"),
            Cue(16.0, 17.0, "due"),
            Cue(31.0, 32.0, "tre"),
        ],
        preview=Preview(),  # type: ignore[arg-type]
        translator=translator,  # type: ignore[arg-type]
        cache=Cache(),  # type: ignore[arg-type]
    )

    player.prepare()

    assert len(player._initial) == INITIAL_BUFFER_SECONDS // CHUNK_SECONDS
    assert [text for call in translator.calls for text in call] == [
        "uno",
        "due",
    ]
    first = player._initial[0]
    start = SAMPLE_RATE
    assert np.all(first[start : start + SAMPLE_RATE] == 1.0)
    player.stop()


def test_audio_crossing_chunk_boundary_is_preserved(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "uvt.progressive.create_speech_engine", lambda *_args: Engine()
    )
    player = ProgressiveDubPlayer(
        media=tmp_path / "video.mp4",
        cues=[Cue(14.5, 15.5, "confine")],
        preview=Preview(),  # type: ignore[arg-type]
        translator=Translator(),  # type: ignore[arg-type]
        cache=Cache(),  # type: ignore[arg-type]
    )

    player.prepare()

    half_second = SAMPLE_RATE // 2
    assert np.all(player._initial[0][-half_second:] == 1.0)
    assert np.all(player._initial[1][:half_second] == 1.0)
    player.stop()
