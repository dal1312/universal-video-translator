import json
from unittest.mock import Mock

import pytest

from uvt.ollama import OllamaError, OllamaTranslator


def test_base_url() -> None:
    translator = OllamaTranslator(url="http://127.0.0.1:11434/api/chat")
    assert translator._base_url() == "http://127.0.0.1:11434"


def test_missing_model_has_precise_error() -> None:
    translator = OllamaTranslator()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"models": [{"name": "other:latest"}]}
    translator._session.get = Mock(return_value=response)
    with pytest.raises(OllamaError, match="ollama pull translategemma:latest"):
        translator._ensure_ready()


def test_translate_many_keeps_order() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {
            "content": json.dumps(
                {"translations": ["Primo", "Secondo"]}
            )
        }
    }
    translator._session.post = Mock(return_value=response)

    assert translator.translate_many(["First", "Second"]) == [
        "Primo",
        "Secondo",
    ]
    assert translator._session.post.call_count == 1


def test_translate_many_fallback_keeps_original_on_partial_batch_or_errors() -> None:
    class _Translator(OllamaTranslator):
        translate_calls: int = 0

        def translate(self, text: str, _source_language: str) -> str:
            self.translate_calls += 1
            if self.translate_calls == 1:
                raise OllamaError("failed")
            return "Secondo"

    translator = _Translator()
    translator._ready = True
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {
            "content": json.dumps({"translations": ["Primo"]})
        }
    }
    translator._session.post = Mock(return_value=response)

    translator.translate = Mock(side_effect=[OllamaError("failed"), "Secondo"])

    assert translator.translate_many(["First", "Second"], "auto") == [
        "First",
        "Secondo",
    ]
