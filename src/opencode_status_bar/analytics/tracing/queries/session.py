"""Session queries aggregator.

Provides a unified interface to all session-related queries by composing
the focused query modules.
"""

from typing import TYPE_CHECKING

from .token_queries import TokenQueries
from .tool_queries import ToolQueries
from .file_queries import FileQueries
from .timeline_queries import TimelineQueries

if TYPE_CHECKING:
    from ..config import TracingConfig
    import duckdb


class SessionQueries:
    """Unified interface for all session queries.

    Composes TokenQueries, ToolQueries, FileQueries, and TimelineQueries
    to provide a single entry point for session-related data retrieval.
    """

    def __init__(self, conn: "duckdb.DuckDBPyConnection", config: "TracingConfig"):
        """Initialize with database connection and config.

        Args:
            conn: DuckDB connection instance
            config: Tracing configuration
        """
        self.tokens = TokenQueries(conn, config)
        self.tools = ToolQueries(conn, config)
        self.files = FileQueries(conn, config)
        self.timeline = TimelineQueries(conn, config)

    def get_session_summary(self, session_id: str) -> dict:
        """Get complete summary of a session with all KPIs.

        This is the primary method for session detail views.
        Returns all metrics needed for the session detail dashboard.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with meta, summary, details, and charts sections
        """
        from datetime import datetime

        try:
            session = self.tokens._get_session_info(session_id)
            if not session:
                return self.tokens._empty_response(session_id)

            token_data = self.tokens._get_session_tokens_internal(session_id)
            tool_data = self.tools._get_session_tools_internal(session_id)
            file_data = self.files._get_session_files_internal(session_id)

            agents_data = self._get_session_agents_internal(session_id)
            duration_ms = self._calculate_duration(session_id)
            cost_usd = self.tokens._calculate_cost(token_data)

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                    "title": session.get("title", ""),
                    "directory": session.get("directory", ""),
                },
                "summary": {
                    "duration_ms": duration_ms,
                    "total_tokens": token_data["total"],
                    "total_tool_calls": tool_data["total_calls"],
                    "total_files": file_data["total_reads"] + file_data["total_writes"],
                    "unique_agents": agents_data["unique_count"],
                    "estimated_cost_usd": round(cost_usd, 4),
                    "status": session.get("status", "completed"),
                },
                "details": {
                    "tokens": token_data,
                    "tools": tool_data,
                    "files": file_data,
                    "agents": agents_data,
                },
                "charts": {
                    "tokens_by_type": self.tokens._tokens_chart_data(token_data),
                    "tools_by_name": self.tools._tools_chart_data(tool_data),
                    "files_by_type": self.files._files_chart_data(file_data),
                },
            }
        except Exception:
            return self.tokens._empty_response(session_id)

    def _get_session_agents_internal(self, session_id: str) -> dict:
        """Get agent metrics for a session."""
        try:
            agent_results = self.tokens._conn.execute(
                """
                SELECT
                    COALESCE(agent, 'user') as agent,
                    COUNT(*) as message_count,
                    SUM(tokens_input + tokens_output) as tokens
                FROM messages
                WHERE session_id = ?
                GROUP BY agent
                ORDER BY message_count DESC
                """,
                [session_id],
            ).fetchall()

            depth_result = self.tokens._conn.execute(
                """
                WITH RECURSIVE trace_depth AS (
                    SELECT trace_id, parent_trace_id, 0 as depth
                    FROM agent_traces
                    WHERE session_id = ? AND parent_trace_id IS NULL
                    
                    UNION ALL
                    
                    SELECT t.trace_id, t.parent_trace_id, td.depth + 1
                    FROM agent_traces t
                    JOIN trace_depth td ON t.parent_trace_id = td.trace_id
                    WHERE td.depth < 10
                )
                SELECT MAX(depth) FROM trace_depth
                """,
                [session_id],
            ).fetchone()

            return {
                "unique_count": len(agent_results),
                "max_depth": depth_result[0] or 0 if depth_result else 0,
                "agents": [
                    {
                        "agent": row[0],
                        "message_count": row[1],
                        "tokens": row[2] or 0,
                    }
                    for row in agent_results
                ],
            }
        except Exception:
            return {
                "unique_count": 0,
                "max_depth": 0,
                "agents": [],
            }

    def _calculate_duration(self, session_id: str) -> int:
        """Calculate session duration in milliseconds."""
        try:
            result = self.tokens._conn.execute(
                """
                SELECT
                    MIN(created_at) as first_event,
                    MAX(COALESCE(completed_at, created_at)) as last_event
                FROM messages
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            if result and result[0] and result[1]:
                delta = result[1] - result[0]
                return int(delta.total_seconds() * 1000)
            return 0
        except Exception:
            return 0
