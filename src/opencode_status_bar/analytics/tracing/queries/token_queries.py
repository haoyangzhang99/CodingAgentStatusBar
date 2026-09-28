"""Token-related queries for sessions.

Handles token metrics, cost calculations, and chart data generation.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseSessionQueries

if TYPE_CHECKING:
    pass


class TokenQueries(BaseSessionQueries):
    """Queries for session token metrics and cost calculations."""

    def get_session_tokens(self, session_id: str) -> dict:
        """Get detailed token metrics for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with token breakdown and charts
        """
        tokens = self._get_session_tokens_internal(session_id)
        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
            },
            "summary": {
                "total": tokens["total"],
                "input": tokens["input"],
                "output": tokens["output"],
                "cache_read": tokens["cache_read"],
                "cache_hit_ratio": tokens["cache_hit_ratio"],
            },
            "details": tokens,
            "charts": {
                "tokens_by_type": self._tokens_chart_data(tokens),
                "tokens_by_agent": tokens.get("by_agent", []),
            },
        }

    def get_session_precise_cost(self, session_id: str) -> dict:
        """Get precise cost calculated from step-finish events.

        This provides more accurate cost data than message-level estimates
        by using the actual cost values from step-finish events.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with meta, cost breakdown, and comparison with estimates
        """
        try:
            # Get precise cost from step_events
            step_result = self._conn.execute(
                """
                SELECT 
                    SUM(cost) as total_cost,
                    SUM(tokens_input) as tokens_in,
                    SUM(tokens_output) as tokens_out,
                    SUM(tokens_reasoning) as tokens_reasoning,
                    SUM(tokens_cache_read) as cache_read,
                    SUM(tokens_cache_write) as cache_write,
                    COUNT(*) as step_count
                FROM step_events
                WHERE session_id = ? AND event_type = 'finish'
                """,
                [session_id],
            ).fetchone()

            # Get estimated cost from messages (for comparison)
            msg_result = self._conn.execute(
                """
                SELECT 
                    SUM(cost) as estimated_cost,
                    SUM(tokens_input) as tokens_in,
                    SUM(tokens_output) as tokens_out
                FROM messages
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            precise_cost = float(step_result[0] or 0) if step_result else 0
            estimated_cost = float(msg_result[0] or 0) if msg_result else 0

            # Calculate difference
            cost_diff = precise_cost - estimated_cost
            cost_diff_pct = (
                (cost_diff / estimated_cost * 100) if estimated_cost > 0 else 0
            )

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                    "source": "step_events"
                    if step_result and step_result[6]
                    else "messages",
                },
                "precise": {
                    "cost_usd": round(precise_cost, 6),
                    "tokens_input": step_result[1] or 0 if step_result else 0,
                    "tokens_output": step_result[2] or 0 if step_result else 0,
                    "tokens_reasoning": step_result[3] or 0 if step_result else 0,
                    "tokens_cache_read": step_result[4] or 0 if step_result else 0,
                    "tokens_cache_write": step_result[5] or 0 if step_result else 0,
                    "step_count": step_result[6] or 0 if step_result else 0,
                },
                "estimated": {
                    "cost_usd": round(estimated_cost, 6),
                    "tokens_input": msg_result[1] or 0 if msg_result else 0,
                    "tokens_output": msg_result[2] or 0 if msg_result else 0,
                },
                "comparison": {
                    "difference_usd": round(cost_diff, 6),
                    "difference_pct": round(cost_diff_pct, 2),
                    "has_precise_data": bool(step_result and step_result[6]),
                },
            }

        except Exception as e:
            return {
                "meta": {"session_id": session_id, "error": str(e)},
                "precise": {"cost_usd": 0, "tokens_input": 0, "tokens_output": 0},
                "estimated": {"cost_usd": 0, "tokens_input": 0, "tokens_output": 0},
                "comparison": {
                    "difference_usd": 0,
                    "difference_pct": 0,
                    "has_precise_data": False,
                },
            }

    # ===== Internal/Private Methods =====

    def _get_session_tokens_internal(self, session_id: str) -> dict:
        """Get token metrics for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with token counts and breakdown
        """
        try:
            # Get overall token stats
            result = self._conn.execute(
                """
                SELECT
                    COUNT(*) as message_count,
                    SUM(tokens_input) as total_input,
                    SUM(tokens_output) as total_output,
                    SUM(tokens_reasoning) as total_reasoning,
                    SUM(tokens_cache_read) as cache_read,
                    SUM(tokens_cache_write) as cache_write
                FROM messages
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            if result is None:
                raise ValueError("No result from tokens query")

            message_count = result[0] or 0
            input_tokens = result[1] or 0
            output_tokens = result[2] or 0
            reasoning_tokens = result[3] or 0
            cache_read = result[4] or 0
            cache_write = result[5] or 0

            # Get by-agent breakdown
            agent_results = self._conn.execute(
                """
                SELECT
                    COALESCE(agent, 'user') as agent,
                    SUM(tokens_input + tokens_output) as total_tokens
                FROM messages
                WHERE session_id = ?
                GROUP BY agent
                ORDER BY total_tokens DESC
                """,
                [session_id],
            ).fetchall()

            total_input = input_tokens
            total = input_tokens + output_tokens + reasoning_tokens

            return {
                "message_count": message_count,
                "input": input_tokens,
                "output": output_tokens,
                "reasoning": reasoning_tokens,
                "cache_read": cache_read,
                "cache_write": cache_write,
                "total": total,
                "cache_hit_ratio": round(
                    (cache_read / total_input * 100) if total_input > 0 else 0, 1
                ),
                "by_agent": [
                    {"agent": row[0], "tokens": row[1] or 0} for row in agent_results
                ],
            }
        except Exception:
            return {
                "message_count": 0,
                "input": 0,
                "output": 0,
                "reasoning": 0,
                "cache_read": 0,
                "cache_write": 0,
                "total": 0,
                "cache_hit_ratio": 0,
                "by_agent": [],
            }

    def _calculate_cost(self, tokens: dict) -> float:
        """Calculate estimated cost in USD.

        Args:
            tokens: Dict with token counts (input, output, cache_read)

        Returns:
            Cost in USD
        """
        input_cost = (tokens.get("input", 0) / 1000) * self._config.cost_per_1k_input
        output_cost = (tokens.get("output", 0) / 1000) * self._config.cost_per_1k_output
        cache_cost = (
            tokens.get("cache_read", 0) / 1000
        ) * self._config.cost_per_1k_cache
        return input_cost + output_cost + cache_cost

    def _tokens_chart_data(self, tokens: dict) -> list[dict]:
        """Format tokens data for pie chart.

        Args:
            tokens: Dict with token counts

        Returns:
            List of chart data points with labels, values, and colors
        """
        return [
            {"label": "Input", "value": tokens.get("input", 0), "color": "#3498db"},
            {"label": "Output", "value": tokens.get("output", 0), "color": "#2ecc71"},
            {
                "label": "Cache",
                "value": tokens.get("cache_read", 0),
                "color": "#9b59b6",
            },
        ]
