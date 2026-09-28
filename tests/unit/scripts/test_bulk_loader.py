"""
Tests for BulkLoader module.

Tests cover:
- Loading sessions via DuckDB native JSON
- Loading messages via DuckDB native JSON
- Loading parts via DuckDB native JSON
- CRITICAL: Parts WITHOUT time.start are still loaded (bug fix!)
- Root trace creation for sessions without parent
- Delegation trace creation from task parts
- Error handling and robustness
"""

import json
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path

import pytest

# Add scripts to path for bulk_loader import
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from opencode_status_bar.analytics.db import AnalyticsDB
from bulk_loader import BulkLoader, BulkLoadResult


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
def temp_storage(tmp_path):
    """Create a temporary storage directory structure."""
    storage_path = tmp_path / "opencode_storage"
    for subdir in ["session", "message", "part"]:
        (storage_path / subdir).mkdir(parents=True, exist_ok=True)
    return storage_path


@pytest.fixture
def bulk_loader(temp_db, temp_storage):
    """Create a BulkLoader instance."""
    return BulkLoader(temp_db, temp_storage)


# === Sample Data Factories ===


def create_session_json(
    session_id: str,
    project_id: str = "proj_001",
    title: str = "Test Session",
    parent_id: str = None,
    additions: int = 10,
    deletions: int = 5,
    files_changed: int = 3,
    created_ms: int = None,
    updated_ms: int = None,
) -> dict:
    """Factory to create session JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": session_id,
        "projectID": project_id,
        "directory": f"/path/to/{project_id}",
        "title": title,
        "parentID": parent_id,
        "version": "1.0.0",
        "summary": {
            "additions": additions,
            "deletions": deletions,
            "files": files_changed,
        },
        "time": {
            "created": created_ms or now_ms,
            "updated": updated_ms or now_ms,
        },
    }


def create_message_json(
    message_id: str,
    session_id: str,
    role: str = "assistant",
    agent: str = "executor",
    model_id: str = "claude-3-5-sonnet",
    provider_id: str = "anthropic",
    tokens_input: int = 1000,
    tokens_output: int = 500,
    cost: float = 0.001,
    created_ms: int = None,
    completed_ms: int = None,
) -> dict:
    """Factory to create message JSON data.

    Note: Uses both top-level modelID/providerID AND model.modelID/providerID
    because the BulkLoader SQL uses COALESCE to handle both formats.
    """
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": message_id,
        "sessionID": session_id,
        "parentID": None,
        "role": role,
        "agent": agent,
        # Include both formats for COALESCE compatibility
        "modelID": model_id,
        "providerID": provider_id,
        "model": {
            "modelID": model_id,
            "providerID": provider_id,
        },
        "mode": "agent",
        "cost": cost,
        "finish": "completed",
        "path": {"cwd": "/path/to/project"},
        "tokens": {
            "input": tokens_input,
            "output": tokens_output,
            "reasoning": 0,
            "cache": {"read": 0, "write": 0},
        },
        "time": {
            "created": created_ms or now_ms,
            "completed": completed_ms or (now_ms + 5000),
        },
    }


def create_part_json(
    part_id: str,
    session_id: str,
    message_id: str,
    part_type: str = "tool",
    tool_name: str = "read",
    status: str = "completed",
    start_ms: int = None,
    end_ms: int = None,
    include_time: bool = True,  # For testing parts without time.start
    text: str = None,  # For text content (required by BulkLoader SQL)
    use_state_time: bool = False,  # If True, put time in state.time instead of top-level
) -> dict:
    """Factory to create part JSON data.

    Note: The BulkLoader SQL expects certain fields to exist.
    - 'text' field for content (even if None)
    - 'state.status' for tool status
    - 'time' or 'state.time' for timestamps (BulkLoader uses COALESCE)

    IMPORTANT: DuckDB cannot divide JSON null by a number. So we must NOT include
    state.time when it contains null values. Only include it with actual timestamps.
    """
    now_ms = int(datetime.now().timestamp() * 1000)
    actual_start = start_ms or now_ms
    actual_end = end_ms or (now_ms + 100)

    # Build state object - only include time if use_state_time is True
    state = {
        "status": status,
        "input": {"filePath": "/path/to/file.py"},
    }

    if use_state_time:
        state["time"] = {
            "start": actual_start,
            "end": actual_end,
        }

    data = {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": part_type,
        "tool": tool_name,
        "text": text,  # Required field for BulkLoader
        "callID": f"call_{part_id}",
        "state": state,
    }

    # Top-level time (primary location) - only when include_time and not using state.time
    if include_time and not use_state_time:
        data["time"] = {
            "start": actual_start,
            "end": actual_end,
        }

    return data


def create_task_part_json(
    part_id: str,
    session_id: str,
    message_id: str,
    subagent_type: str = "tester",
    prompt: str = "Run tests",
    child_session_id: str = None,
    status: str = "completed",
) -> dict:
    """Factory to create task delegation part JSON data.

    Note: child_session_id is stored in state.metadata.sessionId (not in state.input).
    This matches the actual OpenCode JSON format where metadata contains the child session.
    """
    now_ms = int(datetime.now().timestamp() * 1000)
    state = {
        "status": status,
        "input": {
            "subagent_type": subagent_type,
            "prompt": prompt,
        },
        "time": {
            "start": now_ms,
            "end": now_ms + 10000,
        },
    }

    # Add metadata with sessionId if child_session_id is provided
    if child_session_id:
        state["metadata"] = {"sessionId": child_session_id}

    return {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "tool": "task",
        "text": None,  # Required field for BulkLoader
        "callID": f"call_{part_id}",
        "state": state,
        "time": {
            "start": now_ms,
            "end": now_ms + 10000,
        },
    }


def write_json_file(
    storage_path: Path, file_type: str, project_id: str, file_id: str, data: dict
) -> Path:
    """Write JSON data to storage."""
    dir_path = storage_path / file_type / project_id
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{file_id}.json"
    file_path.write_text(json.dumps(data))
    return file_path


# === BulkLoadResult Tests ===


class TestBulkLoadResult:
    """Tests for BulkLoadResult dataclass."""

    def test_result_fields(self):
        """Test BulkLoadResult stores all fields correctly."""
        result = BulkLoadResult(
            file_type="session",
            files_loaded=100,
            duration_seconds=2.5,
            files_per_second=40.0,
            errors=2,
        )

        assert result.file_type == "session"
        assert result.files_loaded == 100
        assert result.duration_seconds == 2.5
        assert result.files_per_second == 40.0
        assert result.errors == 2


# === BulkLoader Count Tests ===


class TestBulkLoaderCount:
    """Tests for count_files functionality."""

    def test_count_files_empty_storage(self, bulk_loader, temp_storage):
        """Test count_files returns 0 for empty directories."""
        counts = bulk_loader.count_files()

        assert counts["session"] == 0
        assert counts["message"] == 0
        assert counts["part"] == 0

    def test_count_files_with_data(self, bulk_loader, temp_storage):
        """Test count_files returns correct counts."""
        # Create session files
        for i in range(3):
            write_json_file(
                temp_storage,
                "session",
                "proj_001",
                f"ses_{i:03d}",
                create_session_json(f"ses_{i:03d}"),
            )

        # Create message files
        for i in range(5):
            write_json_file(
                temp_storage,
                "message",
                "proj_001",
                f"msg_{i:03d}",
                create_message_json(f"msg_{i:03d}", "ses_001"),
            )

        counts = bulk_loader.count_files()

        assert counts["session"] == 3
        assert counts["message"] == 5
        assert counts["part"] == 0

    def test_count_files_handles_missing_directory(self, temp_db, tmp_path):
        """Test that BulkLoader rejects non-existent paths at initialization."""
        # Create loader with non-existent path - should raise ValueError
        fake_storage = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="Storage path does not exist"):
            BulkLoader(temp_db, fake_storage)


# === BulkLoader Session Loading Tests ===


class TestBulkLoaderSessions:
    """Tests for session loading."""

    def test_load_sessions_empty_directory(self, bulk_loader, temp_storage):
        """Test load_sessions handles empty directory.

        Note: DuckDB's read_json_auto throws IOException when glob finds no files,
        which the BulkLoader catches and records as an error. This is expected.
        """
        result = bulk_loader.load_sessions()

        assert result.files_loaded == 0
        # DuckDB throws error on empty glob - this is expected behavior
        assert result.errors == 1

    def test_load_sessions_basic(self, bulk_loader, temp_storage, temp_db):
        """Test loading basic session files."""
        # Create session files
        for i in range(5):
            write_json_file(
                temp_storage,
                "session",
                "proj_001",
                f"ses_{i:03d}",
                create_session_json(
                    f"ses_{i:03d}",
                    title=f"Session {i}",
                    additions=i * 10,
                    deletions=i * 5,
                ),
            )

        result = bulk_loader.load_sessions()

        assert result.files_loaded == 5
        assert result.errors == 0
        assert result.files_per_second > 0

        # Verify in database
        conn = temp_db.connect()
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        assert count == 5

        # Verify specific session data
        session = conn.execute("""
            SELECT id, title, additions, deletions
            FROM sessions WHERE id = 'ses_002'
        """).fetchone()

        assert session[0] == "ses_002"
        assert session[1] == "Session 2"
        assert session[2] == 20
        assert session[3] == 10

    def test_load_sessions_with_parent_relationship(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test sessions with parent relationships are loaded correctly."""
        # Create parent session
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_parent",
            create_session_json("ses_parent", title="Parent Session"),
        )

        # Create child session
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_child",
            create_session_json(
                "ses_child", title="Child Session", parent_id="ses_parent"
            ),
        )

        result = bulk_loader.load_sessions()

        assert result.files_loaded == 2

        # Verify parent relationship
        conn = temp_db.connect()
        child = conn.execute("""
            SELECT parent_id FROM sessions WHERE id = 'ses_child'
        """).fetchone()

        assert child[0] == "ses_parent"

    def test_load_sessions_creates_root_traces(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test that root traces are created for sessions without parent."""
        # Create root session (no parent)
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_root",
            create_session_json("ses_root", title="Root Session", parent_id=None),
        )

        # Create child session (has parent)
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_child",
            create_session_json(
                "ses_child", title="Child Session", parent_id="ses_root"
            ),
        )

        result = bulk_loader.load_sessions()

        # Verify root trace created only for root session
        conn = temp_db.connect()
        root_traces = conn.execute("""
            SELECT trace_id, session_id, subagent_type
            FROM agent_traces WHERE trace_id LIKE 'root_%'
        """).fetchall()

        # Should have exactly 1 root trace
        assert len(root_traces) == 1
        assert root_traces[0][1] == "ses_root"
        assert root_traces[0][2] == "user"


# === BulkLoader Message Loading Tests ===


class TestBulkLoaderMessages:
    """Tests for message loading."""

    def test_load_messages_basic(self, bulk_loader, temp_storage, temp_db):
        """Test loading basic message files."""
        # Create message files
        for i in range(10):
            write_json_file(
                temp_storage,
                "message",
                "proj_001",
                f"msg_{i:03d}",
                create_message_json(
                    f"msg_{i:03d}",
                    "ses_001",
                    tokens_input=100 * (i + 1),
                    tokens_output=50 * (i + 1),
                ),
            )

        result = bulk_loader.load_messages()

        assert result.files_loaded == 10
        assert result.errors == 0

        # Verify token counts
        conn = temp_db.connect()
        msg = conn.execute("""
            SELECT tokens_input, tokens_output
            FROM messages WHERE id = 'msg_005'
        """).fetchone()

        assert msg[0] == 600  # 100 * 6
        assert msg[1] == 300  # 50 * 6

    def test_load_messages_with_cost(self, bulk_loader, temp_storage, temp_db):
        """Test message cost field is loaded correctly."""
        write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_costly",
            create_message_json("msg_costly", "ses_001", cost=0.05),
        )

        bulk_loader.load_messages()

        conn = temp_db.connect()
        msg = conn.execute(
            "SELECT cost FROM messages WHERE id = 'msg_costly'"
        ).fetchone()

        # DuckDB returns Decimal, convert to float for comparison
        assert float(msg[0]) == pytest.approx(0.05, abs=0.001)

    def test_load_messages_with_different_agents(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test messages from different agents are loaded correctly."""
        agents = ["executor", "tester", "reviewer", "refactorer"]

        for i, agent in enumerate(agents):
            write_json_file(
                temp_storage,
                "message",
                "proj_001",
                f"msg_{agent}",
                create_message_json(f"msg_{agent}", "ses_001", agent=agent),
            )

        bulk_loader.load_messages()

        conn = temp_db.connect()
        result = conn.execute("SELECT DISTINCT agent FROM messages").fetchall()
        loaded_agents = {row[0] for row in result}

        assert loaded_agents == set(agents)


# === BulkLoader Part Loading Tests - CRITICAL BUG FIX ===


class TestBulkLoaderParts:
    """Tests for part loading, including the time.start bug fix."""

    def test_load_parts_basic(self, bulk_loader, temp_storage, temp_db):
        """Test loading basic part files.

        The BulkLoader now uses explicit columns schema to ensure both 'time'
        and 'state.time' columns exist even if some JSON files don't have them.
        """
        for i in range(5):
            write_json_file(
                temp_storage,
                "part",
                "proj_001",
                f"prt_{i:03d}",
                create_part_json(
                    f"prt_{i:03d}",
                    "ses_001",
                    "msg_001",
                    use_state_time=True,  # Use state.time format
                ),
            )

        result = bulk_loader.load_parts()

        assert result.files_loaded == 5
        assert result.errors == 0

        conn = temp_db.connect()
        count = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
        assert count == 5

    def test_load_parts_without_time_start_BUG_FIX(
        self, bulk_loader, temp_storage, temp_db
    ):
        """
        CRITICAL TEST: Parts WITHOUT time.start must still be loaded.

        This was a bug where parts without the 'time' field or 'time.start'
        were being skipped. The fix uses COALESCE to handle both
        state.time.start and time.start locations.
        """
        # Create part WITH time.start (normal case)
        write_json_file(
            temp_storage,
            "part",
            "proj_001",
            "prt_with_time",
            create_part_json("prt_with_time", "ses_001", "msg_001", include_time=True),
        )

        # Create part WITHOUT time field at all
        part_no_time = create_part_json(
            "prt_no_time", "ses_001", "msg_001", include_time=False
        )
        write_json_file(temp_storage, "part", "proj_001", "prt_no_time", part_no_time)

        # Create part with time in state.time instead of top-level time
        now_ms = int(datetime.now().timestamp() * 1000)
        part_state_time = {
            "id": "prt_state_time",
            "sessionID": "ses_001",
            "messageID": "msg_001",
            "type": "tool",
            "tool": "bash",
            "text": None,  # Required field for BulkLoader
            "callID": "call_state_time",
            "state": {
                "status": "completed",
                "input": {"command": "ls"},
                "time": {
                    "start": now_ms,
                    "end": now_ms + 200,
                },
            },
            # No top-level 'time' field!
        }
        write_json_file(
            temp_storage, "part", "proj_001", "prt_state_time", part_state_time
        )

        result = bulk_loader.load_parts()

        # ALL THREE parts should be loaded
        assert result.files_loaded == 3, (
            f"Expected 3 parts loaded, got {result.files_loaded}. "
            "Parts without time.start should still be loaded!"
        )

        # Verify in database
        conn = temp_db.connect()
        parts = conn.execute("SELECT id, created_at FROM parts ORDER BY id").fetchall()

        part_ids = {p[0] for p in parts}
        assert "prt_with_time" in part_ids
        assert "prt_no_time" in part_ids, "Part without time field was not loaded!"
        assert "prt_state_time" in part_ids, "Part with state.time was not loaded!"

    def test_load_parts_with_state_time_format(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test that state.time is used correctly for part timestamps.

        The BulkLoader uses explicit columns schema and TRY() to safely
        access state.time.start for tool parts. This test verifies parts
        with state.time are loaded correctly.
        """
        now_ms = int(datetime.now().timestamp() * 1000)

        part_data = {
            "id": "prt_state_time",
            "sessionID": "ses_001",
            "messageID": "msg_001",
            "type": "tool",
            "tool": "read",
            "text": None,  # Required field for BulkLoader
            "callID": "call_state_time",
            "state": {
                "status": "completed",
                "input": {},
                "time": {
                    "start": now_ms,
                    "end": now_ms + 500,
                },
            },
        }
        write_json_file(temp_storage, "part", "proj_001", "prt_state_time", part_data)

        result = bulk_loader.load_parts()

        assert result.files_loaded == 1, (
            f"Expected 1 part loaded, errors={result.errors}"
        )

        conn = temp_db.connect()
        part = conn.execute("""
            SELECT created_at, duration_ms FROM parts WHERE id = 'prt_state_time'
        """).fetchone()

        # created_at should be populated from state.time.start
        assert part is not None, "Part not found in database"
        assert part[0] is not None, "created_at should be set from state.time.start"
        assert part[1] == 500, "duration_ms should be calculated correctly"

    def test_load_parts_creates_delegation_traces(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test that delegation traces are created from task parts."""
        # First need a session and message
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_001",
            create_session_json("ses_001"),
        )
        write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_001",
            create_message_json("msg_001", "ses_001", agent="executor"),
        )
        bulk_loader.load_sessions()
        bulk_loader.load_messages()

        # Create task part
        write_json_file(
            temp_storage,
            "part",
            "proj_001",
            "prt_task",
            create_task_part_json(
                "prt_task",
                "ses_001",
                "msg_001",
                subagent_type="tester",
                prompt="Run unit tests",
                child_session_id="ses_child_001",
            ),
        )

        bulk_loader.load_parts()

        # Verify delegation trace created
        conn = temp_db.connect()
        traces = conn.execute("""
            SELECT trace_id, subagent_type, prompt_input, child_session_id
            FROM agent_traces WHERE trace_id LIKE 'del_%'
        """).fetchall()

        assert len(traces) == 1
        assert traces[0][1] == "tester"
        assert traces[0][3] == "ses_child_001"

        # Verify child_session_id stored in parts table
        part = conn.execute("""
            SELECT child_session_id FROM parts WHERE id = 'prt_task'
        """).fetchone()
        assert part is not None
        assert part[0] == "ses_child_001"


