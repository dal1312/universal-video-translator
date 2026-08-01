# Changelog

[Italiano](CHANGELOG.md) | [English](CHANGELOG.en.md)

## Unreleased

- Authenticated local bridge between popup and application with live state, profile, and latency.
- `uvt://` is now only a fallback when UVT is not already running.
- Latency guard discards obsolete queued audio segments.
- Adaptive synchronization gradually accelerates translated speech using queue delay and source speech duration.
- Background mode with controls in both the popup and Windows notification area.
- SHA-256-verified automatic updates and browser-extension version synchronization.
- Global shortcuts for session control, overlay visibility, and system volume.
- Local mandatory-term glossary with automatic reload and revision-aware translation cache.
- Full exit restores audio routing, threads, and local resources.

## 0.2.1 - 2026-07-31

- The source tab is no longer replaced with the `uvt://` protocol URL.
- Selecting the extension opens and starts **AI Overlay OS** directly; the page URL is not read, transferred, filled, or downloaded.
- Browser requests are one-time; duplicates, restored tabs, and stale requests are ignored without opening UVT.
- The first-use protocol confirmation is shown in an active tab.
- Public links no longer read the browser cookie database automatically; cookies remain a manual option and an access failure retries without cookies.
- Audio routing follows the Chrome, Edge, or Firefox instance that started Overlay.
- The extension never retains tab IDs for cleanup after a restart.
- Automatic startup is cancelled when VB-Cable or browser routing is unavailable; every setup failure restores browser audio.
- A single desktop instance receives later extension clicks through authenticated local IPC.
- Browser routing uses a persistent lease and is recovered automatically after a crash or forced termination.
- Settings, cache, rotating logs, and application state now share `%LOCALAPPDATA%\UniversalVideoTranslator`.
- Diagnostics omit URLs, cookies, transcripts, translations, and device names.
- Windows installation and verification are fail-fast and validate Python, FFmpeg, Deno, Ollama, the model, and VB-Cable.
- The build creates a portable release with licenses, provenance, per-file hashes, a deterministic ZIP, and an external checksum.

## 0.2.0 - 2026-07-30

- Optional Manifest V3 Chrome/Edge extension with only the `activeTab` permission.
- Local `uvt://` protocol registered under HKCU without administrator privileges.
- Strict validation accepting one HTTP/HTTPS URL only.
- Selecting the extension automatically starts download, translation, and video playback with Italian audio only.
- **Collega browser** control and extension files included in the Windows build.
- Regression coverage for parsing, Windows registry values, and GUI startup.

## 0.1.0 - 2026-07-28

- Local Ollama translation and Faster-Whisper transcription.
- YouTube, local media, SRT, and VTT support.
- Kokoro and Windows speech synthesis.
- Progressive playback, desktop overlay, exports, and live system-audio translation.
- Windows setup, verification, and portable build scripts.
