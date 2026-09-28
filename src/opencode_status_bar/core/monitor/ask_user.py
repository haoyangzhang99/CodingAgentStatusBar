"""
Ask user detection for OpenCode sessions.

Handles detection of pending notify_ask_user notifications.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ...utils.settings import get_settings


# Storage path for OpenCode session files (can be overridden for testing)
OPENCODE_STORAGE_PATH: Path = Path.home() / ".local/share/opencode/storage"


@dataclass
class AskUserResult:
    """Result of checking for pending ask_user notifications"""

    has_pending: bool
    title: str = ""
    question: str = ""
    options: list[str] = field(default_factory=list)
    repo: str = ""
    agent: str = ""
    branch: str = ""
    urgency: str = "normal"


def _find_latest_notify_ask_user(
    message_dir: Path, part_dir: Path, cutoff_time: float
) -> tuple[int, dict, list[tuple[int, str, str]]]:
    """Scan messages for the latest notify_ask_user call.

    Args:
        message_dir: Directory containing message files
        part_dir: Directory containing part files
        cutoff_time: Only consider files modified after this timestamp

    Returns:
        (notify_timestamp, notify_input, recent_messages)
        where notify_input is the full input dict from the notify_ask_user call
        and recent_messages is a list of (msg_time, msg_id, role)
    """
    notify_timestamp = 0
    notify_input: dict = {}
    recent_messages: list[tuple[int, str, str]] = []

    for msg_file in message_dir.glob("msg_*.json"):
        # Skip files older than cutoff (fast mtime check, no file read)
        if msg_file.stat().st_mtime < cutoff_time:
            continue

        try:
            data = json.loads(msg_file.read_text())
        except (json.JSONDecodeError, IOError):
            continue

        msg_id = data.get("id", "")
        msg_time = data.get("time", {}).get("created", 0)
        role = data.get("role", "")
        recent_messages.append((msg_time, msg_id, role))

        # Check part files for notify_ask_user
        msg_part_dir = part_dir / msg_id
        if not msg_part_dir.exists():
            continue

        for prt_file in msg_part_dir.glob("prt_*.json"):
            if prt_file.stat().st_mtime < cutoff_time:
                continue

            try:
                part_data = json.loads(prt_file.read_text())
            except (json.JSONDecodeError, IOError):
                continue

            if (
                part_data.get("type") == "tool"
                and part_data.get("tool") == "notify_ask_user"
                and part_data.get("state", {}).get("status") == "completed"
            ):
                part_time = (
                    part_data.get("state", {}).get("time", {}).get("start", msg_time)
                )
                if part_time > notify_timestamp:
                    notify_timestamp = part_time
                    notify_input = part_data.get("state", {}).get("input", {})

    return notify_timestamp, notify_input, recent_messages


def _has_activity_after_notify(
    notify_timestamp: int,
    recent_messages: list[tuple[int, str, str]],
    part_dir: Path,
) -> bool:
    """Check if there's user activity after the notify_ask_user call.

    Returns True if user has responded (user message or other tool call found).
    """
    for msg_time, msg_id, role in recent_messages:
        if msg_time <= notify_timestamp:
            continue

        # User message after notify = user responded
        if role == "user":
            return True

        # Check for non-notify tool calls (indicates agent resumed)
        msg_part_dir = part_dir / msg_id
        if not msg_part_dir.exists():
            continue

        for prt_file in msg_part_dir.glob("prt_*.json"):
            try:
                part_data = json.loads(prt_file.read_text())
            except (json.JSONDecodeError, IOError):
                continue

            if part_data.get("type") == "tool":
                tool_name = part_data.get("tool", "")
                if tool_name and tool_name != "notify_ask_user":
                    return True

    return False


def check_pending_ask_user_from_disk(
    session_id: str,
    storage_path: Optional[Path] = None,
) -> AskUserResult:
    """Check if there's a pending notify_ask_user by scanning RECENT session files.

    Optimized for performance:
    - Only scans files modified within the time threshold (using file mtime)
    - Skips old files without reading their content
    - Returns quickly if no recent activity

    Note: Zombie sessions are filtered by the port cache mechanism in app.py,
    not by this function. This function only checks for pending ask_user
    notifications within the configured timeout.

    Args:
        session_id: The session ID to check
        storage_path: Override for OPENCODE_STORAGE_PATH (useful for testing)

    Returns:
        AskUserResult with has_pending and all ask_user fields
    """
    storage = storage_path or OPENCODE_STORAGE_PATH
    message_dir = storage / "message" / session_id
    part_dir = storage / "part"

    if not message_dir.exists():
        return AskUserResult(has_pending=False)

    # Use configured timeout
    settings = get_settings()
    cutoff_time = time.time() - settings.ask_user_timeout

    try:
        notify_timestamp, notify_input, recent_messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )
    except (
        Exception
    ):  # Intentional catch-all: file scanning failures return safe default
        return AskUserResult(has_pending=False)

    # No recent notify_ask_user found
    if notify_timestamp == 0:
        return AskUserResult(has_pending=False)

    # Check if user has responded
    if _has_activity_after_notify(notify_timestamp, recent_messages, part_dir):
        return AskUserResult(has_pending=False)

    # notify_ask_user found with no activity after -> pending
    # Extract all fields from input
    return AskUserResult(
        has_pending=True,
        title=notify_input.get("title", ""),
        question=notify_input.get("question", ""),
        options=notify_input.get("options", []) or [],
        repo=notify_input.get("repo", ""),
        agent=notify_input.get("agent", ""),
        branch=notify_input.get("branch", ""),
        urgency=notify_input.get("urgency", "normal"),
    )
