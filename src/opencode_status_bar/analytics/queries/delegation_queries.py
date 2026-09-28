"""
Delegation-related queries.

Queries for delegation metrics, patterns, chains, and sessions.
"""

from datetime import datetime
from typing import Optional

from ..models import (
    AgentChain,
    DelegationMetrics,
    DelegationPattern,
    DelegationSession,
)
from .base import BaseQueries



class DelegationQueries(BaseQueries):
    """Queries related to delegations."""

    def _get_delegation_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> Optional[DelegationMetrics]:
        """Get overall delegation metrics."""
        try:
            # Total delegations
            total = self._conn.execute(
                "SELECT COUNT(*) FROM delegations WHERE created_at >= ? AND created_at <= ?",
                [start_date, end_date],
            ).fetchone()[0]

            if total == 0:
                return None

            # Sessions with delegations
            sessions = self._conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM delegations WHERE created_at >= ? AND created_at <= ?",
                [start_date, end_date],
            ).fetchone()[0]

            # Unique patterns
            patterns = self._conn.execute(
                """SELECT COUNT(DISTINCT parent_agent || child_agent) 
                   FROM delegations 
                   WHERE created_at >= ? AND created_at <= ?""",
                [start_date, end_date],
            ).fetchone()[0]

            # Recursive delegations
            recursive = self._conn.execute(
                """SELECT COUNT(*) FROM delegations 
                   WHERE parent_agent = child_agent 
                   AND created_at >= ? AND created_at <= ?""",
                [start_date, end_date],
            ).fetchone()[0]

            # Max depth - calculate dynamically by following chains
            try:
                depth_result = self._conn.execute(
                    """
                    WITH RECURSIVE chain AS (
                        SELECT child_session_id, 1 as depth
                        FROM delegations
                        WHERE created_at >= ? AND created_at <= ?
                          AND parent_agent IS NOT NULL
                        
                        UNION ALL
                        
                        SELECT d.child_session_id, c.depth + 1
                        FROM chain c
                        JOIN delegations d ON c.child_session_id = d.session_id
                        WHERE c.depth < 100  -- Safety limit only, not a real constraint
                    )
                    SELECT MAX(depth) FROM chain
                    """,
                    [start_date, end_date],
                ).fetchone()[0]

                # depth+1 = number of agents in chain
                max_depth = (depth_result + 1) if depth_result else 2
            except (
                Exception
            ):  # Intentional catch-all: recursive CTE may fail, use default
                max_depth = 2

            return DelegationMetrics(
                total_delegations=total,
                sessions_with_delegations=sessions,
                unique_patterns=patterns,
                recursive_delegations=recursive,
                recursive_percentage=(recursive / total * 100) if total > 0 else 0,
                max_depth=max_depth,
                avg_per_session=(total / sessions) if sessions > 0 else 0,
            )
        except Exception:  # Intentional catch-all: query failures return None
            return None

    def _get_delegation_patterns(
        self, start_date: datetime, end_date: datetime
    ) -> list[DelegationPattern]:
        """Get detailed delegation patterns with token metrics."""
        try:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM delegations WHERE created_at >= ? AND created_at <= ?",
                [start_date, end_date],
            ).fetchone()[0]

            if total == 0:
                return []

            # Query patterns with token totals from both parent and child sessions
            results = self._conn.execute(
                """
                SELECT 
                    d.parent_agent,
                    d.child_agent,
                    COUNT(*) as count,
                    SUM(COALESCE(parent_tokens.total, 0) + COALESCE(child_tokens.total, 0)) as total_tokens
                FROM delegations d
                LEFT JOIN (
                    SELECT session_id, SUM(tokens_input + tokens_output) as total
                    FROM messages GROUP BY session_id
                ) parent_tokens ON d.session_id = parent_tokens.session_id
                LEFT JOIN (
                    SELECT session_id, SUM(tokens_input + tokens_output) as total
                    FROM messages GROUP BY session_id
                ) child_tokens ON d.child_session_id = child_tokens.session_id
                WHERE d.created_at >= ? AND d.created_at <= ?
                  AND d.parent_agent IS NOT NULL AND d.child_agent IS NOT NULL
                GROUP BY d.parent_agent, d.child_agent
                ORDER BY total_tokens DESC
                LIMIT 20
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                DelegationPattern(
                    parent=row[0],
                    child=row[1],
                    count=row[2],
                    percentage=(row[2] / total * 100) if total > 0 else 0,
                    tokens_total=row[3] or 0,
                    tokens_avg=(row[3] // row[2]) if row[3] and row[2] else 0,
                )
                for row in results
            ]
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []

    def _get_agent_chains(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentChain]:
        """Get real agent delegation chains from task tool invocations.

        Uses the delegations table to find actual parent->child relationships
        built from task tool invocations with subagent_type.
        """
        # Query direct delegations from the delegations table
        results = self._conn.execute(
            """
            WITH direct_delegations AS (
                -- Get direct parent -> child relationships
                SELECT
                    parent_agent,
                    child_agent,
                    session_id,
                    created_at
                FROM delegations
                WHERE created_at >= ? AND created_at <= ?
                    AND parent_agent IS NOT NULL
                    AND child_agent IS NOT NULL
            ),
            delegation_pairs AS (
                -- Format as "parent -> child" and count occurrences
                SELECT
                    parent_agent || ' -> ' || child_agent as chain,
                    COUNT(*) as occurrences
                FROM direct_delegations
                GROUP BY parent_agent, child_agent
            )
            SELECT chain, occurrences, 2 as depth
            FROM delegation_pairs
            ORDER BY occurrences DESC
            LIMIT 15
            """,
            [start_date, end_date],
        ).fetchall()

        chains = [
            AgentChain(
                chain=row[0],
                occurrences=row[1],
                depth=row[2],
            )
            for row in results
        ]

        # If we have delegations, also try to find longer chains
        # by following child_session_id references
        if chains:
            extended = self._get_extended_chains(start_date, end_date)
            chains.extend(extended)
            # Sort by depth (longer chains first), then by occurrences
            chains.sort(key=lambda c: (-c.depth, -c.occurrences))

        return chains[:15]

    def _get_extended_chains(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentChain]:
        """Find extended chains (depth > 2) by following child_session_id.

        e.g., executeur -> tester -> refactoring
        """
        # Find chains of length 3 by joining delegations
        results = self._conn.execute(
            """
            WITH d1 AS (
                SELECT * FROM delegations
                WHERE created_at >= ? AND created_at <= ?
                    AND parent_agent IS NOT NULL
            ),
            d2 AS (
                SELECT * FROM delegations
                WHERE created_at >= ? AND created_at <= ?
                    AND parent_agent IS NOT NULL
            )
            SELECT
                d1.parent_agent || ' -> ' || d1.child_agent || ' -> ' || d2.child_agent as chain,
                COUNT(*) as occurrences
            FROM d1
            JOIN d2 ON d1.child_session_id = d2.session_id
            WHERE d2.parent_agent = d1.child_agent
            GROUP BY d1.parent_agent, d1.child_agent, d2.child_agent
            HAVING COUNT(*) >= 1
            ORDER BY occurrences DESC
            LIMIT 10
            """,
            [start_date, end_date, start_date, end_date],
        ).fetchall()

        return [
            AgentChain(
                chain=row[0],
                occurrences=row[1],
                depth=3,
            )
            for row in results
        ]

    def _get_delegation_sessions(
        self, start_date: datetime, end_date: datetime
    ) -> list[DelegationSession]:
        """Get sessions with multiple delegations."""
        try:
            results = self._conn.execute(
                """
                SELECT 
                    parent_agent,
                    session_id,
                    COUNT(*) as delegation_count,
                    STRING_AGG(child_agent, ' -> ' ORDER BY created_at) as sequence
                FROM delegations
                WHERE parent_agent IS NOT NULL
                  AND created_at >= ? AND created_at <= ?
                GROUP BY parent_agent, session_id
                HAVING COUNT(*) >= 2
                ORDER BY delegation_count DESC
                LIMIT 20
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                DelegationSession(
                    agent=row[0],
                    session_id=row[1],
                    delegation_count=row[2],
                    sequence=row[3],
                )
                for row in results
            ]
        except (
            Exception
        ):  # Intentional catch-all: query failures return empty list
            return []
