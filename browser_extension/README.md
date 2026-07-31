# UVT Browser Link

This optional Manifest V3 extension starts AI Overlay OS in the local Universal Video Translator application through the `uvt://` protocol.

It does not read or send the page URL and requests no browser permissions. It has no content scripts, host permissions, analytics, remote server, or access to browser history, cookies, page content, or other tabs.

## Install in Chrome or Edge

1. In Universal Video Translator, select **Collega browser** to register `uvt://` and open this directory.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**.
4. Select **Load unpacked** and choose this directory.
5. Pin **Start UVT AI Overlay** to the toolbar.

Start a video and select the extension button. The source page stays open while Windows opens UVT directly on **AI Overlay OS**. UVT waits for VB-Cable detection, routes that browser to `CABLE Input`, and starts real-time translation automatically; it does not fill or start **Video and files**. Without VB-Cable, automatic startup is cancelled. The first click can show Chromium's local-protocol confirmation in an active launcher tab; if the browser leaves that tab open, close it normally. Every click carries a one-time request ID; duplicate, already processed, and stale requests are ignored without opening UVT. UVT uses the browser declared by the extension instead of falling back to Firefox.

The `uvt://` custom protocol is local OS integration rather than a cryptographically authenticated channel. Approve launches only from browsers and applications you trust.
