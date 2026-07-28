from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .transcription import ensure_ffmpeg


class MediaPreview:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.pipeline: subprocess.Popen | None = None

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

    def open(self, media: str | Path, mute_audio: bool = True) -> None:
        self.stop()
        source = str(Path(media))
        ffplay = self._ffplay()
        if ffplay:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            command = [
                ffplay,
                "-loglevel",
                "error",
                "-autoexit",
                "-x",
                "960",
                "-y",
                "540",
                "-window_title",
                "Universal Video Translator - Video",
                source,
            ]
            if mute_audio:
                command.insert(4, "-an")
            self.process = subprocess.Popen(
                command,
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

    def open_pcm_stream(
        self, media: str | Path, samplerate: int = 24000
    ):
        self.stop()
        ffplay = self._ffplay()
        if not ffplay:
            raise RuntimeError("ffplay non trovato.")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [
                ffplay,
                "-loglevel",
                "error",
                "-autoexit",
                "-x",
                "960",
                "-y",
                "540",
                "-window_title",
                "Universal Video Translator - Video",
                "-i",
                "pipe:0",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        if self.process.stdin is None:
            raise RuntimeError("Impossibile aprire lo stream del player.")
        self.pipeline = subprocess.Popen(
            [
                ensure_ffmpeg(),
                "-v",
                "error",
                "-re",
                "-i",
                str(Path(media)),
                "-thread_queue_size",
                "512",
                "-f",
                "f32le",
                "-ar",
                str(samplerate),
                "-ac",
                "1",
                "-i",
                "pipe:0",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-af",
                "apad",
                "-shortest",
                "-max_interleave_delta",
                "1000000",
                "-f",
                "matroska",
                "pipe:1",
            ],
            stdin=subprocess.PIPE,
            stdout=self.process.stdin,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            bufsize=0,
        )
        self.process.stdin.close()
        if self.pipeline.stdin is None:
            raise RuntimeError("Impossibile aprire lo stream audio.")
        return self.pipeline.stdin

    def toggle_pause(self) -> bool:
        if os.name != "nt" or not self.process:
            return False
        import ctypes

        target_pid = self.process.pid
        found = False
        user32 = ctypes.windll.user32

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def callback(window, _param):
            nonlocal found
            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
            if process_id.value == target_pid:
                user32.PostMessageW(window, 0x0100, ord("P"), 0)
                user32.PostMessageW(window, 0x0101, ord("P"), 0)
                found = True
                return False
            return True

        user32.EnumWindows(callback, 0)
        return found

    def wait(self) -> int:
        process = self.process
        return process.wait() if process else 0

    def stop(self) -> None:
        if self.pipeline:
            if self.pipeline.stdin:
                try:
                    self.pipeline.stdin.close()
                except OSError:
                    pass
            if self.pipeline.poll() is None:
                self.pipeline.terminate()
        self.pipeline = None
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.process = None
