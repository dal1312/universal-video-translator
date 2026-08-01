from __future__ import annotations

from uvt.readiness import ComponentStatus, SystemReadiness


def test_readiness_reports_complete_system() -> None:
    readiness = SystemReadiness(
        (
            ComponentStatus("ollama", "Ollama", True, "traduzione"),
            ComponentStatus("ffmpeg", "FFmpeg", True, "media"),
        )
    )

    assert readiness.core_ready
    assert readiness.missing == ()
    assert readiness.summary() == "Sistema pronto"


def test_readiness_distinguishes_required_and_optional_components() -> None:
    incomplete = SystemReadiness(
        (
            ComponentStatus("ollama", "Ollama", False, "traduzione"),
            ComponentStatus("ffmpeg", "FFmpeg", True, "media"),
        )
    )
    optional = SystemReadiness(
        (
            ComponentStatus("ollama", "Ollama", True, "traduzione"),
            ComponentStatus("ffmpeg", "FFmpeg", True, "media"),
            ComponentStatus("kokoro", "Kokoro", False, "voce neurale"),
        )
    )

    assert incomplete.summary() == "Configurazione incompleta: Ollama"
    assert optional.summary() == "Componenti opzionali mancanti: Kokoro"
    assert not optional.available("kokoro")
