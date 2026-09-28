"""Statistics query methods for TracingDataService.

Contains methods for global stats, daily aggregation, and comparison.
"""

from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from ...utils.logger import info


if TYPE_CHECKING:
    from .config import TracingConfig
    from ..queries.trace_queries import TraceQueries
    import duckdb


class StatsQueriesMixin:
    """Mixin providing statistics query methods for TracingDataService.

    Requires _conn property, _config attribute, _trace_q, and helper methods.
    """

    _config: "TracingConfig"
    _trace_q: "TraceQueries"

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get database connection (implemented by main class)."""
        raise NotImplementedError

    def _calculate_cost(self, tokens: dict) -> float:
        raise NotImplementedError

    def get_session_summary(self, session_id: str) -> dict:
        raise NotImplementedError

    def get_global_stats(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> dict:
        """Get global statistics for a time period.

        Args:
            start: Start of period (defaults to 30 days ago)
            end: End of period (defaults to now)

        Returns:
            Dict with aggregated statistics
        """
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=30)

        try:
            # Sessions stats
            session_stats_row = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_sessions,
                    COUNT(DISTINCT directory) as unique_projects
                FROM sessions
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start, end],
            ).fetchone()
            session_stats = session_stats_row if session_stats_row else (0, 0)

            # Message/token stats
            token_stats_row = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_messages,
                    COALESCE(SUM(tokens_input), 0) as total_input,
                    COALESCE(SUM(tokens_output), 0) as total_output,
                    COALESCE(SUM(tokens_cache_read), 0) as total_cache
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start, end],
            ).fetchone()
            token_stats = token_stats_row if token_stats_row else (0, 0, 0, 0)

            # Trace stats
            trace_stats = self._trace_q.get_trace_stats(start, end)

            # Tool stats
            tool_stats_row = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_calls,
                    COUNT(DISTINCT tool_name) as unique_tools
                FROM parts
                WHERE tool_name IS NOT NULL
                  AND created_at >= ? AND created_at <= ?
                """,
                [start, end],
            ).fetchone()
            tool_stats = tool_stats_row if tool_stats_row else (0, 0)

            total_tokens = (token_stats[1] or 0) + (token_stats[2] or 0)
            cost = self._calculate_cost(
                {
                    "input": token_stats[1] or 0,
                    "output": token_stats[2] or 0,
                    "cache_read": token_stats[3] or 0,
                }
            )

            # Top Agents (from agent_traces by subagent_type)
            agent_rows = self._conn.execute(
                """
                SELECT 
                    subagent_type as agent,
                    COUNT(*) as messages,
                    COALESCE(SUM(tokens_in + tokens_out), 0) as tokens
                FROM agent_traces
                WHERE started_at >= ? AND started_at <= ?
                GROUP BY subagent_type
                ORDER BY tokens DESC
                LIMIT 10
                """,
                [start, end],
            ).fetchall()

            # Top Tools with failure rate (from parts)
            tool_rows = self._conn.execute(
                """
                SELECT 
                    tool_name as tool,
                    COUNT(*) as invocations,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as failures
                FROM parts
                WHERE tool_name IS NOT NULL 
                  AND created_at >= ? AND created_at <= ?
                GROUP BY tool_name
                ORDER BY invocations DESC
                LIMIT 10
                """,
                [start, end],
            ).fetchall()

            # Skills load count (from parts where tool_name='skill', parse arguments JSON)
            skill_rows = self._conn.execute(
                """
                SELECT 
                    json_extract_string(arguments, '$.name') as skill,
                    COUNT(*) as load_count
                FROM parts
                WHERE tool_name = 'skill'
                  AND arguments IS NOT NULL
                  AND created_at >= ? AND created_at <= ?
                GROUP BY skill
                ORDER BY load_count DESC
                LIMIT 10
                """,
                [start, end],
            ).fetchall()

            # Format agents list
            agents_list = [
                {
                    "agent": row[0] or "unknown",
                    "messages": row[1] or 0,
                    "tokens": row[2] or 0,
                }
                for row in agent_rows
            ]

            # Format tools list with failure rate
            tools_list = [
                {
                    "tool": row[0] or "unknown",
                    "invocations": row[1] or 0,
                    "failures": row[2] or 0,
                    "failure_rate": f"{(row[2] / row[1] * 100):.1f}%"
                    if row[1] > 0
                    else "0.0%",
                }
                for row in tool_rows
            ]

            # Format skills list
            skills_list = [
                {
                    "skill": row[0] or "unknown",
                    "load_count": row[1] or 0,
                }
                for row in skill_rows
            ]

            return {
                "meta": {
                    "period": {
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                    },
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {
                    "total_sessions": session_stats[0] or 0,
                    "unique_projects": session_stats[1] or 0,
                    "total_messages": token_stats[0] or 0,
                    "total_tokens": total_tokens,
                    "total_traces": trace_stats.get("total_traces", 0),
                    "total_tool_calls": tool_stats[0] or 0,
                    "estimated_cost_usd": round(cost, 2),
                },
                "details": {
                    "tokens": {
                        "input": token_stats[1] or 0,
                        "output": token_stats[2] or 0,
                        "cache_read": token_stats[3] or 0,
                    },
                    "traces": trace_stats,
                    "tools": {
                        "total_calls": tool_stats[0] or 0,
                        "unique_tools": tool_stats[1] or 0,
                    },
                },
                # Detailed breakdowns for dashboard tables
                "agents": agents_list,
                "tools": tools_list,
                "skills": skills_list,
            }

        except Exception as e:
            return {
                "meta": {"error": str(e)},
                "summary": {},
                "details": {},
            }

    def get_comparison(self, session_ids: list[str]) -> dict:
        """Compare metrics across multiple sessions.

        Args:
            session_ids: List of session IDs to compare

        Returns:
            Dict with comparison data for each session
        """
        comparisons = []
        for session_id in session_ids:
            summary = self.get_session_summary(session_id)
            comparisons.append(
                {
                    "session_id": session_id,
                    "title": summary["meta"].get("title", ""),
                    "metrics": summary["summary"],
                }
            )

        return {
            "meta": {
                "sessions_compared": len(session_ids),
                "generated_at": datetime.now().isoformat(),
            },
            "comparisons": comparisons,
        }

    def update_session_stats(self, session_id: str) -> None:
        """Update pre-calculated stats for a session.

        Called after data sync to refresh aggregation tables.

        Args:
            session_id: The session ID to update stats for
        """
        try:
            summary = self.get_session_summary(session_id)
            if not summary["summary"]:
                return

            s = summary["summary"]
            d = summary["details"]

            self._conn.execute(
                """
                INSERT OR REPLACE INTO session_stats (
                    session_id, total_messages, total_tokens_in, total_tokens_out,
                    total_tokens_cache, total_tool_calls, tool_success_rate,
                    total_file_reads, total_file_writes, unique_agents,
                    max_delegation_depth, estimated_cost_usd, duration_ms, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [
                    session_id,
                    d["tokens"].get("message_count", 0),
                    d["tokens"].get("input", 0),
                    d["tokens"].get("output", 0),
                    d["tokens"].get("cache_read", 0),
                    s.get("total_tool_calls", 0),
                    d["tools"].get("success_rate", 0),
                    d["files"].get("total_reads", 0),
                    d["files"].get("total_writes", 0),
                    s.get("unique_agents", 0),
                    d["agents"].get("max_depth", 0),
                    s.get("estimated_cost_usd", 0),
                    s.get("duration_ms", 0),
                ],
            )
            info(f"Updated session_stats for {session_id}")

        except Exception:
            pass

    def update_daily_stats(self, date: Optional[datetime] = None) -> None:
        """Update daily aggregation stats.

        Args:
            date: The date to update (defaults to today)
        """
        if date is None:
            date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")

        try:
            # Calculate daily stats
            stats = self._conn.execute(
                """
                SELECT
                    COUNT(DISTINCT s.id) as sessions,
                    (SELECT COUNT(*) FROM agent_traces WHERE DATE(started_at) = ?) as traces,
                    COALESCE(SUM(m.tokens_input + m.tokens_output), 0) as tokens,
                    (SELECT COUNT(*) FROM parts WHERE DATE(created_at) = ? AND tool_name IS NOT NULL) as tools,
                    AVG(CASE WHEN s.duration_ms > 0 THEN s.duration_ms END) as avg_duration,
                    (SELECT CAST(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS FLOAT) / 
                        NULLIF(COUNT(*), 0) * 100
                     FROM agent_traces WHERE DATE(started_at) = ?) as error_rate
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id AND DATE(m.created_at) = ?
                WHERE DATE(s.created_at) = ?
                """,
                [date_str, date_str, date_str, date_str, date_str],
            ).fetchone()

            if stats:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_stats (
                        date, total_sessions, total_traces, total_tokens,
                        total_tool_calls, avg_session_duration_ms, error_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        date_str,
                        stats[0] or 0,
                        stats[1] or 0,
                        stats[2] or 0,
                        stats[3] or 0,
                        int(stats[4] or 0),
                        round(stats[5] or 0, 2),
                    ],
                )
                info(f"Updated daily_stats for {date_str}")

        except Exception:
            pass

    def get_daily_stats(self, days: int = 7) -> list[dict]:
        """Get aggregated statistics per day.

        Args:
            days: Number of days to retrieve

        Returns:
            List of daily stat dicts
        """
        try:
            start_date = datetime.now() - timedelta(days=days)

            rows = self._conn.execute(
                """
                SELECT 
                    CAST(started_at AS DATE) as date,
                    COUNT(*) as traces,
                    SUM(tokens_in + tokens_out) as tokens,
                    AVG(duration_ms) as avg_duration_ms,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                FROM agent_traces
                WHERE started_at >= ?
                GROUP BY CAST(started_at AS DATE)
                ORDER BY date DESC
                """,
                [start_date],
            ).fetchall()

            # Get session counts separately
            session_rows = self._conn.execute(
                """
                SELECT 
                    CAST(created_at AS DATE) as date,
                    COUNT(*) as sessions
                FROM sessions
                WHERE created_at >= ?
                GROUP BY CAST(created_at AS DATE)
                """,
                [start_date],
            ).fetchall()
            session_by_date = {
                row[0].strftime("%Y-%m-%d"): row[1] for row in session_rows
            }

            # Get tool counts separately
            tool_rows = self._conn.execute(
                """
                SELECT 
                    CAST(created_at AS DATE) as date,
                    COUNT(*) as tool_calls
                FROM parts
                WHERE tool_name IS NOT NULL AND created_at >= ?
                GROUP BY CAST(created_at AS DATE)
                """,
                [start_date],
            ).fetchall()
            tools_by_date = {row[0].strftime("%Y-%m-%d"): row[1] for row in tool_rows}

            return [
                {
                    "date": row[0].strftime("%Y-%m-%d") if row[0] else None,
                    "sessions": session_by_date.get(
                        row[0].strftime("%Y-%m-%d") if row[0] else "", 0
                    ),
                    "traces": row[1] or 0,
                    "tokens": row[2] or 0,
                    "avg_duration_ms": int(row[3] or 0),
                    "errors": row[4] or 0,
                    "tool_calls": tools_by_date.get(
                        row[0].strftime("%Y-%m-%d") if row[0] else "", 0
                    ),
                }
                for row in rows
            ]

        except Exception:
            return []
