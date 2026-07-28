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
from .live import LiveTranslator
from .ollama import OllamaTranslator
from .overlay import SubtitleOverlay
from .player import SubtitlePlayer
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


class TranslatorWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Universal Video Translator")
        self.geometry("980x560")
        self.minsize(850, 480)
        self.player: SubtitlePlayer | None = None
        self.live: LiveTranslator | None = None
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
        self.status_var = tk.StringVar(value="Pronto")
        self._build()
        threading.Thread(target=self._load_models, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(9, weight=1)

        ttk.Label(frame, text="File o URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.file_var).grid(
            row=0, column=1, padx=8, sticky="ew"
        )
        ttk.Button(frame, text="Sfoglia…", command=self._browse).grid(
            row=0, column=2
        )

        ttk.Label(frame, text="Modello Ollama").grid(
            row=1, column=0, pady=(12, 0), sticky="w"
        )
        self.model_combo = ttk.Combobox(
            frame,
            textvariable=self.model_var,
            values=("translategemma:latest", "qwen3:4b"),
            state="readonly",
        )
        self.model_combo.grid(
            row=1, column=1, columnspan=2, padx=(8, 0), pady=(12, 0), sticky="ew"
        )

        ttk.Label(frame, text="Modello Whisper").grid(
            row=2, column=0, pady=(12, 0), sticky="w"
        )
        ttk.Combobox(
            frame,
            textvariable=self.whisper_var,
            values=("tiny", "base", "small", "medium"),
            state="readonly",
        ).grid(row=2, column=1, columnspan=2, padx=(8, 0), pady=(12, 0), sticky="ew")

        ttk.Label(frame, text="Lingua originale").grid(
            row=3, column=0, pady=(12, 0), sticky="w"
        )
        ttk.Combobox(
            frame,
            textvariable=self.language_var,
            values=("auto", "inglese", "spagnolo", "francese", "tedesco"),
            state="readonly",
        ).grid(row=3, column=1, columnspan=2, padx=(8, 0), pady=(12, 0), sticky="ew")

        ttk.Label(frame, text="Velocità voce").grid(
            row=6, column=0, pady=(12, 0), sticky="w"
        )
        ttk.Scale(
            frame, from_=120, to=260, variable=self.rate_var, orient="horizontal"
        ).grid(row=6, column=1, padx=8, pady=(12, 0), sticky="ew")
        ttk.Label(frame, textvariable=self.rate_var, width=4).grid(
            row=6, column=2, pady=(12, 0)
        )

        ttk.Label(frame, text="Motore voce").grid(
            row=4, column=0, pady=(12, 0), sticky="w"
        )
        self.speech_combo = ttk.Combobox(
            frame,
            textvariable=self.speech_engine_var,
            values=("kokoro", "windows"),
            state="readonly",
        )
        self.speech_combo.grid(
            row=4, column=1, columnspan=2, padx=(8, 0), pady=(12, 0), sticky="ew"
        )
        self.speech_combo.bind("<<ComboboxSelected>>", self._refresh_voices)

        ttk.Label(frame, text="Voce italiana").grid(
            row=5, column=0, pady=(12, 0), sticky="w"
        )
        self.voice_combo = ttk.Combobox(
            frame,
            textvariable=self.voice_var,
            values=tuple(KOKORO_VOICES),
            state="readonly",
        )
        self.voice_combo.grid(
            row=5, column=1, columnspan=2, padx=(8, 0), pady=(12, 0), sticky="ew"
        )

        controls = ttk.Frame(frame)
        controls.grid(row=7, column=0, columnspan=3, pady=18)
        self.start_button = ttk.Button(controls, text="Avvia", command=self._start)
        self.start_button.pack(side="left", padx=4)
        self.pause_button = ttk.Button(
            controls, text="Pausa", command=self._pause, state="disabled"
        )
        self.pause_button.pack(side="left", padx=4)
        self.stop_button = ttk.Button(
            controls, text="Stop", command=self._stop, state="disabled"
        )
        self.stop_button.pack(side="left", padx=4)
        self.export_button = ttk.Button(
            controls, text="Esporta audio", command=self._export
        )
        self.export_button.pack(side="left", padx=4)
        self.video_button = ttk.Button(
            controls, text="Crea video IT", command=self._export_video
        )
        self.video_button.pack(side="left", padx=4)
        self.overlay_button = ttk.Button(
            controls, text="Overlay", command=self._toggle_overlay
        )
        self.overlay_button.pack(side="left", padx=4)
        self.live_button = ttk.Button(
            controls, text="Live PC", command=self._toggle_live
        )
        self.live_button.pack(side="left", padx=4)
        ttk.Checkbutton(
            controls, text="Mostra testo", variable=self.show_text_var
        ).pack(side="left", padx=16)

        ttk.Label(frame, textvariable=self.status_var).grid(
            row=8, column=0, columnspan=3, sticky="w"
        )
        self.output = tk.Text(frame, wrap="word", height=10, state="disabled")
        self.output.grid(row=9, column=0, columnspan=3, pady=(8, 0), sticky="nsew")

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

    def _start(self) -> None:
        self.start_button.configure(state="disabled")
        self.status_var.set("Preparazione/trascrizione…")
        threading.Thread(
            target=self._prepare, args=(self._settings(),), daemon=True
        ).start()

    def _prepare(self, settings: RunSettings) -> None:
        try:
            path = self._resolve_input(settings.source)
            cues = load_cues(path, whisper_model=settings.whisper_model)
            if not cues:
                raise ValueError("Nessuna battuta rilevata.")
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
            self.after(0, self._begin_playback)
        except Exception as exc:
            self.after(0, self._show_error, exc)
            self.after(0, self._reset_controls)

    def _begin_playback(self) -> None:
        self.pause_button.configure(state="normal")
        self.stop_button.configure(state="normal")
        if self.player:
            self.player.start()

    def _pause(self) -> None:
        if self.player:
            paused = self.player.toggle_pause()
            self.pause_button.configure(text="Riprendi" if paused else "Pausa")

    def _stop(self) -> None:
        if self.player:
            self.player.stop()
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
                self._resolve_input(settings.source),
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
            source = self._resolve_input(settings.source)
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

    def _resolve_input(self, value: str) -> Path:
        if not is_web_url(value):
            return Path(value)
        if self.download_directory is None:
            self.download_directory = tempfile.TemporaryDirectory(prefix="uvt-url-")
        self.after(0, self.status_var.set, "Download video…")
        return download_video(value, self.download_directory.name)

    def _toggle_overlay(self) -> None:
        visible = self.overlay.toggle()
        self.overlay_button.configure(
            text="Nascondi overlay" if visible else "Overlay"
        )

    def _toggle_live(self) -> None:
        if self.live and self.live.running:
            self.live.stop()
            self.live_button.configure(text="Live PC")
            return
        settings = self._settings()
        self.live = LiveTranslator(
            translator=OllamaTranslator(model=settings.ollama_model),
            cache=TranslationCache(),
            whisper_model=settings.whisper_model,
            source_language=settings.language,
            rate=settings.rate,
            on_text=lambda text: self.after(0, self._show_text, text),
            on_status=lambda text: self.after(0, self._set_status, text),
            on_error=lambda error: self.after(0, self._show_error, error),
        )
        self.live.start()
        self.live_button.configure(text="Stop Live")

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
        if self.player:
            self.player.stop()
        if self.live:
            self.live.stop()
        if self.download_directory:
            self.download_directory.cleanup()
        self.destroy()


def main() -> int:
    TranslatorWindow().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
