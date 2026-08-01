from __future__ import annotations

from uvt.hotkeys import GlobalHotkeys


def test_hotkey_command_queue_is_drained_in_order() -> None:
    hotkeys = GlobalHotkeys()
    hotkeys._commands.put("toggle")
    hotkeys._commands.put("volume_up")

    assert hotkeys.drain() == ["toggle", "volume_up"]
    assert hotkeys.drain() == []
