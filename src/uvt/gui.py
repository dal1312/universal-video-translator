from __future__ import annotations

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
    BrowserProtocolError,
    SUPPORTED_BROWSERS,
    claim_browser_request,
    extension_directory,
    parse_browser_request,
    register_protocol,
)
from .cache import TranslationCache
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
from .settings import AppSettings, SettingsStore
from .tts import KOKORO_VOICES, windows_voice_names
from .workflow import RunSettings, TranslationWorkflow


class TranslatorWindow(tk.Tk):
    def __init__(
        self,
        initial_browser: str | None = None,
        auto_start_overlay: bool = False,
        *,
        audio_router: AudioRoutingLeaseManager | None = None,
        settings_store: SettingsStore | None = None,
        instance_broker: SingleInstanceBroker | None = None,
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
        self._instance_poll_job: str | None = None
        self._settings_save_job: str | None = None
        self._closing = False
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
        self.overlay = SubtitleOverlay(self)
        self.overlay.apply_preferences(
            geometry=saved.overlay_geometry,
            alpha=saved.overlay_alpha,
            font_size=saved.overlay_font_size,
        )

        self.file_var = tk.StringVar()
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
        self.status_var = tk.StringVar(value="Pronto")
        self.dark_mode = saved.dark_mode
        self.advanced_visible = saved.advanced_visible
        self._configure_theme()
        self._build()
        self._restore_saved_layout()
        self._bind_settings_persistence()
        if self._instance_broker is not None:
            self._schedule_instance_poll()
        if auto_start_overlay:
            self.after_idle(self._show_browser_overlay)
        self._start_worker(self._load_models, name="uvt-model-discovery")
        self._start_worker(
            self._load_capture_devices,
            name="uvt-audio-discovery",
        )
        self.protocol("WM_DELETE_WINDOW", self._close)

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
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header.columnconfigure(0, weight=1)
        title_box = ttk.Frame(header)
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_box,
            text="LOCAL AI  /  PRIVATE BY DESIGN",
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
        ).grid(row=0, column=1, padx=(12, 0))
        self.theme_button = ttk.Button(
            header,
            text="Tema chiaro",
            command=self._toggle_theme,
            style="Ghost.TButton",
        )
        self.theme_button.grid(row=0, column=2, padx=(8, 0))

        body = ttk.Panedwindow(root, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew")

        settings = ttk.Frame(body, padding=20, style="Card.TFrame")
        settings.configure(width=320)
        settings.columnconfigure(0, weight=1)
        body.add(settings, weight=0)
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

        self.advanced_button = ttk.Button(
            settings,
            text="Mostra impostazioni avanzate",
            command=self._toggle_advanced_settings,
        )
        self.advanced_button.grid(
            row=12, column=0, sticky="ew", pady=(2, 0)
        )
        self.advanced_frame = ttk.Frame(
            settings, style="Card.TFrame"
        )
        self.advanced_frame.grid(
            row=13, column=0, sticky="ew", pady=(14, 0)
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

        workspace = ttk.Frame(body, padding=(20, 0, 0, 0))
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)
        body.add(workspace, weight=1)

        self.mode_notebook = ttk.Notebook(workspace)
        self.mode_notebook.grid(row=0, column=0, sticky="ew")
        video_tab = ttk.Frame(
            self.mode_notebook, padding=22, style="Card.TFrame"
        )
        self.overlay_tab = ttk.Frame(
            self.mode_notebook, padding=22, style="Card.TFrame"
        )
        self.mode_notebook.add(video_tab, text="  Video e file  ")
        self.mode_notebook.add(self.overlay_tab, text="  AI Overlay OS  ")

        video_tab.columnconfigure(0, weight=1)
        ttk.Label(
            video_tab,
            text="Traduci un video o un file di sottotitoli",
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
            video_tab, text="Sfoglia…", command=self._browse
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
        )
        self.pause_button.pack(side="left", padx=4)
        self.stop_button = ttk.Button(
            video_actions,
            text="Stop",
            command=self._stop,
            state="disabled",
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
        )
        self.export_button.pack(side="left", padx=(0, 8))
        self.video_button = ttk.Button(
            export_actions,
            text="Crea video italiano",
            command=self._export_video,
        )
        self.video_button.pack(side="left")

        self.overlay_tab.columnconfigure(0, weight=1)
        ttk.Label(
            self.overlay_tab,
            text="Traduzione in tempo reale del PC",
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

        overlay_actions = ttk.Frame(
            self.overlay_tab, style="Card.TFrame"
        )
        overlay_actions.grid(row=5, column=0, sticky="w")
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
        )
        self.overlay_button.pack(side="left")

        output_card = ttk.Frame(
            workspace, padding=20, style="Card.TFrame"
        )
        output_card.grid(
            row=1, column=0, sticky="nsew", pady=(14, 0)
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
            text="TRASCRIZIONE ITALIANA",
            style="CardSection.TLabel",
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

        status_bar = ttk.Frame(root, style="Status.TFrame")
        status_bar.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(
            status_bar,
            text="●",
            style="StatusAccent.TLabel",
        ).pack(side="left", padx=(10, 7), pady=7)
        ttk.Label(
            status_bar,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).pack(side="left", pady=7)

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

    def _show_browser_overlay(self) -> None:
        self.mode_notebook.select(self.overlay_tab)
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
        if event.command != "overlay" or request is None:
            return
        self._source_browser = request.browser
        self._show_browser_overlay()
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
        self._show_browser_overlay()
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
        self.start_button.configure(state="disabled")
        self.status_var.set("Preparazione/trascrizione…")
        self._start_worker(
            self._prepare,
            self._settings(),
            name="uvt-prepare",
        )

    def _prepare(self, settings: RunSettings) -> None:
        try:
            prepared = self.workflow.prepare(settings)
            if self._closing:
                if prepared.progressive:
                    prepared.progressive.stop()
                if prepared.player:
                    prepared.player.stop()
                return
            self.progressive = prepared.progressive
            self.player = prepared.player
            self._call_in_ui(self._begin_playback)
        except Exception as exc:
            if self._closing:
                return
            self._call_in_ui(self._show_error, exc)
            self._call_in_ui(self._reset_controls)

    def _begin_playback(self) -> None:
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
            return
        if self.player:
            paused = self.player.toggle_pause()
            self.pause_button.configure(text="Riprendi" if paused else "Pausa")

    def _stop(self) -> None:
        if self.progressive:
            self.progressive.stop()
            self.progressive = None
        if self.player:
            self.player.stop()
        self.preview.stop()
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
                "#0b0f14",
                "#141a23",
                "#f4f7fb",
                "#1c2430",
                "#4f8cff",
                "#283241",
            )
        else:
            bg, panel, fg, field, accent, border = (
                "#eef2f7",
                "#ffffff",
                "#172033",
                "#f7f9fc",
                "#346fe8",
                "#dbe2ea",
            )
        muted = "#93a0b4" if self.dark_mode else "#637083"
        self.configure(bg=bg)
        self.style.configure(
            ".", background=bg, foreground=fg, font=("Segoe UI", 10)
        )
        self.style.configure("TFrame", background=bg)
        self.style.configure(
            "Card.TFrame", background=panel, bordercolor=border, relief="flat"
        )
        self.style.configure(
            "Status.TFrame", background=panel, bordercolor=border, relief="flat"
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
            font=("Segoe UI Semibold", 24),
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
            "StatusAccent.TLabel",
            background=panel,
            foreground="#22c55e",
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
            background=[("selected", panel), ("active", field)],
            foreground=[("selected", accent), ("active", fg)],
        )
        self._theme_colors = (bg, field, fg)

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
            self.live.stop()
            self._restore_browser_audio()
            self.live_button.configure(text="Avvia AI Overlay OS")
            return
        settings = self._settings()
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
                on_status=lambda text: self.after(
                    0, self._set_live_status, text
                ),
                on_error=lambda error: self.after(
                    0, self._show_live_error, error
                ),
            )
            live.start()
        except Exception:
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

    def _routing_browser(self) -> str:
        if self._source_browser in SUPPORTED_BROWSERS:
            return self._source_browser
        selected = self.routing_browser_var.get().lower()
        return selected if selected in SUPPORTED_BROWSERS else "firefox"

    def _route_browser_audio(self) -> bool:
        if "cable output" not in self.capture_device_var.get().lower():
            return False
        browser = self._routing_browser()
        self._browser_audio_routed = browser
        try:
            self._audio_router.route(browser)
        except AudioRoutingError as error:
            self._restore_browser_audio()
            if self._browser_audio_routed is None:
                self.status_var.set(
                    f"Routing automatico {browser.title()} non riuscito: {error}"
                )
            return False
        self.status_var.set(
            f"Ingresso CABLE Output; {browser.title()} su CABLE Input; "
            "voce su uscita Windows"
        )
        return True

    def _restore_browser_audio(self) -> bool:
        browser = self._browser_audio_routed
        if browser is None:
            return True
        try:
            self._audio_router.restore(browser)
        except AudioRoutingError as error:
            self.status_var.set(
                f"Ripristina {browser.title()} manualmente: {error}"
            )
            log_exception("routing", "restore_failed", error)
            return False
        self._browser_audio_routed = None
        return True

    def _show_live_error(self, error: Exception) -> None:
        self._restore_browser_audio()
        self._show_error(error)

    def _set_live_status(self, text: str) -> None:
        self.status_var.set(text)
        if text in {"Overlay OS interrotto", "Errore Overlay OS"}:
            self._restore_browser_audio()
            self.live_button.configure(text="Avvia AI Overlay OS")

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
        self.live_button.configure(state="normal")
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
        self.live_button.configure(state="normal")
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
        self.start_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="Pausa")
        self.stop_button.configure(state="disabled")

    def _close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._instance_broker is not None:
            self._instance_broker.begin_shutdown()
        for job in (self._instance_poll_job, self._settings_save_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._instance_poll_job = None
        self._settings_save_job = None
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
    try:
        if not instance.acquire():
            if request is not None:
                forwarded = instance.forward_overlay(arguments[0])
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
            auto_start_overlay = True
        instance.activate()
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
        )
        if startup_error:
            window.after_idle(
                messagebox.showerror,
                "Avvio Universal Video Translator",
                str(startup_error),
            )
        window.mainloop()
        return 0
    except InstanceIPCError as error:
        log_exception("ipc", "instance_forward_failed", error)
        return 1
    finally:
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
