import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from uvt import audio_routing
from uvt import gui


def test_route_chrome_to_cable_uses_expected_command(monkeypatch) -> None:
    runner = Mock(return_value=Mock(returncode=0, stderr="", stdout=""))
    monkeypatch.setattr(audio_routing, "sound_volume_view_path", lambda: Path("tool.exe"))
    monkeypatch.setattr(audio_routing.subprocess, "run", runner)

    audio_routing.route_browser_to_cable("chrome")

    assert runner.call_args.args[0] == [
        "tool.exe", "/SetAppDefault", "CABLE Input", "all", "chrome.exe"
    ]


def test_restore_edge_uses_windows_default(monkeypatch) -> None:
    runner = Mock(return_value=Mock(returncode=0, stderr="", stdout=""))
    monkeypatch.setattr(audio_routing, "sound_volume_view_path", lambda: Path("tool.exe"))
    monkeypatch.setattr(audio_routing.subprocess, "run", runner)

    audio_routing.restore_browser_default("edge")

    assert runner.call_args.args[0][2] == "DefaultRenderDevice"
    assert runner.call_args.args[0][-1] == "msedge.exe"


def test_nonzero_exit_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(audio_routing, "sound_volume_view_path", lambda: Path("tool.exe"))
    monkeypatch.setattr(
        audio_routing.subprocess,
        "run",
        Mock(return_value=Mock(returncode=2, stderr="failed", stdout="")),
    )

    with pytest.raises(audio_routing.AudioRoutingError, match="failed"):
        audio_routing.route_browser_to_cable("firefox")


def test_unsupported_browser_is_rejected() -> None:
    with pytest.raises(audio_routing.AudioRoutingError, match="non supportato"):
        audio_routing.route_browser_to_cable("safari")


def test_gui_routes_and_restores_only_for_cable_output(monkeypatch) -> None:
    route = Mock()
    restore = Mock()
    window = SimpleNamespace(
        capture_device_var=Mock(get=Mock(return_value="CABLE Output (VB-Audio)")),
        cookies_var=Mock(get=Mock(return_value="firefox")),
        status_var=Mock(),
        _source_browser="chrome",
        _browser_audio_routed=None,
        _audio_router=Mock(route=route, restore=restore),
    )
    window._routing_browser = lambda: gui.TranslatorWindow._routing_browser(window)

    gui.TranslatorWindow._route_browser_audio(window)
    gui.TranslatorWindow._restore_browser_audio(window)
    gui.TranslatorWindow._restore_browser_audio(window)

    route.assert_called_once_with("chrome")
    restore.assert_called_once_with("chrome")
    assert window._browser_audio_routed is None


def test_gui_routing_prefers_calling_browser_over_cookie_setting() -> None:
    window = SimpleNamespace(
        _source_browser="chrome",
        cookies_var=Mock(get=Mock(return_value="firefox")),
    )

    assert gui.TranslatorWindow._routing_browser(window) == "chrome"


def test_failed_route_attempts_immediate_restore(monkeypatch) -> None:
    route = Mock(side_effect=audio_routing.AudioRoutingError("route failed"))
    restore = Mock()
    window = SimpleNamespace(
        capture_device_var=Mock(get=Mock(return_value="CABLE Output")),
        cookies_var=Mock(get=Mock(return_value="nessuno")),
        status_var=Mock(),
        _source_browser="chrome",
        _browser_audio_routed=None,
        _audio_router=Mock(route=route, restore=restore),
    )
    window._routing_browser = lambda: gui.TranslatorWindow._routing_browser(window)
    window._restore_browser_audio = lambda: (
        gui.TranslatorWindow._restore_browser_audio(window)
    )

    assert gui.TranslatorWindow._route_browser_audio(window) is False

    route.assert_called_once_with("chrome")
    restore.assert_called_once_with("chrome")
    assert window._browser_audio_routed is None


def test_failed_restore_keeps_state_for_retry(monkeypatch) -> None:
    restore = Mock(
        side_effect=[
            audio_routing.AudioRoutingError("busy"),
            None,
        ]
    )
    window = SimpleNamespace(
        status_var=Mock(),
        _browser_audio_routed="chrome",
        _audio_router=Mock(restore=restore),
    )

    gui.TranslatorWindow._restore_browser_audio(window)
    assert window._browser_audio_routed == "chrome"

    gui.TranslatorWindow._restore_browser_audio(window)
    assert window._browser_audio_routed is None
    assert restore.call_count == 2


def test_live_error_restores_audio_before_showing_dialog() -> None:
    events: list[str] = []
    window = SimpleNamespace(
        _restore_browser_audio=Mock(
            side_effect=lambda: events.append("restore")
        ),
        _show_error=Mock(side_effect=lambda _error: events.append("dialog")),
    )

    gui.TranslatorWindow._show_live_error(window, RuntimeError("failed"))

    assert events == ["restore", "dialog"]


def test_gui_selects_cable_and_voice_when_devices_are_ready() -> None:
    window = SimpleNamespace(
        capture_combo=Mock(),
        capture_device_var=Mock(),
        live_voice_var=Mock(),
        live_button=Mock(),
        status_var=Mock(),
        _browser_overlay_pending=False,
    )
    values = (
        "Audio di sistema (predefinito)",
        "Microphone",
        "CABLE Output (VB-Audio Virtual Cable)",
    )

    gui.TranslatorWindow._apply_capture_devices(window, values)

    window.capture_combo.configure.assert_called_once_with(values=values)
    window.capture_device_var.set.assert_called_once_with(values[2])
    window.live_voice_var.set.assert_not_called()
    window.live_button.configure.assert_called_once_with(state="normal")


