from __future__ import annotations

import tkinter as tk
import threading
import tempfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cache import TranslationCache
from .downloader import download_video, is_web_url
from .export import export_italian_audio, mux_video_with_italian_audio
from .live import LiveTranslator, capture_device_names
from .media_player import MediaPreview
from .ollama import OllamaTranslator
from .overlay import SubtitleOverlay
from .player import SubtitlePlayer
from .progressive import ProgressiveDubPlayer
from .transcription import load_cues
from .tts import KOKORO_VOICES, windows_voice_names


@dataclass(frozen=True, slots=True)
class RunSettings:
    source: str
    ollama_model: str
    whisper_model: str
    language: str
    rate: int
    speech_engine: str
    voice: str
    cookies_browser: str | None


class TranslatorWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Universal Video Translator | Modern UI")
        self.geometry("1240x780")
        self.minsize(1040, 680)
        self.player: SubtitlePlayer | None = None
        self.progressive: ProgressiveDubPlayer | None = None
        self.live: LiveTranslator | None = None
        self.preview = MediaPreview()
        self.prepared_media: Path | None = None
        self.preview_directory: tempfile.TemporaryDirectory | None = None
        self.preview_has_italian_audio = False
        self.download_directory: tempfile.TemporaryDirectory | None = None
        self.overlay = SubtitleOverlay(self)

        self.file_var = tk.StringVar()
        self.model_var = tk.StringVar(value="translategemma:latest")
        self.language_var = tk.StringVar(value="auto")
        self.rate_var = tk.IntVar(value=185)
        self.whisper_var = tk.StringVar(value="small")
        self.speech_engine_var = tk.StringVar(value="kokoro")
        self.voice_var = tk.StringVar(value="Sara (Kokoro, donna)")
        self.show_text_var = tk.BooleanVar(value=True)
        self.live_voice_var = tk.BooleanVar(value=False)
        self.capture_device_var = tk.StringVar(
            value="Audio di sistema (predefinito)"
        )
        self.cookies_var = tk.StringVar(value="firefox")
        self.status_var = tk.StringVar(value="Pronto")
        self.dark_mode = True
        self.advanced_visible = False
        self._configure_theme()
        self._build()
        threading.Thread(target=self._load_models, daemon=True).start()
        threading.Thread(
            target=self._load_capture_devices, daemon=True
        ).start()
        self.protocol("WM_DELETE_WINDOW", self._close)

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
        self.theme_button = ttk.Button(
            header,
            text="Tema chiaro",
            command=self._toggle_theme,
            style="Ghost.TButton",
        )
        self.theme_button.grid(row=0, column=1, padx=(12, 0))

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
        ).grid(row=3, column=0, sticky="ew", pady=(5, 0))
        self.advanced_frame.grid_remove()

        workspace = ttk.Frame(body, padding=(20, 0, 0, 0))
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)
        body.add(workspace, weight=1)

        notebook = ttk.Notebook(workspace)
        notebook.grid(row=0, column=0, sticky="ew")
        video_tab = ttk.Frame(notebook, padding=22, style="Card.TFrame")
        overlay_tab = ttk.Frame(
            notebook, padding=22, style="Card.TFrame"
        )
        notebook.add(video_tab, text="  Video e file  ")
        notebook.add(overlay_tab, text="  AI Overlay OS  ")

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

        overlay_tab.columnconfigure(0, weight=1)
        ttk.Label(
            overlay_tab,
            text="Traduzione in tempo reale del PC",
            style="CardPanelTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            overlay_tab,
            text="Cattura l’audio di browser e applicazioni e mostra la traduzione sopra ogni finestra.",
            style="CardSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 14))
        ttk.Label(
            overlay_tab, text="INGRESSO AUDIO", style="CardSection.TLabel"
        ).grid(
            row=2, column=0, sticky="w"
        )
        self.capture_combo = ttk.Combobox(
            overlay_tab,
            textvariable=self.capture_device_var,
            values=("Audio di sistema (predefinito)",),
            state="readonly",
        )
        self.capture_combo.grid(
            row=3, column=0, sticky="ew", pady=(7, 12), ipady=3
        )
        ttk.Checkbutton(
            overlay_tab,
            text="Riproduci anche la voce italiana",
            variable=self.live_voice_var,
            style="Card.TCheckbutton",
        ).grid(row=4, column=0, sticky="w", pady=(0, 16))

        overlay_actions = ttk.Frame(
            overlay_tab, style="Card.TFrame"
        )
        overlay_actions.grid(row=5, column=0, sticky="w")
        self.live_button = ttk.Button(
            overlay_actions,
            text="Avvia AI Overlay OS",
            command=self._toggle_live,
            style="Primary.TButton",
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

    def _show_text_menu(self, event: tk.Event) -> None:
        self.file_entry.focus_set()
        self.text_menu.tk_popup(event.x_root, event.y_root)

    def _text_action(self, action: str) -> None:
        self.file_entry.event_generate(action)

    def _start(self) -> None:
        self.start_button.configure(state="disabled")
        self.status_var.set("Preparazione/trascrizione…")
        threading.Thread(
            target=self._prepare, args=(self._settings(),), daemon=True
        ).start()

    def _prepare(self, settings: RunSettings) -> None:
        try:
            path = self._resolve_input(
                settings.source, settings.cookies_browser, settings.language
            )
            is_media = path.suffix.lower() not in {".srt", ".vtt"}
            cues = load_cues(path, whisper_model=settings.whisper_model)
            if not cues:
                raise ValueError("Nessuna battuta rilevata.")
            if is_media:
                if self.progressive:
                    self.progressive.stop()
                self.progressive = ProgressiveDubPlayer(
                    media=path,
                    cues=cues,
                    preview=self.preview,
                    translator=OllamaTranslator(model=settings.ollama_model),
                    cache=TranslationCache(),
                    source_language=settings.language,
                    rate=settings.rate,
                    speech_engine=settings.speech_engine,
                    voice=settings.voice,
                    on_text=lambda text: self.after(0, self._show_text, text),
                    on_status=lambda text: self.after(0, self._set_status, text),
                    on_error=lambda error: self.after(0, self._show_error, error),
                )
                self.progressive.prepare()
                self.player = None
                self.after(0, self._begin_playback)
                return

            self.progressive = None
            self.prepared_media = None
            self.preview_has_italian_audio = False
            self.player = SubtitlePlayer(
                cues=cues,
                translator=OllamaTranslator(model=settings.ollama_model),
                cache=TranslationCache(),
                source_language=settings.language,
                rate=settings.rate,
                speech_engine=settings.speech_engine,
                voice=settings.voice,
                on_text=lambda text: self.after(0, self._show_text, text),
                on_status=lambda text: self.after(0, self._set_status, text),
                on_error=lambda error: self.after(0, self._show_error, error),
            )
            self.player.prepare()
            self.after(0, self._begin_playback)
        except Exception as exc:
            self.after(0, self._show_error, exc)
            self.after(0, self._reset_controls)

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
            if self.prepared_media:
                try:
                    self.preview.open(
                        self.prepared_media,
                        mute_audio=not self.preview_has_italian_audio,
                    )
                    self.after(700, self.player.start)
                    return
                except Exception as exc:
                    self._show_error(exc)
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
        threading.Thread(
            target=self._run_export,
            args=(destination, self._settings()),
            daemon=True,
        ).start()

    def _run_export(self, destination: str, settings: RunSettings) -> None:
        try:
            cues = load_cues(
                self._resolve_input(
                    settings.source, settings.cookies_browser, settings.language
                ),
                whisper_model=settings.whisper_model,
            )
            output = export_italian_audio(
                cues,
                destination,
                translator=OllamaTranslator(model=settings.ollama_model),
                cache=TranslationCache(),
                source_language=settings.language,
                rate=settings.rate,
                speech_engine=settings.speech_engine,
                voice=settings.voice,
                on_progress=lambda current, total: self.after(
                    0, self.status_var.set, f"Esportazione {current}/{total}"
                ),
                on_warning=lambda message: self.after(
                    0,
                    messagebox.showwarning,
                    "Traduzione incompleta",
                    message,
                ),
            )
            self.after(0, self._export_complete, output)
        except Exception as exc:
            self.after(0, self._show_error, exc)
        finally:
            self.after(0, self.export_button.configure, {"state": "normal"})

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
        threading.Thread(
            target=self._run_video_export,
            args=(Path(destination), settings),
            daemon=True,
        ).start()

    def _run_video_export(
        self, destination: Path, settings: RunSettings
    ) -> None:
        try:
            source = self._resolve_input(
                settings.source, settings.cookies_browser, settings.language
            )
            with tempfile.TemporaryDirectory(prefix="uvt-video-") as directory:
                audio = Path(directory) / "italiano.wav"
                cues = load_cues(source, whisper_model=settings.whisper_model)
                export_italian_audio(
                    cues,
                    audio,
                    translator=OllamaTranslator(model=settings.ollama_model),
                    cache=TranslationCache(),
                    source_language=settings.language,
                    rate=settings.rate,
                    speech_engine=settings.speech_engine,
                    voice=settings.voice,
                    on_progress=lambda current, total: self.after(
                        0, self.status_var.set, f"Creazione video {current}/{total}"
                    ),
                    on_warning=lambda message: self.after(
                        0,
                        messagebox.showwarning,
                        "Traduzione incompleta",
                        message,
                    ),
                )
                mux_video_with_italian_audio(source, audio, destination)
            self.after(0, self._video_complete, destination)
        except Exception as exc:
            self.after(0, self._show_error, exc)
        finally:
            self.after(0, self.video_button.configure, {"state": "normal"})

    def _video_complete(self, output: Path) -> None:
        self.status_var.set("Video italiano completato")
        messagebox.showinfo("Video creato", f"File salvato:\n{output}")

    def _resolve_input(
        self,
        value: str,
        cookies_browser: str | None = None,
        source_language: str = "auto",
    ) -> Path:
        if not is_web_url(value):
            return Path(value)
        if self.download_directory is None:
            self.download_directory = tempfile.TemporaryDirectory(prefix="uvt-url-")
        self.after(0, self.status_var.set, "Download video…")
        return download_video(
            value,
            self.download_directory.name,
            cookies_browser=cookies_browser,
            source_language=source_language,
        )

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

    def _toggle_live(self) -> None:
        if self.live and self.live.running:
            self.live.stop()
            self.live_button.configure(text="Avvia AI Overlay OS")
            return
        settings = self._settings()
        self.overlay.show()
        self.overlay_button.configure(text="Nascondi overlay")
        self.live = LiveTranslator(
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
            on_error=lambda error: self.after(0, self._show_error, error),
        )
        self.live.start()
        self.live_button.configure(text="Stop Overlay OS")

    def _set_live_status(self, text: str) -> None:
        self.status_var.set(text)
        if text in {"Overlay OS interrotto", "Errore Overlay OS"}:
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
            self.after(0, self.model_combo.configure, {"values": models})
        except Exception:
            pass

    def _load_capture_devices(self) -> None:
        values = (
            "Audio di sistema (predefinito)",
            *capture_device_names(),
        )
        self.after(
            0, self.capture_combo.configure, {"values": values}
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
        if self.progressive:
            self.progressive.stop()
        if self.player:
            self.player.stop()
        self.preview.stop()
        if self.live:
            self.live.stop()
        if self.download_directory:
            self.download_directory.cleanup()
        if self.preview_directory:
            self.preview_directory.cleanup()
        self.destroy()


def main() -> int:
    TranslatorWindow().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
