import pytest

from uvt.session import (
    SessionConflictError,
    SessionMode,
    SessionPhase,
    TranslationSession,
)


def test_session_runs_one_mode_at_a_time() -> None:
    session = TranslationSession()

    run_id = session.begin(SessionMode.FILE)

    assert session.phase is SessionPhase.PREPARING
    assert session.activate(SessionMode.FILE, run_id)
    assert session.phase is SessionPhase.RUNNING
    with pytest.raises(SessionConflictError):
        session.begin(SessionMode.LIVE)


def test_finishing_session_invalidates_late_callbacks() -> None:
    session = TranslationSession()
    run_id = session.begin(SessionMode.FILE)

    session.begin_stopping(SessionMode.FILE)
    session.finish(SessionMode.FILE)

    assert session.phase is SessionPhase.IDLE
    assert not session.accepts(SessionMode.FILE, run_id)
    assert not session.activate(SessionMode.FILE, run_id)


def test_session_tracks_pause_and_error() -> None:
    session = TranslationSession()
    run_id = session.begin(SessionMode.LIVE)
    session.activate(SessionMode.LIVE, run_id)

    session.set_paused(True)
    assert session.phase is SessionPhase.PAUSED
    session.set_paused(False)
    assert session.phase is SessionPhase.RUNNING
    session.fail(SessionMode.LIVE, run_id)
    assert session.phase is SessionPhase.ERROR
    assert not session.busy
