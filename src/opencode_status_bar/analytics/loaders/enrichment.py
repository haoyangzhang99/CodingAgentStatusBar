"""Session enrichment and metadata helpers."""

import json
from pathlib import Path
from typing import Optional

from ..db import AnalyticsDB
from ...utils.logger import info, error


def get_session_agent(message_dir: Path, session_id: str) -> Optional[str]:
    """Get the agent type for a session from its messages.

    OpenCode stores the agent type in the 'agent' field of message JSON files.
    This is the responding agent (e.g., 'roadmap', 'coordinateur', 'executeur').

    Args:
        message_dir: Path to OpenCode message storage
        session_id: The session ID to find messages for

    Returns:
        The agent name (e.g., 'roadmap', 'coordinateur'), or None if not found
    """
    session_msg_dir = message_dir / session_id
    if not session_msg_dir.exists():
        return None

    # Find the first message with an 'agent' field
    for msg_file in session_msg_dir.glob("*.json"):
        try:
            with open(msg_file) as f:
                data = json.load(f)
            agent = data.get("agent")
            if agent:
                return agent
        except (json.JSONDecodeError, OSError):
            continue

    return None


def get_first_user_message(message_dir: Path, session_id: str) -> Optional[str]:
    """Get the first user message content for a session.

    Args:
        message_dir: Path to OpenCode message storage
        session_id: The session ID to find messages for

    Returns:
        The first user message content, or None if not found
    """
    session_msg_dir = message_dir / session_id
    if not session_msg_dir.exists():
        return None

    # Find all message files and sort by timestamp
    messages = []
    for msg_file in session_msg_dir.glob("*.json"):
        try:
            with open(msg_file) as f:
                data = json.load(f)
            if data.get("role") == "user":
                time_data = data.get("time", {})
                created = time_data.get("created", 0)
                messages.append((created, data))
        except (json.JSONDecodeError, OSError):
            continue

    if not messages:
        return None

    # Sort by creation time and get the first
    messages.sort(key=lambda x: x[0])
    first_msg = messages[0][1]

    # Extract content from summary (title + body if available)
    summary = first_msg.get("summary", {})
    title = summary.get("title", "")
    body = summary.get("body", "")

    if title and body:
        return f"{title}\n\n{body}"
    elif title:
        return title
    elif body:
        return body

    return "(No message content)"


def enrich_sessions_metadata(db: AnalyticsDB) -> int:
    """Enrich sessions with computed fields (Plan 36).

    Computes and fills:
    - is_root: FALSE if parent_id is set
    - project_name: basename of directory
    - ended_at: approximated from updated_at
    - duration_ms: computed from timestamps

    Returns:
        Number of sessions updated
    """
    conn = db.connect()
    updated = 0

    try:
        # Mark child sessions (is_root = FALSE)
        result = conn.execute("""
            UPDATE sessions 
            SET is_root = FALSE 
            WHERE parent_id IS NOT NULL AND (is_root = TRUE OR is_root IS NULL)
        """)
        updated += result.rowcount if hasattr(result, "rowcount") else 0

        # Extract project_name from directory (last path component)
        conn.execute("""
            UPDATE sessions 
            SET project_name = regexp_extract(directory, '[^/]+$')
            WHERE project_name IS NULL AND directory IS NOT NULL
        """)

        # Set ended_at from updated_at (approximation)
        conn.execute("""
            UPDATE sessions 
            SET ended_at = updated_at
            WHERE ended_at IS NULL AND updated_at IS NOT NULL
        """)

        # Calculate duration_ms from timestamps
        conn.execute("""
            UPDATE sessions 
            SET duration_ms = CAST(
                EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000 AS BIGINT
            )
            WHERE duration_ms IS NULL 
              AND updated_at IS NOT NULL 
              AND created_at IS NOT NULL
        """)

        # Count enriched sessions
        row = conn.execute("""
            SELECT COUNT(*) FROM sessions 
            WHERE project_name IS NOT NULL OR duration_ms IS NOT NULL
        """).fetchone()
        enriched: int = row[0] if row else 0

        info(f"Enriched {enriched} sessions with metadata")
        return enriched

    except Exception as e:
        error(f"Session enrichment failed: {e}")
        return 0
