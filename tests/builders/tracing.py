"""
TraceBuilder - Fluent builder for trace tree test data.

Usage:
    # Create a simple trace tree
    tree = (TraceBuilder()
        .with_root("sess-001", "Main session")
        .add_delegation("trace-001", "executor")
        .add_delegation("trace-002", "tester")
        .build())

    # Create a nested tree
    tree = (TraceBuilder()
        .with_root("sess-001", "Main session")
        .add_delegation("trace-001", "executor")
        .add_child_delegation("trace-001", "trace-002", "subtask")
        .build())
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode_status_bar.analytics.db import AnalyticsDB


class TraceBuilder:
    """Fluent builder for creating trace tree test data."""

    def __init__(self, db: AnalyticsDB | None = None):
        """Initialize builder with optional database connection.

        Args:
            db: Optional AnalyticsDB for insert operations
        """
        self._db = db
        self._reset()

    def _reset(self) -> None:
        """Reset builder to default values."""
        self._root_session_id: str | None = None
        self._root_title = "Test Session"
        self._root_directory = "/home/user/project"
        self._traces: list[dict[str, Any]] = []
        self._messages: list[dict[str, Any]] = []
        self._base_time = datetime.now()
        self._time_offset = 0  # milliseconds offset for ordering

    # =========================================================================
    # Fluent setters
    # =========================================================================

    def with_root(
        self,
        session_id: str,
        title: str = "Main Session",
        directory: str = "/home/user/project",
    ) -> TraceBuilder:
        """Set root session info.

        Args:
            session_id: Root session ID
            title: Session title
            directory: Working directory

        Returns:
            Self for chaining
        """
        self._root_session_id = session_id
        self._root_title = title
        self._root_directory = directory
        return self

    def with_base_time(self, base_time: datetime) -> TraceBuilder:
        """Set base time for all traces.

        Args:
            base_time: Base datetime for trace timestamps

        Returns:
            Self for chaining
        """
        self._base_time = base_time
        return self

    def add_delegation(
        self,
        trace_id: str,
        subagent_type: str = "executor",
        status: str = "completed",
        duration_ms: int = 5000,
        tokens_in: int = 500,
        tokens_out: int = 250,
    ) -> TraceBuilder:
        """Add a delegation trace directly under root.

        Args:
            trace_id: Unique trace ID
            subagent_type: Type of agent (executor, tester, etc.)
            status: Trace status (running, completed, error)
            duration_ms: Duration in milliseconds
            tokens_in: Input tokens
            tokens_out: Output tokens

        Returns:
            Self for chaining
        """
        if not self._root_session_id:
            raise ValueError("Must call with_root() before add_delegation()")

        self._time_offset += 1000  # Advance time for ordering
        started_at = self._base_time + timedelta(milliseconds=self._time_offset)

        self._traces.append(
            {
                "trace_id": trace_id,
                "session_id": self._root_session_id,
                "parent_trace_id": f"root_{self._root_session_id}",
                "subagent_type": subagent_type,
                "status": status,
                "duration_ms": duration_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "started_at": started_at,
                "parent_agent": "user",
            }
        )
        return self

    def add_child_delegation(
        self,
        parent_trace_id: str,
        trace_id: str,
        subagent_type: str = "subtask",
        status: str = "completed",
        duration_ms: int = 2000,
        tokens_in: int = 200,
        tokens_out: int = 100,
    ) -> TraceBuilder:
        """Add a nested delegation trace.

        Args:
            parent_trace_id: Parent trace ID
            trace_id: Unique trace ID
            subagent_type: Type of agent
            status: Trace status
            duration_ms: Duration in milliseconds
            tokens_in: Input tokens
            tokens_out: Output tokens

        Returns:
            Self for chaining
        """
        if not self._root_session_id:
            raise ValueError("Must call with_root() before add_child_delegation()")

        # Find parent to get its agent type
        parent_agent = "executor"
        for trace in self._traces:
            if trace["trace_id"] == parent_trace_id:
                parent_agent = trace["subagent_type"]
                break

        self._time_offset += 500
        started_at = self._base_time + timedelta(milliseconds=self._time_offset)

        self._traces.append(
            {
                "trace_id": trace_id,
                "session_id": self._root_session_id,
                "parent_trace_id": parent_trace_id,
                "subagent_type": subagent_type,
                "status": status,
                "duration_ms": duration_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "started_at": started_at,
                "parent_agent": parent_agent,
            }
        )
        return self

    def add_message(
        self,
        trace_id: str,
        message_id: str | None = None,
        role: str = "assistant",
        agent: str | None = None,
        tokens_in: int = 100,
        tokens_out: int = 50,
    ) -> TraceBuilder:
        """Add a message to a trace.

        Args:
            trace_id: Trace to add message to
            message_id: Optional message ID (auto-generated if not provided)
            role: Message role
            agent: Agent type (defaults to trace's subagent_type)
            tokens_in: Input tokens
            tokens_out: Output tokens

        Returns:
            Self for chaining
        """
        if message_id is None:
            message_id = f"msg-{uuid.uuid4().hex[:8]}"

        # Find trace to get session_id and agent
        session_id = self._root_session_id
        if agent is None:
            for trace in self._traces:
                if trace["trace_id"] == trace_id:
                    agent = trace["subagent_type"]
                    break
            else:
                agent = "main"

        self._time_offset += 100
        created_at = self._base_time + timedelta(milliseconds=self._time_offset)

        self._messages.append(
            {
                "id": message_id,
                "session_id": session_id,
                "trace_id": trace_id,
                "role": role,
                "agent": agent,
                "created_at": created_at,
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
            }
        )
        return self

    # =========================================================================
    # Output methods
    # =========================================================================

    def build(self) -> dict[str, Any]:
        """Build trace tree as a dictionary.

        Returns:
            Trace tree data with session, traces, and messages
        """
        return {
            "session": {
                "id": self._root_session_id,
                "title": self._root_title,
                "directory": self._root_directory,
                "created_at": self._base_time.isoformat(),
            },
            "traces": [
                {**t, "started_at": t["started_at"].isoformat()} for t in self._traces
            ],
            "messages": [
                {**m, "created_at": m["created_at"].isoformat()} for m in self._messages
            ],
        }

    def build_flat_traces(self) -> list[dict[str, Any]]:
        """Build just the traces as a flat list.

        Returns:
            List of trace dicts
        """
        return [{**t, "started_at": t["started_at"].isoformat()} for t in self._traces]

    def insert(self) -> str:
        """Insert all data into database.

        Returns:
            Root session ID

        Raises:
            ValueError: If no database connection or no root session
        """
        if not self._db:
            raise ValueError("No database connection. Pass db to TraceBuilder(db)")
        if not self._root_session_id:
            raise ValueError("Must call with_root() before insert()")

        conn = self._db.connect()

        # Insert session
        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                self._root_session_id,
                self._root_directory,
                self._root_title,
                self._base_time,
                self._base_time,
            ],
        )

        # Insert traces
        for trace in self._traces:
            conn.execute(
                """
                INSERT INTO traces (
                    trace_id, session_id, parent_trace_id, subagent_type,
                    parent_agent, status, started_at, tokens_in, tokens_out, duration_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    trace["trace_id"],
                    trace["session_id"],
                    trace["parent_trace_id"],
                    trace["subagent_type"],
                    trace["parent_agent"],
                    trace["status"],
                    trace["started_at"],
                    trace["tokens_in"],
                    trace["tokens_out"],
                    trace["duration_ms"],
                ],
            )

        # Insert messages
        for msg in self._messages:
            conn.execute(
                """
                INSERT INTO messages (
                    id, session_id, role, agent, created_at,
                    tokens_input, tokens_output
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    msg["id"],
                    msg["session_id"],
                    msg["role"],
                    msg["agent"],
                    msg["created_at"],
                    msg["tokens_input"],
                    msg["tokens_output"],
                ],
            )

        return self._root_session_id

    @property
    def root_session_id(self) -> str | None:
        """Get the root session ID."""
        return self._root_session_id

    @property
    def trace_count(self) -> int:
        """Get number of traces."""
        return len(self._traces)

    @property
    def message_count(self) -> int:
        """Get number of messages."""
        return len(self._messages)
