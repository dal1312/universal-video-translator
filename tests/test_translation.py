import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

from uvt.translation import (
    ARGOS_MODEL,
    ArgosError,
    ArgosTranslator,
    FallbackTranslator,
    create_translator,
)


def test_argos_translator_uses_selected_source_language(monkeypatch) -> None:
    translate = Mock(return_value="Buongiorno")
    module = SimpleNamespace(translate=translate)
    package = ModuleType("argostranslate")
    package.__path__ = []  # type: ignore[attr-defined]
    package.translate = module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "argostranslate", package)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", module)

    translator = ArgosTranslator()

    assert translator.translate("Good morning", "inglese") == "Buongiorno"
    translate.assert_called_once_with("Good morning", "en", "it")


def test_argos_many_preserves_failed_segments() -> None:
    class PartialArgos(ArgosTranslator):
        responses = iter(("Uno", ArgosError("missing")))

        def translate(self, text: str, source_language: str = "auto") -> str:
            response = next(self.responses)
            if isinstance(response, Exception):
                raise response
            return response

    translator = PartialArgos()

    assert translator.translate_many(["One", "Two"], "inglese") == [
        "Uno",
        "Two",
    ]
    assert translator.last_failed_indices == (1,)


def test_fallback_replaces_only_failed_ollama_results() -> None:
    primary = Mock(
        model="test",
        cache_key="test-cache",
        last_failed_indices=(1,),
    )
    primary.translate_many.return_value = ["Uno", "Two"]
    fallback = Mock(cache_key=ARGOS_MODEL)
    fallback.translate.return_value = "Due"
    translator = FallbackTranslator(primary, fallback)

    assert translator.translate_many(["One", "Two"], "inglese") == [
        "Uno",
        "Due",
    ]
    assert translator.last_failed_indices == ()


def test_factory_selects_explicit_argos() -> None:
    assert isinstance(create_translator(ARGOS_MODEL), ArgosTranslator)
