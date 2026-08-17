from __future__ import annotations

import threading

import pytest

from uvt.runtime import RuntimeSupervisor


def test_runtime_supervisor_tracks_and_joins_workers() -> None:
    supervisor = RuntimeSupervisor()
    release = threading.Event()

    supervisor.start(release.wait, name="test-worker")

    assert len(supervisor.active_workers) == 1
    release.set()
    assert supervisor.join(timeout=1.0)
    assert supervisor.active_workers == ()


def test_runtime_supervisor_rejects_workers_during_shutdown() -> None:
    supervisor = RuntimeSupervisor()
    supervisor.begin_shutdown()

    with pytest.raises(RuntimeError, match="arresto"):
        supervisor.start(lambda: None, name="late-worker")


def test_runtime_supervisor_collects_resource_failures() -> None:
    def broken() -> None:
        raise OSError("boom")

    errors: list[str] = []
    failures = RuntimeSupervisor.stop_named(
        (("ok", lambda: True), ("false", lambda: False), ("broken", broken)),
        on_error=lambda name, _error: errors.append(name),
    )

    assert failures == ["false", "broken"]
    assert errors == ["broken"]
