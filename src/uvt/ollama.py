from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests
from langdetect import DetectorFactory, LangDetectException, detect_langs

from .glossary import TranslationGlossary


class OllamaError(RuntimeError):
    pass


_NON_ITALIAN_OUTPUT = re.compile(
    r"\b("
    r"the|this|that|with|from|about|working|people|sentence|"
    r"el|los|las|esta|está|estan|están|policia|policía|"
    r"britanico|británico|regreso|regresó|afectado|presencio|"
    r"presenció|ejercicio|funcionando"
    r")\b",
    re.IGNORECASE,
)
_ITALIAN_LANGUAGE_NAMES = {"it", "ita", "italian", "italiano", "italiana"}
DetectorFactory.seed = 0


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _clean_translation(value: str) -> str:
    cleaned = value.strip()
    quote_pairs = {
        '"': '"',
        "'": "'",
        "“": "”",
        "«": "»",
    }
    if (
        len(cleaned) >= 2
        and cleaned[0] in quote_pairs
        and cleaned[-1] == quote_pairs[cleaned[0]]
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _detected_language(value: str) -> tuple[str | None, float]:
    words = re.findall(r"[^\W\d_]+", value, re.UNICODE)
    if len(words) < 3 or sum(map(len, words)) < 12:
        return None, 0.0
    try:
        candidate = detect_langs(value)[0]
    except LangDetectException:
        return None, 0.0
    return candidate.lang, float(candidate.prob)


def _source_is_italian(source: str, source_language: str) -> bool:
    if source_language.casefold() in _ITALIAN_LANGUAGE_NAMES:
        return True
    language, confidence = _detected_language(source)
    return language == "it" and confidence >= 0.70


def _translation_is_valid(
    source: str, translated: str, source_language: str = "auto"
) -> bool:
    source_normalized = _normalized_text(source)
    translated_normalized = _normalized_text(translated)
    if not translated_normalized:
        return False
    if source_normalized == translated_normalized:
        return _source_is_italian(source, source_language)
    if _NON_ITALIAN_OUTPUT.search(translated):
        return False
    language, confidence = _detected_language(translated)
    if language is not None and language != "it" and confidence >= 0.78:
        return False
    if len(source_normalized) < 24:
        return True
    return SequenceMatcher(
        None, source_normalized, translated_normalized
    ).ratio() < 0.92


def _needs_translation_retry(
    source: str, translated: str, source_language: str = "auto"
) -> bool:
    return not _translation_is_valid(source, translated, source_language)


@dataclass(slots=True)
class OllamaTranslator:
    model: str = "translategemma:latest"
    url: str = "http://127.0.0.1:11434/api/chat"
    timeout: float = 300.0
    glossary: TranslationGlossary = field(default_factory=TranslationGlossary)
    _ready: bool = field(default=False, init=False, repr=False)
    _session: requests.Session = field(
        default_factory=requests.Session, init=False, repr=False
    )
    _last_failed_indices: tuple[int, ...] = field(
        default=(), init=False, repr=False
    )

    @property
    def last_failed_indices(self) -> tuple[int, ...]:
        return self._last_failed_indices

    @property
    def cache_key(self) -> str:
        return f"{self.model}|glossary:{self.glossary.fingerprint}"

    def _with_glossary(self, prompt: str, texts: list[str]) -> str:
        terms = self.glossary.matched(texts)
        if not terms:
            return prompt
        return (
            prompt
            + " Usa obbligatoriamente queste equivalenze terminologiche: "
            + json.dumps(terms, ensure_ascii=False, sort_keys=True)
            + "."
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

    def warmup(self) -> None:
        """Load the selected model before the first real translation."""
        self._ensure_ready()
        response = self._session.post(
            f"{self._base_url()}/api/generate",
            json={
                "model": self.model,
                "prompt": "",
                "stream": False,
                "keep_alive": "30m",
            },
            timeout=min(self.timeout, 60.0),
        )
        response.raise_for_status()

    def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        num_predict: int,
        response_format: dict | None = None,
        extra_options: dict | None = None,
    ) -> str:
        self._ensure_ready()
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "messages": messages,
            "options": {
                "temperature": 0.1,
                "num_predict": num_predict,
                **(extra_options or {}),
            },
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
        system_prompt = self._with_glossary((
            "/no_think\nSei un motore di traduzione per doppiaggio. Traduci sempre il testo "
            "ricevuto in italiano naturale e parlato. Non ripetere il testo nella "
            "lingua originale. Mantieni significato, tono e brevità. Rispondi "
            "esclusivamente con la traduzione italiana, senza note né prefissi."
        ), [text])
        return self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"/no_think\n{text}"},
            ],
            num_predict=256,
        )

    def translate_realtime(
        self, text: str, source_language: str = "auto"
    ) -> str:
        """Low-prefill translation path for short live speech segments."""
        word_count = max(1, len(text.split()))
        translated = self._chat(
            [
                {
                    "role": "system",
                    "content": self._with_glossary((
                        "/no_think\nTraduci in italiano parlato. "
                        "Rispondi solo con la traduzione, breve e naturale."
                    ), [text]),
                },
                {"role": "user", "content": f"/no_think\n{text}"},
            ],
            num_predict=max(24, min(96, word_count * 3 + 12)),
            extra_options={"temperature": 0.0, "num_ctx": 1024},
        )
        # Live audio must not block for a second model request: short phrases
        # also produce false negatives in language detection. The compact
        # prompt is deterministic, so accept its first non-empty result.
        cleaned = _clean_translation(translated)
        self._last_failed_indices = ()
        return cleaned

    def _translate_strict(
        self,
        text: str,
        source_language: str = "auto",
        previous: str | None = None,
        following: str | None = None,
    ) -> str:
        system_prompt = self._with_glossary((
            "/no_think\nTraduci obbligatoriamente in italiano naturale. "
            "Il testo puo essere in inglese, spagnolo, francese, tedesco o gia "
            "parzialmente tradotto. Se non e italiano, non copiarlo: traducilo. "
            "Rispondi solo con la versione italiana finale, senza note."
        ), [text])
        context = {
            "previous_context": previous or "",
            "text_to_translate": text,
            "following_context": following or "",
        }
        return self._chat(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "/no_think\n"
                    + json.dumps(context, ensure_ascii=False),
                },
            ],
            num_predict=384,
        )

    def _finalize_translation(
        self,
        text: str,
        translated: str,
        source_language: str,
        previous: str | None = None,
        following: str | None = None,
    ) -> tuple[str, bool]:
        translated = _clean_translation(translated)
        if not _needs_translation_retry(text, translated, source_language):
            return translated, True
        try:
            retry = self._translate_strict(
                text, source_language, previous, following
            )
            retry = _clean_translation(retry)
        except OllamaError:
            return text, False
        if _translation_is_valid(text, retry, source_language):
            return retry, True
        return text, False

    def translate_many(
        self, texts: list[str], source_language: str = "auto"
    ) -> list[str]:
        if not texts:
            self._last_failed_indices = ()
            return []
        if len(texts) == 1:
            try:
                translated = self.translate(texts[0], source_language)
            except OllamaError:
                self._last_failed_indices = (0,)
                return [texts[0]]
            finalized, valid = self._finalize_translation(
                texts[0], translated, source_language
            )
            self._last_failed_indices = () if valid else (0,)
            return [finalized]

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
        system_prompt = self._with_glossary((
            "/no_think\nTraduci in italiano naturale e parlato ogni elemento "
            "dell'array JSON ricevuto. Mantieni esattamente lo stesso ordine e "
            "numero di elementi. Non unire, saltare o spiegare le frasi."
        ), texts)
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
            finalized: list[str] = []
            failed: list[int] = []
            for index, (text, translated) in enumerate(
                zip(texts, translations)
            ):
                result, valid = self._finalize_translation(
                    text,
                    translated,
                    source_language,
                    texts[index - 1] if index else None,
                    texts[index + 1] if index + 1 < len(texts) else None,
                )
                finalized.append(result)
                if not valid:
                    failed.append(index)
            self._last_failed_indices = tuple(failed)
            return finalized
        except (OllamaError, TypeError, ValueError, json.JSONDecodeError):
            translations: list[str] = []
            failed: list[int] = []
            for index, text in enumerate(texts):
                try:
                    translated = self.translate(text, source_language)
                except OllamaError:
                    translations.append(text)
                    failed.append(index)
                    continue
                result, valid = self._finalize_translation(
                    text,
                    translated,
                    source_language,
                    texts[index - 1] if index else None,
                    texts[index + 1] if index + 1 < len(texts) else None,
                )
                translations.append(result)
                if not valid:
                    failed.append(index)
            self._last_failed_indices = tuple(failed)
            return translations
