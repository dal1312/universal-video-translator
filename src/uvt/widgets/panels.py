"""GUI widgets and components."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class StatusFrame(ttk.Frame):
    """Frame per la barra di stato."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, style="Status.TFrame")
        self.columnconfigure(0, weight=1)
        
        self.status_var = tk.StringVar(value="Pronto")
        
        indicator = ttk.Label(
            self,
            text="●",
            style="StatusAccent.TLabel",
        )
        indicator.pack(side="left", padx=(10, 7), pady=7)
        
        self.label = ttk.Label(
            self,
            textvariable=self.status_var,
            style="Status.TLabel",
        )
        self.label.pack(side="left", pady=7)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)


class OutputPanel(ttk.Frame):
    """Pannello per l'output del testo tradotto."""

    def __init__(self, parent: tk.Widget, show_text_var: tk.BooleanVar | None = None) -> None:
        super().__init__(parent, padding=16, style="Card.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        
        self.show_text_var = show_text_var or tk.BooleanVar(value=True)
        
        header = ttk.Frame(self, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        
        ttk.Label(
            header,
            text="TESTO ITALIANO",
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w")
        
        ttk.Checkbutton(
            header,
            text="Mostra testo",
            variable=self.show_text_var,
        ).grid(row=0, column=1, sticky="e")
        
        self.output = tk.Text(
            self, wrap="word", height=12, state="disabled"
        )
        self.output.grid(row=1, column=0, sticky="nsew")

    def append_text(self, text: str) -> None:
        if not self.show_text_var.get():
            return
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def apply_colors(self, bg: str, field: str, fg: str) -> None:
        self.output.configure(
            bg=field,
            fg=fg,
            insertbackground=fg,
            selectbackground="#2563eb",
            relief="flat",
        )


class ActionButtonBar(ttk.Frame):
    """Barra di pulsanti per le azioni principali."""

    def __init__(self, parent: tk.Widget, card_style: bool = True) -> None:
        if card_style:
            super().__init__(parent, style="Card.TFrame")
        else:
            super().__init__(parent)
        
        self.buttons = {}
        self._index = 0

    def add_button(
        self,
        text: str,
        command: callable,
        style: str = "TButton",
        state: str = "normal",
        pack_side: str = "left",
        padx: tuple[int, int] | int = 4,
    ) -> ttk.Button:
        button = ttk.Button(
            self,
            text=text,
            command=command,
            style=style,
            state=state,
        )
        if isinstance(padx, tuple):
            button.pack(side=pack_side, padx=padx)
        else:
            button.pack(side=pack_side, padx=padx)
        
        self.buttons[text] = button
        return button

    def get_button(self, name: str) -> ttk.Button | None:
        return self.buttons.get(name)
