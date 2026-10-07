"""Which parts of the dropdown are shown.

Each part of the dropdown can be turned off in the Settings window. Choices are saved, so they
survive restarts; everything is on until you turn it off.
"""

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from .models import HookState, State


@dataclass(frozen=True)
class Setting:
    key: str
    group: str
    label: str
    help: str
    # Another setting that must be on for this one to matter.
    requires: Optional[str] = None


SETTINGS: list[Setting] = [
    Setting("opencode", "Agents", "OpenCode", "OpenCode sessions in the menu bar and dropdown."),
    Setting("codex", "Agents", "Codex", "Codex sessions in the menu bar and dropdown."),
    Setting("claude", "Agents", "Claude Code",
            "Claude Code sessions in the menu bar and dropdown."),
    Setting("codex_usage", "Usage", "Codex usage",
            "Codex usage bars, and a reminder in the menu bar when usage is low.",
            requires="codex"),
    Setting("claude_usage", "Usage", "Claude Code usage",
            "Claude usage bars, and a reminder in the menu bar when usage is low.",
            requires="claude"),
    Setting("show_opencode", "Buttons", "Show OpenCode", "Brings the OpenCode app to the front."),
    Setting("show_codex", "Buttons", "Show Codex", "Brings the Codex app to the front."),
    Setting("show_claude", "Buttons", "Show Claude", "Brings the Claude app to the front."),
    Setting("refresh", "Buttons", "Refresh", "Redraws the dropdown."),
]

DEFAULTS: dict[str, bool] = {setting.key: True for setting in SETTINGS}


def settings_file() -> Path:
    return Path.home() / ".config/coding-agent-status-bar/settings.json"


def load_settings() -> dict[str, bool]:
    """Saved settings, with defaults for anything missing or unreadable."""
    try:
        saved = json.loads(settings_file().read_text())
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    return {
        key: saved[key] if isinstance(saved.get(key), bool) else default
        for key, default in DEFAULTS.items()
    }


def save_settings(settings: dict[str, bool]) -> None:
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(settings, indent=2))
    os.replace(temporary, path)


def visible_states(
    settings: dict[str, bool],
    state: Optional[State],
    codex: Optional[HookState],
    claude: Optional[HookState],
) -> tuple[Optional[State], Optional[HookState], Optional[HookState]]:
    """The status without what's turned off in Settings, as if those apps weren't running."""

    def visible_hooks(hooks: Optional[HookState], app: str) -> Optional[HookState]:
        if not settings[app]:
            return None
        if hooks is not None and hooks.usage is not None and not settings[f"{app}_usage"]:
            return replace(hooks, usage=None)
        return hooks

    return (
        state if settings["opencode"] else None,
        visible_hooks(codex, "codex"),
        visible_hooks(claude, "claude"),
    )
