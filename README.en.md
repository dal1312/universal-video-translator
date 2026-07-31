# Universal Video Translator

[Italiano](README.md) | [English](README.en.md)

Windows desktop application for translating videos into Italian, generating synchronized speech, and translating system audio in real time. Processing runs locally with Ollama, Faster-Whisper, and Kokoro or Windows voices.

> Status: **v0.2.1 browser integration**. The extension starts AI Overlay OS only and never reads the page URL; Video and files remains available as a manual application workflow.

## Main Features

- YouTube and other supported web URLs through yt-dlp;
- local video, audio, SRT, and VTT files;
- local transcription and Italian translation;
- progressive playback, desktop subtitles, and AI Overlay OS;
- Italian audio and video export;
- persistent settings, rotating diagnostics, and crash-safe audio routing state under `%LOCALAPPDATA%\UniversalVideoTranslator`;
- a single desktop instance: later extension clicks are forwarded to the existing window;
- direct Chrome/Edge AI Overlay OS startup through local `uvt://`, without transferring the page URL.

## Browser Link v0.2

1. Select **Collega browser** in the application. UVT registers `uvt://` for the current Windows user and opens the bundled extension directory.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**, select **Load unpacked**, and choose that directory.
4. Pin **Start UVT AI Overlay** to the toolbar.
5. Start the video in the browser and select the extension. The page and video stay open while UVT selects **AI Overlay OS**, routes browser audio through VB-Cable, and starts real-time translation automatically.

> Expected v0.2.1 behavior: selecting the extension does not fill **Video and files**, start yt-dlp, or download the video. If a URL appears in the application, an older extension version is still active.

The extension **does not read or transmit the page URL** and requests no browser permissions. It has no site permissions, content scripts, analytics, cloud service, history access, cookie access, or access to other tabs. It opens an active local launcher tab so the protocol confirmation is visible; Chrome or Edge may leave that tab open, and it can then be closed normally. Every click creates a one-time request containing only the browser family, timestamp, and a random ID. Duplicate, already processed, or stale requests are ignored without opening UVT. If UVT is already running, an authenticated local connection forwards the request to that same window instead of starting competing Overlay processes. The declared browser is used only for Overlay audio routing. Small anti-replay markers in `%LOCALAPPDATA%\UniversalVideoTranslator\browser-requests` contain no URLs; expired markers are removed on a later extension use.

`uvt://` is a local Windows integration, not a cryptographically authenticated channel. Confirm protocol launches only from browsers and applications you trust.

If the portable application directory is moved, select **Collega browser** again to refresh the registered executable path.

## Automatic AI Overlay OS Audio

At startup, UVT detects and selects `CABLE Output` as its input and enables Italian speech. An extension click waits for device detection and starts Overlay without filling the **Video and files** source field. If VB-Cable is not detected, automatic startup is cancelled instead of capturing default system audio. The browser that opened UVT is routed to `CABLE Input`; stopping Overlay, an Overlay failure, or closing the application restores that browser to the Windows default output. A local routing lease is written before the change, allowing the next startup to recover after a crash or forced termination. Manual Overlay uses the separate **Overlay audio browser** advanced setting rather than the YouTube cookie selection. Keep physical headphones or speakers as the default output so only the Italian voice is played there.

You can still select `System audio (default)` manually or disable Italian speech after device detection.

Routing uses the bundled local SoundVolumeView component. If it is unavailable, extension-triggered automatic startup is cancelled; manual startup remains available and reports that manual routing is required.

### Updating and Quick Check

After every application update:

1. Open `chrome://extensions` or `edge://extensions`.
2. Select **Reload** for **Start UVT AI Overlay**.
3. Confirm that the unpacked extension points to the current build directory:

```text
UniversalVideoTranslator\_internal\browser_extension
```

If selecting the extension still inserts a link into **Video and files**, remove the old extension and load this directory again. If UVT does not open, select **Collega browser** again to refresh the `uvt://` executable path. If UVT reports that VB-Cable was not detected, confirm that `CABLE Output (VB-Audio Virtual Cable)` exists among Windows recording devices; automatic startup remains disabled until that device is available.

## Windows Requirements

- Windows 10 or 11;
- Ollama and a compatible translation model;
- FFmpeg, including `ffmpeg`, `ffprobe`, and `ffplay`;
- Deno for YouTube downloads;
- VB-Cable for automatic browser Overlay startup;
- eSpeak NG x64 for Kokoro voices;
- Python 3.10 or newer when running from source.

## Source Setup

```powershell
.\INSTALL_WINDOWS.bat
.\VERIFICA_WINDOWS.bat
.\AVVIA_WINDOWS.bat
```

Installation uses the explicit virtual-environment Python and validated version constraints; it fails immediately instead of falling back to global Python. To pull the default model too, run `scripts\windows\Install-Windows.ps1 -PullModel`.

## Portable Build

```powershell
.\BUILD_EXE_WINDOWS.bat
```

The standard command creates an official release only from a clean worktree tagged `v0.2.1`. To create a local acceptance package from uncommitted changes, explicitly run `.\BUILD_EXE_WINDOWS.bat -AllowDirty`; provenance will record `dirty: true`.

The pipeline runs preflight checks, tests, PyInstaller, resource validation, and checksum verification. It creates `release\UniversalVideoTranslator-0.2.1-windows-x86_64.zip` plus `.zip.sha256`. The ZIP contains documentation, licenses, provenance, and per-file hashes. Ollama and its models remain external local components.

## Local Data and Diagnostics

Settings, translation cache, rotating logs, browser-request claims, routing recovery state, and single-instance state live under `%LOCALAPPDATA%\UniversalVideoTranslator`. Logs contain technical event codes and exception types but omit URLs, transcript/translation text, cookies, and device names. The main log is `logs\uvt.log`.

After a forced termination, restart UVT to recover a persisted browser-audio route before starting another Overlay. To reset preferences, close UVT and rename `settings.json`; to clear translations only, delete `cache\translations-v1.json`.

## License

Licensed under the [Apache License 2.0](LICENSE).
