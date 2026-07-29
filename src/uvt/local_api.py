from __future__ import annotations

import hmac
import json
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from .assistant_memory import default_memory_path
from .automation import MacroStore
from .plugins import PluginManager


class LocalAPIError(RuntimeError):
    pass


class _APIHandler(BaseHTTPRequestHandler):
    server_version = "UVTLocalAPI/0.3"

    @property
    def api(self) -> "LocalAPIServer":
        return self.server.api  # type: ignore[attr-defined]

    def log_message(self, _format: str, *_args) -> None:
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        expected = f"Bearer {self.api.token}"
        return hmac.compare_digest(header, expected)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._json(
            HTTPStatus.UNAUTHORIZED,
            {"error": "Token API mancante o non valido."},
        )
        return False

    def _read_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise LocalAPIError("Content-Length non valido.") from exc
        if length < 0 or length > 1_000_000:
            raise LocalAPIError("Corpo richiesta troppo grande.")
        try:
            raw = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LocalAPIError("JSON non valido.") from exc
        if not isinstance(raw, dict):
            raise LocalAPIError("Il corpo deve essere un oggetto JSON.")
        return raw

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self._json(
                HTTPStatus.OK,
                {"status": "ok", "service": "AI Overlay OS"},
            )
            return
        if not self._require_auth():
            return
        if path == "/v1/plugins":
            self._json(
                HTTPStatus.OK,
                {"plugins": self.api.plugins.list_plugins()},
            )
            return
        if path == "/v1/macros":
            self._json(
                HTTPStatus.OK,
                {"macros": self.api.macros.names()},
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "Endpoint non trovato."})

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        path = urlsplit(self.path).path
        try:
            body = self._read_body()
            if path == "/v1/assistant":
                instruction = str(body.get("instruction", "")).strip()
                context = str(body.get("context", "")).strip()
                if not instruction:
                    raise LocalAPIError("instruction obbligatoria.")
                answer = self.api.assistant_handler(
                    instruction,
                    context,
                    str(body.get("provider", "Ollama")),
                    str(body.get("model", "")),
                )
                self._json(HTTPStatus.OK, {"answer": answer})
                return

            parts = [unquote(part) for part in path.split("/") if part]
            if (
                len(parts) == 4
                and parts[:2] == ["v1", "macros"]
                and parts[3] == "request"
            ):
                name = parts[2]
                if name not in self.api.macros.names():
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {"error": f"Macro non trovata: {name}"},
                    )
                    return
                self.api.macro_requester(name)
                self._json(
                    HTTPStatus.ACCEPTED,
                    {
                        "status": "confirmation_required",
                        "macro": name,
                    },
                )
                return

            if len(parts) == 4 and parts[:2] == ["v1", "plugins"]:
                plugin_id, command_id = parts[2], parts[3]
                text = str(body.get("text", ""))
                prompt = self.api.plugins.render(
                    plugin_id,
                    command_id,
                    text=text,
                    instruction=str(body.get("instruction", "")),
                )
                answer = self.api.assistant_handler(
                    prompt,
                    text,
                    str(body.get("provider", "Ollama")),
                    str(body.get("model", "")),
                )
                self._json(HTTPStatus.OK, {"answer": answer})
                return
            self._json(
                HTTPStatus.NOT_FOUND, {"error": "Endpoint non trovato."}
            )
        except LocalAPIError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": str(exc)},
            )


class LocalAPIServer:
    def __init__(
        self,
        *,
        assistant_handler: Callable[[str, str, str, str], str],
        macro_requester: Callable[[str], None],
        plugins: PluginManager,
        macros: MacroStore,
        host: str = "127.0.0.1",
        port: int = 8765,
        token_path: str | Path | None = None,
    ) -> None:
        if host not in {"127.0.0.1", "localhost"}:
            raise LocalAPIError(
                "L'API può essere esposta soltanto sul PC locale."
            )
        self.host = host
        self.port = port
        self.assistant_handler = assistant_handler
        self.macro_requester = macro_requester
        self.plugins = plugins
        self.macros = macros
        self.token_path = (
            Path(token_path)
            if token_path is not None
            else default_memory_path().with_name("api-token.txt")
        )
        self.token = self._load_token()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def _load_token(self) -> str:
        if self.token_path.exists():
            token = self.token_path.read_text(encoding="utf-8").strip()
            if len(token) >= 32:
                return token
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)
        self.token_path.write_text(token, encoding="utf-8")
        try:
            self.token_path.chmod(0o600)
        except OSError:
            pass
        return token

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def address(self) -> str:
        port = (
            self._server.server_address[1]
            if self._server is not None
            else self.port
        )
        return f"http://{self.host}:{port}"

    def start(self) -> None:
        if self.running:
            return
        try:
            server = ThreadingHTTPServer((self.host, self.port), _APIHandler)
        except OSError as exc:
            raise LocalAPIError(
                f"Impossibile avviare API locale sulla porta {self.port}: {exc}"
            ) from exc
        server.daemon_threads = True
        server.api = self  # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="uvt-local-api",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        server = self._server
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None

