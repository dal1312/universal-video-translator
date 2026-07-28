from __future__ import annotations

import hashlib
import json
from pathlib import Path


class TranslationCache:
    def __init__(self, path: str | Path = ".uvt-cache.json") -> None:
        self.path = Path(path)
        self._data: dict[str, str] = {}
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = {str(k): str(v) for k, v in raw.items()}
            except (OSError, json.JSONDecodeError):
                self._data = {}

    @staticmethod
    def key(model: str, language: str, text: str) -> str:
        value = "\0".join(("translation-v3", model, language, text))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def get(self, model: str, language: str, text: str) -> str | None:
        return self._data.get(self.key(model, language, text))

    def put(self, model: str, language: str, text: str, translated: str) -> None:
        self._data[self.key(model, language, text)] = translated
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
