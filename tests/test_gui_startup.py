from unittest.mock import Mock

import uvt.gui as gui


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

    window = gui.TranslatorWindow(initial_browser="chrome")

    assert window._source_browser == "chrome"
    assert window.cookies_var.get() == "nessuno"


def test_main_passes_recent_browser_request_for_automatic_overlay(
    monkeypatch,
) -> None:
    window = Mock()
    monkeypatch.setattr(gui, "TranslatorWindow", Mock(return_value=window))
    monkeypatch.setattr(gui, "claim_browser_request", Mock(return_value=True))

    result = gui.main(
        [
            "uvt://overlay?browser=chrome&requested_at=1000"
            "&request_id=123e4567-e89b-42d3-a456-426614174000"
        ]
    )

    assert result == 0
    gui.TranslatorWindow.assert_called_once_with(
        initial_browser="chrome",
        auto_start_overlay=True,
    )
    window.mainloop.assert_called_once_with()


def test_browser_request_selects_overlay_without_touching_source() -> None:
    window = Mock()

    gui.TranslatorWindow._show_browser_overlay(window)

    window.mode_notebook.select.assert_called_once_with(window.overlay_tab)
    window.file_var.set.assert_not_called()
    window.deiconify.assert_called_once_with()
    window.lift.assert_called_once_with()


def test_scheduled_browser_overlay_starts_live() -> None:
    window = Mock()
    window.live = None

    gui.TranslatorWindow._start_browser_overlay(window)

    window._show_browser_overlay.assert_called_once_with()
    window._toggle_live.assert_called_once_with(require_browser_routing=True)
    window._start.assert_not_called()


def test_main_reports_invalid_protocol_without_prefilling(monkeypatch) -> None:
    window = Mock()
    monkeypatch.setattr(gui, "TranslatorWindow", Mock(return_value=window))
    monkeypatch.setattr(gui.messagebox, "showerror", Mock())

    gui.main(["uvt://open?url=https%3A%2F%2Fexample.com"])

    gui.TranslatorWindow.assert_called_once_with(
        initial_browser=None,
        auto_start_overlay=False,
    )
    window.after_idle.assert_called_once()


def test_legacy_protocol_url_exits_without_opening_window(monkeypatch) -> None:
    monkeypatch.setattr(gui, "TranslatorWindow", Mock())

    result = gui.main(
        ["uvt://translate?url=https%3A%2F%2Fexample.com%2Fvideo"]
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
        ]
    )

    assert result == 0
    gui.TranslatorWindow.assert_not_called()
