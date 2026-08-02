from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .browser_bridge import BridgeCommand
from .browser_protocol import BrowserRequest


def bridge_snapshot(
    *,
    mode: str | None,
    phase: str,
    running: bool,
    profile: str,
    browser: str,
    capture_device: str,
    voice: bool,
    auto_ducking: bool,
    latency: Mapping[str, float | int],
    app_version: str,
    update_status: str,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "phase": phase,
        "running": running,
        "profile": profile,
        "browser": browser,
        "capture_device": capture_device,
        "voice": voice,
        "auto_ducking": auto_ducking,
        "latency": dict(latency),
        "app_version": app_version,
        "update_status": update_status,
    }


def browser_request(command: BridgeCommand) -> BrowserRequest | None:
    if command.action == "quit":
        return None
    return BrowserRequest(
        browser=command.browser,
        action=command.action,
        profile=command.profile,
    )


def dispatch_hotkey(
    command: str,
    actions: Mapping[str, Callable[[], None]],
) -> bool:
    action = actions.get(command)
    if action is None:
        return False
    action()
    return True
