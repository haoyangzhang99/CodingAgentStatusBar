"""
Session-related queries.

Queries for sessions, session stats, and session token metrics.
"""

from datetime import datetime
from typing import Optional

from ..models import SessionStats, SessionTokenStats, TokenStats
from .base import BaseQueries


class SessionQueries(BaseQueries):
    """Queries related to sessions."""

    def _get_top_sessions(
        self, start_date: datetime, end_date: datetime, limit: int = 10
    ) -> list[SessionStats]:
        """Get top sessions by token usage."""
        results = self._conn.execute(
            """
            SELECT
                s.id,
                s.title,
                COUNT(m.id) as msg_count,
                COALESCE(SUM(m.tokens_input), 0) as total_input,
                COALESCE(SUM(m.tokens_output), 0) as total_output,
                COALESCE(SUM(m.tokens_reasoning), 0) as total_reasoning,
                COALESCE(SUM(m.tokens_cache_read), 0) as total_cache_read,
                COALESCE(SUM(m.tokens_cache_write), 0) as total_cache_write,
                EXTRACT(EPOCH FROM (MAX(m.created_at) - MIN(m.created_at))) / 60 as duration_min
            FROM sessions s
            JOIN messages m ON s.id = m.session_id
            WHERE s.created_at >= ? AND s.created_at <= ?
            GROUP BY s.id, s.title
            ORDER BY total_input + total_output DESC
            LIMIT ?
            """,
            [start_date, end_date, limit],
        ).fetchall()

        return [
            SessionStats(
                session_id=row[0],
                title=row[1] or "Untitled",
                message_count=row[2],
                tokens=TokenStats(
                    input=row[3],
                    output=row[4],
                    reasoning=row[5],
                    cache_read=row[6],
                    cache_write=row[7],
                ),
                duration_minutes=int(row[8] or 0),
            )
            for row in results
        ]

    def _get_session_token_stats(
        self, start_date: datetime, end_date: datetime
    ) -> Optional[SessionTokenStats]:
        """Get token statistics across sessions."""
        try:
            result = self._conn.execute(
                """
                SELECT 
                    COUNT(*) as sessions,
                    AVG(total_tokens) as avg_tokens,
                    MAX(total_tokens) as max_tokens,
                    MIN(CASE WHEN total_tokens > 0 THEN total_tokens END) as min_tokens,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_tokens) as median_tokens
                FROM (
                    SELECT session_id, SUM(tokens_input + tokens_output) as total_tokens
                    FROM messages
                    WHERE created_at >= ? AND created_at <= ?
                    GROUP BY session_id
                )
                """,
                [start_date, end_date],
            ).fetchone()

            if not result or result[0] == 0:
                return None

            return SessionTokenStats(
                total_sessions=result[0],
                avg_tokens=int(result[1] or 0),
                max_tokens=int(result[2] or 0),
                min_tokens=int(result[3] or 0),
                median_tokens=int(result[4] or 0),
            )
        except Exception:  # Intentional catch-all: query failures return None
            return None

    def _get_avg_session_duration(
        self, start_date: datetime, end_date: datetime
    ) -> float:
        """Get average session duration in minutes."""
        result = self._conn.execute(
            """
            SELECT AVG(duration_min) FROM (
                SELECT
                    s.id,
                    EXTRACT(EPOCH FROM (MAX(m.created_at) - MIN(m.created_at))) / 60 as duration_min
                FROM sessions s
                JOIN messages m ON s.id = m.session_id
                WHERE s.created_at >= ? AND s.created_at <= ?
                GROUP BY s.id
                HAVING COUNT(m.id) > 1
            )
            """,
            [start_date, end_date],
        ).fetchone()

        return float(result[0] or 0)

    def get_session_hierarchy(self, session_id: str) -> dict:
        """Get parent-child session hierarchy for a session."""
        try:
            # Get parent sessions (going up)
            parents: list = []
            current_id: Optional[str] = session_id
            while current_id:
                result = self._conn.execute(
                    "SELECT id, parent_id, title FROM sessions WHERE id = ?",
                    [current_id],
                ).fetchone()
                if result:
                    parents.insert(0, {"id": result[0], "title": result[2]})
                    current_id = result[1]
                else:
                    break

            # Get child sessions (going down)
            children = self._conn.execute(
                """
                SELECT id, title, parent_id FROM sessions
                WHERE parent_id = ?
                ORDER BY created_at
                """,
                [session_id],
            ).fetchall()

            return {
                "parents": parents,
                "current": session_id,
                "children": [{"id": row[0], "title": row[1]} for row in children],
            }
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty hierarchy
            return {"parents": [], "current": session_id, "children": []}
