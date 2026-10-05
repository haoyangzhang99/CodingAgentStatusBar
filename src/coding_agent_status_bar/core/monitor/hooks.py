"""Read the status files written by the Codex and Claude Code hooks in integrations/."""

import json
import math
import os
import time
from pathlib import Path

from ..models import Agent, HookState, SessionStatus, Tool

CODEX_BUNDLE_ID = "com.openai.codex"
CLAUDE_BUNDLE_ID = "com.anthropic.claudefordesktop"
# Finished sessions show as Done for a minute, like OpenCode sessions.
DONE_RETENTION = 60_000
# Some turns end without an event, so a session working this long without one is idle.
STALE_BUSY = 15 * 60_000


def app_running(bundle_id: str) -> bool:
    """Whether the desktop app with this bundle ID is open."""
    try:
        import AppKit

        return bool(
            AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)
        )
    except Exception:
        return False


def read_codex_state() -> HookState:
    return read_hook_state("codex", CODEX_BUNDLE_ID, "Codex")


def read_claude_state() -> HookState:
    return read_hook_state("claude", CLAUDE_BUNDLE_ID, "Claude Code")


def read_hook_state(folder: str, bundle_id: str, name: str) -> HookState:
    """The app runs if its desktop app is open or a session's process is alive."""
    now = time.time() * 1000
    live = False
    recent: list[tuple[float, Agent]] = []
    for path in (Path.home() / ".config/coding-agent-status-bar" / folder).glob("*.json"):
        try:
            data = json.loads(path.read_text())
            pid, updated, directory = data["pid"], data["updated"], data["directory"]
            status, permission = data["status"], data["permission"]
            # Codex can't report questions, so its files have no "question".
            question = data.get("question", False)
            if (
                data["version"] != 1
                or type(pid) is not int
                or pid <= 0
                or type(updated) not in (int, float)
                or not math.isfinite(updated)
                or not isinstance(directory, str)
                or status not in ("ready", "busy", "idle")
                or type(permission) is not bool
                or type(question) is not bool
            ):
                continue
            # Sessions of a process that has exited are over.
            os.kill(pid, 0)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        live = True
        age = max(0, now - updated)
        # Waiting for you can take as long as you're away; working can't.
        if status == "busy" and not (permission or question) and age > STALE_BUSY:
            status = "idle"
        if status == "ready" or (status == "idle" and age > DONE_RETENTION):
            continue
        recent.append((updated, Agent(
            id=path.stem,
            title=os.path.basename(directory) or name,
            dir=os.path.basename(directory),
            full_dir=directory,
            status=SessionStatus.BUSY if status == "busy" else SessionStatus.IDLE,
            tools=[Tool(name="Approval required", permission_pending=True)] if permission else [],
            has_pending_ask_user=question,
            ask_user_title=f"{name} needs your answer" if question else "",
        )))
    recent.sort(key=lambda item: item[0], reverse=True)
    return HookState(
        running=live or app_running(bundle_id),
        sessions=[agent for _, agent in recent],
    )
