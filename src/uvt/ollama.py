from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests


class OllamaError(RuntimeError):
    pass


@dataclass(slots=True)
class OllamaTranslator:
    model: str = "translategemma:latest"
    url: str = "http://127.0.0.1:11434/api/chat"
    timeout: float = 300.0
    _ready: bool = field(default=False, init=False, repr=False)
    _session: requests.Session = field(
        default_factory=requests.Session, init=False, repr=False
    )

    def _base_url(self) -> str:
        parsed = urlsplit(self.url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _installed_models(self) -> set[str]:
        response = self._session.get(f"{self._base_url()}/api/tags", timeout=3)
        response.raise_for_status()
        return {
            str(item.get("name", ""))
            for item in response.json().get("models", [])
            if item.get("name")
        }

    def _ensure_ready(self) -> None:
        if self._ready:
            return
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
        self._ready = True

    def list_models(self) -> list[str]:
        self._ensure_ready()
        return sorted(self._installed_models(), key=str.casefold)

    def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        num_predict: int,
        response_format: dict | None = None,
    ) -> str:
        self._ensure_ready()
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "messages": messages,
            "options": {"temperature": 0.1, "num_predict": num_predict},
        }
        if response_format is not None:
            payload["format"] = response_format
        try:
            response = self._session.post(
                self.url,
                json=payload,
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
            response_payload = response.json()
            content = str(response_payload["message"]["content"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise OllamaError(
                f"Risposta Ollama non valida: {response.text[:500]}"
            ) from exc
        if not content:
            raise OllamaError("Ollama ha restituito una traduzione vuota.")
        return content

    def translate(self, text: str, source_language: str = "auto") -> str:
        system_prompt = (
            "/no_think\nSei un motore di traduzione per doppiaggio. Traduci sempre il testo "
            "ricevuto in italiano naturale e parlato. Non ripetere il testo nella "
            "lingua originale. Mantieni significato, tono e brevità. Rispondi "
            "esclusivamente con la traduzione italiana, senza note né prefissi."
        )
        return self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"/no_think\n{text}"},
            ],
            num_predict=256,
        )

    def translate_many(
        self, texts: list[str], source_language: str = "auto"
    ) -> list[str]:
        if not texts:
            return []
        if len(texts) == 1:
            return [self.translate(texts[0], source_language)]

        schema = {
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["translations"],
        }
        system_prompt = (
            "/no_think\nTraduci in italiano naturale e parlato ogni elemento "
            "dell'array JSON ricevuto. Mantieni esattamente lo stesso ordine e "
            "numero di elementi. Non unire, saltare o spiegare le frasi."
        )
        try:
            content = self._chat(
                [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(texts, ensure_ascii=False),
                    },
                ],
                num_predict=2048,
                response_format=schema,
            )
            decoded = json.loads(content)
            translations = decoded.get("translations")
            if (
                not isinstance(translations, list)
                or len(translations) != len(texts)
                or not all(
                    isinstance(item, str) and item.strip()
                    for item in translations
                )
            ):
                raise ValueError("numero di traduzioni non valido")
            return [item.strip() for item in translations]
        except (OllamaError, TypeError, ValueError, json.JSONDecodeError):
            return [self.translate(text, source_language) for text in texts]
