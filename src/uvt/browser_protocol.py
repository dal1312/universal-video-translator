from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

from .downloader import is_web_url
from .paths import app_paths

PROTOCOL = "uvt"
TRANSLATE_ACTION = "translate"
OVERLAY_ACTION = "overlay"
ACTION = TRANSLATE_ACTION
REGISTRY_PATH = rf"Software\Classes\{PROTOCOL}"
SUPPORTED_BROWSERS = frozenset({"chrome", "edge", "firefox"})
REQUEST_MAX_AGE_SECONDS = 120
REQUEST_FUTURE_TOLERANCE_SECONDS = 15
REQUEST_CLAIM_RETENTION_SECONDS = 86400


class BrowserProtocolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BrowserRequest:
    url: str | None = None
    browser: str | None = None
    requested_at: int | None = None
    request_id: str | None = None
    action: str = TRANSLATE_ACTION


def make_translate_uri(
    url: str,
    *,
    browser: str | None = None,
    requested_at: int | None = None,
    request_id: str | None = None,
) -> str:
    if not is_web_url(url):
        raise BrowserProtocolError("Il collegamento deve usare HTTP o HTTPS.")
    query: dict[str, str | int] = {"url": url}
    if browser is not None:
        browser = browser.lower()
        if browser not in SUPPORTED_BROWSERS:
            raise BrowserProtocolError("Browser chiamante non supportato.")
        query["browser"] = browser
    if requested_at is not None:
        query["requested_at"] = requested_at
    if request_id is not None:
        query["request_id"] = _validated_request_id(request_id)
    return f"{PROTOCOL}://{TRANSLATE_ACTION}?{urlencode(query)}"


def make_overlay_uri(
    *,
    browser: str,
    requested_at: int,
    request_id: str,
) -> str:
    browser = browser.lower()
    if browser not in SUPPORTED_BROWSERS:
        raise BrowserProtocolError("Browser chiamante non supportato.")
    if requested_at < 0:
        raise BrowserProtocolError("Data della richiesta UVT non valida.")
    query = {
        "browser": browser,
        "requested_at": requested_at,
        "request_id": _validated_request_id(request_id),
    }
    return f"{PROTOCOL}://{OVERLAY_ACTION}?{urlencode(query)}"


def parse_browser_request(value: str) -> BrowserRequest:
    action = urlparse(value).netloc.lower()
    if action == OVERLAY_ACTION:
        return parse_overlay_request(value)
    if action == TRANSLATE_ACTION:
        return parse_translate_request(value)
    raise BrowserProtocolError("Collegamento UVT non valido.")


def parse_overlay_request(value: str) -> BrowserRequest:
    parsed = urlparse(value)
    if (
        parsed.scheme.lower() != PROTOCOL
        or parsed.netloc.lower() != OVERLAY_ACTION
        or parsed.path not in {"", "/"}
        or parsed.fragment
    ):
        raise BrowserProtocolError("Collegamento UVT non valido.")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if not set(query).issubset({"browser", "requested_at", "request_id"}):
        raise BrowserProtocolError("La richiesta Overlay contiene parametri non validi.")
    if any(len(values) != 1 for values in query.values()):
        raise BrowserProtocolError("Il collegamento UVT contiene parametri duplicati.")
    browser = query.get("browser", [None])[0]
    if browser is not None:
        browser = browser.lower()
        if browser not in SUPPORTED_BROWSERS:
            raise BrowserProtocolError("Browser chiamante non supportato.")
    requested_at_value = query.get("requested_at", [None])[0]
    requested_at = None
    if requested_at_value is not None:
        try:
            requested_at = int(requested_at_value)
        except ValueError as exc:
            raise BrowserProtocolError("Data della richiesta UVT non valida.") from exc
        if requested_at < 0:
            raise BrowserProtocolError("Data della richiesta UVT non valida.")
    request_id_value = query.get("request_id", [None])[0]
    request_id = (
        _validated_request_id(request_id_value)
        if request_id_value is not None
        else None
    )
    return BrowserRequest(
        browser=browser,
        requested_at=requested_at,
        request_id=request_id,
        action=OVERLAY_ACTION,
    )


def parse_translate_request(value: str) -> BrowserRequest:
    parsed = urlparse(value)
    if (
        parsed.scheme.lower() != PROTOCOL
        or parsed.netloc.lower() != TRANSLATE_ACTION
        or parsed.path not in {"", "/"}
        or parsed.fragment
    ):
        raise BrowserProtocolError("Collegamento UVT non valido.")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if not set(query).issubset(
        {"url", "browser", "requested_at", "request_id"}
    ):
        raise BrowserProtocolError("Il collegamento UVT deve contenere un solo URL.")
    if "url" not in query or len(query["url"]) != 1:
        raise BrowserProtocolError("Il collegamento UVT deve contenere un solo URL.")
    if any(len(values) != 1 for values in query.values()):
        raise BrowserProtocolError("Il collegamento UVT contiene parametri duplicati.")
    url = query["url"][0].strip()
    if not is_web_url(url):
        raise BrowserProtocolError("Il collegamento deve usare HTTP o HTTPS.")
    browser = query.get("browser", [None])[0]
    if browser is not None:
        browser = browser.lower()
        if browser not in SUPPORTED_BROWSERS:
            raise BrowserProtocolError("Browser chiamante non supportato.")
    requested_at_value = query.get("requested_at", [None])[0]
    requested_at = None
    if requested_at_value is not None:
        try:
            requested_at = int(requested_at_value)
        except ValueError as exc:
            raise BrowserProtocolError("Data della richiesta UVT non valida.") from exc
        if requested_at < 0:
            raise BrowserProtocolError("Data della richiesta UVT non valida.")
    request_id_value = query.get("request_id", [None])[0]
    request_id = (
        _validated_request_id(request_id_value)
        if request_id_value is not None
        else None
    )
    return BrowserRequest(url, browser, requested_at, request_id)


