"""Skills usage data loader."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from ..db import AnalyticsDB
from ...utils.logger import info
from ...utils.datetime import ms_to_datetime


def load_skills(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load skill usage from skill tool invocations."""
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_days)
    skill_id = 0
    skills = []

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        for part_file in msg_dir.glob("*.json"):
            try:
                with open(part_file) as f:
                    data = json.load(f)

                if data.get("tool") != "skill":
                    continue

                state = data.get("state", {})
                skill_name = state.get("input", {}).get("name")
                if not skill_name:
                    continue

                time_data = data.get("time", {})
                start_ts = time_data.get("start")
                loaded_at = ms_to_datetime(start_ts)
                if loaded_at and loaded_at < cutoff:
                    continue

                skill_id += 1
                skills.append(
                    {
                        "id": skill_id,
                        "message_id": data.get("messageID"),
                        "session_id": data.get("sessionID"),
                        "skill_name": skill_name,
                        "loaded_at": loaded_at,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue

    if not skills:
        info("No skills found")
        return 0

    for s in skills:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO skills
                (id, message_id, session_id, skill_name, loaded_at)
                VALUES (?, ?, ?, ?, ?)""",
                [
                    s["id"],
                    s["message_id"],
                    s["session_id"],
                    s["skill_name"],
                    s["loaded_at"],
                ],
            )
        except Exception:  # Intentional catch-all: skip individual insert failures
            continue

    row = conn.execute("SELECT COUNT(*) FROM skills").fetchone()
    count = row[0] if row else 0
    return count
