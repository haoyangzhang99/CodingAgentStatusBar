"""
Dimension queries.

Queries for directory and model statistics, and anomaly detection.
"""

from datetime import datetime

from ..models import DirectoryStats, ModelStats
from .base import BaseQueries



class DimensionQueries(BaseQueries):
    """Queries for dimension-based statistics (directory, model)."""

    def _get_directory_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[DirectoryStats]:
        """Get statistics per working directory."""
        try:
            results = self._conn.execute(
                """
                SELECT 
                    s.directory,
                    COUNT(DISTINCT s.id) as sessions,
                    COALESCE(SUM(m.tokens_input + m.tokens_output), 0) as tokens
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                WHERE s.created_at >= ? AND s.created_at <= ?
                  AND s.directory IS NOT NULL
                GROUP BY s.directory
                ORDER BY tokens DESC
                LIMIT 10
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                DirectoryStats(
                    directory=row[0],
                    sessions=row[1],
                    tokens=row[2],
                )
                for row in results
            ]
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []

    def _get_model_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[ModelStats]:
        """Get statistics per model."""
        try:
            # First get total tokens for percentage calculation
            total_tokens = self._conn.execute(
                """
                SELECT COALESCE(SUM(tokens_input + tokens_output), 0)
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()[0]

            results = self._conn.execute(
                """
                SELECT 
                    model_id,
                    provider_id,
                    COUNT(*) as messages,
                    COALESCE(SUM(tokens_input + tokens_output), 0) as tokens
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                  AND model_id IS NOT NULL
                GROUP BY model_id, provider_id
                ORDER BY tokens DESC
                LIMIT 10
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                ModelStats(
                    model_id=row[0],
                    provider_id=row[1] or "unknown",
                    messages=row[2],
                    tokens=row[3],
                    percentage=(row[3] / total_tokens * 100) if total_tokens > 0 else 0,
                )
                for row in results
            ]
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []

    def _get_anomalies(self, start_date: datetime, end_date: datetime) -> list[str]:
        """Detect anomalies in usage patterns."""
        anomalies = []

        # Check for sessions with excessive task calls (> 10)
        try:
            excessive_tasks = self._conn.execute(
                """
                SELECT ANY_VALUE(s.title) as title, COUNT(*) as task_count
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                JOIN sessions s ON m.session_id = s.id
                WHERE p.tool_name = 'task'
                    AND p.created_at >= ? AND p.created_at <= ?
                GROUP BY s.id
                HAVING task_count > 10
                ORDER BY task_count DESC
                LIMIT 5
                """,
                [start_date, end_date],
            ).fetchall()

            for title, count in excessive_tasks:
                short_title = (
                    title[:30] + "..."
                    if title and len(title) > 30
                    else (title or "Untitled")
                )
                anomalies.append(f"Session '{short_title}' has {count} task calls")
        except Exception:
            pass  # nosec B110 - anomaly detection is optional

        # Check for high tool failure rates (> 20%)
        try:
            high_failure_tools = self._conn.execute(
                """
                SELECT
                    tool_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as failures
                FROM parts
                WHERE created_at >= ? AND created_at <= ?
                    AND tool_name IS NOT NULL
                GROUP BY tool_name
                HAVING total >= 10 AND (failures * 100.0 / total) > 20
                """,
                [start_date, end_date],
            ).fetchall()

            for tool, total, failures in high_failure_tools:
                rate = (failures / total) * 100
                anomalies.append(
                    f"Tool '{tool}' has {rate:.0f}% failure rate ({failures}/{total})"
                )
        except Exception:
            pass  # nosec B110 - anomaly detection is optional

        return anomalies

    def get_anomalies(self, days: int) -> list[str]:
        """Public method for backward compatibility."""
        start_date, end_date = self._get_date_range(days)
        return self._get_anomalies(start_date, end_date)
