from uvt.cache import TranslationCache
from uvt.live import LiveTranslator


def test_live_initial_state(tmp_path) -> None:
    live = LiveTranslator(
        translator=object(),  # type: ignore[arg-type]
        cache=TranslationCache(tmp_path / "cache.json"),
    )
    assert not live.running
    live.stop()
