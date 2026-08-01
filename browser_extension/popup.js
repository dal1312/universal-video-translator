const profile = document.querySelector("#profile");
const status = document.querySelector("#status");

async function restoreState() {
  const { uvtState } = await chrome.storage.local.get("uvtState");
  if (uvtState?.profile) profile.value = uvtState.profile;
  if (uvtState?.command) {
    status.textContent = `Ultimo comando: ${uvtState.command}`;
  }
}

async function command(name) {
  status.textContent = "Invio richiesta locale…";
  const response = await chrome.runtime.sendMessage({
    type: "uvt-command",
    command: name,
    profile: profile.value,
  });
  status.textContent = response?.ok ? "Richiesta inviata a UVT" : response?.error || "Errore";
}

document.querySelector("#start").addEventListener("click", () => command("overlay"));
document.querySelector("#focus").addEventListener("click", () => command("focus"));
document.querySelector("#stop").addEventListener("click", () => command("stop"));
profile.addEventListener("change", () => chrome.storage.local.set({
  uvtState: { status: "configured", profile: profile.value, updatedAt: Date.now() },
}));
restoreState();
