from types import SimpleNamespace
from unittest.mock import Mock

import uvt.gui as gui
from uvt.session import SessionMode, TranslationSession
from uvt.settings import AppSettings


class _OwnerBroker:
    activated = False

    def acquire(self) -> bool:
        return True

    def activate(self) -> None:
        self.activated = True

    def close(self) -> None:
        pass

    def begin_shutdown(self) -> None:
        pass

    def drain_events(self) -> list:
        return []


class _PromotedBroker(_OwnerBroker):
    def __init__(self) -> None:
        self.is_owner = False
        self.acquire_calls = 0

    def acquire(self) -> bool:
        self.acquire_calls += 1
        if self.acquire_calls >= 2:
            self.is_owner = True
        return self.is_owner

    def forward_overlay(self, _uri: str) -> bool:
        return False


def test_browser_request_does_not_enable_browser_cookies_automatically(
    monkeypatch,
) -> None:
    class FakeVariable:
        def __init__(self, value=None, **_kwargs) -> None:
            self.value = value

        def get(self):
            return self.value

        def set(self, value) -> None:
            self.value = value

    monkeypatch.setattr(gui.tk.Tk, "__init__", lambda _self: None)
    monkeypatch.setattr(gui.TranslatorWindow, "title", Mock())
    monkeypatch.setattr(gui.TranslatorWindow, "geometry", Mock())
    monkeypatch.setattr(gui.TranslatorWindow, "minsize", Mock())
    monkeypatch.setattr(gui.TranslatorWindow, "protocol", Mock())
    monkeypatch.setattr(gui.tk, "StringVar", FakeVariable)
    monkeypatch.setattr(gui.tk, "IntVar", FakeVariable)
    monkeypatch.setattr(gui.tk, "BooleanVar", FakeVariable)
    monkeypatch.setattr(gui, "MediaPreview", Mock())
    monkeypatch.setattr(gui, "SubtitleOverlay", Mock())
    monkeypatch.setattr(gui.TranslatorWindow, "_configure_theme", Mock())
    monkeypatch.setattr(gui.TranslatorWindow, "_build", Mock())
    monkeypatch.setattr(
        gui.threading,
        "Thread",
        Mock(return_value=Mock(start=Mock())),
    )

    store = Mock(load=Mock(return_value=AppSettings()))
    window = gui.TranslatorWindow(
        initial_browser="chrome",
        settings_store=store,
    )

    assert window._source_browser == "chrome"
    assert window.cookies_var.get() == "nessuno"


def test_main_passes_recent_browser_request_for_automatic_overlay(
    monkeypatch,
) -> None:
    window = Mock()
    broker = _OwnerBroker()
    monkeypatch.setattr(gui, "TranslatorWindow", Mock(return_value=window))
    monkeypatch.setattr(gui, "claim_browser_request", Mock(return_value=True))

    result = gui.main(
        [
            "uvt://overlay?browser=chrome&requested_at=1000"
            "&request_id=123e4567-e89b-42d3-a456-426614174000"
        ],
        broker=broker,
        audio_router=Mock(recover=Mock(return_value=False)),
    )

    assert result == 0
    call = gui.TranslatorWindow.call_args
    assert call.kwargs["initial_browser"] == "chrome"
    assert call.kwargs["auto_start_overlay"] is True
    assert call.kwargs["instance_broker"] is broker
    window.mainloop.assert_called_once_with()


def test_main_becomes_owner_when_previous_instance_stops_before_forward(
    monkeypatch,
) -> None:
    window = Mock()
    broker = _PromotedBroker()
    monkeypatch.setattr(gui, "TranslatorWindow", Mock(return_value=window))
    monkeypatch.setattr(gui, "claim_browser_request", Mock(return_value=True))
    monkeypatch.setattr(gui.time, "sleep", Mock())

    result = gui.main(
        [
            "uvt://overlay?browser=chrome&requested_at=1000"
            "&request_id=123e4567-e89b-42d3-a456-426614174000"
        ],
        broker=broker,
        audio_router=Mock(recover=Mock(return_value=False)),
    )

    assert result == 0
    assert broker.acquire_calls == 2
    assert broker.activated
    window.mainloop.assert_called_once_with()


