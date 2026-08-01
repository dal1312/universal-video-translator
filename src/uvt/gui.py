from __future__ import annotations

import json
import os
import sys
import tkinter as tk
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .audio_routing import (
    AudioRoutingLeaseManager,
    AudioRoutingError,
)
from .browser_protocol import (
    BrowserRequest,
    BrowserProtocolError,
    FOCUS_ACTION,
    OVERLAY_ACTION,
    STOP_ACTION,
    SUPPORTED_BROWSERS,
    claim_browser_request,
    extension_directory,
    parse_browser_request,
    register_protocol,
)
from .browser_bridge import LocalBrowserBridge
from .cache import TranslationCache
from .controllers import (
    BrowserAudioController,
    FileTranslationController,
    LiveTranslationController,
)
from .diagnostics import log_exception, logger
from .documents import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    DocumentTranslationError,
    DocumentTranslator,
    default_document_destination,
)
from .error_messages import present_error
from .hotkeys import GlobalHotkeys, change_system_volume
from .glossary import TranslationGlossary
from .live import (
    LiveTranslator,
    capture_device_names,
    preferred_cable_output,
)
from .media_player import MediaPreview
from .instance_ipc import InstanceEvent, InstanceIPCError, SingleInstanceBroker
from .ollama import OllamaTranslator
from .overlay import SubtitleOverlay
from .player import SubtitlePlayer
from .progressive import ProgressiveDubPlayer
from .profiles import profile_by_key, profile_key_from_label
from .readiness import (
    SystemReadiness,
    detect_system_readiness,
    select_available_model,
)
from .runtime import RuntimeSupervisor
from .session import SessionMode, TranslationSession
from .settings import AppSettings, SettingsStore
from .tts import KOKORO_VOICES, windows_voice_names
from .tray import TrayController
from .ui_layout import build_window
from .ui_theme import apply_theme
from .updates import AutomaticUpdater, UpdateResult, launch_pending_update
from .workflow import PreparedPlayback, RunSettings, TranslationWorkflow


