"""
Tests for root trace token extraction and validation.

Verifies that:
1. Root traces extract tokens from their session's messages
2. Backfill updates existing root traces with correct tokens
3. Validation ensures tokens are within reasonable ranges
4. Edge cases (no messages, zero tokens) are handled correctly

Fixes DQ-001: Root trace tokens hardcoded to 0
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.indexer.trace_builder.builder import TraceBuilder


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


def create_session_with_messages(db, session_id: str, message_count: int = 3):
    """Create a session and its messages with realistic tokens."""
    conn = db.connect()
    base_time = datetime.now() - timedelta(minutes=10)

    # Create session
    conn.execute(
        """
        INSERT INTO sessions (id, title, created_at, updated_at, parent_id)
        VALUES (?, ?, ?, ?, NULL)
        """,
        [session_id, f"Test session {session_id}", base_time, datetime.now()],
    )

    # Create messages with tokens
    for i in range(message_count):
        msg_time = base_time + timedelta(seconds=i * 30)
        conn.execute(
            """
            INSERT INTO messages (
                id, session_id, role, agent, 
                tokens_input, tokens_output, tokens_reasoning,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"msg_{session_id}_{i}",
                session_id,
                "assistant" if i % 2 == 1 else "user",
                "dev" if i % 2 == 1 else None,
                1000 + i * 100,  # input: 1000, 1100, 1200...
                2000 + i * 200,  # output: 2000, 2200, 2400...
                500 + i * 50,  # reasoning: 500, 550, 600...
                msg_time,
            ],
        )


# === Tests for Root Trace Token Extraction ===


class TestRootTraceTokenExtraction:
    """Tests for extracting tokens from messages for root traces."""

    def test_root_trace_aggregates_tokens_from_messages(self, temp_db, trace_builder):
        """Verify root traces get tokens from their session's messages."""
        session_id = "ses_root_001"

        # Create session with 3 messages
        create_session_with_messages(temp_db, session_id, message_count=3)
        # Expected: input = 1000+1100+1200 = 3300
        # Expected: output = 2000+2200+2400 = 6600

        # Create root trace (initially with 0 tokens)
        conn = temp_db.connect()
        conn.execute(
            """
            INSERT INTO agent_traces (
                trace_id, session_id, subagent_type, prompt_input, 
                started_at, child_session_id, tokens_in, tokens_out
            )
            VALUES (?, ?, 'user', 'Test prompt', ?, ?, 0, 0)
            """,
            [f"root_{session_id}", session_id, datetime.now(), session_id],
        )

        # Run backfill to aggregate tokens
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 1, "Should update 1 root trace"

        # Verify tokens were updated
        result = conn.execute(
            f"SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'root_{session_id}'"
        ).fetchone()

        assert result[0] == 3300, f"Expected tokens_in=3300, got {result[0]}"
        assert result[1] == 6600, f"Expected tokens_out=6600, got {result[1]}"

    def test_root_trace_with_no_messages_stays_zero(self, temp_db, trace_builder):
        """Verify root traces without messages keep zero tokens."""
        session_id = "ses_root_no_msgs"

        conn = temp_db.connect()

        # Create session without messages
        conn.execute(
            """
            INSERT INTO sessions (id, title, created_at, parent_id)
            VALUES (?, 'Empty session', ?, NULL)
            """,
            [session_id, datetime.now()],
        )

        # Create root trace with 0 tokens
        conn.execute(
            """
            INSERT INTO agent_traces (
                trace_id, session_id, subagent_type, prompt_input,
                started_at, child_session_id, tokens_in, tokens_out
            )
            VALUES (?, ?, 'user', 'Test', ?, ?, 0, 0)
            """,
            [f"root_{session_id}", session_id, datetime.now(), session_id],
        )

        # Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 0, "Should not update traces without messages"

        # Verify tokens still 0
        result = conn.execute(
            f"SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'root_{session_id}'"
        ).fetchone()

        assert result[0] == 0, "tokens_in should remain 0"
        assert result[1] == 0, "tokens_out should remain 0"

    def test_multiple_root_traces_backfilled_together(self, temp_db, trace_builder):
        """Verify backfill updates multiple root traces in one go."""
        conn = temp_db.connect()

        # Create 5 root sessions with messages
        for i in range(5):
            session_id = f"ses_batch_{i}"
            create_session_with_messages(temp_db, session_id, message_count=2)
            # Each session: input = 1000+1100 = 2100, output = 2000+2200 = 4200

            # Create root trace with 0 tokens
            conn.execute(
                """
                INSERT INTO agent_traces (
                    trace_id, session_id, subagent_type, prompt_input,
                    started_at, child_session_id, tokens_in, tokens_out
                )
                VALUES (?, ?, 'user', 'Test', ?, ?, 0, 0)
                """,
                [f"root_{session_id}", session_id, datetime.now(), session_id],
            )

        # Run backfill once
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 5, f"Should update 5 root traces, got {updated}"

        # Verify all traces have correct tokens
        results = conn.execute(
            """
            SELECT tokens_in, tokens_out 
            FROM agent_traces 
            WHERE trace_id LIKE 'root_ses_batch_%'
            ORDER BY trace_id
            """
        ).fetchall()

        for tokens_in, tokens_out in results:
            assert tokens_in == 2100, f"Expected tokens_in=2100, got {tokens_in}"
            assert tokens_out == 4200, f"Expected tokens_out=4200, got {tokens_out}"


