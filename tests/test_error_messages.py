from __future__ import annotations

from uvt.audio_routing import AudioRoutingError
from uvt.documents import DocumentTranslationError
from uvt.error_messages import present_error
from uvt.ollama import OllamaError


def test_missing_whisper_has_an_actionable_message() -> None:
    error = ModuleNotFoundError("No module named 'faster_whisper'")
    error.name = "faster_whisper"

    presentation = present_error(error)

    assert presentation.title == "Trascrizione non disponibile"
    assert "INSTALL_WINDOWS.bat" in presentation.message


def test_known_operational_errors_do_not_expose_internal_details() -> None:
    ollama = present_error(OllamaError("HTTP 500 internal payload"))
    routing = present_error(AudioRoutingError("process 1234 failed"))

    assert "HTTP 500" not in ollama.message
    assert "process 1234" not in routing.message
    assert "VB-Cable" in routing.message


def test_document_error_preserves_useful_problem_description() -> None:
    presentation = present_error(
        DocumentTranslationError("Formato non supportato: .pages")
    )

    assert presentation.title == "Documento non tradotto"
    assert ".pages" in presentation.message


def test_unknown_error_points_to_diagnostics() -> None:
    presentation = present_error(RuntimeError("secret implementation detail"))

    assert "secret implementation detail" not in presentation.message
    assert "diagnostica" in presentation.message.casefold()
