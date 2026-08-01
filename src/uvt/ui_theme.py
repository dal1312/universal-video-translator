from __future__ import annotations

from dataclasses import dataclass
from tkinter import ttk
from typing import Any


@dataclass(frozen=True, slots=True)
class ThemePalette:
    background: str
    panel: str
    foreground: str
    field: str
    accent: str
    border: str
    muted: str
    hover: str


def palette(dark: bool) -> ThemePalette:
    if dark:
        return ThemePalette(
            "#070a10",
            "#101722",
            "#f4f7fb",
            "#172131",
            "#6c8bff",
            "#26354a",
            "#8290a5",
            "#7f9aff",
        )
    return ThemePalette(
        "#f3f5f8",
        "#ffffff",
        "#172033",
        "#f7f9fc",
        "#315ef5",
        "#d7dee8",
        "#64748b",
        "#244bd1",
    )


def apply_theme(
    window: Any,
    style: ttk.Style,
    *,
    dark: bool,
    settings_canvas: Any | None = None,
) -> ThemePalette:
    colors = palette(dark)
    bg = colors.background
    panel = colors.panel
    fg = colors.foreground
    field = colors.field
    accent = colors.accent
    border = colors.border
    muted = colors.muted

    window.configure(bg=bg)
    if settings_canvas is not None:
        settings_canvas.configure(background=panel)

    style.configure(
        ".", background=bg, foreground=fg, font=("Segoe UI Variable Text", 10)
    )
    style.configure("TFrame", background=bg)
    style.configure("Main.TPanedwindow", background=bg)
    style.configure("Card.TFrame", background=panel, relief="flat")
    for name in ("Surface.TFrame", "Status.TFrame"):
        style.configure(
            name,
            background=panel,
            bordercolor=border,
            borderwidth=1,
            relief="solid",
        )

    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("Card.TLabel", background=panel, foreground=fg)
    _label(
        style,
        "Title.TLabel",
        bg,
        fg,
        ("Segoe UI Variable Display Semibold", 22),
    )
    _label(style, "Subtitle.TLabel", bg, muted, ("Segoe UI Variable Text", 10))
    _label(
        style,
        "CardPanelTitle.TLabel",
        panel,
        fg,
        ("Segoe UI Variable Display Semibold", 17),
    )
    _label(
        style,
        "CardSection.TLabel",
        panel,
        accent,
        ("Segoe UI Variable Text Semibold", 8),
    )
    _label(
        style,
        "CardSubtitle.TLabel",
        panel,
        muted,
        ("Segoe UI Variable Text", 9),
    )
    _label(
        style,
        "CardAccent.TLabel",
        panel,
        accent,
        ("Segoe UI Variable Text Semibold", 10),
    )
    style.configure("Status.TLabel", background=panel, foreground=fg)
    style.configure("StatusGood.TLabel", background=panel, foreground="#34d399")
    style.configure("StatusBusy.TLabel", background=panel, foreground="#fbbf24")
    style.configure("StatusError.TLabel", background=panel, foreground="#fb7185")

    style.configure(
        "TEntry",
        fieldbackground=field,
        foreground=fg,
        insertcolor=fg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        padding=(11, 9),
    )
    style.configure(
        "TCombobox",
        fieldbackground=field,
        foreground=fg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        padding=(10, 8),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", field)],
        foreground=[("readonly", fg)],
    )

    style.configure(
        "TButton",
        background=field,
        foreground=fg,
        borderwidth=0,
        padding=(14, 9),
        font=("Segoe UI Variable Text Semibold", 9),
    )
    style.map(
        "TButton",
        background=[("active", border), ("disabled", panel)],
        foreground=[("disabled", muted)],
    )
    _button(style, "Ghost.TButton", field, fg, (13, 9))
    _button(style, "Secondary.TButton", field, fg, (15, 10))
    style.map(
        "Secondary.TButton",
        background=[("active", border), ("disabled", field)],
        foreground=[("disabled", muted)],
    )
    _button(
        style,
        "Mode.TButton",
        panel,
        muted,
        (17, 10),
        font=("Segoe UI Variable Text Semibold", 9),
    )
    style.map(
        "Mode.TButton",
        background=[("active", field), ("disabled", panel)],
        foreground=[("active", fg), ("disabled", muted)],
    )
    _button(
        style,
        "ModeSelected.TButton",
        accent,
        "white",
        (17, 10),
        font=("Segoe UI Variable Text Semibold", 9),
    )
    style.map(
        "ModeSelected.TButton",
        background=[("active", colors.hover), ("disabled", accent)],
        foreground=[("disabled", "white")],
    )
    style.configure(
        "Subtle.TButton",
        background=panel,
        foreground=muted,
        borderwidth=1,
        bordercolor=border,
        padding=(13, 9),
    )
    style.map(
        "Subtle.TButton",
        background=[("active", field)],
        foreground=[("active", fg)],
    )
    _button(
        style,
        "Danger.TButton",
        "#321b24" if dark else "#fff1f3",
        "#fb7185" if dark else "#be123c",
        (15, 10),
    )
    style.map(
        "Danger.TButton",
        background=[
            ("active", "#48212d" if dark else "#ffe4e8"),
            ("disabled", field),
        ],
        foreground=[("disabled", muted)],
    )
    _button(
        style,
        "Primary.TButton",
        accent,
        "white",
        (18, 10),
        font=("Segoe UI Variable Text Semibold", 10),
    )
    style.map(
        "Primary.TButton",
        background=[("active", colors.hover), ("disabled", "#475569")],
        foreground=[("disabled", "#cbd5e1")],
    )

    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.configure("Card.TCheckbutton", background=panel, foreground=fg)
    style.map("Card.TCheckbutton", background=[("active", panel)])
    style.configure(
        "Horizontal.TScale",
        background=panel,
        troughcolor=field,
        bordercolor=panel,
    )
    style.configure(
        "Vertical.TScrollbar",
        background=field,
        troughcolor=panel,
        bordercolor=panel,
        arrowcolor=muted,
        relief="flat",
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", border), ("pressed", accent)],
        arrowcolor=[("active", fg)],
    )
    return colors


def _label(
    style: ttk.Style,
    name: str,
    background: str,
    foreground: str,
    font: tuple[str, int],
) -> None:
    style.configure(
        name,
        background=background,
        foreground=foreground,
        font=font,
    )


def _button(
    style: ttk.Style,
    name: str,
    background: str,
    foreground: str,
    padding: tuple[int, int],
    *,
    font: tuple[str, int] | None = None,
) -> None:
    options: dict[str, Any] = {
        "background": background,
        "foreground": foreground,
        "padding": padding,
    }
    if font is not None:
        options["font"] = font
    style.configure(name, **options)
