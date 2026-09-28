"""
Tests for TraceBuilder - Plan 45 trace table building.

Tests the exchanges, exchange_traces, and session_traces building functionality.
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.indexer.trace_builder import TraceBuilder
from opencode_status_bar.analytics.indexer.trace_builder.helpers import extract_prompt


class TestExtractPrompt:
    """Tests for extract_prompt helper function."""

    def test_empty_arguments(self):
        assert extract_prompt(None) == ""
        assert extract_prompt("") == ""

    def test_invalid_json(self):
        assert extract_prompt("not json") == ""

    def test_prompt_only(self):
        args = json.dumps({"prompt": "Analyze the code"})
        assert extract_prompt(args) == "Analyze the code"

    def test_description_only(self):
        args = json.dumps({"description": "Task description"})
        assert extract_prompt(args) == "Task description"

    def test_combined_description_and_prompt(self):
        args = json.dumps(
            {"description": "Task description", "prompt": "Detailed prompt here"}
        )
        result = extract_prompt(args)
        assert result == "Task description\n\nDetailed prompt here"

    def test_empty_fields(self):
        args = json.dumps({"prompt": "", "description": ""})
        assert extract_prompt(args) == ""

    def test_description_with_empty_prompt(self):
        args = json.dumps({"description": "Just description", "prompt": ""})
        assert extract_prompt(args) == "Just description"

    def test_prompt_with_empty_description(self):
        args = json.dumps({"description": "", "prompt": "Just prompt"})
        assert extract_prompt(args) == "Just prompt"


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        db = AnalyticsDB(db_path=db_path)
        db.connect()
        yield db
        db.close()


@pytest.fixture
def trace_builder(temp_db):
    """Create a TraceBuilder with the temporary database."""
    return TraceBuilder(temp_db)


class TestBuildExchangesEmpty:
    """Tests for build_exchanges with empty database."""

    def test_build_exchanges_empty_db(self, trace_builder, temp_db):
        """build_exchanges returns 0 when no messages exist."""
        count = trace_builder.build_exchanges()
        assert count == 0

        # Verify table is empty
        conn = temp_db.connect()
        result = conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()
        assert result[0] == 0

    def test_build_exchanges_with_session_filter_empty(self, trace_builder):
        """build_exchanges with session filter returns 0 for non-existent session."""
        count = trace_builder.build_exchanges(session_id="non_existent")
        assert count == 0


class TestBuildExchangesCreatesRecords:
    """Tests for build_exchanges with data."""

    def test_build_exchanges_creates_records(self, trace_builder, temp_db):
        """build_exchanges creates exchange records from message pairs."""
        conn = temp_db.connect()

        # Create a session
        session_id = "test_session_1"
        now = datetime.now()
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [session_id, "proj1", "/test", "Test Session", now, now],
        )

        # Create user message
        user_msg_id = "msg_user_1"
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, agent, model_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [user_msg_id, session_id, "user", None, None, now],
        )

        # Create user text part
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["prt_user_1", session_id, user_msg_id, "text", "Hello, AI!", now],
        )

        # Create assistant message (with parent_id linking to user message)
        assistant_msg_id = "msg_asst_1"
        assistant_time = now + timedelta(seconds=5)
        conn.execute(
            """
            INSERT INTO messages (id, session_id, parent_id, role, agent, model_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                assistant_msg_id,
                session_id,
                user_msg_id,
                "assistant",
                "dev",
                "claude-4",
                assistant_time,
            ],
        )

        # Create assistant text part
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "prt_asst_1",
                session_id,
                assistant_msg_id,
                "text",
                "Hello! How can I help?",
                assistant_time,
            ],
        )

        # Build exchanges
        count = trace_builder.build_exchanges()
        assert count == 1

        # Verify exchange record
        result = conn.execute(
            "SELECT * FROM exchanges WHERE session_id = ?", [session_id]
        ).fetchone()
        assert result is not None

        # Get column names
        columns = [
            desc[0] for desc in conn.execute("SELECT * FROM exchanges").description
        ]
        exchange = dict(zip(columns, result))

        assert exchange["session_id"] == session_id
        assert exchange["exchange_number"] == 1
        assert exchange["user_message_id"] == user_msg_id
        assert exchange["assistant_message_id"] == assistant_msg_id
        assert exchange["prompt_input"] == "Hello, AI!"
        assert exchange["prompt_output"] == "Hello! How can I help?"
        assert exchange["agent"] == "dev"
        assert exchange["model_id"] == "claude-4"

    def test_build_exchanges_multiple_exchanges(self, trace_builder, temp_db):
        """build_exchanges handles multiple exchanges in a session."""
        conn = temp_db.connect()

        session_id = "test_session_multi"
        now = datetime.now()

        # Create session
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [session_id, "proj1", "/test", "Multi Exchange", now, now],
        )

        # Create 3 user-assistant pairs
        for i in range(3):
            user_time = now + timedelta(seconds=i * 10)
            asst_time = user_time + timedelta(seconds=5)

            # User message
            user_msg_id = f"msg_user_{i}"
            conn.execute(
                """
                INSERT INTO messages (id, session_id, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [user_msg_id, session_id, "user", user_time],
            )
            conn.execute(
                """
                INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    f"prt_u_{i}",
                    session_id,
                    user_msg_id,
                    "text",
                    f"Question {i}",
                    user_time,
                ],
            )

            # Assistant message
            asst_msg_id = f"msg_asst_{i}"
            conn.execute(
                """
                INSERT INTO messages (id, session_id, parent_id, role, agent, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [asst_msg_id, session_id, user_msg_id, "assistant", "dev", asst_time],
            )
            conn.execute(
                """
                INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    f"prt_a_{i}",
                    session_id,
                    asst_msg_id,
                    "text",
                    f"Answer {i}",
                    asst_time,
                ],
            )

        # Build exchanges
        count = trace_builder.build_exchanges()
        assert count == 3

        # Verify ordering
        results = conn.execute(
            """
            SELECT exchange_number, prompt_input, prompt_output
            FROM exchanges
            WHERE session_id = ?
            ORDER BY exchange_number
            """,
            [session_id],
        ).fetchall()

        assert len(results) == 3
        for i, row in enumerate(results):
            assert row[0] == i + 1  # exchange_number is 1-based
            assert row[1] == f"Question {i}"
            assert row[2] == f"Answer {i}"


