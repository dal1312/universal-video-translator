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
    model: str = "translategemma:latest"
    url: str = "http://127.0.0.1:11434/api/chat"
    timeout: float = 300.0

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

    def list_models(self) -> list[str]:
        self._ensure_ready()
        return sorted(self._installed_models(), key=str.casefold)

    def translate(self, text: str, source_language: str = "auto") -> str:
        self._ensure_ready()
        system_prompt = (
            "/no_think\nSei un motore di traduzione per doppiaggio. Traduci sempre il testo "
            "ricevuto in italiano naturale e parlato. Non ripetere il testo nella "
            "lingua originale. Mantieni significato, tono e brevità. Rispondi "
            "esclusivamente con la traduzione italiana, senza note né prefissi."
        )
        language_label = (
            "rilevamento automatico"
            if source_language == "auto"
            else source_language
        )
        prompt = (
            "/no_think\n"
            f"Lingua originale: {language_label}\n"
            f"Traduci esclusivamente in italiano:\n{text}"
        )
        try:
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "stream": False,
                    "think": False,
                    "keep_alive": "30m",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = str(exc)
            if exc.response is not None:
                body = exc.response.text.strip().replace("\n", " ")
                detail = f"HTTP {exc.response.status_code}: {body[:500]}"
            raise OllamaError(
                f"Errore API Ollama: {detail}"
            ) from exc
        try:
            payload = response.json()
            translated = str(payload["message"]["content"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise OllamaError(
                f"Risposta Ollama non valida: {response.text[:500]}"
            ) from exc
        if not translated:
            raise OllamaError("Ollama ha restituito una traduzione vuota.")
        return translated
