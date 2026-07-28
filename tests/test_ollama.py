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


def test_answer_uses_user_instruction_and_screen_context() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {"content": "La risposta è 42."}
    }
    translator._session.post = Mock(return_value=response)

    result = translator.answer(
        "Spiegami l'errore", "ValueError alla riga 42"
    )

    assert result == "La risposta è 42."
    payload = translator._session.post.call_args.kwargs["json"]
    prompt = payload["messages"][1]["content"]
    assert "Spiegami l'errore" in prompt
    assert "ValueError alla riga 42" in prompt


def test_answer_includes_recent_memory() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"message": {"content": "Continuazione"}}
    translator._session.post = Mock(return_value=response)

    translator.answer(
        "Continua",
        "Nuovo testo",
        history=[("Domanda precedente", "Risposta precedente")],
    )

    messages = translator._session.post.call_args.kwargs["json"]["messages"]
    assert any("Domanda precedente" in item["content"] for item in messages)
    assert any("Risposta precedente" in item["content"] for item in messages)
