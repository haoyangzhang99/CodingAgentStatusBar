"""Tool-related queries for sessions.

Handles tool usage metrics, operations tracking, and chart data generation.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseSessionQueries

if TYPE_CHECKING:
    pass


class ToolQueries(BaseSessionQueries):
    """Queries for session tool usage and operations."""

    def get_session_tools(self, session_id: str) -> dict:
        """Get detailed tool usage for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with tool breakdown and charts
        """
        tools = self._get_session_tools_internal(session_id)
        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
            },
            "summary": {
                "total_calls": tools["total_calls"],
                "unique_tools": tools["unique_tools"],
                "success_rate": tools["success_rate"],
                "avg_duration_ms": tools["avg_duration_ms"],
            },
            "details": tools,
            "charts": {
                "tools_by_name": self._tools_chart_data(tools),
                "tools_by_status": tools.get("by_status", []),
            },
        }

    def get_session_tool_operations(self, session_id: str) -> dict:
        """Get detailed tool operations with context.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with list of tool operations with display info
        """
        try:
            # Get all tool operations with display context
            results = self._conn.execute(
                """
                SELECT
                    p.tool_name,
                    p.content,
                    p.arguments,
                    p.tool_status,
                    p.duration_ms,
                    p.created_at
                FROM parts p
                WHERE p.session_id = ?
                  AND p.tool_name IS NOT NULL
                ORDER BY p.created_at ASC
                """,
                [session_id],
            ).fetchall()

            operations = []
            for row in results:
                tool_name = row[0]
                content = row[1]
                arguments = row[2]

                # Extract display info using helper
                display_info = self._extract_tool_display_info(
                    tool_name, content, arguments
                )

                op = {
                    "tool_name": tool_name,
                    "display_info": display_info,
                    "status": row[3],
                    "duration_ms": int(row[4] or 0),
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                operations.append(op)

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {"total_operations": len(operations)},
                "operations": operations,
            }

        except Exception as e:
            return {
                "meta": {"session_id": session_id, "error": str(e)},
                "summary": {"total_operations": 0},
                "operations": [],
            }

    # ===== Internal/Private Methods =====

    def _get_session_tools_internal(self, session_id: str) -> dict:
        """Get tool metrics for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with tool statistics
        """
        try:
            # Get overall stats
            result = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_calls,
                    COUNT(DISTINCT tool_name) as unique_tools,
                    SUM(CASE WHEN tool_status = 'completed' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as errors,
                    AVG(duration_ms) as avg_duration
                FROM parts
                WHERE session_id = ? AND tool_name IS NOT NULL
                """,
                [session_id],
            ).fetchone()

            if result is None:
                raise ValueError("No result from tools query")

            total = result[0] or 0
            success = result[2] or 0

            # Get top tools
            top_tools = self._conn.execute(
                """
                SELECT
                    tool_name,
                    COUNT(*) as count,
                    AVG(duration_ms) as avg_duration,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as errors
                FROM parts
                WHERE session_id = ? AND tool_name IS NOT NULL
                GROUP BY tool_name
                ORDER BY count DESC
                LIMIT 10
                """,
                [session_id],
            ).fetchall()

            return {
                "total_calls": total,
                "unique_tools": result[1] or 0,
                "success_count": success,
                "error_count": result[3] or 0,
                "success_rate": round((success / total * 100) if total > 0 else 0, 1),
                "avg_duration_ms": int(result[4] or 0),
                "top_tools": [
                    {
                        "name": row[0],
                        "count": row[1],
                        "avg_duration_ms": int(row[2] or 0),
                        "error_count": row[3] or 0,
                    }
                    for row in top_tools
                ],
            }
        except Exception:
            return {
                "total_calls": 0,
                "unique_tools": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
                "top_tools": [],
            }

    def _tools_chart_data(self, tools: dict) -> list[dict]:
        """Format tools data for bar chart.

        Args:
            tools: Dict with tool statistics

        Returns:
            List of chart data points
        """
        return [
            {"label": t["name"], "value": t["count"]}
            for t in tools.get("top_tools", [])[:5]
        ]

    def _extract_tool_display_info(
        self, tool_name: str | None, content: str | None, arguments: str | None
    ) -> str:
        """Extract human-readable display info from tool arguments.

        Args:
            tool_name: Name of the tool (bash, read, write, edit, etc.)
            content: Tool result content (unused)
            arguments: JSON string of tool arguments

        Returns:
            Short display string for the tool operation
        """
        from ..helpers import extract_tool_display_info as helper_extract

        return helper_extract(tool_name, arguments, content)