def test_gui_starts_pending_browser_overlay_after_device_lookup() -> None:
    window = SimpleNamespace(
        capture_combo=Mock(),
        capture_device_var=Mock(),
        live_voice_var=Mock(),
        live_button=Mock(),
        status_var=Mock(),
        _browser_overlay_pending=True,
        after_idle=Mock(),
        _start_browser_overlay=Mock(),
    )

    gui.TranslatorWindow._apply_capture_devices(
        window,
        (
            "Audio di sistema (predefinito)",
            "CABLE Output (VB-Audio Virtual Cable)",
        ),
    )

    assert window._browser_overlay_pending is False
    window.after_idle.assert_called_once_with(window._start_browser_overlay)


def test_gui_does_not_autostart_overlay_without_vb_cable() -> None:
    window = SimpleNamespace(
        capture_combo=Mock(),
        capture_device_var=Mock(),
        live_voice_var=Mock(),
        live_button=Mock(),
        status_var=Mock(),
        _browser_overlay_pending=True,
        after_idle=Mock(),
        _start_browser_overlay=Mock(),
    )

    gui.TranslatorWindow._apply_capture_devices(
        window,
        ("Audio di sistema (predefinito)", "Microphone"),
    )

    assert window._browser_overlay_pending is False
    window.after_idle.assert_not_called()
    window.status_var.set.assert_called_with(
        "Avvio automatico annullato: VB-Cable non rilevato. "
        "Installa o attiva VB-Cable, poi riprova."
    )


def test_overlay_setup_failure_restores_browser_audio() -> None:
    window = SimpleNamespace(
        live=None,
        _settings=Mock(return_value=Mock()),
        _route_browser_audio=Mock(return_value=True),
        _restore_browser_audio=Mock(),
        overlay=Mock(show=Mock(side_effect=RuntimeError("setup failed"))),
        overlay_button=Mock(),
        live_button=Mock(),
    )

    with pytest.raises(RuntimeError, match="setup failed"):
        gui.TranslatorWindow._toggle_live(
            window,
            require_browser_routing=True,
        )

    window._restore_browser_audio.assert_called_once_with()
    window.live_button.configure.assert_not_called()


def test_routing_lease_is_written_before_route_command(tmp_path) -> None:
    state = tmp_path / "routing.json"
    observed: list[dict] = []
    manager = audio_routing.AudioRoutingLeaseManager(
        state,
        route_command=lambda _browser: observed.append(
            json.loads(state.read_text(encoding="utf-8"))
        ),
        restore_command=Mock(),
    )

    manager.route("chrome")

    assert observed[0]["phase"] == "pending"
    assert observed[0]["browser"] == "chrome"
    assert json.loads(state.read_text(encoding="utf-8"))["phase"] == "active"


def test_failed_route_leaves_recoverable_pending_lease(tmp_path) -> None:
    state = tmp_path / "routing.json"
    manager = audio_routing.AudioRoutingLeaseManager(
        state,
        route_command=Mock(side_effect=audio_routing.AudioRoutingError("busy")),
        restore_command=Mock(),
    )

    with pytest.raises(audio_routing.AudioRoutingError, match="busy"):
        manager.route("edge")

    lease = json.loads(state.read_text(encoding="utf-8"))
    assert lease["phase"] == "pending"
    assert lease["browser"] == "edge"


def test_recover_restores_stale_lease_and_removes_it(tmp_path) -> None:
    state = tmp_path / "routing.json"
    restored = Mock()
    manager = audio_routing.AudioRoutingLeaseManager(
        state,
        route_command=Mock(),
        restore_command=restored,
    )
    manager._write_lease(
        {
            "schema_version": 1,
            "browser": "firefox",
            "owner_pid": 123,
            "owner_token": "stale-owner",
            "phase": "active",
            "created_at": 1,
            "restore_target": "DefaultRenderDevice",
        }
    )

    assert manager.recover() is True

    restored.assert_called_once_with("firefox")
    assert not state.exists()


def test_failed_restore_keeps_persisted_lease_for_next_start(tmp_path) -> None:
    state = tmp_path / "routing.json"
    manager = audio_routing.AudioRoutingLeaseManager(
        state,
        route_command=Mock(),
        restore_command=Mock(side_effect=OSError("unavailable")),
    )
    manager._write_lease(
        {
            "schema_version": 1,
            "browser": "chrome",
            "owner_pid": 123,
            "owner_token": "stale-owner",
            "phase": "pending",
            "created_at": 1,
            "restore_target": "DefaultRenderDevice",
        }
    )

    with pytest.raises(audio_routing.AudioRoutingError, match="Ripristino audio"):
        manager.recover()

    assert state.exists()


def test_corrupt_routing_lease_never_executes_restore(tmp_path) -> None:
    state = tmp_path / "routing.json"
    state.write_text('{"browser":"chrome","phase":"active"}', encoding="utf-8")
    restored = Mock()
    manager = audio_routing.AudioRoutingLeaseManager(
        state,
        route_command=Mock(),
        restore_command=restored,
    )

    with pytest.raises(audio_routing.AudioRoutingError, match="non valido"):
        manager.recover()

    restored.assert_not_called()
