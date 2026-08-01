const MIN_LAUNCH_INTERVAL_MS = 1500;
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
  if (message?.type !== "uvt-command") return false;
  const now = Date.now();
  if (now - lastLaunchAt < MIN_LAUNCH_INTERVAL_MS) {
    sendResponse({ ok: false, error: "Attendi un momento prima di riprovare." });
    return false;
  }
  lastLaunchAt = now;
  const command = ["overlay", "stop", "focus"].includes(message.command)
    ? message.command
    : "focus";
  const query = new URLSearchParams({
    browser: browserName(),
    requested_at: String(Math.floor(now / 1000)),
    request_id: crypto.randomUUID(),
  });
  if (command === "overlay" && ["rapido", "bilanciato", "qualita"].includes(message.profile)) {
    query.set("profile", message.profile);
  }
  const target = `uvt://${command}?${query.toString()}`;
  // Keep the video selected: the protocol launcher stays in background while
  // UVT handles the command locally.
  chrome.tabs.create({ url: target, active: false })
    .then(async () => {
      await setState({ status: "requested", command, profile: message.profile || null });
      sendResponse({ ok: true });
    })
    .catch(async (error) => {
      await setState({ status: "error", command, message: String(error) });
      sendResponse({ ok: false, error: String(error) });
    });
  return true;
});
