from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path

from .paths import app_paths


class TranslationCache:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else app_paths().translation_cache
        self._data: dict[str, str] = {}
        self._load()

    @classmethod
    def _file_lock(cls) -> threading.Lock:
        if not hasattr(cls, "_lock"):
            cls._lock = threading.Lock()
        return cls._lock

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self._file_lock():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = {str(k): str(v) for k, v in raw.items()}
            except (OSError, json.JSONDecodeError):
                self._data = {}

    @staticmethod
    def key(model: str, language: str, text: str) -> str:
        value = "\0".join(("translation-v5", model, language, text))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def get(self, model: str, language: str, text: str) -> str | None:
        return self._data.get(self.key(model, language, text))

    def put(self, model: str, language: str, text: str, translated: str) -> None:
        with self._file_lock():
            self._data[self.key(model, language, text)] = translated
            self._save()

    def put_many(
        self, translations: list[tuple[str, str, str, str]]
    ) -> None:
        if not translations:
            return
        with self._file_lock():
            for model, language, text, translated in translations:
                self._data[self.key(model, language, text)] = translated
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        current: dict[str, str] = {}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    current = {str(k): str(v) for k, v in loaded.items()}
            except (OSError, json.JSONDecodeError):
                current = {}
        current.update(self._data)
        self._data = current

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(current, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
