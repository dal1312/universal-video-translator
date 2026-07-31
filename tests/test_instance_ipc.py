import time
from uuid import uuid4

from uvt.browser_protocol import make_overlay_uri
from uvt.instance_ipc import SingleInstanceBroker


def test_second_broker_forwards_overlay_to_single_owner(tmp_path, monkeypatch) -> None:
    claims = tmp_path / "claims"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    name = f"Local\\UVT-test-{uuid4()}"
    owner = SingleInstanceBroker(tmp_path / "ipc", mutex_name=name)
    secondary = SingleInstanceBroker(tmp_path / "ipc", mutex_name=name)
    uri = make_overlay_uri(
        browser="chrome",
        requested_at=int(time.time()),
        request_id=str(uuid4()),
    )
    try:
        assert owner.acquire()
        owner.activate()
        assert not secondary.acquire()
        assert secondary.forward_overlay(uri)
        deadline = time.monotonic() + 2
        events = []
        while time.monotonic() < deadline and not events:
            events = owner.drain_events()
            time.sleep(0.01)
        assert len(events) == 1
        assert events[0].request.browser == "chrome"
        assert secondary.forward_overlay(uri)
        assert owner.drain_events() == []
    finally:
        secondary.close()
        owner.close()


def test_second_broker_can_focus_owner(tmp_path) -> None:
    name = f"Local\\UVT-test-{uuid4()}"
    owner = SingleInstanceBroker(tmp_path / "ipc", mutex_name=name)
    secondary = SingleInstanceBroker(tmp_path / "ipc", mutex_name=name)
    try:
        assert owner.acquire()
        owner.activate()
        assert not secondary.acquire()
        assert secondary.forward_focus()
        deadline = time.monotonic() + 2
        events = []
        while time.monotonic() < deadline and not events:
            events = owner.drain_events()
            time.sleep(0.01)
        assert [event.command for event in events] == ["focus"]
    finally:
        secondary.close()
        owner.close()
