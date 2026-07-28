from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


class MediaPreview:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None

    @staticmethod
    def _ffplay() -> str | None:
        executable = shutil.which("ffplay")
        if executable:
            return executable
        root = Path(sys.executable).resolve().parent
        for candidate in (root / "ffplay.exe", root / "_internal" / "ffplay.exe"):
            if candidate.is_file():
                return str(candidate)
        return None

    def open(self, media: str | Path) -> None:
        self.stop()
        source = str(Path(media))
        ffplay = self._ffplay()
        if ffplay:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen(
                [
                    ffplay,
                    "-loglevel",
                    "error",
                    "-autoexit",
                    "-an",
                    "-window_title",
                    "Universal Video Translator - Video",
                    source,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            return
        if os.name == "nt":
            os.startfile(source)
            return
        raise RuntimeError("ffplay non trovato.")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.process = None
