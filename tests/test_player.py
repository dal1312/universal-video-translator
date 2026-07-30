from types import SimpleNamespace

from uvt.player import SubtitlePlayer


class _Translator:
    model = "test"

    def translate(self, _text: str, _source_language: str) -> str:
        raise RuntimeError("translation failed")


class _Cache:
    def get(self, _model: str, _source_language: str, _text: str):
        return None

    def put(self, *_args) -> None:
        return None


def test_player_initial_state() -> None:
    player = SubtitlePlayer([], translator=object(), cache=object())  # type: ignore
    assert not player.running
    assert not player.paused


def test_pause_toggle() -> None:
    player = SubtitlePlayer([], translator=object(), cache=object())  # type: ignore
    assert player.toggle_pause()
    assert player.paused
    assert not player.toggle_pause()


def test_player_translate_falls_back_to_original() -> None:
    messages: list[str] = []
    player = SubtitlePlayer(
        [],
        translator=_Translator(),  # type: ignore[arg-type]
        cache=_Cache(),  # type: ignore[arg-type]
        on_status=messages.append,
    )

    assert player._translate("original", position=2) == "original"
    assert any("Fallback originale per battuta 2" in item for item in messages)


def test_player_prepare_continues_after_translation_error(monkeypatch) -> None:
    prewarmed: list[str] = []

    class _Engine:
        def prewarm(self, text: str) -> None:
            prewarmed.append(text)

    monkeypatch.setattr("uvt.player.create_speech_engine", lambda *_args: _Engine())
    player = SubtitlePlayer(
        [SimpleNamespace(text="prima"), SimpleNamespace(text="seconda")],
        translator=_Translator(),  # type: ignore[arg-type]
        cache=_Cache(),  # type: ignore[arg-type]
    )

    player.prepare()

    assert prewarmed == ["prima"]


def test_player_uses_translation_when_cache_write_fails() -> None:
    messages: list[str] = []

    class Translator:
        model = "test"

        def translate(self, _text: str, _source_language: str) -> str:
            return "tradotto"

    class Cache:
        def get(self, *_args):
            return None

        def put(self, *_args) -> None:
            raise OSError("read only")

    player = SubtitlePlayer(
        [],
        translator=Translator(),  # type: ignore[arg-type]
        cache=Cache(),  # type: ignore[arg-type]
        on_status=messages.append,
    )

    assert player._translate("originale", position=1) == "tradotto"
    assert any("Cache traduzione non aggiornata" in item for item in messages)
