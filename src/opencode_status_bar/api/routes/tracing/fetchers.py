"""
Tracing Fetchers - Database fetching functions for tracing routes.
"""

import re
from typing import Any


# =============================================================================
# Trace Fetchers
# =============================================================================


def fetch_root_traces(
    conn: Any, start_date: Any, limit: int = 80, offset: int = 0
) -> list:
    return conn.execute(
        """
        SELECT 
            t.trace_id,
            t.session_id,
            t.parent_agent,
            t.subagent_type,
            t.started_at,
            t.ended_at,
            t.duration_ms,
            t.tokens_in,
            t.tokens_out,
            t.status,
            t.prompt_input,
            s.title,
            s.directory,
            t.child_session_id
        FROM agent_traces t
        LEFT JOIN sessions s ON t.session_id = s.id
        WHERE t.parent_trace_id IS NULL
          AND t.trace_id LIKE 'root_%'
          AND t.trace_id NOT LIKE '%_seg%'
          AND t.started_at >= ?
        ORDER BY t.started_at DESC
        LIMIT ?
        OFFSET ?
        """,
        [start_date, limit, offset],
    ).fetchall()


def fetch_segment_traces(conn: Any, start_date: Any) -> dict:
    """Fetch segment traces and group them by session_id.

    Args:
        conn: Database connection
        start_date: Start date filter for traces

    Returns:
        Dictionary mapping session_id to list of segment rows
    """
    segment_rows = conn.execute(
        """
        SELECT 
            t.trace_id,
            t.session_id,
            t.parent_agent,
            t.subagent_type,
            t.started_at,
            t.ended_at,
            t.duration_ms,
            t.tokens_in,
            t.tokens_out,
            t.status,
            t.prompt_input,
            t.child_session_id
        FROM agent_traces t
        WHERE t.trace_id LIKE 'root_%_seg%'
          AND t.started_at >= ?
        ORDER BY t.started_at ASC
        """,
        [start_date],
    ).fetchall()

    segments_by_session: dict = {}
    for row in segment_rows:
        session_id = row[1]
        if session_id not in segments_by_session:
            segments_by_session[session_id] = []
        segments_by_session[session_id].append(row)

    return segments_by_session


def fetch_child_traces(conn: Any, start_date: Any) -> list:
    """Fetch child traces (delegations) from database.

    Args:
        conn: Database connection
        start_date: Start date filter for traces

    Returns:
        List of child trace rows
    """
    return conn.execute(
        """
        SELECT 
            t.trace_id,
            t.session_id,
            t.parent_trace_id,
            t.parent_agent,
            t.subagent_type,
            t.started_at,
            t.ended_at,
            t.duration_ms,
            t.tokens_in,
            t.tokens_out,
            t.status,
            t.prompt_input,
            t.prompt_output,
            t.child_session_id
        FROM agent_traces t
        WHERE t.parent_trace_id IS NOT NULL
          AND t.trace_id NOT LIKE 'root_%'
          AND t.started_at >= ?
        ORDER BY t.started_at ASC
        """,
        [start_date],
    ).fetchall()


def fetch_messages_for_exchanges(conn: Any, root_session_ids: set) -> list:
    """Fetch all messages for root sessions to build exchanges.

    Args:
        conn: Database connection
        root_session_ids: Set of root session IDs

    Returns:
        List of message rows
    """
    if not root_session_ids:
        return []

    # Placeholders are just "?" markers for parameterized query - safe
    placeholders = ",".join(["?" for _ in root_session_ids])
    return conn.execute(
        f"""
        SELECT 
            m.id,
            m.session_id,
            m.created_at,
            m.role,
            m.agent,
            (SELECT p.content FROM parts p 
             WHERE p.message_id = m.id AND p.part_type = 'text' 
             LIMIT 1) as content,
            m.tokens_input,
            m.tokens_output,
            m.tokens_cache_read,
            m.tokens_cache_write
        FROM messages m
        WHERE m.session_id IN ({placeholders})
        ORDER BY m.session_id, m.created_at ASC
        """,  # nosec B608
        list(root_session_ids),
    ).fetchall()