class TestBuildExchangeTracesOrdering:
    """Tests for build_exchange_traces event ordering."""

    def test_build_exchange_traces_ordering(self, trace_builder, temp_db):
        """build_exchange_traces orders events chronologically within exchange."""
        conn = temp_db.connect()

        session_id = "test_session_traces"
        now = datetime.now()

        # Create session
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [session_id, "proj1", "/test", "Trace Test", now, now],
        )

        # Create user message and part
        user_msg_id = "msg_user_t"
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [user_msg_id, session_id, "user", now],
        )
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["prt_u_t", session_id, user_msg_id, "text", "Do something", now],
        )

        # Create assistant message
        asst_msg_id = "msg_asst_t"
        asst_time = now + timedelta(seconds=1)
        conn.execute(
            """
            INSERT INTO messages (id, session_id, parent_id, role, agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [asst_msg_id, session_id, user_msg_id, "assistant", "dev", asst_time],
        )

        # Create parts in reverse chronological order to test ordering
        # 1. Tool call (t+2s)
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "prt_tool",
                session_id,
                asst_msg_id,
                "tool",
                "read",
                "completed",
                asst_time + timedelta(seconds=1),
            ],
        )

        # 2. Reasoning (t+1s)
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, reasoning_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "prt_reason",
                session_id,
                asst_msg_id,
                "reasoning",
                "Let me think...",
                asst_time,
            ],
        )

        # 3. Response text (t+3s)
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "prt_resp",
                session_id,
                asst_msg_id,
                "text",
                "Done!",
                asst_time + timedelta(seconds=2),
            ],
        )

        # First build exchanges (required for exchange_traces)
        trace_builder.build_exchanges()

        # Build exchange traces
        count = trace_builder.build_exchange_traces()
        assert count >= 3  # At least user_prompt, reasoning, tool_call

        # Verify event ordering
        results = conn.execute(
            """
            SELECT event_type, event_order
            FROM exchange_traces
            WHERE session_id = ?
            ORDER BY event_order
            """,
            [session_id],
        ).fetchall()

        # First event should be user_prompt
        assert results[0][0] == "user_prompt"
        assert results[0][1] == 1

        # Events should be in ascending order
        orders = [r[1] for r in results]
        assert orders == sorted(orders)


class TestBuildSessionTraces:
    """Tests for build_session_traces."""

    def test_build_session_traces_empty_db(self, trace_builder, temp_db):
        """build_session_traces returns 0 when no sessions exist."""
        count = trace_builder.build_session_traces()
        assert count == 0

    def test_build_session_traces_creates_records(self, trace_builder, temp_db):
        """build_session_traces creates session trace records."""
        conn = temp_db.connect()

        session_id = "test_session_st"
        now = datetime.now()

        # Create session
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [session_id, "proj1", "/test/project", "My Session", now, now],
        )

        # Build session traces
        count = trace_builder.build_session_traces()
        assert count == 1

        # Verify session trace record
        result = conn.execute(
            "SELECT * FROM session_traces WHERE session_id = ?", [session_id]
        ).fetchone()
        assert result is not None

        columns = [
            desc[0] for desc in conn.execute("SELECT * FROM session_traces").description
        ]
        trace = dict(zip(columns, result))

        assert trace["session_id"] == session_id
        assert trace["title"] == "My Session"
        assert trace["directory"] == "/test/project"
        assert trace["depth"] == 0


class TestBuildAll:
    """Tests for build_all orchestration."""

    def test_build_all_returns_stats(self, trace_builder, temp_db):
        """build_all returns counts for all tables."""
        result = trace_builder.build_all()

        assert isinstance(result, dict)
        assert "exchanges" in result
        assert "exchange_traces" in result
        assert "session_traces" in result
        assert result["exchanges"] == 0
        assert result["exchange_traces"] == 0
        assert result["session_traces"] == 0

    def test_build_all_with_data(self, trace_builder, temp_db):
        """build_all builds all tables with data."""
        conn = temp_db.connect()

        session_id = "test_all"
        now = datetime.now()

        # Create session
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [session_id, "proj1", "/test", "Test All", now, now],
        )

        # Create user message
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ["msg_u_all", session_id, "user", now],
        )
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["prt_u_all", session_id, "msg_u_all", "text", "Hello", now],
        )

        # Create assistant message
        conn.execute(
            """
            INSERT INTO messages (id, session_id, parent_id, role, agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "msg_a_all",
                session_id,
                "msg_u_all",
                "assistant",
                "dev",
                now + timedelta(seconds=1),
            ],
        )
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "prt_a_all",
                session_id,
                "msg_a_all",
                "text",
                "Hi!",
                now + timedelta(seconds=1),
            ],
        )

        result = trace_builder.build_all()

        assert result["exchanges"] == 1
        assert result["exchange_traces"] >= 1
        assert result["session_traces"] == 1


