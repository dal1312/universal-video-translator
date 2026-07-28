import queue

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
