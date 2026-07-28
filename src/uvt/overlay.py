from __future__ import annotations

import tkinter as tk


class SubtitleOverlay(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self._alpha = 0.88
        self._font_size = 20
        self.attributes("-alpha", self._alpha)
        try:
            self.attributes("-toolwindow", True)
        except tk.TclError:
            pass
        self.configure(bg="#101010")
        self.geometry("1000x150+160+650")
        self.minsize(420, 90)

        self.label = tk.Label(
            self,
            bg="#101010",
            fg="white",
            font=("Segoe UI", self._font_size, "bold"),
            wraplength=940,
            justify="center",
            padx=28,
            pady=18,
        )
        self.label.pack(fill="both", expand=True)
        self.grip = tk.Label(
            self,
            text="◢",
            bg="#101010",
            fg="#9ca3af",
            cursor="size_nw_se",
            font=("Segoe UI", 10),
        )
        self.grip.place(relx=1.0, rely=1.0, anchor="se")

        for widget in (self, self.label):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<Button-3>", self._show_menu)
        self.grip.bind("<ButtonPress-1>", self._resize_start)
        self.grip.bind("<B1-Motion>", self._resize_move)
        self.bind("<Escape>", lambda _event: self.hide())

        self.menu = tk.Menu(
            self,
            tearoff=False,
            bg="#252b35",
            fg="white",
            activebackground="#3b82f6",
            activeforeground="white",
        )
        self.menu.add_command(label="Testo più grande", command=self._font_up)
        self.menu.add_command(label="Testo più piccolo", command=self._font_down)
        self.menu.add_separator()
        self.menu.add_command(
            label="Più trasparente",
            command=lambda: self._change_alpha(-0.08),
        )
        self.menu.add_command(
            label="Meno trasparente",
            command=lambda: self._change_alpha(0.08),
        )
        self.menu.add_separator()
        self.menu.add_command(label="Nascondi overlay", command=self.hide)

        self._drag_x = self._drag_y = 0
        self._resize_x = self._resize_y = 0
        self._resize_width = self._resize_height = 0

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x, self._drag_y = event.x, event.y

    def _drag_move(self, event: tk.Event) -> None:
        self.geometry(
            f"+{event.x_root-self._drag_x}+{event.y_root-self._drag_y}"
        )

    def _resize_start(self, event: tk.Event) -> None:
        self._resize_x, self._resize_y = event.x_root, event.y_root
        self._resize_width, self._resize_height = (
            self.winfo_width(),
            self.winfo_height(),
        )

    def _resize_move(self, event: tk.Event) -> None:
        width = max(420, self._resize_width + event.x_root - self._resize_x)
        height = max(90, self._resize_height + event.y_root - self._resize_y)
        self.geometry(f"{width}x{height}")
        self.label.configure(wraplength=max(360, width - 60))

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _font_up(self) -> None:
        self._font_size = min(42, self._font_size + 2)
        self.label.configure(
            font=("Segoe UI", self._font_size, "bold")
        )

    def _font_down(self) -> None:
        self._font_size = max(12, self._font_size - 2)
        self.label.configure(
            font=("Segoe UI", self._font_size, "bold")
        )

    def _change_alpha(self, change: float) -> None:
        self._alpha = max(0.45, min(1.0, self._alpha + change))
        self.attributes("-alpha", self._alpha)

    def show_text(self, text: str) -> None:
        self.label.configure(text=text)

    def show(self) -> None:
        self.deiconify()
        self.lift()

    def hide(self) -> None:
        self.withdraw()

    def toggle(self) -> bool:
        if self.state() == "withdrawn":
            self.show()
            return True
        self.hide()
        return False
