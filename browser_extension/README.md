# UVT Browser Link

This optional Manifest V3 extension controls AI Overlay OS through browser Native Messaging. The native host authenticates to UVT's loopback bridge with an install-specific secret. It displays live session and latency status; if UVT is closed, it falls back to the `uvt://` protocol to launch it.

It does not read or send the page URL. While AI Overlay is active, a small
caption observer reads only visible subtitle elements on YouTube and Rumble
and forwards their text to the local UVT process. It does not access cookies,
history, or general page content, and it contacts no remote server.

## Install in Chrome, Edge, or Firefox

Firefox 121 or newer is required. The Manifest V3 package declares both the
event-page script used by Firefox and the service worker used by Chrome/Edge.

1. In Universal Video Translator, select **Collega browser** to register `uvt://` and open this directory.
2. Open `chrome://extensions`, `edge://extensions`, or `about:debugging#/runtime/this-firefox`.
3. Enable **Developer mode**.
4. In Chrome/Edge select **Load unpacked** and choose this directory. In Firefox select **Load Temporary Add-on** and choose `manifest.json` from this directory. If the file picker opens in the wrong place, run `INSTALLA_FIREFOX.bat` from the project folder; it opens the exact manifest file location.
5. Pin **Start UVT AI Overlay** to the toolbar.

When UVT is installed from source, **Collega browser** also writes the Firefox
Native Messaging host manifest to `%APPDATA%\\Mozilla\\NativeMessagingHosts`.
For a portable build, run **Collega browser** again after moving the folder.

Select the extension icon to open its standard popup. Choose **Rapido**, **Bilanciato**, or **Qualita**, then start, focus, or stop AI Overlay OS. The popup communicates only with the registered UVT native host, keeps the source tab selected, and shows live connection/session/latency data. **Apri UVT** is the only command that intentionally brings the desktop window forward. If UVT is closed, the first command uses the registered protocol to launch it. UVT waits for VB-Cable detection, routes that browser to `CABLE Input`, and starts pause-aware incremental translation. Without VB-Cable, automatic startup is cancelled.

Closing the desktop window during an active session hides it without stopping translation. Use **Apri UVT** to restore it, or **Esci completamente da UVT** to stop the session, restore audio routing, and terminate UVT.

The `uvt://` custom protocol is local OS integration rather than a cryptographically authenticated channel. Approve launches only from browsers and applications you trust.
