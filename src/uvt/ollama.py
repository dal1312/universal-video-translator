from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests


class OllamaError(RuntimeError):
    pass


@dataclass(slots=True)
class OllamaTranslator:
    model: str = "qwen3:4b"
    url: str = "http://127.0.0.1:11434/api/chat"
    timeout: float = 90.0

    def _base_url(self) -> str:
        parsed = urlsplit(self.url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _installed_models(self) -> set[str]:
        response = requests.get(f"{self._base_url()}/api/tags", timeout=3)
        response.raise_for_status()
        return {
            str(item.get("name", ""))
            for item in response.json().get("models", [])
            if item.get("name")
        }

    def _ensure_ready(self) -> None:
        try:
            models = self._installed_models()
        except requests.RequestException:
            executable = shutil.which("ollama")
            if not executable:
                raise OllamaError(
                    "Ollama non trovato. Installalo oppure aggiungilo al PATH."
                )
            flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                flags |= subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS
            subprocess.Popen(
                [executable, "serve"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            for _attempt in range(20):
                time.sleep(0.5)
                try:
                    models = self._installed_models()
                    break
                except requests.RequestException:
                    continue
            else:
                raise OllamaError(
                    "Impossibile avviare Ollama. Apri Ollama e riprova."
                )

        accepted = {self.model, f"{self.model}:latest"}
        if not models.intersection(accepted):
            available = ", ".join(sorted(models)) or "nessuno"
            raise OllamaError(
                f"Modello {self.model!r} non installato. "
                f"Esegui: ollama pull {self.model}. "
                f"Modelli disponibili: {available}"
            )

    def translate(self, text: str, source_language: str = "auto") -> str:
        self._ensure_ready()
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
                "Ollama ha risposto con un errore durante la traduzione."
            ) from exc
        if not translated:
            raise OllamaError("Ollama ha restituito una traduzione vuota.")
        return translated
