"""
Trace-related queries.

Queries for agent traces extracted from task tool invocations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


from ..models import AgentTrace
from .base import BaseQueries


@dataclass
class TraceTreeNode:
    """A node in the trace hierarchy tree."""

    trace: AgentTrace
    children: list["TraceTreeNode"] = field(default_factory=list)
    depth: int = 0


@dataclass
class SessionWithTraces:
    """A session that has agent traces."""

    session_id: str
    title: Optional[str]
    trace_count: int
    first_trace_at: Optional[datetime]
    total_duration_ms: int


@dataclass
class SessionNode:
    """A session in the hierarchy with delegation info."""

    session_id: str
    title: Optional[str]
    parent_session_id: Optional[str]
    agent_type: Optional[str]  # The agent running in this session
    parent_agent: Optional[str]  # The agent that delegated to this session
    created_at: Optional[datetime]
    directory: Optional[str] = None  # Project directory
    trace_count: int = 0
    prompt_input: Optional[str] = None  # First user message (for ROOT sessions)
    children: list["SessionNode"] = field(default_factory=list)


class TraceQueries(BaseQueries):
    """Queries related to agent traces."""

    def get_traces_by_session(self, session_id: str) -> list[AgentTrace]:
        """Get all traces for a specific session.

        Args:
            session_id: The session ID to query

        Returns:
            List of AgentTrace objects ordered by start time
        """
        try:
            # Join with delegations to get accurate parent_agent
            results = self._conn.execute(
                """
                SELECT
                    t.trace_id, t.session_id, t.parent_trace_id,
                    COALESCE(d.parent_agent, t.parent_agent) as parent_agent,
                    t.subagent_type, t.prompt_input, t.prompt_output,
                    t.started_at, t.ended_at, t.duration_ms,
                    t.tokens_in, t.tokens_out, t.status, t.tools_used, t.child_session_id
                FROM agent_traces t
                LEFT JOIN delegations d ON t.trace_id = d.id
                WHERE t.session_id = ?
                ORDER BY t.started_at ASC
                """,
                [session_id],
            ).fetchall()

            return [self._row_to_trace(row) for row in results]
        except Exception:
            return []

    def get_trace_tree(self, session_id: str) -> list[TraceTreeNode]:
        """Get hierarchical tree of traces for a session.

        Reconstructs the delegation hierarchy by following
        child_session_id references.

        Args:
            session_id: The root session ID

        Returns:
            List of root TraceTreeNode objects with nested children
        """
        try:
            # Get all traces that start from this session or are children
            results = self._conn.execute(
                """
                WITH RECURSIVE trace_tree AS (
                    -- Root traces (directly in the session)
                    SELECT
                        trace_id, session_id, parent_trace_id, parent_agent,
                        subagent_type, prompt_input, prompt_output,
                        started_at, ended_at, duration_ms,
                        tokens_in, tokens_out, status, tools_used, child_session_id,
                        0 as depth
                    FROM agent_traces
                    WHERE session_id = ?

                    UNION ALL

                    -- Child traces (in child sessions)
                    SELECT
                        t.trace_id, t.session_id, t.parent_trace_id, t.parent_agent,
                        t.subagent_type, t.prompt_input, t.prompt_output,
                        t.started_at, t.ended_at, t.duration_ms,
                        t.tokens_in, t.tokens_out, t.status, t.tools_used, t.child_session_id,
                        tt.depth + 1
                    FROM agent_traces t
                    JOIN trace_tree tt ON t.session_id = tt.child_session_id
                    WHERE tt.depth < 10  -- Prevent infinite recursion
                )
                SELECT * FROM trace_tree
                ORDER BY started_at ASC
                """,
                [session_id],
            ).fetchall()

            # Build tree structure
            traces_by_id: dict[str, TraceTreeNode] = {}
            root_nodes: set[TraceTreeNode] = set()  # Use set for O(1) operations

            for row in results:
                trace = self._row_to_trace(row[:15])  # First 15 columns
                depth = row[15] if len(row) > 15 else 0
                node = TraceTreeNode(trace=trace, depth=depth)
                traces_by_id[trace.trace_id] = node

            # Link parents and children
            for node in traces_by_id.values():
                if (
                    node.trace.parent_trace_id
                    and node.trace.parent_trace_id in traces_by_id
                ):
                    parent = traces_by_id[node.trace.parent_trace_id]
                    parent.children.append(node)
                elif node.depth == 0:
                    root_nodes.add(node)  # O(1) set addition

            # If no parent links, use session hierarchy
            if not any(n.children for n in traces_by_id.values()):
                session_to_nodes: dict[str, list[TraceTreeNode]] = {}
                for node in traces_by_id.values():
                    session = node.trace.session_id
                    if session not in session_to_nodes:
                        session_to_nodes[session] = []
                    session_to_nodes[session].append(node)

                for node in traces_by_id.values():
                    if node.trace.child_session_id:
                        children = session_to_nodes.get(node.trace.child_session_id, [])
                        node.children.extend(children)
                        # O(1) set operations instead of O(N) list operations
                        root_nodes.difference_update(children)

            return list(root_nodes)  # Convert back to list for return type

        except Exception:
            return []

    def get_traces_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentTrace]:
        """Get all traces within a date range.

        Args:
            start_date: Start of the range
            end_date: End of the range

        Returns:
            List of AgentTrace objects
        """
        try:
            # Join with delegations to get accurate parent_agent
            # delegations.id matches agent_traces.trace_id
            results = self._conn.execute(
                """
                SELECT
                    t.trace_id, t.session_id, t.parent_trace_id,
                    COALESCE(d.parent_agent, t.parent_agent) as parent_agent,
                    t.subagent_type, t.prompt_input, t.prompt_output,
                    t.started_at, t.ended_at, t.duration_ms,
                    t.tokens_in, t.tokens_out, t.status, t.tools_used, t.child_session_id
                FROM agent_traces t
                LEFT JOIN delegations d ON t.trace_id = d.id
                WHERE t.started_at >= ? AND t.started_at <= ?
                ORDER BY t.started_at DESC
                """,
                [start_date, end_date],
            ).fetchall()

            return [self._row_to_trace(row) for row in results]
        except Exception:
            return []

    def get_traces_by_agent(self, subagent_type: str) -> list[AgentTrace]:
        """Get all traces for a specific agent type.

        Args:
            subagent_type: The agent type (e.g., "tester", "executeur")

        Returns:
            List of AgentTrace objects
        """
        try:
            # Join with delegations to get accurate parent_agent
            results = self._conn.execute(
                """
                SELECT
                    t.trace_id, t.session_id, t.parent_trace_id,
                    COALESCE(d.parent_agent, t.parent_agent) as parent_agent,
                    t.subagent_type, t.prompt_input, t.prompt_output,
                    t.started_at, t.ended_at, t.duration_ms,
                    t.tokens_in, t.tokens_out, t.status, t.tools_used, t.child_session_id
                FROM agent_traces t
                LEFT JOIN delegations d ON t.trace_id = d.id
                WHERE t.subagent_type = ?
                ORDER BY t.started_at DESC
                """,
                [subagent_type],
            ).fetchall()

            return [self._row_to_trace(row) for row in results]
        except Exception:
            return []

    def get_trace_details(self, trace_id: str) -> Optional[AgentTrace]:
        """Get full details of a specific trace.

        Args:
            trace_id: The trace ID to query

        Returns:
            AgentTrace with full prompts, or None if not found
        """
        try:
            # Join with delegations to get accurate parent_agent
            result = self._conn.execute(
                """
                SELECT
                    t.trace_id, t.session_id, t.parent_trace_id,
                    COALESCE(d.parent_agent, t.parent_agent) as parent_agent,
                    t.subagent_type, t.prompt_input, t.prompt_output,
                    t.started_at, t.ended_at, t.duration_ms,
                    t.tokens_in, t.tokens_out, t.status, t.tools_used, t.child_session_id
                FROM agent_traces t
                LEFT JOIN delegations d ON t.trace_id = d.id
                WHERE t.trace_id = ?
                """,
                [trace_id],
            ).fetchone()

            if result:
                return self._row_to_trace(result)
            return None
        except Exception:
            return None

    def get_sessions_with_traces(self, limit: int = 50) -> list[SessionWithTraces]:
        """Get list of sessions that have agent traces.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of SessionWithTraces ordered by most recent first
        """
        try:
            results = self._conn.execute(
                """
                SELECT
                    t.session_id,
                    s.title,
                    COUNT(*) as trace_count,
                    MIN(t.started_at) as first_trace_at,
                    SUM(COALESCE(t.duration_ms, 0)) as total_duration_ms
                FROM agent_traces t
                LEFT JOIN sessions s ON t.session_id = s.id
                GROUP BY t.session_id, s.title
                ORDER BY first_trace_at DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()

            return [
                SessionWithTraces(
                    session_id=row[0],
                    title=row[1],
                    trace_count=row[2],
                    first_trace_at=row[3],
                    total_duration_ms=row[4] or 0,
                )
                for row in results
            ]
        except Exception:
            return []

    def get_trace_stats(self, start_date: datetime, end_date: datetime) -> dict:
        """Get aggregate statistics for traces in a period.

        Args:
            start_date: Start of the range
            end_date: End of the range

        Returns:
            Dict with total_traces, unique_agents, avg_duration_ms, etc.
        """
        try:
            result = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_traces,
                    COUNT(DISTINCT subagent_type) as unique_agents,
                    COUNT(DISTINCT session_id) as sessions_with_traces,
                    AVG(duration_ms) as avg_duration_ms,
                    SUM(duration_ms) as total_duration_ms,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                FROM agent_traces
                WHERE started_at >= ? AND started_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()

            if result:
                return {
                    "total_traces": result[0] or 0,
                    "unique_agents": result[1] or 0,
                    "sessions_with_traces": result[2] or 0,
                    "avg_duration_ms": int(result[3] or 0),
                    "total_duration_ms": result[4] or 0,
                    "completed": result[5] or 0,
                    "errors": result[6] or 0,
                }
            return {}
        except Exception:
            return {}

    def get_agent_type_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """Get trace statistics grouped by agent type.

        Args:
            start_date: Start of the range
            end_date: End of the range

        Returns:
            List of dicts with agent, count, avg_duration, etc.
        """
        try:
            results = self._conn.execute(
                """
                SELECT
                    subagent_type,
                    COUNT(*) as count,
                    AVG(duration_ms) as avg_duration_ms,
                    SUM(duration_ms) as total_duration_ms,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                FROM agent_traces
                WHERE started_at >= ? AND started_at <= ?
                GROUP BY subagent_type
                ORDER BY count DESC
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                {
                    "agent": row[0],
                    "count": row[1],
                    "avg_duration_ms": int(row[2] or 0),
                    "total_duration_ms": row[3] or 0,
                    "completed": row[4] or 0,
                }
                for row in results
            ]
        except Exception:
            return []

    def get_session_hierarchy(
        self, start_date: datetime, end_date: datetime, limit: int = 100
    ) -> list[SessionNode]:
        """Get sessions with their delegation hierarchy.

        Returns sessions as a tree structure based on delegations.
        Includes:
        - ROOT sessions (direct user conversations, parentID is NULL)
        - CHILD sessions (created via delegation, parentID is not NULL)

        Root sessions display with 🌳 icon and show user prompts.
        Child sessions display with 🔗 icon and show delegation info.

        Args:
            start_date: Start of the date range
            end_date: End of the date range
            limit: Maximum number of root sessions to return

        Returns:
            List of root SessionNode objects with children populated
        """
        try:
            # Get sessions including:
            # 1. ROOT sessions (parent_id IS NULL) that have activity
            # 2. Sessions that are part of delegation chains
            # 3. Sessions with traces
            results = self._conn.execute(
                """
                WITH relevant_sessions AS (
                    -- ROOT sessions (no parent) - these are direct user conversations
                    SELECT DISTINCT id as session_id FROM sessions WHERE parent_id IS NULL
                    UNION
                    -- Sessions that are parents (have children delegated to them)
                    SELECT DISTINCT parent_id as session_id FROM sessions WHERE parent_id IS NOT NULL
                    UNION
                    -- Sessions that are children (created by delegation)
                    SELECT DISTINCT id as session_id FROM sessions WHERE parent_id IS NOT NULL
                    UNION
                    -- Sessions with traces
                    SELECT DISTINCT session_id FROM agent_traces
                )
                SELECT
                    s.id as session_id,
                    s.title,
                    s.parent_id,
                    s.created_at,
                    s.directory,
                    d.parent_agent,
                    d.child_agent,
                    (SELECT COUNT(*) FROM agent_traces t WHERE t.session_id = s.id) as trace_count,
                    -- Get prompt: for ROOT from root trace, for CHILD from delegation trace
                    COALESCE(
                        (SELECT prompt_input FROM agent_traces t 
                         WHERE t.child_session_id = s.id AND t.trace_id LIKE 'root_%' 
                         LIMIT 1),
                        (SELECT prompt_input FROM agent_traces t 
                         WHERE t.child_session_id = s.id AND t.trace_id NOT LIKE 'root_%' 
                         LIMIT 1)
                    ) as root_prompt
                FROM sessions s
                LEFT JOIN delegations d ON s.id = d.child_session_id
                WHERE s.id IN (SELECT session_id FROM relevant_sessions)
                  AND s.created_at >= ? AND s.created_at <= ?
                ORDER BY s.created_at ASC
                """,
                [start_date, end_date],
            ).fetchall()

            # Build lookup
            sessions_by_id: dict[str, SessionNode] = {}
            for row in results:
                node = SessionNode(
                    session_id=row[0],
                    title=row[1],
                    parent_session_id=row[2],
                    created_at=row[3],
                    directory=row[4],
                    parent_agent=row[5],
                    agent_type=row[6],  # child_agent from delegation
                    trace_count=row[7] or 0,
                    prompt_input=row[8],  # Root prompt from agent_traces
                )
                sessions_by_id[node.session_id] = node

            # Build tree - find root sessions and attach children
            root_sessions: list[SessionNode] = []
            for session in sessions_by_id.values():
                if (
                    session.parent_session_id
                    and session.parent_session_id in sessions_by_id
                ):
                    parent = sessions_by_id[session.parent_session_id]
                    parent.children.append(session)
                else:
                    root_sessions.append(session)

            # Sort children by created_at (chronological order - oldest first)
            for session in sessions_by_id.values():
                session.children.sort(key=lambda s: s.created_at or datetime.min)

            # Sort root sessions by created_at DESC (most recent first) and limit
            root_sessions.sort(key=lambda s: s.created_at or datetime.min, reverse=True)
            return root_sessions[:limit]

        except Exception:
            return []

    def _row_to_trace(self, row: tuple) -> AgentTrace:
        """Convert a database row to AgentTrace object."""
        tools = row[13] if row[13] else []
        if isinstance(tools, str):
            # Handle case where tools_used is stored as string
            import json

            try:
                tools = json.loads(tools)
            except (json.JSONDecodeError, TypeError):
                tools = []

        return AgentTrace(
            trace_id=row[0],
            session_id=row[1],
            parent_trace_id=row[2],
            parent_agent=row[3],
            subagent_type=row[4],
            prompt_input=row[5] or "",
            prompt_output=row[6],
            started_at=row[7],
            ended_at=row[8],
            duration_ms=row[9],
            tokens_in=row[10],
            tokens_out=row[11],
            status=row[12] or "running",
            tools_used=tools,
            child_session_id=row[14] if len(row) > 14 else None,
        )
