"""
Tests for trace builder token aggregation.

These tests verify that:
1. Tokens are correctly aggregated from child session messages
2. create_trace_from_delegation updates tokens immediately
3. backfill_missing_tokens fixes traces created before messages

This is a regression test for the bug where subagent traces had
tokens: None because messages were indexed before the trace was created.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.indexer.trace_builder.builder import TraceBuilder
from opencode_status_bar.analytics.indexer.parsers import ParsedDelegation, ParsedPart


# === Fixtures ===


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=True) as f:
        db_path = Path(f.name)

    db = AnalyticsDB(db_path=db_path)
    db.connect()
    yield db
    db.close()

    try:
        db_path.unlink()
    except Exception:
        pass


@pytest.fixture
def trace_builder(temp_db):
    """Create a TraceBuilder instance."""
    return TraceBuilder(temp_db)


def create_test_messages(db, session_id: str, count: int = 3):
    """Create test messages in the database."""
    conn = db.connect()
    base_time = datetime.now() - timedelta(minutes=10)

    for i in range(count):
        msg_time = base_time + timedelta(seconds=i * 10)
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, tokens_input, tokens_output, created_at)
            VALUES (?, ?, 'assistant', ?, ?, ?)
            """,
            [
                f"msg_{session_id}_{i}",
                session_id,
                100 + i * 10,  # tokens_input: 100, 110, 120...
                500 + i * 50,  # tokens_output: 500, 550, 600...
                msg_time,
            ],
        )


# === Tests for update_trace_tokens ===


class TestUpdateTraceTokens:
    """Tests for update_trace_tokens method."""

    def test_updates_tokens_from_child_session(self, temp_db, trace_builder):
        """Verify tokens are aggregated from child session messages."""
        child_session_id = "ses_child_123"

        # Create messages in child session
        create_test_messages(temp_db, child_session_id, count=3)
        # Expected: input = 100 + 110 + 120 = 330, output = 500 + 550 + 600 = 1650

        # Create a trace with this child_session_id (no tokens yet)
        conn = temp_db.connect()
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, child_session_id)
            VALUES ('trace_1', 'ses_parent', 'explore', 'test prompt', ?, ?)
            """,
            [datetime.now(), child_session_id],
        )

        # Call update_trace_tokens
        trace_builder.update_trace_tokens(child_session_id)

        # Verify tokens were updated
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_1'"
        ).fetchone()

        assert result[0] == 330, f"Expected tokens_in=330, got {result[0]}"
        assert result[1] == 1650, f"Expected tokens_out=1650, got {result[1]}"

    def test_no_update_when_no_messages(self, temp_db, trace_builder):
        """Verify no update when child session has no messages."""
        child_session_id = "ses_empty"

        # Create trace without messages in child session
        conn = temp_db.connect()
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, child_session_id)
            VALUES ('trace_2', 'ses_parent', 'explore', 'test', ?, ?)
            """,
            [datetime.now(), child_session_id],
        )

        # Call update_trace_tokens
        trace_builder.update_trace_tokens(child_session_id)

        # Verify tokens remain NULL
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_2'"
        ).fetchone()

        assert result[0] is None, "tokens_in should remain NULL"
        assert result[1] is None, "tokens_out should remain NULL"


# === Tests for create_trace_from_delegation with token update ===


