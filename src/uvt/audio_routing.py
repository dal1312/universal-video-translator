from __future__ import annotations

import subprocess
import sys
from pathlib import Path


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
