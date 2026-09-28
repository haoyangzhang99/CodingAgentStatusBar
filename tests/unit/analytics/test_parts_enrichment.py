"""
Tests for Parts Enrichment (Plan 34 - US-05).

Covers:
- DB Schema: step_events, patches tables and parts enrichment columns
- Loader: _process_reasoning_part, _process_step_start_part, _process_step_finish_part,
          _process_patch_part, _process_compaction_part, _process_file_part
- Service: get_session_reasoning, get_session_steps, get_session_git_history, get_session_precise_cost
- API: /api/session/<id>/reasoning, /api/session/<id>/steps, /api/session/<id>/git-history,
       /api/session/<id>/precise-cost
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import time

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.loaders.parts import (
    load_parts_fast,
    LoaderStats,
    _process_reasoning_part,
    _process_step_start_part,
    _process_step_finish_part,
    _process_patch_part,
    _process_compaction_part,
    _process_file_part,
)
from opencode_status_bar.analytics.tracing import TracingDataService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service(tracing_service: TracingDataService) -> TracingDataService:
    """Alias for tracing_service from conftest."""
    return tracing_service


@pytest.fixture
def current_timestamp() -> int:
    """Current timestamp in milliseconds."""
    return int(time.time() * 1000)


# =============================================================================
# Test DB Schema - step_events and patches tables
# =============================================================================


class TestDBSchema:
    """Tests for database schema - step_events, patches tables and parts columns."""

    def test_step_events_table_exists(self, analytics_db: AnalyticsDB):
        """step_events table should exist with correct schema."""
        conn = analytics_db.connect()

        # Query schema
        result = conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'step_events' ORDER BY ordinal_position"
        ).fetchall()

        columns = {row[0]: row[1] for row in result}

        # Verify required columns
        assert "id" in columns
        assert "session_id" in columns
        assert "message_id" in columns
        assert "event_type" in columns
        assert "reason" in columns
        assert "snapshot_hash" in columns
        assert "cost" in columns
        assert "tokens_input" in columns
        assert "tokens_output" in columns
        assert "tokens_reasoning" in columns
        assert "tokens_cache_read" in columns
        assert "tokens_cache_write" in columns
        assert "created_at" in columns

    def test_patches_table_exists(self, analytics_db: AnalyticsDB):
        """patches table should exist with correct schema."""
        conn = analytics_db.connect()

        # Query schema
        result = conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'patches' ORDER BY ordinal_position"
        ).fetchall()

        columns = {row[0]: row[1] for row in result}

        # Verify required columns
        assert "id" in columns
        assert "session_id" in columns
        assert "message_id" in columns
        assert "git_hash" in columns
        assert "files" in columns
        assert "created_at" in columns

    def test_parts_enrichment_columns_exist(self, analytics_db: AnalyticsDB):
        """parts table should have enrichment columns."""
        conn = analytics_db.connect()

        # Query schema
        result = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'parts'"
        ).fetchall()

        columns = {row[0] for row in result}

        # Verify enrichment columns (added via migration)
        assert "reasoning_text" in columns
        assert "anthropic_signature" in columns
        assert "compaction_auto" in columns
        assert "file_mime" in columns
        assert "file_name" in columns

    def test_step_events_indexes_exist(self, analytics_db: AnalyticsDB):
        """step_events table should have performance indexes."""
        conn = analytics_db.connect()

        # Check indexes via DuckDB metadata
        result = conn.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'step_events'"
        ).fetchall()

        index_names = [row[0] for row in result]

        # At least session_id index should exist
        assert any("session" in idx.lower() for idx in index_names)

    def test_patches_indexes_exist(self, analytics_db: AnalyticsDB):
        """patches table should have performance indexes."""
        conn = analytics_db.connect()

        # Check indexes via DuckDB metadata
        result = conn.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'patches'"
        ).fetchall()

        index_names = [row[0] for row in result]

        # At least session_id index should exist
        assert any("session" in idx.lower() for idx in index_names)

    def test_insert_step_event(self, analytics_db: AnalyticsDB):
        """Should be able to insert step_events."""
        conn = analytics_db.connect()

        conn.execute(
            """INSERT INTO step_events 
               (id, session_id, message_id, event_type, reason, snapshot_hash,
                cost, tokens_input, tokens_output, tokens_reasoning,
                tokens_cache_read, tokens_cache_write, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "step_001",
                "ses_001",
                "msg_001",
                "finish",
                "tool_use",
                "abc123",
                0.00123,
                1000,
                500,
                100,
                200,
                50,
                datetime.now(),
            ],
        )

        result = conn.execute(
            "SELECT id, event_type, cost FROM step_events WHERE id = ?",
            ["step_001"],
        ).fetchone()

        assert result[0] == "step_001"
        assert result[1] == "finish"
        assert float(result[2]) == pytest.approx(0.00123, abs=0.0001)

    def test_insert_patch(self, analytics_db: AnalyticsDB):
        """Should be able to insert patches with file array."""
        conn = analytics_db.connect()

        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]

        conn.execute(
            """INSERT INTO patches 
               (id, session_id, message_id, git_hash, files, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "patch_001",
                "ses_001",
                "msg_001",
                "abc123def456",
                files,
                datetime.now(),
            ],
        )

        result = conn.execute(
            "SELECT id, git_hash, files FROM patches WHERE id = ?",
            ["patch_001"],
        ).fetchone()

        assert result[0] == "patch_001"
        assert result[1] == "abc123def456"
        assert list(result[2]) == files


# =============================================================================
# Test LoaderStats
# =============================================================================


class TestLoaderStats:
    """Tests for LoaderStats dataclass."""

    def test_initial_values(self):
        """Stats should initialize to zero."""
        stats = LoaderStats()

        assert stats.text == 0
        assert stats.tool == 0
        assert stats.reasoning == 0
        assert stats.step_start == 0
        assert stats.step_finish == 0
        assert stats.patch == 0
        assert stats.compaction == 0
        assert stats.file == 0
        assert stats.total == 0

    def test_total_calculation(self):
        """Total should sum all counters."""
        stats = LoaderStats(
            text=10,
            tool=20,
            reasoning=5,
            step_start=3,
            step_finish=3,
            patch=2,
            compaction=1,
            file=4,
        )

        assert stats.total == 48

    def test_str_representation(self):
        """String representation should list non-zero counts."""
        stats = LoaderStats(text=5, tool=3, reasoning=2)

        result = str(stats)

        assert "5 text" in result
        assert "3 tools" in result
        assert "2 reasoning" in result
        assert "steps" not in result  # step_start + step_finish = 0
        assert "patches" not in result

    def test_str_empty(self):
        """Empty stats should show '0'."""
        stats = LoaderStats()
        assert str(stats) == "0"


# =============================================================================
# Test Loader Functions - Processing Parts
# =============================================================================


class TestProcessReasoningPart:
    """Tests for _process_reasoning_part function."""

    def test_extracts_reasoning_text(self):
        """Should extract reasoning text from part data."""
        data = {
            "text": "I am thinking about how to solve this problem...",
            "metadata": {"anthropic": {"signature": "sig_abc123"}},
        }
        batch: list = []
        stats = LoaderStats()
        created_at = datetime.now()

        _process_reasoning_part(
            data, "prt_001", "ses_001", "msg_001", created_at, batch, stats
        )

        assert len(batch) == 1
        assert stats.reasoning == 1

        # Check tuple structure
        row = batch[0]
        assert row[0] == "prt_001"  # id
        assert row[1] == "ses_001"  # session_id
        assert row[2] == "msg_001"  # message_id
        assert row[3] == "reasoning"  # part_type
        assert (
            row[13] == "I am thinking about how to solve this problem..."
        )  # reasoning_text
        assert row[14] == "sig_abc123"  # anthropic_signature

    def test_handles_missing_signature(self):
        """Should handle missing anthropic signature."""
        data = {"text": "Some reasoning", "metadata": {}}
        batch: list = []
        stats = LoaderStats()

        _process_reasoning_part(
            data, "prt_001", "ses_001", "msg_001", None, batch, stats
        )

        assert len(batch) == 1
        row = batch[0]
        assert row[13] == "Some reasoning"  # reasoning_text
        assert row[14] is None  # anthropic_signature

    def test_handles_empty_text(self):
        """Should handle empty reasoning text."""
        data = {"text": "", "metadata": {}}
        batch: list = []
        stats = LoaderStats()

        _process_reasoning_part(
            data, "prt_001", "ses_001", "msg_001", None, batch, stats
        )

        assert len(batch) == 1
        assert stats.reasoning == 1
        assert batch[0][13] == ""  # Empty text is still stored


class TestProcessStepStartPart:
    """Tests for _process_step_start_part function."""

    def test_extracts_snapshot_hash(self):
        """Should extract snapshot hash from step-start event."""
        data = {"snapshot": "snap_abc123"}
        batch: list = []
        stats = LoaderStats()
        created_at = datetime.now()

        _process_step_start_part(
            data, "prt_001", "ses_001", "msg_001", created_at, batch, stats
        )

        assert len(batch) == 1
        assert stats.step_start == 1

        row = batch[0]
        assert row[0] == "prt_001"  # id
        assert row[1] == "ses_001"  # session_id
        assert row[2] == "msg_001"  # message_id
        assert row[3] == "start"  # event_type
        assert row[4] is None  # reason
        assert row[5] == "snap_abc123"  # snapshot_hash
        assert row[6] == 0  # cost
        assert row[7] == 0  # tokens_input

    def test_handles_missing_snapshot(self):
        """Should handle missing snapshot."""
        data = {}
        batch: list = []
        stats = LoaderStats()

        _process_step_start_part(
            data, "prt_001", "ses_001", "msg_001", None, batch, stats
        )

        assert len(batch) == 1
        assert batch[0][5] is None  # snapshot_hash


class TestProcessStepFinishPart:
    """Tests for _process_step_finish_part function."""

    def test_extracts_tokens_and_cost(self):
        """Should extract tokens and cost from step-finish event."""
        data = {
            "reason": "tool_use",
            "snapshot": "snap_xyz789",
            "cost": 0.00456,
            "tokens": {
                "input": 1500,
                "output": 750,
                "reasoning": 200,
                "cacheRead": 300,
                "cacheWrite": 100,
            },
        }
        batch: list = []
        stats = LoaderStats()
        created_at = datetime.now()

        _process_step_finish_part(
            data, "prt_002", "ses_001", "msg_001", created_at, batch, stats
        )

        assert len(batch) == 1
        assert stats.step_finish == 1

        row = batch[0]
        assert row[0] == "prt_002"  # id
        assert row[3] == "finish"  # event_type
        assert row[4] == "tool_use"  # reason
        assert row[5] == "snap_xyz789"  # snapshot_hash
        assert row[6] == 0.00456  # cost
        assert row[7] == 1500  # tokens_input
        assert row[8] == 750  # tokens_output
        assert row[9] == 200  # tokens_reasoning
        assert row[10] == 300  # tokens_cache_read
        assert row[11] == 100  # tokens_cache_write

    def test_handles_missing_tokens(self):
        """Should handle missing tokens with defaults."""
        data = {"reason": "end_turn"}
        batch: list = []
        stats = LoaderStats()

        _process_step_finish_part(
            data, "prt_002", "ses_001", "msg_001", None, batch, stats
        )

        row = batch[0]
        assert row[6] == 0  # cost default
        assert row[7] == 0  # tokens_input default
        assert row[8] == 0  # tokens_output default

    def test_handles_invalid_tokens_type(self):
        """Should handle non-dict tokens gracefully."""
        data = {"tokens": "invalid"}
        batch: list = []
        stats = LoaderStats()

        _process_step_finish_part(
            data, "prt_002", "ses_001", "msg_001", None, batch, stats
        )

        row = batch[0]
        assert row[7] == 0  # Falls back to defaults


class TestProcessPatchPart:
    """Tests for _process_patch_part function."""

    def test_extracts_git_hash_and_files(self):
        """Should extract git hash and files from patch part."""
        data = {"hash": "abc123def456", "files": ["src/main.py", "src/utils.py"]}
        batch: list = []
        stats = LoaderStats()
        created_at = datetime.now()

        _process_patch_part(
            data, "prt_003", "ses_001", "msg_001", created_at, batch, stats
        )

        assert len(batch) == 1
        assert stats.patch == 1

        row = batch[0]
        assert row[0] == "prt_003"  # id
        assert row[1] == "ses_001"  # session_id
        assert row[2] == "msg_001"  # message_id
        assert row[3] == "abc123def456"  # git_hash
        assert row[4] == ["src/main.py", "src/utils.py"]  # files
        assert row[5] == created_at  # created_at

    def test_skips_missing_hash(self):
        """Should skip patch without git hash."""
        data = {"files": ["src/main.py"]}
        batch: list = []
        stats = LoaderStats()

        _process_patch_part(data, "prt_003", "ses_001", "msg_001", None, batch, stats)

        assert len(batch) == 0
        assert stats.patch == 0

    def test_handles_missing_files(self):
        """Should handle missing files list."""
        data = {"hash": "abc123"}
        batch: list = []
        stats = LoaderStats()

        _process_patch_part(data, "prt_003", "ses_001", "msg_001", None, batch, stats)

        assert len(batch) == 1
        assert batch[0][4] == []  # Empty files list

    def test_handles_invalid_files_type(self):
        """Should handle non-list files."""
        data = {"hash": "abc123", "files": "not_a_list"}
        batch: list = []
        stats = LoaderStats()

        _process_patch_part(data, "prt_003", "ses_001", "msg_001", None, batch, stats)

        assert len(batch) == 1
        assert batch[0][4] == []  # Falls back to empty list


class TestProcessCompactionPart:
    """Tests for _process_compaction_part function."""

    def test_extracts_auto_flag(self):
        """Should extract auto compaction flag."""
        data = {"auto": True}
        batch: list = []
        stats = LoaderStats()
        created_at = datetime.now()

        _process_compaction_part(
            data, "prt_004", "ses_001", "msg_001", created_at, batch, stats
        )

        assert len(batch) == 1
        assert stats.compaction == 1

        row = batch[0]
        assert row[0] == "prt_004"  # id
        assert row[3] == "compaction"  # part_type
        assert row[15]  # compaction_auto

    def test_handles_manual_compaction(self):
        """Should handle manual compaction (auto=False)."""
        data = {"auto": False}
        batch: list = []
        stats = LoaderStats()

        _process_compaction_part(
            data, "prt_004", "ses_001", "msg_001", None, batch, stats
        )

        assert not batch[0][15]

    def test_defaults_to_false(self):
        """Should default to auto=False when missing."""
        data = {}
        batch: list = []
        stats = LoaderStats()

        _process_compaction_part(
            data, "prt_004", "ses_001", "msg_001", None, batch, stats
        )

        assert not batch[0][15]


class TestProcessFilePart:
    """Tests for _process_file_part function."""

    def test_extracts_mime_and_filename(self):
        """Should extract MIME type and filename."""
        data = {"mime": "image/png", "filename": "screenshot.png"}
        batch: list = []
        stats = LoaderStats()
        created_at = datetime.now()

        _process_file_part(
            data, "prt_005", "ses_001", "msg_001", created_at, batch, stats
        )

        assert len(batch) == 1
        assert stats.file == 1

        row = batch[0]
        assert row[0] == "prt_005"  # id
        assert row[3] == "file"  # part_type
        assert row[16] == "image/png"  # file_mime
        assert row[17] == "screenshot.png"  # file_name

    def test_skips_empty_metadata(self):
        """Should skip file without mime or filename."""
        data = {}
        batch: list = []
        stats = LoaderStats()

        _process_file_part(data, "prt_005", "ses_001", "msg_001", None, batch, stats)

        assert len(batch) == 0
        assert stats.file == 0

    def test_accepts_partial_metadata(self):
        """Should accept file with only mime or only filename."""
        # Only mime
        data = {"mime": "text/plain"}
        batch: list = []
        stats = LoaderStats()

        _process_file_part(data, "prt_005", "ses_001", "msg_001", None, batch, stats)

        assert len(batch) == 1
        assert batch[0][16] == "text/plain"
        assert batch[0][17] is None


# =============================================================================
# Test Loader - load_parts_fast Integration
# =============================================================================


class TestLoadPartsFast:
    """Tests for load_parts_fast function with file system integration."""

    def test_loads_reasoning_parts(self, analytics_db: AnalyticsDB, temp_storage: Path):
        """Should load reasoning parts from storage."""
        # Create part file
        msg_dir = temp_storage / "part" / "msg_001"
        msg_dir.mkdir(parents=True)

        part_file = msg_dir / "prt_reason_001.json"
        part_file.write_text(
            json.dumps(
                {
                    "id": "prt_reason_001",
                    "sessionID": "ses_001",
                    "messageID": "msg_001",
                    "type": "reasoning",
                    "text": "Analyzing the problem...",
                    "metadata": {"anthropic": {"signature": "sig_test"}},
                    "time": {"start": int(time.time() * 1000)},
                }
            )
        )

        count = load_parts_fast(analytics_db, temp_storage, max_days=30)

        assert count >= 1

        # Verify data in DB
        conn = analytics_db.connect()
        result = conn.execute(
            "SELECT reasoning_text, anthropic_signature FROM parts WHERE id = ?",
            ["prt_reason_001"],
        ).fetchone()

        assert result[0] == "Analyzing the problem..."
        assert result[1] == "sig_test"

    def test_loads_step_events(self, analytics_db: AnalyticsDB, temp_storage: Path):
        """Should load step-start and step-finish events."""
        msg_dir = temp_storage / "part" / "msg_001"
        msg_dir.mkdir(parents=True)

        # Step start
        (msg_dir / "prt_step_start.json").write_text(
            json.dumps(
                {
                    "id": "prt_step_start",
                    "sessionID": "ses_001",
                    "messageID": "msg_001",
                    "type": "step-start",
                    "snapshot": "snap_001",
                    "time": {"start": int(time.time() * 1000)},
                }
            )
        )

        # Step finish
        (msg_dir / "prt_step_finish.json").write_text(
            json.dumps(
                {
                    "id": "prt_step_finish",
                    "sessionID": "ses_001",
                    "messageID": "msg_001",
                    "type": "step-finish",
                    "reason": "tool_use",
                    "cost": 0.005,
                    "tokens": {"input": 1000, "output": 500, "reasoning": 100},
                    "time": {"start": int(time.time() * 1000)},
                }
            )
        )

        count = load_parts_fast(analytics_db, temp_storage, max_days=30)

        assert count >= 2

        # Verify step_events table
        conn = analytics_db.connect()
        results = conn.execute(
            "SELECT id, event_type, cost FROM step_events WHERE session_id = ? ORDER BY id",
            ["ses_001"],
        ).fetchall()

        assert len(results) == 2
        events = {r[1]: r for r in results}
        assert "start" in events
        assert "finish" in events
        assert float(events["finish"][2]) == pytest.approx(0.005, abs=0.0001)

    def test_loads_patches(self, analytics_db: AnalyticsDB, temp_storage: Path):
        """Should load patch parts to patches table."""
        msg_dir = temp_storage / "part" / "msg_001"
        msg_dir.mkdir(parents=True)

        (msg_dir / "prt_patch_001.json").write_text(
            json.dumps(
                {
                    "id": "prt_patch_001",
                    "sessionID": "ses_001",
                    "messageID": "msg_001",
                    "type": "patch",
                    "hash": "abc123def",
                    "files": ["file1.py", "file2.py"],
                    "time": {"start": int(time.time() * 1000)},
                }
            )
        )

        load_parts_fast(analytics_db, temp_storage, max_days=30)

        conn = analytics_db.connect()
        result = conn.execute(
            "SELECT git_hash, files FROM patches WHERE id = ?", ["prt_patch_001"]
        ).fetchone()

        assert result[0] == "abc123def"
        assert list(result[1]) == ["file1.py", "file2.py"]

    def test_skips_old_data(self, analytics_db: AnalyticsDB, temp_storage: Path):
        """Should skip parts older than max_days."""
        msg_dir = temp_storage / "part" / "msg_old"
        msg_dir.mkdir(parents=True)

        # Create file with old modification time
        part_file = msg_dir / "prt_old.json"
        part_file.write_text(
            json.dumps(
                {
                    "id": "prt_old",
                    "sessionID": "ses_old",
                    "messageID": "msg_old",
                    "type": "text",
                    "text": "Old message",
                    "time": {
                        "start": int(
                            (datetime.now() - timedelta(days=60)).timestamp() * 1000
                        )
                    },
                }
            )
        )

        # Set old mtime on directory
        old_time = time.time() - 60 * 86400  # 60 days ago
        import os

        os.utime(msg_dir, (old_time, old_time))

        count = load_parts_fast(analytics_db, temp_storage, max_days=30)

        conn = analytics_db.connect()
        result = conn.execute(
            "SELECT COUNT(*) FROM parts WHERE id = ?", ["prt_old"]
        ).fetchone()

        assert result[0] == 0

    def test_handles_empty_storage(self, analytics_db: AnalyticsDB, temp_storage: Path):
        """Should handle missing part directory gracefully."""
        # Don't create part directory
        count = load_parts_fast(analytics_db, temp_storage, max_days=30)

        assert count == 0


# =============================================================================
# Test Service - Session Queries (Plan 34 methods)
# =============================================================================


class TestGetSessionReasoning:
    """Tests for get_session_reasoning service method."""

    def test_returns_reasoning_entries(self, analytics_db: AnalyticsDB):
        """Should return reasoning parts for session."""
        conn = analytics_db.connect()

        # Insert test data
        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_001", "Test Session", datetime.now()],
        )
        conn.execute(
            """INSERT INTO parts 
               (id, session_id, message_id, part_type, reasoning_text, anthropic_signature, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt_001",
                "ses_001",
                "msg_001",
                "reasoning",
                "First reasoning...",
                "sig_001",
                datetime.now(),
            ],
        )
        conn.execute(
            """INSERT INTO parts 
               (id, session_id, message_id, part_type, reasoning_text, anthropic_signature, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt_002",
                "ses_001",
                "msg_002",
                "reasoning",
                "Second reasoning...",
                None,
                datetime.now(),
            ],
        )

        service = TracingDataService(db=analytics_db)
        result = service.get_session_reasoning("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert result["meta"]["count"] == 2
        assert result["summary"]["total_entries"] == 2
        assert result["summary"]["signed_entries"] == 1
        assert len(result["details"]) == 2

        # Check entry structure
        entry = result["details"][0]
        assert "id" in entry
        assert "text" in entry
        assert "signature" in entry
        assert "has_signature" in entry

    def test_returns_empty_for_no_reasoning(self, analytics_db: AnalyticsDB):
        """Should return empty list for session without reasoning."""
        conn = analytics_db.connect()
        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_empty", "Empty Session", datetime.now()],
        )

        service = TracingDataService(db=analytics_db)
        result = service.get_session_reasoning("ses_empty")

        assert result["meta"]["count"] == 0
        assert result["summary"]["total_entries"] == 0
        assert result["details"] == []


class TestGetSessionSteps:
    """Tests for get_session_steps service method."""

    def test_returns_step_events(self, analytics_db: AnalyticsDB):
        """Should return step events with token counts and costs."""
        conn = analytics_db.connect()

        # Insert test data
        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_001", "Test Session", datetime.now()],
        )
        conn.execute(
            """INSERT INTO step_events 
               (id, session_id, message_id, event_type, reason, cost,
                tokens_input, tokens_output, tokens_reasoning, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "step_001",
                "ses_001",
                "msg_001",
                "start",
                None,
                0,
                0,
                0,
                0,
                datetime.now(),
            ],
        )
        conn.execute(
            """INSERT INTO step_events 
               (id, session_id, message_id, event_type, reason, cost,
                tokens_input, tokens_output, tokens_reasoning, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "step_002",
                "ses_001",
                "msg_001",
                "finish",
                "tool_use",
                0.005,
                1000,
                500,
                100,
                datetime.now(),
            ],
        )

        service = TracingDataService(db=analytics_db)
        result = service.get_session_steps("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert result["meta"]["count"] == 2
        assert result["summary"]["total_steps"] == 1  # Only finish events counted
        assert result["summary"]["total_cost"] == pytest.approx(0.005, abs=0.0001)
        assert result["summary"]["total_tokens_input"] == 1000
        assert result["summary"]["total_tokens_output"] == 500
        assert result["summary"]["total_tokens_reasoning"] == 100
        assert len(result["details"]) == 2

    def test_accumulates_multiple_steps(self, analytics_db: AnalyticsDB):
        """Should accumulate costs from multiple step-finish events."""
        conn = analytics_db.connect()

        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_multi", "Multi Session", datetime.now()],
        )

        # Insert multiple finish events
        for i in range(3):
            conn.execute(
                """INSERT INTO step_events 
                   (id, session_id, message_id, event_type, cost, tokens_input, tokens_output, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    f"step_{i}",
                    "ses_multi",
                    f"msg_{i}",
                    "finish",
                    0.001 * (i + 1),
                    100 * (i + 1),
                    50 * (i + 1),
                    datetime.now(),
                ],
            )

        service = TracingDataService(db=analytics_db)
        result = service.get_session_steps("ses_multi")

        assert result["summary"]["total_steps"] == 3
        # 0.001 + 0.002 + 0.003 = 0.006
        assert result["summary"]["total_cost"] == pytest.approx(0.006, abs=0.0001)
        # 100 + 200 + 300 = 600
        assert result["summary"]["total_tokens_input"] == 600