class TestCreateTraceUpdatesTokens:
    """Tests for token update during trace creation."""

    def test_creates_trace_and_updates_tokens(self, temp_db, trace_builder):
        """Verify trace creation updates tokens from existing child messages."""
        child_session_id = "ses_child_new"
        parent_session_id = "ses_parent_new"

        # First, create messages in the child session (simulating they arrived first)
        create_test_messages(temp_db, child_session_id, count=2)
        # Expected: input = 100 + 110 = 210, output = 500 + 550 = 1050

        # Now create delegation and part
        delegation = ParsedDelegation(
            id="prt_test_123",
            session_id=parent_session_id,
            message_id="msg_test",
            parent_agent="user",
            child_session_id=child_session_id,
            child_agent="explore",
            created_at=datetime.now() - timedelta(minutes=5),
        )

        part = ParsedPart(
            id="prt_test_123",
            message_id="msg_test",
            session_id=parent_session_id,
            part_type="tool_use",
            content=None,
            tool_name="task",
            tool_status="completed",
            call_id="call_123",
            arguments='{"prompt": "test"}',
            created_at=datetime.now() - timedelta(minutes=5),
            ended_at=datetime.now(),
            duration_ms=300000,
            error_message=None,
            error_data=None,
        )

        # Create trace (should update tokens immediately)
        trace_id = trace_builder.create_trace_from_delegation(delegation, part)

        # Verify trace was created with tokens
        conn = temp_db.connect()
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = ?",
            [trace_id],
        ).fetchone()

        assert result is not None, "Trace should be created"
        assert result[0] == 210, f"Expected tokens_in=210, got {result[0]}"
        assert result[1] == 1050, f"Expected tokens_out=1050, got {result[1]}"


# === Tests for parent trace resolution ===