def fetch_subagent_tokens(conn: Any, start_date: Any) -> tuple[dict, list]:
    """Fetch subagent sessions and their token counts.

    Args:
        conn: Database connection
        start_date: Start date filter

    Returns:
        Tuple of (subagent_tokens dict, subagent_by_time list)
    """
    subagent_sessions = conn.execute(
        """
        SELECT 
            id,
            title,
            created_at
        FROM sessions
        WHERE title LIKE '%subagent)%'
          AND created_at >= ?
        ORDER BY created_at ASC
        """,
        [start_date],
    ).fetchall()

    subagent_tokens: dict = {}
    if subagent_sessions:
        subagent_ids = [s[0] for s in subagent_sessions]
        # Placeholders are just "?" markers for parameterized query - safe
        sa_placeholders = ",".join(["?" for _ in subagent_ids])
        token_rows = conn.execute(
            f"""
            SELECT 
                session_id,
                COALESCE(SUM(tokens_input), 0) as tokens_in,
                COALESCE(SUM(tokens_output), 0) as tokens_out,
                COALESCE(SUM(tokens_cache_read), 0) as cache_read
            FROM messages
            WHERE session_id IN ({sa_placeholders})
            GROUP BY session_id
            """,  # nosec B608
            subagent_ids,
        ).fetchall()
        for trow in token_rows:
            subagent_tokens[trow[0]] = {
                "tokens_in": trow[1],
                "tokens_out": trow[2],
                "cache_read": trow[3],
            }

    # Build index of subagent sessions by (timestamp, agent_type)
    subagent_by_time: list = []
    for sa_row in subagent_sessions:
        sa_id, sa_title, sa_created = sa_row
        match = re.search(r"@(\w+)\s+subagent", sa_title or "")
        if match and sa_created:
            agent_type = match.group(1)
            subagent_by_time.append(
                {
                    "session_id": sa_id,
                    "agent_type": agent_type,
                    "created_at": sa_created,
                    "tokens": subagent_tokens.get(sa_id, {}),
                }
            )

    return subagent_tokens, subagent_by_time


def fetch_tokens_by_session(conn: Any, root_session_ids: set) -> dict:
    """Fetch aggregated tokens per session.

    Args:
        conn: Database connection
        root_session_ids: Set of root session IDs

    Returns:
        Dictionary mapping session_id to token counts
    """
    if not root_session_ids:
        return {}

    # Placeholders are just "?" markers for parameterized query - safe
    placeholders = ",".join(["?" for _ in root_session_ids])
    token_rows = conn.execute(
        f"""
        SELECT 
            session_id,
            COALESCE(SUM(tokens_input), 0) as tokens_in,
            COALESCE(SUM(tokens_output), 0) as tokens_out,
            COALESCE(SUM(tokens_cache_read), 0) as cache_read,
            COALESCE(SUM(tokens_cache_write), 0) as cache_write
        FROM messages
        WHERE session_id IN ({placeholders})
        GROUP BY session_id
        """,  # nosec B608
        list(root_session_ids),
    ).fetchall()

    tokens_by_session: dict = {}
    for trow in token_rows:
        tokens_by_session[trow[0]] = {
            "tokens_in": trow[1],
            "tokens_out": trow[2],
            "cache_read": trow[3],
            "cache_write": trow[4],
        }

    return tokens_by_session


def get_initial_agents(conn: Any, root_session_ids: set) -> dict:
    """Get initial agent type from root traces.

    Args:
        conn: Database connection
        root_session_ids: Set of root session IDs

    Returns:
        Dictionary mapping session_id to initial agent type
    """
    if not root_session_ids:
        return {}

    # Placeholders are just "?" markers for parameterized query - safe
    placeholders = ",".join(["?" for _ in root_session_ids])
    root_agent_rows = conn.execute(
        f"""
        SELECT session_id, subagent_type, started_at
        FROM agent_traces
        WHERE session_id IN ({placeholders})
          AND trace_id LIKE 'root_%'
          AND trace_id NOT LIKE '%_seg%'
        """,  # nosec B608
        list(root_session_ids),
    ).fetchall()

    initial_agent: dict = {}
    for arow in root_agent_rows:
        initial_agent[arow[0]] = arow[1]

    return initial_agent
