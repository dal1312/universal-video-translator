# Universal Video Translator

[Italiano](README.md) | [English](README.en.md)

Windows desktop application for translating videos into Italian, generating synchronized speech, and translating system audio in real time. Processing runs locally with Ollama, Faster-Whisper, and Kokoro or Windows voices.

## Main Features

- YouTube and other supported web URLs through yt-dlp;
- local video, audio, SRT, and VTT files;
- local transcription and Italian translation;
- progressive playback, desktop subtitles, and AI Overlay OS;
- Italian audio and video export;
- direct Chrome/Edge AI Overlay OS startup through local `uvt://`, without transferring the page URL.

## Browser Link v0.2

1. Select **Collega browser** in the application. UVT registers `uvt://` for the current Windows user and opens the bundled extension directory.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**, select **Load unpacked**, and choose that directory.
4. Pin **Start UVT AI Overlay** to the toolbar.
5. Start the video in the browser and select the extension. The page and video stay open while UVT selects **AI Overlay OS**, routes browser audio through VB-Cable, and starts real-time translation automatically.

The extension **does not read or transmit the page URL** and requests no browser permissions. It has no site permissions, content scripts, analytics, cloud service, history access, cookie access, or access to other tabs. It opens an active local launcher tab so the protocol confirmation is visible; Chrome or Edge may leave that tab open, and it can then be closed normally. Every click creates a one-time request containing only the browser family, timestamp, and a random ID. Duplicate, already processed, or stale requests are ignored without opening UVT. The declared browser is used only for Overlay audio routing. Small anti-replay markers in `%LOCALAPPDATA%\UniversalVideoTranslator\browser-requests` contain no URLs; expired markers are removed on a later extension use.

`uvt://` is a local Windows integration, not a cryptographically authenticated channel. Confirm protocol launches only from browsers and applications you trust.

If the portable application directory is moved, select **Collega browser** again to refresh the registered executable path.

## Automatic AI Overlay OS Audio

At startup, UVT detects and selects `CABLE Output` as its input and enables Italian speech. An extension click waits for device detection and starts Overlay without filling the **Video and files** source field. If VB-Cable is not detected, automatic startup is cancelled instead of capturing default system audio. The browser that opened UVT is routed to `CABLE Input`; stopping Overlay, an Overlay failure, or closing the application restores that browser to the Windows default output. When UVT is opened manually, it uses the browser selected in advanced settings. Keep physical headphones or speakers as the default output so only the Italian voice is played there.

You can still select `System audio (default)` manually or disable Italian speech after device detection.

Routing uses the bundled local SoundVolumeView component. If it is unavailable, extension-triggered automatic startup is cancelled; manual startup remains available and reports that manual routing is required.

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