class TestParentTraceResolution:
    """Tests for immediate parent trace resolution during creation."""

    def test_resolves_parent_trace_on_creation(self, temp_db, trace_builder):
        """Verify parent trace is resolved immediately when creating delegation trace."""
        parent_session_id = "ses_parent_resolve"
        child_session_id = "ses_child_resolve"

        # First, create a root trace for the parent session
        conn = temp_db.connect()
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, child_session_id)
            VALUES ('root_ses_parent_resolve', ?, 'user', 'root prompt', ?, ?)
            """,
            [
                parent_session_id,
                datetime.now() - timedelta(minutes=10),
                parent_session_id,
            ],
        )

        # Create delegation
        delegation = ParsedDelegation(
            id="prt_resolve_test",
            session_id=parent_session_id,
            message_id="msg_resolve",
            parent_agent="user",
            child_session_id=child_session_id,
            child_agent="explore",
            created_at=datetime.now() - timedelta(minutes=5),
        )

        part = ParsedPart(
            id="prt_resolve_test",
            message_id="msg_resolve",
            session_id=parent_session_id,
            part_type="tool_use",
            content=None,
            tool_name="task",
            tool_status="completed",
            call_id="call_resolve",
            arguments='{"prompt": "test"}',
            created_at=datetime.now() - timedelta(minutes=5),
            ended_at=datetime.now(),
            duration_ms=300000,
            error_message=None,
            error_data=None,
        )

        # Create trace - parent should be resolved immediately
        trace_id = trace_builder.create_trace_from_delegation(delegation, part)

        # Verify parent_trace_id was set
        result = conn.execute(
            "SELECT parent_trace_id FROM agent_traces WHERE trace_id = ?",
            [trace_id],
        ).fetchone()

        assert result[0] == "root_ses_parent_resolve", (
            f"Expected parent_trace_id='root_ses_parent_resolve', got '{result[0]}'"
        )

    def test_no_parent_when_root_not_exists(self, temp_db, trace_builder):
        """Verify parent_trace_id is NULL when no root trace exists."""
        parent_session_id = "ses_orphan"
        child_session_id = "ses_child_orphan"

        # Don't create root trace - delegation will be orphan

        delegation = ParsedDelegation(
            id="prt_orphan_test",
            session_id=parent_session_id,
            message_id="msg_orphan",
            parent_agent="user",
            child_session_id=child_session_id,
            child_agent="explore",
            created_at=datetime.now(),
        )

        part = ParsedPart(
            id="prt_orphan_test",
            message_id="msg_orphan",
            session_id=parent_session_id,
            part_type="tool_use",
            content=None,
            tool_name="task",
            tool_status="completed",
            call_id="call_orphan",
            arguments='{"prompt": "test"}',
            created_at=datetime.now(),
            ended_at=datetime.now(),
            duration_ms=1000,
            error_message=None,
            error_data=None,
        )

        trace_id = trace_builder.create_trace_from_delegation(delegation, part)

        conn = temp_db.connect()
        result = conn.execute(
            "SELECT parent_trace_id FROM agent_traces WHERE trace_id = ?",
            [trace_id],
        ).fetchone()

        assert result[0] is None, "parent_trace_id should be NULL when no root exists"

    def test_chained_delegations_resolve_correctly(self, temp_db, trace_builder):
        """Verify chained delegations (A -> B -> C) resolve parent correctly."""
        session_a = "ses_chain_a"
        session_b = "ses_chain_b"
        session_c = "ses_chain_c"

        conn = temp_db.connect()

        # Create root trace for session A
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, child_session_id)
            VALUES ('root_chain_a', ?, 'user', 'root', ?, ?)
            """,
            [session_a, datetime.now() - timedelta(minutes=20), session_a],
        )

        # Create delegation A -> B (in session A, creates session B)
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, parent_trace_id, subagent_type, prompt_input, 
             started_at, child_session_id)
            VALUES ('del_a_to_b', ?, 'root_chain_a', 'coordinator', 'delegate to B', ?, ?)
            """,
            [session_a, datetime.now() - timedelta(minutes=15), session_b],
        )

        # Now create delegation B -> C (should find del_a_to_b as parent)
        delegation_b_to_c = ParsedDelegation(
            id="del_b_to_c",
            session_id=session_b,  # In session B
            message_id="msg_b",
            parent_agent="coordinator",
            child_session_id=session_c,
            child_agent="explore",
            created_at=datetime.now() - timedelta(minutes=10),
        )

        part = ParsedPart(
            id="del_b_to_c",
            message_id="msg_b",
            session_id=session_b,
            part_type="tool_use",
            content=None,
            tool_name="task",
            tool_status="completed",
            call_id="call_b",
            arguments='{"prompt": "explore"}',
            created_at=datetime.now() - timedelta(minutes=10),
            ended_at=datetime.now(),
            duration_ms=600000,
            error_message=None,
            error_data=None,
        )

        trace_id = trace_builder.create_trace_from_delegation(delegation_b_to_c, part)

        # Verify parent is del_a_to_b (the trace that created session B)
        result = conn.execute(
            "SELECT parent_trace_id FROM agent_traces WHERE trace_id = ?",
            [trace_id],
        ).fetchone()

        assert result[0] == "del_a_to_b", (
            f"Expected parent_trace_id='del_a_to_b', got '{result[0]}'"
        )


# === Tests for backfill_missing_tokens ===


class TestBackfillMissingTokens:
    """Tests for backfill_missing_tokens method."""

    def test_backfills_traces_with_missing_tokens(self, temp_db, trace_builder):
        """Verify backfill updates all traces with missing tokens."""
        # Create 3 traces with child sessions but no tokens
        conn = temp_db.connect()
        for i in range(3):
            child_id = f"ses_child_{i}"
            # Create messages first
            create_test_messages(temp_db, child_id, count=2)

            # Create trace with NULL tokens
            conn.execute(
                """
                INSERT INTO agent_traces 
                (trace_id, session_id, subagent_type, prompt_input, started_at, 
                 child_session_id, tokens_in, tokens_out)
                VALUES (?, 'ses_parent', 'explore', 'test', ?, ?, NULL, NULL)
                """,
                [f"trace_{i}", datetime.now(), child_id],
            )

        # Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 3, f"Expected 3 traces updated, got {updated}"

        # Verify all traces have tokens now
        results = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces ORDER BY trace_id"
        ).fetchall()

        for i, (tokens_in, tokens_out) in enumerate(results):
            assert tokens_in == 210, (
                f"Trace {i}: expected tokens_in=210, got {tokens_in}"
            )
            assert tokens_out == 1050, (
                f"Trace {i}: expected tokens_out=1050, got {tokens_out}"
            )

    def test_skips_traces_with_existing_tokens(self, temp_db, trace_builder):
        """Verify backfill skips traces that already have tokens."""
        conn = temp_db.connect()
        child_id = "ses_child_existing"

        # Create messages
        create_test_messages(temp_db, child_id, count=2)

        # Create trace WITH existing tokens
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, tokens_in, tokens_out)
            VALUES ('trace_existing', 'ses_parent', 'explore', 'test', ?, ?, 999, 888)
            """,
            [datetime.now(), child_id],
        )

        # Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 0, "Should not update traces with existing tokens"

        # Verify tokens unchanged
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_existing'"
        ).fetchone()

        assert result[0] == 999, "tokens_in should be unchanged"
        assert result[1] == 888, "tokens_out should be unchanged"

    def test_handles_traces_without_messages(self, temp_db, trace_builder):
        """Verify backfill handles traces whose child sessions have no messages."""
        conn = temp_db.connect()

        # Create trace with child session that has no messages
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, tokens_in, tokens_out)
            VALUES ('trace_no_msgs', 'ses_parent', 'explore', 'test', ?, 'ses_empty', NULL, NULL)
            """,
            [datetime.now()],
        )

        # Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 0, "Should not update traces without messages"

        # Verify tokens still NULL
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_no_msgs'"
        ).fetchone()

        assert result[0] is None, "tokens_in should remain NULL"
        assert result[1] is None, "tokens_out should remain NULL"


# === Integration test: Full flow ===


class TestTokenAggregationFlow:
    """Integration tests for the complete token aggregation flow."""

    def test_messages_before_trace_scenario(self, temp_db, trace_builder):
        """Test the exact bug scenario: messages indexed before trace exists.

        This simulates the race condition where:
        1. Child session messages are indexed
        2. update_trace_tokens is called (but trace doesn't exist yet)
        3. Trace is created later
        4. backfill_missing_tokens should fix it
        """
        child_session_id = "ses_race_condition"
        parent_session_id = "ses_parent_race"

        # Step 1: Messages arrive and are indexed
        create_test_messages(temp_db, child_session_id, count=5)
        # Expected: input = 100+110+120+130+140 = 600
        # Expected: output = 500+550+600+650+700 = 3000

        # Step 2: update_trace_tokens called (trace doesn't exist - no effect)
        trace_builder.update_trace_tokens(child_session_id)

        # Step 3: Trace created later (without tokens because call already happened)
        conn = temp_db.connect()
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, tokens_in, tokens_out)
            VALUES ('trace_race', ?, 'explore', 'test', ?, ?, NULL, NULL)
            """,
            [parent_session_id, datetime.now(), child_session_id],
        )

        # Verify tokens are NULL (bug state)
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_race'"
        ).fetchone()
        assert result[0] is None, "Bug: tokens should be NULL at this point"

        # Step 4: backfill_missing_tokens fixes the issue
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 1, "Should fix 1 trace"

        # Verify tokens are now correct
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_race'"
        ).fetchone()

        assert result[0] == 600, f"Expected tokens_in=600, got {result[0]}"
        assert result[1] == 3000, f"Expected tokens_out=3000, got {result[1]}"