# === Tests for Token Validation ===


class TestTokenValidation:
    """Tests for token value validation."""

    def test_tokens_are_non_negative(self, temp_db):
        """Verify tokens cannot be negative."""
        conn = temp_db.connect()
        session_id = "ses_validation_001"

        # Create session
        conn.execute(
            """
            INSERT INTO sessions (id, title, created_at, parent_id)
            VALUES (?, 'Test', ?, NULL)
            """,
            [session_id, datetime.now()],
        )

        # Try to create message with negative tokens (should use 0 instead)
        conn.execute(
            """
            INSERT INTO messages (
                id, session_id, role, tokens_input, tokens_output, created_at
            )
            VALUES (?, ?, 'assistant', GREATEST(0, -100), GREATEST(0, -200), ?)
            """,
            [f"msg_{session_id}", session_id, datetime.now()],
        )

        # Verify tokens are 0
        result = conn.execute(
            f"SELECT tokens_input, tokens_output FROM messages WHERE id = 'msg_{session_id}'"
        ).fetchone()

        assert result[0] == 0, "Negative input tokens should become 0"
        assert result[1] == 0, "Negative output tokens should become 0"

    def test_tokens_within_reasonable_ranges(self, temp_db):
        """Verify tokens are within expected ranges."""
        conn = temp_db.connect()
        session_id = "ses_range_001"

        # Create session
        conn.execute(
            """
            INSERT INTO sessions (id, title, created_at, parent_id)
            VALUES (?, 'Test', ?, NULL)
            """,
            [session_id, datetime.now()],
        )

        # Create message with large but valid tokens
        conn.execute(
            """
            INSERT INTO messages (
                id, session_id, role, tokens_input, tokens_output, created_at
            )
            VALUES (?, ?, 'assistant', 95000, 45000, ?)
            """,
            [f"msg_{session_id}", session_id, datetime.now()],
        )

        # Verify tokens are stored correctly
        result = conn.execute(
            f"SELECT tokens_input, tokens_output FROM messages WHERE id = 'msg_{session_id}'"
        ).fetchone()

        assert result[0] == 95000, "Large input tokens should be stored"
        assert result[1] == 45000, "Large output tokens should be stored"
        assert result[0] < 100000, "Input tokens below max threshold"
        assert result[1] < 50000, "Output tokens below max threshold"

    def test_suspicious_token_counts_logged(self, temp_db, caplog):
        """Verify suspicious token counts are logged for investigation."""
        conn = temp_db.connect()
        session_id = "ses_suspicious_001"

        # Create session
        conn.execute(
            """
            INSERT INTO sessions (id, title, created_at, parent_id)
            VALUES (?, 'Test', ?, NULL)
            """,
            [session_id, datetime.now()],
        )

        # Create message with suspiciously large tokens
        tokens_input = 150000  # Over 100K (suspicious)
        tokens_output = 75000  # Over 50K (suspicious)

        conn.execute(
            """
            INSERT INTO messages (
                id, session_id, role, tokens_input, tokens_output, created_at
            )
            VALUES (?, ?, 'assistant', ?, ?, ?)
            """,
            [
                f"msg_{session_id}",
                session_id,
                tokens_input,
                tokens_output,
                datetime.now(),
            ],
        )

        # Query for suspicious tokens
        result = conn.execute(
            """
            SELECT id, tokens_input, tokens_output
            FROM messages
            WHERE tokens_input > 100000 OR tokens_output > 50000
            """
        ).fetchone()

        assert result is not None, "Should find suspicious message"
        assert result[1] == tokens_input, f"Input tokens: {result[1]}"
        assert result[2] == tokens_output, f"Output tokens: {result[2]}"


# === Integration Tests ===


