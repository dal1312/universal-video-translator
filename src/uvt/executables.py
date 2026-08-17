from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def find_executable(name: str) -> str | None:
    """Resolve a supported runtime from PATH, the bundle, or known installs."""
    discovered = shutil.which(name)
    if discovered:
        return discovered

    filename = name if name.casefold().endswith(".exe") else f"{name}.exe"
    runtime_root = Path(sys.executable).resolve().parent
    candidates = [runtime_root / filename, runtime_root / "_internal" / filename]

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        local_root = Path(local_app_data)
        if name.casefold().removesuffix(".exe") == "ollama":
            candidates.append(local_root / "Programs" / "Ollama" / "ollama.exe")
        if name.casefold().removesuffix(".exe") in {"ffmpeg", "ffplay", "ffprobe"}:
            packages = local_root / "Microsoft" / "WinGet" / "Packages"
            candidates.extend(
                sorted(
                    packages.glob(f"Gyan.FFmpeg*/ffmpeg-*/bin/{filename}"),
                    reverse=True,
                )
            )

    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            # Windows can deny metadata access to a stale or restricted
            # installation (for example Ollama under AppData). Treat it as
            # unavailable so readiness detection never crashes its worker.
            continue
    return None
