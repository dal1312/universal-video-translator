from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable


APP_NAME = "UniversalVideoTranslator"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command(
    *,
    executable: str | Path | None = None,
    script: str | Path | None = None,
    frozen: bool | None = None,
) -> str:
    program = Path(executable or sys.executable).resolve()
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        return f'"{program}" --minimized'
    pythonw = (
        program.with_name("pythonw.exe")
        if os.name == "nt" or program.suffix.casefold() == ".exe"
        else program
    )
    if script is None:
        return f'"{pythonw}" -m uvt.gui --minimized'
    entry = Path(script).resolve()
    return f'"{pythonw}" "{entry}" --minimized'


class StartupManager:
    def is_enabled(self) -> bool:
        if os.name != "nt":
            return False
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                winreg.KEY_READ,
            ) as key:
                value, _kind = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
        except OSError:
            return False

    def set_enabled(self, enabled: bool) -> None:
        if os.name != "nt":
            raise RuntimeError("L’avvio automatico è disponibile su Windows.")
        import winreg

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key,
                    APP_NAME,
                    0,
                    winreg.REG_SZ,
                    launch_command(),
                )
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass


class TrayController:
    def __init__(
        self,
        on_show: Callable[[], None],
        on_capture: Callable[[], None],
        on_voice: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.on_show = on_show
        self.on_capture = on_capture
        self.on_voice = on_voice
        self.on_exit = on_exit
        self._icon = None

    @property
    def running(self) -> bool:
        return self._icon is not None

    def start(self) -> None:
        if self.running:
            return
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise RuntimeError(
                "Tray Windows non installata. Esegui INSTALL_WINDOWS.bat."
            ) from exc

        image = Image.new("RGBA", (64, 64), "#14171c")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (5, 5, 59, 59),
            radius=14,
            fill="#2563eb",
        )
        draw.text((18, 18), "AI", fill="white")
        menu = pystray.Menu(
            pystray.MenuItem(
                "Apri AI Overlay OS",
                lambda _icon, _item: self.on_show(),
                default=True,
            ),
            pystray.MenuItem(
                "Analizza schermo",
                lambda _icon, _item: self.on_capture(),
            ),
            pystray.MenuItem(
                "Comando vocale",
                lambda _icon, _item: self.on_voice(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Esci",
                lambda _icon, _item: self.on_exit(),
            ),
        )
        self._icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        self._icon.run_detached()

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        if icon is not None:
            icon.stop()
