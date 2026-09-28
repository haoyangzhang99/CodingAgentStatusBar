"""
Tests for delegation traces with child sessions.

These tests verify that:
1. child_session_id is correctly extracted from state.metadata.sessionId
2. Delegation traces link correctly to child sessions
3. The tracing tree shows children for delegations

This is a regression test for the bug where delegations showed children: []
because child_session_id was extracted from the wrong JSON path.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import sys
from pathlib import Path

import pytest

# Add scripts to path for bulk_loader import
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from opencode_status_bar.analytics.db import AnalyticsDB
from bulk_loader import BulkLoader


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


# === Helper Functions ===


def write_json_file(
    storage_path: Path, file_type: str, project_id: str, file_id: str, data: dict
) -> Path:
    """Write JSON data to storage."""
    dir_path = storage_path / file_type / project_id
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{file_id}.json"
    file_path.write_text(json.dumps(data))
    return file_path


def create_session_json(
    session_id: str, title: str = "Test Session", parent_id=None
) -> dict:
    """Factory to create session JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": session_id,
        "projectID": "proj_001",
        "directory": "/path/to/project",
        "title": title,
        "parentID": parent_id,
        "version": "1.0.0",
        "summary": {"additions": 10, "deletions": 5, "files": 3},
        "time": {"created": now_ms, "updated": now_ms},
    }


