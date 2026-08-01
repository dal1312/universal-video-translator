from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from uvt.browser_bridge import LocalBrowserBridge


def _request(bridge, path, *, method="GET", payload=None, origin=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:{bridge.port}{path}",
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Origin": origin} if origin else {}),
        },
    )
    with urlopen(request, timeout=2) as response:
        return response.status, json.loads(response.read())


def test_bridge_exposes_state_and_accepts_extension_command() -> None:
    bridge = LocalBrowserBridge(port=0)
    assert bridge.start()
    try:
        bridge.update_state({"running": True, "phase": "running"})
        status, state = _request(
            bridge, "/v1/status", origin="chrome-extension://test-id"
        )
        accepted, response = _request(
            bridge,
            "/v1/command",
            method="POST",
            origin="chrome-extension://test-id",
            payload={
                "command": "overlay",
                "profile": "rapido",
                "browser": "chrome",
            },
        )

        assert status == 200 and state["running"] is True
        assert accepted == 202 and response["ok"] is True
        assert bridge.drain_commands()[0].action == "overlay"
    finally:
        bridge.close()


def test_bridge_rejects_web_pages_and_invalid_commands() -> None:
    bridge = LocalBrowserBridge(port=0)
    assert bridge.start()
    try:
        with pytest.raises(HTTPError) as forbidden:
            _request(bridge, "/v1/status", origin="https://example.com")
        assert forbidden.value.code == 403

        with pytest.raises(HTTPError) as invalid:
            _request(
                bridge,
                "/v1/command",
                method="POST",
                origin="chrome-extension://test-id",
                payload={"command": "delete", "browser": "chrome"},
            )
        assert invalid.value.code == 400
    finally:
        bridge.close()
