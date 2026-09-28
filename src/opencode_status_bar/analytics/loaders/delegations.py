"""Delegations (agent task handoffs) data loader."""

import json
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path

from ..db import AnalyticsDB
from ...utils.logger import info
from ...utils.datetime import ms_to_datetime
from .utils import collect_recent_part_files, chunked


def load_delegations(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load agent delegations from task tool invocations.

    Uses a chunked approach for performance without freezing:
    1. Python scans directories and filters by mtime (fast)
    2. Process files in chunks to avoid memory/CPU spikes
    """
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    # Phase 1: Collect recent files (mtime filter)
    recent_files = collect_recent_part_files(part_dir, max_days)
    if not recent_files:
        info("No recent part files found")
        return 0

    info(f"Scanning {len(recent_files)} recent part files for delegations")

    cutoff = datetime.now() - timedelta(days=max_days)
    delegations: list[dict] = []

    # Phase 2: Process files in chunks (avoid CPU spikes)
    chunk_size = 500
    for chunk in chunked(recent_files, chunk_size):
        for file_path in chunk:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)

                if data.get("tool") != "task":
                    continue

                state = data.get("state", {})
                input_data = state.get("input", {})
                subagent_type = input_data.get("subagent_type")
                if not subagent_type:
                    continue

                # Extract timing
                time_data = state.get("time", {})
                start_ts = time_data.get("start")
                started_at = ms_to_datetime(start_ts)

                # Skip old entries
                if started_at and started_at < cutoff:
                    continue

                metadata = state.get("metadata", {})
                delegations.append(
                    {
                        "id": data.get("id"),
                        "message_id": data.get("messageID"),
                        "session_id": data.get("sessionID"),
                        "child_agent": subagent_type,
                        "child_session_id": metadata.get("sessionId"),
                        "created_at": started_at,
                    }
                )

            except (json.JSONDecodeError, OSError):
                continue

        # Small sleep between chunks to let UI breathe
        time_module.sleep(0.01)

    if not delegations:
        info("No delegations found")
        return 0

    # Batch lookup: get all parent agents in one query
    message_ids = [d["message_id"] for d in delegations if d.get("message_id")]
    parent_agents: dict[str, str] = {}
    if message_ids:
        try:
            # Placeholders are just "?" markers for parameterized query - safe
            placeholders = ",".join(["?" for _ in message_ids])
            results = conn.execute(
                f"SELECT id, agent FROM messages WHERE id IN ({placeholders})",  # nosec B608
                message_ids,
            ).fetchall()
            parent_agents = {r[0]: r[1] for r in results if r[1]}
        except Exception:
            pass  # nosec B110 - parent_agents enrichment is optional

    # Batch insert delegations
    for d in delegations:
        try:
            msg_id = d.get("message_id")
            parent_agent = parent_agents.get(msg_id) if msg_id else None
            conn.execute(
                """INSERT OR REPLACE INTO delegations
                (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    d["id"],
                    d["message_id"],
                    d["session_id"],
                    parent_agent,
                    d["child_agent"],
                    d["child_session_id"],
                    d["created_at"],
                ],
            )
        except Exception:  # Intentional catch-all: skip individual insert failures
            continue

    row = conn.execute("SELECT COUNT(*) FROM delegations").fetchone()
    count = row[0] if row else 0
    return count
