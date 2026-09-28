"""Detail query methods for TracingDataService.

Contains methods for retrieving detailed information about traces and costs.
"""

from typing import Optional, TYPE_CHECKING



if TYPE_CHECKING:
    from .config import TracingConfig
    import duckdb


class DetailQueriesMixin:
    """Mixin providing detail query methods for TracingDataService.

    Requires _conn property, _config attribute, and helper methods.
    """

    _config: "TracingConfig"

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get database connection (implemented by main class)."""
        raise NotImplementedError

    def _get_session_tokens_internal(self, session_id: str) -> dict:
        raise NotImplementedError

    def get_trace_details(self, trace_id: str) -> Optional[dict]:
        """Get full details of a specific trace.

        Args:
            trace_id: The trace ID to query

        Returns:
            Dict with trace details or None if not found
        """
        try:
            row = self._conn.execute(
                """
                SELECT 
                    t.trace_id, t.session_id, t.parent_trace_id,
                    t.parent_agent, t.subagent_type,
                    t.started_at, t.ended_at, t.duration_ms,
                    t.tokens_in, t.tokens_out, t.status,
                    t.prompt_input, t.prompt_output,
                    t.child_session_id,
                    s.title as session_title,
                    s.directory as session_directory
                FROM agent_traces t
                LEFT JOIN sessions s ON t.session_id = s.id
                WHERE t.trace_id = ?
                """,
                [trace_id],
            ).fetchone()

            if not row:
                return None

            # Get child traces
            children = self._conn.execute(
                """
                SELECT trace_id, subagent_type, status, duration_ms
                FROM agent_traces
                WHERE parent_trace_id = ?
                ORDER BY started_at ASC
                """,
                [trace_id],
            ).fetchall()

            # Get tools for this trace's session
            tools = []
            if row[13]:  # child_session_id
                tool_rows = self._conn.execute(
                    """
                    SELECT tool_name, tool_status, duration_ms, created_at
                    FROM parts
                    WHERE session_id = ? AND tool_name IS NOT NULL
                    ORDER BY created_at ASC
                    """,
                    [row[13]],
                ).fetchall()
                tools = [
                    {
                        "tool_name": t[0],
                        "status": t[1],
                        "duration_ms": t[2],
                        "created_at": t[3].isoformat() if t[3] else None,
                    }
                    for t in tool_rows
                ]

            return {
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
                "child_session_id": row[13],
                "session_title": row[14],
                "session_directory": row[15],
                "children": [
                    {
                        "trace_id": c[0],
                        "subagent_type": c[1],
                        "status": c[2],
                        "duration_ms": c[3],
                    }
                    for c in children
                ],
                "tools": tools,
            }

        except Exception:
            return None

    def get_session_cost_breakdown(self, session_id: str) -> dict:
        """Get detailed cost breakdown for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with cost breakdown by agent and token type
        """
        try:
            # Get token breakdown
            tokens = self._get_session_tokens_internal(session_id)

            # Calculate costs
            input_cost = (tokens["input"] / 1000) * self._config.cost_per_1k_input
            output_cost = (tokens["output"] / 1000) * self._config.cost_per_1k_output
            cache_cost = (tokens["cache_read"] / 1000) * self._config.cost_per_1k_cache
            total_cost = input_cost + output_cost + cache_cost

            # Get cost by agent
            by_agent = []
            for agent_data in tokens.get("by_agent", []):
                agent_tokens = agent_data.get("tokens", 0)
                # Estimate input/output split (rough 60/40 based on typical usage)
                est_input = int(agent_tokens * 0.6)
                est_output = agent_tokens - est_input
                agent_cost = (est_input / 1000) * self._config.cost_per_1k_input + (
                    est_output / 1000
                ) * self._config.cost_per_1k_output
                by_agent.append(
                    {
                        "agent": agent_data.get("agent", "unknown"),
                        "tokens": agent_tokens,
                        "estimated_cost_usd": round(agent_cost, 4),
                    }
                )

            return {
                "session_id": session_id,
                "total_cost_usd": round(total_cost, 4),
                "breakdown": {
                    "input": {
                        "tokens": tokens["input"],
                        "rate_per_1k": self._config.cost_per_1k_input,
                        "cost_usd": round(input_cost, 4),
                    },
                    "output": {
                        "tokens": tokens["output"],
                        "rate_per_1k": self._config.cost_per_1k_output,
                        "cost_usd": round(output_cost, 4),
                    },
                    "cache_read": {
                        "tokens": tokens["cache_read"],
                        "rate_per_1k": self._config.cost_per_1k_cache,
                        "cost_usd": round(cache_cost, 4),
                    },
                },
                "by_agent": by_agent,
                "cache_savings_usd": round(
                    (tokens["cache_read"] / 1000)
                    * (self._config.cost_per_1k_input - self._config.cost_per_1k_cache),
                    4,
                ),
            }

        except Exception:
            return {
                "session_id": session_id,
                "total_cost_usd": 0,
                "breakdown": {},
                "by_agent": [],
                "cache_savings_usd": 0,
            }
