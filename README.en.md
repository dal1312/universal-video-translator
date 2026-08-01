# Universal Video Translator

[Italiano](README.md) | [English](README.en.md)

Universal Video Translator is a Windows desktop application for translating video content into Italian, generating synchronized speech, and translating browser audio in real time through **AI Overlay OS**.

Version **v0.2.1** adds a safer browser integration: the extension does not read the current page URL, does not send URLs to the application, and starts AI Overlay OS only. The **Video and files** workflow remains available manually for YouTube URLs, local media, audio, SRT, and VTT files.

## Project Status

- Current version: `0.2.1`.
- Target platform: Windows 10/11 x64.
- Recommended distribution: portable ZIP produced by the release pipeline.
- Processing model: local, using Ollama, Faster-Whisper, and Kokoro or Windows voices.
- Browser extension target: Chrome and Edge, loaded unpacked.

## Features

- Italian translation for local videos, audio, SRT/VTT subtitles, and yt-dlp-supported URLs.
- YouTube downloads with Deno validation, 720p format limit, and visible progress.
- Existing subtitle priority with local Faster-Whisper fallback.
- Local translation through Ollama, with `translategemma:latest` as the default model.
- Kokoro-82M speech, Windows voices, and serialized speech playback to avoid overlap.
- Progressive player with resizable video, pause, stop, and translated-only audio output.
- WAV/MP3 export and MP4 creation with an Italian audio track.
- AI Overlay OS for real-time browser audio translation.
- Automatic Chrome/Edge routing through VB-Cable with crash-safe recovery.
- Single desktop instance with authenticated local forwarding for later extension clicks.
- Settings, cache, logs, and recovery state stored under `%LOCALAPPDATA%\UniversalVideoTranslator`.
- Reproducible Windows release pipeline with ZIP, checksums, provenance, and licenses.

## Operating Modes

### Video and files

Use this workflow when you want to process a file or URL manually.

1. Enter a supported URL or select a video, audio, SRT, or VTT file.
2. Choose the Ollama model, source language, speech engine, and voice.
3. Select **Avvia**.
4. Play the result or export audio/video.

For YouTube, keep the source language on `auto` in most cases. If a video requires authentication, select the browser where you are already signed in from the advanced settings.

### AI Overlay OS

Use this workflow to translate browser audio in real time.

1. Install VB-Cable.
2. Start UVT.
3. UVT detects `CABLE Output` and enables Italian speech.
4. Select the browser extension or start **AI Overlay OS** manually.
5. The browser is routed to `CABLE Input`; physical speakers or headphones remain the Windows default output.

If VB-Cable is not detected, extension-triggered automatic startup is blocked instead of capturing the wrong system audio source.

## Pipeline

```text
Video / YouTube / SRT / VTT
        |
        v
Existing subtitles or Faster-Whisper
        |
        v
Italian translation with Ollama
        |
        v
Kokoro or Windows voice
        |
        v
Synchronized player or export
```

AI Overlay OS uses the same local translation and speech stack on real-time audio windows instead of a complete media file. Adaptive synchronization gradually changes speech speed to recover delay without abrupt voice changes.

## Windows Requirements