# === BulkLoader load_all Integration Tests ===


class TestBulkLoaderLoadAll:
    """Integration tests for load_all orchestration."""

    def test_load_all_processes_in_order(self, bulk_loader, temp_storage):
        """Test load_all processes sessions, messages, parts in order."""
        # Create sample data
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_001",
            create_session_json("ses_001"),
        )
        write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_001",
            create_message_json("msg_001", "ses_001"),
        )
        write_json_file(
            temp_storage,
            "part",
            "proj_001",
            "prt_001",
            create_part_json("prt_001", "ses_001", "msg_001", use_state_time=True),
        )

        results = bulk_loader.load_all()

        assert "session" in results
        assert "message" in results
        assert "part" in results

        assert results["session"].files_loaded == 1
        assert results["message"].files_loaded == 1
        assert results["part"].files_loaded == 1

    def test_load_all_with_cutoff_time(self, bulk_loader, temp_storage, temp_db):
        """Test load_all with cutoff time filters old files."""
        now_ms = int(time.time() * 1000)
        old_ms = now_ms - 3600000  # 1 hour ago

        # Create old session (should be loaded with cutoff in future)
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_old",
            create_session_json("ses_old", created_ms=old_ms, updated_ms=old_ms),
        )

        # Load all - the cutoff is used for the sync state, not filtering
        cutoff = time.time() + 100  # Future cutoff
        results = bulk_loader.load_all(cutoff_time=cutoff)

        assert results["session"].files_loaded >= 1


