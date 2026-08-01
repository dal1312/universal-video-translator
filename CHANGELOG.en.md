# Changelog

[Italiano](CHANGELOG.md) | [English](CHANGELOG.en.md)

## Unreleased

- Repeatable local benchmark for Whisper accuracy, multilingual fidelity, Ollama latency, and Kokoro speed; full Ollama warm-up removes the first Live translation delay.
- Audio/video export moved out of the window into a dedicated controller, with progressive-player workers registered in the runtime supervisor for deterministic shutdown.
- Document translation lifecycle extracted from the GUI into a dedicated controller with centralized cancellation and session state.
- Tk layout extracted into a dedicated module, repeatable preflight, and parallel Ollama, Whisper, and speech warm-up to reduce the first Live response.
- End-to-end Windows smoke test covering GUI construction, contextual settings, and complete shutdown.
- Operational failures centralized into actionable messages that explain the problem and correction without exposing internal details.
- Visual system extracted from the main window and automatic selection of an installed Ollama model when the saved choice is unavailable.
- Contextual settings panel, collapsed at startup, with automatic component detection and Windows voice fallback when Kokoro is unavailable.
- Central runtime supervisor for background workers and coordinated multimedia-resource shutdown.
- Desktop UI redesigned as a local control room with clearer typography, flow navigation, and operating states.
- Adaptive layout with safe on-screen positioning and a compact Live panel that keeps translation output visible.
- Authenticated local bridge between popup and application with live state, profile, and latency.
- `uvt://` is now only a fallback when UVT is not already running.
- Latency guard discards obsolete queued audio segments.
- Adaptive synchronization gradually accelerates translated speech using queue delay and source speech duration.
- Background mode with controls in both the popup and Windows notification area.
- SHA-256-verified automatic updates and browser-extension version synchronization.
- Global shortcuts for session control, overlay visibility, and system volume.
- Local mandatory-term glossary with automatic reload and revision-aware translation cache.
- New local Documents mode for TXT, Markdown, HTML, EPUB, DOCX, and text-based PDF files.
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
