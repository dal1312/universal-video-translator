from __future__ import annotations

import json
from pathlib import Path

from types import SimpleNamespace

from uvt.browser_bridge import LocalBrowserBridge
from uvt.native_messaging import EXTENSION_ID, HOST_NAME, _relay, register_native_host


class _Key:
    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class _Registry:
    HKEY_CURRENT_USER = object()
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def CreateKey(self, _root, path: str) -> _Key:
        return _Key(path)

    def SetValueEx(self, key: _Key, _name, _reserved, _kind, value: str) -> None:
        self.values[key.path] = value


def test_native_host_registration_is_user_scoped_and_origin_locked(
    monkeypatch, tmp_path
) -> None:
    registry = _Registry()
    executable = tmp_path / "UVTNativeHost.exe"
    executable.touch()
    monkeypatch.setattr(
        "uvt.native_messaging.native_host_executable", lambda: executable
    )
    manifest_path = register_native_host(registry, tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == HOST_NAME
    assert manifest["allowed_origins"] == [f"chrome-extension://{EXTENSION_ID}/"]
    assert Path(manifest["path"]).is_file()
    assert len(registry.values) == 2


def test_native_host_relays_with_install_token(monkeypatch, tmp_path) -> None:
    token_path = tmp_path / "browser-bridge.token"
    token_path.write_text("test-token", encoding="ascii")
    bridge = LocalBrowserBridge(port=0, token="test-token")
    assert bridge.start()
    monkeypatch.setattr("uvt.native_messaging.BRIDGE_PORT", bridge.port)
    monkeypatch.setattr(
        "uvt.native_messaging.app_paths",
        lambda: SimpleNamespace(browser_bridge_token=token_path),
    )
    try:
        result = _relay({"type": "status"})
    finally:
        bridge.close()

    assert result["ok"] is True
    assert result["available"] is True
