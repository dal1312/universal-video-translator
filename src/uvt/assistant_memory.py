from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    created_at: str
    window_title: str
    instruction: str
    context: str
    answer: str


def default_memory_path() -> Path:
    if os.name == "nt":
        root = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
    else:
        root = Path(
            os.environ.get(
                "XDG_DATA_HOME", Path.home() / ".local" / "share"
            )
        )
    directory = root / "UniversalVideoTranslator"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "assistant-memory.sqlite3"


class AssistantMemory:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_memory_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assistant_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    window_title TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    context TEXT NOT NULL,
                    answer TEXT NOT NULL
                )
                """
            )

    def add(
        self,
        window_title: str,
        instruction: str,
        context: str,
        answer: str,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO assistant_memory
                    (created_at, window_title, instruction, context, answer)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    window_title[:500],
                    instruction[:4000],
                    context[:50000],
                    answer[:50000],
                ),
            )

    def recent(self, limit: int = 10) -> list[MemoryEntry]:
        safe_limit = max(1, min(100, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT created_at, window_title, instruction, context, answer
                FROM assistant_memory
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [MemoryEntry(*map(str, row)) for row in rows]

    def conversation_context(
        self, limit: int = 3
    ) -> list[tuple[str, str]]:
        entries = list(reversed(self.recent(limit)))
        return [
            (entry.instruction[-1500:], entry.answer[-3000:])
            for entry in entries
        ]

    def formatted_history(self, limit: int = 20) -> str:
        entries = self.recent(limit)
        if not entries:
            return "La memoria dell’assistente è vuota."
        sections = []
        for entry in entries:
            timestamp = entry.created_at.replace("T", " ")[:19]
            sections.append(
                f"[{timestamp}] {entry.window_title}\n"
                f"Domanda: {entry.instruction}\n"
                f"Risposta: {entry.answer}"
            )
        return "\n\n".join(sections)

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM assistant_memory")

