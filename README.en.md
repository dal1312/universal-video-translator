# Universal Video Translator

[Italiano](README.md) | [English](README.en.md)

Windows desktop application for translating videos into Italian, generating synchronized speech, and translating system audio in real time. Processing runs locally with Ollama, Faster-Whisper, and Kokoro or Windows voices.

## Main Features

- YouTube and other supported web URLs through yt-dlp;
- local video, audio, SRT, and VTT files;
- local transcription and Italian translation;
- progressive playback, desktop subtitles, and AI Overlay OS;
- Italian audio and video export;
- optional Chrome/Edge integration through the local `uvt://` protocol.

## Browser Link v0.2

1. Select **Collega browser** in the application. UVT registers `uvt://` for the current Windows user and opens the bundled extension directory.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**, select **Load unpacked**, and choose that directory.
4. Pin **Send to Universal Video Translator** to the toolbar.
5. On a video page, select the extension. UVT downloads the content, starts translation, and automatically opens the player with Italian audio only.

The extension requests only `activeTab`. It reads the active tab's HTTP/HTTPS URL only when its toolbar button is selected. It has no host permissions, content scripts, analytics, cloud service, history access, or cookie access.

If the portable application directory is moved, select **Collega browser** again to refresh the registered executable path.

## Automatic AI Overlay OS Audio

At startup, UVT detects and selects `CABLE Output` as its input and enables Italian speech. Starting Overlay routes Firefox to `CABLE Input`; stopping Overlay, an Overlay failure, or closing the application restores Firefox to the Windows default output. Keep physical headphones or speakers as the default output so only the Italian voice is played there.

You can still select `System audio (default)` manually or disable Italian speech after device detection.

Routing uses the bundled local SoundVolumeView component. If it is unavailable, Overlay continues running and reports that manual routing is required.

## Windows Requirements

- Windows 10 or 11;
- Ollama and a compatible translation model;
- FFmpeg, including `ffmpeg`, `ffprobe`, and `ffplay`;
- eSpeak NG x64 for Kokoro voices;
- Python 3.10 or newer when running from source.

## Source Setup

```powershell
.\INSTALL_WINDOWS.bat
.\VERIFICA_WINDOWS.bat
.\AVVIA_WINDOWS.bat
```

## Portable Build

```powershell
.\BUILD_EXE_WINDOWS.bat
```

Distribute the complete `dist\UniversalVideoTranslator` directory. Ollama and its models remain external local components.

## License

Licensed under the [Apache License 2.0](LICENSE).