def create_message_json(
    message_id: str, session_id: str, agent: str = "executor"
) -> dict:
    """Factory to create message JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": message_id,
        "sessionID": session_id,
        "role": "assistant",
        "agent": agent,
        "modelID": "claude-3-5-sonnet",
        "providerID": "anthropic",
        "time": {"created": now_ms, "completed": now_ms + 5000},
    }


def create_task_part_with_metadata(
    part_id: str,
    session_id: str,
    message_id: str,
    subagent_type: str = "roadmap",
    prompt: str = "Analyze the codebase",
    child_session_id: str = None,
    status: str = "completed",
) -> dict:
    """Factory to create task delegation part with state.metadata.sessionId.

    This matches the actual OpenCode JSON format where the child session ID
    is stored in state.metadata.sessionId (not in state.input).
    """
    now_ms = int(datetime.now().timestamp() * 1000)

    state = {
        "status": status,
        "input": {
            "subagent_type": subagent_type,
            "prompt": prompt,
            "description": f"Delegation to {subagent_type}",
        },
        "time": {"start": now_ms, "end": now_ms + 10000},
    }

    # CRITICAL: child_session_id is in state.metadata.sessionId, NOT state.input
    if child_session_id:
        state["metadata"] = {"sessionId": child_session_id}

    return {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "tool": "task",
        "text": None,
        "callID": f"call_{part_id}",
        "state": state,
        "time": {"start": now_ms, "end": now_ms + 10000},
    }


# === Test Classes ===


class TestDelegationChildSessionId:
    """Tests for child_session_id extraction from state.metadata.sessionId."""

    def test_delegation_has_child_session_id_from_metadata(
        self, bulk_loader, temp_storage, temp_db
    ):
        """
        CRITICAL: child_session_id must be extracted from state.metadata.sessionId.

        This was a bug where child_session_id was extracted from arguments
        (which contains state.input) instead of state.metadata.sessionId.
        """
        child_session = "ses_child_roadmap_001"

        # Create parent session and message
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_parent",
            create_session_json("ses_parent", title="Parent Session"),
        )
        write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_001",
            create_message_json("msg_001", "ses_parent", agent="plan"),
        )

        # Create task part with child_session_id in state.metadata.sessionId
        task_part = create_task_part_with_metadata(
            "prt_task_001",
            "ses_parent",
            "msg_001",
            subagent_type="roadmap",
            prompt="Create roadmap for feature X",
            child_session_id=child_session,
        )
        write_json_file(temp_storage, "part", "proj_001", "prt_task_001", task_part)

        # Load all data
        bulk_loader.load_sessions()
        bulk_loader.load_messages()
        bulk_loader.load_parts()

        # Verify child_session_id is in parts table
        conn = temp_db.connect()
        part = conn.execute("""
            SELECT id, child_session_id FROM parts WHERE id = 'prt_task_001'
        """).fetchone()

        assert part is not None, "Task part not found in database"
        assert part[1] == child_session, (
            f"child_session_id should be '{child_session}' but got '{part[1]}'. "
            "This means state.metadata.sessionId was not extracted correctly."
        )

    def test_delegation_trace_has_child_session_id(
        self, bulk_loader, temp_storage, temp_db
    ):
        """
        Delegation trace must have child_session_id populated from parts table.
        """
        child_session = "ses_roadmap_task_002"

        # Create session, message, and task part
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_main",
            create_session_json("ses_main", title="Main Session"),
        )
        write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_main",
            create_message_json("msg_main", "ses_main", agent="executor"),
        )
        write_json_file(
            temp_storage,
            "part",
            "proj_001",
            "prt_delegation",
            create_task_part_with_metadata(
                "prt_delegation",
                "ses_main",
                "msg_main",
                subagent_type="tester",
                prompt="Run unit tests",
                child_session_id=child_session,
            ),
        )

        # Load all data (this creates delegation traces)
        bulk_loader.load_sessions()
        bulk_loader.load_messages()
        bulk_loader.load_parts()

        # Verify delegation trace has child_session_id
        conn = temp_db.connect()
        trace = conn.execute("""
            SELECT trace_id, subagent_type, child_session_id
            FROM agent_traces
            WHERE trace_id LIKE 'del_%'
        """).fetchone()

        assert trace is not None, "Delegation trace not created"
        assert trace[1] == "tester", (
            f"Expected subagent_type 'tester', got '{trace[1]}'"
        )
        assert trace[2] == child_session, (
            f"Expected child_session_id '{child_session}' but got '{trace[2]}'. "
            "Delegation trace should get child_session_id from parts.child_session_id"
        )

    def test_delegation_without_child_session_still_works(
        self, bulk_loader, temp_storage, temp_db
    ):
        """
        Delegations without metadata.sessionId should still be created (with NULL child_session_id).
        """
        # Create session, message
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_no_child",
            create_session_json("ses_no_child"),
        )
        write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_no_child",
            create_message_json("msg_no_child", "ses_no_child"),
        )

        # Create task part WITHOUT metadata.sessionId
        task_part = create_task_part_with_metadata(
            "prt_no_child",
            "ses_no_child",
            "msg_no_child",
            subagent_type="reviewer",
            prompt="Review the code",
            child_session_id=None,  # No child session
        )
        write_json_file(temp_storage, "part", "proj_001", "prt_no_child", task_part)

        # Load all data
        bulk_loader.load_sessions()
        bulk_loader.load_messages()
        bulk_loader.load_parts()

        # Verify part loaded with NULL child_session_id
        conn = temp_db.connect()
        part = conn.execute("""
            SELECT id, child_session_id FROM parts WHERE id = 'prt_no_child'
        """).fetchone()

        assert part is not None
        assert part[1] is None, "child_session_id should be NULL when not provided"

        # Verify delegation trace created with NULL child_session_id
        trace = conn.execute("""
            SELECT trace_id, child_session_id
            FROM agent_traces WHERE trace_id = 'del_prt_no_child'
        """).fetchone()

        assert trace is not None, (
            "Delegation trace should be created even without child session"
        )
        assert trace[1] is None


class TestDelegationTreeChildren:
    """Tests for delegation children in tracing tree."""

    def test_multiple_delegations_with_different_child_sessions(
        self, bulk_loader, temp_storage, temp_db
    ):
        """
        Multiple delegations in a session should each have their own child_session_id.
        """
        # Create main session and message
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_multi",
            create_session_json("ses_multi", title="Multi-delegation Session"),
        )
        write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_multi",
            create_message_json("msg_multi", "ses_multi", agent="plan"),
        )

        # Create multiple task parts with different child sessions
        delegations = [
            ("prt_task_a", "roadmap", "ses_child_roadmap"),
            ("prt_task_b", "tester", "ses_child_tester"),
            ("prt_task_c", "reviewer", "ses_child_reviewer"),
        ]

        for part_id, subagent, child_session in delegations:
            task_part = create_task_part_with_metadata(
                part_id,
                "ses_multi",
                "msg_multi",
                subagent_type=subagent,
                prompt=f"Task for {subagent}",
                child_session_id=child_session,
            )
            write_json_file(temp_storage, "part", "proj_001", part_id, task_part)

        # Load all data
        bulk_loader.load_sessions()
        bulk_loader.load_messages()
        bulk_loader.load_parts()

        # Verify all delegation traces have correct child_session_id
        conn = temp_db.connect()
        traces = conn.execute("""
            SELECT trace_id, subagent_type, child_session_id
            FROM agent_traces
            WHERE trace_id LIKE 'del_%'
            ORDER BY trace_id
        """).fetchall()

        assert len(traces) == 3, f"Expected 3 delegation traces, got {len(traces)}"

        trace_dict = {t[1]: t[2] for t in traces}
        assert trace_dict["roadmap"] == "ses_child_roadmap"
        assert trace_dict["tester"] == "ses_child_tester"
        assert trace_dict["reviewer"] == "ses_child_reviewer"


class TestBackwardCompatibility:
    """Tests ensuring backward compatibility with existing data."""

    def test_parts_without_metadata_field_still_load(
        self, bulk_loader, temp_storage, temp_db
    ):
        """
        Parts without state.metadata field should still load (child_session_id = NULL).

        This ensures backward compatibility with older JSON files that don't have
        the metadata field.
        """
        now_ms = int(datetime.now().timestamp() * 1000)

        # Create part with OLD format (no metadata field at all)
        old_format_part = {
            "id": "prt_old_format",
            "sessionID": "ses_001",
            "messageID": "msg_001",
            "type": "tool",
            "tool": "task",
            "text": None,
            "callID": "call_old",
            "state": {
                "status": "completed",
                "input": {
                    "subagent_type": "executor",
                    "prompt": "Do something",
                },
                "time": {"start": now_ms, "end": now_ms + 5000},
                # NO metadata field!
            },
            "time": {"start": now_ms, "end": now_ms + 5000},
        }

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
            temp_storage, "part", "proj_001", "prt_old_format", old_format_part
        )

        # Load should succeed
        bulk_loader.load_sessions()
        bulk_loader.load_messages()
        result = bulk_loader.load_parts()

        assert result.files_loaded == 1, "Part with old format should be loaded"
        assert result.errors == 0

        # Verify child_session_id is NULL
        conn = temp_db.connect()
        part = conn.execute("""
            SELECT child_session_id FROM parts WHERE id = 'prt_old_format'
        """).fetchone()

        assert part[0] is None, "child_session_id should be NULL for old format parts"
