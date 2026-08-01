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
from .profiles import PROFILE_LABELS, profile_by_key, profile_key_from_label
from .session import SessionMode, TranslationSession
from .settings import AppSettings, SettingsStore
from .tts import KOKORO_VOICES, windows_voice_names
from .tray import TrayController
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
    ) -> None:
        self._settings_store = settings_store or SettingsStore()
        saved = self._settings_store.load()
        super().__init__()
        self.title("Universal Video Translator | Modern UI")
        try:
            self.geometry(saved.window_geometry)
        except tk.TclError:
            self.geometry("1240x780")
        self.minsize(1040, 680)
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
        self._instance_poll_job: str | None = None
        self._settings_save_job: str | None = None
        self._closing = False
        self._background_notice_shown = False
        self.session = TranslationSession()
        self._file_run_id = 0
        self._live_run_id = 0
        self._workers: set[threading.Thread] = set()
        self._workers_lock = threading.Lock()
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
        self.source_mode_var = tk.StringVar(value="file")
        self.model_var = tk.StringVar(value=saved.ollama_model)
        self.language_var = tk.StringVar(value=saved.language)
        self.rate_var = tk.IntVar(value=saved.rate)
        self.whisper_var = tk.StringVar(value=saved.whisper_model)
        self.speech_engine_var = tk.StringVar(value=saved.speech_engine)
        self.voice_var = tk.StringVar(value=saved.voice)
        self.show_text_var = tk.BooleanVar(value=saved.show_text)
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
        self.status_var = tk.StringVar(value="Pronto")
        self.dark_mode = saved.dark_mode
        self.advanced_visible = saved.advanced_visible
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
        self.protocol("WM_DELETE_WINDOW", self._request_close)
        self._tray = TrayController(
            on_open=lambda: self.after(0, self._restore_from_background),
            on_stop=lambda: self.after(0, self._stop_from_tray),
            on_quit=lambda: self.after(0, self._close),
        )
        self._tray.start()

    def _start_worker(
        self,
        target,
        *args,
        name: str,
    ) -> threading.Thread:
        def run() -> None:
            try:
                target(*args)
            finally:
                with self._workers_lock:
                    self._workers.discard(thread)

        thread = threading.Thread(target=run, name=name, daemon=True)
        with self._workers_lock:
            self._workers.add(thread)
        thread.start()
        return thread

    def _join_workers(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        current = threading.current_thread()
        with self._workers_lock:
            workers = tuple(self._workers)
        for worker in workers:
            if worker is current:
                continue
            worker.join(max(0.0, deadline - time.monotonic()))
        return not any(worker.is_alive() for worker in workers if worker is not current)

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
        root = ttk.Frame(self, padding=(28, 24, 28, 22))
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        header.columnconfigure(0, weight=1)
        title_box = ttk.Frame(header)
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_box,
            text="LOCAL AI  •  PRIVATE BY DESIGN",
            style="Eyebrow.TLabel",
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            title_box,
            text="Universal Video Translator",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            text="Traduzione, doppiaggio e sottotitoli in tempo reale sul tuo PC",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))
        ttk.Button(
            header,
            text="Collega browser",
            command=self._connect_browser,
            style="Ghost.TButton",
        ).grid(row=0, column=1, padx=(12, 0), sticky="e")
        self.theme_button = ttk.Button(
            header,
            text="Tema chiaro",
            command=self._toggle_theme,
            style="Ghost.TButton",
        )
        self.theme_button.grid(row=0, column=2, padx=(8, 0))

        body = ttk.Panedwindow(root, orient="horizontal", style="Main.TPanedwindow")
        body.grid(row=1, column=0, sticky="nsew")

        settings_card = ttk.Frame(body, style="Surface.TFrame")
        settings_card.configure(width=310)
        settings_card.columnconfigure(0, weight=1)
        settings_card.rowconfigure(0, weight=1)
        panel_color = self.style.lookup("Card.TFrame", "background")
        self.settings_canvas = tk.Canvas(
            settings_card,
            background=panel_color,
            borderwidth=0,
            highlightthickness=0,
        )
        settings_scrollbar = ttk.Scrollbar(
            settings_card,
            orient="vertical",
            command=self.settings_canvas.yview,
        )
        self.settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        self.settings_canvas.grid(row=0, column=0, sticky="nsew")
        settings_scrollbar.grid(row=0, column=1, sticky="ns")
        settings = ttk.Frame(
            self.settings_canvas, padding=22, style="Card.TFrame"
        )
        settings.columnconfigure(0, weight=1)
        settings_window = self.settings_canvas.create_window(
            (0, 0), window=settings, anchor="nw"
        )
        settings.bind(
            "<Configure>",
            lambda _event: self.settings_canvas.configure(
                scrollregion=self.settings_canvas.bbox("all")
            ),
        )
        self.settings_canvas.bind(
            "<Configure>",
            lambda event: self.settings_canvas.itemconfigure(
                settings_window, width=event.width
            ),
        )
        settings.bind(
            "<Enter>",
            lambda _event: self.settings_canvas.bind_all(
                "<MouseWheel>", self._scroll_settings
            ),
        )
        settings.bind(
            "<Leave>",
            lambda _event: self.settings_canvas.unbind_all("<MouseWheel>"),
        )
        body.add(settings_card, weight=1)
        ttk.Label(
            settings, text="CONFIGURAZIONE", style="CardSection.TLabel"
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            settings,
            text="Imposta una volta, usa in entrambe le modalità.",
            style="CardSubtitle.TLabel",
            wraplength=270,
        ).grid(row=1, column=0, sticky="w", pady=(4, 18))

        ttk.Label(settings, text="Modello Ollama", style="Card.TLabel").grid(
            row=2, column=0, sticky="w"
        )
        self.model_combo = ttk.Combobox(
            settings,
            textvariable=self.model_var,
            values=("translategemma:latest", "qwen3:4b"),
            state="readonly",
        )
        self.model_combo.grid(
            row=3, column=0, sticky="ew", pady=(6, 14)
        )

        ttk.Label(settings, text="Lingua originale", style="Card.TLabel").grid(
            row=4, column=0, sticky="w"
        )
        ttk.Combobox(
            settings,
            textvariable=self.language_var,
            values=("auto", "inglese", "spagnolo", "francese", "tedesco"),
            state="readonly",
        ).grid(row=5, column=0, sticky="ew", pady=(6, 14))

        ttk.Label(settings, text="Motore voce", style="Card.TLabel").grid(
            row=6, column=0, sticky="w"
        )
        self.speech_combo = ttk.Combobox(
            settings,
            textvariable=self.speech_engine_var,
            values=("kokoro", "windows"),
            state="readonly",
        )
        self.speech_combo.grid(
            row=7, column=0, sticky="ew", pady=(6, 14)
        )
        self.speech_combo.bind(
            "<<ComboboxSelected>>", self._refresh_voices
        )

        ttk.Label(settings, text="Voce italiana", style="Card.TLabel").grid(
            row=8, column=0, sticky="w"
        )
        self.voice_combo = ttk.Combobox(
            settings,
            textvariable=self.voice_var,
            values=tuple(KOKORO_VOICES),
            state="readonly",
        )
        self.voice_combo.grid(
            row=9, column=0, sticky="ew", pady=(6, 14)
        )

        rate_header = ttk.Frame(settings, style="Card.TFrame")
        rate_header.grid(row=10, column=0, sticky="ew")
        rate_header.columnconfigure(0, weight=1)
        ttk.Label(rate_header, text="Velocità voce", style="Card.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            rate_header, textvariable=self.rate_var, style="CardAccent.TLabel"
        ).grid(row=0, column=1, sticky="e")
        ttk.Scale(
            settings,
            from_=120,
            to=260,
            variable=self.rate_var,
            orient="horizontal",
        ).grid(row=11, column=0, sticky="ew", pady=(5, 16))

        ttk.Label(settings, text="Profilo prestazioni", style="Card.TLabel").grid(
            row=12, column=0, sticky="w"
        )
        self.profile_combo = ttk.Combobox(
            settings,
            textvariable=self.profile_var,
            values=PROFILE_LABELS,
            state="readonly",
        )
        self.profile_combo.grid(row=13, column=0, sticky="ew", pady=(6, 14))
        self.profile_combo.bind("<<ComboboxSelected>>", self._apply_profile)

        self.advanced_button = ttk.Button(
            settings,
            text="Mostra impostazioni avanzate",
            command=self._toggle_advanced_settings,
            style="Subtle.TButton",
        )
        self.advanced_button.grid(
            row=14, column=0, sticky="ew", pady=(2, 0)
        )
        self.advanced_frame = ttk.Frame(
            settings, style="Card.TFrame"
        )
        self.advanced_frame.grid(
            row=15, column=0, sticky="ew", pady=(14, 0)
        )
        self.advanced_frame.columnconfigure(0, weight=1)
        ttk.Label(
            self.advanced_frame, text="Modello Whisper", style="Card.TLabel"
        ).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Combobox(
            self.advanced_frame,
            textvariable=self.whisper_var,
            values=("tiny", "base", "small", "medium"),
            state="readonly",
        ).grid(row=1, column=0, sticky="ew", pady=(5, 12))
        ttk.Label(
            self.advanced_frame, text="Cookie YouTube", style="Card.TLabel"
        ).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Combobox(
            self.advanced_frame,
            textvariable=self.cookies_var,
            values=("firefox", "chrome", "edge", "nessuno"),
            state="readonly",
        ).grid(row=3, column=0, sticky="ew", pady=(5, 12))
        ttk.Label(
            self.advanced_frame, text="Browser audio Overlay", style="Card.TLabel"
        ).grid(row=4, column=0, sticky="w")
        ttk.Combobox(
            self.advanced_frame,
            textvariable=self.routing_browser_var,
            values=("firefox", "chrome", "edge"),
            state="readonly",
        ).grid(row=5, column=0, sticky="ew", pady=(5, 0))
        self.advanced_frame.grid_remove()

        workspace = ttk.Frame(body, padding=(22, 0, 0, 0))
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(3, weight=1)
        body.add(workspace, weight=3)

        ttk.Label(
            workspace,
            text="SORGENTE DA TRADURRE",
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w")

        source_selector = ttk.Frame(
            workspace, padding=4, style="Surface.TFrame"
        )
        source_selector.grid(row=1, column=0, sticky="w", pady=(8, 10))
        self.file_mode_button = ttk.Button(
            source_selector,
            text="File o URL",
            command=lambda: self._select_source_mode("file"),
            style="ModeSelected.TButton",
        )
        self.file_mode_button.pack(side="left")
        self.live_mode_button = ttk.Button(
            source_selector,
            text="Browser o audio PC",
            command=lambda: self._select_source_mode("live"),
            style="Mode.TButton",
        )
        self.live_mode_button.pack(side="left", padx=(4, 0))

        mode_stage = ttk.Frame(workspace)
        mode_stage.grid(row=2, column=0, sticky="ew")
        mode_stage.columnconfigure(0, weight=1)
        video_tab = ttk.Frame(
            mode_stage, padding=22, style="Surface.TFrame"
        )
        self.video_tab = video_tab
        self.overlay_tab = ttk.Frame(
            mode_stage, padding=22, style="Surface.TFrame"
        )
        video_tab.grid(row=0, column=0, sticky="ew")
        self.overlay_tab.grid(row=0, column=0, sticky="ew")
        self.overlay_tab.grid_remove()

        video_tab.columnconfigure(0, weight=1)
        ttk.Label(
            video_tab,
            text="Traduci contenuti e sottotitoli",
            style="CardPanelTitle.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            video_tab,
            text="Inserisci un collegamento YouTube oppure seleziona un file locale.",
            style="CardSubtitle.TLabel",
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 18),
        )
        ttk.Label(
            video_tab, text="SORGENTE", style="CardSection.TLabel"
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 7))
        self.file_entry = ttk.Entry(
            video_tab, textvariable=self.file_var
        )
        self.file_entry.grid(
            row=3, column=0, sticky="ew", padx=(0, 10), ipady=4
        )
        self.file_entry.bind("<Button-3>", self._show_text_menu)
        ttk.Button(
            video_tab,
            text="Sfoglia…",
            command=self._browse,
            style="Subtle.TButton",
        ).grid(row=3, column=1, ipady=3)

        video_actions = ttk.Frame(video_tab, style="Card.TFrame")
        video_actions.grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(18, 0)
        )
        self.start_button = ttk.Button(
            video_actions,
            text="Avvia traduzione",
            command=self._start,
            style="Primary.TButton",
        )
        self.start_button.pack(side="left", padx=(0, 8))
        self.pause_button = ttk.Button(
            video_actions,
            text="Pausa",
            command=self._pause,
            state="disabled",
            style="Secondary.TButton",
        )
        self.pause_button.pack(side="left", padx=4)
        self.stop_button = ttk.Button(
            video_actions,
            text="Stop",
            command=self._stop,
            state="disabled",
            style="Danger.TButton",
        )
        self.stop_button.pack(side="left", padx=4)

        export_actions = ttk.Frame(video_tab, style="Card.TFrame")
        export_actions.grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        self.export_button = ttk.Button(
            export_actions,
            text="Esporta audio",
            command=self._export,
            style="Secondary.TButton",
        )
        self.export_button.pack(side="left", padx=(0, 8))
        self.video_button = ttk.Button(
            export_actions,
            text="Crea video italiano",
            command=self._export_video,
            style="Secondary.TButton",
        )
        self.video_button.pack(side="left")

        self.overlay_tab.columnconfigure(0, weight=1)
        ttk.Label(
            self.overlay_tab,
            text="Traduzione live dell’audio del PC",
            style="CardPanelTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.overlay_tab,
            text=(
                "Rileva VB-Cable, configura il browser chiamante e riproduce "
                "automaticamente la voce italiana."
            ),
            style="CardSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 14))
        ttk.Label(
            self.overlay_tab, text="INGRESSO AUDIO", style="CardSection.TLabel"
        ).grid(
            row=2, column=0, sticky="w"
        )
        self.capture_combo = ttk.Combobox(
            self.overlay_tab,
            textvariable=self.capture_device_var,
            values=("Audio di sistema (predefinito)",),
            state="readonly",
        )
        self.capture_combo.grid(
            row=3, column=0, sticky="ew", pady=(7, 12), ipady=3
        )
        ttk.Checkbutton(
            self.overlay_tab,
            text="Riproduci anche la voce italiana",
            variable=self.live_voice_var,
            style="Card.TCheckbutton",
        ).grid(row=4, column=0, sticky="w", pady=(0, 16))
        ttk.Checkbutton(
            self.overlay_tab,
            text="Abbassa automaticamente l’audio originale durante la voce",
            variable=self.auto_ducking_var,
            style="Card.TCheckbutton",
        ).grid(row=5, column=0, sticky="w", pady=(0, 16))

        overlay_actions = ttk.Frame(
            self.overlay_tab, style="Card.TFrame"
        )
        overlay_actions.grid(row=6, column=0, sticky="w")
        self.live_button = ttk.Button(
            overlay_actions,
            text="Avvia AI Overlay OS",
            command=self._toggle_live,
            style="Primary.TButton",
            state="disabled",
        )
        self.live_button.pack(side="left", padx=(0, 8))
        self.overlay_button = ttk.Button(
            overlay_actions,
            text="Mostra overlay",
            command=self._toggle_overlay,
            style="Secondary.TButton",
        )
        self.overlay_button.pack(side="left")
        diagnostics_row = ttk.Frame(self.overlay_tab, style="Card.TFrame")
        diagnostics_row.grid(row=7, column=0, sticky="ew", pady=(16, 0))
        diagnostics_row.columnconfigure(0, weight=1)
        ttk.Label(
            diagnostics_row,
            textvariable=self.latency_var,
            style="CardAccent.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            diagnostics_row,
            text="Copia diagnostica",
            command=self._copy_diagnostics,
            style="Subtle.TButton",
        ).grid(row=0, column=1, sticky="e")
        ttk.Label(
            self.overlay_tab,
            textvariable=self.latency_detail_var,
            style="CardSubtitle.TLabel",
        ).grid(row=8, column=0, sticky="w", pady=(5, 0))

        output_card = ttk.Frame(
            workspace, padding=20, style="Surface.TFrame"
        )
        output_card.grid(
            row=3, column=0, sticky="nsew", pady=(16, 0)
        )
        output_card.columnconfigure(0, weight=1)
        output_card.rowconfigure(1, weight=1)
        output_header = ttk.Frame(
            output_card, style="Card.TFrame"
        )
        output_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        output_header.columnconfigure(0, weight=1)
        ttk.Label(
            output_header,
            text="Output traduzione",
            style="CardPanelTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            output_header,
            text="Mostra testo",
            variable=self.show_text_var,
            style="Card.TCheckbutton",
        ).grid(row=0, column=1, sticky="e")
        self.output = tk.Text(
            output_card, wrap="word", height=12, state="disabled"
        )
        self.output.grid(row=1, column=0, sticky="nsew")
        self._apply_text_colors()

        status_bar = ttk.Frame(root, padding=(12, 8), style="Status.TFrame")
        status_bar.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.status_dot = ttk.Label(
            status_bar,
            text="●",
            style="StatusGood.TLabel",
        )
        self.status_dot.pack(side="left", padx=(0, 8))
        ttk.Label(
            status_bar,
            text="STATO",
            style="StatusKey.TLabel",
        ).pack(side="left", padx=(0, 10))
        ttk.Label(
            status_bar,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).pack(side="left")
        self.status_var.trace_add(
            "write", lambda *_args: self._refresh_status_indicator()
        )
        self._refresh_status_indicator()

        self.text_menu = tk.Menu(self, tearoff=False)
        self.text_menu.add_command(
            label="Taglia", command=lambda: self._text_action("<<Cut>>")
        )
        self.text_menu.add_command(
            label="Copia", command=lambda: self._text_action("<<Copy>>")
        )
        self.text_menu.add_command(
            label="Incolla", command=lambda: self._text_action("<<Paste>>")
        )
        self.text_menu.add_separator()
        self.text_menu.add_command(
            label="Seleziona tutto",
            command=lambda: self._text_action("<<SelectAll>>"),
        )
        self._apply_text_colors()

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
                text="Mostra impostazioni avanzate"
            )
        self._schedule_settings_save()

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

    def _select_source_mode(self, mode: str) -> None:
        if mode not in {"file", "live"}:
            return
        if self.session.busy:
            active = "file o URL" if self.session.mode is SessionMode.FILE else "audio live"
            self.status_var.set(
                f"Interrompi prima la sessione {active} attiva."
            )
            return
        self.source_mode_var.set(mode)
        if mode == "live":
            self.video_tab.grid_remove()
            self.overlay_tab.grid()
        else:
            self.overlay_tab.grid_remove()
            self.video_tab.grid()
        self.file_mode_button.configure(
            style="ModeSelected.TButton" if mode == "file" else "Mode.TButton"
        )
        self.live_mode_button.configure(
            style="ModeSelected.TButton" if mode == "live" else "Mode.TButton"
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
            messagebox.showerror("Collegamento browser", str(error))
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
        if self.dark_mode:
            bg, panel, fg, field, accent, border = (
                "#090d14",
                "#121925",
                "#f5f7fb",
                "#1a2331",
                "#5b8cff",
                "#293548",
            )
        else:
            bg, panel, fg, field, accent, border = (
                "#f1f4f9",
                "#ffffff",
                "#152033",
                "#f6f8fc",
                "#2f6fed",
                "#d8e0eb",
            )
        muted = "#93a0b4" if self.dark_mode else "#637083"
        self.configure(bg=bg)
        if "settings_canvas" in self.__dict__:
            self.settings_canvas.configure(background=panel)
        self.style.configure(
            ".", background=bg, foreground=fg, font=("Segoe UI", 10)
        )
        self.style.configure("TFrame", background=bg)
        self.style.configure("Main.TPanedwindow", background=bg)
        self.style.configure(
            "Card.TFrame",
            background=panel,
            relief="flat",
        )
        self.style.configure(
            "Surface.TFrame",
            background=panel,
            bordercolor=border,
            borderwidth=1,
            relief="solid",
        )
        self.style.configure(
            "Status.TFrame",
            background=panel,
            bordercolor=border,
            borderwidth=1,
            relief="solid",
        )
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("Card.TLabel", background=panel, foreground=fg)
        self.style.configure(
            "Eyebrow.TLabel",
            background=bg,
            foreground=accent,
            font=("Segoe UI Semibold", 9),
        )
        self.style.configure(
            "Title.TLabel",
            background=bg,
            foreground=fg,
            font=("Segoe UI Semibold", 26),
        )
        self.style.configure(
            "PanelTitle.TLabel",
            background=bg,
            foreground=fg,
            font=("Segoe UI Semibold", 15),
        )
        self.style.configure(
            "CardPanelTitle.TLabel",
            background=panel,
            foreground=fg,
            font=("Segoe UI Semibold", 15),
        )
        self.style.configure(
            "Section.TLabel",
            background=bg,
            foreground=accent,
            font=("Segoe UI Semibold", 9),
        )
        self.style.configure(
            "CardSection.TLabel",
            background=panel,
            foreground=accent,
            font=("Segoe UI Semibold", 9),
        )
        self.style.configure(
            "Subtitle.TLabel",
            background=bg,
            foreground=muted,
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "CardSubtitle.TLabel",
            background=panel,
            foreground=muted,
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "Accent.TLabel",
            background=bg,
            foreground=accent,
            font=("Segoe UI", 10, "bold"),
        )
        self.style.configure(
            "CardAccent.TLabel",
            background=panel,
            foreground=accent,
            font=("Segoe UI Semibold", 10),
        )
        self.style.configure(
            "Status.TLabel", background=panel, foreground=fg
        )
        self.style.configure(
            "StatusKey.TLabel",
            background=panel,
            foreground=muted,
            font=("Segoe UI Semibold", 8),
        )
        self.style.configure(
            "StatusGood.TLabel",
            background=panel,
            foreground="#22c55e",
        )
        self.style.configure(
            "StatusBusy.TLabel",
            background=panel,
            foreground="#f59e0b",
        )
        self.style.configure(
            "StatusError.TLabel",
            background=panel,
            foreground="#ef4444",
        )
        self.style.configure(
            "TEntry",
            fieldbackground=field,
            foreground=fg,
            insertcolor=fg,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
            padding=(10, 8),
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=field,
            foreground=fg,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
            padding=(8, 6),
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", field)],
            foreground=[("readonly", fg)],
        )
        self.style.configure(
            "TButton",
            background=field,
            foreground=fg,
            borderwidth=0,
            padding=(13, 8),
            font=("Segoe UI Semibold", 10),
        )
        self.style.map(
            "TButton",
            background=[("active", border), ("disabled", panel)],
            foreground=[("disabled", muted)],
        )
        self.style.configure(
            "Ghost.TButton", background=field, foreground=fg, padding=(14, 9)
        )
        self.style.configure(
            "Secondary.TButton",
            background=field,
            foreground=fg,
            padding=(14, 9),
        )
        self.style.map(
            "Secondary.TButton",
            background=[("active", border), ("disabled", panel)],
            foreground=[("disabled", muted)],
        )
        self.style.configure(
            "Mode.TButton",
            background=panel,
            foreground=muted,
            padding=(16, 9),
        )
        self.style.map(
            "Mode.TButton",
            background=[("active", field), ("disabled", panel)],
            foreground=[("active", fg), ("disabled", muted)],
        )
        self.style.configure(
            "ModeSelected.TButton",
            background=accent,
            foreground="white",
            padding=(16, 9),
        )
        self.style.map(
            "ModeSelected.TButton",
            background=[("active", "#60a5fa"), ("disabled", accent)],
            foreground=[("disabled", "white")],
        )
        self.style.configure(
            "Subtle.TButton",
            background=panel,
            foreground=muted,
            borderwidth=1,
            bordercolor=border,
            padding=(13, 8),
        )
        self.style.map(
            "Subtle.TButton",
            background=[("active", field)],
            foreground=[("active", fg)],
        )
        self.style.configure(
            "Danger.TButton",
            background="#3a2026" if self.dark_mode else "#fff1f2",
            foreground="#fb7185" if self.dark_mode else "#be123c",
            padding=(14, 9),
        )
        self.style.map(
            "Danger.TButton",
            background=[
                ("active", "#542631" if self.dark_mode else "#ffe4e6"),
                ("disabled", panel),
            ],
            foreground=[("disabled", muted)],
        )
        self.style.configure(
            "Primary.TButton",
            background=accent,
            foreground="white",
            font=("Segoe UI Semibold", 10),
            padding=(16, 9),
        )
        self.style.map(
            "Primary.TButton",
            background=[
                ("active", "#60a5fa"),
                ("disabled", "#475569"),
            ],
            foreground=[("disabled", "#cbd5e1")],
        )
        self.style.configure("TCheckbutton", background=bg, foreground=fg)
        self.style.configure(
            "Card.TCheckbutton", background=panel, foreground=fg
        )
        self.style.map(
            "Card.TCheckbutton", background=[("active", panel)]
        )
        self.style.configure(
            "Horizontal.TScale",
            background=panel,
            troughcolor=field,
            bordercolor=panel,
        )
        self.style.configure(
            "Vertical.TScrollbar",
            background=field,
            troughcolor=panel,
            bordercolor=panel,
            arrowcolor=muted,
            relief="flat",
        )
        self.style.map(
            "Vertical.TScrollbar",
            background=[("active", border), ("pressed", accent)],
            arrowcolor=[("active", fg)],
        )
        self.style.configure(
            "TNotebook", background=bg, borderwidth=0
        )
        self.style.configure(
            "TNotebook.Tab",
            background=panel,
            foreground=fg,
            padding=(18, 11),
            font=("Segoe UI Semibold", 10),
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", field), ("active", field)],
            foreground=[("selected", accent), ("active", fg)],
        )
        self._theme_colors = (bg, field, fg)

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
        bg, field, fg = self._theme_colors
        self.output.configure(
            bg=field,
            fg=fg,
            insertbackground=fg,
            selectbackground="#2563eb",
            relief="flat",
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

    def _load_models(self) -> None:
        try:
            models = OllamaTranslator(model="translategemma:latest").list_models()
            self._call_in_ui(self.model_combo.configure, {"values": models})
        except Exception as error:
            log_exception("models", "discovery_failed", error)

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
        self.status_var.set(
            "Rilevamento audio non riuscito. Consulta il log diagnostico e riprova."
        )

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
        messagebox.showerror("Errore", str(error))

    def _reset_controls(self) -> None:
        self.session.finish(SessionMode.FILE)
        self._file_run_id = self.session.run_id
        self.pause_button.configure(state="disabled", text="Pausa")
        self.stop_button.configure(state="disabled")
        self._sync_mode_controls()

    def _sync_mode_controls(self) -> None:
        file_active = self.session.mode is SessionMode.FILE and self.session.busy
        live_active = self.session.mode is SessionMode.LIVE and self.session.busy
        self.start_button.configure(
            state="disabled" if file_active or live_active else "normal"
        )
        live_enabled = live_active or (
            getattr(self, "_capture_devices_loaded", False) and not file_active
        )
        self.live_button.configure(
            state="normal" if live_enabled else "disabled"
        )
        selector_state = "disabled" if self.session.busy else "normal"
        self.file_mode_button.configure(state=selector_state)
        self.live_mode_button.configure(state=selector_state)

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

    def _close(self) -> None:
        if self._closing:
            return
        self._closing = True
        tray = getattr(self, "_tray", None)
        if tray is not None:
            tray.close()
        if self._instance_broker is not None:
            self._instance_broker.begin_shutdown()
        for job in (
            self._instance_poll_job,
            self._browser_bridge_poll_job,
            self._settings_save_job,
        ):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._instance_poll_job = None
        self._browser_bridge_poll_job = None
        self._settings_save_job = None
        if self._browser_bridge is not None:
            self._browser_bridge.close()
        failures: list[str] = []
        for name, action in (
            ("progressive", self.progressive.stop if self.progressive else None),
            ("player", self.player.stop if self.player else None),
            ("preview", self.preview.stop),
            ("live", self.live.stop if self.live else None),
        ):
            if action is None:
                continue
            try:
                stopped = action()
                if stopped is False:
                    failures.append(name)
            except Exception as error:
                failures.append(name)
                log_exception("shutdown", f"{name}_stop_failed", error)
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
