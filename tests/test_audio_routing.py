from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from uvt import audio_routing
from uvt import gui


def test_route_firefox_to_cable_uses_expected_command(monkeypatch) -> None:
    runner = Mock(return_value=Mock(returncode=0, stderr="", stdout=""))
    monkeypatch.setattr(audio_routing, "sound_volume_view_path", lambda: Path("tool.exe"))
    monkeypatch.setattr(audio_routing.subprocess, "run", runner)

    audio_routing.route_firefox_to_cable()

    assert runner.call_args.args[0] == [
        "tool.exe", "/SetAppDefault", "CABLE Input", "all", "firefox.exe"
    ]


def test_restore_firefox_uses_windows_default(monkeypatch) -> None:
    runner = Mock(return_value=Mock(returncode=0, stderr="", stdout=""))
    monkeypatch.setattr(audio_routing, "sound_volume_view_path", lambda: Path("tool.exe"))
    monkeypatch.setattr(audio_routing.subprocess, "run", runner)

    audio_routing.restore_firefox_default()

    assert runner.call_args.args[0][2] == "DefaultRenderDevice"


def test_nonzero_exit_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(audio_routing, "sound_volume_view_path", lambda: Path("tool.exe"))
    monkeypatch.setattr(
        audio_routing.subprocess,
        "run",
        Mock(return_value=Mock(returncode=2, stderr="failed", stdout="")),
    )

    with pytest.raises(audio_routing.AudioRoutingError, match="failed"):
        audio_routing.route_firefox_to_cable()


def test_gui_routes_and_restores_only_for_cable_output(monkeypatch) -> None:
    route = Mock()
    restore = Mock()
    monkeypatch.setattr(gui, "route_firefox_to_cable", route)
    monkeypatch.setattr(gui, "restore_firefox_default", restore)
    window = SimpleNamespace(
        capture_device_var=Mock(get=Mock(return_value="CABLE Output (VB-Audio)")),
        status_var=Mock(),
        _firefox_audio_routed=False,
    )

    gui.TranslatorWindow._route_firefox_audio(window)
    gui.TranslatorWindow._restore_firefox_audio(window)
    gui.TranslatorWindow._restore_firefox_audio(window)

    route.assert_called_once_with()
    restore.assert_called_once_with()
    assert window._firefox_audio_routed is False


def test_gui_selects_cable_and_voice_when_devices_are_ready() -> None:
    window = SimpleNamespace(
        capture_combo=Mock(),
        capture_device_var=Mock(),
        live_voice_var=Mock(),
        live_button=Mock(),
        status_var=Mock(),
    )
    values = (
        "Audio di sistema (predefinito)",
        "Microphone",
        "CABLE Output (VB-Audio Virtual Cable)",
    )

    gui.TranslatorWindow._apply_capture_devices(window, values)

    window.capture_combo.configure.assert_called_once_with(values=values)
    window.capture_device_var.set.assert_called_once_with(values[2])
    window.live_voice_var.set.assert_called_once_with(True)
    window.live_button.configure.assert_called_once_with(state="normal")
