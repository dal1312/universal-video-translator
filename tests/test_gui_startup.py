from unittest.mock import Mock

import uvt.gui as gui


def test_main_passes_browser_url_for_automatic_startup(monkeypatch) -> None:
    window = Mock()
    monkeypatch.setattr(gui, "TranslatorWindow", Mock(return_value=window))

    result = gui.main(
        ["uvt://translate?url=https%3A%2F%2Fexample.com%2Fvideo"]
    )

    assert result == 0
    gui.TranslatorWindow.assert_called_once_with(
        initial_url="https://example.com/video"
    )
    window.mainloop.assert_called_once_with()


def test_browser_url_schedules_video_start() -> None:
    window = Mock()

    gui.TranslatorWindow._open_browser_video(
        window, "https://example.com/video"
    )

    window.file_var.set.assert_called_once_with("https://example.com/video")
    window.after_idle.assert_called_once_with(window._start_browser_video)


def test_scheduled_browser_video_focuses_and_starts() -> None:
    window = Mock()

    gui.TranslatorWindow._start_browser_video(window)

    window._focus_browser_url.assert_called_once_with()
    window._start.assert_called_once_with()


def test_main_reports_invalid_protocol_without_prefilling(monkeypatch) -> None:
    window = Mock()
    monkeypatch.setattr(gui, "TranslatorWindow", Mock(return_value=window))
    monkeypatch.setattr(gui.messagebox, "showerror", Mock())

    gui.main(["uvt://open?url=https%3A%2F%2Fexample.com"])

    gui.TranslatorWindow.assert_called_once_with(initial_url=None)
    window.after_idle.assert_called_once()
