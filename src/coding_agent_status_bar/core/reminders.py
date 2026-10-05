"""Low-usage reminders.

A limit with less than LOW_USAGE percent left shows in the menu bar, such as "Codex: 8% left",
until you open the menu. After that only its yellow bar in the dropdown shows it, until that
limit resets. Dismissals are saved, so restarting the app doesn't show them again.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from .models import HookState, UsageLimit

# Reset times this close (in seconds) belong to the same window.
SAME_WINDOW = 600


def dismissed_file() -> Path:
    return Path.home() / ".config/coding-agent-status-bar/dismissed-reminders.json"


def low_limits(apps: dict[str, Optional[HookState]]) -> list[tuple[str, UsageLimit]]:
    """(app name, limit) for each low limit of an app that is running."""
    return [
        (name, limit)
        for name, state in apps.items()
        if state is not None and state.running and state.usage is not None
        for limit in state.usage.limits
        if limit.low
    ]


def is_dismissed(name: str, limit: UsageLimit, dismissed: list[dict]) -> bool:
    return any(
        entry["app"] == name
        and entry["limit"] == limit.name
        and abs(entry["resets_at"] - limit.resets_at) <= SAME_WINDOW
        for entry in dismissed
    )


def reminder_for(apps: dict[str, Optional[HookState]], dismissed: list[dict]) -> Optional[str]:
    """Menu bar text for the lowest limit not yet dismissed, or None."""
    pending = [(n, limit) for n, limit in low_limits(apps) if not is_dismissed(n, limit, dismissed)]
    if not pending:
        return None
    name, limit = min(pending, key=lambda item: item[1].left)
    return f"{name}: {limit.left}% left"


def dismiss(apps: dict[str, Optional[HookState]], dismissed: list[dict], now: float) -> bool:
    """Dismiss every reminder that would show; return whether there were any."""
    new = [
        {"app": name, "limit": limit.name, "resets_at": limit.resets_at}
        for name, limit in low_limits(apps)
        if not is_dismissed(name, limit, dismissed)
    ]
    if new:
        dismissed[:] = [entry for entry in dismissed if entry["resets_at"] > now] + new
    return bool(new)


def load_dismissed(now: Optional[float] = None) -> list[dict]:
    """Saved dismissals for limits that haven't reset yet."""
    now = time.time() if now is None else now
    try:
        entries = json.loads(dismissed_file().read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(entries, list):
        return []
    return [
        entry for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("app"), str)
        and isinstance(entry.get("limit"), str)
        and type(entry.get("resets_at")) in (int, float)
        and entry["resets_at"] > now
    ]


def save_dismissed(entries: list[dict]) -> None:
    path = dismissed_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(entries))
    os.replace(temporary, path)
