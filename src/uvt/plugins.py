from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .assistant_memory import default_memory_path


class PluginError(RuntimeError):
    pass


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


@dataclass(frozen=True, slots=True)
class PluginCommand:
    id: str
    title: str
    prompt: str


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    id: str
    name: str
    version: str
    description: str
    commands: tuple[PluginCommand, ...]

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "commands": [
                {"id": command.id, "title": command.title}
                for command in self.commands
            ],
        }


BUILTIN_PLUGINS = (
    PluginDescriptor(
        id="writing",
        name="Scrittura",
        version="1.0",
        description="Correzione e riscrittura del testo visibile.",
        commands=(
            PluginCommand(
                id="improve",
                title="Migliora testo",
                prompt=(
                    "Migliora chiarezza, grammatica e stile del testo "
                    "visibile. Mantieni significato e lingua originale."
                ),
            ),
            PluginCommand(
                id="formal",
                title="Riscrivi formale",
                prompt=(
                    "Riscrivi il testo visibile in stile professionale "
                    "e formale."
                ),
            ),
        ),
    ),
    PluginDescriptor(
        id="developer",
        name="Sviluppo software",
        version="1.0",
        description="Analisi contestuale di codice ed errori.",
        commands=(
            PluginCommand(
                id="explain-error",
                title="Spiega errore",
                prompt=(
                    "Analizza l'errore visibile, identifica la causa "
                    "probabile e proponi una correzione concreta."
                ),
            ),
            PluginCommand(
                id="review-code",
                title="Controlla codice",
                prompt=(
                    "Esamina il codice visibile e segnala bug, rischi "
                    "e miglioramenti prioritari."
                ),
            ),
        ),
    ),
    PluginDescriptor(
        id="universal-translate",
        name="Traduttore universale",
        version="1.0",
        description="Traduzione contestuale del testo sullo schermo.",
        commands=(
            PluginCommand(
                id="italian",
                title="Traduci in italiano",
                prompt=(
                    "Traduci integralmente in italiano naturale il testo "
                    "visibile, senza note aggiuntive."
                ),
            ),
        ),
    ),
)


class PluginManager:
    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = (
            Path(directory)
            if directory is not None
            else default_memory_path().parent / "plugins"
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, PluginDescriptor] = {}
        self.reload()

    @staticmethod
    def _parse(raw: dict[str, Any]) -> PluginDescriptor:
        plugin_id = str(raw.get("id", "")).strip().casefold()
        if not _IDENTIFIER.fullmatch(plugin_id):
            raise PluginError("ID plugin non valido.")
        commands_raw = raw.get("commands")
        if not isinstance(commands_raw, list) or not commands_raw:
            raise PluginError("Il plugin non contiene comandi.")
        commands = []
        for value in commands_raw:
            if not isinstance(value, dict):
                raise PluginError("Comando plugin non valido.")
            command_id = str(value.get("id", "")).strip().casefold()
            prompt = str(value.get("prompt", "")).strip()
            if not _IDENTIFIER.fullmatch(command_id) or not prompt:
                raise PluginError("Comando plugin incompleto.")
            if len(prompt) > 8000:
                raise PluginError("Prompt plugin troppo lungo.")
            commands.append(
                PluginCommand(
                    id=command_id,
                    title=str(value.get("title", command_id)).strip()[:100],
                    prompt=prompt,
                )
            )
        return PluginDescriptor(
            id=plugin_id,
            name=str(raw.get("name", plugin_id)).strip()[:100],
            version=str(raw.get("version", "1.0")).strip()[:30],
            description=str(raw.get("description", "")).strip()[:500],
            commands=tuple(commands),
        )

    def reload(self) -> None:
        self._plugins = {plugin.id: plugin for plugin in BUILTIN_PLUGINS}
        for path in sorted(self.directory.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    continue
                plugin = self._parse(raw)
                self._plugins[plugin.id] = plugin
            except (OSError, json.JSONDecodeError, PluginError):
                continue

    def list_plugins(self) -> list[dict[str, Any]]:
        return [
            self._plugins[key].public_dict()
            for key in sorted(self._plugins)
        ]

    def command_choices(self) -> list[str]:
        choices = []
        for plugin_id in sorted(self._plugins):
            plugin = self._plugins[plugin_id]
            choices.extend(
                f"{plugin.id}.{command.id} — {command.title}"
                for command in plugin.commands
            )
        return choices

    def render(
        self,
        plugin_id: str,
        command_id: str,
        *,
        text: str,
        instruction: str = "",
    ) -> str:
        plugin = self._plugins.get(plugin_id.casefold())
        if plugin is None:
            raise PluginError(f"Plugin non trovato: {plugin_id}")
        command = next(
            (
                item
                for item in plugin.commands
                if item.id == command_id.casefold()
            ),
            None,
        )
        if command is None:
            raise PluginError(
                f"Comando plugin non trovato: {plugin_id}.{command_id}"
            )
        return (
            command.prompt.replace("{text}", text[:30000]).replace(
                "{instruction}", instruction[:4000]
            )
        )