# === Tests for parent_agent resolution ===


class TestParentAgentResolution:
    """Tests for parent_agent being correctly set from parent's subagent_type.

    This is a regression test for the bug where child traces showed
    'user -> explore' instead of 'plan -> explore' because:
    1. Root traces are created with subagent_type='user'
    2. resolve_parent_traces() ran BEFORE update_root_trace_agents()
    3. So parent_agent was copied as 'user' instead of actual agent
    """

    def test_resolve_parent_traces_updates_parent_agent(self, temp_db, trace_builder):
        """Verify resolve_parent_traces updates parent_agent from parent's subagent_type."""
        parent_session_id = "ses_parent_agent_test"
        child_session_id = "ses_child_agent_test"

        conn = temp_db.connect()

        # Create root trace with subagent_type='plan' (already updated)
        conn.execute(
            """
            INSERT INTO agent_traces
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, parent_agent)
            VALUES ('root_ses_parent_agent_test', ?, 'plan', 'root prompt', ?, ?, 'user')
            """,
            [
                parent_session_id,
                datetime.now() - timedelta(minutes=10),
                parent_session_id,
            ],
        )

        # Create child trace with parent_agent='user' (wrong - should be 'plan')
        conn.execute(
            """
            INSERT INTO agent_traces
            (trace_id, session_id, subagent_type, prompt_input, started_at,
             child_session_id, parent_agent, parent_trace_id)
            VALUES ('child_trace', ?, 'explore', 'child prompt', ?, ?, 'user', 'root_ses_parent_agent_test')
            """,
            [parent_session_id, datetime.now(), child_session_id],
        )

        # Verify initial state: parent_agent is 'user'
        result = conn.execute(
            "SELECT parent_agent FROM agent_traces WHERE trace_id = 'child_trace'"
        ).fetchone()
        assert result[0] == "user", "Initial parent_agent should be 'user'"

        # Run resolve_parent_traces
        trace_builder.resolve_parent_traces()

        # Verify parent_agent is now 'plan' (from parent's subagent_type)
        result = conn.execute(
            "SELECT parent_agent FROM agent_traces WHERE trace_id = 'child_trace'"
        ).fetchone()
        assert result[0] == "plan", f"Expected parent_agent='plan', got '{result[0]}'"

    def test_update_root_trace_agents_from_messages(self, temp_db, trace_builder):
        """Verify update_root_trace_agents updates subagent_type from first message."""
        session_id = "ses_root_agent_update"

        conn = temp_db.connect()

        # Create root trace with subagent_type='user' (initial state)
        conn.execute(
            """
            INSERT INTO agent_traces
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, parent_agent)
            VALUES ('root_ses_root_agent_update', ?, 'user', 'root prompt', ?, ?, 'user')
            """,
            [session_id, datetime.now() - timedelta(minutes=10), session_id],
        )

        # Create assistant message with agent='plan'
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, agent, created_at)
            VALUES ('msg_agent_1', ?, 'assistant', 'plan', ?)
            """,
            [session_id, datetime.now()],
        )

        # Verify initial state: subagent_type is 'user'
        result = conn.execute(
            "SELECT subagent_type FROM agent_traces WHERE trace_id = 'root_ses_root_agent_update'"
        ).fetchone()
        assert result[0] == "user", "Initial subagent_type should be 'user'"

        # Run update_root_trace_agents
        trace_builder.update_root_trace_agents()

        # Verify subagent_type is now 'plan'
        result = conn.execute(
            "SELECT subagent_type FROM agent_traces WHERE trace_id = 'root_ses_root_agent_update'"
        ).fetchone()
        assert result[0] == "plan", f"Expected subagent_type='plan', got '{result[0]}'"

    def test_correct_order_root_update_then_resolve(self, temp_db, trace_builder):
        """Integration test: correct order updates parent_agent correctly.

        This tests the full scenario:
        1. Root trace created with subagent_type='user'
        2. Child trace created with parent_agent='user'
        3. Messages show root is actually 'plan'
        4. update_root_trace_agents() -> root becomes 'plan'
        5. resolve_parent_traces() -> child's parent_agent becomes 'plan'
        """
        parent_session_id = "ses_order_test_parent"
        child_session_id = "ses_order_test_child"

        conn = temp_db.connect()

        # Step 1: Create root trace with subagent_type='user'
        conn.execute(
            """
            INSERT INTO agent_traces
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, parent_agent)
            VALUES ('root_ses_order_test_parent', ?, 'user', 'root prompt', ?, ?, 'user')
            """,
            [
                parent_session_id,
                datetime.now() - timedelta(minutes=10),
                parent_session_id,
            ],
        )

        # Step 2: Create child trace with parent_agent='user' and parent_trace_id set
        conn.execute(
            """
            INSERT INTO agent_traces
            (trace_id, session_id, subagent_type, prompt_input, started_at,
             child_session_id, parent_agent, parent_trace_id)
            VALUES ('child_order_test', ?, 'explore', 'child prompt', ?, ?, 'user', 'root_ses_order_test_parent')
            """,
            [parent_session_id, datetime.now(), child_session_id],
        )

        # Step 3: Create message showing root is 'plan'
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, agent, created_at)
            VALUES ('msg_order_1', ?, 'assistant', 'plan', ?)
            """,
            [parent_session_id, datetime.now()],
        )

        # Step 4: Run update_root_trace_agents FIRST (correct order)
        trace_builder.update_root_trace_agents()

        # Verify root is now 'plan'
        result = conn.execute(
            "SELECT subagent_type FROM agent_traces WHERE trace_id = 'root_ses_order_test_parent'"
        ).fetchone()
        assert result[0] == "plan", (
            f"Root subagent_type should be 'plan', got '{result[0]}'"
        )

        # Step 5: Run resolve_parent_traces
        trace_builder.resolve_parent_traces()

        # Verify child's parent_agent is 'plan' (not 'user')
        result = conn.execute(
            "SELECT parent_agent FROM agent_traces WHERE trace_id = 'child_order_test'"
        ).fetchone()
        assert result[0] == "plan", f"Expected parent_agent='plan', got '{result[0]}'"

    def test_wrong_order_produces_wrong_parent_agent(self, temp_db, trace_builder):
        """Regression test: wrong order produces wrong parent_agent.

        This documents the bug: if resolve_parent_traces() runs BEFORE
        update_root_trace_agents(), the parent_agent stays 'user'.
        """
        parent_session_id = "ses_wrong_order_parent"
        child_session_id = "ses_wrong_order_child"

        conn = temp_db.connect()

        # Create root trace with subagent_type='user'
        conn.execute(
            """
            INSERT INTO agent_traces
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, parent_agent)
            VALUES ('root_ses_wrong_order_parent', ?, 'user', 'root prompt', ?, ?, 'user')
            """,
            [
                parent_session_id,
                datetime.now() - timedelta(minutes=10),
                parent_session_id,
            ],
        )

        # Create child trace with parent_agent=NULL (will be resolved)
        conn.execute(
            """
            INSERT INTO agent_traces
            (trace_id, session_id, subagent_type, prompt_input, started_at,
             child_session_id, parent_agent, parent_trace_id)
            VALUES ('child_wrong_order', ?, 'explore', 'child prompt', ?, ?, NULL, 'root_ses_wrong_order_parent')
            """,
            [parent_session_id, datetime.now(), child_session_id],
        )

        # Create message showing root should be 'plan'
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, agent, created_at)
            VALUES ('msg_wrong_1', ?, 'assistant', 'plan', ?)
            """,
            [parent_session_id, datetime.now()],
        )

        # WRONG ORDER: resolve_parent_traces BEFORE update_root_trace_agents
        trace_builder.resolve_parent_traces()

        # Bug: parent_agent is 'user' because root's subagent_type is still 'user'
        result = conn.execute(
            "SELECT parent_agent FROM agent_traces WHERE trace_id = 'child_wrong_order'"
        ).fetchone()
        assert result[0] == "user", (
            f"Bug state: parent_agent should be 'user', got '{result[0]}'"
        )

        # Now run update_root_trace_agents (fixes root)
        trace_builder.update_root_trace_agents()

        # Root is now 'plan'
        result = conn.execute(
            "SELECT subagent_type FROM agent_traces WHERE trace_id = 'root_ses_wrong_order_parent'"
        ).fetchone()
        assert result[0] == "plan", f"Root should be 'plan', got '{result[0]}'"

        # Run resolve_parent_traces again to fix the child
        trace_builder.resolve_parent_traces()

        # Now parent_agent is correctly 'plan'
        result = conn.execute(
            "SELECT parent_agent FROM agent_traces WHERE trace_id = 'child_wrong_order'"
        ).fetchone()
        assert result[0] == "plan", (
            f"Fixed: parent_agent should be 'plan', got '{result[0]}'"
        )
