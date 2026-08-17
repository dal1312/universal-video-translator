from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from .paths import app_paths


class AudioRoutingError(RuntimeError):
    pass


_BROWSER_PROCESSES = {
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
}


def sound_volume_view_path() -> Path:
    roots = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    roots.extend((Path(sys.executable).resolve().parent, Path(__file__).resolve().parents[2]))
    for root in roots:
        candidate = root / "third_party" / "SoundVolumeView" / "SoundVolumeView.exe"
        if candidate.is_file():
            return candidate
    raise AudioRoutingError("SoundVolumeView non trovato nella cartella dell'app.")


def _set_browser_output(browser: str, device: str) -> None:
    process_name = _BROWSER_PROCESSES.get(browser.lower())
    if process_name is None:
        raise AudioRoutingError(f"Browser non supportato per il routing: {browser}")
    command = [
        str(sound_volume_view_path()),
        "/SetAppDefault",
        device,
        "all",
        process_name,
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AudioRoutingError(f"Routing audio {browser} fallito: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise AudioRoutingError(
            f"SoundVolumeView ha restituito {result.returncode}{suffix}"
        )


def route_browser_to_cable(browser: str) -> None:
    _set_browser_output(browser, "CABLE Input")


def restore_browser_default(browser: str) -> None:
    _set_browser_output(browser, "DefaultRenderDevice")


def _sound_volume_value(process_name: str, command: str) -> str:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [str(sound_volume_view_path()), command, process_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AudioRoutingError(f"Lettura volume fallita: {exc}") from exc
    if result.returncode:
        raise AudioRoutingError("Impossibile leggere il volume del browser.")
    return result.stdout.strip()


def _set_browser_volume(browser: str, percent: float) -> None:
    process_name = _BROWSER_PROCESSES.get(browser.lower())
    if process_name is None:
        raise AudioRoutingError(f"Browser non supportato: {browser}")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [
                str(sound_volume_view_path()),
                "/SetVolume",
                process_name,
                f"{max(0.0, min(100.0, percent)):.1f}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AudioRoutingError(f"Regolazione volume fallita: {exc}") from exc
    if result.returncode:
        raise AudioRoutingError("Regolazione volume browser fallita.")


class BrowserVolumeDucker:
    """Temporarily lowers browser volume and restores the exact prior value."""

    def __init__(self, browser: str, duck_percent: int = 30) -> None:
        self.browser = _validated_browser(browser)
        self.duck_percent = max(0, min(100, int(duck_percent)))
        self._original_percent: float | None = None
        self._lock = threading.Lock()

    def duck(self) -> bool:
        with self._lock:
            if self._original_percent is not None:
                return True
            process_name = _BROWSER_PROCESSES[self.browser]
            try:
                original = float(
                    _sound_volume_value(process_name, "/GetPercent")
                )
                muted = _sound_volume_value(process_name, "/GetMute") == "1"
                if muted:
                    return False
                self._original_percent = original
                _set_browser_volume(
                    self.browser,
                    original * self.duck_percent / 100.0,
                )
                return True
            except (AudioRoutingError, ValueError):
                self._original_percent = None
                return False

    def restore(self) -> bool:
        with self._lock:
            original = self._original_percent
            self._original_percent = None
        if original is None:
            return True
        try:
            _set_browser_volume(self.browser, original)
            return True
        except AudioRoutingError:
            return False


class AudioRoutingLeaseManager:
    def __init__(
        self,
        state_path: str | Path | None = None,
        *,
        route_command: Callable[[str], None] | None = None,
        restore_command: Callable[[str], None] | None = None,
    ) -> None:
        self.state_path = (
            Path(state_path) if state_path is not None else app_paths().routing_lease
        )
        self._route_command = route_command or route_browser_to_cable
        self._restore_command = restore_command or restore_browser_default
        self._owner_token = secrets.token_hex(16)

    def route(self, browser: str) -> None:
        browser = _validated_browser(browser)
        if self.state_path.exists():
            self.recover()
        lease = {
            "schema_version": 1,
            "browser": browser,
            "owner_pid": os.getpid(),
            "owner_token": self._owner_token,
            "phase": "pending",
            "created_at": int(time.time()),
            "restore_target": "DefaultRenderDevice",
        }
        self._write_lease(lease)
        self._route_command(browser)
        lease["phase"] = "active"
        self._write_lease(lease)

    def restore(
        self,
        browser: str | None = None,
        *,
        retries: int = 3,
        retry_delay: float = 0.15,
    ) -> bool:
        lease = self._read_lease(required=False)
        target = _validated_browser(browser or lease.get("browser") if lease else browser)
        last_error: Exception | None = None
        for attempt in range(max(1, retries)):
            try:
                self._restore_command(target)
            except Exception as error:
                last_error = error
                if attempt + 1 < max(1, retries):
                    time.sleep(max(0.0, retry_delay))
                continue
            self._delete_lease(lease)
            return True
        if isinstance(last_error, AudioRoutingError):
            raise last_error
        raise AudioRoutingError(f"Ripristino audio {target} fallito.") from last_error

    def recover(self) -> bool:
        lease = self._read_lease(required=False)
        if not lease:
            return False
        self.restore(str(lease["browser"]))
        return True

    def pending_browser(self) -> str | None:
        lease = self._read_lease(required=False)
        return str(lease["browser"]) if lease else None

    def _read_lease(self, *, required: bool) -> dict:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if required:
                raise AudioRoutingError("Stato del routing audio non trovato.")
            return {}
        except (OSError, json.JSONDecodeError) as error:
            raise AudioRoutingError(
                "Stato del routing audio non leggibile; ripristina il browser manualmente."
            ) from error
        if (
            not isinstance(raw, dict)
            or raw.get("schema_version") != 1
            or raw.get("phase") not in {"pending", "active"}
            or raw.get("restore_target") != "DefaultRenderDevice"
        ):
            raise AudioRoutingError(
                "Stato del routing audio non valido; ripristina il browser manualmente."
            )
        _validated_browser(raw.get("browser"))
        return raw

    def _write_lease(self, lease: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.",
            suffix=".tmp",
            dir=self.state_path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(lease, handle, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.state_path)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise

    def _delete_lease(self, lease: dict) -> None:
        if not lease:
            return
        try:
            current = self._read_lease(required=False)
            if current and current.get("owner_token") != lease.get("owner_token"):
                return
            self.state_path.unlink()
        except FileNotFoundError:
            return
        except OSError as error:
            raise AudioRoutingError("Impossibile rimuovere lo stato del routing audio.") from error


def _validated_browser(browser: object) -> str:
    if not isinstance(browser, str) or browser.lower() not in _BROWSER_PROCESSES:
        raise AudioRoutingError(f"Browser non supportato per il routing: {browser}")
    return browser.lower()
