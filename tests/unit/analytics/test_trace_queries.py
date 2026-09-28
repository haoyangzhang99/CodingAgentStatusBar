"""
Tests for Agent Trace queries and extraction.

Covers:
- extract_traces()
- load_traces()
- TraceQueries (get_traces_by_session, get_trace_tree, etc.)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.loader import extract_traces, load_traces
from opencode_status_bar.analytics.models import AgentTrace
from opencode_status_bar.analytics.queries.trace_queries import (
    TraceQueries,
    TraceTreeNode,
    SessionWithTraces,
)


# =============================================================================
# Fixtures (db is provided by conftest.py)
# =============================================================================


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    """Create a mock OpenCode storage structure."""
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "session").mkdir()
    (storage / "message").mkdir()
    (storage / "part").mkdir()
    return storage


def create_task_part(
    storage_path: Path,
    part_id: str,
    session_id: str,
    message_id: str,
    subagent_type: str,
    prompt: str,
    output: str | None = None,
    status: str = "completed",
    start_ts: int | None = None,
    end_ts: int | None = None,
    child_session_id: str | None = None,
    tools_summary: list[dict] | None = None,
) -> Path:
    """Create a task tool invocation part file."""
    if start_ts is None:
        start_ts = int(datetime.now().timestamp() * 1000)
    if end_ts is None:
        end_ts = start_ts + 5000  # 5 seconds

    part_dir = storage_path / "part" / message_id
    part_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "tool": "task",
        "state": {
            "status": status,
            "input": {
                "subagent_type": subagent_type,
                "prompt": prompt,
                "description": f"Invoke {subagent_type}",
            },
            "output": output,
            "time": {"start": start_ts, "end": end_ts},
            "metadata": {
                "sessionId": child_session_id,
                "summary": tools_summary or [],
            },
        },
    }

    part_file = part_dir / f"{part_id}.json"
    with open(part_file, "w") as f:
        json.dump(data, f)

    return part_file


# =============================================================================
# Test extract_traces
# =============================================================================


class TestExtractTraces:
    """Tests for extract_traces function."""

    def test_returns_empty_when_no_parts_directory(self, tmp_path: Path):
        """Should return empty list when parts directory doesn't exist."""
        storage = tmp_path / "nonexistent"
        traces = extract_traces(storage, max_days=30)
        assert traces == []

    def test_returns_empty_when_no_task_parts(self, storage_path: Path):
        """Should return empty list when no task tool parts exist."""
        # Create a non-task part
        msg_dir = storage_path / "part" / "msg_123"
        msg_dir.mkdir(parents=True)
        part_data = {
            "id": "prt_123",
            "sessionID": "ses_123",
            "messageID": "msg_123",
            "type": "tool",
            "tool": "read",
            "state": {"status": "completed"},
        }
        with open(msg_dir / "prt_123.json", "w") as f:
            json.dump(part_data, f)

        traces = extract_traces(storage_path, max_days=30)
        assert traces == []

    def test_extracts_task_invocation(self, storage_path: Path):
        """Should extract task tool invocations as traces."""
        create_task_part(
            storage_path,
            part_id="prt_001",
            session_id="ses_001",
            message_id="msg_001",
            subagent_type="tester",
            prompt="Write tests for the module",
            output="I have created 5 tests...",
        )

        traces = extract_traces(storage_path, max_days=30)

        assert len(traces) == 1
        trace = traces[0]
        assert trace.trace_id == "prt_001"
        assert trace.session_id == "ses_001"
        assert trace.subagent_type == "tester"
        assert trace.prompt_input == "Write tests for the module"
        assert trace.prompt_output == "I have created 5 tests..."
        assert trace.status == "completed"

    def test_extracts_timing_information(self, storage_path: Path):
        """Should extract start/end times and calculate duration."""
        start = int(datetime.now().timestamp() * 1000)
        end = start + 10000  # 10 seconds

        create_task_part(
            storage_path,
            part_id="prt_002",
            session_id="ses_002",
            message_id="msg_002",
            subagent_type="executor",
            prompt="Implement the feature",
            start_ts=start,
            end_ts=end,
        )

        traces = extract_traces(storage_path, max_days=30)

        assert len(traces) == 1
        trace = traces[0]
        assert trace.duration_ms == 10000
        # Verify timestamps are datetime objects with correct values
        assert isinstance(trace.started_at, datetime)
        assert isinstance(trace.ended_at, datetime)
        assert trace.started_at.timestamp() * 1000 == start
        assert trace.ended_at.timestamp() * 1000 == end

    def test_extracts_tools_used_from_summary(self, storage_path: Path):
        """Should extract tools used from metadata.summary."""
        tools_summary = [
            {"id": "prt_t1", "tool": "read", "state": {"status": "completed"}},
            {"id": "prt_t2", "tool": "write", "state": {"status": "completed"}},
            {"id": "prt_t3", "tool": "bash", "state": {"status": "completed"}},
        ]

        create_task_part(
            storage_path,
            part_id="prt_003",
            session_id="ses_003",
            message_id="msg_003",
            subagent_type="refactoring",
            prompt="Refactor the code",
            tools_summary=tools_summary,
        )

        traces = extract_traces(storage_path, max_days=30)

        assert len(traces) == 1
        trace = traces[0]
        assert trace.tools_used == ["read", "write", "bash"]

    def test_extracts_child_session_id(self, storage_path: Path):
        """Should extract child session ID from metadata."""
        create_task_part(
            storage_path,
            part_id="prt_004",
            session_id="ses_004",
            message_id="msg_004",
            subagent_type="quality",
            prompt="Review the code",
            child_session_id="ses_child_001",
        )

        traces = extract_traces(storage_path, max_days=30)

        assert len(traces) == 1
        assert traces[0].child_session_id == "ses_child_001"

    def test_skips_old_traces(self, storage_path: Path):
        """Should skip traces older than max_days."""
        import os

        old_time = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)

        create_task_part(
            storage_path,
            part_id="prt_old",
            session_id="ses_old",
            message_id="msg_old",
            subagent_type="tester",
            prompt="Old test",
            start_ts=old_time,
            end_ts=old_time + 1000,
        )

        # Set the directory's mtime to match the old timestamp
        # (extract_traces uses mtime-based filtering for performance)
        old_ts = old_time / 1000  # Convert ms to seconds
        msg_dir = storage_path / "part" / "msg_old"
        os.utime(msg_dir, (old_ts, old_ts))

        traces = extract_traces(storage_path, max_days=30)

        assert len(traces) == 0

    def test_handles_missing_subagent_type(self, storage_path: Path):
        """Should skip parts without subagent_type."""
        msg_dir = storage_path / "part" / "msg_no_type"
        msg_dir.mkdir(parents=True)

        part_data = {
            "id": "prt_no_type",
            "sessionID": "ses_no_type",
            "messageID": "msg_no_type",
            "type": "tool",
            "tool": "task",
            "state": {
                "status": "completed",
                "input": {"prompt": "No subagent type"},  # Missing subagent_type
            },
        }
        with open(msg_dir / "prt_no_type.json", "w") as f:
            json.dump(part_data, f)

        traces = extract_traces(storage_path, max_days=30)
        assert len(traces) == 0


