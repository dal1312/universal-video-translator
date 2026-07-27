from uvt.player import SubtitlePlayer


def test_player_initial_state() -> None:
    player = SubtitlePlayer([], translator=object(), cache=object())  # type: ignore
    assert not player.running
    assert not player.paused


def test_pause_toggle() -> None:
    player = SubtitlePlayer([], translator=object(), cache=object())  # type: ignore
    assert player.toggle_pause()
    assert player.paused
    assert not player.toggle_pause()