class TestBuildWithSessionFilter:
    """Tests for building with session_id filter."""

    def test_build_exchanges_filters_by_session(self, trace_builder, temp_db):
        """build_exchanges with session_id only builds for that session."""
        conn = temp_db.connect()
        now = datetime.now()

        # Create two sessions
        for i in range(2):
            session_id = f"session_{i}"
            conn.execute(
                """
                INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [session_id, "proj1", "/test", f"Session {i}", now, now],
            )

            # User message
            conn.execute(
                """
                INSERT INTO messages (id, session_id, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [f"msg_u_{i}", session_id, "user", now],
            )
            conn.execute(
                """
                INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [f"prt_u_{i}", session_id, f"msg_u_{i}", "text", f"Q{i}", now],
            )

            # Assistant message
            conn.execute(
                """
                INSERT INTO messages (id, session_id, parent_id, role, agent, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    f"msg_a_{i}",
                    session_id,
                    f"msg_u_{i}",
                    "assistant",
                    "dev",
                    now + timedelta(seconds=1),
                ],
            )
            conn.execute(
                """
                INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    f"prt_a_{i}",
                    session_id,
                    f"msg_a_{i}",
                    "text",
                    f"A{i}",
                    now + timedelta(seconds=1),
                ],
            )

        # Build only for session_0
        count = trace_builder.build_exchanges(session_id="session_0")
        assert count == 1

        # Verify only session_0 has exchanges
        result = conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()
        assert result[0] == 1

        result = conn.execute("SELECT session_id FROM exchanges").fetchone()
        assert result[0] == "session_0"


class TestRebuildBehavior:
    """Tests for rebuild (DELETE before INSERT) behavior."""

    def test_build_exchanges_deletes_existing(self, trace_builder, temp_db):
        """build_exchanges deletes existing exchanges before rebuilding."""
        conn = temp_db.connect()
        now = datetime.now()

        session_id = "rebuild_test"
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [session_id, "proj1", "/test", "Rebuild Test", now, now],
        )

        # Create messages
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ["msg_u_rb", session_id, "user", now],
        )
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["prt_u_rb", session_id, "msg_u_rb", "text", "Original", now],
        )
        conn.execute(
            """
            INSERT INTO messages (id, session_id, parent_id, role, agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "msg_a_rb",
                session_id,
                "msg_u_rb",
                "assistant",
                "dev",
                now + timedelta(seconds=1),
            ],
        )
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "prt_a_rb",
                session_id,
                "msg_a_rb",
                "text",
                "Response",
                now + timedelta(seconds=1),
            ],
        )

        # Build first time
        count1 = trace_builder.build_exchanges()
        assert count1 == 1

        # Build again - should still have only 1 (not 2)
        count2 = trace_builder.build_exchanges()
        assert count2 == 1

        # Verify only 1 exchange exists
        result = conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()
        assert result[0] == 1


