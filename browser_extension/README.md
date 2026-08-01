# UVT Browser Link

This optional Manifest V3 extension starts AI Overlay OS in the local Universal Video Translator application through the `uvt://` protocol.

It does not read or send the page URL. The only permission is local extension storage, used to remember the selected performance profile and the latest requested command. It has no content scripts, host permissions, analytics, remote server, or access to browser history, cookies, or page content.

## Install in Chrome or Edge

1. In Universal Video Translator, select **Collega browser** to register `uvt://` and open this directory.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**.
4. Select **Load unpacked** and choose this directory.
5. Pin **Start UVT AI Overlay** to the toolbar.

Select the extension icon to open its standard popup. Choose **Rapido**, **Bilanciato**, or **Qualita**, then start, focus, or stop AI Overlay OS. Starting Overlay keeps the source tab selected and runs UVT in the background; **Apri UVT** is the only command that intentionally brings the desktop window forward. UVT waits for VB-Cable detection, routes that browser to `CABLE Input`, and starts pause-aware incremental translation; it does not fill or start **Video and files**. The badge records the latest requested state (`ON`, `OFF`, or `ERR`). Without VB-Cable, automatic startup is cancelled. Every command carries a one-time request ID; duplicate, already processed, and stale requests are ignored.

The `uvt://` custom protocol is local OS integration rather than a cryptographically authenticated channel. Approve launches only from browsers and applications you trust.
