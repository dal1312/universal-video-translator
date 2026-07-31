const MIN_LAUNCH_INTERVAL_MS = 10000;
let launchPending = false;
let lastLaunchAt = 0;

function browserName() {
  const userAgent = navigator.userAgent || "";
  if (/Edg\//i.test(userAgent)) {
    return "edge";
  }
  if (/Firefox\//i.test(userAgent)) {
    return "firefox";
  }
  return "chrome";
}

async function showBadge(tabId, text, color) {
  if (typeof tabId !== "number") {
    return;
  }
  await chrome.action.setBadgeText({ tabId, text });
  await chrome.action.setBadgeBackgroundColor({ tabId, color });
}

chrome.action.onClicked.addListener(async (tab) => {
  const now = Date.now();
  if (launchPending || now - lastLaunchAt < MIN_LAUNCH_INTERVAL_MS) {
    await showBadge(tab.id, "WAIT", "#9a6700");
    return;
  }
  launchPending = true;
  lastLaunchAt = now;
  const query = new URLSearchParams({
    browser: browserName(),
    requested_at: String(Math.floor(now / 1000)),
    request_id: crypto.randomUUID(),
  });
  const target = `uvt://overlay?${query.toString()}`;

  try {
    // Keep the source page intact, but activate the launcher so Chromium's
    // first-use external-protocol confirmation is visible to the user.
    await chrome.tabs.create({ url: target, active: true });
    await showBadge(tab.id, "OK", "#18794e");
  } catch (_error) {
    await showBadge(tab.id, "ERR", "#b42318");
  } finally {
    launchPending = false;
  }
});
