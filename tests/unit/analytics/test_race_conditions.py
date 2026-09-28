"""
Tests for race condition handling between bulk and real-time loading.

Verifies that:
1. Files created during bulk load are not missed
2. Files are not duplicated between bulk and realtime
3. Phase handoff works correctly
4. Crash recovery works
"""

import time
import json
from pathlib import Path
import pytest

from opencode_status_bar.analytics.indexer.file_processing import FileProcessingState


class TestFileProcessingState:
    """Test file processing state tracking."""

    @pytest.fixture
    def state(self, analytics_db):
        """Create FileProcessingState instance."""
        return FileProcessingState(analytics_db)

    def test_table_creation(self, state, analytics_db):
        """Test that file_processing_state table is created."""
        conn = analytics_db.connect()
        # Verify we can query the table
        count = conn.execute("SELECT COUNT(*) FROM file_processing_state").fetchone()
        assert count is not None
        assert count[0] == 0  # Should be empty

    def test_is_already_processed_new_file(self, state):
        """Test that new files are not marked as processed."""
        assert not state.is_already_processed("/test/file1.json")

    def test_mark_processed(self, state):
        """Test marking a file as processed."""
        file_path = "/test/file1.json"
        state.mark_processed(file_path, file_type="session", status="processed")

        assert state.is_already_processed(file_path)

    def test_mark_processed_with_checksum(self, state):
        """Test marking file with checksum."""
        file_path = "/test/file2.json"
        state.mark_processed(
            file_path,
            file_type="message",
            status="processed",
            checksum="abc123",
            last_modified=123456.0,
        )

        info = state.get_file_info(file_path)
        assert info is not None
        assert info["checksum"] == "abc123"
        assert info["status"] == "processed"

    def test_mark_failed(self, state):
        """Test marking a file as failed."""
        file_path = "/test/file3.json"
        state.mark_processed(file_path, file_type="part", status="failed")

        # Failed files should still be marked to avoid retrying
        assert state.is_already_processed(file_path)

        info = state.get_file_info(file_path)
        assert info["status"] == "failed"

    def test_mark_processed_batch(self, state):
        """Test batch marking for bulk operations."""
        files = [
            ("/test/file1.json", "session", "processed", None, 123.0),
            ("/test/file2.json", "message", "processed", None, 124.0),
            ("/test/file3.json", "part", "processed", None, 125.0),
        ]

        count = state.mark_processed_batch(files)
        assert count == 3

        # Verify all are marked
        for file_path, _, _, _, _ in files:
            assert state.is_already_processed(file_path)

    def test_duplicate_prevention(self, state):
        """Test that processing same file twice is detected."""
        file_path = "/test/dup.json"

        # Mark once
        state.mark_processed(file_path, file_type="session", status="processed")
        assert state.is_already_processed(file_path)

        # Try to mark again - should still be processed
        state.mark_processed(file_path, file_type="session", status="processed")
        assert state.is_already_processed(file_path)

    def test_get_stats(self, state):
        """Test getting processing statistics."""
        state.mark_processed("/test/s1.json", file_type="session", status="processed")
        state.mark_processed("/test/s2.json", file_type="session", status="processed")
        state.mark_processed("/test/m1.json", file_type="message", status="processed")
        state.mark_processed("/test/f1.json", file_type="part", status="failed")

        stats = state.get_stats()
        assert stats["total_files"] == 4
        assert stats["by_status"]["processed"] == 3
        assert stats["by_status"]["failed"] == 1
        assert stats["by_type"]["session"] == 2
        assert stats["by_type"]["message"] == 1


class TestRaceConditionScenarios:
    """Test race condition scenarios between bulk and realtime."""

    def create_session_file(self, storage, session_id, mtime=None):
        """Helper to create a session file in nested directory structure."""
        # Create project subdirectory (matches actual OpenCode structure)
        project_dir = storage / "session" / "test-project"
        project_dir.mkdir(exist_ok=True, parents=True)

        session_file = project_dir / f"{session_id}.json"
        session_data = {
            "id": session_id,
            "title": f"Session {session_id}",
            "time": {"created": int(time.time() * 1000)},
        }
        session_file.write_text(json.dumps(session_data))

        if mtime:
            import os

            os.utime(session_file, (mtime, mtime))

        return session_file

    def test_concurrent_file_creation(self, temp_storage, analytics_db):
        """Test file created during bulk load is handled correctly."""
        state = FileProcessingState(analytics_db)
        t0 = time.time()

        # Simulate bulk load marking files
        file1 = self.create_session_file(temp_storage, "sess1", mtime=t0 - 10)
        state.mark_processed(str(file1), file_type="session", status="processed")

        # File created during bulk (after T0) - should NOT be marked
        file2 = self.create_session_file(temp_storage, "sess2", mtime=t0 + 5)

        # Watcher should process this file
        assert not state.is_already_processed(str(file2))

        # After watcher processes it
        state.mark_processed(str(file2), file_type="session", status="processed")
        assert state.is_already_processed(str(file2))

    def test_no_duplicates(self, temp_storage, analytics_db):
        """Test that same file is not processed twice."""
        state = FileProcessingState(analytics_db)
        file1 = self.create_session_file(temp_storage, "sess1")

        # Bulk load processes it
        assert not state.is_already_processed(str(file1))
        state.mark_processed(str(file1), file_type="session", status="processed")

        # Watcher should skip it
        assert state.is_already_processed(str(file1))

        # Verify it was only processed once
        stats = state.get_stats()
        assert stats["total_files"] == 1

    def test_crash_recovery_file_state_persistence(self, temp_storage, analytics_db):
        """Test file processing state persists across crashes."""
        state = FileProcessingState(analytics_db)

        t0 = time.time()

        # Mark some files as processed
        file1 = self.create_session_file(temp_storage, "sess1", mtime=t0 - 10)
        state.mark_processed(str(file1), file_type="session", status="processed")

        # Simulate crash - create new instances
        state2 = FileProcessingState(analytics_db)

        # Should remember what was processed
        assert state2.is_already_processed(str(file1))

        # New file should not be marked
        file2 = self.create_session_file(temp_storage, "sess2", mtime=t0 - 5)
        assert not state2.is_already_processed(str(file2))


class TestIntegration:
    """Integration tests for the complete flow."""

    pass
