"""Service layer for business logic."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..cache import TranslationCache
from ..ollama import OllamaTranslator
from ..subtitles import Cue


class TranslatorService(Protocol):
    """Interfaccia per il servizio di traduzione."""

    def translate(self, text: str, source_language: str) -> str: ...
    def list_models(self) -> list[str]: ...


class TranslationService:
    """Servizio di traduzione che gestisce cache e modello Ollama."""

    def __init__(
        self,
        model: str = "translategemma:latest",
        cache: TranslationCache | None = None,
    ) -> None:
        self.translator = OllamaTranslator(model=model)
        self.cache = cache or TranslationCache()
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def translate(self, text: str, source_language: str) -> str:
        """Traduce un testo usando la cache se disponibile."""
        cached = self.cache.get(self._model, source_language, text)
        if cached is not None:
            return cached
        translated = self.translator.translate(text, source_language)
        self.cache.put(self._model, source_language, text, translated)
        return translated

    def list_models(self) -> list[str]:
        """Restituisce la lista dei modelli disponibili."""
        return self.translator.list_models()

    def pretranslate_cues(
        self,
        cues: list[Cue],
        source_language: str,
        on_progress: callable | None = None,
    ) -> dict[str, str]:
        """Pre-traduce tutti i cue e restituisce un dizionario delle traduzioni."""
        translations: dict[str, str] = {}
        total = len(cues)
        for position, cue in enumerate(cues, start=1):
            translated = self.cache.get(self._model, source_language, cue.text)
            if translated is None:
                translated = self.translator.translate(cue.text, source_language)
                self.cache.put(self._model, source_language, cue.text, translated)
            translations[cue.text] = translated
            if on_progress:
                on_progress(position, total)
        return translations