def test_main_reports_forward_failure_instead_of_silent_success(
    monkeypatch,
) -> None:
    broker = _PromotedBroker()
    broker.acquire = Mock(return_value=False)
    times = iter((0.0, 4.0))
    monkeypatch.setattr(gui.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(gui, "TranslatorWindow", Mock())

    result = gui.main(
        [
            "uvt://overlay?browser=chrome&requested_at=1000"
            "&request_id=123e4567-e89b-42d3-a456-426614174000"
        ],
        broker=broker,
        audio_router=Mock(recover=Mock(return_value=False)),
    )

    assert result == 1
    gui.TranslatorWindow.assert_not_called()


def test_browser_request_selects_overlay_without_touching_source() -> None:
    window = Mock()

    gui.TranslatorWindow._show_browser_overlay(window)

    window._select_source_mode.assert_called_once_with("live")
    window.file_var.set.assert_not_called()
    window.deiconify.assert_called_once_with()
    window.lift.assert_called_once_with()


def test_background_browser_overlay_does_not_focus_desktop() -> None:
    window = Mock()

    gui.TranslatorWindow._show_browser_overlay(window, False)

    window._select_source_mode.assert_called_once_with("live")
    window.deiconify.assert_not_called()
    window.lift.assert_not_called()
    window.focus_force.assert_not_called()


def test_source_selector_shows_one_pipeline() -> None:
    window = SimpleNamespace(
        session=TranslationSession(),
        source_mode_var=Mock(),
        video_tab=Mock(),
        overlay_tab=Mock(),
        file_mode_button=Mock(),
        live_mode_button=Mock(),
        status_var=Mock(),
    )

    gui.TranslatorWindow._select_source_mode(window, "live")

    window.source_mode_var.set.assert_called_once_with("live")
    window.video_tab.grid_remove.assert_called_once_with()
    window.overlay_tab.grid.assert_called_once_with()


def test_source_selector_does_not_switch_active_session() -> None:
    session = TranslationSession()
    session.begin(SessionMode.FILE)
    window = SimpleNamespace(
        session=session,
        source_mode_var=Mock(),
        video_tab=Mock(),
        overlay_tab=Mock(),
        file_mode_button=Mock(),
        live_mode_button=Mock(),
        status_var=Mock(),
    )

    gui.TranslatorWindow._select_source_mode(window, "live")

    window.source_mode_var.set.assert_not_called()
    window.overlay_tab.grid.assert_not_called()
    window.status_var.set.assert_called_once()


def test_scheduled_browser_overlay_starts_live() -> None:
    window = Mock()
    window.live = None

    gui.TranslatorWindow._start_browser_overlay(window)

    window._show_browser_overlay.assert_called_once_with(False)
    window._toggle_live.assert_called_once_with(require_browser_routing=True)
    window._start.assert_not_called()


def test_main_reports_invalid_protocol_without_prefilling(monkeypatch) -> None:
    window = Mock()
    monkeypatch.setattr(gui, "TranslatorWindow", Mock(return_value=window))
    monkeypatch.setattr(gui.messagebox, "showerror", Mock())

    gui.main(
        ["uvt://open?url=https%3A%2F%2Fexample.com"],
        broker=_OwnerBroker(),
        audio_router=Mock(recover=Mock(return_value=False)),
    )

    call = gui.TranslatorWindow.call_args
    assert call.kwargs["initial_browser"] is None
    assert call.kwargs["auto_start_overlay"] is False
    window.after_idle.assert_called_once()


def test_legacy_protocol_url_exits_without_opening_window(monkeypatch) -> None:
    monkeypatch.setattr(gui, "TranslatorWindow", Mock())

    result = gui.main(
        ["uvt://translate?url=https%3A%2F%2Fexample.com%2Fvideo"],
        broker=_OwnerBroker(),
        audio_router=Mock(recover=Mock(return_value=False)),
    )

    assert result == 0
    gui.TranslatorWindow.assert_not_called()


def test_replayed_protocol_request_exits_without_opening_window(
    monkeypatch,
) -> None:
    monkeypatch.setattr(gui, "TranslatorWindow", Mock())
    monkeypatch.setattr(gui, "claim_browser_request", Mock(return_value=False))

    result = gui.main(
        [
            "uvt://overlay?browser=chrome&requested_at=1000"
            "&request_id=123e4567-e89b-42d3-a456-426614174000"
        ],
        broker=_OwnerBroker(),
        audio_router=Mock(recover=Mock(return_value=False)),
    )

    assert result == 0
    gui.TranslatorWindow.assert_not_called()
