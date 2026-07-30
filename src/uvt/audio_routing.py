from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class AudioRoutingError(RuntimeError):
    pass


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


def _set_firefox_output(device: str) -> None:
    command = [
        str(sound_volume_view_path()),
        "/SetAppDefault",
        device,
        "all",
        "firefox.exe",
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
        raise AudioRoutingError(f"Routing audio Firefox fallito: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise AudioRoutingError(
            f"SoundVolumeView ha restituito {result.returncode}{suffix}"
        )


def route_firefox_to_cable() -> None:
    _set_firefox_output("CABLE Input")


def restore_firefox_default() -> None:
    _set_firefox_output("DefaultRenderDevice")
