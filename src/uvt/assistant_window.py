from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable


class AssistantWindow(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        on_submit: Callable[[str, str], None],
        on_history: Callable[[], str],
        on_clear_history: Callable[[], None],
        on_speak: Callable[[str], None],
        on_save_screenshot: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.withdraw()
        self.title("AI Overlay OS — Assistente schermo")
        self.geometry("820x610+260+120")
        self.minsize(650, 480)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self._on_submit = on_submit
        self._on_history = on_history
        self._on_clear_history = on_clear_history
        self._on_speak = on_speak
        self._on_save_screenshot = on_save_screenshot
        self._title_var = tk.StringVar(value="Finestra attiva")
        self._status_var = tk.StringVar(value="Pronto")
        self._prompt_var = tk.StringVar(value="Spiegami ciò che vedi")
        self._build()

    def _build(self) -> None:
        self.configure(bg="#14171c")
        root = tk.Frame(self, bg="#14171c", padx=18, pady=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        root.rowconfigure(7, weight=1)

        tk.Label(
            root,
            textvariable=self._title_var,
            bg="#14171c",
            fg="#60a5fa",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            root,
            text="TESTO RILEVATO",
            bg="#14171c",
            fg="#9ca3af",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(14, 5))
        self.context = tk.Text(
            root,
            height=8,
            wrap="word",
            bg="#252b35",
            fg="#f1f3f5",
            insertbackground="white",
            selectbackground="#2563eb",
            relief="flat",
            padx=10,
            pady=10,
        )
        self.context.grid(row=2, column=0, sticky="nsew")

        tk.Label(
            root,
            text="COSA DEVE FARE L’IA?",
            bg="#14171c",
            fg="#9ca3af",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", pady=(14, 5))
        command_row = tk.Frame(root, bg="#14171c")
        command_row.grid(row=4, column=0, sticky="ew")
        command_row.columnconfigure(0, weight=1)
        self.prompt = tk.Entry(
            command_row,
            textvariable=self._prompt_var,
            bg="#252b35",
            fg="#f1f3f5",
            insertbackground="white",
            relief="flat",
            font=("Segoe UI", 11),
        )
        self.prompt.grid(row=0, column=0, sticky="ew", ipady=8)
        self.prompt.bind("<Return>", lambda _event: self.submit())
        self.submit_button = ttk.Button(
            command_row,
            text="Invia",
            command=self.submit,
            style="Primary.TButton",
        )
        self.submit_button.grid(row=0, column=1, padx=(10, 0))

        quick_row = tk.Frame(root, bg="#14171c")
        quick_row.grid(row=5, column=0, sticky="ew", pady=(9, 0))
        actions = (
            ("Traduci", "Traduci in italiano il testo visibile"),
            ("Spiega", "Spiegami chiaramente ciò che vedi"),
            ("Riassumi", "Riassumi il contenuto visibile"),
            ("Correggi", "Correggi gli errori nel testo visibile"),
        )
        for label, instruction in actions:
            ttk.Button(
                quick_row,
                text=label,
                command=lambda value=instruction: self.quick_submit(value),
            ).pack(side="left", padx=(0, 6))
        ttk.Button(
            quick_row, text="Cronologia", command=self.show_history
        ).pack(side="right")

        tk.Label(
            root,
            text="RISPOSTA",
            bg="#14171c",
            fg="#9ca3af",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(row=6, column=0, sticky="ew", pady=(14, 5))
        self.result = tk.Text(
            root,
            height=9,
            wrap="word",
            state="disabled",
            bg="#252b35",
            fg="#f1f3f5",
            selectbackground="#2563eb",
            relief="flat",
            padx=10,
            pady=10,
        )
        self.result.grid(row=7, column=0, sticky="nsew")
        footer = tk.Frame(root, bg="#14171c")
        footer.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        tk.Label(
            footer,
            textvariable=self._status_var,
            bg="#14171c",
            fg="#9ca3af",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            footer,
            text="Copia risposta",
            command=self.copy_result,
        ).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(
            footer,
            text="Leggi risposta",
            command=self.speak_result,
        ).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(
            footer,
            text="Salva schermata",
            command=self._on_save_screenshot,
        ).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(
            footer,
            text="Cancella memoria",
            command=self.clear_history,
        ).grid(row=0, column=4, padx=(6, 0))

    def open_loading(self, title: str = "Finestra attiva") -> None:
        self._title_var.set(title)
        self.set_context("Riconoscimento del testo in corso…")
        self.set_result("")
        self.set_busy(True, "OCR in corso…")
        self.deiconify()
        self.lift()
        self.focus_force()

    def set_context(self, text: str) -> None:
        self.context.delete("1.0", "end")
        self.context.insert("1.0", text)

    def set_result(self, text: str) -> None:
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("1.0", text)
        self.result.configure(state="disabled")

    def set_busy(self, busy: bool, status: str) -> None:
        self._status_var.set(status)
        self.submit_button.configure(
            state="disabled" if busy else "normal"
        )

    def submit(self) -> None:
        command = self._prompt_var.get().strip()
        context = self.context.get("1.0", "end").strip()
        if not command or not context:
            return
        self.set_result("")
        self.set_busy(True, "Ollama sta elaborando…")
        self._on_submit(command, context)

    def quick_submit(self, instruction: str) -> None:
        self._prompt_var.set(instruction)
        self.submit()

    def show_history(self) -> None:
        self.set_result(self._on_history())
        self.set_busy(False, "Cronologia locale")

    def clear_history(self) -> None:
        if not messagebox.askyesno(
            "Cancella memoria",
            "Eliminare definitivamente la cronologia dell’assistente?",
            parent=self,
        ):
            return
        self._on_clear_history()
        self.set_result("Memoria locale cancellata.")
        self.set_busy(False, "Memoria cancellata")

    def result_text(self) -> str:
        return self.result.get("1.0", "end").strip()

    def copy_result(self) -> None:
        text = self.result_text()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._status_var.set("Risposta copiata")

    def speak_result(self) -> None:
        text = self.result_text()
        if text:
            self._status_var.set("Lettura della risposta…")
            self._on_speak(text)

    @property
    def window_title(self) -> str:
        return self._title_var.get()

    def show_error(self, error: Exception) -> None:
        self.set_result(f"ERRORE: {error}")
        self.set_busy(False, "Errore")
