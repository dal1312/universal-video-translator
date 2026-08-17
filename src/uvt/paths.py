from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_DIRECTORY = "UniversalVideoTranslator"


@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path

    @property
    def settings(self) -> Path:
        return self.root / "settings.json"

    @property
    def translation_cache(self) -> Path:
        return self.root / "cache" / "translations-v5.json"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def routing_lease(self) -> Path:
        return self.root / "state" / "audio-routing.json"

    @property
    def browser_requests(self) -> Path:
        return self.root / "browser-requests"

    @property
    def browser_bridge_token(self) -> Path:
        return self.root / "state" / "browser-bridge.token"

    @property
    def native_messaging(self) -> Path:
        return self.root / "native-messaging"

    @property
    def instance_state(self) -> Path:
        return self.root / "instance"

    @property
    def updates(self) -> Path:
        return self.root / "updates"

    @property
    def glossary(self) -> Path:
        return self.root / "glossary.json"

    @property
    def engines(self) -> Path:
        return self.root / "engines"



def default_app_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data).expanduser()
        if candidate.is_absolute():
            return candidate / APP_DIRECTORY
    return Path.home() / ".uvt" / APP_DIRECTORY


def app_paths(root: str | Path | None = None) -> AppPaths:
    resolved = Path(root).expanduser() if root is not None else default_app_root()
    if not resolved.is_absolute():
        raise ValueError("Il percorso dati dell'app deve essere assoluto.")
    return AppPaths(resolved)
