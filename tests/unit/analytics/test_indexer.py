"""
Tests for the indexer module.

Tests the core functionality:
- File tracking (change detection)
- Parsing all file types
- Trace building
- Queue processing
"""

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.indexer import (
    FileTracker,
    FileParser,
    ParsedSession,
    ParsedMessage,
    ParsedPart,
    ParsedDelegation,
    TraceBuilder,
    ProcessingQueue,
)


# === Fixtures ===


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Get a temp file path but delete it so DuckDB can create it fresh
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=True) as f:
        db_path = Path(f.name)

    # File is deleted, DuckDB will create it
    db = AnalyticsDB(db_path=db_path)
    db.connect()
    yield db
    db.close()

    # Cleanup
    try:
        db_path.unlink()
    except Exception:
        pass


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir)

        # Create directory structure
        for subdir in ["session", "message", "part", "todo", "project"]:
            (storage_path / subdir).mkdir(parents=True, exist_ok=True)

        yield storage_path


@pytest.fixture
def sample_session_data():
    """Sample session JSON data."""
    return {
        "id": "ses_123",
        "projectID": "proj_abc",
        "directory": "/path/to/project",
        "title": "Test Session",
        "parentID": None,
        "version": "1.0",
        "summary": {
            "additions": 10,
            "deletions": 5,
            "files": 3,
        },
        "time": {
            "created": int(datetime.now().timestamp() * 1000),
            "updated": int(datetime.now().timestamp() * 1000),
        },
    }


@pytest.fixture
def sample_message_data():
    """Sample message JSON data."""
    return {
        "id": "msg_456",
        "sessionID": "ses_123",
        "parentID": None,
        "role": "assistant",
        "agent": "executor",
        "modelID": "claude-3-5-sonnet",
        "providerID": "anthropic",
        "mode": "agent",
        "cost": 0.001,
        "finish": "completed",
        "path": {"cwd": "/path/to/project"},
        "tokens": {
            "input": 1000,
            "output": 500,
            "reasoning": 100,
            "cache": {"read": 200, "write": 100},
        },
        "time": {
            "created": int(datetime.now().timestamp() * 1000),
            "completed": int(datetime.now().timestamp() * 1000) + 5000,
        },
    }


@pytest.fixture
def sample_part_data():
    """Sample part (tool) JSON data."""
    return {
        "id": "part_789",
        "sessionID": "ses_123",
        "messageID": "msg_456",
        "type": "tool",
        "tool": "read",
        "callID": "call_xyz",
        "state": {
            "status": "completed",
            "input": {"filePath": "/path/to/file.py"},
        },
        "time": {
            "start": int(datetime.now().timestamp() * 1000),
            "end": int(datetime.now().timestamp() * 1000) + 100,
        },
    }


@pytest.fixture
def sample_task_part_data():
    """Sample task (delegation) part JSON data."""
    return {
        "id": "part_task_001",
        "sessionID": "ses_123",
        "messageID": "msg_456",
        "type": "tool",
        "tool": "task",
        "callID": "call_task",
        "state": {
            "status": "completed",
            "input": {
                "subagent_type": "tester",
                "prompt": "Run the tests",
            },
            "metadata": {
                "sessionId": "ses_child_001",
            },
            "time": {
                "start": int(datetime.now().timestamp() * 1000),
                "end": int(datetime.now().timestamp() * 1000) + 10000,
            },
        },
        "time": {
            "start": int(datetime.now().timestamp() * 1000),
            "end": int(datetime.now().timestamp() * 1000) + 10000,
        },
    }


# === FileParser Tests ===


