from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .paths import app_paths


class TranslationGlossary:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else app_paths().glossary
        self._modified_ns = -1
        self._terms: dict[str, str] = {}

    def ensure_template(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps(
                    {
                        "OpenAI": "OpenAI",
                        "machine learning": "apprendimento automatico",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return self.path

    def matched(self, texts: list[str]) -> dict[str, str]:
        self._reload()
        combined = " ".join(texts).casefold()
        return {
            source: target
            for source, target in self._terms.items()
            if source.casefold() in combined
        }

    @property
    def fingerprint(self) -> str:
        self._reload()
        payload = json.dumps(
            self._terms, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:12]

    def _reload(self) -> None:
        try:
            modified_ns = self.path.stat().st_mtime_ns
        except OSError:
            modified_ns = -1
        if modified_ns == self._modified_ns:
            return
        self._modified_ns = modified_ns
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._terms = {}
            return
        if not isinstance(value, dict):
            self._terms = {}
            return
        self._terms = {
            source.strip()[:120]: target.strip()[:160]
            for source, target in list(value.items())[:200]
            if isinstance(source, str)
            and isinstance(target, str)
            and source.strip()
            and target.strip()
        }
