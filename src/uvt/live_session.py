from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .cache import TranslationCache
from .live import LiveTranslator
from .ollama import resolve_live_model
from .profiles import profile_by_key
from .translation import create_translator


def build_live_translator(
    *,
    model: str,
    whisper_model: str,
    source_language: str,
    rate: int,
    profile: str,
    speech_engine: str,
    voice: str,
    speak: bool,
    capture_device: str | None,
    on_text: Callable[[str], None],
    on_status: Callable[[str], None],
    on_error: Callable[[Exception], None],
    on_metrics: Callable[[dict[str, float | int]], None],
    volume_ducker: Any = None,
    live_factory: Callable[..., LiveTranslator] | None = None,
) -> tuple[LiveTranslator, str, bool]:
    """Compose the Live pipeline outside the Tk window.

    Returns the translator, the effective Ollama model, and whether Rapido
    switched away from a large selected model. Keeping this composition pure
    makes the GUI responsible only for lifecycle and presentation.
    """
    live_model, switched = (
        resolve_live_model(model) if profile == "rapido" else (model, False)
    )
    # Il profilo Live deve essere la fonte autorevole del modello Whisper.
    # In precedenza il valore salvato nelle impostazioni poteva prevalere
    # sul profilo selezionato (per esempio Bilanciato con "medium"),
    # trasformando la trascrizione nel collo di bottiglia da 7-12 secondi.
    effective_whisper_model = profile_by_key(profile).whisper_model
    factory = live_factory or LiveTranslator
    live = factory(
        translator=create_translator(live_model),
        cache=TranslationCache(),
        whisper_model=effective_whisper_model,
        source_language=source_language,
        rate=rate,
        profile=profile,
        speech_engine=speech_engine,
        voice=voice,
        speak=speak,
        capture_device=capture_device,
        on_text=on_text,
        on_status=on_status,
        on_error=on_error,
        on_metrics=on_metrics,
        volume_ducker=volume_ducker,
    )
    return live, live_model, switched
