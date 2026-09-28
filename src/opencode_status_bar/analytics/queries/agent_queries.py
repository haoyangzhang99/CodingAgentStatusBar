"""
Agent-related queries.

Queries for agent statistics, roles, and delegation stats.
"""

from datetime import datetime

from ..models import AgentDelegationStats, AgentRole, AgentStats, TokenStats
from .base import BaseQueries



class AgentQueries(BaseQueries):
    """Queries related to agents."""

    def _get_agent_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentStats]:
        """Get per-agent statistics."""
        results = self._conn.execute(
            """
            SELECT
                agent,
                COUNT(*) as msg_count,
                COALESCE(SUM(tokens_input), 0) as total_input,
                COALESCE(SUM(tokens_output), 0) as total_output,
                COALESCE(SUM(tokens_reasoning), 0) as total_reasoning,
                COALESCE(SUM(tokens_cache_read), 0) as total_cache_read,
                COALESCE(SUM(tokens_cache_write), 0) as total_cache_write
            FROM messages
            WHERE created_at >= ? AND created_at <= ?
                AND agent IS NOT NULL
            GROUP BY agent
            ORDER BY total_input + total_output DESC
            """,
            [start_date, end_date],
        ).fetchall()

        return [
            AgentStats(
                agent=row[0] or "unknown",
                message_count=row[1],
                tokens=TokenStats(
                    input=row[2],
                    output=row[3],
                    reasoning=row[4],
                    cache_read=row[5],
                    cache_write=row[6],
                ),
            )
            for row in results
        ]

    def _get_agent_roles(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentRole]:
        """Get agent classification based on delegation behavior."""
        try:
            # Get delegations sent per agent
            sent = dict(
                self._conn.execute(
                    """SELECT parent_agent, COUNT(*) FROM delegations 
                       WHERE created_at >= ? AND created_at <= ? AND parent_agent IS NOT NULL
                       GROUP BY parent_agent""",
                    [start_date, end_date],
                ).fetchall()
            )

            # Get delegations received per agent
            received = dict(
                self._conn.execute(
                    """SELECT child_agent, COUNT(*) FROM delegations 
                       WHERE created_at >= ? AND created_at <= ? AND child_agent IS NOT NULL
                       GROUP BY child_agent""",
                    [start_date, end_date],
                ).fetchall()
            )

            # Get tokens per agent
            tokens = dict(
                self._conn.execute(
                    """SELECT agent, SUM(tokens_input + tokens_output) FROM messages 
                       WHERE created_at >= ? AND created_at <= ? AND agent IS NOT NULL
                       GROUP BY agent""",
                    [start_date, end_date],
                ).fetchall()
            )

            # Combine all agents
            all_agents = set(sent.keys()) | set(received.keys())
            roles = []

            for agent in all_agents:
                s = sent.get(agent, 0)
                r = received.get(agent, 0)
                t = tokens.get(agent, 0)

                # Determine role
                if r == 0 and s > 0:
                    role = "orchestrator"
                elif s == 0 and r > 0:
                    role = "worker"
                else:
                    role = "hub"

                fan_out = (s / r) if r > 0 else float("inf") if s > 0 else 0
                tokens_per_task = (t // r) if r > 0 else 0

                roles.append(
                    AgentRole(
                        agent=agent,
                        role=role,
                        delegations_sent=s,
                        delegations_received=r,
                        fan_out=fan_out,
                        tokens_total=t,
                        tokens_per_task=tokens_per_task,
                    )
                )

            # Sort by total activity (sent + received)
            roles.sort(key=lambda x: -(x.delegations_sent + x.delegations_received))
            return roles
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []

    def _get_agent_delegation_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentDelegationStats]:
        """Get delegation statistics per agent."""
        try:
            results = self._conn.execute(
                """
                WITH session_delegations AS (
                    SELECT 
                        parent_agent,
                        session_id,
                        COUNT(*) as deleg_count
                    FROM delegations
                    WHERE parent_agent IS NOT NULL
                      AND created_at >= ? AND created_at <= ?
                    GROUP BY parent_agent, session_id
                )
                SELECT 
                    parent_agent,
                    COUNT(*) as sessions_count,
                    SUM(deleg_count) as total_delegations,
                    ROUND(AVG(deleg_count), 1) as avg_per_session,
                    MAX(deleg_count) as max_per_session
                FROM session_delegations
                GROUP BY parent_agent
                ORDER BY total_delegations DESC
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                AgentDelegationStats(
                    agent=row[0],
                    sessions_with_delegations=row[1],
                    total_delegations=row[2],
                    avg_per_session=row[3],
                    max_per_session=row[4],
                )
                for row in results
            ]
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []
