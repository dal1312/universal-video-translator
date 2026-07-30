chrome.action.onClicked.addListener((tab) => {
  const pageUrl = tab.url || "";
  if (!/^https?:\/\//i.test(pageUrl)) {
    chrome.action.setBadgeText({ tabId: tab.id, text: "ERR" });
    chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#b42318" });
    return;
  }

  const target = `uvt://translate?url=${encodeURIComponent(pageUrl)}`;
  chrome.tabs.update(tab.id, { url: target });
});
