from pathlib import Path

import numpy as np

from uvt.progressive import (
    CHUNK_SECONDS,
    INITIAL_BUFFER_SECONDS,
    SAMPLE_RATE,
    VOICE_GAP_SECONDS,
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


def test_close_cues_are_fitted_without_delaying_next_voice(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "uvt.progressive.create_speech_engine", lambda *_args: Engine()
    )
    player = ProgressiveDubPlayer(
        media=tmp_path / "video.mp4",
        cues=[
            Cue(1.0, 2.0, "prima"),
            Cue(1.5, 2.5, "seconda"),
        ],
        preview=Preview(),  # type: ignore[arg-type]
        translator=Translator(),  # type: ignore[arg-type]
        cache=Cache(),  # type: ignore[arg-type]
    )

    player.prepare()

    audio = np.concatenate(player._initial)
    second_start = round(1.5 * SAMPLE_RATE)
    gap = round(VOICE_GAP_SECONDS * SAMPLE_RATE)
    assert np.max(audio) == 1.0
    assert np.all(audio[second_start - gap : second_start] == 0.0)
    assert np.all(
        audio[second_start : second_start + SAMPLE_RATE] == 1.0
    )
    player.stop()


def test_missing_batch_translation_falls_back_to_original(tmp_path: Path) -> None:
    cached: list[tuple[str, str, str, str]] = []

    class PartialTranslator(Translator):
        def translate_many(
            self, texts: list[str], _language: str
        ) -> list[str]:
            return ["IT uno"]

    class RecordingCache(Cache):
        def put_many(self, translations) -> None:
            cached.extend(translations)

    player = ProgressiveDubPlayer(
        media=tmp_path / "video.mp4",
        cues=[],
        preview=Preview(),  # type: ignore[arg-type]
        translator=PartialTranslator(),  # type: ignore[arg-type]
        cache=RecordingCache(),  # type: ignore[arg-type]
    )

    player._translate_cues(
        [Cue(0.0, 1.0, "uno"), Cue(1.0, 2.0, "due")]
    )

    assert player._translations == {"uno": "IT uno", "due": "due"}
    assert cached == [("test", "auto", "uno", "IT uno")]


def test_progressive_continues_when_cache_is_unavailable(
    tmp_path: Path,
) -> None:
    statuses: list[str] = []

    class BrokenCache(Cache):
        def get(self, *_args):
            raise OSError("locked")

        def put_many(self, _translations) -> None:
            raise OSError("locked")

    player = ProgressiveDubPlayer(
        media=tmp_path / "video.mp4",
        cues=[],
        preview=Preview(),  # type: ignore[arg-type]
        translator=Translator(),  # type: ignore[arg-type]
        cache=BrokenCache(),  # type: ignore[arg-type]
        on_status=statuses.append,
    )

    player._translate_cues([Cue(0.0, 1.0, "uno")])

    assert player._translations == {"uno": "IT uno"}
    assert any("Cache traduzione non disponibile" in item for item in statuses)
    assert any("Cache traduzione non aggiornata" in item for item in statuses)


def test_progressive_reports_untranslated_segments(tmp_path: Path) -> None:
    statuses: list[str] = []

    class FailedTranslator(Translator):
        last_failed_indices = (0,)

        def translate_many(
            self, texts: list[str], _language: str
        ) -> list[str]:
            return texts

    player = ProgressiveDubPlayer(
        media=tmp_path / "video.mp4",
        cues=[],
        preview=Preview(),  # type: ignore[arg-type]
        translator=FailedTranslator(),  # type: ignore[arg-type]
        cache=Cache(),  # type: ignore[arg-type]
        on_status=statuses.append,
    )

    player._translate_cues([Cue(0.0, 1.0, "untranslated")])

    assert any("1 segmenti non tradotti" in item for item in statuses)
