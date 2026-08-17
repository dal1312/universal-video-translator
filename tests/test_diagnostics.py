import logging

from uvt import diagnostics


def test_diagnostics_creates_bounded_rotating_log(tmp_path) -> None:
    logger = logging.getLogger(diagnostics.LOGGER_NAME)
    old_handlers = list(logger.handlers)
    logger.handlers.clear()
    try:
        path = diagnostics.configure_diagnostics(tmp_path)
        diagnostics.logger("test").info("event=safe_test")
        for handler in logger.handlers:
            handler.flush()
        assert path == tmp_path / "uvt.log"
        assert "event=safe_test" in path.read_text(encoding="utf-8")
        handler = logger.handlers[0]
        assert handler.maxBytes == 1_000_000
        assert handler.backupCount == 3
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers[:] = old_handlers


def test_exception_log_omits_exception_message(tmp_path) -> None:
    root = logging.getLogger(diagnostics.LOGGER_NAME)
    old_handlers = list(root.handlers)
    root.handlers.clear()
    try:
        path = diagnostics.configure_diagnostics(tmp_path)
        try:
            raise RuntimeError("https://secret.example/private transcript")
        except RuntimeError as error:
            diagnostics.log_exception("test", "failed", error)
        for handler in root.handlers:
            handler.flush()
        content = path.read_text(encoding="utf-8")
        assert "RuntimeError" in content
        assert "secret.example" not in content
        assert "transcript" not in content
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers[:] = old_handlers
