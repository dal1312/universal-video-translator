from pathlib import Path

import pytest

from uvt.cache import TranslationCache
from uvt.export import export_italian_audio
from uvt.subtitles import Cue


def test_export_rejects_empty_cues(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Nessuna battuta"):
        export_italian_audio(
            [],
            tmp_path / "output.wav",
            translator=object(),  # type: ignore[arg-type]
            cache=object(),  # type: ignore[arg-type]
        )


def test_export_translates_in_batches(tmp_path: Path, monkeypatch) -> None:
    class Translator:
        model = "test"

        def __init__(self) -> None:
            self.batch_sizes: list[int] = []

        def translate_many(
            self, texts: list[str], _source_language: str
        ) -> list[str]:
            self.batch_sizes.append(len(texts))
            return [f"IT {text}" for text in texts]

    class Engine:
        def save(self, _text: str, destination: str | Path) -> None:
            Path(destination).write_bytes(b"wav")

    monkeypatch.setattr(
        "uvt.export.create_speech_engine", lambda *_args: Engine()
    )
    monkeypatch.setattr("uvt.export.ensure_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        "uvt.export.subprocess.run", lambda *_args, **_kwargs: None
    )

    translator = Translator()
    cues = [
        Cue(float(index), float(index + 1), f"text {index}")
        for index in range(13)
    ]
    export_italian_audio(
        cues,
        tmp_path / "output.wav",
        translator=translator,  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
    )

    assert translator.batch_sizes == [12, 1]


def test_export_falls_back_to_original_when_batch_shorter(tmp_path: Path, monkeypatch) -> None:
    generated: list[str] = []

    class Translator:
        model = "test"

        def translate_many(
            self,
            texts: list[str],
            _source_language: str,
        ) -> list[str]:
            return [f"IT {texts[0]}"]

    class Engine:
        def save(self, text: str, destination: str | Path) -> None:
            generated.append(text)
            Path(destination).write_bytes(b"wav")

    monkeypatch.setattr(
        "uvt.export.create_speech_engine", lambda *_args: Engine()
    )
    monkeypatch.setattr("uvt.export.ensure_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        "uvt.export.subprocess.run", lambda *_args, **_kwargs: None
    )

    export_italian_audio(
        [
            Cue(0.0, 1.0, "salve"),
            Cue(1.0, 2.0, "mondo"),
        ],
        tmp_path / "output.wav",
        translator=Translator(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
    )

    assert generated == ["IT salve", "mondo"]
