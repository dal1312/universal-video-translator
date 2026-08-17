from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .transcription import ensure_ffmpeg, find_media_tool


class MediaPreview:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.pipeline: subprocess.Popen | None = None

    @staticmethod
    def _ffplay() -> str | None:
        return find_media_tool("ffplay")

    @staticmethod
    def _ffprobe() -> str | None:
        return find_media_tool("ffprobe")

    @staticmethod
    def _has_media_streams(media: str | Path) -> tuple[bool, bool]:
        ffprobe = MediaPreview._ffprobe()
        if not ffprobe:
            return True, True

        command = [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-print_format",
            "json",
            str(media),
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            streams = json.loads(result.stdout or "{}").get("streams", [])
            has_video = any(
                stream.get("codec_type") == "video" for stream in streams
            )
            has_audio = any(
                stream.get("codec_type") == "audio" for stream in streams
            )
            return has_video, has_audio
        except Exception:
            return True, True

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

        media_path = str(Path(media))
        has_video, has_audio = self._has_media_streams(media_path)
        if not has_video and not has_audio:
            raise RuntimeError("Il file non contiene tracce audio o video.")

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

        ffmpeg_command = [
            ensure_ffmpeg(),
            "-v",
            "error",
            "-re",
            "-i",
            media_path,
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
        ]
        if has_video:
            ffmpeg_command.extend(["-map", "0:v:0"])

        ffmpeg_command.extend(
            ["-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
        )
        if has_video:
            ffmpeg_command.extend(["-af", "apad"])

        ffmpeg_command.extend(
            [
                "-shortest",
                "-max_interleave_delta",
                "1000000",
                "-f",
                "matroska",
                "pipe:1",
            ]
        )
        self.pipeline = subprocess.Popen(
            ffmpeg_command,
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

    @staticmethod
    def _terminate(process: subprocess.Popen, timeout: float) -> bool:
        if process.poll() is not None:
            return True
        try:
            process.terminate()
            process.wait(timeout=max(0.0, timeout))
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=max(0.0, timeout))
            except (subprocess.TimeoutExpired, AttributeError, OSError):
                return False
        except (AttributeError, OSError):
            return process.poll() is not None
        return process.poll() is not None

    def stop(self, timeout: float = 2.0) -> bool:
        stopped = True
        if self.pipeline:
            if self.pipeline.stdin:
                try:
                    self.pipeline.stdin.close()
                except OSError:
                    pass
            stopped = self._terminate(self.pipeline, timeout) and stopped
        self.pipeline = None
        if self.process:
            stopped = self._terminate(self.process, timeout) and stopped
        self.process = None
        return stopped
