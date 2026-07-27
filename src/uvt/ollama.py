from __future__ import annotations

from dataclasses import dataclass

import requests


class OllamaError(RuntimeError):
    pass


@dataclass(slots=True)
class OllamaTranslator:
    model: str = "qwen3:4b"
    url: str = "http://127.0.0.1:11434/api/chat"
    timeout: float = 90.0

    def translate(self, text: str, source_language: str = "auto") -> str:
        prompt = (
            "Traduci il testo seguente in italiano naturale e parlato, adatto al "
            "doppiaggio video. Mantieni significato, tono e brevità. Restituisci "
            "soltanto la traduzione, senza note o prefissi.\n"
            f"Lingua originale: {source_language}\nTesto: {text}"
        )
        try:
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {"temperature": 0.2},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            translated = response.json()["message"]["content"].strip()
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise OllamaError(
                "Ollama non risponde correttamente. Verifica che sia attivo e "
                f"che il modello {self.model!r} sia installato."
            ) from exc
        if not translated:
            raise OllamaError("Ollama ha restituito una traduzione vuota.")
        return translated
