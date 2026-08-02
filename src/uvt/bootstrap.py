from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Sequence

from . import __version__
from .diagnostics import (
    configure_diagnostics,
    ensure_windowed_streams,
    install_exception_hooks,
    log_exception,
    logger,
)


def main(argv: Sequence[str] | None = None) -> int:
    ensure_windowed_streams()
    log_path = configure_diagnostics()
    install_exception_hooks()
    logger("bootstrap").info(
        "event=application_start version=%s frozen=%s",
        __version__,
        bool(getattr(sys, "frozen", False)),
    )
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--install-argos-models"]:
        try:
            from .optional_engines import install_argos_packages

            install_argos_packages()
            return 0
        except Exception as error:
            log_exception("bootstrap", "argos_install_failed", error)
            _show_fatal_error(f"Installazione modelli Argos fallita: {error}")
            return 1
    try:
        from .gui import main as gui_main

        result = gui_main(arguments)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        log_exception("bootstrap", "fatal_startup_error", error)
        detail = f"\n\nLog: {log_path}" if log_path else ""
        _show_fatal_error(
            "Universal Video Translator non può avviarsi."
            f"{detail}"
        )
        return 1
    logger("bootstrap").info("event=application_exit code=%s", result)
    return result


def _show_fatal_error(message: str) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                message,
                "Universal Video Translator",
                0x10,
            )
            return
        except Exception:
            pass
    try:
        print(message, file=sys.stderr)
    except Exception:
        pass
