from __future__ import annotations

import json
import os
import subprocess
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .assistant_memory import default_memory_path


class AutomationError(RuntimeError):
    pass


ALLOWED_KEYS = {
    "alt",
    "backspace",
    "ctrl",
    "delete",
    "down",
    "end",
    "enter",
    "esc",
    "home",
    "left",
    "pagedown",
    "pageup",
    "right",
    "shift",
    "space",
    "tab",
    "up",
    "win",
    *tuple(chr(value) for value in range(ord("a"), ord("z") + 1)),
    *tuple(str(value) for value in range(10)),
}

ALLOWED_APPS = {
    "notepad": ("notepad.exe",),
    "calculator": ("calc.exe",),
    "explorer": ("explorer.exe",),
    "paint": ("mspaint.exe",),
}


@dataclass(frozen=True, slots=True)
class AutomationAction:
    type: str
    text: str = ""
    url: str = ""
    app: str = ""
    keys: tuple[str, ...] = ()
    x: int = 0
    y: int = 0
    seconds: float = 0

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AutomationAction":
        kind = str(raw.get("type", "")).strip().casefold()
        allowed_types = {
            "open_url",
            "open_app",
            "copy_text",
            "type_text",
            "hotkey",
            "press",
            "click",
            "wait",
        }
        if kind not in allowed_types:
            raise AutomationError(f"Azione non consentita: {kind!r}")

        text = str(raw.get("text", ""))
        if len(text) > 5000:
            raise AutomationError("Testo automazione troppo lungo.")

        url = str(raw.get("url", "")).strip()
        if kind == "open_url":
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise AutomationError(f"URL non valido: {url!r}")

        app = str(raw.get("app", "")).strip().casefold()
        if kind == "open_app" and app not in ALLOWED_APPS:
            raise AutomationError(
                f"Applicazione non autorizzata: {app!r}"
            )

        keys = tuple(
            str(key).strip().casefold()
            for key in raw.get("keys", [])
            if str(key).strip()
        )
        if kind in {"hotkey", "press"}:
            if not keys or len(keys) > 4:
                raise AutomationError("Combinazione di tasti non valida.")
            invalid = set(keys) - ALLOWED_KEYS
            if invalid:
                raise AutomationError(
                    f"Tasti non consentiti: {', '.join(sorted(invalid))}"
                )

        x = int(raw.get("x", 0))
        y = int(raw.get("y", 0))
        if kind == "click" and (x < 0 or y < 0):
            raise AutomationError("Coordinate del clic non valide.")

        seconds = float(raw.get("seconds", 0))
        if kind == "wait" and not 0 <= seconds <= 10:
            raise AutomationError("Attesa consentita: da 0 a 10 secondi.")

        return cls(
            type=kind,
            text=text,
            url=url,
            app=app,
            keys=keys,
            x=x,
            y=y,
            seconds=seconds,
        )

    def description(self) -> str:
        details = {
            "open_url": f"Apri URL: {self.url}",
            "open_app": f"Apri applicazione: {self.app}",
            "copy_text": f"Copia negli appunti: {self.text[:120]}",
            "type_text": f"Scrivi: {self.text[:120]}",
            "hotkey": f"Scorciatoia: {'+'.join(self.keys)}",
            "press": f"Premi: {'+'.join(self.keys)}",
            "click": f"Clic alle coordinate ({self.x}, {self.y})",
            "wait": f"Attendi {self.seconds:g} secondi",
        }
        return details[self.type]


@dataclass(frozen=True, slots=True)
class AutomationPlan:
    title: str
    actions: tuple[AutomationAction, ...]

    @classmethod
    def from_payload(
        cls, payload: str | dict[str, Any]
    ) -> "AutomationPlan":
        if isinstance(payload, str):
            start, end = payload.find("{"), payload.rfind("}")
            if start < 0 or end <= start:
                raise AutomationError("Il modello non ha prodotto un piano JSON.")
            try:
                raw = json.loads(payload[start : end + 1])
            except json.JSONDecodeError as exc:
                raise AutomationError(
                    "Piano automazione JSON non valido."
                ) from exc
        else:
            raw = payload
        if not isinstance(raw, dict):
            raise AutomationError("Piano automazione non valido.")
        action_values = raw.get("actions")
        if not isinstance(action_values, list) or not action_values:
            raise AutomationError("Il piano non contiene azioni.")
        if len(action_values) > 20:
            raise AutomationError("Massimo 20 azioni per automazione.")
        actions = tuple(
            AutomationAction.from_dict(item)
            for item in action_values
            if isinstance(item, dict)
        )
        if len(actions) != len(action_values):
            raise AutomationError("Una o più azioni non sono valide.")
        return cls(
            title=str(raw.get("title", "Automazione")).strip()[:120]
            or "Automazione",
            actions=actions,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "actions": [
                {**asdict(action), "keys": list(action.keys)}
                for action in self.actions
            ],
        }

    def description(self) -> str:
        lines = [self.title]
        lines.extend(
            f"{index}. {action.description()}"
            for index, action in enumerate(self.actions, start=1)
        )
        return "\n".join(lines)


class AutomationExecutor:
    def __init__(
        self, on_status: Callable[[str], None] | None = None
    ) -> None:
        self.on_status = on_status or (lambda _text: None)

    def execute(self, plan: AutomationPlan) -> None:
        try:
            import pyautogui
            import pyperclip
        except ImportError as exc:
            raise AutomationError(
                "Automazione non installata. Esegui INSTALL_WINDOWS.bat."
            ) from exc

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.15
        pyautogui.sleep(0.6)
        for index, action in enumerate(plan.actions, start=1):
            self.on_status(
                f"Automazione {index}/{len(plan.actions)}: "
                f"{action.description()}"
            )
            if action.type == "open_url":
                webbrowser.open(action.url)
            elif action.type == "open_app":
                subprocess.Popen(
                    ALLOWED_APPS[action.app],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=int(
                        getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    ),
                )
            elif action.type == "copy_text":
                pyperclip.copy(action.text)
            elif action.type == "type_text":
                pyperclip.copy(action.text)
                pyautogui.hotkey("ctrl", "v")
            elif action.type == "hotkey":
                pyautogui.hotkey(*action.keys)
            elif action.type == "press":
                for key in action.keys:
                    pyautogui.press(key)
            elif action.type == "click":
                width, height = pyautogui.size()
                if action.x >= width or action.y >= height:
                    raise AutomationError(
                        f"Clic fuori dallo schermo: ({action.x}, {action.y})"
                    )
                pyautogui.click(action.x, action.y)
            elif action.type == "wait":
                pyautogui.sleep(action.seconds)


class MacroStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = (
            Path(path)
            if path is not None
            else default_memory_path().with_name("macros.json")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self, name: str, plan: AutomationPlan) -> None:
        safe_name = name.strip()[:100]
        if not safe_name:
            raise AutomationError("Nome macro non valido.")
        macros = self._read()
        macros[safe_name] = plan.to_dict()
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(macros, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def names(self) -> list[str]:
        return sorted(self._read(), key=str.casefold)

    def load(self, name: str) -> AutomationPlan:
        raw = self._read().get(name)
        if raw is None:
            raise AutomationError(f"Macro non trovata: {name}")
        return AutomationPlan.from_payload(raw)

