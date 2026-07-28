from unittest.mock import Mock, patch

import pytest

from uvt.ollama import OllamaError, OllamaTranslator


def test_base_url() -> None:
    translator = OllamaTranslator(url="http://127.0.0.1:11434/api/chat")
    assert translator._base_url() == "http://127.0.0.1:11434"


@patch("uvt.ollama.requests.get")
def test_missing_model_has_precise_error(get: Mock) -> None:
    get.return_value.raise_for_status.return_value = None
    get.return_value.json.return_value = {"models": [{"name": "other:latest"}]}
    with pytest.raises(OllamaError, match="ollama pull translategemma:latest"):
        OllamaTranslator()._ensure_ready()
