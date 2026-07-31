from pathlib import Path

from uvt.subtitles import Cue
from uvt.workflow import RunSettings, TranslationWorkflow


def settings(source: str) -> RunSettings:
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


def test_workflow_prepares_subtitle_player(monkeypatch, tmp_path: Path) -> None:
    prepared: list[bool] = []

    class Player:
        def __init__(self, **kwargs) -> None:
            assert kwargs["cues"] == [Cue(0.0, 1.0, "hello")]

        def prepare(self) -> None:
            prepared.append(True)

    monkeypatch.setattr(
        "uvt.workflow.load_cues",
        lambda *_args, **_kwargs: [Cue(0.0, 1.0, "hello")],
    )
    monkeypatch.setattr("uvt.workflow.SubtitlePlayer", Player)
    workflow = TranslationWorkflow(
        preview=object(),  # type: ignore[arg-type]
        on_text=lambda _text: None,
        on_status=lambda _status: None,
        on_error=lambda _error: None,
    )

    result = workflow.prepare(settings(str(tmp_path / "captions.srt")))

    assert prepared == [True]
    assert result.player is not None
    assert result.progressive is None


def test_workflow_reports_remote_download_progress(monkeypatch, tmp_path: Path) -> None:
    statuses: list[str] = []
    media = tmp_path / "video.mp4"
    monkeypatch.setattr(
        "uvt.workflow.download_video",
        lambda *_args, **_kwargs: (media, False),
    )
    workflow = TranslationWorkflow(
        preview=object(),  # type: ignore[arg-type]
        on_text=lambda _text: None,
        on_status=statuses.append,
        on_error=lambda _error: None,
    )

    assert workflow.resolve_input(settings("https://example.com/video")) == media
    assert statuses[0] == "Download video: avvio…"
    assert "trascrizione locale" in statuses[-1]
    workflow.close()