# =============================================================================
# Test load_traces
# =============================================================================


class TestLoadTraces:
    """Tests for load_traces function."""

    def test_returns_zero_when_no_traces(
        self, temp_db: AnalyticsDB, storage_path: Path
    ):
        """Should return 0 when no traces to load."""
        count = load_traces(temp_db, storage_path, max_days=30)
        assert count == 0

    def test_loads_traces_into_database(self, temp_db: AnalyticsDB, storage_path: Path):
        """Should load extracted traces into database."""
        create_task_part(
            storage_path,
            part_id="prt_load_001",
            session_id="ses_load_001",
            message_id="msg_load_001",
            subagent_type="tester",
            prompt="Test the module",
            output="Tests created",
        )

        count = load_traces(temp_db, storage_path, max_days=30)

        assert count == 1

        # Verify in database
        conn = temp_db.connect()
        result = conn.execute(
            "SELECT trace_id, subagent_type, session_id, prompt_input, prompt_output FROM agent_traces"
        ).fetchone()
        assert result[0] == "prt_load_001"
        assert result[1] == "tester"
        assert result[2] == "ses_load_001"
        assert result[3] == "Test the module"
        assert result[4] == "Tests created"

    def test_creates_table_if_not_exists(self, tmp_path: Path, storage_path: Path):
        """Should create agent_traces table if it doesn't exist."""
        import duckdb

        # Create a bare database without schema
        db_path = tmp_path / "bare.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.close()

        db = AnalyticsDB(db_path)

        create_task_part(
            storage_path,
            part_id="prt_bare",
            session_id="ses_bare",
            message_id="msg_bare",
            subagent_type="executor",
            prompt="Execute",
        )

        # Should not raise error
        count = load_traces(db, storage_path, max_days=30)
        assert count == 1


