from types import SimpleNamespace
from unittest.mock import Mock

from uvt import gui
from uvt.controllers import FileTranslationController, LiveTranslationController
from uvt.session import SessionMode, SessionPhase, TranslationSession
from uvt.workflow import PreparedPlayback, RunSettings


def run_settings(source: str = "captions.srt") -> RunSettings:
    return RunSettings(
        source=source,
        ollama_model="test",
        whisper_model="tiny",
        language="auto",
        rate=185,
        speech_engine="windows",
        voice="default",
        cookies_browser=None,
    )


def test_starting_file_stops_live_mode_first() -> None:
    settings = run_settings()
    window = SimpleNamespace(
        _settings=Mock(return_value=settings),
        _stop_live_mode=Mock(return_value=True),
        _select_source_mode=Mock(),
        session=TranslationSession(),
        _file_run_id=0,
        start_button=Mock(),
        live_button=Mock(),
        status_var=Mock(),
        _start_worker=Mock(),
        _prepare=Mock(),
    )
    window.file_controller = FileTranslationController(
        window.session, Mock()
    )

    gui.TranslatorWindow._start(window)

    window._stop_live_mode.assert_called_once_with()
    assert window.session.mode is SessionMode.FILE
    assert window.session.phase is SessionPhase.PREPARING
    window.live_button.configure.assert_called_once_with(state="disabled")
    window._start_worker.assert_called_once_with(
        window._prepare,
        settings,
        1,
        name="uvt-prepare",
    )


def test_starting_live_stops_file_mode_first(monkeypatch) -> None:
    events: list[str] = []
    session = TranslationSession()
    session.begin(SessionMode.FILE)

    def stop_file() -> None:
        events.append("file-stop")
        session.finish(SessionMode.FILE)

    class FakeLive:
        running = True

        def __init__(self, **_kwargs) -> None:
            pass

        def start(self) -> None:
            events.append("live-start")

    monkeypatch.setattr(gui, "LiveTranslator", FakeLive)
    window = SimpleNamespace(
        live=None,
        _stop=Mock(side_effect=stop_file),
        _select_source_mode=Mock(),
        session=session,
        _live_run_id=0,
        _settings=Mock(return_value=run_settings()),
        _route_browser_audio=Mock(return_value=False),
        _restore_browser_audio=Mock(),
        _sync_mode_controls=Mock(),
        overlay=Mock(),
        overlay_button=Mock(),
        live_button=Mock(),
        live_voice_var=Mock(get=Mock(return_value=False)),
        capture_device_var=Mock(
            get=Mock(return_value="Audio di sistema (predefinito)")
        ),
        after=Mock(),
        profile_var=Mock(get=Mock(return_value="Rapido")),
        auto_ducking_var=Mock(get=Mock(return_value=False)),
        browser_audio_controller=Mock(),
    )
    window.live_controller = LiveTranslationController(session)

    gui.TranslatorWindow._toggle_live(window)

    assert events == ["file-stop", "live-start"]
    window.live_button.configure.assert_called_with(text="Stop Overlay OS")


def test_late_file_preparation_is_discarded() -> None:
    player = Mock()
    prepared = PreparedPlayback(player=player)
    window = SimpleNamespace(
        workflow=Mock(prepare=Mock(return_value=prepared)),
        session=TranslationSession(run_id=2),
        _closing=False,
        _file_run_id=2,
        _discard_prepared=gui.TranslatorWindow._discard_prepared,
        _call_in_ui=Mock(),
    )
    window.file_controller = FileTranslationController(
        window.session, window.workflow
    )

    gui.TranslatorWindow._prepare(window, run_settings(), 1)

    player.stop.assert_called_once_with()
    window._call_in_ui.assert_not_called()


def test_stale_live_status_does_not_replace_file_status() -> None:
    session = TranslationSession()
    session.begin(SessionMode.FILE)
    window = SimpleNamespace(
        session=session,
        _live_run_id=0,
        live=Mock(),
        status_var=Mock(),
        live_button=Mock(),
        _restore_browser_audio=Mock(),
        _sync_mode_controls=Mock(),
    )

    gui.TranslatorWindow._set_live_status(window, "Overlay OS interrotto")

    window.status_var.set.assert_not_called()
    assert window.live is None
    window._restore_browser_audio.assert_called_once_with()
