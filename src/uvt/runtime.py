from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from typing import Any


class RuntimeSupervisor:
    """Own background workers and coordinate deterministic shutdown."""

    def __init__(self) -> None:
        self._workers: set[threading.Thread] = set()
        self._lock = threading.Lock()
        self._closing = threading.Event()

    @property
    def closing(self) -> bool:
        return self._closing.is_set()

    @property
    def active_workers(self) -> tuple[threading.Thread, ...]:
        with self._lock:
            return tuple(worker for worker in self._workers if worker.is_alive())

    def start(
        self,
        target: Callable[..., Any],
        *args: Any,
        name: str,
    ) -> threading.Thread:
        if self.closing:
            raise RuntimeError("Il runtime è in fase di arresto.")

        def run() -> None:
            try:
                target(*args)
            finally:
                with self._lock:
                    self._workers.discard(thread)

        thread = threading.Thread(target=run, name=name, daemon=True)
        with self._lock:
            self._workers.add(thread)
        thread.start()
        return thread

    def begin_shutdown(self) -> None:
        self._closing.set()

    def join(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        current = threading.current_thread()
        for worker in self.active_workers:
            if worker is current:
                continue
            worker.join(max(0.0, deadline - time.monotonic()))
        return not any(
            worker.is_alive()
            for worker in self.active_workers
            if worker is not current
        )

    @staticmethod
    def stop_named(
        resources: Iterable[tuple[str, Callable[[], Any] | None]],
        *,
        on_error: Callable[[str, Exception], None] | None = None,
    ) -> list[str]:
        failures: list[str] = []
        for name, stop in resources:
            if stop is None:
                continue
            try:
                if stop() is False:
                    failures.append(name)
            except Exception as error:
                failures.append(name)
                if on_error is not None:
                    on_error(name, error)
        return failures
