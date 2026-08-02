from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from langdetect import LangDetectException, detect

from .ollama import OllamaError, OllamaTranslator


ARGOS_MODEL = "argos:offline"
_LANGUAGE_CODES = {
    "inglese": "en",
    "spagnolo": "es",
    "francese": "fr",
    "tedesco": "de",
    "italiano": "it",
}


class TranslationEngine(Protocol):
    model: str

    @property
    def cache_key(self) -> str: ...

    @property
    def last_failed_indices(self) -> tuple[int, ...]: ...

    def warmup(self) -> None: ...

    def translate(self, text: str, source_language: str = "auto") -> str: ...

    def translate_realtime(
        self, text: str, source_language: str = "auto"
    ) -> str: ...

    def translate_many(
        self, texts: list[str], source_language: str = "auto"
    ) -> list[str]: ...


class ArgosError(RuntimeError):
    pass


@dataclass(slots=True)
class ArgosTranslator:
    model: str = ARGOS_MODEL
    _last_failed_indices: tuple[int, ...] = field(
        default=(), init=False, repr=False
    )

    @property
    def cache_key(self) -> str:
        return self.model

    @property
    def last_failed_indices(self) -> tuple[int, ...]:
        return self._last_failed_indices

    @staticmethod
    def available() -> bool:
        try:
            import argostranslate.translate as argos_translate

            languages = argos_translate.get_installed_languages()
            italian = next(
                (language for language in languages if language.code == "it"),
                None,
            )
            if italian is None:
                return False
            return any(
                language.code != "it"
                and language.get_translation(italian) is not None
                for language in languages
            )
        except (ImportError, OSError):
            return False

    @staticmethod
    def _source_code(text: str, source_language: str) -> str:
        selected = source_language.strip().casefold()
        if selected not in {"", "auto"}:
            return _LANGUAGE_CODES.get(selected, selected)
        try:
            return detect(text)
        except LangDetectException as error:
            raise ArgosError(
                "Lingua sorgente non riconosciuta da Argos. "
                "Selezionala nelle impostazioni avanzate."
            ) from error

    def warmup(self) -> None:
        if not self.available():
            raise ArgosError(
                "Argos o i pacchetti verso l'italiano non sono installati. "
                "Esegui INSTALLA_MOTORI_OPZIONALI_WINDOWS.bat -Argos."
            )

    def translate(self, text: str, source_language: str = "auto") -> str:
        if not text.strip():
            return text
        try:
            import argostranslate.translate as argos_translate
        except ImportError as error:
            raise ArgosError(
                "Argos Translate non installato. Esegui "
                "INSTALLA_MOTORI_OPZIONALI_WINDOWS.bat -Argos."
            ) from error
        source_code = self._source_code(text, source_language)
        if source_code == "it":
            return text
        try:
            translated = argos_translate.translate(text, source_code, "it")
        except Exception as error:
            raise ArgosError(
                f"Pacchetto Argos {source_code}→it non disponibile. "
                "Installa i modelli opzionali e riprova."
            ) from error
        if not translated.strip() or translated.strip() == text.strip():
            raise ArgosError(
                f"Argos non ha tradotto il testo da {source_code} a italiano."
            )
        return translated.strip()

    def translate_realtime(
        self, text: str, source_language: str = "auto"
    ) -> str:
        return self.translate(text, source_language)

    def translate_many(
        self, texts: list[str], source_language: str = "auto"
    ) -> list[str]:
        translated: list[str] = []
        failed: list[int] = []
        for index, text in enumerate(texts):
            try:
                translated.append(self.translate(text, source_language))
            except ArgosError:
                translated.append(text)
                failed.append(index)
        self._last_failed_indices = tuple(failed)
        return translated


@dataclass(slots=True)
class FallbackTranslator:
    primary: OllamaTranslator
    fallback: ArgosTranslator
    _last_failed_indices: tuple[int, ...] = field(
        default=(), init=False, repr=False
    )

    @property
    def model(self) -> str:
        return self.primary.model

    @property
    def cache_key(self) -> str:
        return f"{self.primary.cache_key}|fallback:{self.fallback.cache_key}"

    @property
    def last_failed_indices(self) -> tuple[int, ...]:
        return self._last_failed_indices

    def warmup(self) -> None:
        try:
            self.primary.warmup()
        except (OllamaError, OSError):
            self.fallback.warmup()

    def translate(self, text: str, source_language: str = "auto") -> str:
        try:
            return self.primary.translate(text, source_language)
        except OllamaError:
            return self.fallback.translate(text, source_language)

    def translate_realtime(
        self, text: str, source_language: str = "auto"
    ) -> str:
        try:
            return self.primary.translate_realtime(text, source_language)
        except OllamaError:
            return self.fallback.translate_realtime(text, source_language)

    def translate_many(
        self, texts: list[str], source_language: str = "auto"
    ) -> list[str]:
        results = self.primary.translate_many(texts, source_language)
        failed = set(self.primary.last_failed_indices)
        if not failed:
            self._last_failed_indices = ()
            return results
        unresolved: list[int] = []
        for index in failed:
            try:
                results[index] = self.fallback.translate(
                    texts[index], source_language
                )
            except ArgosError:
                unresolved.append(index)
        self._last_failed_indices = tuple(sorted(unresolved))
        return results


def create_translator(model: str) -> TranslationEngine:
    selected = model.strip() or "translategemma:latest"
    if selected.casefold() == ARGOS_MODEL:
        return ArgosTranslator()
    ollama = OllamaTranslator(model=selected)
    if ArgosTranslator.available():
        return FallbackTranslator(ollama, ArgosTranslator())
    return ollama