def parse_translate_uri(value: str) -> str:
    return parse_translate_request(value).url


def browser_request_is_fresh(
    request: BrowserRequest,
    *,
    now: int | None = None,
) -> bool:
    if (
        request.action != OVERLAY_ACTION
        or request.browser is None
        or request.requested_at is None
        or request.request_id is None
    ):
        return False
    current_time = int(time.time()) if now is None else now
    age = current_time - request.requested_at
    return -REQUEST_FUTURE_TOLERANCE_SECONDS <= age <= REQUEST_MAX_AGE_SECONDS


def claim_browser_request(
    request: BrowserRequest,
    *,
    claim_directory: str | Path | None = None,
    now: int | None = None,
) -> bool:
    if not browser_request_is_fresh(request, now=now):
        return False
    current_time = int(time.time()) if now is None else now
    directory = Path(claim_directory or browser_request_claim_directory())
    try:
        directory.mkdir(parents=True, exist_ok=True)
        _remove_expired_claims(directory, current_time)
    except OSError as exc:
        raise BrowserProtocolError(
            "Impossibile verificare la richiesta monouso del browser."
        ) from exc
    claim = directory / f"{request.request_id}.claim"
    try:
        claim_file = claim.open("x", encoding="ascii")
    except FileExistsError:
        return False
    except OSError as exc:
        raise BrowserProtocolError(
            "Impossibile verificare la richiesta monouso del browser."
        ) from exc
    try:
        with claim_file:
            claim_file.write(str(request.requested_at))
    except OSError as exc:
        try:
            claim.unlink()
        except OSError:
            pass
        raise BrowserProtocolError(
            "Impossibile salvare la richiesta monouso del browser."
        ) from exc
    return True


def browser_request_claim_directory() -> Path:
    return app_paths().browser_requests


def _validated_request_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise BrowserProtocolError("ID della richiesta UVT non valido.") from exc
    canonical = str(parsed)
    if parsed.version != 4 or value.lower() != canonical:
        raise BrowserProtocolError("ID della richiesta UVT non valido.")
    return canonical


def _remove_expired_claims(directory: Path, now: int) -> None:
    cutoff = now - REQUEST_CLAIM_RETENTION_SECONDS
    for claim in directory.glob("*.claim"):
        try:
            if claim.stat().st_mtime < cutoff:
                claim.unlink()
        except OSError:
            continue


def protocol_command(
    executable: str | Path | None = None,
    script: str | Path | None = None,
) -> str:
    explicit_executable = executable is not None
    executable_path = Path(executable or sys.executable).resolve()
    parts = [str(executable_path)]
    if script is not None:
        parts.append(str(Path(script).resolve()))
    elif not explicit_executable and not getattr(sys, "frozen", False):
        parts.append(
            str(Path(__file__).resolve().parents[2] / "universal_video_translator.py")
        )
    return f'{subprocess.list2cmdline(parts)} "%1"'


def register_protocol(
    command: str | None = None,
    registry: ModuleType | None = None,
) -> str:
    registry = registry or _windows_registry()
    command = command or protocol_command()
    with registry.CreateKey(registry.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
        registry.SetValueEx(key, "", 0, registry.REG_SZ, "URL:UVT Browser Link")
        registry.SetValueEx(key, "URL Protocol", 0, registry.REG_SZ, "")
    with registry.CreateKey(
        registry.HKEY_CURRENT_USER, rf"{REGISTRY_PATH}\shell\open\command"
    ) as key:
        registry.SetValueEx(key, "", 0, registry.REG_SZ, command)
    return command


def unregister_protocol(registry: ModuleType | None = None) -> None:
    registry = registry or _windows_registry()
    for suffix in (
        r"shell\open\command",
        r"shell\open",
        "shell",
        "",
    ):
        path = REGISTRY_PATH if not suffix else rf"{REGISTRY_PATH}\{suffix}"
        try:
            registry.DeleteKey(registry.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            continue


def extension_directory() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return bundle_root / "browser_extension"


def _windows_registry() -> ModuleType:
    if os.name != "nt":
        raise BrowserProtocolError("Il collegamento browser è disponibile su Windows.")
    import winreg

    return winreg
