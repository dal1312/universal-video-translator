from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from .paths import app_paths


LOGGER_NAME = "uvt"


def configure_diagnostics(log_directory: str | Path | None = None) -> Path | None:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        handler = logger.handlers[0]
        return Path(handler.baseFilename) if hasattr(handler, "baseFilename") else None
    logger.setLevel(logging.INFO)
    logger.propagate = False
    directory = Path(log_directory) if log_directory is not None else app_paths().logs
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "uvt.log"
        handler = RotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        logger.addHandler(logging.NullHandler())
        return None
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
    logger.info("event=diagnostics_ready")
    return path


def logger(component: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{component}")


def log_exception(component: str, event: str, error: BaseException) -> None:
    logger(component).error(
        "event=%s exception=%s location=%s",
        event,
        type(error).__name__,
        _exception_location(error.__traceback__),
    )


def install_exception_hooks() -> None:
    def system_hook(
        exception_type: type[BaseException],
        error: BaseException,
        _traceback: TracebackType | None,
    ) -> None:
        if issubclass(exception_type, (KeyboardInterrupt, SystemExit)):
            return
        log_exception("bootstrap", "uncaught_exception", error)

    def thread_hook(arguments: threading.ExceptHookArgs) -> None:
        log_exception("thread", "uncaught_thread_exception", arguments.exc_value)

    sys.excepthook = system_hook
    threading.excepthook = thread_hook


def ensure_windowed_streams() -> None:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _exception_location(traceback: TracebackType | None) -> str:
    current = traceback
    last = None
    while current is not None:
        last = current
        current = current.tb_next
    if last is None:
        return "unknown"
    filename = Path(last.tb_frame.f_code.co_filename).name
    function = last.tb_frame.f_code.co_name
    return f"{filename}:{last.tb_lineno}:{function}"
