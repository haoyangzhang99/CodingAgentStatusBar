"""File operations data loader."""

import json
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path

from ..db import AnalyticsDB
from ..path_matcher import DiffPathMatcher, DiffStats
from ...utils.logger import info
from ...utils.datetime import ms_to_datetime
from .utils import collect_recent_part_files, chunked


def load_file_operations(
    db: AnalyticsDB, storage_path: Path, max_days: int = 30
) -> int:
    """Load file operations from tool invocations.

    Extracts read, write, and edit operations from parts data.
    Uses chunked Python processing to avoid CPU spikes.

    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage
        max_days: Only load operations from the last N days

    Returns:
        Number of file operations loaded
    """
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    # Phase 1: Collect recent files (mtime filter)
    recent_files = collect_recent_part_files(part_dir, max_days)
    if not recent_files:
        info("No recent part files found for file operations")
        return 0

    info(f"Scanning {len(recent_files)} recent part files for file operations")

    cutoff = datetime.now() - timedelta(days=max_days)
    operations: list[dict] = []
    file_tools = {"read", "write", "edit"}

    # Phase 2: Process files in chunks (avoid CPU spikes)
    chunk_size = 500
    for chunk in chunked(recent_files, chunk_size):
        for file_path in chunk:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)

                tool_name = data.get("tool")
                if tool_name not in file_tools:
                    continue

                state = data.get("state", {})
                input_data = state.get("input", {})

                # Extract file path from tool input
                path = input_data.get("filePath") or input_data.get("path")
                if not path:
                    continue

                time_data = state.get("time", {})
                start_ts = time_data.get("start")
                timestamp = ms_to_datetime(start_ts)

                # Skip old entries
                if timestamp and timestamp < cutoff:
                    continue

                operations.append(
                    {
                        "id": data.get("id"),
                        "session_id": data.get("sessionID"),
                        "trace_id": None,
                        "operation": tool_name,
                        "file_path": path,
                        "timestamp": timestamp,
                        "risk_level": "normal",
                        "risk_reason": None,
                    }
                )

            except (json.JSONDecodeError, OSError):
                continue

        # Small sleep between chunks to let UI breathe
        time_module.sleep(0.01)

    if not operations:
        info("No file operations found")
        return 0

    for op in operations:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO file_operations
                (id, session_id, trace_id, operation, file_path, timestamp, risk_level, risk_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    op["id"],
                    op["session_id"],
                    op["trace_id"],
                    op["operation"],
                    op["file_path"],
                    op["timestamp"],
                    op["risk_level"],
                    op["risk_reason"],
                ],
            )
        except Exception:
            continue

    row = conn.execute("SELECT COUNT(*) FROM file_operations").fetchone()
    count = row[0] if row else 0

    enriched = enrich_file_operations_with_diff_stats(db, storage_path)
    if enriched > 0:
        info(f"Enriched {enriched} file operations with diff stats")

    return count


def enrich_file_operations_with_diff_stats(db: AnalyticsDB, storage_path: Path) -> int:
    """Enrich file_operations with per-file additions/deletions from session_diff JSON.

    Reads session_diff/{session_id}.json files and updates file_operations
    with additions/deletions counts for each file.

    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage

    Returns:
        Number of file operations enriched
    """
    conn = db.connect()
    diff_dir = storage_path / "session_diff"

    if not diff_dir.exists():
        return 0

    sessions_with_ops = conn.execute(
        "SELECT DISTINCT session_id FROM file_operations WHERE session_id IS NOT NULL"
    ).fetchall()
    session_ids = {row[0] for row in sessions_with_ops}

    if not session_ids:
        return 0

    enriched_count = 0

    for session_id in session_ids:
        diff_file = diff_dir / f"{session_id}.json"
        if not diff_file.exists():
            continue

        try:
            with open(diff_file, "r") as f:
                diff_data = json.load(f)

            if not isinstance(diff_data, list):
                continue

            diff_by_file: dict[str, DiffStats] = {}
            for item in diff_data:
                if isinstance(item, dict):
                    file_path = item.get("file")
                    if file_path:
                        diff_by_file[file_path] = DiffStats(
                            additions=item.get("additions", 0),
                            deletions=item.get("deletions", 0),
                        )

            if not diff_by_file:
                continue

            matcher = DiffPathMatcher(diff_by_file)

            file_ops = conn.execute(
                """SELECT id, file_path FROM file_operations 
                   WHERE session_id = ? AND operation IN ('write', 'edit')""",
                [session_id],
            ).fetchall()

            for op_id, op_file_path in file_ops:
                stats = matcher.match(op_file_path)
                if stats:
                    conn.execute(
                        """UPDATE file_operations 
                           SET additions = ?, deletions = ? 
                           WHERE id = ?""",
                        [stats["additions"], stats["deletions"], op_id],
                    )
                    enriched_count += 1

        except (json.JSONDecodeError, OSError):
            continue

    return enriched_count
