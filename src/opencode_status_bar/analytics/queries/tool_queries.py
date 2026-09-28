"""
Tool and skill-related queries.

Queries for tool statistics, skill usage, and performance metrics.
"""

from datetime import datetime

from ..models import SkillByAgent, SkillStats, ToolStats
from .base import BaseQueries



class ToolQueries(BaseQueries):
    """Queries related to tools and skills."""

    def _get_tool_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[ToolStats]:
        """Get per-tool statistics.

        Filters tools by date using the parent message's created_at timestamp,
        since parts.created_at may be NULL.
        """
        results = self._conn.execute(
            """
            SELECT
                p.tool_name,
                COUNT(*) as invocations,
                SUM(CASE WHEN p.tool_status = 'error' THEN 1 ELSE 0 END) as failures
            FROM parts p
            JOIN messages m ON p.message_id = m.id
            WHERE m.created_at >= ? AND m.created_at <= ?
                AND p.tool_name IS NOT NULL
            GROUP BY p.tool_name
            ORDER BY invocations DESC
            LIMIT 15
            """,
            [start_date, end_date],
        ).fetchall()

        return [
            ToolStats(
                tool_name=row[0],
                invocations=row[1],
                failures=row[2] or 0,
            )
            for row in results
        ]

    def _get_skill_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[SkillStats]:
        """Get skill usage statistics.

        Filters skills by date using the parent message's created_at timestamp,
        since skills.loaded_at may be NULL.
        """
        results = self._conn.execute(
            """
            SELECT
                s.skill_name,
                COUNT(*) as load_count
            FROM skills s
            JOIN messages m ON s.message_id = m.id
            WHERE m.created_at >= ? AND m.created_at <= ?
                AND s.skill_name IS NOT NULL
            GROUP BY s.skill_name
            ORDER BY load_count DESC
            """,
            [start_date, end_date],
        ).fetchall()

        return [
            SkillStats(
                skill_name=row[0],
                load_count=row[1],
            )
            for row in results
        ]

    def _get_skills_by_agent(
        self, start_date: datetime, end_date: datetime
    ) -> list[SkillByAgent]:
        """Get skill usage per agent.

        Filters by message created_at to respect the selected time period.
        """
        try:
            results = self._conn.execute(
                """
                SELECT 
                    m.agent,
                    s.skill_name,
                    COUNT(*) as count
                FROM skills s
                JOIN messages m ON s.message_id = m.id
                WHERE m.agent IS NOT NULL
                    AND m.created_at >= ? AND m.created_at <= ?
                GROUP BY m.agent, s.skill_name
                ORDER BY count DESC
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                SkillByAgent(
                    agent=row[0],
                    skill_name=row[1],
                    count=row[2],
                )
                for row in results
            ]
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []

    def get_tool_performance(self, days: int) -> list[dict]:
        """Get tool performance stats (duration) for the last N days."""
        start_date, end_date = self._get_date_range(days)

        try:
            results = self._conn.execute(
                """
                SELECT 
                    tool_name,
                    COUNT(*) as invocations,
                    COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                    COALESCE(MAX(duration_ms), 0) as max_duration_ms,
                    COALESCE(MIN(duration_ms), 0) as min_duration_ms,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as failures
                FROM parts
                WHERE created_at >= ? AND created_at <= ?
                    AND tool_name IS NOT NULL
                    AND duration_ms IS NOT NULL
                GROUP BY tool_name
                ORDER BY avg_duration_ms DESC
                LIMIT 20
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                {
                    "tool_name": row[0],
                    "invocations": row[1],
                    "avg_duration_ms": int(row[2]),
                    "max_duration_ms": row[3],
                    "min_duration_ms": row[4],
                    "failures": row[5] or 0,
                }
                for row in results
            ]
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []
