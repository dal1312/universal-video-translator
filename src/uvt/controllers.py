from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import threading
from typing import Any

from .audio_routing import (
    AudioRoutingLeaseManager,
    AudioRoutingError,
    BrowserVolumeDucker,
)
from .documents import DocumentTranslator
from .ollama import OllamaTranslator
from .session import SessionMode, TranslationSession
from .workflow import PreparedPlayback, RunSettings, TranslationWorkflow


class FileTranslationController:
    def __init__(
        self,
        session: TranslationSession,
        workflow: TranslationWorkflow,
    ) -> None:
        self.session = session
        self.workflow = workflow

    def begin(self) -> int:
        return self.session.begin(SessionMode.FILE)

    def prepare(
        self, settings: RunSettings, run_id: int
    ) -> PreparedPlayback | None:
        prepared = self.workflow.prepare(settings)
        if not self.session.accepts(SessionMode.FILE, run_id):
            self.discard(prepared)
            return None
        return prepared

    def activate(self, run_id: int) -> bool:
        return self.session.activate(SessionMode.FILE, run_id)

    def stop(self, player, progressive, preview) -> None:
        self.session.begin_stopping(SessionMode.FILE)
        for playback in (progressive, player):
            if playback:
                playback.stop()
        preview.stop()
        self.session.finish(SessionMode.FILE)

    @staticmethod
    def discard(prepared: PreparedPlayback) -> None:
        for playback in (prepared.progressive, prepared.player):
            if playback:
                playback.stop()


class LiveTranslationController:
    def __init__(self, session: TranslationSession) -> None:
        self.session = session

    def begin(self) -> int:
        return self.session.begin(SessionMode.LIVE)

    def activate(self, live: Any, run_id: int) -> bool:
        try:
            live.start()
        except Exception:
            self.session.fail(SessionMode.LIVE, run_id)
            raise
        return self.session.activate(SessionMode.LIVE, run_id)

    def stop(self, live) -> bool:
        self.session.begin_stopping(SessionMode.LIVE)
        if live is not None and live.running and not live.stop():
            return False
        self.session.finish(SessionMode.LIVE)
        return True


class DocumentTranslationController:
    def __init__(self, session: TranslationSession) -> None:
        self.session = session
        self.cancel = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self.cancel.is_set()

    def begin(self) -> int:
        self.cancel.clear()
        return self.session.begin(SessionMode.DOCUMENT)

    def translate(
        self,
        source: Path,
        destination: Path,
        *,
        language: str,
        model: str,
        run_id: int,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Path | None:
        translator = DocumentTranslator(OllamaTranslator(model=model))
        result = translator.translate(
            source,
            destination,
            source_language=language,
            cancel=self.cancel,
            on_progress=on_progress,
        )
        if not self.session.accepts(SessionMode.DOCUMENT, run_id):
            return None
        return result

    def request_stop(self) -> None:
        self.session.begin_stopping(SessionMode.DOCUMENT)
        self.cancel.set()

    def finish(self) -> None:
        self.session.finish(SessionMode.DOCUMENT)


class BrowserAudioController:
    def __init__(
        self,
        router: AudioRoutingLeaseManager,
        *,
        selected_browser: Callable[[], str],
        on_status: Callable[[str], None],
    ) -> None:
        self.router = router
        self.selected_browser = selected_browser
        self.on_status = on_status
        self.routed_browser: str | None = None

    def route(self) -> bool:
        browser = self.selected_browser()
        self.routed_browser = browser
        try:
            self.router.route(browser)
        except AudioRoutingError as error:
            self.restore()
            self.on_status(
                f"Routing automatico {browser.title()} non riuscito: {error}"
            )
            return False
        self.on_status(
            f"{browser.title()} su CABLE Input; voce su uscita Windows"
        )
        return True

    def restore(self) -> bool:
        browser = self.routed_browser
        if browser is None:
            return True
        try:
            self.router.restore(browser)
        except AudioRoutingError as error:
            self.on_status(
                f"Ripristina {browser.title()} manualmente: {error}"
            )
            return False
        self.routed_browser = None
        return True

    def ducker(self, percent: int) -> BrowserVolumeDucker:
        return BrowserVolumeDucker(self.selected_browser(), percent)
