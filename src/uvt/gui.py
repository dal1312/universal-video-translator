from __future__ import annotations

import tkinter as tk
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cache import TranslationCache
from .export import export_italian_audio
from .ollama import OllamaTranslator
from .player import SubtitlePlayer
from .transcription import load_cues


class TranslatorWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Universal Video Translator")
        self.geometry("760x500")
        self.minsize(650, 430)
        self.player: SubtitlePlayer | None = None

        self.file_var = tk.StringVar()
        self.model_var = tk.StringVar(value="qwen3:4b")
        self.language_var = tk.StringVar(value="auto")
        self.rate_var = tk.IntVar(value=185)
        self.whisper_var = tk.StringVar(value="small")
        self.show_text_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Pronto")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(7, weight=1)

        ttk.Label(frame, text="Sottotitoli").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.file_var).grid(
            row=0, column=1, padx=8, sticky="ew"
        )
        ttk.Button(frame, text="Sfoglia…", command=self._browse).grid(
            row=0, column=2
        )

        ttk.Label(frame, text="Modello Ollama").grid(
            row=1, column=0, pady=(12, 0), sticky="w"
        )
        ttk.Entry(frame, textvariable=self.model_var).grid(
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
            row=4, column=0, pady=(12, 0), sticky="w"
        )
        ttk.Scale(
            frame, from_=120, to=260, variable=self.rate_var, orient="horizontal"
        ).grid(row=4, column=1, padx=8, pady=(12, 0), sticky="ew")
        ttk.Label(frame, textvariable=self.rate_var, width=4).grid(
            row=4, column=2, pady=(12, 0)
        )

        controls = ttk.Frame(frame)
        controls.grid(row=5, column=0, columnspan=3, pady=18)
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
        ttk.Checkbutton(
            controls, text="Mostra testo", variable=self.show_text_var
        ).pack(side="left", padx=16)

        ttk.Label(frame, textvariable=self.status_var).grid(
            row=6, column=0, columnspan=3, sticky="w"
        )
        self.output = tk.Text(frame, wrap="word", height=10, state="disabled")
        self.output.grid(row=7, column=0, columnspan=3, pady=(8, 0), sticky="nsew")

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
        threading.Thread(target=self._prepare, daemon=True).start()

    def _prepare(self) -> None:
        try:
            path = Path(self.file_var.get())
            cues = load_cues(path, whisper_model=self.whisper_var.get())
            if not cues:
                raise ValueError("Nessuna battuta rilevata.")
            self.player = SubtitlePlayer(
                cues=cues,
                translator=OllamaTranslator(model=self.model_var.get().strip()),
                cache=TranslationCache(),
                source_language=self.language_var.get(),
                rate=self.rate_var.get(),
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
            target=self._run_export, args=(destination,), daemon=True
        ).start()

    def _run_export(self, destination: str) -> None:
        try:
            cues = load_cues(
                Path(self.file_var.get()), whisper_model=self.whisper_var.get()
            )
            output = export_italian_audio(
                cues,
                destination,
                translator=OllamaTranslator(model=self.model_var.get().strip()),
                cache=TranslationCache(),
                source_language=self.language_var.get(),
                rate=self.rate_var.get(),
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

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        if text in {"Completato", "Interrotto", "Errore"}:
            self._reset_controls()

    def _show_text(self, text: str) -> None:
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
        self.destroy()


def main() -> int:
    TranslatorWindow().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