class TestFileParser:
    """Tests for FileParser."""

    def test_parse_session_valid(self, sample_session_data):
        """Test parsing a valid session."""
        result = FileParser.parse_session(sample_session_data)

        assert isinstance(result, ParsedSession)
        assert result.id == "ses_123"
        assert result.project_id == "proj_abc"
        assert result.title == "Test Session"
        assert result.additions == 10
        assert result.deletions == 5

    def test_parse_session_invalid(self):
        """Test parsing invalid session data."""
        assert FileParser.parse_session({}) is None
        assert FileParser.parse_session({"no_id": True}) is None
        assert FileParser.parse_session("not a dict") is None

    def test_parse_message_valid(self, sample_message_data):
        """Test parsing a valid message."""
        result = FileParser.parse_message(sample_message_data)

        assert isinstance(result, ParsedMessage)
        assert result.id == "msg_456"
        assert result.session_id == "ses_123"
        assert result.agent == "executor"
        assert result.tokens_input == 1000
        assert result.tokens_output == 500

    def test_parse_part_tool(self, sample_part_data):
        """Test parsing a tool part."""
        result = FileParser.parse_part(sample_part_data)

        assert isinstance(result, ParsedPart)
        assert result.id == "part_789"
        assert result.tool_name == "read"
        assert result.tool_status == "completed"
        assert result.duration_ms == 100
        assert result.child_session_id is None

    def test_parse_part_task_extracts_child_session_id(self, sample_task_part_data):
        """Test parsing a task part extracts child_session_id from metadata."""
        result = FileParser.parse_part(sample_task_part_data)

        assert isinstance(result, ParsedPart)
        assert result.tool_name == "task"
        assert result.child_session_id == "ses_child_001"

    def test_parse_part_text(self):
        """Test parsing a text part."""
        data = {
            "id": "part_text",
            "sessionID": "ses_123",
            "messageID": "msg_456",
            "type": "text",
            "text": "Hello, world!",
            "time": {"start": 1000},
        }
        result = FileParser.parse_part(data)

        assert result.content == "Hello, world!"
        assert result.tool_name is None

    def test_parse_delegation(self, sample_task_part_data):
        """Test parsing a delegation from task tool."""
        result = FileParser.parse_delegation(sample_task_part_data)

        assert isinstance(result, ParsedDelegation)
        assert result.child_agent == "tester"
        assert result.child_session_id == "ses_child_001"

    def test_parse_skill(self):
        """Test parsing a skill usage."""
        data = {
            "id": "part_skill",
            "sessionID": "ses_123",
            "messageID": "msg_456",
            "tool": "skill",
            "state": {"input": {"name": "clean-code"}},
            "time": {"start": 1000},
        }
        result = FileParser.parse_skill(data)

        assert result.skill_name == "clean-code"

    def test_parse_file_operation(self, sample_part_data):
        """Test parsing a file operation."""
        result = FileParser.parse_file_operation(sample_part_data)

        assert result.operation == "read"
        assert result.file_path == "/path/to/file.py"

    def test_parse_todos(self):
        """Test parsing todos."""
        data = [
            {"id": "1", "content": "Task 1", "status": "pending", "priority": "high"},
            {"id": "2", "content": "Task 2", "status": "completed", "priority": "low"},
        ]
        mtime = datetime.now()
        result = FileParser.parse_todos("ses_123", data, mtime)

        assert len(result) == 2
        assert result[0].content == "Task 1"
        assert result[1].status == "completed"


# === FileTracker Tests ===


class TestFileTracker:
    """Tests for FileTracker."""

    def test_needs_indexing_new_file(self, temp_db, temp_storage):
        """Test that new files need indexing."""
        tracker = FileTracker(temp_db)

        # Create a new file
        test_file = temp_storage / "session" / "test_project" / "ses_001.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"id": "ses_001"}')

        assert tracker.needs_indexing(test_file)

    def test_needs_indexing_after_mark(self, temp_db, temp_storage):
        """Test that indexed files don't need re-indexing."""
        tracker = FileTracker(temp_db)

        # Create and mark as indexed
        test_file = temp_storage / "session" / "test_project" / "ses_001.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"id": "ses_001"}')

        tracker.mark_indexed(test_file, "session", "ses_001")

        # Should not need indexing now
        assert not tracker.needs_indexing(test_file)

    def test_needs_indexing_after_modification(self, temp_db, temp_storage):
        """Test that modified files need re-indexing."""
        tracker = FileTracker(temp_db)

        # Create and mark as indexed
        test_file = temp_storage / "session" / "test_project" / "ses_001.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"id": "ses_001"}')
        tracker.mark_indexed(test_file, "session", "ses_001")

        test_file.write_text('{"id": "ses_001", "title": "Updated"}')
        future_mtime = time.time() + 10
        os.utime(test_file, (future_mtime, future_mtime))

        # Should need indexing again
        assert tracker.needs_indexing(test_file)

    def test_get_unindexed_files(self, temp_db, temp_storage):
        """Test getting unindexed files."""
        tracker = FileTracker(temp_db)

        # Create session directory
        session_dir = temp_storage / "session" / "project1"
        session_dir.mkdir(parents=True, exist_ok=True)

        # Create some files
        for i in range(5):
            (session_dir / f"ses_{i:03d}.json").write_text(f'{{"id": "ses_{i:03d}"}}')

        # Index some of them
        tracker.mark_indexed(session_dir / "ses_000.json", "session", "ses_000")
        tracker.mark_indexed(session_dir / "ses_001.json", "session", "ses_001")

        # Get unindexed
        unindexed = tracker.get_unindexed_files(
            temp_storage / "session", "session", limit=10
        )

        # Should have 3 unindexed
        assert len(unindexed) == 3

    def test_get_stats(self, temp_db, temp_storage):
        """Test getting tracker statistics."""
        tracker = FileTracker(temp_db)

        # Create and index some files
        session_dir = temp_storage / "session" / "project1"
        session_dir.mkdir(parents=True, exist_ok=True)

        for i in range(3):
            f = session_dir / f"ses_{i}.json"
            f.write_text(f'{{"id": "ses_{i}"}}')
            tracker.mark_indexed(f, "session", f"ses_{i}")

        stats = tracker.get_stats()

        assert stats["total_files"] == 3
        assert stats["by_type"]["session"] == 3
        assert stats["errors"] == 0

    def test_needs_indexing_with_string_path(self, temp_db, temp_storage):
        """Test that needs_indexing accepts string paths (Bug fix #2)."""
        tracker = FileTracker(temp_db)

        # Create a new file
        test_file = temp_storage / "session" / "test_project" / "ses_str.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"id": "ses_str"}')

        # Test with string path - should work without raising AttributeError
        string_path = str(test_file)
        result = tracker.needs_indexing(string_path)

        assert result  # New file needs indexing

        # Mark as indexed and test again with string
        tracker.mark_indexed(test_file, "session", "ses_str")
        result = tracker.needs_indexing(string_path)

        assert not result  # Already indexed