class TestDelegationLinkage:
    """Tests for delegation parent-child linking and depth calculation."""

    def test_session_traces_root_depth_zero(self, trace_builder, temp_db):
        """Root sessions (no parent) have depth=0."""
        conn = temp_db.connect()
        now = datetime.now()

        # Create root session (no parent delegation)
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["ses_root", "proj1", "/test", "Root Session", now, now],
        )

        # Build session traces
        count = trace_builder.build_session_traces()
        assert count == 1

        # Verify depth is 0
        result = conn.execute(
            """
            SELECT depth, parent_session_id FROM session_traces
            WHERE session_id = 'ses_root'
            """
        ).fetchone()
        assert result[0] == 0  # depth
        assert result[1] is None  # no parent

    def test_session_traces_child_depth_one(self, trace_builder, temp_db):
        """Direct child of root has depth=1."""
        conn = temp_db.connect()
        now = datetime.now()

        # Create root session
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["ses_parent", "proj1", "/test", "Parent Session", now, now],
        )

        # Create child session
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["ses_child", "proj1", "/test", "Child Session", now, now],
        )

        # Create delegation linking parent to child
        conn.execute(
            """
            INSERT INTO delegations (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["del_1", "msg_1", "ses_parent", "plan", "dev", "ses_child", now],
        )

        # Build session traces
        count = trace_builder.build_session_traces()
        assert count == 2

        # Verify parent depth is 0
        parent_result = conn.execute(
            "SELECT depth, parent_session_id FROM session_traces WHERE session_id = 'ses_parent'"
        ).fetchone()
        assert parent_result[0] == 0  # depth
        assert parent_result[1] is None  # no parent

        # Verify child depth is 1 and has correct parent
        child_result = conn.execute(
            "SELECT depth, parent_session_id FROM session_traces WHERE session_id = 'ses_child'"
        ).fetchone()
        assert child_result[0] == 1  # depth
        assert child_result[1] == "ses_parent"  # parent_session_id

    def test_session_traces_nested_depth(self, trace_builder, temp_db):
        """Nested delegations have increasing depth (grandchild = depth 2)."""
        conn = temp_db.connect()
        now = datetime.now()

        # Create 3-level hierarchy: root -> child -> grandchild
        for ses_id, title in [
            ("ses_root", "Root"),
            ("ses_child", "Child"),
            ("ses_grandchild", "Grandchild"),
        ]:
            conn.execute(
                """
                INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [ses_id, "proj1", "/test", title, now, now],
            )

        # Link root -> child
        conn.execute(
            """
            INSERT INTO delegations (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["del_1", "msg_1", "ses_root", "plan", "dev", "ses_child", now],
        )

        # Link child -> grandchild
        conn.execute(
            """
            INSERT INTO delegations (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["del_2", "msg_2", "ses_child", "dev", "tester", "ses_grandchild", now],
        )

        # Build session traces
        count = trace_builder.build_session_traces()
        assert count == 3

        # Verify depths
        results = conn.execute(
            """
            SELECT session_id, depth, parent_session_id
            FROM session_traces
            ORDER BY depth
            """
        ).fetchall()

        depths = {r[0]: (r[1], r[2]) for r in results}

        assert depths["ses_root"] == (0, None)
        assert depths["ses_child"] == (1, "ses_root")
        assert depths["ses_grandchild"] == (2, "ses_child")

    @pytest.mark.skip(
        reason="_calculate_delegation_depth is now part of MaterializedTableManager internal implementation"
    )
    def test_calculate_delegation_depth_method(self, trace_builder, temp_db):
        """_calculate_delegation_depth returns correct depth for any session."""
        conn = temp_db.connect()
        now = datetime.now()

        # Create 3-level hierarchy
        for ses_id in ["ses_a", "ses_b", "ses_c"]:
            conn.execute(
                """
                INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [ses_id, "proj1", "/test", ses_id, now, now],
            )

        # a -> b -> c
        conn.execute(
            """
            INSERT INTO delegations (id, message_id, session_id, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ["d1", "m1", "ses_a", "ses_b", now],
        )
        conn.execute(
            """
            INSERT INTO delegations (id, message_id, session_id, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ["d2", "m2", "ses_b", "ses_c", now],
        )

        # Test depth calculation
        assert trace_builder._calculate_delegation_depth("ses_a") == 0
        assert trace_builder._calculate_delegation_depth("ses_b") == 1
        assert trace_builder._calculate_delegation_depth("ses_c") == 2

    def test_session_traces_with_parent_trace_id(self, trace_builder, temp_db):
        """session_traces includes parent_trace_id from agent_traces."""
        conn = temp_db.connect()
        now = datetime.now()

        # Create parent and child sessions
        for ses_id in ["ses_parent", "ses_child"]:
            conn.execute(
                """
                INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [ses_id, "proj1", "/test", ses_id, now, now],
            )

        # Create delegation
        conn.execute(
            """
            INSERT INTO delegations (id, message_id, session_id, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ["del_abc", "msg_1", "ses_parent", "ses_child", now],
        )

        # Create agent_trace that links to child session
        conn.execute(
            """
            INSERT INTO agent_traces (trace_id, session_id, subagent_type, prompt_input, started_at, child_session_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["del_abc", "ses_parent", "dev", "Do something", now, "ses_child"],
        )

        # Build session traces
        trace_builder.build_session_traces()

        # Verify child session has correct parent_trace_id
        result = conn.execute(
            """
            SELECT parent_trace_id FROM session_traces
            WHERE session_id = 'ses_child'
            """
        ).fetchone()

        assert result[0] == "del_abc"


class TestDelegationResultEventType:
    """Tests for delegation_result event type in exchange_traces materialization."""

    def test_delegation_result_created_for_tool_with_child_session(
        self, trace_builder, temp_db
    ):
        """delegation_result event is created for tool calls with child_session_id and result_summary."""
        conn = temp_db.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["ses_deleg", "proj1", "/test", "Delegation Test", now, now],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ["msg_u", "ses_deleg", "user", None, now],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, parent_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "msg_a",
                "ses_deleg",
                "assistant",
                "build",
                "msg_u",
                now + timedelta(seconds=1),
            ],
        )

        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["prt_u", "ses_deleg", "msg_u", "text", "Hello", now],
        )

        conn.execute(
            """INSERT INTO parts 
               (id, session_id, message_id, part_type, tool_name, child_session_id, 
                result_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt_tool",
                "ses_deleg",
                "msg_a",
                "tool",
                "mcp_task",
                "ses_child_123",
                "Task completed successfully",
                now + timedelta(seconds=2),
            ],
        )

        trace_builder.build_exchanges()
        count = trace_builder.build_exchange_traces()

        results = conn.execute(
            """SELECT event_type, event_data FROM exchange_traces
               WHERE session_id = 'ses_deleg' AND event_type = 'delegation_result'"""
        ).fetchall()

        assert len(results) == 1
        assert results[0][0] == "delegation_result"

        import json

        event_data = json.loads(results[0][1])
        assert event_data["tool_name"] == "mcp_task"
        assert event_data["child_session_id"] == "ses_child_123"
        assert event_data["result_summary"] == "Task completed successfully"

    def test_no_delegation_result_without_child_session(self, trace_builder, temp_db):
        """delegation_result is NOT created for tool calls without child_session_id."""
        conn = temp_db.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["ses_no_deleg", "proj1", "/test", "No Delegation Test", now, now],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ["msg_u2", "ses_no_deleg", "user", None, now],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, parent_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "msg_a2",
                "ses_no_deleg",
                "assistant",
                "build",
                "msg_u2",
                now + timedelta(seconds=1),
            ],
        )

        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["prt_u2", "ses_no_deleg", "msg_u2", "text", "Hello", now],
        )

        conn.execute(
            """INSERT INTO parts 
               (id, session_id, message_id, part_type, tool_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "prt_tool2",
                "ses_no_deleg",
                "msg_a2",
                "tool",
                "bash",
                now + timedelta(seconds=2),
            ],
        )

        trace_builder.build_exchanges()
        trace_builder.build_exchange_traces()

        results = conn.execute(
            """SELECT event_type FROM exchange_traces
               WHERE session_id = 'ses_no_deleg' AND event_type = 'delegation_result'"""
        ).fetchall()

        assert len(results) == 0

    def test_no_delegation_result_without_result_summary(self, trace_builder, temp_db):
        """delegation_result is NOT created for tool calls without result_summary."""
        conn = temp_db.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["ses_no_summary", "proj1", "/test", "No Summary Test", now, now],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ["msg_u3", "ses_no_summary", "user", None, now],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, parent_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "msg_a3",
                "ses_no_summary",
                "assistant",
                "build",
                "msg_u3",
                now + timedelta(seconds=1),
            ],
        )

        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["prt_u3", "ses_no_summary", "msg_u3", "text", "Hello", now],
        )

        conn.execute(
            """INSERT INTO parts 
               (id, session_id, message_id, part_type, tool_name, child_session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt_tool3",
                "ses_no_summary",
                "msg_a3",
                "tool",
                "mcp_task",
                "ses_child_456",
                now + timedelta(seconds=2),
            ],
        )

        trace_builder.build_exchanges()
        trace_builder.build_exchange_traces()

        results = conn.execute(
            """SELECT event_type FROM exchange_traces
               WHERE session_id = 'ses_no_summary' AND event_type = 'delegation_result'"""
        ).fetchall()

        assert len(results) == 0
