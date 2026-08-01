from __future__ import annotations

import ctypes
import os
import queue
import threading
from ctypes import wintypes


HOTKEY_BINDINGS = {
    1: ("toggle", 0x77),  # Ctrl+Alt+F8
    2: ("stop", 0x78),  # Ctrl+Alt+F9
    3: ("overlay", 0x79),  # Ctrl+Alt+F10
    4: ("volume_down", 0x28),  # Ctrl+Alt+Down
    5: ("volume_up", 0x26),  # Ctrl+Alt+Up
}


class GlobalHotkeys:
    def __init__(self) -> None:
        self._commands: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._available = False

    def start(self) -> bool:
        if os.name != "nt":
            return False
        self._thread = threading.Thread(
            target=self._run, name="uvt-global-hotkeys", daemon=True
        )
        self._thread.start()
        self._ready.wait(1.5)
        return self._available

    def drain(self) -> list[str]:
        commands: list[str] = []
        while True:
            try:
                commands.append(self._commands.get_nowait())
            except queue.Empty:
                return commands

    def close(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=1.5)
        self._thread = None
        self._thread_id = 0

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())
        registered: list[int] = []
        try:
            for identifier, (_command, key) in HOTKEY_BINDINGS.items():
                if user32.RegisterHotKey(None, identifier, 0x0001 | 0x0002, key):
                    registered.append(identifier)
            self._available = bool(registered)
            self._ready.set()
            message = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and message.wParam in registered:
                    self._commands.put(HOTKEY_BINDINGS[int(message.wParam)][0])
        finally:
            for identifier in registered:
                user32.UnregisterHotKey(None, identifier)
            self._ready.set()


def change_system_volume(direction: int) -> None:
    if os.name != "nt" or direction == 0:
        return
    key = 0xAF if direction > 0 else 0xAE
    user32 = ctypes.windll.user32
    user32.keybd_event(key, 0, 0, 0)
    user32.keybd_event(key, 0, 0x0002, 0)