class TestGetSessionGitHistory:
    """Tests for get_session_git_history service method."""

    def test_returns_patches(self, analytics_db: AnalyticsDB):
        """Should return git patches with file lists."""
        conn = analytics_db.connect()

        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_001", "Test Session", datetime.now()],
        )
        conn.execute(
            """INSERT INTO patches (id, session_id, message_id, git_hash, files, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "patch_001",
                "ses_001",
                "msg_001",
                "abc123",
                ["src/main.py", "src/utils.py"],
                datetime.now(),
            ],
        )
        conn.execute(
            """INSERT INTO patches (id, session_id, message_id, git_hash, files, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "patch_002",
                "ses_001",
                "msg_002",
                "def456",
                ["tests/test_main.py"],
                datetime.now(),
            ],
        )

        service = TracingDataService(db=analytics_db)
        result = service.get_session_git_history("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert result["meta"]["commits"] == 2
        assert result["summary"]["total_commits"] == 2
        assert result["summary"]["unique_files"] == 3
        assert len(result["details"]) == 2

        # Check patch structure
        patch = result["details"][0]
        assert "id" in patch
        assert "hash" in patch
        assert "files" in patch
        assert "file_count" in patch

    def test_returns_empty_for_no_patches(self, analytics_db: AnalyticsDB):
        """Should return empty for session without patches."""
        conn = analytics_db.connect()
        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_empty", "Empty Session", datetime.now()],
        )

        service = TracingDataService(db=analytics_db)
        result = service.get_session_git_history("ses_empty")

        assert result["meta"]["commits"] == 0
        assert result["summary"]["total_commits"] == 0
        assert result["details"] == []


