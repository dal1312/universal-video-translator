# UVT Browser Link

This optional Manifest V3 extension controls AI Overlay OS through a loopback-only local bridge. It displays live session and latency status; if UVT is closed, it falls back to the `uvt://` protocol to launch it.

It does not read or send the page URL. The only permission is local extension storage, used to remember the selected performance profile and the latest requested command. It has no content scripts, host permissions, analytics, remote server, or access to browser history, cookies, or page content.

## Install in Chrome or Edge

1. In Universal Video Translator, select **Collega browser** to register `uvt://` and open this directory.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**.
4. Select **Load unpacked** and choose this directory.
5. Pin **Start UVT AI Overlay** to the toolbar.

Select the extension icon to open its standard popup. Choose **Rapido**, **Bilanciato**, or **Qualita**, then start, focus, or stop AI Overlay OS. The popup talks only to `127.0.0.1:17321`, keeps the source tab selected, and shows live connection/session/latency data. **Apri UVT** is the only command that intentionally brings the desktop window forward. If UVT is closed, the first command uses the registered protocol to launch it. UVT waits for VB-Cable detection, routes that browser to `CABLE Input`, and starts pause-aware incremental translation. Without VB-Cable, automatic startup is cancelled.

Closing the desktop window during an active session hides it without stopping translation. Use **Apri UVT** to restore it, or **Esci completamente da UVT** to stop the session, restore audio routing, and terminate UVT.

The `uvt://` custom protocol is local OS integration rather than a cryptographically authenticated channel. Approve launches only from browsers and applications you trust.