- Windows 10 or Windows 11 x64.
- Python 3.10 x64 when running from source.
- [Ollama](https://ollama.com/download/windows) with `translategemma:latest` or a compatible model.
- FFmpeg with `ffmpeg`, `ffprobe`, and `ffplay`.
- [Deno](https://deno.com/) for YouTube URLs.
- [VB-Cable](https://vb-audio.com/Cable/) for automatic browser Overlay startup.
- eSpeak NG x64 or bundled eSpeak data for Kokoro.
- Sufficient disk space for local models and dependencies.

## Source Setup

Open PowerShell in the project directory and run:

```powershell
.\INSTALL_WINDOWS.bat
.\VERIFICA_WINDOWS.bat
.\AVVIA_WINDOWS.bat
```

The installer looks for Python x64 3.10 through `py -3.10` first and then
`python`, always creates the `.venv`, applies validated constraints, and fails
immediately on errors. It does not modify the global Python installation. If
the runtime is missing, it prints `winget install Python.Python.3.10` directly.

To pull the default model as part of setup:

```powershell
scripts\windows\Install-Windows.ps1 -PullModel
```

## Manual Startup

```powershell
.\.venv\Scripts\python.exe .\universal_video_translator.py
```

If Ollama is not already running:

```powershell
ollama serve
```

## Browser Link

1. Select **Collega browser** in the application.
2. Windows registers `uvt://` for the current user only.
3. The application opens the bundled extension directory.
4. Open `chrome://extensions` or `edge://extensions`.
5. Enable **Developer mode**.
6. Select **Load unpacked**.
7. Choose this directory:

```text
UniversalVideoTranslator\_internal\browser_extension
```

8. Pin **Start UVT AI Overlay** to the browser toolbar.

Expected v0.2.1 behavior:

- the click does not read the page URL;
- the click does not fill **Video and files**;
- the click does not start yt-dlp or download the video;
- the click selects **AI Overlay OS**, waits for VB-Cable, and starts live translation;
- if UVT is already running, the request is forwarded to the existing window.

If a click still inserts a URL into **Video and files** after an update, remove the old extension, load the extension bundled with the current build, and select **Collega browser** again.

## Security And Privacy

UVT is designed for local use.

- The extension requests no browser permissions.
- The extension has no content scripts, host permissions, cookie access, history access, tab access, analytics, or cloud service.
- The `uvt://` protocol carries only browser family, timestamp, and a one-time random ID.
- Duplicate, stale, or already processed requests are ignored.
- Anti-replay markers contain no URLs and are cleaned on later extension use.
- Logs do not record URLs, transcripts, translations, cookies, or device names.
- External network access is limited to user-requested video, dependency, and model downloads.

`uvt://` is a local Windows integration, not an end-to-end cryptographically authenticated channel. Confirm protocol launches only from trusted browsers and applications.

## Local Data

UVT stores operational data in:

```text
%LOCALAPPDATA%\UniversalVideoTranslator
```

Main contents:

- `settings.json`: user preferences.
- `cache\translations-v5.json`: translation cache.
- `logs\uvt.log`: privacy-safe rotating diagnostics.
- `browser-requests\`: anti-replay markers.
- audio-routing state: crash-recovery lease for browser output restoration.

To reset preferences, close UVT and rename `settings.json`. To clear translations only, delete `cache\translations-v5.json`.

## Verification

```powershell
.\VERIFICA_WINDOWS.bat
```

Verification is non-mutating and checks syntax, tests, versions, Python dependencies, FFmpeg/ffprobe/ffplay, Deno, SoundVolumeView, eSpeak NG, Kokoro, Faster-Whisper, SoundCard, Ollama, the default model, and VB-Cable.

The essential check can be repeated inside the app with **Settings → Verify configuration**. To validate real GUI construction, the contextual panel, and shutdown:

```powershell
.\.venv\Scripts\python.exe scripts\windows\smoke_gui.py
```

To measure Whisper accuracy, translation fidelity, Ollama time, and Kokoro
generation speed repeatably on the real local engines:

```powershell
.\.venv\Scripts\python.exe scripts\windows\benchmark_local.py --output WINDOWS_BENCHMARK.json
```

This controlled benchmark does not replace a live measurement: browser
latency also includes capture, VAD, speech pauses, and audio queues.

The latest local validation recorded in `WINDOWS_VALIDATION.md` includes:

- The complete pytest suite passed in the latest local validation.
- Successful PyInstaller build.
- Successful single-instance packaged smoke test.
- ZIP and payload checksum verification.

## Windows Build And Release

```powershell
.\BUILD_EXE_WINDOWS.bat
```

The standard command creates an official release only from a clean worktree tagged `v0.2.1`. To create a local acceptance package from uncommitted changes, explicitly run:

```powershell
.\BUILD_EXE_WINDOWS.bat -AllowDirty
```

Main outputs:

```text
dist-browser-v0.2-release\UniversalVideoTranslator\UniversalVideoTranslator.exe
release\UniversalVideoTranslator-0.2.1-windows-x86_64.zip
release\UniversalVideoTranslator-0.2.1-windows-x86_64.zip.sha256
```

Distribute the full ZIP, not only the EXE. The package includes README files, changelogs, license, third-party notices, provenance, and `SHA256SUMS.txt`.

## Third-Party Components

Bundled and external components are documented in `THIRD_PARTY_NOTICES.md`.

- SoundVolumeView 2.53 is bundled unchanged for per-application audio routing.
- FFmpeg full build is copied into the Windows package.
- Ollama, Deno, VB-Cable, and translation/speech models remain external local components.

Review licensing terms before redistributing the package in commercial contexts.

## Troubleshooting

- **Extension opens Video and files**: old extension version; remove it and load `_internal\browser_extension` from the current build.
- **UVT does not start from the browser**: select **Collega browser** again to refresh the `uvt://` registration.
- **VB-Cable not detected**: confirm that `CABLE Output (VB-Audio Virtual Cable)` exists in Windows recording devices.
- **Browser remains on CABLE Input after a crash**: restart UVT; the routing lease attempts automatic recovery.
- **YouTube fails**: check Deno, FFmpeg, and the selected browser cookies in advanced settings.
- **Diagnostics needed**: inspect `%LOCALAPPDATA%\UniversalVideoTranslator\logs\uvt.log`.

## Known Limits

- Translation quality depends on the selected Ollama model.
- First Kokoro use may require downloading the model.
- YouTube can change access controls or require valid cookies.
- Browser audio routing applies to the browser process family, not a single tab.
- v0.2.1 is a portable distribution, not an MSI installer.
- After moving the portable directory, select **Collega browser** again.

## License

Licensed under the [Apache License 2.0](LICENSE).

## Author

Developed by [dal1312](https://github.com/dal1312).
