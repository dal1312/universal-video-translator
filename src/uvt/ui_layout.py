from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .profiles import PROFILE_LABELS
from .tts import KOKORO_VOICES


def build_window(window: Any) -> None:
    root = ttk.Frame(window, padding=(22, 16, 22, 16))
    root.pack(fill="both", expand=True)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    header = ttk.Frame(root)
    header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    header.columnconfigure(0, weight=1)
    title_box = ttk.Frame(header)
    title_box.grid(row=0, column=0, sticky="w")
    ttk.Label(
        title_box,
        text="Universal Video Translator",
        style="Title.TLabel",
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        title_box,
        text="Traduzione locale di media, audio e documenti",
        style="Subtitle.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(1, 0))
    ttk.Button(
        header,
        text="Impostazioni",
        command=window._toggle_settings_panel,
        style="Ghost.TButton",
    ).grid(row=0, column=1, rowspan=2, padx=(8, 0), sticky="e")
    ttk.Button(
        header,
        text="Estensione browser",
        command=window._connect_browser,
        style="Ghost.TButton",
    ).grid(row=0, column=2, rowspan=2, padx=(8, 0), sticky="e")
    window.theme_button = ttk.Button(
        header,
        text="Tema chiaro",
        command=window._toggle_theme,
        style="Ghost.TButton",
    )
    window.theme_button.grid(row=0, column=3, rowspan=2, padx=(8, 0))

    body = ttk.Panedwindow(root, orient="horizontal", style="Main.TPanedwindow")
    body.grid(row=1, column=0, sticky="nsew")
    window.main_body = body

    settings_card = ttk.Frame(body, style="Surface.TFrame")
    window.settings_card = settings_card
    settings_card.configure(width=270)
    settings_card.columnconfigure(0, weight=1)
    settings_card.rowconfigure(0, weight=1)
    panel_color = window.style.lookup("Card.TFrame", "background")
    window.settings_canvas = tk.Canvas(
        settings_card,
        background=panel_color,
        borderwidth=0,
        highlightthickness=0,
    )
    settings_scrollbar = ttk.Scrollbar(
        settings_card,
        orient="vertical",
        command=window.settings_canvas.yview,
    )
    window.settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
    window.settings_canvas.grid(row=0, column=0, sticky="nsew")
    settings_scrollbar.grid(row=0, column=1, sticky="ns")
    settings = ttk.Frame(
        window.settings_canvas, padding=(18, 18, 16, 20), style="Card.TFrame"
    )
    settings.columnconfigure(0, weight=1)
    settings_window = window.settings_canvas.create_window(
        (0, 0), window=settings, anchor="nw"
    )
    settings.bind(
        "<Configure>",
        lambda _event: window.settings_canvas.configure(
            scrollregion=window.settings_canvas.bbox("all")
        ),
    )
    window.settings_canvas.bind(
        "<Configure>",
        lambda event: window.settings_canvas.itemconfigure(
            settings_window, width=event.width
        ),
    )
    settings.bind(
        "<Enter>",
        lambda _event: window.settings_canvas.bind_all(
            "<MouseWheel>", window._scroll_settings
        ),
    )
    settings.bind(
        "<Leave>",
        lambda _event: window.settings_canvas.unbind_all("<MouseWheel>"),
    )
    body.add(settings_card, weight=1)
    ttk.Label(
        settings, text="IMPOSTAZIONI", style="CardSection.TLabel"
    ).grid(row=0, column=0, sticky="w")

    ttk.Label(settings, text="Voce italiana", style="Card.TLabel").grid(
        row=1, column=0, sticky="w", pady=(18, 0)
    )
    window.voice_combo = ttk.Combobox(
        settings,
        textvariable=window.voice_var,
        values=tuple(KOKORO_VOICES),
        state="readonly",
    )
    window.voice_combo.grid(
        row=2, column=0, sticky="ew", pady=(6, 16)
    )

    rate_header = ttk.Frame(settings, style="Card.TFrame")
    rate_header.grid(row=3, column=0, sticky="ew")
    rate_header.columnconfigure(0, weight=1)
    ttk.Label(rate_header, text="Velocità voce", style="Card.TLabel").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        rate_header, textvariable=window.rate_var, style="CardAccent.TLabel"
    ).grid(row=0, column=1, sticky="e")
    ttk.Scale(
        settings,
        from_=120,
        to=260,
        variable=window.rate_var,
        orient="horizontal",
    ).grid(row=4, column=0, sticky="ew", pady=(5, 18))

    ttk.Label(settings, text="Profilo prestazioni", style="Card.TLabel").grid(
        row=5, column=0, sticky="w"
    )
    window.profile_combo = ttk.Combobox(
        settings,
        textvariable=window.profile_var,
        values=PROFILE_LABELS,
        state="readonly",
    )
    window.profile_combo.grid(row=6, column=0, sticky="ew", pady=(6, 18))
    window.profile_combo.bind("<<ComboboxSelected>>", window._apply_profile)

    ttk.Label(
        settings,
        textvariable=window.system_status_var,
        style="CardSubtitle.TLabel",
        wraplength=230,
    ).grid(row=7, column=0, sticky="w", pady=(0, 8))
    ttk.Button(
        settings,
        text="Verifica configurazione",
        command=window._run_preflight,
        style="Subtle.TButton",
    ).grid(row=8, column=0, sticky="ew", pady=(0, 10))

    window.advanced_button = ttk.Button(
        settings,
        text="Impostazioni avanzate",
        command=window._toggle_advanced_settings,
        style="Subtle.TButton",
    )
    window.advanced_button.grid(
        row=9, column=0, sticky="ew"
    )
    window.advanced_frame = ttk.Frame(
        settings, style="Card.TFrame"
    )
    window.advanced_frame.grid(
        row=10, column=0, sticky="ew", pady=(14, 0)
    )
    window.advanced_frame.columnconfigure(0, weight=1)
    ttk.Label(
        window.advanced_frame, text="Modello traduzione", style="Card.TLabel"
    ).grid(row=0, column=0, sticky="w")
    window.model_combo = ttk.Combobox(
        window.advanced_frame,
        textvariable=window.model_var,
        values=("translategemma:latest", "translategemma:12b", "argos:offline"),
        state="readonly",
    )
    window.model_combo.grid(row=1, column=0, sticky="ew", pady=(5, 12))
    ttk.Label(
        window.advanced_frame, text="Lingua sorgente", style="Card.TLabel"
    ).grid(row=2, column=0, sticky="w")
    ttk.Combobox(
        window.advanced_frame,
        textvariable=window.language_var,
        values=("auto", "inglese", "spagnolo", "francese", "tedesco"),
        state="readonly",
    ).grid(row=3, column=0, sticky="ew", pady=(5, 12))
    ttk.Label(
        window.advanced_frame, text="Motore voce", style="Card.TLabel"
    ).grid(row=4, column=0, sticky="w")
    window.speech_combo = ttk.Combobox(
        window.advanced_frame,
        textvariable=window.speech_engine_var,
        values=("kokoro", "piper", "windows"),
        state="readonly",
    )
    window.speech_combo.grid(row=5, column=0, sticky="ew", pady=(5, 12))
    window.speech_combo.bind("<<ComboboxSelected>>", window._refresh_voices)
    ttk.Label(
        window.advanced_frame, text="Modello Whisper", style="Card.TLabel"
    ).grid(
        row=6, column=0, sticky="w"
    )
    ttk.Combobox(
        window.advanced_frame,
        textvariable=window.whisper_var,
        values=("tiny", "base", "small", "medium"),
        state="readonly",
    ).grid(row=7, column=0, sticky="ew", pady=(5, 12))
    ttk.Label(
        window.advanced_frame, text="Cookie YouTube", style="Card.TLabel"
    ).grid(
        row=8, column=0, sticky="w"
    )
    ttk.Combobox(
        window.advanced_frame,
        textvariable=window.cookies_var,
        values=("firefox", "chrome", "edge", "nessuno"),
        state="readonly",
    ).grid(row=9, column=0, sticky="ew", pady=(5, 12))
    ttk.Label(
        window.advanced_frame, text="Browser audio Overlay", style="Card.TLabel"
    ).grid(row=10, column=0, sticky="w")
    ttk.Combobox(
        window.advanced_frame,
        textvariable=window.routing_browser_var,
        values=("firefox", "chrome", "edge"),
        state="readonly",
    ).grid(row=11, column=0, sticky="ew", pady=(5, 0))
    ttk.Button(
        window.advanced_frame,
        text="Modifica glossario traduzioni",
        command=window._open_glossary,
        style="Subtle.TButton",
    ).grid(row=12, column=0, sticky="ew", pady=(12, 0))
    ttk.Checkbutton(
        window.advanced_frame,
        text="Mostra trascrizione nell’app",
        variable=window.show_text_var,
        command=window._refresh_output_visibility,
        style="Card.TCheckbutton",
    ).grid(row=13, column=0, sticky="w", pady=(14, 0))
    window.advanced_frame.grid_remove()

    workspace = ttk.Frame(body, padding=(18, 0, 0, 0))
    window.workspace = workspace
    workspace.columnconfigure(0, weight=1)
    workspace.rowconfigure(1, weight=1)
    body.add(workspace, weight=3)
    body.forget(settings_card)
    window.settings_visible = False

    source_selector = ttk.Frame(
        workspace, padding=4, style="Surface.TFrame"
    )
    source_selector.grid(row=0, column=0, sticky="w", pady=(0, 10))
    window.file_mode_button = ttk.Button(
        source_selector,
        text="Media",
        command=lambda: window._select_source_mode("file"),
        style="ModeSelected.TButton",
    )
    window.file_mode_button.pack(side="left")
    window.live_mode_button = ttk.Button(
        source_selector,
        text="Live audio",
        command=lambda: window._select_source_mode("live"),
        style="Mode.TButton",
    )
    window.live_mode_button.pack(side="left", padx=(4, 0))
    window.document_mode_button = ttk.Button(
        source_selector,
        text="Documenti",
        command=lambda: window._select_source_mode("document"),
        style="Mode.TButton",
    )
    window.document_mode_button.pack(side="left", padx=(4, 0))

    mode_stage = ttk.Frame(workspace)
    mode_stage.grid(row=1, column=0, sticky="nsew")
    mode_stage.columnconfigure(0, weight=1)
    mode_stage.rowconfigure(0, weight=1)
    video_tab = ttk.Frame(
        mode_stage, padding=22, style="Surface.TFrame"
    )
    window.video_tab = video_tab
    window.overlay_tab = ttk.Frame(
        mode_stage, padding=(22, 14), style="Surface.TFrame"
    )
    window.document_tab = ttk.Frame(
        mode_stage, padding=22, style="Surface.TFrame"
    )
    video_tab.grid(row=0, column=0, sticky="nsew")
    window.overlay_tab.grid(row=0, column=0, sticky="nsew")
    window.document_tab.grid(row=0, column=0, sticky="nsew")
    window.overlay_tab.grid_remove()
    window.document_tab.grid_remove()

    video_tab.columnconfigure(0, weight=1)
    ttk.Label(
        video_tab,
        text="Traduci contenuti e sottotitoli",
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
    window.file_entry = ttk.Entry(
        video_tab, textvariable=window.file_var
    )
    window.file_entry.grid(
        row=3, column=0, sticky="ew", padx=(0, 10), ipady=4
    )
    window.file_entry.bind("<Button-3>", window._show_text_menu)
    ttk.Button(
        video_tab,
        text="Sfoglia…",
        command=window._browse,
        style="Subtle.TButton",
    ).grid(row=3, column=1, ipady=3)

    video_actions = ttk.Frame(video_tab, style="Card.TFrame")
    video_actions.grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(18, 0)
    )
    window.start_button = ttk.Button(
        video_actions,
        text="Avvia traduzione",
        command=window._start,
        style="Primary.TButton",
    )
    window.start_button.pack(side="left", padx=(0, 8))
    window.pause_button = ttk.Button(
        video_actions,
        text="Pausa",
        command=window._pause,
        state="disabled",
        style="Secondary.TButton",
    )
    window.pause_button.pack(side="left", padx=4)
    window.stop_button = ttk.Button(
        video_actions,
        text="Stop",
        command=window._stop,
        state="disabled",
        style="Danger.TButton",
    )
    window.stop_button.pack(side="left", padx=4)

    export_actions = ttk.Frame(video_tab, style="Card.TFrame")
    export_actions.grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(12, 0)
    )
    window.export_button = ttk.Button(
        export_actions,
        text="Esporta audio",
        command=window._export,
        style="Secondary.TButton",
    )
    window.export_button.pack(side="left", padx=(0, 8))
    window.video_button = ttk.Button(
        export_actions,
        text="Crea video italiano",
        command=window._export_video,
        style="Secondary.TButton",
    )
    window.video_button.pack(side="left")

    window.document_tab.columnconfigure(0, weight=1)
    ttk.Label(
        window.document_tab,
        text="Traduzione locale di documenti",
        style="CardPanelTitle.TLabel",
    ).grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(
        window.document_tab,
        text="TXT, Markdown, HTML, EPUB, DOCX e PDF con testo incorporato.",
        style="CardSubtitle.TLabel",
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 18))
    ttk.Label(
        window.document_tab, text="DOCUMENTO SORGENTE", style="CardSection.TLabel"
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 7))
    ttk.Entry(
        window.document_tab, textvariable=window.document_var
    ).grid(row=3, column=0, sticky="ew", padx=(0, 10), ipady=4)
    ttk.Button(
        window.document_tab,
        text="Sfoglia…",
        command=window._browse_document,
        style="Subtle.TButton",
    ).grid(row=3, column=1, ipady=3)
    ttk.Label(
        window.document_tab, text="DESTINAZIONE", style="CardSection.TLabel"
    ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(16, 7))
    ttk.Entry(
        window.document_tab, textvariable=window.document_output_var
    ).grid(row=5, column=0, sticky="ew", padx=(0, 10), ipady=4)
    ttk.Button(
        window.document_tab,
        text="Salva come…",
        command=window._browse_document_output,
        style="Subtle.TButton",
    ).grid(row=5, column=1, ipady=3)
    document_actions = ttk.Frame(window.document_tab, style="Card.TFrame")
    document_actions.grid(row=6, column=0, columnspan=2, sticky="w", pady=(18, 0))
    window.document_start_button = ttk.Button(
        document_actions,
        text="Traduci documento",
        command=window._start_document_translation,
        style="Primary.TButton",
    )
    window.document_start_button.pack(side="left", padx=(0, 8))
    window.document_stop_button = ttk.Button(
        document_actions,
        text="Stop",
        command=window._stop_document_translation,
        state="disabled",
        style="Danger.TButton",
    )
    window.document_stop_button.pack(side="left")

    window.overlay_tab.columnconfigure(0, weight=1)
    ttk.Label(
        window.overlay_tab,
        text="Traduzione live dell’audio del PC",
        style="CardPanelTitle.TLabel",
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        window.overlay_tab,
        text=(
            "Rileva VB-Cable, configura il browser chiamante e riproduce "
            "automaticamente la voce italiana."
        ),
        style="CardSubtitle.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(3, 10))
    ttk.Label(
        window.overlay_tab, text="INGRESSO AUDIO", style="CardSection.TLabel"
    ).grid(
        row=2, column=0, sticky="w"
    )
    window.capture_combo = ttk.Combobox(
        window.overlay_tab,
        textvariable=window.capture_device_var,
        values=("Audio di sistema (predefinito)",),
        state="readonly",
    )
    window.capture_combo.grid(
        row=3, column=0, sticky="ew", pady=(7, 8), ipady=3
    )
    overlay_options = ttk.Frame(window.overlay_tab, style="Card.TFrame")
    overlay_options.grid(row=4, column=0, sticky="ew", pady=(0, 12))
    ttk.Checkbutton(
        overlay_options,
        text="Riproduci anche la voce italiana",
        variable=window.live_voice_var,
        style="Card.TCheckbutton",
    ).pack(side="left")
    ttk.Checkbutton(
        overlay_options,
        text="Abbassa automaticamente l’audio originale durante la voce",
        variable=window.auto_ducking_var,
        style="Card.TCheckbutton",
    ).pack(side="left", padx=(18, 0))

    overlay_actions = ttk.Frame(
        window.overlay_tab, style="Card.TFrame"
    )
    overlay_actions.grid(row=5, column=0, sticky="ew")
    window.live_button = ttk.Button(
        overlay_actions,
        text="Avvia AI Overlay OS",
        command=window._toggle_live,
        style="Primary.TButton",
        state="disabled",
    )
    window.live_button.pack(side="left", padx=(0, 8))
    window.overlay_button = ttk.Button(
        overlay_actions,
        text="Mostra overlay",
        command=window._toggle_overlay,
        style="Secondary.TButton",
    )
    window.overlay_button.pack(side="left")
    ttk.Label(
        overlay_actions,
        textvariable=window.latency_var,
        style="CardAccent.TLabel",
    ).pack(side="left", padx=(18, 0))
    ttk.Button(
        overlay_actions,
        text="Copia diagnostica",
        command=window._copy_diagnostics,
        style="Subtle.TButton",
    ).pack(side="right")
    window.output_card = ttk.Frame(
        workspace, padding=16, style="Surface.TFrame"
    )
    window.output_card.grid(
        row=2, column=0, sticky="nsew", pady=(12, 0)
    )
    window.output_card.columnconfigure(0, weight=1)
    window.output_card.rowconfigure(1, weight=1)
    output_header = ttk.Frame(
        window.output_card, style="Card.TFrame"
    )
    output_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    ttk.Label(
        output_header,
        text="Output traduzione",
        style="CardPanelTitle.TLabel",
    ).grid(row=0, column=0, sticky="w")
    window.output = tk.Text(
        window.output_card, wrap="word", height=3, state="disabled"
    )
    window.output.grid(row=1, column=0, sticky="nsew")
    window._refresh_output_visibility()
    window._apply_text_colors()

    status_bar = ttk.Frame(root, padding=(12, 8), style="Status.TFrame")
    status_bar.grid(row=2, column=0, sticky="ew", pady=(14, 0))
    window.status_dot = ttk.Label(
        status_bar,
        text="●",
        style="StatusGood.TLabel",
    )
    window.status_dot.pack(side="left", padx=(0, 8))
    ttk.Label(
        status_bar,
        textvariable=window.status_var,
        style="Status.TLabel",
    ).pack(side="left")
    window.status_var.trace_add(
        "write", lambda *_args: window._refresh_status_indicator()
    )
    window._refresh_status_indicator()

    window.text_menu = tk.Menu(window, tearoff=False)
    window.text_menu.add_command(
        label="Taglia", command=lambda: window._text_action("<<Cut>>")
    )
    window.text_menu.add_command(
        label="Copia", command=lambda: window._text_action("<<Copy>>")
    )
    window.text_menu.add_command(
        label="Incolla", command=lambda: window._text_action("<<Paste>>")
    )
    window.text_menu.add_separator()
    window.text_menu.add_command(
        label="Seleziona tutto",
        command=lambda: window._text_action("<<SelectAll>>"),
    )
    window._apply_text_colors()
