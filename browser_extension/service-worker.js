const MIN_LAUNCH_INTERVAL_MS = 1500;
const NATIVE_HOST = "it.uvt.browser";
let lastLaunchAt = 0;

function browserName() {
  const userAgent = navigator.userAgent || "";
  if (/Edg\//i.test(userAgent)) return "edge";
  if (/Firefox\//i.test(userAgent)) return "firefox";
  return "chrome";
}

async function setState(state) {
  await chrome.storage.local.set({ uvtState: { ...state, updatedAt: Date.now() } });
  const badge = state.status === "error" ? "ERR" : state.command === "stop" ? "OFF" : "ON";
  const color = state.status === "error" ? "#b42318" : state.command === "stop" ? "#64748b" : "#18794e";
  await chrome.action.setBadgeText({ text: badge });
  await chrome.action.setBadgeBackgroundColor({ color });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "uvt-status") {
    chrome.runtime.sendNativeMessage(NATIVE_HOST, { type: "status" })
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, available: false, error: String(error) }));
    return true;
  }
  if (message?.type !== "uvt-command") return false;
  const now = Date.now();
  if (now - lastLaunchAt < MIN_LAUNCH_INTERVAL_MS) {
    sendResponse({ ok: false, error: "Attendi un momento prima di riprovare." });
    return false;
  }
  lastLaunchAt = now;
  const command = ["overlay", "stop", "focus", "quit"].includes(message.command)
    ? message.command
    : "focus";
  sendCommand(command, message.profile, now)
    .then(sendResponse)
    .catch(async (error) => {
      await setState({ status: "error", command, message: String(error) });
      sendResponse({ ok: false, error: String(error) });
    });
  return true;
});

async function sendCommand(command, profile, now) {
  try {
    const response = await chrome.runtime.sendNativeMessage(NATIVE_HOST, {
      type: "command",
      payload: { command, profile, browser: browserName() },
    });
    if (!response?.ok) throw new Error(response?.error || "UVT non disponibile");
    await setState({ status: "connected", command, profile: profile || null });
    return { ok: true, via: "bridge" };
  } catch (_bridgeError) {
    if (command === "quit") {
      await setState({ status: "idle", command });
      return { ok: true, via: "offline" };
    }
    return launchProtocol(command, profile, now);
  }
}

async function launchProtocol(command, profile, now) {
  const query = new URLSearchParams({
    browser: browserName(),
    requested_at: String(Math.floor(now / 1000)),
    request_id: crypto.randomUUID(),
  });
  if (command === "overlay" && ["rapido", "bilanciato", "qualita"].includes(profile)) {
    query.set("profile", profile);
  }
  const target = `uvt://${command}?${query.toString()}`;
  // Keep the video selected: the protocol launcher stays in background while
  // UVT handles the command locally.
  await chrome.tabs.create({ url: target, active: false });
  await setState({ status: "requested", command, profile: profile || null });
  return { ok: true, via: "protocol" };
}
