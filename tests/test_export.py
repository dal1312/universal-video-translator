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


def test_export_falls_back_for_missing_batch_items(
    tmp_path: Path, monkeypatch
) -> None:
    saved: list[str] = []
    cached: list[tuple[str, str, str, str]] = []

    class Translator:
        model = "test"

        def translate_many(
            self, _texts: list[str], _source_language: str
        ) -> list[str]:
            return ["IT uno"]

    class Cache:
        def get(self, *_args):
            return None

        def put_many(self, translations) -> None:
            cached.extend(translations)

    class Engine:
        def save(self, text: str, destination: str | Path) -> None:
            saved.append(text)
            Path(destination).write_bytes(b"wav")

    monkeypatch.setattr(
        "uvt.export.create_speech_engine", lambda *_args: Engine()
    )
    monkeypatch.setattr("uvt.export.ensure_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        "uvt.export.subprocess.run", lambda *_args, **_kwargs: None
    )

    export_italian_audio(
        [Cue(0.0, 1.0, "uno"), Cue(1.0, 2.0, "due")],
        tmp_path / "output.wav",
        translator=Translator(),  # type: ignore[arg-type]
        cache=Cache(),  # type: ignore[arg-type]
    )

    assert saved == ["IT uno", "due"]
    assert cached == [("test", "auto", "uno", "IT uno")]


def test_export_continues_when_cache_is_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    saved: list[str] = []

    class Translator:
        model = "test"

        def translate_many(
            self, texts: list[str], _source_language: str
        ) -> list[str]:
            return [f"IT {text}" for text in texts]

    class Cache:
        def get(self, *_args):
            raise OSError("locked")

        def put_many(self, _translations) -> None:
            raise OSError("locked")

    class Engine:
        def save(self, text: str, destination: str | Path) -> None:
            saved.append(text)
            Path(destination).write_bytes(b"wav")

    monkeypatch.setattr(
        "uvt.export.create_speech_engine", lambda *_args: Engine()
    )
    monkeypatch.setattr("uvt.export.ensure_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        "uvt.export.subprocess.run", lambda *_args, **_kwargs: None
    )

    export_italian_audio(
        [Cue(0.0, 1.0, "uno")],
        tmp_path / "output.wav",
        translator=Translator(),  # type: ignore[arg-type]
        cache=Cache(),  # type: ignore[arg-type]
    )

    assert saved == ["IT uno"]


def test_export_warns_about_untranslated_segments(
    tmp_path: Path, monkeypatch
) -> None:
    warnings: list[str] = []

    class Translator:
        model = "test"
        last_failed_indices = (0,)

        def translate_many(
            self, texts: list[str], _source_language: str
        ) -> list[str]:
            return texts

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

    export_italian_audio(
        [Cue(0.0, 1.0, "untranslated")],
        tmp_path / "output.wav",
        translator=Translator(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
        on_warning=warnings.append,
    )

    assert warnings == [
        "1 segmenti non sono stati tradotti e rimangono nella lingua originale."
    ]
