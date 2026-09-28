"""
Time series queries.

Queries for hourly usage, daily stats, and temporal patterns.
"""

from datetime import datetime

from ..models import DailyStats, HourlyDelegations, HourlyStats
from .base import BaseQueries



class TimeSeriesQueries(BaseQueries):
    """Queries for time-based statistics."""

    def _get_hourly_usage(
        self, start_date: datetime, end_date: datetime
    ) -> list[HourlyStats]:
        """Get usage patterns by hour of day."""
        results = self._conn.execute(
            """
            SELECT
                EXTRACT(HOUR FROM created_at) as hour,
                COUNT(*) as msg_count,
                COALESCE(SUM(tokens_input + tokens_output), 0) as total_tokens
            FROM messages
            WHERE created_at >= ? AND created_at <= ?
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hour
            """,
            [start_date, end_date],
        ).fetchall()

        return [
            HourlyStats(
                hour=int(row[0]),
                message_count=row[1],
                tokens=row[2],
            )
            for row in results
        ]

    def _get_hourly_delegations(
        self, start_date: datetime, end_date: datetime
    ) -> list[HourlyDelegations]:
        """Get delegation counts by hour of day."""
        try:
            results = self._conn.execute(
                """
                SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) as count
                FROM delegations
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY hour
                ORDER BY hour
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                HourlyDelegations(hour=int(row[0]), count=row[1]) for row in results
            ]
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []

    def _get_daily_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[DailyStats]:
        """Get daily activity statistics for time series chart."""
        try:
            # Get sessions per day
            sessions_per_day = dict(
                self._conn.execute(
                    """
                    SELECT DATE_TRUNC('day', created_at) as day, COUNT(*) as count
                    FROM sessions
                    WHERE created_at >= ? AND created_at <= ?
                    GROUP BY day
                    """,
                    [start_date, end_date],
                ).fetchall()
            )

            # Get messages and tokens per day
            messages_per_day = {}
            tokens_per_day = {}
            results = self._conn.execute(
                """
                SELECT 
                    DATE_TRUNC('day', created_at) as day,
                    COUNT(*) as msg_count,
                    COALESCE(SUM(tokens_input + tokens_output), 0) as tokens
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY day
                """,
                [start_date, end_date],
            ).fetchall()
            for day, msg_count, tokens in results:
                messages_per_day[day] = msg_count
                tokens_per_day[day] = tokens

            # Get delegations per day
            delegations_per_day = dict(
                self._conn.execute(
                    """
                    SELECT DATE_TRUNC('day', created_at) as day, COUNT(*) as count
                    FROM delegations
                    WHERE created_at >= ? AND created_at <= ?
                    GROUP BY day
                    """,
                    [start_date, end_date],
                ).fetchall()
            )

            # Combine all days
            all_days = (
                set(sessions_per_day.keys())
                | set(messages_per_day.keys())
                | set(delegations_per_day.keys())
            )

            daily_stats = []
            for day in sorted(all_days):
                daily_stats.append(
                    DailyStats(
                        date=day,
                        sessions=sessions_per_day.get(day, 0),
                        messages=messages_per_day.get(day, 0),
                        tokens=tokens_per_day.get(day, 0),
                        delegations=delegations_per_day.get(day, 0),
                    )
                )

            return daily_stats
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []
