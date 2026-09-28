"""
Tests for Analytics loader module - JSON data loading from OpenCode storage.

Covers:
- get_opencode_storage_path()
- load_sessions_fast()
- load_messages_fast()
- load_parts_fast()
- load_skills()
- load_delegations()
- load_opencode_data()
- extract_root_sessions()
- get_first_user_message()
- load_traces()
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.loader import (
    get_opencode_storage_path,
    load_sessions_fast,
    load_messages_fast,
    load_parts_fast,
    load_skills,
    load_delegations,
    load_opencode_data,
    extract_root_sessions,
    get_first_user_message,
    load_traces,
    ROOT_TRACE_PREFIX,
    ROOT_AGENT_TYPE,
)


# =============================================================================
# Fixtures (db is provided by conftest.py)
# =============================================================================


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    """Create a mock OpenCode storage directory structure."""
    storage = tmp_path / "opencode_storage"
    storage.mkdir(parents=True)
    return storage


@pytest.fixture
def current_timestamp() -> int:
    """Current timestamp in milliseconds (for recent data)."""
    return int(time.time() * 1000)


@pytest.fixture
def old_timestamp() -> int:
    """Timestamp 60 days ago in milliseconds."""
    return int((datetime.now() - timedelta(days=60)).timestamp() * 1000)


# =============================================================================
# Helper Functions
# =============================================================================


def create_session_file(
    session_dir: Path,
    session_id: str,
    project_id: str = "proj_001",
    title: str = "Test Session",
    directory: str = "/test/path",
    created_ts: int | None = None,
    updated_ts: int | None = None,
    parent_id: str | None = None,
) -> Path:
    """Create a session JSON file."""
    now_ms = int(time.time() * 1000)
    created_ts = created_ts or now_ms
    updated_ts = updated_ts or now_ms

    session_subdir = session_dir / session_id
    session_subdir.mkdir(parents=True, exist_ok=True)

    session_file = session_subdir / "session.json"
    data = {
        "id": session_id,
        "projectID": project_id,
        "directory": directory,
        "title": title,
        "parentID": parent_id,
        "time": {"created": created_ts, "updated": updated_ts},
    }
    session_file.write_text(json.dumps(data))
    return session_file


def create_message_file(
    message_dir: Path,
    message_id: str,
    session_id: str = "ses_001",
    role: str = "assistant",
    agent: str = "executor",
    created_ts: int | None = None,
    tokens_input: int = 100,
    tokens_output: int = 50,
    summary: dict | None = None,
) -> Path:
    """Create a message JSON file."""
    now_ms = int(time.time() * 1000)
    created_ts = created_ts or now_ms

    msg_subdir = message_dir / session_id
    msg_subdir.mkdir(parents=True, exist_ok=True)

    message_file = msg_subdir / f"{message_id}.json"
    data = {
        "id": message_id,
        "sessionID": session_id,
        "parentID": None,
        "role": role,
        "agent": agent,
        "modelID": "claude-sonnet",
        "providerID": "anthropic",
        "tokens": {
            "input": tokens_input,
            "output": tokens_output,
            "reasoning": 0,
            "cache": {"read": 0, "write": 0},
        },
        "time": {"created": created_ts, "completed": created_ts + 1000},
    }
    if summary:
        data["summary"] = summary
    message_file.write_text(json.dumps(data))
    return message_file


def create_part_file(
    part_dir: Path,
    part_id: str,
    message_id: str = "msg_001",
    tool: str = "bash",
    tool_status: str = "completed",
    part_type: str = "tool",
    start_ts: int | None = None,
    session_id: str | None = None,
    state: dict | None = None,
) -> Path:
    """Create a part JSON file."""
    now_ms = int(time.time() * 1000)
    start_ts = start_ts or now_ms

    msg_subdir = part_dir / message_id
    msg_subdir.mkdir(parents=True, exist_ok=True)

    part_file = msg_subdir / f"{part_id}.json"
    data = {
        "id": part_id,
        "messageID": message_id,
        "type": part_type,
        "tool": tool,
        "state": state or {"status": tool_status},
        "time": {"start": start_ts},
    }
    if session_id:
        data["sessionID"] = session_id
    part_file.write_text(json.dumps(data))
    return part_file


def create_skill_part_file(
    part_dir: Path,
    part_id: str,
    message_id: str,
    session_id: str,
    skill_name: str,
    start_ts: int | None = None,
) -> Path:
    """Create a skill tool invocation part file."""
    return create_part_file(
        part_dir,
        part_id,
        message_id=message_id,
        tool="skill",
        start_ts=start_ts,
        session_id=session_id,
        state={"input": {"name": skill_name}},
    )


def create_delegation_part_file(
    part_dir: Path,
    part_id: str,
    message_id: str,
    session_id: str,
    subagent_type: str,
    child_session_id: str | None = None,
    start_ts: int | None = None,
) -> Path:
    """Create a task tool invocation part file (delegation)."""
    now_ms = int(time.time() * 1000)
    start_ts = start_ts or now_ms

    msg_subdir = part_dir / message_id
    msg_subdir.mkdir(parents=True, exist_ok=True)

    part_file = msg_subdir / f"{part_id}.json"
    data = {
        "id": part_id,
        "messageID": message_id,
        "sessionID": session_id,
        "type": "tool",
        "tool": "task",
        "state": {
            "input": {"subagent_type": subagent_type},
            "time": {"start": start_ts},
            "metadata": {"sessionId": child_session_id},
        },
        "time": {"start": start_ts},
    }
    part_file.write_text(json.dumps(data))
    return part_file


# =============================================================================
# Test: get_opencode_storage_path
# =============================================================================


class TestGetOpencodeStoragePath:
    """Tests for get_opencode_storage_path function."""

    def test_returns_valid_storage_path_structure(self):
        """Function returns a valid Path with correct structure in home directory."""
        result = get_opencode_storage_path()

        # Verify exact structure
        assert result.name == "storage"
        assert result.parent.name == "opencode"
        assert str(Path.home()) in str(result)
        # Verify it's an absolute path
        assert result.is_absolute() == True
        # Verify path ends with opencode/storage (could be .config or .local/share)
        assert str(result).endswith("opencode/storage")


# =============================================================================
# Test: Loaders return zero on missing directories
# =============================================================================


class TestLoadersDirectoryNotExists:
    """Tests for loaders when directories don't exist."""

    @pytest.mark.parametrize(
        "loader_func,expected_count",
        [
            (load_sessions_fast, 0),
            (load_messages_fast, 0),
            (load_parts_fast, 0),
            (load_skills, 0),
            (load_delegations, 0),
        ],
    )
    def test_returns_zero_when_directory_not_exists(
        self, temp_db: AnalyticsDB, storage_path: Path, loader_func, expected_count
    ):
        """All loaders return 0 when their directory doesn't exist."""
        result = loader_func(temp_db, storage_path)
        assert result == expected_count


# =============================================================================
# Test: Load valid data (sessions, messages, parts)
# =============================================================================


class TestLoadValidData:
    """Tests for loading valid data from JSON files."""

    def test_loads_sessions_with_correct_data(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads sessions from valid JSON files with correct data in database."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create 3 session files with specific data
        for i in range(3):
            create_session_file(
                session_dir,
                f"ses_{i}",
                project_id=f"proj_{i}",
                title=f"Session {i}",
                directory=f"/path/{i}",
                created_ts=current_timestamp + i * 1000,
            )

        result = load_sessions_fast(temp_db, storage_path)

        # Verify count
        assert result == 3

        # Verify data in database
        conn = temp_db.connect()
        sessions = conn.execute(
            "SELECT id, title, project_id, directory FROM sessions ORDER BY id"
        ).fetchall()

        # Verify session count
        assert len(sessions) == 3

        # Verify first session completely
        assert sessions[0][0] == "ses_0"
        assert sessions[0][1] == "Session 0"
        assert sessions[0][2] == "proj_0"
        assert sessions[0][3] == "/path/0"

        # Verify second session
        assert sessions[1][0] == "ses_1"
        assert sessions[1][1] == "Session 1"
        assert sessions[1][2] == "proj_1"

        # Verify third session
        assert sessions[2][0] == "ses_2"
        assert sessions[2][1] == "Session 2"

    def test_loads_messages_with_token_metrics(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads messages with correct token metrics from JSON files."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create messages with specific token values
        create_message_file(
            message_dir,
            "msg_001",
            session_id="ses_001",
            role="assistant",
            agent="executor",
            tokens_input=500,
            tokens_output=200,
            created_ts=current_timestamp,
        )
        create_message_file(
            message_dir,
            "msg_002",
            session_id="ses_001",
            role="user",
            tokens_input=50,
            tokens_output=0,
            created_ts=current_timestamp + 1000,
        )

        result = load_messages_fast(temp_db, storage_path)

        # Verify count
        assert result == 2

        # Verify data in database
        conn = temp_db.connect()
        messages = conn.execute(
            "SELECT id, session_id, role, agent, tokens_input, tokens_output FROM messages ORDER BY id"
        ).fetchall()

        # Verify message count
        assert len(messages) == 2

        # Verify first message completely
        assert messages[0][0] == "msg_001"
        assert messages[0][1] == "ses_001"
        assert messages[0][2] == "assistant"
        assert messages[0][3] == "executor"
        assert messages[0][4] == 500
        assert messages[0][5] == 200

        # Verify second message
        assert messages[1][0] == "msg_002"
        assert messages[1][1] == "ses_001"
        assert messages[1][2] == "user"
        assert messages[1][4] == 50
        assert messages[1][5] == 0

    def test_loads_only_tool_type_parts(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads only parts with type='tool', ignoring other types."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create multiple tool parts
        create_part_file(
            part_dir,
            "prt_bash",
            message_id="msg_001",
            tool="bash",
            start_ts=current_timestamp,
        )
        create_part_file(
            part_dir,
            "prt_read",
            message_id="msg_001",
            tool="read",
            start_ts=current_timestamp + 1000,
        )

        # Create text part (should be ignored)
        create_part_file(
            part_dir,
            "prt_text",
            message_id="msg_002",
            tool="text",
            part_type="text",
            start_ts=current_timestamp,
        )

        result = load_parts_fast(temp_db, storage_path)

        # Only tool parts should be loaded (2 tools, 1 text ignored)
        assert result == 2

        conn = temp_db.connect()
        parts = conn.execute(
            "SELECT id, tool_name, message_id FROM parts ORDER BY id"
        ).fetchall()

        # Verify parts count
        assert len(parts) == 2

        # Verify first part
        assert parts[0][0] == "prt_bash"
        assert parts[0][1] == "bash"
        assert parts[0][2] == "msg_001"

        # Verify second part
        assert parts[1][0] == "prt_read"
        assert parts[1][1] == "read"
        assert parts[1][2] == "msg_001"

        # Verify text part was NOT loaded
        text_parts = conn.execute(
            "SELECT id FROM parts WHERE id = 'prt_text'"
        ).fetchall()
        assert len(text_parts) == 0


# =============================================================================
# Test: Skip old data
# =============================================================================


class TestSkipOldData:
    """Tests for skipping old data based on max_days parameter."""

    @pytest.mark.parametrize(
        "loader_func,create_recent,create_old",
        [
            (
                load_sessions_fast,
                lambda d, ts: create_session_file(
                    d / "session", "ses_recent", created_ts=ts
                ),
                lambda d, ts: create_session_file(
                    d / "session", "ses_old", created_ts=ts
                ),
            ),
            (
                load_messages_fast,
                lambda d, ts: create_message_file(
                    d / "message", "msg_recent", created_ts=ts
                ),
                lambda d, ts: create_message_file(
                    d / "message", "msg_old", created_ts=ts
                ),
            ),
            (
                load_skills,
                lambda d, ts: create_skill_part_file(
                    d / "part", "prt_recent", "msg_r", "ses_r", "skill-r", ts
                ),
                lambda d, ts: create_skill_part_file(
                    d / "part", "prt_old", "msg_o", "ses_o", "skill-o", ts
                ),
            ),
            (
                load_delegations,
                lambda d, ts: create_delegation_part_file(
                    d / "part", "prt_recent", "msg_r", "ses_r", "tester", start_ts=ts
                ),
                lambda d, ts: create_delegation_part_file(
                    d / "part", "prt_old", "msg_o", "ses_o", "old-agent", start_ts=ts
                ),
            ),
        ],
    )
    def test_skips_old_data_based_on_max_days(
        self,
        temp_db: AnalyticsDB,
        storage_path: Path,
        current_timestamp: int,
        old_timestamp: int,
        loader_func,
        create_recent,
        create_old,
    ):
        """All loaders skip data older than max_days."""
        # Create directories
        (storage_path / "session").mkdir(exist_ok=True)
        (storage_path / "message").mkdir(exist_ok=True)
        (storage_path / "part").mkdir(exist_ok=True)

        # Create recent and old data
        create_recent(storage_path, current_timestamp)
        create_old(storage_path, old_timestamp)

        result = loader_func(temp_db, storage_path, max_days=30)

        # Only recent data should be loaded
        assert result == 1


# =============================================================================
# Test: Skills loading
# =============================================================================


class TestSkillsLoading:
    """Comprehensive tests for skills loading."""

    def test_loads_skills_with_filtering_and_validation(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads skill invocations with proper filtering and data validation."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create valid skill parts
        create_skill_part_file(
            part_dir,
            "prt_skill_1",
            "msg_001",
            "ses_001",
            "functional-testing",
            current_timestamp,
        )
        create_skill_part_file(
            part_dir,
            "prt_skill_2",
            "msg_002",
            "ses_001",
            "agentic-flow",
            current_timestamp + 1000,
        )
        create_skill_part_file(
            part_dir,
            "prt_skill_3",
            "msg_003",
            "ses_002",
            "clean-code",
            current_timestamp + 2000,
        )

        # Create non-skill tool part (should be ignored)
        create_part_file(part_dir, "prt_bash", tool="bash", start_ts=current_timestamp)

        # Create skill with missing name (should be ignored)
        missing_dir = part_dir / "msg_missing"
        missing_dir.mkdir()
        (missing_dir / "prt_missing.json").write_text(
            json.dumps(
                {
                    "id": "prt_missing",
                    "messageID": "msg_missing",
                    "sessionID": "ses_001",
                    "tool": "skill",
                    "state": {"input": {}},
                    "time": {"start": current_timestamp},
                }
            )
        )

        # Create invalid JSON (should be ignored)
        invalid_dir = part_dir / "msg_invalid"
        invalid_dir.mkdir()
        (invalid_dir / "prt_invalid.json").write_text("{ not valid json }")

        result = load_skills(temp_db, storage_path)

        # Only 3 valid skills should be loaded
        assert result == 3

        # Verify data in database (id is auto-generated, so don't test it)
        conn = temp_db.connect()
        skills = conn.execute(
            "SELECT skill_name, session_id, message_id FROM skills ORDER BY skill_name"
        ).fetchall()

        # Verify skills count
        assert len(skills) == 3

        # Verify first skill (agentic-flow)
        assert skills[0][0] == "agentic-flow"
        assert skills[0][1] == "ses_001"
        assert skills[0][2] == "msg_002"

        # Verify second skill (clean-code)
        assert skills[1][0] == "clean-code"
        assert skills[1][1] == "ses_002"
        assert skills[1][2] == "msg_003"

        # Verify third skill (functional-testing)
        assert skills[2][0] == "functional-testing"
        assert skills[2][1] == "ses_001"
        assert skills[2][2] == "msg_001"

        # Verify non-skill and invalid parts were NOT loaded
        non_skill = conn.execute(
            "SELECT COUNT(*) FROM skills WHERE skill_name IS NULL OR skill_name = ''"
        ).fetchone()
        assert non_skill[0] == 0


# =============================================================================
# Test: Delegations loading
# =============================================================================


class TestDelegationsLoading:
    """Comprehensive tests for delegations loading."""

    def test_loads_delegations_with_parent_resolution(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads delegations with proper filtering and parent agent resolution."""
        # First insert messages to be parents
        conn = temp_db.connect()
        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES ('msg_parent', 'ses_001', 'assistant', 'executor', CURRENT_TIMESTAMP)"""
        )
        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES ('msg_coord', 'ses_001', 'assistant', 'coordinator', CURRENT_TIMESTAMP)"""
        )

        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create valid delegation parts
        create_delegation_part_file(
            part_dir,
            "prt_del_1",
            "msg_parent",
            "ses_001",
            "tester",
            "child_001",
            current_timestamp,
        )
        create_delegation_part_file(
            part_dir,
            "prt_del_2",
            "msg_coord",
            "ses_001",
            "refactoring",
            "child_002",
            current_timestamp + 1000,
        )
        create_delegation_part_file(
            part_dir,
            "prt_del_3",
            "msg_unknown",
            "ses_001",
            "quality",
            "child_003",
            current_timestamp + 2000,
        )

        # Create non-task tool (should be ignored)
        create_part_file(part_dir, "prt_bash", tool="bash", start_ts=current_timestamp)

        # Create delegation with missing subagent_type (should be ignored)
        missing_dir = part_dir / "msg_missing"
        missing_dir.mkdir()
        (missing_dir / "prt_missing.json").write_text(
            json.dumps(
                {
                    "id": "prt_missing",
                    "messageID": "msg_missing",
                    "sessionID": "ses_001",
                    "tool": "task",
                    "state": {"input": {}},
                    "time": {"start": current_timestamp},
                }
            )
        )

        result = load_delegations(temp_db, storage_path)

        # Only 3 valid delegations should be loaded
        assert result == 3

        # Verify data in database
        delegations = conn.execute(
            "SELECT id, child_agent, parent_agent, session_id, child_session_id FROM delegations ORDER BY id"
        ).fetchall()

        # Verify delegations count
        assert len(delegations) == 3

        # Verify first delegation (from executor)
        assert delegations[0][0] == "prt_del_1"
        assert delegations[0][1] == "tester"
        assert delegations[0][2] == "executor"  # Resolved from message
        assert delegations[0][3] == "ses_001"
        assert delegations[0][4] == "child_001"

        # Verify second delegation (from coordinator)
        assert delegations[1][0] == "prt_del_2"
        assert delegations[1][1] == "refactoring"
        assert delegations[1][2] == "coordinator"  # Resolved from message
        assert delegations[1][4] == "child_002"

        # Verify third delegation (unknown parent)
        assert delegations[2][0] == "prt_del_3"
        assert delegations[2][1] == "quality"

        # Verify non-task tools were NOT loaded as delegations
        non_task = conn.execute(
            "SELECT COUNT(*) FROM delegations WHERE child_agent = 'bash'"
        ).fetchone()
        assert non_task[0] == 0


# =============================================================================
# Test: load_opencode_data orchestration
# =============================================================================


class TestLoadOpencodeData:
    """Tests for load_opencode_data orchestration function."""

    def test_returns_error_when_storage_not_found(
        self, temp_db: AnalyticsDB, tmp_path: Path
    ):
        """Returns error dict when storage path doesn't exist."""
        non_existent = tmp_path / "non_existent"

        result = load_opencode_data(db=temp_db, storage_path=non_existent)

        assert result["error"] == "Storage not found"
        assert result["sessions"] == 0
        assert result["messages"] == 0
        assert result["parts"] == 0
        # Skills and delegations may not be in error response
        assert result.get("skills", 0) == 0
        assert result.get("delegations", 0) == 0

    def test_clear_vs_preserve_data_behavior(
        self, temp_db: AnalyticsDB, storage_path: Path
    ):
        """Tests clear_first=True vs False behavior."""
        # Pre-populate database
        conn = temp_db.connect()
        conn.execute(
            """INSERT INTO sessions (id, title, created_at)
               VALUES ('existing', 'Existing', CURRENT_TIMESTAMP)"""
        )

        # Create session directory (empty)
        (storage_path / "session").mkdir()

        # Test clear_first=True
        load_opencode_data(db=temp_db, storage_path=storage_path, clear_first=True)
        count_after_clear = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        assert count_after_clear[0] == 0

        # Re-insert and test preserve
        conn.execute(
            """INSERT INTO sessions (id, title, created_at)
               VALUES ('existing2', 'Existing2', CURRENT_TIMESTAMP)"""
        )

        load_opencode_data(db=temp_db, storage_path=storage_path, clear_first=False)
        count_after_preserve = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        assert count_after_preserve[0] == 1

    def test_loads_all_data_types_with_options(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads all data types correctly with skip_parts option."""
        # Create directories
        session_dir = storage_path / "session"
        session_dir.mkdir()
        message_dir = storage_path / "message"
        message_dir.mkdir()
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create test data
        create_session_file(
            session_dir, "ses_001", title="Test", created_ts=current_timestamp
        )
        create_message_file(
            message_dir, "msg_001", session_id="ses_001", created_ts=current_timestamp
        )
        create_part_file(part_dir, "prt_001", tool="bash", start_ts=current_timestamp)
        create_skill_part_file(
            part_dir, "prt_skill", "msg_002", "ses_001", "test-skill", current_timestamp
        )
        create_delegation_part_file(
            part_dir,
            "prt_del",
            "msg_001",
            "ses_001",
            "tester",
            start_ts=current_timestamp,
        )

        # Test with skip_parts=True (default)
        result1 = load_opencode_data(
            db=temp_db, storage_path=storage_path, clear_first=True
        )

        assert result1["sessions"] == 1
        assert result1["messages"] == 1
        assert result1["parts"] == 0  # Skipped by default
        assert result1["skills"] == 1
        assert result1["delegations"] == 1
        assert "error" not in result1

        # Test with skip_parts=False
        result2 = load_opencode_data(
            db=temp_db, storage_path=storage_path, clear_first=True, skip_parts=False
        )

        # All tool-type parts loaded (bash + skill + task = 3 parts)
        assert result2["parts"] == 3

    def test_uses_defaults_when_not_provided(
        self, temp_db: AnalyticsDB, storage_path: Path
    ):
        """Uses default storage path and creates DB when not provided."""
        (storage_path / "session").mkdir()

        with patch(
            "opencode_status_bar.analytics.loaders.get_opencode_storage_path"
        ) as mock_path:
            mock_path.return_value = Path("/non/existent/path")
            load_opencode_data(db=temp_db)
            mock_path.assert_called_once()

        with patch("opencode_status_bar.analytics.loaders.AnalyticsDB") as mock_db_class:
            mock_db = MagicMock()
            mock_db.connect.return_value = MagicMock()
            mock_db_class.return_value = mock_db
            load_opencode_data(storage_path=storage_path)
            mock_db_class.assert_called_once()


# =============================================================================
# Test: Edge cases and special content
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special content handling."""

    def test_handles_empty_directories(self, temp_db: AnalyticsDB, storage_path: Path):
        """Handles empty session/message/part directories gracefully."""
        (storage_path / "session").mkdir()
        (storage_path / "message").mkdir()
        (storage_path / "part").mkdir()

        result = load_opencode_data(db=temp_db, storage_path=storage_path)

        # Verify all counts are zero
        assert result["sessions"] == 0
        assert result["messages"] == 0
        assert result["parts"] == 0
        assert result["skills"] == 0
        assert result["delegations"] == 0

        # Verify no error
        assert "error" not in result

        # Verify database is empty
        conn = temp_db.connect()
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        assert session_count[0] == 0
        assert message_count[0] == 0

    def test_handles_special_content_variations(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Handles unicode, special characters, and nested structures."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Unicode content
        session_subdir = session_dir / "ses_unicode"
        session_subdir.mkdir()
        (session_subdir / "session.json").write_text(
            json.dumps(
                {
                    "id": "ses_unicode",
                    "projectID": "proj_001",
                    "directory": "/projet/francais",
                    "title": "Session avec accents",
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # Special characters in path
        create_session_file(
            session_dir,
            "ses_special",
            directory="/path/with spaces/and-dashes",
            title="Session with 'quotes'",
            created_ts=current_timestamp,
        )

        # Deeply nested structure
        nested_dir = session_dir / "proj_001" / "branch_main" / "ses_nested"
        nested_dir.mkdir(parents=True)
        (nested_dir / "session.json").write_text(
            json.dumps(
                {
                    "id": "ses_nested",
                    "projectID": "proj_001",
                    "directory": "/test",
                    "title": "Nested Session",
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                }
            )
        )

        result = load_sessions_fast(temp_db, storage_path)

        assert result == 3

        conn = temp_db.connect()
        sessions = conn.execute("SELECT id, title FROM sessions ORDER BY id").fetchall()

        assert len(sessions) == 3
        # Verify unicode content
        unicode_session = [s for s in sessions if s[0] == "ses_unicode"][0]
        assert "accents" in unicode_session[1]

    def test_handles_null_and_missing_values(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Handles null/missing time values and optional fields."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Skill with empty time object
        msg_dir = part_dir / "msg_no_time"
        msg_dir.mkdir()
        (msg_dir / "prt_no_time.json").write_text(
            json.dumps(
                {
                    "id": "prt_no_time",
                    "messageID": "msg_no_time",
                    "sessionID": "ses_001",
                    "tool": "skill",
                    "state": {"input": {"name": "test-skill"}},
                    "time": {},
                }
            )
        )

        # Valid skill for comparison
        create_skill_part_file(
            part_dir,
            "prt_valid",
            "msg_001",
            "ses_001",
            "valid-skill",
            current_timestamp,
        )

        result = load_skills(temp_db, storage_path)

        # Both should load (null time means no cutoff filter)
        assert result >= 1

    def test_handles_invalid_json_gracefully(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Handles invalid JSON files without crashing."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create valid session
        create_session_file(
            session_dir, "ses_valid", title="Valid", created_ts=current_timestamp
        )

        # Create invalid JSON file (DuckDB will fail on this)
        invalid_dir = session_dir / "ses_invalid"
        invalid_dir.mkdir()
        (invalid_dir / "session.json").write_text("{ invalid json }")

        # Returns 0 because malformed JSON causes query to fail
        result = load_sessions_fast(temp_db, storage_path)
        assert result == 0

    def test_handles_missing_required_fields(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Handles sessions with missing required fields (WHERE id IS NOT NULL)."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Session with missing id field
        missing_id_dir = session_dir / "ses_missing"
        missing_id_dir.mkdir()
        (missing_id_dir / "session.json").write_text(
            json.dumps(
                {
                    "projectID": "proj",
                    "title": "Missing ID",
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                }
            )
        )

        # Valid session
        create_session_file(
            session_dir, "ses_valid", title="Valid", created_ts=current_timestamp
        )

        result = load_sessions_fast(temp_db, storage_path)

        # Only valid session should be loaded
        assert result == 1


# =============================================================================
# Test: get_first_user_message
# =============================================================================


class TestGetFirstUserMessage:
    """Comprehensive tests for get_first_user_message function."""

    def test_extracts_first_user_message_with_all_scenarios(
        self, storage_path: Path, current_timestamp: int
    ):
        """Tests all scenarios for first user message extraction."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Scenario 1: Non-existent session
        result_missing = get_first_user_message(message_dir, "non_existent_session")
        assert result_missing is None

        # Scenario 2: Only assistant messages (no user)
        create_message_file(
            message_dir,
            "msg_assistant",
            session_id="ses_no_user",
            role="assistant",
            created_ts=current_timestamp,
        )
        result_no_user = get_first_user_message(message_dir, "ses_no_user")
        assert result_no_user is None

        # Scenario 3: User message with title and body
        ses_full_dir = message_dir / "ses_full"
        ses_full_dir.mkdir()
        (ses_full_dir / "msg_user.json").write_text(
            json.dumps(
                {
                    "id": "msg_user",
                    "sessionID": "ses_full",
                    "role": "user",
                    "time": {"created": current_timestamp},
                    "summary": {
                        "title": "Implement feature X",
                        "body": "Please add tests",
                    },
                }
            )
        )
        result_full = get_first_user_message(message_dir, "ses_full")
        # Verify complete message content
        assert "Implement feature X" in result_full
        assert "Please add tests" in result_full
        # Verify exact format (title + blank line + body)
        assert result_full == "Implement feature X\n\nPlease add tests"

        # Scenario 4: Title only (empty body)
        ses_title_dir = message_dir / "ses_title"
        ses_title_dir.mkdir()
        (ses_title_dir / "msg_title.json").write_text(
            json.dumps(
                {
                    "id": "msg_title",
                    "sessionID": "ses_title",
                    "role": "user",
                    "time": {"created": current_timestamp},
                    "summary": {"title": "Just a title", "body": ""},
                }
            )
        )
        result_title = get_first_user_message(message_dir, "ses_title")
        assert result_title == "Just a title"

        # Scenario 5: Multiple messages (returns first chronologically)
        ses_multi_dir = message_dir / "ses_multi"
        ses_multi_dir.mkdir()
        (ses_multi_dir / "msg_second.json").write_text(
            json.dumps(
                {
                    "id": "msg_second",
                    "sessionID": "ses_multi",
                    "role": "user",
                    "time": {"created": current_timestamp + 1000},
                    "summary": {"title": "Second message", "body": ""},
                }
            )
        )
        (ses_multi_dir / "msg_first.json").write_text(
            json.dumps(
                {
                    "id": "msg_first",
                    "sessionID": "ses_multi",
                    "role": "user",
                    "time": {"created": current_timestamp},
                    "summary": {"title": "First message", "body": ""},
                }
            )
        )
        result_multi = get_first_user_message(message_dir, "ses_multi")
        # Verify first message is returned (chronologically)
        assert result_multi == "First message"
        assert "Second message" not in result_multi


# =============================================================================
# Test: extract_root_sessions
# =============================================================================


class TestExtractRootSessions:
    """Comprehensive tests for extract_root_sessions function."""

    def test_extracts_root_sessions_with_all_features(
        self, storage_path: Path, current_timestamp: int, old_timestamp: int
    ):
        """Tests root session extraction with filtering and data population."""
        session_dir = storage_path / "session"
        session_dir.mkdir()
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create ROOT session (no parentID)
        proj_dir = session_dir / "proj_001"
        proj_dir.mkdir()
        (proj_dir / "ses_root.json").write_text(
            json.dumps(
                {
                    "id": "ses_root",
                    "projectID": "proj_001",
                    "directory": "/test",
                    "title": "Root Session Title",
                    "parentID": None,
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                }
            )
        )

        # Create CHILD session (with parentID - should be excluded)
        (proj_dir / "ses_child.json").write_text(
            json.dumps(
                {
                    "id": "ses_child",
                    "projectID": "proj_001",
                    "directory": "/test",
                    "title": "Child Session",
                    "parentID": "ses_root",
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                }
            )
        )

        # Create OLD ROOT session (should be excluded with max_days)
        (proj_dir / "ses_old.json").write_text(
            json.dumps(
                {
                    "id": "ses_old",
                    "projectID": "proj_001",
                    "directory": "/test",
                    "title": "Old Root",
                    "parentID": None,
                    "time": {"created": old_timestamp, "updated": old_timestamp},
                }
            )
        )

        # Create user message for root session
        ses_root_dir = message_dir / "ses_root"
        ses_root_dir.mkdir()
        (ses_root_dir / "msg_user.json").write_text(
            json.dumps(
                {
                    "id": "msg_user",
                    "sessionID": "ses_root",
                    "role": "user",
                    "time": {"created": current_timestamp},
                    "summary": {
                        "title": "Help me implement Plan 27",
                        "body": "Add root session tracing",
                    },
                }
            )
        )

        # Test extraction with max_days filter
        result = extract_root_sessions(storage_path, max_days=30)

        # Only recent ROOT session should be extracted
        assert len(result) == 1

        root = result[0]
        # Verify trace ID format
        assert root.trace_id == f"{ROOT_TRACE_PREFIX}ses_root"
        assert root.trace_id.startswith(ROOT_TRACE_PREFIX)

        # Verify agent type
        assert root.subagent_type == ROOT_AGENT_TYPE

        # Verify prompt from user message
        assert "Help me implement Plan 27" in root.prompt_input
        assert "root session tracing" in root.prompt_input

        # Verify child_session_id self-reference
        assert root.child_session_id == "ses_root"

    def test_falls_back_to_title_when_no_message(
        self, storage_path: Path, current_timestamp: int
    ):
        """Falls back to session title when no user message exists."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        proj_dir = session_dir / "proj_001"
        proj_dir.mkdir()
        (proj_dir / "ses_no_msg.json").write_text(
            json.dumps(
                {
                    "id": "ses_no_msg",
                    "projectID": "proj_001",
                    "directory": "/test",
                    "title": "OpenMonitor Planning",
                    "parentID": None,
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                }
            )
        )

        result = extract_root_sessions(storage_path)

        assert len(result) == 1
        assert result[0].prompt_input == "OpenMonitor Planning"

    def test_returns_empty_when_no_sessions(self, storage_path: Path):
        """Returns empty list when session directory doesn't exist."""
        result = extract_root_sessions(storage_path)
        assert result == []


# =============================================================================
# Test: load_traces with root sessions
# =============================================================================


class TestLoadTracesWithRootSessions:
    """Tests for load_traces function including root sessions."""

    def test_loads_both_root_and_delegation_traces(
        self, temp_db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads both root sessions and delegation traces into agent_traces table."""
        session_dir = storage_path / "session"
        session_dir.mkdir()
        message_dir = storage_path / "message"
        message_dir.mkdir()
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create ROOT session
        proj_dir = session_dir / "proj_001"
        proj_dir.mkdir()
        (proj_dir / "ses_root.json").write_text(
            json.dumps(
                {
                    "id": "ses_root",
                    "projectID": "proj_001",
                    "directory": "/test",
                    "title": "Test Root",
                    "parentID": None,
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                }
            )
        )

        # Create delegation trace
        create_delegation_part_file(
            part_dir,
            "prt_del",
            "msg_001",
            "ses_root",
            "tester",
            child_session_id="ses_child",
            start_ts=current_timestamp,
        )

        result = load_traces(temp_db, storage_path)

        # At least 1 root + 1 delegation
        assert result >= 2

        conn = temp_db.connect()

        # Verify root traces
        root_traces = conn.execute(
            "SELECT trace_id, subagent_type, session_id FROM agent_traces WHERE trace_id LIKE 'root_%'"
        ).fetchall()
        assert len(root_traces) == 1
        assert root_traces[0][0].startswith("root_")
        assert root_traces[0][1] == ROOT_AGENT_TYPE
        assert root_traces[0][2] == "ses_root"

        # Verify delegation traces
        delegation_traces = conn.execute(
            "SELECT trace_id, subagent_type, session_id, child_session_id FROM agent_traces WHERE trace_id NOT LIKE 'root_%'"
        ).fetchall()
        assert len(delegation_traces) == 1
        assert delegation_traces[0][0] == "prt_del"
        assert delegation_traces[0][1] == "tester"
        assert delegation_traces[0][2] == "ses_root"
        assert delegation_traces[0][3] == "ses_child"
