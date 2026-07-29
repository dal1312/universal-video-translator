from types import SimpleNamespace

from uvt.player import SubtitlePlayer


class _Translator:
    model = "test"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def translate(self, text: str, _source_language: str) -> str:
        self.calls.append(text)
        raise RuntimeError("translation failed")


class _Cache:
    def get(self, _model: str, _source_language: str, _text: str):
        return None

    def put(
        self,
        _model: str,
        _source_language: str,
        text: str,
        translated: str,
    ) -> None:
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


def test_player_translate_fallback_on_error() -> None:
    messages: list[str] = []

    player = SubtitlePlayer(
        [],
        translator=_Translator(),  # type: ignore[arg-type]
        cache=_Cache(),  # type: ignore[arg-type]
        on_status=messages.append,
    )

    assert player._translate("original", position=2) == "original"
    assert any("Fallback originale per battuta 2" in item for item in messages)


def test_player_prepare_continues_with_bad_translation(monkeypatch) -> None:
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
