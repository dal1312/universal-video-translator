from __future__ import annotations

import ctypes
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
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

    def __init__(
        self,
        callback: Callable[[], None],
        *,
        modifiers: int | None = None,
        virtual_key: int | None = None,
        hotkey_id: int | None = None,
        label: str = "CTRL+SPACE",
    ) -> None:
        self.callback = callback
        self.modifiers = (
            self._MOD_CONTROL if modifiers is None else modifiers
        )
        self.virtual_key = self._VK_SPACE if virtual_key is None else virtual_key
        self.hotkey_id = self._HOTKEY_ID if hotkey_id is None else hotkey_id
        self.label = label
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
            None,
            self.hotkey_id,
            self.modifiers,
            self.virtual_key,
        ):
            self.error = (
                f"{self.label} è già utilizzato da un altro programma."
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
                    and message.wParam == self.hotkey_id
                ):
                    try:
                        self.callback()
                    except Exception:
                        continue
        finally:
            user32.UnregisterHotKey(None, self.hotkey_id)
            self._thread_id = 0

    def stop(self) -> None:
        if os.name == "nt" and self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(
                self._thread_id, self._WM_QUIT, 0, 0
            )
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None


class ContinuousOCR:
    def __init__(
        self,
        on_text: Callable[[str, str, object], None],
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        interval: float = 4.0,
    ) -> None:
        self.on_text = on_text
        self.on_status = on_status or (lambda _text: None)
        self.on_error = on_error or (lambda _error: None)
        self.interval = max(2.0, float(interval))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_digest = ""

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="uvt-continuous-ocr",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        self.on_status("OCR continuo attivo")
        while not self._stop.is_set():
            try:
                capture = capture_active_window()
                title = capture.title.strip()
                if title.casefold().startswith(
                    ("ai overlay os", "universal video translator")
                ):
                    if self._stop.wait(self.interval):
                        break
                    continue
                text = extract_text(capture.image)
                digest = hashlib.sha256(
                    f"{title}\0{text}".encode("utf-8")
                ).hexdigest()
                if digest != self._last_digest:
                    self._last_digest = digest
                    self.on_text(title, text, capture.image)
            except ScreenAssistantError:
                pass
            except Exception as exc:
                self.on_error(exc)
                break
            if self._stop.wait(self.interval):
                break
        self.on_status("OCR continuo interrotto")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None


class RegionSelector(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        on_selected: Callable[[object, tuple[int, int, int, int]], None],
    ) -> None:
        super().__init__(master)
        self.on_selected = on_selected
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.28)
        self.configure(bg="black")
        self._origin_x = self._origin_y = 0
        self._start_x = self._start_y = 0
        self._rectangle = None

        if os.name == "nt":
            user32 = ctypes.windll.user32
            self._origin_x = int(user32.GetSystemMetrics(76))
            self._origin_y = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
        else:
            width = self.winfo_screenwidth()
            height = self.winfo_screenheight()
        self.geometry(
            f"{width}x{height}{self._origin_x:+d}{self._origin_y:+d}"
        )
        self.canvas = tk.Canvas(
            self,
            bg="black",
            cursor="crosshair",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            width // 2,
            35,
            text="Trascina per selezionare l’area — ESC annulla",
            fill="white",
            font=("Segoe UI", 14, "bold"),
        )
        self.canvas.bind("<ButtonPress-1>", self._start)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._finish)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.focus_force()
        self.grab_set()

    def _start(self, event: tk.Event) -> None:
        self._start_x, self._start_y = event.x, event.y
        self._rectangle = self.canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="#3b82f6",
            width=3,
        )

    def _move(self, event: tk.Event) -> None:
        if self._rectangle is not None:
            self.canvas.coords(
                self._rectangle,
                self._start_x,
                self._start_y,
                event.x,
                event.y,
            )

    def _finish(self, event: tk.Event) -> None:
        x1, x2 = sorted((self._start_x, event.x))
        y1, y2 = sorted((self._start_y, event.y))
        if x2 - x1 < 20 or y2 - y1 < 20:
            self.destroy()
            return
        bounds = (
            x1 + self._origin_x,
            y1 + self._origin_y,
            x2 + self._origin_x,
            y2 + self._origin_y,
        )
        self.grab_release()
        self.withdraw()
        self.after(120, self._capture, bounds)

    def _capture(self, bounds: tuple[int, int, int, int]) -> None:
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab(bbox=bounds, all_screens=True)
            self.on_selected(image, bounds)
        finally:
            self.destroy()
