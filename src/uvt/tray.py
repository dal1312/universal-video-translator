from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .branding import create_icon


class TrayController:
    """Optional Windows notification-area controller."""

    def __init__(
        self,
        *,
        on_open: Callable[[], None],
        on_stop: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_open = on_open
        self._on_stop = on_stop
        self._on_quit = on_quit
        self._icon: Any = None

    def start(self) -> bool:
        try:
            import pystray
        except ImportError:
            return False

        image = create_icon(64)
        menu = pystray.Menu(
            pystray.MenuItem("Apri UVT", lambda *_: self._on_open(), default=True),
            pystray.MenuItem("Stop AI Overlay", lambda *_: self._on_stop()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Esci completamente", lambda *_: self._on_quit()),
        )
        self._icon = pystray.Icon(
            "universal-video-translator",
            image,
            "Universal Video Translator",
            menu,
        )
        self._icon.run_detached()
        return True

    def notify(self, message: str) -> None:
        if self._icon is not None:
            try:
                self._icon.notify(message, "Universal Video Translator")
            except Exception:
                pass

    def close(self) -> None:
        icon, self._icon = self._icon, None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
