from __future__ import annotations

import json
import queue
import secrets
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .paths import app_paths


BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 17321
_ALLOWED_ACTIONS = {"overlay", "stop", "focus", "quit"}
_ALLOWED_PROFILES = {"rapido", "bilanciato", "qualita"}
_ALLOWED_BROWSERS = {"chrome", "edge", "firefox"}


@dataclass(frozen=True, slots=True)
class BridgeCommand:
    action: str
    profile: str | None
    browser: str


class LocalBrowserBridge:
    """Loopback-only bridge for the browser extension.

    Browser pages are rejected by Origin; only extension origins can read state
    or enqueue commands. Tk state is copied into a locked snapshot by the UI.
    """

    def __init__(
        self,
        host: str = BRIDGE_HOST,
        port: int = BRIDGE_PORT,
        *,
        token: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._state: dict[str, Any] = {
            "available": True,
            "mode": None,
            "phase": "idle",
            "running": False,
            "profile": "rapido",
            "latency": {},
        }
        self._state_lock = threading.Lock()
        self._commands: queue.Queue[BridgeCommand] = queue.Queue(maxsize=16)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._token = token or self._load_or_create_token()

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self) -> None:  # noqa: N802
                if not self._authorized():
                    self.send_error(403)
                    return
                self.send_response(204)
                self._cors()
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header(
                    "Access-Control-Allow-Headers", "Content-Type"
                )
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/v1/status":
                    self.send_error(404)
                    return
                if not self._authorized():
                    self.send_error(403)
                    return
                self._json(200, bridge.snapshot())

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/v1/command":
                    self.send_error(404)
                    return
                if not self._authorized():
                    self.send_error(403)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if size < 2 or size > 1024:
                        raise ValueError
                    payload = json.loads(self.rfile.read(size))
                    command = bridge._parse_command(payload)
                    bridge._enqueue(command)
                except (ValueError, TypeError, json.JSONDecodeError, queue.Full):
                    self._json(400, {"ok": False, "error": "Comando non valido"})
                    return
                self._json(202, {"ok": True, "accepted": command.action})

            def _json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self._cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _cors(self) -> None:
                origin = self.headers.get("Origin")
                if origin:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")

            def _authorized(self) -> bool:
                authorization = self.headers.get("Authorization", "")
                return secrets.compare_digest(
                    authorization, f"Bearer {bridge._token}"
                )

            def log_message(self, _format: str, *_args) -> None:
                return

        try:
            self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        except OSError:
            self._server = None
            return False
        self._server.daemon_threads = True
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="uvt-browser-bridge",
            daemon=True,
        )
        self._thread.start()
        return True

    def close(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None

    def update_state(self, value: dict[str, Any]) -> None:
        with self._state_lock:
            self._state = {"available": True, **value}

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self._state)

    def drain_commands(self) -> list[BridgeCommand]:
        commands: list[BridgeCommand] = []
        while True:
            try:
                commands.append(self._commands.get_nowait())
            except queue.Empty:
                return commands

    def _enqueue(self, command: BridgeCommand) -> None:
        self._commands.put_nowait(command)

    @staticmethod
    def _load_or_create_token() -> str:
        path = app_paths().browser_bridge_token
        try:
            token = path.read_text(encoding="ascii").strip()
            if len(token) >= 43:
                return token
        except OSError:
            pass
        token = secrets.token_urlsafe(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="ascii")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return token

    @staticmethod
    def _parse_command(payload: object) -> BridgeCommand:
        if not isinstance(payload, dict):
            raise ValueError
        action = payload.get("command")
        browser = payload.get("browser", "chrome")
        profile = payload.get("profile")
        if action not in _ALLOWED_ACTIONS or browser not in _ALLOWED_BROWSERS:
            raise ValueError
        if profile is not None and profile not in _ALLOWED_PROFILES:
            raise ValueError
        return BridgeCommand(str(action), profile, str(browser))
