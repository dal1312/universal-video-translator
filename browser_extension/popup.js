const profile = document.querySelector("#profile");
const status = document.querySelector("#status");
const connection = document.querySelector("#connection");
const connectionDot = document.querySelector("#connection-dot");
const session = document.querySelector("#session");
const latency = document.querySelector("#latency");
const details = document.querySelector("#details");
const BRIDGE_STATUS_URL = "http://127.0.0.1:17321/v1/status";

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
  status.textContent = response?.ok
    ? name === "quit" ? "Chiusura UVT richiesta" : response.via === "bridge" ? "Comando eseguito" : "Avvio UVT richiesto…"
    : response?.error || "Errore";
  if (response?.via === "bridge") window.setTimeout(refreshStatus, 250);
}

async function refreshStatus() {
  try {
    const response = await fetch(BRIDGE_STATUS_URL, {
      cache: "no-store",
      headers: { "X-UVT-Client": "uvt-extension-v1" },
    });
    if (!response.ok) throw new Error("offline");
    const state = await response.json();
    connection.textContent = "UVT connesso";
    connectionDot.classList.add("online");
    session.textContent = state.running ? "AI Overlay attivo" : "UVT pronto";
    const current = state.latency?.current_ms;
    const median = state.latency?.median_ms;
    latency.textContent = current ? `Latenza: ${(current / 1000).toFixed(1)} s` : "Latenza: in attesa";
    const dropped = state.latency?.dropped_segments || 0;
    const dropInfo = dropped ? ` · Recuperati ${dropped}` : "";
    details.textContent = median ? `Mediana ${(median / 1000).toFixed(1)} s · Profilo ${state.profile}${dropInfo}` : `Profilo ${state.profile}${dropInfo}`;
    if (state.profile) profile.value = state.profile;
  } catch (_error) {
    connection.textContent = "UVT non connesso";
    connectionDot.classList.remove("online");
    session.textContent = "Premi Avvia per aprire UVT";
    latency.textContent = "Latenza: —";
    details.textContent = "";
  }
}

document.querySelector("#start").addEventListener("click", () => command("overlay"));
document.querySelector("#focus").addEventListener("click", () => command("focus"));
document.querySelector("#stop").addEventListener("click", () => command("stop"));
document.querySelector("#quit").addEventListener("click", () => command("quit"));
profile.addEventListener("change", () => chrome.storage.local.set({
  uvtState: { status: "configured", profile: profile.value, updatedAt: Date.now() },
}));
restoreState();
refreshStatus();
window.setInterval(refreshStatus, 1000);
