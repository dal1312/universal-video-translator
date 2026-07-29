import queue
import sys
import types

from uvt.cache import TranslationCache
from uvt.live import LiveTranslator, is_probable_echo, put_latest


def test_live_initial_state(tmp_path) -> None:
    live = LiveTranslator(
        translator=object(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
    )
    assert not live.running
    live.stop()


def test_live_queue_discards_oldest_audio() -> None:
    items: queue.Queue = queue.Queue(maxsize=2)
    put_latest(items, "vecchio")
    put_latest(items, "medio")
    put_latest(items, "nuovo")

    assert items.get_nowait() == "medio"
    assert items.get_nowait() == "nuovo"


def test_live_echo_detection() -> None:
    history = ["Questa è la traduzione italiana appena pronunciata."]

    assert is_probable_echo(
        "questa è la traduzione italiana appena pronunciata", history
    )
    assert not is_probable_echo(
        "The next original sentence is completely different", history
    )


def test_live_defaults_to_text_only(tmp_path) -> None:
    live = LiveTranslator(
        translator=object(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
    )

    assert not live.speak
    assert live.chunk_seconds == 4.0
    assert live.capture_device is None


def test_live_falls_back_to_original_on_translate_error(monkeypatch) -> None:
    captured: list[str] = []
    status: list[str] = []
    errors: list[Exception] = []

    class _Translator:
        model = "test"

        def translate(self, _text: str, _source_language: str) -> str:
            raise RuntimeError("fail")

    class _Cache:
        def get(self, _model: str, _source_language: str, _text: str) -> None:
            return None

        def put(
            self,
            _model: str,
            _source_language: str,
            _text: str,
            _translated: str,
        ) -> None:
            return None

    class _Segment:
        def __init__(self, text: str) -> None:
            self.text = text

    class _WhisperModel:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def transcribe(self, *_args, **_kwargs) -> tuple[list[_Segment], None]:
            return [
                _Segment("Ciao")
            ], None

    fake_soundcard = types.ModuleType("soundcard")
    fake_soundcard.default_speaker = lambda: types.SimpleNamespace(name="speaker")
    fake_soundcard.get_microphone = lambda *_args, **_kwargs: types.SimpleNamespace(
        name="speaker"
    )
    fake_soundcard.all_microphones = lambda *_args, **_kwargs: []

    fake_faster_whisper = types.ModuleType("faster_whisper")
    fake_faster_whisper.WhisperModel = _WhisperModel

    monkeypatch.setitem(sys.modules, "soundcard", fake_soundcard)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_faster_whisper)
    monkeypatch.setattr(
        "uvt.live.LiveTranslator._capture",
        lambda *args, **kwargs: None,
    )

    live = LiveTranslator(
        translator=_Translator(),  # type: ignore[arg-type]
        cache=_Cache(),  # type: ignore[arg-type]
        on_text=lambda text: captured.append(text),
        on_status=status.append,
        on_error=errors.append,
    )
    from uvt.live import _END

    import numpy as np

    live._audio_queue.put(np.array([0.1, -0.1], dtype=np.float32))
    live._audio_queue.put(_END)
    live._run()

    assert captured == ["Ciao"]
    assert any("Fallback originale" in item for item in status)
    assert not errors