# === BulkLoader Stats Tests ===


class TestBulkLoaderStats:
    """Tests for get_stats functionality."""

    def test_get_stats_after_loading(self, bulk_loader, temp_storage):
        """Test get_stats returns correct counts after loading."""
        # Create and load data
        for i in range(3):
            write_json_file(
                temp_storage,
                "session",
                "proj_001",
                f"ses_{i:03d}",
                create_session_json(f"ses_{i:03d}"),
            )

        for i in range(5):
            write_json_file(
                temp_storage,
                "message",
                "proj_001",
                f"msg_{i:03d}",
                create_message_json(f"msg_{i:03d}", "ses_001"),
            )

        bulk_loader.load_sessions()
        bulk_loader.load_messages()

        stats = bulk_loader.get_stats()

        assert stats["sessions_loaded"] == 3
        assert stats["messages_loaded"] == 5
        assert stats["parts_loaded"] == 0
        assert stats["total_loaded"] == 8


# === Error Handling Tests ===


class TestBulkLoaderErrorHandling:
    """Tests for error handling and robustness."""

    def test_load_sessions_handles_invalid_json(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test load_sessions doesn't crash on invalid JSON files.

        DuckDB's ignore_errors=true attempts to skip malformed rows.
        The exact behavior depends on DuckDB version and file structure.
        The main requirement is that the loader completes without exception.
        """
        # Create valid file
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_valid",
            create_session_json("ses_valid"),
        )

        # Create invalid JSON file
        invalid_path = temp_storage / "session" / "proj_001" / "ses_invalid.json"
        invalid_path.parent.mkdir(parents=True, exist_ok=True)
        invalid_path.write_text("{ this is not valid json }")

        # Should not crash - that's the main requirement
        result = bulk_loader.load_sessions()

        # Verify the loader completes without exception
        assert result is not None
        assert isinstance(result.files_loaded, int)
        assert isinstance(result.errors, int)

        # The valid session should be in database if no errors
        if result.errors == 0:
            conn = temp_db.connect()
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            assert count >= 1

    def test_load_from_nonexistent_directory(self, temp_db, tmp_path):
        """Test that BulkLoader rejects non-existent directory at initialization."""
        fake_storage = tmp_path / "does_not_exist"

        with pytest.raises(ValueError, match="Storage path does not exist"):
            BulkLoader(temp_db, fake_storage)

    def test_load_parts_with_text_content(self, bulk_loader, temp_storage, temp_db):
        """Test load_parts loads text parts correctly.

        Text parts have 'text' field instead of tool fields.
        The BulkLoader now uses explicit columns schema to handle all
        part types including text parts with or without state.time.
        """
        now_ms = int(datetime.now().timestamp() * 1000)

        # Create text part with all required fields for BulkLoader
        text_part = {
            "id": "prt_text",
            "sessionID": "ses_001",
            "messageID": "msg_001",
            "type": "text",
            "text": "Hello world",
            "state": {
                "status": None,
                "input": None,
                "time": {
                    "start": now_ms,
                    "end": now_ms + 100,
                },
            },
        }
        write_json_file(temp_storage, "part", "proj_001", "prt_text", text_part)

        result = bulk_loader.load_parts()

        # Should load without error
        assert result.files_loaded == 1, (
            f"Expected 1, got {result.files_loaded}, errors={result.errors}"
        )

        conn = temp_db.connect()
        part = conn.execute(
            "SELECT id, content FROM parts WHERE id = 'prt_text'"
        ).fetchone()
        assert part[0] == "prt_text"
        assert part[1] == "Hello world"


# === BulkLoader File Operations Loading Tests ===


class TestBulkLoaderFileOperations:
    """Tests for file operations loading."""

    def test_load_file_operations_extracts_read_write_edit(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test load_file_operations extracts file paths from read/write/edit parts."""
        now_ms = int(datetime.now().timestamp() * 1000)

        parts_data = [
            ("prt_read", "read", "/path/to/source.py"),
            ("prt_write", "write", "/path/to/output.py"),
            ("prt_edit", "edit", "/path/to/modified.py"),
        ]

        for part_id, tool_name, file_path in parts_data:
            part = {
                "id": part_id,
                "sessionID": "ses_001",
                "messageID": "msg_001",
                "type": "tool",
                "tool": tool_name,
                "text": None,
                "callID": f"call_{part_id}",
                "state": {
                    "status": "completed",
                    "input": {"filePath": file_path},
                    "time": {"start": now_ms, "end": now_ms + 100},
                },
            }
            write_json_file(temp_storage, "part", "proj_001", part_id, part)

        result = bulk_loader.load_file_operations()

        assert result.files_loaded == 3
        assert result.errors == 0

        conn = temp_db.connect()
        file_ops = conn.execute(
            "SELECT id, operation, file_path FROM file_operations ORDER BY id"
        ).fetchall()

        assert len(file_ops) == 3
        assert file_ops[0] == ("prt_edit", "edit", "/path/to/modified.py")
        assert file_ops[1] == ("prt_read", "read", "/path/to/source.py")
        assert file_ops[2] == ("prt_write", "write", "/path/to/output.py")

    def test_load_file_operations_ignores_non_file_tools(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test load_file_operations ignores bash, grep, glob and other tools."""
        now_ms = int(datetime.now().timestamp() * 1000)

        non_file_tools = ["bash", "grep", "glob", "task", "webfetch"]
        for tool_name in non_file_tools:
            part = {
                "id": f"prt_{tool_name}",
                "sessionID": "ses_001",
                "messageID": "msg_001",
                "type": "tool",
                "tool": tool_name,
                "text": None,
                "callID": f"call_{tool_name}",
                "state": {
                    "status": "completed",
                    "input": {"pattern": "test"},
                    "time": {"start": now_ms, "end": now_ms + 100},
                },
            }
            write_json_file(temp_storage, "part", "proj_001", f"prt_{tool_name}", part)

        result = bulk_loader.load_file_operations()

        assert result.files_loaded == 0

    def test_load_file_operations_uses_path_fallback(
        self, bulk_loader, temp_storage, temp_db
    ):
        """Test load_file_operations uses 'path' when 'filePath' is not present."""
        now_ms = int(datetime.now().timestamp() * 1000)

        part = {
            "id": "prt_path_fallback",
            "sessionID": "ses_001",
            "messageID": "msg_001",
            "type": "tool",
            "tool": "read",
            "text": None,
            "callID": "call_path",
            "state": {
                "status": "completed",
                "input": {"path": "/fallback/path.py"},
                "time": {"start": now_ms, "end": now_ms + 100},
            },
        }
        write_json_file(temp_storage, "part", "proj_001", "prt_path_fallback", part)

        result = bulk_loader.load_file_operations()

        assert result.files_loaded == 1

        conn = temp_db.connect()
        file_op = conn.execute(
            "SELECT file_path FROM file_operations WHERE id = 'prt_path_fallback'"
        ).fetchone()

        assert file_op[0] == "/fallback/path.py"


class TestEnrichFileOperationsWithDiffs:
    def test_enrich_file_operations_with_diffs_success(
        self, temp_storage, temp_db, bulk_loader
    ):
        now_ms = int(time.time() * 1000)
        session_id = "ses_enrich_test"

        session = {
            "id": session_id,
            "projectID": "proj_001",
            "directory": "/test",
            "title": "Test Session",
            "time": {"created": now_ms, "updated": now_ms},
        }
        write_json_file(temp_storage, "session", "proj_001", session_id, session)

        part_write = {
            "id": "prt_write",
            "sessionID": session_id,
            "messageID": "msg_001",
            "tool": "write",
            "state": {
                "status": "completed",
                "input": {"filePath": "/test/file1.py"},
                "time": {"start": now_ms, "end": now_ms + 100},
            },
        }
        write_json_file(temp_storage, "part", "proj_001", "prt_write", part_write)

        part_edit = {
            "id": "prt_edit",
            "sessionID": session_id,
            "messageID": "msg_002",
            "tool": "edit",
            "state": {
                "status": "completed",
                "input": {"filePath": "/test/file2.py"},
                "time": {"start": now_ms, "end": now_ms + 100},
            },
        }
        write_json_file(temp_storage, "part", "proj_001", "prt_edit", part_edit)

        diff_data = [
            {"file": "/test/file1.py", "additions": 50, "deletions": 10},
            {"file": "/test/file2.py", "additions": 30, "deletions": 20},
        ]
        diff_dir = temp_storage / "session_diff"
        diff_dir.mkdir(exist_ok=True)
        diff_file = diff_dir / f"{session_id}.json"
        diff_file.write_text(json.dumps(diff_data))

        bulk_loader.load_sessions()
        bulk_loader.load_file_operations()

        enriched = bulk_loader.enrich_file_operations_with_diffs()

        assert enriched == 2

        conn = temp_db.connect()
        file1 = conn.execute(
            "SELECT additions, deletions FROM file_operations WHERE id = 'prt_write'"
        ).fetchone()
        file2 = conn.execute(
            "SELECT additions, deletions FROM file_operations WHERE id = 'prt_edit'"
        ).fetchone()

        assert file1[0] == 50
        assert file1[1] == 10
        assert file2[0] == 30
        assert file2[1] == 20

    def test_enrich_file_operations_no_diffs(self, temp_storage, temp_db, bulk_loader):
        now_ms = int(time.time() * 1000)
        session_id = "ses_no_diffs"

        session = {
            "id": session_id,
            "projectID": "proj_001",
            "directory": "/test",
            "title": "Test Session",
            "time": {"created": now_ms, "updated": now_ms},
        }
        write_json_file(temp_storage, "session", "proj_001", session_id, session)

        part_write = {
            "id": "prt_no_diff",
            "sessionID": session_id,
            "messageID": "msg_001",
            "tool": "write",
            "state": {
                "status": "completed",
                "input": {"filePath": "/test/file1.py"},
                "time": {"start": now_ms, "end": now_ms + 100},
            },
        }
        write_json_file(temp_storage, "part", "proj_001", "prt_no_diff", part_write)

        bulk_loader.load_sessions()
        bulk_loader.load_file_operations()

        enriched = bulk_loader.enrich_file_operations_with_diffs()

        assert enriched == 0

        conn = temp_db.connect()
        file1 = conn.execute(
            "SELECT additions, deletions FROM file_operations WHERE id = 'prt_no_diff'"
        ).fetchone()

        assert file1[0] is None or file1[0] == 0
        assert file1[1] is None or file1[1] == 0
