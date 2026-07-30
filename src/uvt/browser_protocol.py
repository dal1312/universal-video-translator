from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlencode, urlparse

from .downloader import is_web_url

PROTOCOL = "uvt"
ACTION = "translate"
REGISTRY_PATH = rf"Software\Classes\{PROTOCOL}"


class BrowserProtocolError(ValueError):
    pass


def make_translate_uri(url: str) -> str:
    if not is_web_url(url):
        raise BrowserProtocolError("Il collegamento deve usare HTTP o HTTPS.")
    return f"{PROTOCOL}://{ACTION}?{urlencode({'url': url})}"


def parse_translate_uri(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme.lower() != PROTOCOL
        or parsed.netloc.lower() != ACTION
        or parsed.path not in {"", "/"}
        or parsed.fragment
    ):
        raise BrowserProtocolError("Collegamento UVT non valido.")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) != {"url"} or len(query["url"]) != 1:
        raise BrowserProtocolError("Il collegamento UVT deve contenere un solo URL.")
    url = query["url"][0].strip()
    if not is_web_url(url):
        raise BrowserProtocolError("Il collegamento deve usare HTTP o HTTPS.")
    return url


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
