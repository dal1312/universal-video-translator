import queue
import sys
import threading
import types

from uvt.cache import TranslationCache
from uvt.live import (
    LiveTranslator,
    capture_device_names,
    is_probable_echo,
    preferred_cable_output,
    put_latest,
)


def test_live_initial_state(tmp_path) -> None:
    live = LiveTranslator(
        translator=object(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
    )
    assert not live.running
    live.stop()


def test_live_stop_waits_for_worker(tmp_path) -> None:
    live = LiveTranslator(
        translator=object(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
    )
    started = threading.Event()

    def run() -> None:
        started.set()
        live._stop.wait()

    live._run = run  # type: ignore[method-assign]
    live.start()
    assert started.wait(1.0)

    assert live.stop(timeout=1.0)
    assert not live.running
    assert live._thread is None


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
    assert live.chunk_seconds == 1.8
    assert live._audio_queue.maxsize == 1
    assert live._speech_queue.maxsize == 1
    assert live.capture_device is None


def test_live_chunk_duration_is_bounded(tmp_path) -> None:
    fast = LiveTranslator(
        translator=object(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "fast-cache.json"),
        chunk_seconds=0.25,
    )
    slow = LiveTranslator(
        translator=object(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "slow-cache.json"),
        chunk_seconds=20,
    )

    assert fast.chunk_seconds == 1.5
    assert slow.chunk_seconds == 8.0


def test_capture_device_lookup_leaves_soundcard_to_initialize_com(monkeypatch) -> None:
    fake_soundcard = types.ModuleType("soundcard")
    fake_soundcard.all_microphones = lambda **_kwargs: [
        types.SimpleNamespace(name="Cable Output")
    ]
    monkeypatch.setitem(sys.modules, "soundcard", fake_soundcard)
    monkeypatch.setattr(
        "uvt.live.initialize_windows_com",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected COM init")),
    )

    assert capture_device_names() == ["Cable Output"]


def test_preferred_cable_output_uses_vb_cable_device() -> None:
    assert preferred_cable_output(
        ["Microphone", "CABLE Output (VB-Audio Virtual Cable)"]
    ) == "CABLE Output (VB-Audio Virtual Cable)"
    assert preferred_cable_output(["Microphone"]) is None


def test_capture_creates_wasapi_device_in_com_thread(monkeypatch, tmp_path) -> None:
    released: list[bool] = []

    class _Recorder:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def record(self, **_kwargs):
            live._stop.set()
            return object()

    fake_soundcard = types.ModuleType("soundcard")
    fake_soundcard.default_speaker = lambda: types.SimpleNamespace(name="speaker")
    fake_soundcard.get_microphone = lambda *_args, **_kwargs: types.SimpleNamespace(
        name="speaker", recorder=lambda **_kwargs: _Recorder()
    )
    monkeypatch.setitem(sys.modules, "soundcard", fake_soundcard)
    live = LiveTranslator(
        translator=object(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
    )
    monkeypatch.setattr("uvt.live.initialize_windows_com", lambda: True)
    monkeypatch.setattr(
        "uvt.live.uninitialize_windows_com", lambda: released.append(True)
    )

    live._capture(16000)

    assert released == [True]


def test_live_falls_back_to_original_on_translate_error(monkeypatch) -> None:
    captured: list[str] = []
    statuses: list[str] = []
    errors: list[Exception] = []

    class _Translator:
        model = "test"

        def translate(self, _text: str, _source_language: str) -> str:
            raise RuntimeError("fail")

    class _Cache:
        def get(self, *_args):
            return None

        def put(self, *_args) -> None:
            return None

    class _Segment:
        text = "Hello"

    class _WhisperModel:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def transcribe(self, *_args, **_kwargs):
            return [_Segment()], None

    fake_soundcard = types.ModuleType("soundcard")
    fake_soundcard.default_speaker = lambda: types.SimpleNamespace(name="speaker")
    fake_soundcard.get_microphone = lambda *_args, **_kwargs: types.SimpleNamespace(
        name="speaker"
    )
    fake_soundcard.all_microphones = lambda *_args, **_kwargs: []
    fake_whisper = types.ModuleType("faster_whisper")
    fake_whisper.WhisperModel = _WhisperModel

    monkeypatch.setitem(sys.modules, "soundcard", fake_soundcard)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_whisper)
    monkeypatch.setattr("uvt.live.LiveTranslator._capture", lambda *_args: None)

    live = LiveTranslator(
        translator=_Translator(),  # type: ignore[arg-type]
        cache=_Cache(),  # type: ignore[arg-type]
        on_text=captured.append,
        on_status=statuses.append,
        on_error=errors.append,
    )
    from uvt.live import _END

    import numpy as np

    live._audio_queue = queue.Queue(maxsize=2)
    live._audio_queue.put(np.array([0.1, -0.1], dtype=np.float32))
    live._audio_queue.put(_END)
    live._run()

    assert captured == ["Hello"]
    assert any("Fallback originale" in item for item in statuses)
    assert not errors


def test_live_uses_translation_when_cache_write_fails(monkeypatch) -> None:
    captured: list[str] = []
    statuses: list[str] = []
    errors: list[Exception] = []

    class _Translator:
        model = "test"

        def translate(self, _text: str, _source_language: str) -> str:
            return "Ciao"

    class _Cache:
        def get(self, *_args):
            return None

        def put(self, *_args) -> None:
            raise OSError("read only")

    class _Segment:
        text = "Hello"

    class _WhisperModel:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def transcribe(self, *_args, **_kwargs):
            return [_Segment()], None

    fake_soundcard = types.ModuleType("soundcard")
    fake_soundcard.default_speaker = lambda: types.SimpleNamespace(name="speaker")
    fake_soundcard.get_microphone = lambda *_args, **_kwargs: types.SimpleNamespace(
        name="speaker"
    )
    fake_soundcard.all_microphones = lambda *_args, **_kwargs: []
    fake_whisper = types.ModuleType("faster_whisper")
    fake_whisper.WhisperModel = _WhisperModel

    monkeypatch.setitem(sys.modules, "soundcard", fake_soundcard)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_whisper)
    monkeypatch.setattr("uvt.live.LiveTranslator._capture", lambda *_args: None)

    live = LiveTranslator(
        translator=_Translator(),  # type: ignore[arg-type]
        cache=_Cache(),  # type: ignore[arg-type]
        on_text=captured.append,
        on_status=statuses.append,
        on_error=errors.append,
    )
    from uvt.live import _END

    import numpy as np

    live._audio_queue = queue.Queue(maxsize=2)
    live._audio_queue.put(np.array([0.1, -0.1], dtype=np.float32))
    live._audio_queue.put(_END)
    live._run()

    assert captured == ["Ciao"]
    assert any("Cache traduzione non aggiornata" in item for item in statuses)
    assert not errors


def test_live_warms_translator_before_first_translation() -> None:
    calls: list[str] = []

    class _Translator:
        def warmup(self) -> None:
            calls.append("warmup")

    live = LiveTranslator(
        translator=_Translator(),  # type: ignore[arg-type]
        cache=object(),  # type: ignore[arg-type]
    )

    live._warmup_translator()

    assert calls == ["warmup"]
    assert live._warmup_complete.is_set()
