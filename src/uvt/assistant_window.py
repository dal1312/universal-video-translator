from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class AssistantWindow(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        on_submit: Callable[[str, str], None],
    ) -> None:
        super().__init__(master)
        self.withdraw()
        self.title("AI Overlay OS — Assistente schermo")
        self.geometry("820x610+260+120")
        self.minsize(650, 480)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self._on_submit = on_submit
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
        root.rowconfigure(6, weight=1)

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

        tk.Label(
            root,
            text="RISPOSTA",
            bg="#14171c",
            fg="#9ca3af",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(row=5, column=0, sticky="ew", pady=(14, 5))
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
        self.result.grid(row=6, column=0, sticky="nsew")
        tk.Label(
            root,
            textvariable=self._status_var,
            bg="#14171c",
            fg="#9ca3af",
            anchor="w",
        ).grid(row=7, column=0, sticky="ew", pady=(10, 0))

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

    def show_error(self, error: Exception) -> None:
        self.set_result(f"ERRORE: {error}")
        self.set_busy(False, "Errore")