# =============================================================================
# Test TraceQueries
# =============================================================================


class TestTraceQueries:
    """Tests for TraceQueries class."""

    @pytest.fixture
    def queries(self, temp_db: AnalyticsDB) -> TraceQueries:
        """Create TraceQueries instance."""
        return TraceQueries(temp_db)

    @pytest.fixture
    def populated_db(self, temp_db: AnalyticsDB) -> AnalyticsDB:
        """Populate database with test traces."""
        conn = temp_db.connect()

        # Insert test traces
        traces = [
            (
                "trace_1",
                "ses_a",
                None,
                "coordinator",
                "executor",
                "Execute task 1",
                "Done 1",
                "2026-01-01 10:00:00",
                "2026-01-01 10:05:00",
                300000,
                1000,
                500,
                "completed",
                [],
                "ses_child_1",
            ),
            (
                "trace_2",
                "ses_a",
                "trace_1",
                "executor",
                "tester",
                "Test task",
                "Tests done",
                "2026-01-01 10:02:00",
                "2026-01-01 10:04:00",
                120000,
                500,
                200,
                "completed",
                [],
                "ses_child_2",
            ),
            (
                "trace_3",
                "ses_b",
                None,
                "coordinator",
                "refactoring",
                "Refactor",
                "Refactored",
                "2026-01-01 11:00:00",
                "2026-01-01 11:10:00",
                600000,
                2000,
                1000,
                "completed",
                [],
                None,
            ),
        ]

        for t in traces:
            conn.execute(
                """INSERT INTO agent_traces 
                   (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                    prompt_input, prompt_output, started_at, ended_at, duration_ms,
                    tokens_in, tokens_out, status, tools_used, child_session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                list(t),
            )

        return temp_db

    def test_get_traces_by_session(self, populated_db: AnalyticsDB):
        """Should return all traces for a session."""
        queries = TraceQueries(populated_db)
        traces = queries.get_traces_by_session("ses_a")

        assert len(traces) == 2
        assert traces[0].trace_id == "trace_1"
        assert traces[1].trace_id == "trace_2"

    def test_get_traces_by_session_empty(self, queries: TraceQueries):
        """Should return empty list for non-existent session."""
        traces = queries.get_traces_by_session("nonexistent")
        assert traces == []

    def test_get_trace_details(self, populated_db: AnalyticsDB):
        """Should return full trace details."""
        queries = TraceQueries(populated_db)
        trace = queries.get_trace_details("trace_1")

        assert trace.trace_id == "trace_1"
        assert trace.session_id == "ses_a"
        assert trace.parent_trace_id is None
        assert trace.parent_agent == "coordinator"
        assert trace.subagent_type == "executor"
        assert trace.prompt_input == "Execute task 1"
        assert trace.prompt_output == "Done 1"
        assert trace.duration_ms == 300000
        assert trace.tokens_in == 1000
        assert trace.tokens_out == 500
        assert trace.status == "completed"
        assert trace.child_session_id == "ses_child_1"

    def test_get_trace_details_not_found(self, queries: TraceQueries):
        """Should return None for non-existent trace."""
        trace = queries.get_trace_details("nonexistent")
        assert trace is None

    def test_get_traces_by_date_range(self, populated_db: AnalyticsDB):
        """Should return traces within date range."""
        queries = TraceQueries(populated_db)
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 10, 30, 0)

        traces = queries.get_traces_by_date_range(start, end)

        assert len(traces) == 2  # trace_1 and trace_2

    def test_get_traces_by_agent(self, populated_db: AnalyticsDB):
        """Should return traces for specific agent type."""
        queries = TraceQueries(populated_db)
        traces = queries.get_traces_by_agent("tester")

        assert len(traces) == 1
        assert traces[0].subagent_type == "tester"

    def test_get_sessions_with_traces(self, populated_db: AnalyticsDB):
        """Should return sessions that have traces."""
        queries = TraceQueries(populated_db)
        sessions = queries.get_sessions_with_traces()

        assert len(sessions) == 2
        # Verify session IDs
        session_ids = [s.session_id for s in sessions]
        assert "ses_a" in session_ids
        assert "ses_b" in session_ids

        # Verify trace counts
        ses_a = next(s for s in sessions if s.session_id == "ses_a")
        ses_b = next(s for s in sessions if s.session_id == "ses_b")
        assert ses_a.trace_count == 2
        assert ses_b.trace_count == 1

    def test_get_trace_stats(self, populated_db: AnalyticsDB):
        """Should return aggregate statistics."""
        queries = TraceQueries(populated_db)
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 2)

        stats = queries.get_trace_stats(start, end)

        assert stats["total_traces"] == 3
        assert stats["unique_agents"] == 3  # executor, tester, refactoring
        assert stats["sessions_with_traces"] == 2
        assert stats["completed"] == 3

    def test_get_agent_type_stats(self, populated_db: AnalyticsDB):
        """Should return stats grouped by agent type."""
        queries = TraceQueries(populated_db)
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 2)

        stats = queries.get_agent_type_stats(start, end)

        assert len(stats) == 3
        agent_names = [s["agent"] for s in stats]
        assert "executor" in agent_names
        assert "tester" in agent_names
        assert "refactoring" in agent_names

        # Verify each agent has required fields
        for agent_stat in stats:
            assert "agent" in agent_stat
            assert "count" in agent_stat
            assert agent_stat["count"] >= 1


class TestTraceTreeNode:
    """Tests for TraceTreeNode dataclass."""

    def test_creates_node_with_trace(self):
        """Should create a tree node with trace."""
        trace = AgentTrace(
            trace_id="t1",
            session_id="s1",
            subagent_type="executor",
            prompt_input="Test",
        )
        node = TraceTreeNode(trace=trace, depth=0)

        assert node.trace == trace
        assert node.depth == 0
        assert node.children == []

    def test_node_can_have_children(self):
        """Should allow adding children to node."""
        parent_trace = AgentTrace(
            trace_id="t1",
            session_id="s1",
            subagent_type="executor",
            prompt_input="Parent",
        )
        child_trace = AgentTrace(
            trace_id="t2", session_id="s2", subagent_type="tester", prompt_input="Child"
        )

        parent = TraceTreeNode(trace=parent_trace, depth=0)
        child = TraceTreeNode(trace=child_trace, depth=1)
        parent.children.append(child)

        assert len(parent.children) == 1
        assert parent.children[0].trace.trace_id == "t2"


class TestSessionWithTraces:
    """Tests for SessionWithTraces dataclass."""

    def test_creates_session_with_traces(self):
        """Should create session with trace metadata."""
        session = SessionWithTraces(
            session_id="ses_123",
            title="Test Session",
            trace_count=5,
            first_trace_at=datetime(2026, 1, 1, 10, 0),
            total_duration_ms=60000,
        )

        assert session.session_id == "ses_123"
        assert session.title == "Test Session"
        assert session.trace_count == 5
        assert session.total_duration_ms == 60000
