from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SessionMode(str, Enum):
    FILE = "file"
    LIVE = "live"


class SessionPhase(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class SessionConflictError(RuntimeError):
    pass


@dataclass(slots=True)
class TranslationSession:
    mode: SessionMode | None = None
    phase: SessionPhase = SessionPhase.IDLE
    run_id: int = 0

    @property
    def busy(self) -> bool:
        return self.phase in {
            SessionPhase.PREPARING,
            SessionPhase.RUNNING,
            SessionPhase.PAUSED,
            SessionPhase.STOPPING,
        }

    def begin(self, mode: SessionMode) -> int:
        if self.busy:
            raise SessionConflictError(
                f"Sessione {self.mode or 'sconosciuta'} ancora attiva."
            )
        self.run_id += 1
        self.mode = mode
        self.phase = SessionPhase.PREPARING
        return self.run_id

    def accepts(self, mode: SessionMode, run_id: int) -> bool:
        return self.mode is mode and self.run_id == run_id and self.busy

    def activate(self, mode: SessionMode, run_id: int) -> bool:
        if not self.accepts(mode, run_id):
            return False
        self.phase = SessionPhase.RUNNING
        return True

    def set_paused(self, paused: bool) -> None:
        if self.phase not in {SessionPhase.RUNNING, SessionPhase.PAUSED}:
            return
        self.phase = SessionPhase.PAUSED if paused else SessionPhase.RUNNING

    def begin_stopping(self, mode: SessionMode) -> bool:
        if self.mode is not mode or not self.busy:
            return False
        self.phase = SessionPhase.STOPPING
        return True

    def finish(self, mode: SessionMode) -> None:
        if self.mode is not mode:
            return
        self.run_id += 1
        self.mode = None
        self.phase = SessionPhase.IDLE

    def fail(self, mode: SessionMode, run_id: int) -> None:
        if self.mode is mode and self.run_id == run_id:
            self.phase = SessionPhase.ERROR