class TestGetSessionPreciseCost:
    """Tests for get_session_precise_cost service method."""

    def test_calculates_precise_cost(self, analytics_db: AnalyticsDB):
        """Should calculate precise cost from step_events."""
        conn = analytics_db.connect()

        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_001", "Test Session", datetime.now()],
        )

        # Insert step_events with costs
        for i in range(3):
            conn.execute(
                """INSERT INTO step_events 
                   (id, session_id, message_id, event_type, cost,
                    tokens_input, tokens_output, tokens_reasoning,
                    tokens_cache_read, tokens_cache_write, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    f"step_{i}",
                    "ses_001",
                    f"msg_{i}",
                    "finish",
                    0.01 * (i + 1),  # 0.01, 0.02, 0.03
                    1000,
                    500,
                    100,
                    200,
                    50,
                    datetime.now(),
                ],
            )

        # Insert message with estimated cost
        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, cost, tokens_input, tokens_output, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ["msg_001", "ses_001", "assistant", 0.05, 2500, 1000, datetime.now()],
        )

        service = TracingDataService(db=analytics_db)
        result = service.get_session_precise_cost("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        # Precise cost: 0.01 + 0.02 + 0.03 = 0.06
        assert result["precise"]["cost_usd"] == pytest.approx(0.06, abs=0.001)
        assert result["precise"]["tokens_input"] == 3000
        assert result["precise"]["tokens_output"] == 1500
        assert result["precise"]["step_count"] == 3

        # Estimated cost from messages
        assert result["estimated"]["cost_usd"] == pytest.approx(0.05, abs=0.001)

        # Comparison
        assert result["comparison"]["has_precise_data"]
        assert result["comparison"]["difference_usd"] == pytest.approx(0.01, abs=0.001)

    def test_returns_zeros_for_no_data(self, analytics_db: AnalyticsDB):
        """Should return zeros for session without data."""
        conn = analytics_db.connect()
        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_empty", "Empty Session", datetime.now()],
        )

        service = TracingDataService(db=analytics_db)
        result = service.get_session_precise_cost("ses_empty")

        assert result["precise"]["cost_usd"] == 0
        assert not result["comparison"]["has_precise_data"]


# =============================================================================
# Test API Endpoints (Plan 34 endpoints)
# =============================================================================


class TestAPIEndpoints:
    """Tests for API endpoints using Flask test client."""

    @pytest.fixture
    def app(self, analytics_db: AnalyticsDB):
        """Create Flask app with test configuration."""
        from flask import Flask
        from opencode_status_bar.api.routes.sessions import sessions_bp
        from opencode_status_bar.api.routes._context import RouteContext

        app = Flask(__name__)
        app.register_blueprint(sessions_bp)

        # Configure route context
        service = TracingDataService(db=analytics_db)
        context = RouteContext.get_instance()
        context.configure(
            db_lock=threading.Lock(),
            get_service=lambda: service,
        )

        return app

    @pytest.fixture
    def client(self, app):
        """Create Flask test client."""
        return app.test_client()

    @pytest.fixture
    def populated_db(self, analytics_db: AnalyticsDB):
        """Populate database with test data for API tests."""
        conn = analytics_db.connect()

        # Insert session
        conn.execute(
            """INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)""",
            ["ses_api", "API Test Session", datetime.now()],
        )

        # Insert reasoning parts
        conn.execute(
            """INSERT INTO parts 
               (id, session_id, message_id, part_type, reasoning_text, anthropic_signature, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt_reason",
                "ses_api",
                "msg_001",
                "reasoning",
                "Thinking...",
                "sig_123",
                datetime.now(),
            ],
        )

        # Insert step events
        conn.execute(
            """INSERT INTO step_events 
               (id, session_id, message_id, event_type, cost, tokens_input, tokens_output, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "step_001",
                "ses_api",
                "msg_001",
                "finish",
                0.01,
                1000,
                500,
                datetime.now(),
            ],
        )

        # Insert patches
        conn.execute(
            """INSERT INTO patches (id, session_id, message_id, git_hash, files, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["patch_001", "ses_api", "msg_001", "abc123", ["file.py"], datetime.now()],
        )

        return analytics_db

    def test_reasoning_endpoint(self, client, populated_db):
        """GET /api/session/<id>/reasoning should return reasoning data."""
        response = client.get("/api/session/ses_api/reasoning")

        assert response.status_code == 200
        data = response.json
        assert data["success"]
        assert data["data"]["meta"]["session_id"] == "ses_api"
        assert data["data"]["summary"]["total_entries"] == 1
        assert len(data["data"]["details"]) == 1

    def test_steps_endpoint(self, client, populated_db):
        """GET /api/session/<id>/steps should return step events."""
        response = client.get("/api/session/ses_api/steps")

        assert response.status_code == 200
        data = response.json
        assert data["success"]
        assert data["data"]["meta"]["session_id"] == "ses_api"
        assert data["data"]["summary"]["total_steps"] == 1
        assert data["data"]["summary"]["total_cost"] == pytest.approx(0.01, abs=0.001)

    def test_git_history_endpoint(self, client, populated_db):
        """GET /api/session/<id>/git-history should return patches."""
        response = client.get("/api/session/ses_api/git-history")

        assert response.status_code == 200
        data = response.json
        assert data["success"]
        assert data["data"]["meta"]["session_id"] == "ses_api"
        assert data["data"]["summary"]["total_commits"] == 1

    def test_precise_cost_endpoint(self, client, populated_db):
        """GET /api/session/<id>/precise-cost should return cost data."""
        response = client.get("/api/session/ses_api/precise-cost")

        assert response.status_code == 200
        data = response.json
        assert data["success"]
        assert data["data"]["meta"]["session_id"] == "ses_api"
        assert data["data"]["precise"]["cost_usd"] == pytest.approx(0.01, abs=0.001)
        assert data["data"]["estimated"]["cost_usd"] == 0.0
        assert data["data"]["comparison"]["has_precise_data"]

    def test_reasoning_endpoint_nonexistent_session(self, client, analytics_db):
        """Reasoning endpoint should handle non-existent session."""
        response = client.get("/api/session/nonexistent/reasoning")

        assert response.status_code == 200
        data = response.json
        assert data["success"]
        assert data["data"]["meta"]["count"] == 0

    def test_steps_endpoint_nonexistent_session(self, client, analytics_db):
        """Steps endpoint should handle non-existent session."""
        response = client.get("/api/session/nonexistent/steps")

        assert response.status_code == 200
        data = response.json
        assert data["success"]
        assert data["data"]["summary"]["total_steps"] == 0
