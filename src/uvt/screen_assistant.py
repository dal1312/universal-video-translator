from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import tempfile
import threading
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class ScreenAssistantError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ScreenCapture:
    title: str
    image: object


def _creation_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def find_tesseract() -> str | None:
    executable = shutil.which("tesseract")
    if executable:
        return executable
    if os.name != "nt":
        return None
    candidates = (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Tesseract-OCR"
        / "tesseract.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "Tesseract-OCR"
        / "tesseract.exe",
    )
    return next((str(path) for path in candidates if path.is_file()), None)


def normalize_ocr_text(text: str) -> str:
    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.replace("\r", "\n").split("\n")
    ]
    return "\n".join(line for line in lines if line).strip()


def _foreground_window() -> tuple[str, tuple[int, int, int, int] | None]:
    if os.name != "nt":
        return "Schermo", None
    user32 = ctypes.windll.user32
    handle = user32.GetForegroundWindow()
    if not handle:
        return "Schermo", None

    length = user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    rect = wintypes.RECT()
    if not user32.GetWindowRect(handle, ctypes.byref(rect)):
        return buffer.value or "Finestra attiva", None
    if rect.right <= rect.left or rect.bottom <= rect.top:
        return buffer.value or "Finestra attiva", None
    return (
        buffer.value or "Finestra attiva",
        (rect.left, rect.top, rect.right, rect.bottom),
    )


def capture_active_window() -> ScreenCapture:
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise ScreenAssistantError(
            "Pillow non installato. Esegui nuovamente INSTALL_WINDOWS.bat."
        ) from exc

    title, bounds = _foreground_window()
    try:
        image = ImageGrab.grab(bbox=bounds, all_screens=True)
    except Exception as exc:
        raise ScreenAssistantError(
            f"Impossibile acquisire la finestra attiva: {exc}"
        ) from exc
    return ScreenCapture(title=title, image=image)


def extract_text(image: object) -> str:
    executable = find_tesseract()
    if not executable:
        raise ScreenAssistantError(
            "Tesseract OCR non trovato. Installa Tesseract e riavvia il programma."
        )
    with tempfile.TemporaryDirectory(prefix="uvt-screen-") as directory:
        screenshot = Path(directory) / "screen.png"
        try:
            image.save(screenshot, format="PNG")
        except Exception as exc:
            raise ScreenAssistantError(
                f"Impossibile salvare lo screenshot: {exc}"
            ) from exc
        completed = subprocess.run(
            [executable, str(screenshot), "stdout", "--psm", "6"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
            check=False,
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "errore OCR sconosciuto"
        raise ScreenAssistantError(f"Tesseract OCR: {detail}")
    text = normalize_ocr_text(completed.stdout)
    if not text:
        raise ScreenAssistantError(
            "Nessun testo rilevato nella finestra attiva."
        )
    return text


class GlobalHotkey:
    _HOTKEY_ID = 0xA103
    _MOD_CONTROL = 0x0002
    _VK_SPACE = 0x20
    _WM_HOTKEY = 0x0312
    _WM_QUIT = 0x0012

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self.error: str | None = None

    def start(self) -> bool:
        if os.name != "nt":
            self.error = "La scorciatoia globale è disponibile su Windows."
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._ready.clear()
        self.error = None
        self._thread = threading.Thread(
            target=self._run,
            name="uvt-global-hotkey",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=2)
        return self.error is None and self._thread.is_alive()

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())
        if not user32.RegisterHotKey(
            None, self._HOTKEY_ID, self._MOD_CONTROL, self._VK_SPACE
        ):
            self.error = (
                "CTRL+SPACE è già utilizzato da un altro programma."
            )
            self._ready.set()
            return
        self._ready.set()
        message = wintypes.MSG()
        try:
            while user32.GetMessageW(
                ctypes.byref(message), None, 0, 0
            ) > 0:
                if (
                    message.message == self._WM_HOTKEY
                    and message.wParam == self._HOTKEY_ID
                ):
                    try:
                        self.callback()
                    except Exception:
                        continue
        finally:
            user32.UnregisterHotKey(None, self._HOTKEY_ID)
            self._thread_id = 0

    def stop(self) -> None:
        if os.name == "nt" and self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(
                self._thread_id, self._WM_QUIT, 0, 0
            )
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None

