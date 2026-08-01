from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from uvt.controllers import (
    DocumentTranslationController,
    MediaExportController,
)
from uvt.session import SessionMode, SessionPhase, TranslationSession


def test_document_controller_owns_translation_lifecycle(
    monkeypatch, tmp_path: Path
) -> None:
    session = TranslationSession()
    controller = DocumentTranslationController(session)
    translated = tmp_path / "translated.txt"
    document_translator = Mock()
    document_translator.translate.return_value = translated
    monkeypatch.setattr(
        "uvt.controllers.DocumentTranslator",
        Mock(return_value=document_translator),
    )
    monkeypatch.setattr("uvt.controllers.OllamaTranslator", Mock())

    run_id = controller.begin()
    result = controller.translate(
        tmp_path / "source.txt",
        translated,
        language="auto",
        model="test:latest",
        run_id=run_id,
    )

    assert result == translated
    assert session.mode is SessionMode.DOCUMENT
    assert session.phase is SessionPhase.PREPARING
    assert document_translator.translate.call_args.kwargs["cancel"] is controller.cancel


def test_document_controller_cancels_and_finishes_session() -> None:
    session = TranslationSession()
    controller = DocumentTranslationController(session)
    controller.begin()

    controller.request_stop()

    assert controller.cancelled
    assert session.phase is SessionPhase.STOPPING
    controller.finish()
    assert session.phase is SessionPhase.IDLE


def test_media_export_controller_delegates_audio_and_video(
    tmp_path: Path,
) -> None:
    workflow = Mock()
    audio = tmp_path / "voice.wav"
    video = tmp_path / "dubbed.mp4"
    workflow.export_audio.return_value = audio
    workflow.export_video.return_value = video
    controller = MediaExportController(workflow)
    settings = Mock()
    progress = Mock()
    warning = Mock()

    assert controller.export_audio(
        audio, settings, on_progress=progress, on_warning=warning
    ) == audio
    assert controller.export_video(
        video, settings, on_progress=progress, on_warning=warning
    ) == video
    workflow.export_audio.assert_called_once_with(
        audio,
        settings,
        on_progress=progress,
        on_warning=warning,
    )
    workflow.export_video.assert_called_once_with(
        video,
        settings,
        on_progress=progress,
        on_warning=warning,
    )
