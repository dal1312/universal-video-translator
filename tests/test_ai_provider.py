from unittest.mock import Mock

import pytest

from uvt.ai_provider import (
    AIProviderError,
    OpenAICompatibleAssistant,
    create_assistant_client,
)
from uvt.ollama import OllamaTranslator


def test_create_ollama_assistant() -> None:
    client = create_assistant_client(
        "Ollama", "", ollama_model="qwen3:4b"
    )
    assert isinstance(client, OllamaTranslator)
    assert client.model == "qwen3:4b"


def test_lm_studio_resolves_loaded_model() -> None:
    client = OpenAICompatibleAssistant(
        provider="LM Studio",
        base_url="http://127.0.0.1:1234/v1",
    )
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": [{"id": "local-model"}]}
    client._session.get = Mock(return_value=response)

    assert client._resolve_model() == "local-model"


def test_openai_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AIProviderError, match="OPENAI_API_KEY"):
        create_assistant_client(
            "OpenAI", "model", ollama_model="qwen3:4b"
        )
