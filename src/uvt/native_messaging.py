from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path
from types import ModuleType
from urllib.error import URLError
from urllib.request import Request, urlopen

from .browser_bridge import BRIDGE_HOST, BRIDGE_PORT
from .paths import app_paths


HOST_NAME = "it.uvt.browser"
EXTENSION_ID = "mkicadoggkgglocilpndbmjagaafmgag"
FIREFOX_EXTENSION_ID = "uvt@dal1312.local"
_REGISTRY_PATHS = (
    rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}",
    rf"Software\Microsoft\Edge\NativeMessagingHosts\{HOST_NAME}",
)


def native_host_executable() -> Path:
    if getattr(sys, "frozen", False):
        launcher = Path(sys.executable).resolve().parent / "UVTNativeHost.exe"
    else:
        launcher = Path(sys.executable).resolve().parent / "uvt-native-host.exe"
    if not launcher.is_file():
        raise OSError("Launcher Native Messaging non trovato; reinstalla UVT")
    return launcher


def register_native_host(
    registry: ModuleType | None = None,
    root: str | Path | None = None,
) -> Path:
    registry = registry or _windows_registry()
    directory = app_paths(root).native_messaging
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / f"{HOST_NAME}.json"
    manifest.write_text(
        json.dumps(
            {
                "name": HOST_NAME,
                "description": "Universal Video Translator local bridge",
                "path": str(native_host_executable()),
                "type": "stdio",
                "allowed_origins": [f"chrome-extension://{EXTENSION_ID}/"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    firefox_manifest = _firefox_manifest_path(directory, root)
    firefox_manifest.parent.mkdir(parents=True, exist_ok=True)
    firefox_manifest.write_text(
        json.dumps(
            {
                "name": HOST_NAME,
                "description": "Universal Video Translator local bridge",
                "path": str(native_host_executable()),
                "type": "stdio",
                "allowed_extensions": [FIREFOX_EXTENSION_ID],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for path in _REGISTRY_PATHS:
        with registry.CreateKey(registry.HKEY_CURRENT_USER, path) as key:
            registry.SetValueEx(key, "", 0, registry.REG_SZ, str(manifest.resolve()))
    return manifest


def _firefox_manifest_path(directory: Path, root: str | Path | None) -> Path:
    """Return the Firefox host path without changing Chrome's contract.

    Firefox discovers native hosts from a dedicated per-user directory. Tests
    pass an isolated app root, so keep their fixture inside that root instead
    of touching the real AppData tree.
    """
    if root is not None:
        return directory / f"{HOST_NAME}-firefox.json"
    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / "Mozilla" / "NativeMessagingHosts" / f"{HOST_NAME}.json"
    return directory / f"{HOST_NAME}-firefox.json"


def run_native_host(stdin=None, stdout=None) -> int:
    source = stdin or sys.stdin.buffer
    target = stdout or sys.stdout.buffer
    while True:
        header = source.read(4)
        if not header:
            return 0
        if len(header) != 4:
            return 1
        size = struct.unpack("<I", header)[0]
        if size < 2 or size > 64 * 1024:
            return 1
        try:
            message = json.loads(source.read(size).decode("utf-8"))
            response = _relay(message)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, URLError) as error:
            response = {"ok": False, "error": str(error), "available": False}
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
        target.write(struct.pack("<I", len(encoded)))
        target.write(encoded)
        target.flush()


def _relay(message: object) -> dict:
    if not isinstance(message, dict) or message.get("type") not in {"status", "command", "subtitle"}:
        raise ValueError("Messaggio Native Messaging non valido")
    token = app_paths().browser_bridge_token.read_text(encoding="ascii").strip()
    request_type = message["type"]
    path = {
        "status": "/v1/status",
        "command": "/v1/command",
        "subtitle": "/v1/subtitle",
    }[request_type]
    payload = None
    method = "GET"
    if request_type in {"command", "subtitle"}:
        method = "POST"
        payload = json.dumps(message.get("payload", {})).encode("utf-8")
    request = Request(
        f"http://{BRIDGE_HOST}:{BRIDGE_PORT}{path}",
        data=payload,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=2) as response:
        result = json.loads(response.read())
    return {"ok": True, **result}


def _windows_registry() -> ModuleType:
    if os.name != "nt":
        raise OSError("Native Messaging è disponibile solo su Windows")
    import winreg

    return winreg
