"""Read subscription usage: Codex's from its own session files, and Claude's from the file
that integrations/coding-agent-status-bar-claude.py writes as Claude Code's status line.

Codex session files also hold conversations. Only their usage records are parsed, and nothing
else from them is kept.
"""

import json
import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import Usage, UsageLimit

# Codex files sessions by the day they started, and a resumed session stays in that folder.
CODEX_DAYS = 30
# Most session files read per check. Codex also rewrites old sessions without adding readings,
# so the newest reading isn't always in the latest file changed.
CODEX_MAX_FILES = 20
# Bytes read from the end of a session file, trying the larger size if the smaller has no record.
CODEX_TAILS = (256 * 1024, 4 * 1024 * 1024)
CLAUDE_LIMITS = {"five_hour": "5-hour", "seven_day": "Weekly"}

# Session file path -> ((modified time, size), latest record), so unchanged files aren't reread.
_codex_tails: dict[str, tuple[tuple[int, int], Optional[tuple[float, dict]]]] = {}


def is_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)  # type: ignore[arg-type]


def window_name(minutes: int) -> str:
    if minutes == 7 * 24 * 60:
        return "Weekly"
    if minutes % (24 * 60) == 0:
        return f"{minutes // (24 * 60)}-day"
    if minutes % 60 == 0:
        return f"{minutes // 60}-hour"
    return f"{minutes}-minute"


def make_limit(name: str, used: object, resets_at: object, now: float) -> Optional[UsageLimit]:
    if not is_number(used):
        return None
    resets = resets_at if is_number(resets_at) else 0
    if 0 < resets <= now:  # type: ignore[operator]
        return UsageLimit(name, 100, resets, reset=True)  # type: ignore[arg-type]
    # Round down, so a limit that is nearly out never shows as more than it has.
    left = math.floor(min(100.0, max(0.0, 100 - used)))  # type: ignore[operator]
    return UsageLimit(name, left, resets)  # type: ignore[arg-type]


# --- Codex -------------------------------------------------------------------------------


def newest_folders(path: Path, depth: int, count: int) -> list[Path]:
    """The `count` newest folders `depth` levels below path, by name (YYYY/MM/DD)."""
    if depth == 0:
        return [path]
    try:
        names = sorted((e.name for e in os.scandir(path) if e.is_dir()), reverse=True)
    except OSError:
        return []
    found: list[Path] = []
    for name in names:
        found += newest_folders(path / name, depth - 1, count - len(found))
        if len(found) >= count:
            break
    return found


def latest_codex_record(path: str, size: int) -> Optional[tuple[float, dict]]:
    """(Unix time, rate limits) of the last usage record in a Codex session file."""
    for tail in CODEX_TAILS:
        start = max(0, size - tail)
        try:
            with open(path, "rb") as file:
                file.seek(start)
                lines = file.read(size - start).split(b"\n")
        except OSError:
            return None
        if start > 0:
            lines = lines[1:]  # Starts mid-line
        for line in reversed(lines):
            if b'"token_count"' not in line or b'"rate_limits"' not in line:
                continue
            try:
                record = json.loads(line)
                payload = record["payload"]
                limits = payload["rate_limits"]
                if payload["type"] != "token_count" or not isinstance(limits, dict):
                    continue
                # Other limit IDs are for individual models, not the plan.
                if limits.get("limit_id") not in (None, "codex"):
                    continue
                return datetime.fromisoformat(record["timestamp"]).timestamp(), limits
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        if start == 0:
            break
    return None


def read_codex_usage(now: Optional[float] = None) -> Optional[Usage]:
    """The newest usage reading in Codex's recent session files, or None."""
    now = time.time() if now is None else now
    files = []
    for folder in newest_folders(Path.home() / ".codex" / "sessions", 3, CODEX_DAYS):
        try:
            for entry in os.scandir(folder):
                if entry.name.startswith("rollout-") and entry.name.endswith(".jsonl"):
                    stat = entry.stat()
                    files.append((stat.st_mtime_ns, stat.st_size, entry.path))
        except OSError:
            continue
    files.sort(reverse=True)

    newest = None
    seen = {}
    for modified, size, path in files[:CODEX_MAX_FILES]:
        # A file can't hold a reading newer than its last change, so the rest are older.
        if newest and modified / 1e9 < newest[0]:
            break
        cached = _codex_tails.get(path)
        record = cached[1] if cached and cached[0] == (modified, size) else (
            latest_codex_record(path, size)
        )
        seen[path] = ((modified, size), record)
        if record and (newest is None or record[0] > newest[0]):
            newest = record
    _codex_tails.clear()
    _codex_tails.update(seen)
    if newest is None:
        return None

    updated, limits = newest
    windows = []
    for key in ("primary", "secondary"):
        window = limits.get(key)
        if not isinstance(window, dict):
            continue
        minutes = window.get("window_minutes")
        if type(minutes) is not int or minutes <= 0:
            continue
        limit = make_limit(window_name(minutes), window.get("used_percent"), window.get("resets_at"), now)
        if limit:
            windows.append(limit)
    return Usage(windows, updated) if windows else None


# --- Claude ------------------------------------------------------------------------------


def read_claude_usage(now: Optional[float] = None) -> Optional[Usage]:
    """The usage that Claude Code's status line last saved, or None."""
    now = time.time() if now is None else now
    path = Path.home() / ".config/coding-agent-status-bar/claude-usage.json"
    try:
        data = json.loads(path.read_text())
        updated, windows = data["updated"], data["limits"]
        if data["version"] != 1 or not is_number(updated) or not isinstance(windows, dict):
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    limits = []
    for key, name in CLAUDE_LIMITS.items():
        window = windows.get(key)
        if isinstance(window, dict):
            limit = make_limit(name, window.get("used_percentage"), window.get("resets_at"), now)
            if limit:
                limits.append(limit)
    return Usage(limits, updated / 1000) if limits else None