class TestRootTraceTokensIntegration:
    """Integration tests for the complete root trace token flow."""

    def test_bulk_load_creates_root_traces_then_backfills_tokens(
        self, temp_db, trace_builder
    ):
        """Test the complete flow: create traces, then backfill tokens."""
        conn = temp_db.connect()

        # Step 1: Simulate bulk load - sessions and messages loaded
        for i in range(3):
            session_id = f"ses_bulk_{i}"
            create_session_with_messages(temp_db, session_id, message_count=3)

        # Step 2: Create root traces (with 0 tokens, simulating CREATE_ROOT_TRACES_SQL)
        for i in range(3):
            session_id = f"ses_bulk_{i}"
            conn.execute(
                """
                INSERT INTO agent_traces (
                    trace_id, session_id, subagent_type, prompt_input,
                    started_at, child_session_id, tokens_in, tokens_out, status
                )
                SELECT 
                    'root_' || id,
                    id,
                    'user',
                    title,
                    created_at,
                    id,
                    0,
                    0,
                    'completed'
                FROM sessions WHERE id = ?
                """,
                [session_id],
            )

        # Step 3: Verify all root traces have 0 tokens initially
        result = conn.execute(
            """
            SELECT COUNT(*) FROM agent_traces 
            WHERE trace_id LIKE 'root_ses_bulk_%' 
            AND tokens_in = 0 AND tokens_out = 0
            """
        ).fetchone()
        assert result[0] == 3, "All root traces should start with 0 tokens"

        # Step 4: Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 3, f"Should update 3 root traces, got {updated}"

        # Step 5: Verify all root traces now have correct tokens
        result = conn.execute(
            """
            SELECT COUNT(*) FROM agent_traces 
            WHERE trace_id LIKE 'root_ses_bulk_%' 
            AND tokens_in = 3300 AND tokens_out = 6600
            """
        ).fetchone()
        assert result[0] == 3, "All root traces should have updated tokens"

    def test_incremental_backfill_only_updates_zero_tokens(
        self, temp_db, trace_builder
    ):
        """Verify backfill only updates traces with 0 tokens, not all traces."""
        conn = temp_db.connect()

        # Create 2 sessions with messages
        for i in range(2):
            session_id = f"ses_incremental_{i}"
            create_session_with_messages(temp_db, session_id, message_count=2)

        # Create root trace 1 with 0 tokens
        conn.execute(
            """
            INSERT INTO agent_traces (
                trace_id, session_id, subagent_type, prompt_input,
                started_at, child_session_id, tokens_in, tokens_out
            )
            VALUES (?, ?, 'user', 'Test', ?, ?, 0, 0)
            """,
            [
                "root_ses_incremental_0",
                "ses_incremental_0",
                datetime.now(),
                "ses_incremental_0",
            ],
        )

        # Create root trace 2 with already-correct tokens
        conn.execute(
            """
            INSERT INTO agent_traces (
                trace_id, session_id, subagent_type, prompt_input,
                started_at, child_session_id, tokens_in, tokens_out
            )
            VALUES (?, ?, 'user', 'Test', ?, ?, 2100, 4200)
            """,
            [
                "root_ses_incremental_1",
                "ses_incremental_1",
                datetime.now(),
                "ses_incremental_1",
            ],
        )

        # Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 1, "Should only update trace with 0 tokens"

        # Verify trace 1 updated
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'root_ses_incremental_0'"
        ).fetchone()
        assert result[0] == 2100, "Trace 1 should be updated"
        assert result[1] == 4200, "Trace 1 should be updated"

        # Verify trace 2 unchanged
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'root_ses_incremental_1'"
        ).fetchone()
        assert result[0] == 2100, "Trace 2 should be unchanged"
        assert result[1] == 4200, "Trace 2 should be unchanged"


# === Performance Tests ===


class TestTokenBackfillPerformance:
    """Tests for backfill performance with large datasets."""

    def test_backfill_handles_large_batch_efficiently(self, temp_db, trace_builder):
        """Verify backfill can handle 100+ root traces efficiently."""
        import time

        conn = temp_db.connect()

        # Create 100 root sessions with messages
        for i in range(100):
            session_id = f"ses_perf_{i:03d}"
            create_session_with_messages(temp_db, session_id, message_count=5)

            # Create root trace with 0 tokens
            conn.execute(
                """
                INSERT INTO agent_traces (
                    trace_id, session_id, subagent_type, prompt_input,
                    started_at, child_session_id, tokens_in, tokens_out
                )
                VALUES (?, ?, 'user', 'Test', ?, ?, 0, 0)
                """,
                [f"root_{session_id}", session_id, datetime.now(), session_id],
            )

        # Measure backfill performance
        start = time.time()
        updated = trace_builder.backfill_missing_tokens()
        duration = time.time() - start

        assert updated == 100, f"Should update 100 traces, got {updated}"
        assert duration < 2.0, f"Backfill took {duration:.2f}s, should be < 2s"

        # Verify correctness with sampling
        result = conn.execute(
            """
            SELECT tokens_in, tokens_out 
            FROM agent_traces 
            WHERE trace_id = 'root_ses_perf_050'
            """
        ).fetchone()

        # Expected: 5 messages with input 1000+1100+1200+1300+1400 = 6000
        # output 2000+2200+2400+2600+2800 = 12000
        assert result[0] == 6000, f"Sample trace input tokens: {result[0]}"
        assert result[1] == 12000, f"Sample trace output tokens: {result[1]}"
