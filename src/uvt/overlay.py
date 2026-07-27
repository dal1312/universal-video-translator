from __future__ import annotations

import tkinter as tk


class SubtitleOverlay(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.88)
        self.configure(bg="#101010")
        self.label = tk.Label(
            self,
            bg="#101010",
            fg="white",
            font=("Segoe UI", 20, "bold"),
            wraplength=1000,
            justify="center",
            padx=24,
            pady=14,
        )
        self.label.pack(fill="both", expand=True)
        self.geometry("+160+760")
        self.bind("<ButtonPress-1>", self._drag_start)
        self.bind("<B1-Motion>", self._drag_move)
        self._drag_x = self._drag_y = 0

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x, self._drag_y = event.x, event.y

    def _drag_move(self, event: tk.Event) -> None:
        self.geometry(f"+{event.x_root-self._drag_x}+{event.y_root-self._drag_y}")

    def show_text(self, text: str) -> None:
        self.label.configure(text=text)

    def toggle(self) -> bool:
        if self.state() == "withdrawn":
            self.deiconify()
            return True
        self.withdraw()
        return False