# === ProcessingQueue Tests ===


class TestProcessingQueue:
    """Tests for ProcessingQueue."""

    def test_put_and_get(self, temp_storage):
        """Test basic put/get operations."""
        queue = ProcessingQueue()

        # Create test files
        test_file = temp_storage / "session" / "ses_001.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"id": "ses_001"}')

        # Put and get
        assert queue.put("session", test_file)
        batch = queue.get_batch(max_items=10, timeout=0.1)

        assert len(batch) == 1
        assert batch[0] == ("session", test_file)

    def test_dedupe(self, temp_storage):
        """Test that duplicates are rejected."""
        queue = ProcessingQueue()

        test_file = temp_storage / "session" / "ses_001.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"id": "ses_001"}')

        # First put succeeds
        assert queue.put("session", test_file)
        # Duplicate rejected
        assert not queue.put("session", test_file)

        assert queue.size == 1

    def test_clear(self, temp_storage):
        """Test clearing the queue."""
        queue = ProcessingQueue()

        for i in range(3):
            f = temp_storage / f"session_{i}.json"
            f.write_text("{}")
            queue.put("session", f)

        assert queue.size == 3
        queue.clear()
        assert queue.size == 0


# === TraceBuilder Tests ===


class TestTraceBuilder:
    """Tests for TraceBuilder."""

    def test_create_root_trace(self, temp_db):
        """Test creating a root trace."""
        builder = TraceBuilder(temp_db)

        trace_id = builder.create_root_trace(
            session_id="ses_123",
            title="Test Session",
            agent="executor",
            first_message="Hello",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert trace_id.startswith("root_")

        # Verify in database
        conn = temp_db.connect()
        result = conn.execute(
            "SELECT subagent_type FROM agent_traces WHERE trace_id = ?",
            [trace_id],
        ).fetchone()

        assert result[0] == "executor"

    def test_get_stats(self, temp_db):
        """Test getting trace statistics."""
        builder = TraceBuilder(temp_db)

        # Create some traces
        builder.create_root_trace(
            session_id="ses_1",
            title="Session 1",
            agent="executor",
            first_message=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        builder.create_root_trace(
            session_id="ses_2",
            title="Session 2",
            agent="tester",
            first_message=None,
            created_at=datetime.now(),
            updated_at=None,  # Running
        )

        stats = builder.get_stats()

        assert stats["total"] == 2
        assert stats["root_traces"] == 2


# === Performance Tests ===


class TestPerformance:
    """Performance-related tests."""

    def test_change_detection_performance(self, temp_db, temp_storage):
        """Test that change detection is fast."""
        tracker = FileTracker(temp_db)

        # Create 100 files
        session_dir = temp_storage / "session" / "project1"
        session_dir.mkdir(parents=True, exist_ok=True)

        for i in range(100):
            f = session_dir / f"ses_{i:03d}.json"
            f.write_text(f'{{"id": "ses_{i:03d}"}}')
            tracker.mark_indexed(f, "session", f"ses_{i:03d}")

        # Time checking all files
        start = time.time()
        for i in range(100):
            f = session_dir / f"ses_{i:03d}.json"
            tracker.needs_indexing(f)
        elapsed = time.time() - start

        # Should be very fast (< 1 second for 100 files)
        assert elapsed < 1.0, f"Change detection took {elapsed:.2f}s for 100 files"

    def test_batch_limit_respected(self, temp_db, temp_storage):
        """Test that backfill respects batch limits."""
        tracker = FileTracker(temp_db)

        # Create 200 files
        session_dir = temp_storage / "session" / "project1"
        session_dir.mkdir(parents=True, exist_ok=True)

        for i in range(200):
            f = session_dir / f"ses_{i:03d}.json"
            f.write_text(f'{{"id": "ses_{i:03d}"}}')

        # Get with limit
        unindexed = tracker.get_unindexed_files(
            temp_storage / "session", "session", limit=100
        )

        # Should respect limit
        assert len(unindexed) <= 100
