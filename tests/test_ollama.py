import json
from unittest.mock import Mock

import pytest

from uvt.ollama import (
    OllamaError,
    OllamaTranslator,
    _translation_is_valid,
)


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


def test_realtime_translation_uses_small_context_and_token_budget() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {"content": "Questa prova funziona."}
    }
    translator._session.post = Mock(return_value=response)

    assert translator.translate_realtime(
        "This test works.", "inglese"
    ) == "Questa prova funziona."
    payload = translator._session.post.call_args.kwargs["json"]
    assert payload["options"]["num_ctx"] == 1024
    assert payload["options"]["num_predict"] <= 96
    assert payload["options"]["temperature"] == 0.0


def test_realtime_translation_never_retries_short_result() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"message": {"content": '"Va bene."'}}
    translator._session.post = Mock(return_value=response)

    assert translator.translate_realtime("All right.") == "Va bene."
    assert translator._session.post.call_count == 1


def test_translate_many_fallback_keeps_original_on_errors() -> None:
    class _Translator(OllamaTranslator):
        calls = 0

        def translate(self, _text: str, _source_language: str) -> str:
            self.calls += 1
            if self.calls == 1:
                raise OllamaError("failed")
            return "Secondo"

    translator = _Translator()
    translator._ready = True
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {"content": json.dumps({"translations": ["Primo"]})}
    }
    translator._session.post = Mock(return_value=response)
    assert translator.translate_many(["First", "Second"], "auto") == [
        "First",
        "Secondo",
    ]


def test_translate_many_single_item_falls_back_to_original() -> None:
    class _Translator(OllamaTranslator):
        def translate(self, _text: str, _source_language: str) -> str:
            raise OllamaError("failed")

    translator = _Translator()

    assert translator.translate_many(["Only"], "auto") == ["Only"]


def test_translate_many_retries_untranslated_batch_item() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    first = Mock()
    first.raise_for_status.return_value = None
    first.json.return_value = {
        "message": {
            "content": json.dumps(
                {
                    "translations": [
                        "Un agente de policia britanico en Birmania regreso a Europa.",
                        "Secondo",
                    ]
                }
            )
        }
    }
    retry = Mock()
    retry.raise_for_status.return_value = None
    retry.json.return_value = {
        "message": {
            "content": "Un agente di polizia britannico in Birmania torno in Europa."
        }
    }
    translator._session.post = Mock(side_effect=[first, retry])

    assert translator.translate_many(
        [
            "Un agente de policia britanico en Birmania regreso a Europa.",
            "Second",
        ],
        "auto",
    ) == [
        "Un agente di polizia britannico in Birmania torno in Europa.",
        "Secondo",
    ]
    assert translator._session.post.call_count == 2


def test_translate_many_retries_non_italian_batch_output() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    first = Mock()
    first.raise_for_status.return_value = None
    first.json.return_value = {
        "message": {
            "content": json.dumps(
                {
                    "translations": [
                        "El prototipo local esta funcionando.",
                        "Secondo",
                    ]
                }
            )
        }
    }
    retry = Mock()
    retry.raise_for_status.return_value = None
    retry.json.return_value = {
        "message": {"content": "Il prototipo locale funziona."}
    }
    translator._session.post = Mock(side_effect=[first, retry])

    assert translator.translate_many(
        ["The local prototype is working.", "Second"], "auto"
    ) == ["Il prototipo locale funziona.", "Secondo"]
    assert translator._session.post.call_count == 2


def test_italian_source_can_remain_unchanged() -> None:
    text = "Questa frase è già scritta correttamente in italiano."

    assert _translation_is_valid(text, text, "auto")
    assert _translation_is_valid(text, text, "it")


def test_strict_retry_uses_adjacent_context() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    batch = Mock()
    batch.raise_for_status.return_value = None
    batch.json.return_value = {
        "message": {
            "content": json.dumps(
                {
                    "translations": [
                        "Prima frase.",
                        "He wrote about it in London.",
                        "Terza frase.",
                    ]
                }
            )
        }
    }
    retry = Mock()
    retry.raise_for_status.return_value = None
    retry.json.return_value = {
        "message": {"content": "Ne scrisse a Londra."}
    }
    translator._session.post = Mock(side_effect=[batch, retry])

    result = translator.translate_many(
        [
            "First sentence.",
            "He wrote about it in London.",
            "Third sentence.",
        ]
    )

    assert result == [
        "Prima frase.",
        "Ne scrisse a Londra.",
        "Terza frase.",
    ]
    retry_payload = translator._session.post.call_args_list[1].kwargs["json"]
    context = json.loads(
        retry_payload["messages"][1]["content"].split("\n", 1)[1]
    )
    assert context == {
        "previous_context": "First sentence.",
        "text_to_translate": "He wrote about it in London.",
        "following_context": "Third sentence.",
    }


def test_second_non_italian_result_is_reported_as_failed() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    batch = Mock()
    batch.raise_for_status.return_value = None
    batch.json.return_value = {
        "message": {
            "content": json.dumps(
                {"translations": ["El prototipo sigue funcionando."]}
            )
        }
    }
    retry = Mock()
    retry.raise_for_status.return_value = None
    retry.json.return_value = {
        "message": {"content": "El prototipo todavía funciona."}
    }
    translator._session.post = Mock(side_effect=[batch, retry])

    source = "The prototype is still working."
    assert translator.translate_many([source]) == [source]
    assert translator.last_failed_indices == (0,)


def test_translation_removes_only_matching_outer_quotes() -> None:
    translator = OllamaTranslator()
    translator._ready = True
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {"content": '"Il prototipo locale funziona."'}
    }
    translator._session.post = Mock(return_value=response)

    assert translator.translate_many(
        ["The local prototype is working."]
    ) == ["Il prototipo locale funziona."]