class TranslatorWindow(tk.Tk):
    def __init__(
        self,
        initial_browser: str | None = None,
        auto_start_overlay: bool = False,
        *,
        audio_router: AudioRoutingLeaseManager | None = None,
        settings_store: SettingsStore | None = None,
        instance_broker: SingleInstanceBroker | None = None,
        browser_bridge: LocalBrowserBridge | None = None,
        check_updates: bool = True,
    ) -> None:
        self._settings_store = settings_store or SettingsStore()
        saved = self._settings_store.load()
        super().__init__()
        self.title("Universal Video Translator | Modern UI")
        try:
            self.geometry(saved.window_geometry)
        except tk.TclError:
            self.geometry("1280x820")
        self.minsize(1120, 720)
        self.player: SubtitlePlayer | None = None
        self.progressive: ProgressiveDubPlayer | None = None
        self.live: LiveTranslator | None = None
        self._source_browser = (
            initial_browser if initial_browser in SUPPORTED_BROWSERS else None
        )
        self._browser_overlay_pending = auto_start_overlay
        self._browser_audio_routed: str | None = None
        self._audio_router = audio_router or AudioRoutingLeaseManager()
        self._instance_broker = instance_broker
        self._browser_bridge = browser_bridge
        self._browser_bridge_poll_job: str | None = None
        self._hotkey_poll_job: str | None = None
        self._instance_poll_job: str | None = None
        self._settings_save_job: str | None = None
        self._closing = False
        self._background_notice_shown = False
        self.session = TranslationSession()
        self._file_run_id = 0
        self._live_run_id = 0
        self._document_run_id = 0
        self._document_cancel = threading.Event()
        self._runtime = RuntimeSupervisor()
        self._capture_devices_loaded = False
        self.preview = MediaPreview()
        self.workflow = TranslationWorkflow(
            self.preview,
            on_text=lambda text: self._call_in_ui(self._show_text, text),
            on_status=lambda text: self._call_in_ui(self._set_status, text),
            on_error=lambda error: self._call_in_ui(self._show_error, error),
        )
        self.file_controller = FileTranslationController(
            self.session, self.workflow
        )
        self.live_controller = LiveTranslationController(self.session)
        self.browser_audio_controller = BrowserAudioController(
            self._audio_router,
            selected_browser=self._routing_browser,
            on_status=lambda text: self.status_var.set(text),
        )
        self.overlay = SubtitleOverlay(self)
        self.overlay.apply_preferences(
            geometry=saved.overlay_geometry,
            alpha=saved.overlay_alpha,
            font_size=saved.overlay_font_size,
        )

        self.file_var = tk.StringVar()
        self.document_var = tk.StringVar()
        self.document_output_var = tk.StringVar()
        self.source_mode_var = tk.StringVar(value="file")
        self.model_var = tk.StringVar(value=saved.ollama_model)
        self.language_var = tk.StringVar(value=saved.language)
        self.rate_var = tk.IntVar(value=saved.rate)
        self.whisper_var = tk.StringVar(value=saved.whisper_model)
        self.speech_engine_var = tk.StringVar(value=saved.speech_engine)
        self.voice_var = tk.StringVar(value=saved.voice)
        self.show_text_var = tk.BooleanVar(value=False)
        self.live_voice_var = tk.BooleanVar(value=saved.live_voice)
        self.capture_device_var = tk.StringVar(
            value=saved.capture_device or "Audio di sistema (predefinito)"
        )
        self.cookies_var = tk.StringVar(value=saved.cookies_browser)
        self.routing_browser_var = tk.StringVar(value=saved.routing_browser)
        self.profile_var = tk.StringVar(
            value=profile_by_key(saved.performance_profile).label
        )
        self.auto_ducking_var = tk.BooleanVar(value=saved.auto_ducking)
        self.latency_var = tk.StringVar(value="Latenza: in attesa")
        self.latency_detail_var = tk.StringVar(value="")
        self._latest_latency: dict[str, float | int] = {}
        self._update_status = "checking"
        self.status_var = tk.StringVar(value="Pronto")
        self.system_status_var = tk.StringVar(value="Verifica configurazione…")
        self._preflight_running = False
        self.dark_mode = saved.dark_mode
        self.advanced_visible = False
        self._configure_theme()
        self._build()
        self._restore_saved_layout()
        self._bind_settings_persistence()
        if self._instance_broker is not None:
            self._schedule_instance_poll()
        if self._browser_bridge is not None:
            self._schedule_browser_bridge_poll()
        if auto_start_overlay:
            self.iconify()
            self.after_idle(self._show_browser_overlay, False)
        self._start_worker(self._load_models, name="uvt-model-discovery")
        self._start_worker(
            self._load_capture_devices,
            name="uvt-audio-discovery",
        )
        self._start_worker(
            self._detect_readiness,
            name="uvt-readiness",
        )
        self.protocol("WM_DELETE_WINDOW", self._request_close)
        self._tray = TrayController(
            on_open=lambda: self.after(0, self._restore_from_background),
            on_stop=lambda: self.after(0, self._stop_from_tray),
            on_quit=lambda: self.after(0, self._close),
        )
        self._tray.start()
        self._hotkeys = GlobalHotkeys()
        if self._hotkeys.start():
            self._schedule_hotkey_poll()
        self._updater = AutomaticUpdater(__version__)
        if check_updates:
            self._start_worker(self._check_updates, name="uvt-update-check")
        try:
            self.after_idle(self._ensure_window_on_screen)
        except (RecursionError, RuntimeError, tk.TclError):
            # Tk may be intentionally absent in headless startup tests.
            pass

    def _start_worker(
        self,
        target,
        *args,
        name: str,
    ) -> threading.Thread:
        return self._runtime.start(target, *args, name=name)

    def _ensure_window_on_screen(self) -> None:
        if self.state() == "zoomed":
            return
        self.update_idletasks()
        width = min(self.winfo_width(), self.winfo_screenwidth())
        height = min(self.winfo_height(), self.winfo_screenheight())
        x = max(0, min(self.winfo_x(), self.winfo_screenwidth() - width))
        y = max(0, min(self.winfo_y(), self.winfo_screenheight() - height))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _join_workers(self, timeout: float = 2.0) -> bool:
        return self._runtime.join(timeout)

    def _call_in_ui(self, callback, *args) -> None:
        if self._closing:
            return
        try:
            self.after(0, callback, *args)
        except (RuntimeError, tk.TclError):
            if not self._closing:
                raise

    def report_callback_exception(
        self,
        exception_type: type[BaseException],
        error: BaseException,
        _traceback,
    ) -> None:
        log_exception("tk", "callback_failed", error)
        try:
            messagebox.showerror(
                "Errore interno",
                "Operazione non completata. Consulta il log diagnostico in "
                "%LOCALAPPDATA%\\UniversalVideoTranslator\\logs.",
            )
        except tk.TclError:
            pass

    def _build(self) -> None:
        build_window(self)

    def _toggle_advanced_settings(self) -> None:
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced_frame.grid()
            self.advanced_button.configure(
                text="Nascondi impostazioni avanzate"
            )
        else:
            self.advanced_frame.grid_remove()
            self.advanced_button.configure(
                text="Impostazioni avanzate"
            )
        self._schedule_settings_save()

    def _toggle_settings_panel(self) -> None:
        if self.settings_visible:
            self.main_body.forget(self.settings_card)
            self.settings_visible = False
            return
        self.main_body.insert(0, self.settings_card, weight=1)
        self.settings_visible = True

    def _refresh_output_visibility(self) -> None:
        output_card = getattr(self, "output_card", None)
        if output_card is None:
            return
        workspace = output_card.master
        if self.show_text_var.get():
            output_card.grid()
            workspace.rowconfigure(1, weight=0)
            workspace.rowconfigure(2, weight=1)
        else:
            output_card.grid_remove()
            workspace.rowconfigure(1, weight=1)
            workspace.rowconfigure(2, weight=0)

    def _apply_profile(self, _event=None) -> None:
        profile = profile_by_key(profile_key_from_label(self.profile_var.get()))
        self.whisper_var.set(profile.whisper_model)
        self.status_var.set(
            f"Profilo {profile.label}: Whisper {profile.whisper_model}, "
            f"segmenti fino a {profile.max_segment_seconds:.1f}s"
        )

    def _update_latency(self, metrics: dict[str, float | int]) -> None:
        self._latest_latency.update(metrics)
        current = float(self._latest_latency.get("current_ms", 0.0))
        median_value = float(self._latest_latency.get("median_ms", 0.0))
        self.latency_var.set(
            f"Latenza: {current / 1000:.2f}s · mediana {median_value / 1000:.2f}s"
        )
        self.latency_detail_var.set(
            "Acquisizione {capture:.0f}ms · Whisper {whisper:.0f}ms · "
            "Traduzione {translation:.0f}ms · Code {queue:.0f}ms · "
            "Voce {speed:.2f}× · Scarto {offset:.0f}ms".format(
                capture=float(self._latest_latency.get("capture_ms", 0.0)),
                whisper=float(self._latest_latency.get("transcribe_ms", 0.0)),
                translation=float(self._latest_latency.get("translate_ms", 0.0)),
                queue=float(
                    self._latest_latency.get(
                        "speech_queue_ms",
                        self._latest_latency.get("queue_ms", 0.0),
                    )
                ),
                speed=float(self._latest_latency.get("adaptive_speed", 1.0)),
                offset=float(self._latest_latency.get("sync_offset_ms", 0.0)),
            )
        )

    def _copy_diagnostics(self) -> None:
        payload = {
            "session": {
                "mode": self.session.mode.value if self.session.mode else None,
                "phase": self.session.phase.value,
            },
            "profile": profile_key_from_label(self.profile_var.get()),
            "browser": self._routing_browser(),
            "capture_device": self.capture_device_var.get(),
            "latency": self._latest_latency,
        }
        self.clipboard_clear()
        self.clipboard_append(json.dumps(payload, ensure_ascii=False, indent=2))
        self.status_var.set("Diagnostica copiata negli appunti")

    def _open_glossary(self) -> None:
        try:
            path = TranslationGlossary().ensure_template()
            os.startfile(path)  # type: ignore[attr-defined]
            self.status_var.set(
                "Glossario aperto: le modifiche saranno applicate automaticamente"
            )
        except OSError as error:
            messagebox.showerror("Glossario", str(error))

    def _scroll_settings(self, event: tk.Event) -> None:
        delta = int(-event.delta / 120)
        if delta:
            self.settings_canvas.yview_scroll(delta, "units")

    def _restore_saved_layout(self) -> None:
        if "theme_button" in self.__dict__:
            self.theme_button.configure(
                text="Tema chiaro" if self.dark_mode else "Tema scuro"
            )
        if "advanced_frame" not in self.__dict__:
            return
        if self.advanced_visible:
            self.advanced_frame.grid()
            self.advanced_button.configure(text="Nascondi impostazioni avanzate")

    def _bind_settings_persistence(self) -> None:
        variables = (
            self.model_var,
            self.language_var,
            self.rate_var,
            self.whisper_var,
            self.speech_engine_var,
            self.voice_var,
            self.show_text_var,
            self.live_voice_var,
            self.capture_device_var,
            self.cookies_var,
            self.routing_browser_var,
            self.profile_var,
            self.auto_ducking_var,
        )
        for variable in variables:
            if hasattr(variable, "trace_add"):
                variable.trace_add(
                    "write", lambda *_args: self._schedule_settings_save()
                )

    def _schedule_settings_save(self) -> None:
        if self._closing:
            return
        if self._settings_save_job:
            try:
                self.after_cancel(self._settings_save_job)
            except tk.TclError:
                pass
        self._settings_save_job = self.after(600, self._save_app_settings)

    def _current_app_settings(self) -> AppSettings:
        overlay_geometry, overlay_alpha, overlay_font_size = self.overlay.preferences()
        return AppSettings(
            ollama_model=self.model_var.get().strip() or "translategemma:latest",
            language=self.language_var.get(),
            rate=int(self.rate_var.get()),
            whisper_model=self.whisper_var.get(),
            speech_engine=self.speech_engine_var.get(),
            voice=self.voice_var.get(),
            show_text=bool(self.show_text_var.get()),
            live_voice=bool(self.live_voice_var.get()),
            capture_device=self.capture_device_var.get(),
            cookies_browser=self.cookies_var.get(),
            routing_browser=self.routing_browser_var.get(),
            performance_profile=profile_key_from_label(self.profile_var.get()),
            auto_ducking=bool(self.auto_ducking_var.get()),
            dark_mode=self.dark_mode,
            advanced_visible=self.advanced_visible,
            window_geometry=self.geometry(),
            overlay_geometry=overlay_geometry,
            overlay_alpha=overlay_alpha,
            overlay_font_size=overlay_font_size,
        )

    def _save_app_settings(self) -> None:
        self._settings_save_job = None
        try:
            self._settings_store.save(self._current_app_settings())
        except Exception as error:
            log_exception("settings", "save_failed", error)

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleziona sottotitoli",
            filetypes=(
                ("Video, audio o sottotitoli", "*.mp4 *.mkv *.webm *.mp3 *.wav *.m4a *.srt *.vtt"),
                ("Tutti i file", "*.*"),
            ),
        )
        if path:
            self.file_var.set(path)

    def _browse_document(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleziona documento",
            filetypes=(
                ("Documenti supportati", "*.txt *.md *.html *.htm *.epub *.docx *.pdf"),
                ("Tutti i file", "*.*"),
            ),
        )
        if path:
            self.document_var.set(path)
            self.document_output_var.set(str(default_document_destination(path)))

    def _browse_document_output(self) -> None:
        source = Path(self.document_var.get())
        path = filedialog.asksaveasfilename(
            title="Salva documento tradotto",
            initialfile=f"{source.stem or 'documento'}.italiano{source.suffix}",
            defaultextension=source.suffix,
        )
        if path:
            self.document_output_var.set(path)

    def _select_source_mode(self, mode: str) -> None:
        if mode not in {"file", "live", "document"}:
            return
        if self.session.busy:
            active = self.session.mode.value if self.session.mode else "sconosciuta"
            self.status_var.set(
                f"Interrompi prima la sessione {active} attiva."
            )
            return
        self.source_mode_var.set(mode)
        self.video_tab.grid_remove()
        self.overlay_tab.grid_remove()
        document_tab = getattr(self, "document_tab", None)
        if document_tab is not None:
            document_tab.grid_remove()
        selected = {
            "file": self.video_tab,
            "live": self.overlay_tab,
            "document": document_tab,
        }[mode]
        if selected is not None:
            selected.grid()
        self.file_mode_button.configure(
            style="ModeSelected.TButton" if mode == "file" else "Mode.TButton"
        )
        self.live_mode_button.configure(
            style="ModeSelected.TButton" if mode == "live" else "Mode.TButton"
        )
        document_button = getattr(self, "document_mode_button", None)
        if document_button is not None:
            document_button.configure(
                style=(
                    "ModeSelected.TButton"
                    if mode == "document"
                    else "Mode.TButton"
                )
            )

    def _show_browser_overlay(self, focus_window: bool = True) -> None:
        self._select_source_mode("live")
        if focus_window:
            self.deiconify()
            self.lift()
            try:
                self.focus_force()
            except tk.TclError:
                pass
        self.status_var.set(
            "Richiesta browser ricevuta: preparazione AI Overlay OS..."
        )

    def _schedule_instance_poll(self) -> None:
        if self._closing or self._instance_broker is None:
            return
        self._instance_poll_job = self.after(75, self._poll_instance_events)

    def _poll_instance_events(self) -> None:
        self._instance_poll_job = None
        broker = self._instance_broker
        if self._closing or broker is None:
            return
        for event in broker.drain_events():
            self._handle_instance_event(event)
        self._schedule_instance_poll()

    def _schedule_browser_bridge_poll(self) -> None:
        if self._closing or self._browser_bridge is None:
            return
        self._browser_bridge_poll_job = self.after(
            150, self._poll_browser_bridge
        )

    def _poll_browser_bridge(self) -> None:
        self._browser_bridge_poll_job = None
        bridge = self._browser_bridge
        if self._closing or bridge is None:
            return
        bridge.update_state(
            {
                "mode": self.session.mode.value if self.session.mode else None,
                "phase": self.session.phase.value,
                "running": self.session.busy,
                "profile": profile_key_from_label(self.profile_var.get()),
                "browser": self._routing_browser(),
                "capture_device": self.capture_device_var.get(),
                "voice": bool(self.live_voice_var.get()),
                "auto_ducking": bool(self.auto_ducking_var.get()),
                "latency": dict(self._latest_latency),
                "app_version": __version__,
                "update_status": self._update_status,
            }
        )
        for command in bridge.drain_commands():
            if command.action == "quit":
                self._close()
                return
            self._handle_browser_request(
                BrowserRequest(
                    browser=command.browser,
                    action=command.action,
                    profile=command.profile,
                )
            )
        self._schedule_browser_bridge_poll()

    def _schedule_hotkey_poll(self) -> None:
        if self._closing:
            return
        self._hotkey_poll_job = self.after(120, self._poll_hotkeys)

    def _poll_hotkeys(self) -> None:
        self._hotkey_poll_job = None
        if self._closing:
            return
        hotkeys = getattr(self, "_hotkeys", None)
        for command in hotkeys.drain() if hotkeys is not None else ():
            if command == "toggle":
                self._toggle_live()
            elif command == "stop":
                self._stop_from_tray()
            elif command == "overlay":
                self._toggle_overlay()
            elif command == "volume_up":
                change_system_volume(1)
            elif command == "volume_down":
                change_system_volume(-1)
        self._schedule_hotkey_poll()

    def _check_updates(self) -> None:
        try:
            result = self._updater.check_and_stage()
        except Exception as error:
            logger("updates").warning("event=update_check_failed error=%s", error)
            result = UpdateResult(
                "error", message="Controllo aggiornamenti fallito"
            )
        self._call_in_ui(self._set_update_result, result)

    def _set_update_result(self, result: UpdateResult) -> None:
        self._update_status = result.status
        if result.status in {"available", "staged"}:
            self.status_var.set(result.message)
            tray = getattr(self, "_tray", None)
            if tray is not None:
                tray.notify(result.message)

    def _handle_instance_event(self, event: InstanceEvent) -> None:
        if event.command == "focus":
            self.deiconify()
            self.lift()
            try:
                self.focus_force()
            except tk.TclError:
                pass
            return
        request = event.request
        if event.command not in {"overlay", "browser"} or request is None:
            return
        self._handle_browser_request(request)

    def _handle_browser_request(self, request) -> None:
        self._source_browser = request.browser
        requested_profile = getattr(request, "profile", None)
        if requested_profile:
            profile = profile_by_key(requested_profile)
            self.profile_var.set(profile.label)
            self._apply_profile()
        if request.action == FOCUS_ACTION:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.status_var.set("UVT portato in primo piano dal browser")
            return
        if request.action == STOP_ACTION:
            if TranslatorWindow._session_active(self, SessionMode.FILE):
                self._stop()
            if TranslatorWindow._session_active(self, SessionMode.LIVE):
                self._stop_live_mode()
            self.status_var.set("Sessione interrotta dal browser")
            return
        if request.action != OVERLAY_ACTION:
            return
        self._show_browser_overlay(False)
        if self.live and self.live.running:
            self.status_var.set("AI Overlay OS è già attivo.")
            return
        self._browser_overlay_pending = True
        if self._capture_devices_loaded:
            self._browser_overlay_pending = False
            if "cable output" in self.capture_device_var.get().lower():
                self.after_idle(self._start_browser_overlay)
            else:
                self.status_var.set(
                    "Avvio automatico annullato: VB-Cable non rilevato."
                )

    def _start_browser_overlay(self) -> None:
        self._show_browser_overlay(False)
        if self.live and self.live.running:
            return
        try:
            self._toggle_live(require_browser_routing=True)
        except Exception as error:
            self._show_error(error)

    def _connect_browser(self) -> None:
        try:
            register_protocol()
            extension = extension_directory()
            if not extension.is_dir():
                raise BrowserProtocolError(
                    "Cartella dell'estensione browser non trovata."
                )
            os.startfile(extension)
        except (BrowserProtocolError, OSError) as error:
            self._show_error(error)
            return
        messagebox.showinfo(
            "Collegamento browser",
            "Protocollo UVT registrato per questo utente.\n\n"
            "In Chrome o Edge apri la pagina delle estensioni, attiva la "
            "modalità sviluppatore, scegli 'Carica estensione non pacchettizzata' "
            "e seleziona la cartella appena aperta.\n\n"
            "Quando premi il pulsante, l'estensione non legge né invia il link: "
            "apre direttamente AI Overlay OS, configura l'audio del browser e "
            "avvia la traduzione in tempo reale.",
        )

    def _show_text_menu(self, event: tk.Event) -> None:
        self.file_entry.focus_set()
        self.text_menu.tk_popup(event.x_root, event.y_root)

    def _text_action(self, action: str) -> None:
        self.file_entry.event_generate(action)

    def _start_document_translation(self) -> None:
        source = Path(self.document_var.get().strip())
        destination = Path(self.document_output_var.get().strip())
        if not source.is_file() or source.suffix.casefold() not in SUPPORTED_DOCUMENT_EXTENSIONS:
            messagebox.showerror("Documenti", "Seleziona un documento supportato.")
            return
        if destination.suffix.casefold() != source.suffix.casefold():
            messagebox.showerror(
                "Documenti", "La destinazione deve mantenere lo stesso formato."
            )
            return
        if self.session.busy:
            messagebox.showerror("Documenti", "Interrompi prima la sessione attiva.")
            return
        self._select_source_mode("document")
        run_id = self.session.begin(SessionMode.DOCUMENT)
        self._document_run_id = run_id
        self._document_cancel.clear()
        self.document_start_button.configure(state="disabled")
        self.document_stop_button.configure(state="normal")
        self.status_var.set("Preparazione documento…")
        self._start_worker(
            self._translate_document,
            source,
            destination,
            self.language_var.get(),
            self.model_var.get(),
            run_id,
            name="uvt-document-translation",
        )

    def _translate_document(
        self,
        source: Path,
        destination: Path,
        language: str,
        model: str,
        run_id: int,
    ) -> None:
        try:
            translator = DocumentTranslator(OllamaTranslator(model=model))
            result = translator.translate(
                source,
                destination,
                source_language=language,
                cancel=self._document_cancel,
                on_progress=lambda done, total: self._call_in_ui(
                    self.status_var.set,
                    f"Documento: {done}/{total} blocchi tradotti",
                ),
            )
        except Exception as error:
            if run_id == self._document_run_id:
                self._call_in_ui(self._finish_document_translation, error)
            return
        if run_id == self._document_run_id:
            self._call_in_ui(self._finish_document_translation, None, result)

    def _finish_document_translation(
        self, error: Exception | None, result: Path | None = None
    ) -> None:
        self.session.finish(SessionMode.DOCUMENT)
        self._document_run_id = self.session.run_id
        self.document_start_button.configure(state="normal")
        self.document_stop_button.configure(state="disabled")
        self._sync_mode_controls()
        if error is not None:
            if isinstance(error, DocumentTranslationError) and self._document_cancel.is_set():
                self.status_var.set("Traduzione documento interrotta")
            else:
                self._show_error(error)
                self.status_var.set("Errore traduzione documento")
            return
        self.status_var.set(f"Documento tradotto: {result}")

    def _stop_document_translation(self) -> None:
        if self.session.mode is not SessionMode.DOCUMENT or not self.session.busy:
            return
        self.session.begin_stopping(SessionMode.DOCUMENT)
        document_cancel = getattr(self, "_document_cancel", None)
        if document_cancel is not None:
            document_cancel.set()
        self.document_stop_button.configure(state="disabled")
        self.status_var.set("Arresto traduzione documento…")

    def _start(self) -> None:
        settings = self._settings()
        if not settings.source:
            self.status_var.set("Sorgente richiesta")
            messagebox.showerror(
                "Errore",
                "Seleziona un video, audio o file di sottotitoli.",
            )
            return
        if not self._stop_live_mode():
            messagebox.showerror(
                "Errore",
                "AI Overlay OS non si è arrestato. Riprova prima di avviare il file.",
            )
            return
        self._select_source_mode("file")
        run_id = self.file_controller.begin()
        self._file_run_id = run_id
        self.start_button.configure(state="disabled")
        self.live_button.configure(state="disabled")
        self.status_var.set("Preparazione/trascrizione…")
        self._start_worker(
            self._prepare,
            settings,
            run_id,
            name="uvt-prepare",
        )

    def _prepare(self, settings: RunSettings, run_id: int) -> None:
        try:
            prepared = self.file_controller.prepare(settings, run_id)
            if prepared is None:
                return
            if (
                self._closing
                or run_id != self._file_run_id
                or not self.session.accepts(SessionMode.FILE, run_id)
            ):
                self.file_controller.discard(prepared)
                return
            self._call_in_ui(self._begin_playback, prepared, run_id)
        except Exception as exc:
            if self._closing or run_id != self._file_run_id:
                return
            self._call_in_ui(self._show_error, exc)
            self._call_in_ui(self._reset_controls)

    @staticmethod
    def _discard_prepared(prepared: PreparedPlayback) -> None:
        for playback in (prepared.progressive, prepared.player):
            if playback:
                playback.stop()

    def _begin_playback(
        self, prepared: PreparedPlayback, run_id: int
    ) -> None:
        if run_id != self._file_run_id:
            self.file_controller.discard(prepared)
            return
        if not self.file_controller.activate(run_id):
            self.file_controller.discard(prepared)
            return
        self.progressive = prepared.progressive
        self.player = prepared.player
        self.pause_button.configure(state="normal")
        self.stop_button.configure(state="normal")
        if self.progressive:
            try:
                self.progressive.start()
            except Exception as exc:
                self._show_error(exc)
                self._reset_controls()
            return
        if self.player:
            self.player.start()

    def _pause(self) -> None:
        if self.progressive:
            paused = self.progressive.toggle_pause()
            self.pause_button.configure(text="Riprendi" if paused else "Pausa")
            self.session.set_paused(paused)
            return
        if self.player:
            paused = self.player.toggle_pause()
            self.pause_button.configure(text="Riprendi" if paused else "Pausa")
            self.session.set_paused(paused)

    def _stop(self) -> None:
        progressive = self.progressive
        player = self.player
        self.progressive = None
        self.player = None
        self.file_controller.stop(player, progressive, self.preview)
        self._reset_controls()

    def _export(self) -> None:
        destination = filedialog.asksaveasfilename(
            title="Salva traccia italiana",
            defaultextension=".wav",
            filetypes=(("Audio WAV", "*.wav"), ("Audio MP3", "*.mp3")),
        )
        if not destination:
            return
        self.export_button.configure(state="disabled")
        self.status_var.set("Preparazione esportazione…")
        self._start_worker(
            self._run_export,
            destination,
            self._settings(),
            name="uvt-export-audio",
        )

    def _run_export(self, destination: str, settings: RunSettings) -> None:
        try:
            output = self.workflow.export_audio(
                destination,
                settings,
                on_progress=lambda current, total: self._call_in_ui(
                    self.status_var.set, f"Esportazione {current}/{total}"
                ),
                on_warning=lambda message: self._call_in_ui(
                    messagebox.showwarning,
                    "Traduzione incompleta",
                    message,
                ),
            )
            self._call_in_ui(self._export_complete, output)
        except Exception as exc:
            self._call_in_ui(self._show_error, exc)
        finally:
            self._call_in_ui(self.export_button.configure, {"state": "normal"})

    def _export_complete(self, output: Path) -> None:
        self.status_var.set("Esportazione completata")
        messagebox.showinfo("Traccia creata", f"File salvato:\n{output}")

    def _export_video(self) -> None:
        settings = self._settings()
        source_value = settings.source
        if Path(source_value).suffix.lower() in {".srt", ".vtt"}:
            messagebox.showerror("Errore", "Seleziona il file video originale.")
            return
        destination = filedialog.asksaveasfilename(
            title="Salva video in italiano",
            defaultextension=".mp4",
            filetypes=(("Video MP4", "*.mp4"),),
        )
        if not destination:
            return
        self.video_button.configure(state="disabled")
        self._start_worker(
            self._run_video_export,
            Path(destination),
            settings,
            name="uvt-export-video",
        )

    def _run_video_export(
        self, destination: Path, settings: RunSettings
    ) -> None:
        try:
            output = self.workflow.export_video(
                destination,
                settings,
                on_progress=lambda current, total: self._call_in_ui(
                    self.status_var.set, f"Creazione video {current}/{total}"
                ),
                on_warning=lambda message: self._call_in_ui(
                    messagebox.showwarning,
                    "Traduzione incompleta",
                    message,
                ),
            )
            self._call_in_ui(self._video_complete, output)
        except Exception as exc:
            self._call_in_ui(self._show_error, exc)
        finally:
            self._call_in_ui(self.video_button.configure, {"state": "normal"})

    def _video_complete(self, output: Path) -> None:
        self.status_var.set("Video italiano completato")
        messagebox.showinfo("Video creato", f"File salvato:\n{output}")

    def _toggle_overlay(self) -> None:
        visible = self.overlay.toggle()
        self.overlay_button.configure(
            text="Nascondi overlay" if visible else "Mostra overlay"
        )

    def _configure_theme(self) -> None:
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._apply_theme()

    def _apply_theme(self) -> None:
        self._theme_palette = apply_theme(
            self,
            self.style,
            dark=self.dark_mode,
            settings_canvas=getattr(self, "settings_canvas", None),
        )

    def _refresh_status_indicator(self) -> None:
        if "status_dot" not in self.__dict__:
            return
        status = self.status_var.get().casefold()
        if any(
            word in status
            for word in ("errore", "non riuscito", "fallita", "annullato")
        ):
            style = "StatusError.TLabel"
        elif any(
            word in status
            for word in (
                "preparazione",
                "caricamento",
                "download",
                "esportazione",
                "creazione",
                "riproduzione",
                "ascolto",
            )
        ):
            style = "StatusBusy.TLabel"
        else:
            style = "StatusGood.TLabel"
        self.status_dot.configure(style=style)

    def _apply_text_colors(self) -> None:
        colors = self._theme_palette
        field = colors.field
        fg = colors.foreground
        self.output.configure(
            bg=field,
            fg=fg,
            insertbackground=fg,
            selectbackground="#315ef5",
            relief="flat",
            padx=16,
            pady=14,
            spacing1=2,
            spacing3=8,
            font=("Segoe UI Variable Text", 11),
            highlightthickness=1,
            highlightbackground=colors.border,
            highlightcolor=colors.accent,
        )
        if hasattr(self, "text_menu"):
            self.text_menu.configure(bg=field, fg=fg)

    def _toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self._apply_theme()
        self._apply_text_colors()
        self.theme_button.configure(
            text="Tema chiaro" if self.dark_mode else "Tema scuro"
        )
        self._schedule_settings_save()

    def _toggle_live(self, *, require_browser_routing: bool = False) -> None:
        if TranslatorWindow._session_active(self, SessionMode.DOCUMENT):
            self.status_var.set("Interrompi prima la traduzione del documento.")
            return
        if self.live and self.live.running:
            self._stop_live_mode()
            return
        if TranslatorWindow._session_active(self, SessionMode.FILE):
            self._stop()
        self._select_source_mode("live")
        settings = self._settings()
        profile_key = profile_key_from_label(self.profile_var.get())
        volume_ducker = (
            self.browser_audio_controller.ducker(
                profile_by_key(profile_key).ducking_percent
            )
            if self.auto_ducking_var.get() and self.live_voice_var.get()
            else None
        )
        live_run_id = self.live_controller.begin()
        self._live_run_id = live_run_id
        live: LiveTranslator | None = None
        try:
            routed = self._route_browser_audio()
            if require_browser_routing and not routed:
                raise AudioRoutingError(
                    "Routing automatico del browser non disponibile. "
                    "Verifica VB-Cable e riprova."
                )
            self.overlay.show()
            self.overlay_button.configure(text="Nascondi overlay")
            live = LiveTranslator(
                translator=OllamaTranslator(model=settings.ollama_model),
                cache=TranslationCache(),
                whisper_model=settings.whisper_model,
                source_language=settings.language,
                rate=settings.rate,
                profile=profile_key,
                speech_engine=settings.speech_engine,
                voice=settings.voice,
                speak=self.live_voice_var.get(),
                capture_device=(
                    None
                    if self.capture_device_var.get()
                    == "Audio di sistema (predefinito)"
                    else self.capture_device_var.get()
                ),
                on_text=lambda text: self.after(0, self._show_text, text),
                on_status=lambda text, run_id=live_run_id: self.after(
                    0, self._set_live_status, text, run_id
                ),
                on_error=lambda error: self.after(
                    0, self._show_live_error, error
                ),
                on_metrics=lambda metrics: self.after(
                    0, self._update_latency, metrics
                ),
                volume_ducker=volume_ducker,
            )
            if not self.live_controller.activate(live, live_run_id):
                raise RuntimeError("Sessione Overlay OS non più valida.")
        except Exception:
            self.session.fail(SessionMode.LIVE, live_run_id)
            if live is not None:
                try:
                    live.stop()
                except Exception:
                    pass
            try:
                self.overlay.hide()
                self.overlay_button.configure(text="Mostra overlay")
            except Exception:
                pass
            self._restore_browser_audio()
            raise
        self.live = live
        self.live_button.configure(text="Stop Overlay OS")
        self._sync_mode_controls()

    def _stop_live_mode(self) -> bool:
        live = self.live
        if not self.live_controller.stop(live):
            self.status_var.set(
                "AI Overlay OS non si è arrestato: attendi e riprova."
            )
            self._sync_mode_controls()
            return False
        self.live = None
        self._live_run_id = self.session.run_id
        self._restore_browser_audio()
        self.live_button.configure(text="Avvia AI Overlay OS")
        self._sync_mode_controls()
        return True

    def _routing_browser(self) -> str:
        if self._source_browser in SUPPORTED_BROWSERS:
            return self._source_browser
        selected = self.routing_browser_var.get().lower()
        return selected if selected in SUPPORTED_BROWSERS else "firefox"

    def _route_browser_audio(self) -> bool:
        if "cable output" not in self.capture_device_var.get().lower():
            return False
        routed = self.browser_audio_controller.route()
        self._browser_audio_routed = (
            self.browser_audio_controller.routed_browser if routed else None
        )
        return routed

    def _restore_browser_audio(self) -> bool:
        restored = self.browser_audio_controller.restore()
        self._browser_audio_routed = (
            self.browser_audio_controller.routed_browser
        )
        return restored

    def _show_live_error(self, error: Exception) -> None:
        self._restore_browser_audio()
        self._show_error(error)

    def _set_live_status(self, text: str, run_id: int | None = None) -> None:
        if run_id is not None and run_id != self._live_run_id:
            return
        terminal = text in {"Overlay OS interrotto", "Errore Overlay OS"}
        if not TranslatorWindow._session_active(self, SessionMode.FILE):
            self.status_var.set(text)
        if terminal:
            if text == "Errore Overlay OS":
                self.session.fail(SessionMode.LIVE, self._live_run_id)
            self.session.finish(SessionMode.LIVE)
            self._live_run_id = self.session.run_id
            self.live = None
            self._restore_browser_audio()
            self.live_button.configure(text="Avvia AI Overlay OS")
            self._sync_mode_controls()

    def _settings(self) -> RunSettings:
        selected_voice = self.voice_var.get()
        if self.speech_engine_var.get() == "kokoro":
            selected_voice = KOKORO_VOICES.get(selected_voice, selected_voice)
        return RunSettings(
            source=self.file_var.get().strip(),
            ollama_model=self.model_var.get().strip() or "translategemma:latest",
            whisper_model=self.whisper_var.get(),
            language=self.language_var.get(),
            rate=self.rate_var.get(),
            speech_engine=self.speech_engine_var.get(),
            voice=selected_voice,
            cookies_browser=(
                None if self.cookies_var.get() == "nessuno" else self.cookies_var.get()
            ),
        )

    def _refresh_voices(self, _event=None) -> None:
        if self.speech_engine_var.get() == "kokoro":
            values = tuple(KOKORO_VOICES)
            self.voice_combo.configure(values=values)
            self.voice_var.set(values[0])
            return
        values = tuple(windows_voice_names()) or ("default",)
        self.voice_combo.configure(values=values)
        self.voice_var.set(values[0])

    def _detect_readiness(self) -> None:
        readiness = detect_system_readiness()
        self._call_in_ui(self._apply_readiness, readiness)

    def _run_preflight(self) -> None:
        if self._preflight_running:
            return
        self._preflight_running = True
        self.system_status_var.set("Verifica in corso…")
        self._start_worker(self._perform_preflight, name="uvt-preflight")

    def _perform_preflight(self) -> None:
        try:
            self._detect_readiness()
            self._load_models()
            self._load_capture_devices()
        finally:
            self._call_in_ui(self._finish_preflight)

    def _finish_preflight(self) -> None:
        self._preflight_running = False

    def _apply_readiness(self, readiness: SystemReadiness) -> None:
        self._readiness = readiness
        if (
            self.speech_engine_var.get() == "kokoro"
            and not readiness.available("kokoro")
        ):
            self.speech_engine_var.set("windows")
            self._refresh_voices()
        self.system_status_var.set(readiness.summary())
        if self.status_var.get() in {"Pronto", "Sistema pronto"}:
            self.status_var.set(readiness.summary())

    def _load_models(self) -> None:
        try:
            models = OllamaTranslator(model="translategemma:latest").list_models()
            self._call_in_ui(self._apply_models, models)
        except Exception as error:
            log_exception("models", "discovery_failed", error)

    def _apply_models(self, models: list[str]) -> None:
        self.model_combo.configure(values=models)
        selected = select_available_model(models, self.model_var.get())
        if selected is not None and selected != self.model_var.get():
            self.model_var.set(selected)
            self.status_var.set(f"Modello selezionato automaticamente: {selected}")

    def _load_capture_devices(self) -> None:
        try:
            devices = capture_device_names()
        except Exception as error:
            log_exception("audio", "device_discovery_failed", error)
            self._call_in_ui(self._apply_capture_device_error, error)
            return
        values = ("Audio di sistema (predefinito)", *devices)
        self._call_in_ui(self._apply_capture_devices, values)

    def _apply_capture_device_error(self, error: Exception) -> None:
        self._capture_devices_loaded = True
        self._browser_overlay_pending = False
        self.live_button.configure(
            state=(
                "disabled"
                if TranslatorWindow._session_active(self, SessionMode.FILE)
                else "normal"
            )
        )
        self.status_var.set(present_error(error).problem)

    def _apply_capture_devices(self, values: tuple[str, ...]) -> None:
        self._capture_devices_loaded = True
        self.capture_combo.configure(values=values)
        cable_output = preferred_cable_output(values)
        current = self.capture_device_var.get()
        if self._browser_overlay_pending and cable_output:
            self.capture_device_var.set(cable_output)
        elif current in values:
            self.capture_device_var.set(current)
        elif cable_output:
            self.capture_device_var.set(cable_output)
        else:
            self.capture_device_var.set("Audio di sistema (predefinito)")
        if cable_output:
            self.status_var.set(
                "Overlay pronto: audio automatico tramite VB-Cable"
            )
        else:
            self.status_var.set(
                "VB-Cable non rilevato: disponibile Audio di sistema"
            )
        self.live_button.configure(
            state=(
                "disabled"
                if TranslatorWindow._session_active(self, SessionMode.FILE)
                else "normal"
            )
        )
        if self._browser_overlay_pending:
            self._browser_overlay_pending = False
            if cable_output:
                self.after_idle(self._start_browser_overlay)
            else:
                self.status_var.set(
                    "Avvio automatico annullato: VB-Cable non rilevato. "
                    "Installa o attiva VB-Cable, poi riprova."
                )

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        if text in {"Completato", "Interrotto", "Errore"}:
            if text == "Errore":
                self.session.fail(SessionMode.FILE, self._file_run_id)
            self._reset_controls()

    def _show_text(self, text: str) -> None:
        self.overlay.show_text(text)
        if not self.show_text_var.get():
            return
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _show_error(self, error: Exception) -> None:
        log_exception("ui", "operation_failed", error)
        presentation = present_error(error)
        messagebox.showerror(presentation.title, presentation.message)

    def _reset_controls(self) -> None:
        self.session.finish(SessionMode.FILE)
        self._file_run_id = self.session.run_id
        self.pause_button.configure(state="disabled", text="Pausa")
        self.stop_button.configure(state="disabled")
        self._sync_mode_controls()

    def _sync_mode_controls(self) -> None:
        file_active = self.session.mode is SessionMode.FILE and self.session.busy
        live_active = self.session.mode is SessionMode.LIVE and self.session.busy
        document_active = (
            self.session.mode is SessionMode.DOCUMENT and self.session.busy
        )
        self.start_button.configure(
            state="disabled" if self.session.busy else "normal"
        )
        live_enabled = live_active or (
            getattr(self, "_capture_devices_loaded", False)
            and not file_active
            and not document_active
        )
        self.live_button.configure(
            state="normal" if live_enabled else "disabled"
        )
        selector_state = "disabled" if self.session.busy else "normal"
        self.file_mode_button.configure(state=selector_state)
        self.live_mode_button.configure(state=selector_state)
        document_mode_button = getattr(self, "document_mode_button", None)
        if document_mode_button is not None:
            document_mode_button.configure(state=selector_state)
        document_start_button = getattr(self, "document_start_button", None)
        if document_start_button is not None:
            document_start_button.configure(
                state="disabled" if self.session.busy else "normal"
            )
        document_stop_button = getattr(self, "document_stop_button", None)
        if document_stop_button is not None:
            document_stop_button.configure(
                state="normal" if document_active else "disabled"
            )

    @staticmethod
    def _session_active(window, mode: SessionMode) -> bool:
        session = getattr(window, "session", None)
        return bool(session and session.mode is mode and session.busy)

    def _request_close(self) -> None:
        if self.session.busy:
            self.withdraw()
            self.status_var.set(
                "UVT continua in background; riaprilo dall'estensione"
            )
            if not getattr(self, "_background_notice_shown", False):
                tray = getattr(self, "_tray", None)
                if tray is not None:
                    tray.notify(
                        "La traduzione continua in background. Usa l'icona UVT per riaprire."
                    )
                self._background_notice_shown = True
            return
        self._close()

    def _restore_from_background(self) -> None:
        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def _stop_from_tray(self) -> None:
        if TranslatorWindow._session_active(self, SessionMode.FILE):
            self._stop()
        if TranslatorWindow._session_active(self, SessionMode.LIVE):
            self._stop_live_mode()
        if TranslatorWindow._session_active(self, SessionMode.DOCUMENT):
            self._stop_document_translation()

    def _close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._runtime.begin_shutdown()
        document_cancel = getattr(self, "_document_cancel", None)
        if document_cancel is not None:
            document_cancel.set()
        tray = getattr(self, "_tray", None)
        if tray is not None:
            tray.close()
        hotkeys = getattr(self, "_hotkeys", None)
        if hotkeys is not None:
            hotkeys.close()
        if self._instance_broker is not None:
            self._instance_broker.begin_shutdown()
        for job in (
            self._instance_poll_job,
            self._browser_bridge_poll_job,
            self._hotkey_poll_job,
            self._settings_save_job,
        ):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._instance_poll_job = None
        self._browser_bridge_poll_job = None
        self._hotkey_poll_job = None
        self._settings_save_job = None
        if self._browser_bridge is not None:
            self._browser_bridge.close()
        failures = self._runtime.stop_named(
            (
                ("progressive", self.progressive.stop if self.progressive else None),
                ("player", self.player.stop if self.player else None),
                ("preview", self.preview.stop),
                ("live", self.live.stop if self.live else None),
            ),
            on_error=lambda name, error: log_exception(
                "shutdown", f"{name}_stop_failed", error
            ),
        )
        workers_stopped = self._join_workers()
        if not workers_stopped:
            failures.append("workers")
        restored = self._restore_browser_audio()
        try:
            self._save_app_settings()
        except Exception as error:
            failures.append("settings")
            log_exception("shutdown", "settings_flush_failed", error)
        if workers_stopped:
            try:
                self.workflow.close()
            except Exception as error:
                failures.append("workflow")
                log_exception("shutdown", "workflow_cleanup_failed", error)
        if not restored:
            try:
                messagebox.showwarning(
                    "Ripristino audio necessario",
                    "Non è stato possibile ripristinare il browser. UVT riproverà "
                    "automaticamente al prossimo avvio; nel frattempo seleziona "
                    "manualmente l'uscita predefinita di Windows.",
                )
            except tk.TclError:
                pass
        if failures:
            logger("shutdown").warning(
                "event=shutdown_partial failures=%s", ",".join(failures)
            )
        launch_pending_update()
        self.destroy()


