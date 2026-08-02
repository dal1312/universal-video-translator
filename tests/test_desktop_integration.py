from __future__ import annotations

from uvt.browser_bridge import BridgeCommand
from uvt.desktop_integration import bridge_snapshot, browser_request, dispatch_hotkey


def test_bridge_snapshot_copies_mutable_latency() -> None:
    latency = {"current_ms": 1200.0}
    result = bridge_snapshot(
        mode="live",
        phase="running",
        running=True,
        profile="rapido",
        browser="chrome",
        capture_device="cable",
        voice=True,
        auto_ducking=True,
        latency=latency,
        app_version="0.2.1",
        update_status="current",
    )
    latency["current_ms"] = 9000.0
    assert result["latency"] == {"current_ms": 1200.0}


def test_browser_command_is_converted_without_tk() -> None:
    request = browser_request(BridgeCommand("overlay", "rapido", "chrome"))
    assert request is not None
    assert request.action == "overlay"
    assert browser_request(BridgeCommand("quit", None, "chrome")) is None


def test_hotkey_dispatch_is_independent_from_gui() -> None:
    called: list[str] = []
    assert dispatch_hotkey("toggle", {"toggle": lambda: called.append("toggle")})
    assert not dispatch_hotkey("unknown", {})
    assert called == ["toggle"]
