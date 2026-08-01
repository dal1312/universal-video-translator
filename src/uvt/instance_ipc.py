from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import queue
import secrets
import socket
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .browser_protocol import (
    BrowserProtocolError,
    BrowserRequest,
    claim_browser_request,
    parse_browser_request,
)
from .diagnostics import log_exception, logger
from .paths import app_paths


IPC_VERSION = 1
MAX_MESSAGE_BYTES = 8192
_MUTEX_PREFIX = "Local\\UniversalVideoTranslator-Browser-v0.2.1"


class InstanceIPCError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InstanceEvent:
    command: str
    request: BrowserRequest | None = None


class SingleInstanceBroker:
    def __init__(
        self,
        state_directory: str | Path | None = None,
        *,
        mutex_name: str | None = None,
    ) -> None:
        root = Path(state_directory) if state_directory is not None else app_paths().instance_state
        self.state_directory = root
        session = _session_id()
        self.descriptor_path = root / f"ipc-v{IPC_VERSION}-{session}.json"
        suffix = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
        self.mutex_name = mutex_name or f"{_MUTEX_PREFIX}-{session}-{suffix}"
        self._events: queue.Queue[InstanceEvent] = queue.Queue()
        self._stop = threading.Event()
        self._accepting = threading.Event()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._token: str | None = None
        self._mutex_handle = None
        self._fallback_lock: Path | None = None
        self.is_owner = False

    def acquire(self) -> bool:
        if self.is_owner:
            return True
        if not self._acquire_mutex():
            return False
        try:
            self._start_server()
        except Exception:
            self._release_mutex()
            raise
        self.is_owner = True
        return True

    def forward_overlay(self, uri: str) -> bool:
        return self.forward_browser_request(uri)

    def forward_browser_request(self, uri: str) -> bool:
        return self._send({"command": "browser", "uri": uri}) in {
            "accepted",
            "duplicate",
        }

    def forward_focus(self) -> bool:
        return self._send({"command": "focus"}) == "accepted"

    def activate(self) -> None:
        if not self.is_owner or self._socket is None:
            raise InstanceIPCError("Il broker primario non è pronto.")
        self._accepting.set()

    def drain_events(self) -> list[InstanceEvent]:
        events: list[InstanceEvent] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def begin_shutdown(self) -> None:
        self._accepting.clear()

    def close(self) -> None:
        self.begin_shutdown()
        self._stop.set()
        server = self._socket
        self._socket = None
        if server is not None:
            try:
                server.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None
        self._remove_own_descriptor()
        self._release_mutex()
        self.is_owner = False

    def _start_server(self) -> None:
        self.state_directory.mkdir(parents=True, exist_ok=True)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(8)
        server.settimeout(0.25)
        self._socket = server
        self._token = secrets.token_urlsafe(32)
        descriptor = {
            "version": IPC_VERSION,
            "pid": os.getpid(),
            "port": server.getsockname()[1],
            "token": self._token,
        }
        _atomic_json_write(self.descriptor_path, descriptor)
        self._thread = threading.Thread(
            target=self._listen,
            name="uvt-instance-ipc",
            daemon=True,
        )
        self._thread.start()
        logger("ipc").info("event=instance_owner_ready")

    def _listen(self) -> None:
        while not self._stop.is_set():
            server = self._socket
            if server is None:
                return
            try:
                connection, _address = server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(1.0)
                response = self._handle_connection(connection)
                try:
                    connection.sendall(
                        json.dumps({"status": response}).encode("utf-8") + b"\n"
                    )
                except OSError:
                    continue

    def _handle_connection(self, connection: socket.socket) -> str:
        try:
            payload = _receive_message(connection)
            if not self._accepting.is_set():
                return "shutting_down" if self._stop.is_set() else "starting"
            token = payload.get("token")
            if not isinstance(token, str) or self._token is None:
                return "unauthorized"
            if not hmac.compare_digest(token, self._token):
                return "unauthorized"
            command = payload.get("command")
            if command == "focus":
                self._events.put(InstanceEvent("focus"))
                return "accepted"
            if command not in {"overlay", "browser"} or not isinstance(
                payload.get("uri"), str
            ):
                return "invalid"
            request = parse_browser_request(payload["uri"])
            if not claim_browser_request(request):
                return "duplicate"
            self._events.put(InstanceEvent("browser", request))
            return "accepted"
        except (BrowserProtocolError, InstanceIPCError, OSError, ValueError) as error:
            log_exception("ipc", "message_rejected", error)
            return "invalid"

    def _send(self, message: dict[str, str]) -> str:
        deadline = time.monotonic() + 3.0
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                descriptor = json.loads(self.descriptor_path.read_text(encoding="utf-8"))
                if descriptor.get("version") != IPC_VERSION:
                    raise InstanceIPCError("Versione IPC non compatibile.")
                port = int(descriptor["port"])
                token = str(descriptor["token"])
                payload = {**message, "token": token}
                encoded = json.dumps(payload).encode("utf-8") + b"\n"
                if len(encoded) > MAX_MESSAGE_BYTES:
                    raise InstanceIPCError("Messaggio IPC troppo grande.")
                with socket.create_connection(("127.0.0.1", port), timeout=0.75) as connection:
                    connection.sendall(encoded)
                    response = _receive_message(connection)
                status = str(response.get("status", "invalid"))
                if status in {"starting", "shutting_down"}:
                    time.sleep(0.08)
                    continue
                return status
            except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                last_error = error
                time.sleep(0.08)
        raise InstanceIPCError("L'istanza UVT esistente non risponde.") from last_error

    def _acquire_mutex(self) -> bool:
        if os.name == "nt":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_mutex = kernel32.CreateMutexW
            create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            create_mutex.restype = ctypes.c_void_p
            handle = create_mutex(None, False, self.mutex_name)
            if not handle:
                raise InstanceIPCError("Impossibile creare il mutex dell'applicazione.")
            already_exists = ctypes.get_last_error() == 183
            if already_exists:
                _close_windows_handle(handle)
                return False
            self._mutex_handle = handle
            return True
        self.state_directory.mkdir(parents=True, exist_ok=True)
        lock = self.state_directory / "instance.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        os.close(descriptor)
        self._fallback_lock = lock
        return True

    def _release_mutex(self) -> None:
        if self._mutex_handle is not None:
            _close_windows_handle(self._mutex_handle)
            self._mutex_handle = None
        if self._fallback_lock is not None:
            try:
                self._fallback_lock.unlink()
            except OSError:
                pass
            self._fallback_lock = None

    def _remove_own_descriptor(self) -> None:
        if self._token is None:
            return
        try:
            descriptor = json.loads(self.descriptor_path.read_text(encoding="utf-8"))
            if hmac.compare_digest(str(descriptor.get("token", "")), self._token):
                self.descriptor_path.unlink()
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
            pass
        self._token = None


def _receive_message(connection: socket.socket) -> dict:
    data = bytearray()
    while len(data) <= MAX_MESSAGE_BYTES:
        chunk = connection.recv(min(2048, MAX_MESSAGE_BYTES + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in chunk:
            break
    if not data or len(data) > MAX_MESSAGE_BYTES:
        raise InstanceIPCError("Messaggio IPC non valido.")
    raw = bytes(data).split(b"\n", 1)[0]
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise InstanceIPCError("Messaggio IPC non valido.")
    return payload


def _atomic_json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _session_id() -> int:
    if os.name != "nt":
        return 0
    session = ctypes.c_uint(0)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    process_id_to_session_id = kernel32.ProcessIdToSessionId
    process_id_to_session_id.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
    process_id_to_session_id.restype = ctypes.c_bool
    if process_id_to_session_id(os.getpid(), ctypes.byref(session)):
        return int(session.value)
    return 0


def _close_windows_handle(handle) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_bool
    close_handle(handle)