def main(
    argv: Sequence[str] | None = None,
    *,
    broker: SingleInstanceBroker | None = None,
    audio_router: AudioRoutingLeaseManager | None = None,
    settings_store: SettingsStore | None = None,
    browser_bridge: LocalBrowserBridge | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    request = None
    initial_browser = None
    auto_start_overlay = False
    startup_error = None
    if arguments:
        try:
            if len(arguments) != 1:
                raise BrowserProtocolError("È consentito un solo collegamento UVT.")
            request = parse_browser_request(arguments[0])
        except BrowserProtocolError as error:
            startup_error = error
    instance = broker or SingleInstanceBroker()
    router = audio_router or AudioRoutingLeaseManager()
    bridge = browser_bridge or LocalBrowserBridge()
    try:
        if not instance.acquire():
            if request is not None:
                forward = getattr(
                    instance,
                    "forward_browser_request",
                    instance.forward_overlay,
                )
                forwarded = forward(arguments[0])
            else:
                forwarded = instance.forward_focus()
            if forwarded:
                return 0
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline and not instance.acquire():
                time.sleep(0.08)
            if not instance.is_owner:
                raise InstanceIPCError(
                    "La richiesta non è stata inoltrata all'istanza UVT esistente."
                )
        if request is not None:
            if not claim_browser_request(request):
                return 0
            initial_browser = request.browser
            auto_start_overlay = request.action == OVERLAY_ACTION
        instance.activate()
        if not bridge.start():
            logger("browser_bridge").warning("event=bridge_start_failed")
            bridge = None
        try:
            recovered = router.recover()
            if recovered:
                logger("routing").info("event=stale_route_recovered")
        except AudioRoutingError as error:
            log_exception("routing", "startup_recovery_failed", error)
            startup_error = error
            auto_start_overlay = False
        window = TranslatorWindow(
            initial_browser=initial_browser,
            auto_start_overlay=auto_start_overlay,
            audio_router=router,
            settings_store=settings_store,
            instance_broker=instance,
            browser_bridge=bridge,
        )
        if startup_error:
            window.after_idle(
                messagebox.showerror,
                "Avvio Universal Video Translator",
                str(startup_error),
            )
        if request is not None and request.action != OVERLAY_ACTION:
            window.after_idle(window._handle_browser_request, request)
        window.mainloop()
        return 0
    except InstanceIPCError as error:
        log_exception("ipc", "instance_forward_failed", error)
        return 1
    finally:
        if bridge is not None:
            bridge.close()
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
