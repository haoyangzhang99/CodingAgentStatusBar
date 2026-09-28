"""
Analytics queries module.

Provides AnalyticsQueries facade that composes all domain-specific query classes.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ..models import PeriodStats, TokenStats
from .agent_queries import AgentQueries
from .delegation_queries import DelegationQueries
from .dimension_queries import DimensionQueries
from .enriched_queries import EnrichedQueries
from .session_queries import SessionQueries
from .time_series_queries import TimeSeriesQueries
from .tool_queries import ToolQueries
from .trace_queries import TraceQueries, TraceTreeNode, SessionWithTraces

if TYPE_CHECKING:
    from ..db import AnalyticsDB


# Custom agents from open-flow (exclude generic agents like build, plan, compaction)
CUSTOM_AGENTS = {
    "executeur",  # FR
    "executor",  # EN
    "tester",
    "quality",
    "roadmap",
    "refactoring",
}


class AnalyticsQueries(
    SessionQueries,
    AgentQueries,
    DelegationQueries,
    ToolQueries,
    TimeSeriesQueries,
    DimensionQueries,
    EnrichedQueries,
):
    """Facade class that provides all analytics queries.

    Composes multiple query classes using multiple inheritance:
    - SessionQueries: Sessions, session stats, session token metrics
    - AgentQueries: Agent statistics, roles, delegation stats
    - DelegationQueries: Delegation metrics, patterns, chains
    - ToolQueries: Tool and skill statistics
    - TimeSeriesQueries: Hourly and daily statistics
    - DimensionQueries: Directory, model stats, anomalies
    - EnrichedQueries: Todos, projects, costs
    """

    def __init__(self, db: "AnalyticsDB"):
        """Initialize with a database instance.

        Args:
            db: The analytics database instance
        """
        super().__init__(db)

    def get_period_stats(self, days: int) -> PeriodStats:
        """Get statistics for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            PeriodStats with all metrics
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Session count
        session_count = self._conn.execute(
            """
            SELECT COUNT(*) FROM sessions
            WHERE created_at >= ? AND created_at <= ?
            """,
            [start_date, end_date],
        ).fetchone()[0]

        # Message count and token totals
        msg_result = self._conn.execute(
            """
            SELECT
                COUNT(*) as msg_count,
                COALESCE(SUM(tokens_input), 0) as total_input,
                COALESCE(SUM(tokens_output), 0) as total_output,
                COALESCE(SUM(tokens_reasoning), 0) as total_reasoning,
                COALESCE(SUM(tokens_cache_read), 0) as total_cache_read,
                COALESCE(SUM(tokens_cache_write), 0) as total_cache_write
            FROM messages
            WHERE created_at >= ? AND created_at <= ?
            """,
            [start_date, end_date],
        ).fetchone()

        tokens = TokenStats(
            input=msg_result[1],
            output=msg_result[2],
            reasoning=msg_result[3],
            cache_read=msg_result[4],
            cache_write=msg_result[5],
        )

        # Agent stats
        agents = self._get_agent_stats(start_date, end_date)

        # Tool stats
        tools = self._get_tool_stats(start_date, end_date)

        # Skill stats
        skills = self._get_skill_stats(start_date, end_date)

        # Top sessions by tokens
        top_sessions = self._get_top_sessions(start_date, end_date)

        # Hourly usage patterns
        hourly_usage = self._get_hourly_usage(start_date, end_date)

        # Agent chains
        agent_chains = self._get_agent_chains(start_date, end_date)

        # Average session duration
        avg_duration = self._get_avg_session_duration(start_date, end_date)

        # Anomalies
        anomalies = self._get_anomalies(start_date, end_date)

        # Advanced delegation stats
        delegation_metrics = self._get_delegation_metrics(start_date, end_date)
        delegation_patterns = self._get_delegation_patterns(start_date, end_date)
        agent_roles = self._get_agent_roles(start_date, end_date)
        hourly_delegations = self._get_hourly_delegations(start_date, end_date)

        # Time series
        daily_stats = self._get_daily_stats(start_date, end_date)

        # Session token stats
        session_token_stats = self._get_session_token_stats(start_date, end_date)

        # New dimension metrics
        directories = self._get_directory_stats(start_date, end_date)
        models = self._get_model_stats(start_date, end_date)

        # Skills and delegation analysis
        skills_by_agent = self._get_skills_by_agent(start_date, end_date)
        delegation_sessions = self._get_delegation_sessions(start_date, end_date)
        agent_delegation_stats = self._get_agent_delegation_stats(start_date, end_date)

        return PeriodStats(
            start_date=start_date,
            end_date=end_date,
            session_count=session_count,
            message_count=msg_result[0],
            tokens=tokens,
            agents=agents,
            tools=tools,
            skills=skills,
            top_sessions=top_sessions,
            hourly_usage=hourly_usage,
            agent_chains=agent_chains,
            avg_session_duration_min=avg_duration,
            anomalies=anomalies,
            delegation_metrics=delegation_metrics,
            delegation_patterns=delegation_patterns,
            agent_roles=agent_roles,
            hourly_delegations=hourly_delegations,
            daily_stats=daily_stats,
            session_token_stats=session_token_stats,
            directories=directories,
            models=models,
            skills_by_agent=skills_by_agent,
            delegation_sessions=delegation_sessions,
            agent_delegation_stats=agent_delegation_stats,
        )


__all__ = [
    "AnalyticsQueries",
    "CUSTOM_AGENTS",
    # Individual query classes for advanced use
    "SessionQueries",
    "AgentQueries",
    "DelegationQueries",
    "ToolQueries",
    "TimeSeriesQueries",
    "DimensionQueries",
    "EnrichedQueries",
    "TraceQueries",
    "TraceTreeNode",
    "SessionWithTraces",
]
