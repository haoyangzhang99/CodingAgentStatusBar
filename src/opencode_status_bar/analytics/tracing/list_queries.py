"""List query methods for TracingDataService.

Contains paginated list methods for sessions, traces, delegations.
"""

from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING



if TYPE_CHECKING:
    import duckdb


class ListQueriesMixin:
    """Mixin providing list query methods for TracingDataService.

    Requires _conn property and _paginate helper method.
    """

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get database connection (implemented by main class)."""
        raise NotImplementedError

    def _paginate(
        self,
        data: list,
        page: int = 1,
        per_page: int = 50,
        total: Optional[int] = None,
    ) -> dict:
        raise NotImplementedError

    def get_sessions_list(
        self,
        days: int = 30,
        limit: int = 100,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
    ) -> dict:
        """Get paginated list of sessions.

        Args:
            days: Filter sessions from last N days
            limit: Maximum total results
            page: Page number (1-based)
            per_page: Results per page
            search: Optional search query for title/directory

        Returns:
            Dict with data, meta (pagination info)
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            offset = (page - 1) * per_page
            per_page = min(per_page, 200)

            # Build query with optional search
            if search:
                search_pattern = f"%{search}%"
                count_result = self._conn.execute(
                    """
                    SELECT COUNT(*) FROM sessions
                    WHERE created_at >= ?
                      AND (title LIKE ? OR directory LIKE ?)
                    """,
                    [start_date, search_pattern, search_pattern],
                ).fetchone()
                total = min(count_result[0] if count_result else 0, limit)

                rows = self._conn.execute(
                    """
                    SELECT id, title, directory, created_at, updated_at
                    FROM sessions
                    WHERE created_at >= ?
                      AND (title LIKE ? OR directory LIKE ?)
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    [start_date, search_pattern, search_pattern, per_page, offset],
                ).fetchall()
            else:
                count_result = self._conn.execute(
                    """
                    SELECT COUNT(*) FROM sessions
                    WHERE created_at >= ?
                    """,
                    [start_date],
                ).fetchone()
                total = min(count_result[0] if count_result else 0, limit)

                rows = self._conn.execute(
                    """
                    SELECT id, title, directory, created_at, updated_at
                    FROM sessions
                    WHERE created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    [start_date, per_page, offset],
                ).fetchall()

            sessions = [
                {
                    "id": row[0],
                    "title": row[1],
                    "directory": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None,
                }
                for row in rows
            ]

            return self._paginate(sessions, page, per_page, total)

        except Exception:
            return self._paginate([], page, per_page, 0)

    def get_traces_list(
        self,
        days: int = 30,
        limit: int = 500,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """Get paginated list of agent traces.

        Args:
            days: Filter traces from last N days
            limit: Maximum total results
            page: Page number (1-based)
            per_page: Results per page

        Returns:
            Dict with data, meta (pagination info)
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            offset = (page - 1) * per_page
            per_page = min(per_page, 200)

            count_result = self._conn.execute(
                """
                SELECT COUNT(*) FROM agent_traces
                WHERE started_at >= ?
                """,
                [start_date],
            ).fetchone()
            total = min(count_result[0] if count_result else 0, limit)

            rows = self._conn.execute(
                """
                SELECT 
                    trace_id, session_id, parent_trace_id,
                    parent_agent, subagent_type,
                    started_at, ended_at, duration_ms,
                    tokens_in, tokens_out, status,
                    prompt_input, prompt_output
                FROM agent_traces
                WHERE started_at >= ?
                ORDER BY started_at DESC
                LIMIT ? OFFSET ?
                """,
                [start_date, per_page, offset],
            ).fetchall()

            traces = [
                {
                    "trace_id": row[0],
                    "session_id": row[1],
                    "parent_trace_id": row[2],
                    "parent_agent": row[3],
                    "subagent_type": row[4],
                    "started_at": row[5].isoformat() if row[5] else None,
                    "ended_at": row[6].isoformat() if row[6] else None,
                    "duration_ms": row[7],
                    "tokens_in": row[8],
                    "tokens_out": row[9],
                    "status": row[10],
                    "prompt_input": row[11],
                    "prompt_output": row[12],
                }
                for row in rows
            ]

            return self._paginate(traces, page, per_page, total)

        except Exception:
            return self._paginate([], page, per_page, 0)

    def get_delegations_list(
        self,
        days: int = 30,
        limit: int = 1000,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """Get paginated list of delegations.

        Args:
            days: Filter delegations from last N days
            limit: Maximum total results
            page: Page number (1-based)
            per_page: Results per page

        Returns:
            Dict with data, meta (pagination info)
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            offset = (page - 1) * per_page
            per_page = min(per_page, 200)

            count_result = self._conn.execute(
                """
                SELECT COUNT(*) FROM delegations
                WHERE created_at >= ?
                """,
                [start_date],
            ).fetchone()
            total = min(count_result[0] if count_result else 0, limit)

            rows = self._conn.execute(
                """
                SELECT 
                    id, session_id, parent_agent, child_agent,
                    child_session_id, created_at
                FROM delegations
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                [start_date, per_page, offset],
            ).fetchall()

            delegations = [
                {
                    "id": row[0],
                    "parent_session_id": row[1],
                    "parent_agent": row[2],
                    "child_agent": row[3],
                    "child_session_id": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                for row in rows
            ]

            return self._paginate(delegations, page, per_page, total)

        except Exception:
            return self._paginate([], page, per_page, 0)

    def search_sessions(self, query: str, limit: int = 20) -> list[dict]:
        """Search sessions by title or directory.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching session dicts
        """
        try:
            search_pattern = f"%{query}%"
            rows = self._conn.execute(
                """
                SELECT 
                    s.id, s.title, s.directory, s.created_at, s.updated_at,
                    (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count,
                    (SELECT SUM(tokens_input + tokens_output) FROM messages WHERE session_id = s.id) as total_tokens
                FROM sessions s
                WHERE s.title LIKE ? OR s.directory LIKE ?
                ORDER BY s.created_at DESC
                LIMIT ?
                """,
                [search_pattern, search_pattern, limit],
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "directory": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None,
                    "message_count": row[5] or 0,
                    "total_tokens": row[6] or 0,
                }
                for row in rows
            ]

        except Exception:
            return []
