"""
Tests for SecurityEnrichmentWorker - TDD for Plan 42.

The enrichment worker:
1. NEVER reads files from disk - only queries the parts table
2. Enriches parts with risk_score, risk_level, risk_reason
3. Runs asynchronously in background
4. Can resume after restart (tracks enriched via security_enriched_at column)

These tests define the expected behavior BEFORE implementation.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# These imports will fail until we implement the module
# That's expected in TDD - tests first, implementation second


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def enrichment_db(analytics_db):
    """Create database with parts table including risk columns for enrichment."""
    conn = analytics_db.connect()

    # Drop and recreate parts table with new risk columns
    conn.execute("DROP TABLE IF EXISTS parts")
    conn.execute("""
        CREATE TABLE parts (
            id VARCHAR PRIMARY KEY,
            session_id VARCHAR,
            message_id VARCHAR,
            part_type VARCHAR,
            tool_name VARCHAR,
            tool_status VARCHAR,
            arguments VARCHAR,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            -- New security enrichment columns
            risk_score INTEGER,
            risk_level VARCHAR,
            risk_reason VARCHAR,
            mitre_techniques VARCHAR,
            security_enriched_at TIMESTAMP,
            -- Scope-aware security columns (Plan 44)
            scope_verdict VARCHAR,
            scope_resolved_path VARCHAR
        )
    """)

    # Create sessions table for scope analysis (JOIN in worker)
    conn.execute("DROP TABLE IF EXISTS sessions")
    conn.execute("""
        CREATE TABLE sessions (
            id VARCHAR PRIMARY KEY,
            directory VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    return analytics_db


@pytest.fixture
def sample_unenriched_parts(enrichment_db):
    """Insert sample parts that need enrichment."""
    conn = enrichment_db.connect()
    now = datetime.now()

    parts = [
        # Bash command - should be analyzed
        (
            "prt_001",
            "ses_001",
            "msg_001",
            "tool",
            "bash",
            "completed",
            json.dumps({"command": "rm -rf /tmp/test", "description": "cleanup"}),
        ),
        # Read file - should be analyzed
        (
            "prt_002",
            "ses_001",
            "msg_001",
            "tool",
            "read",
            "completed",
            json.dumps({"filePath": "/etc/passwd"}),
        ),
        # Write file - should be analyzed
        (
            "prt_003",
            "ses_001",
            "msg_002",
            "tool",
            "write",
            "completed",
            json.dumps({"filePath": "/home/user/.bashrc", "content": "export FOO=bar"}),
        ),
        # Edit file - should be analyzed
        (
            "prt_004",
            "ses_001",
            "msg_002",
            "tool",
            "edit",
            "completed",
            json.dumps({"filePath": "/etc/hosts", "oldString": "a", "newString": "b"}),
        ),
        # Webfetch - should be analyzed
        (
            "prt_005",
            "ses_002",
            "msg_003",
            "tool",
            "webfetch",
            "completed",
            json.dumps({"url": "https://pastebin.com/raw/abc123"}),
        ),
        # Glob - should NOT be analyzed (not a security-relevant tool)
        (
            "prt_006",
            "ses_002",
            "msg_003",
            "tool",
            "glob",
            "completed",
            json.dumps({"pattern": "**/*.py"}),
        ),
        # Grep - should NOT be analyzed
        (
            "prt_007",
            "ses_002",
            "msg_003",
            "tool",
            "grep",
            "completed",
            json.dumps({"pattern": "TODO", "include": "*.py"}),
        ),
    ]

    for part_id, ses_id, msg_id, ptype, tool, status, args in parts:
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, arguments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            [part_id, ses_id, msg_id, ptype, tool, status, args],
        )

    return parts


@pytest.fixture
def mock_analyzer():
    """Mock risk analyzer that returns predictable results."""
    analyzer = MagicMock()

    def analyze_command(cmd):
        from opencode_status_bar.security.analyzer import RiskResult

        if "rm -rf" in cmd:
            return RiskResult(score=70, level="high", reason="Recursive delete")
        return RiskResult(score=10, level="low", reason="Safe command")

    def analyze_file_path(path, write_mode=False):
        from opencode_status_bar.security.analyzer import RiskResult

        if "/etc/passwd" in path:
            return RiskResult(score=80, level="critical", reason="System file")
        if ".bashrc" in path or "/etc/" in path:
            score = 60 if write_mode else 50
            return RiskResult(
                score=score,
                level="high" if write_mode else "medium",
                reason="Config file",
            )
        return RiskResult(score=10, level="low", reason="Normal file")

    def analyze_url(url):
        from opencode_status_bar.security.analyzer import RiskResult

        if "pastebin" in url:
            return RiskResult(score=85, level="critical", reason="Paste site")
        return RiskResult(score=10, level="low", reason="Normal URL")

    analyzer.analyze_command.side_effect = analyze_command
    analyzer.analyze_file_path.side_effect = analyze_file_path
    analyzer.analyze_url.side_effect = analyze_url

    return analyzer


# =============================================================================
# Tests for enrichment logic (no file I/O)
# =============================================================================


class TestEnrichmentWorkerNoFileIO:
    """Verify the worker NEVER reads files - only queries DB."""

    def test_enrich_batch_queries_db_not_files(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """enrich_batch should query parts table, not read files from disk."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        # Mock Path.exists and Path.read_text to detect any file access
        with (
            patch.object(Path, "exists") as mock_exists,
            patch.object(Path, "read_text") as mock_read,
        ):
            mock_exists.return_value = True
            mock_read.return_value = "{}"

            # Run enrichment
            enriched_count = worker.enrich_batch(limit=10)

            # Should NOT have called any file operations
            mock_exists.assert_not_called()
            mock_read.assert_not_called()

        # But should have enriched some parts
        assert enriched_count > 0

    def test_enrich_uses_arguments_column_for_data(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """Worker should extract command/filePath/url from arguments JSON column."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)
        worker.enrich_batch(limit=10)

        # Verify analyzer was called with data from arguments column
        # Check bash command was analyzed
        mock_analyzer.analyze_command.assert_any_call("rm -rf /tmp/test")

        # Check file paths were analyzed (read uses write_mode=False, write/edit use write_mode=True)
        mock_analyzer.analyze_file_path.assert_any_call("/etc/passwd", write_mode=False)
        mock_analyzer.analyze_file_path.assert_any_call(
            "/home/user/.bashrc", write_mode=True
        )
        mock_analyzer.analyze_file_path.assert_any_call("/etc/hosts", write_mode=True)

        # Check URL was analyzed
        mock_analyzer.analyze_url.assert_any_call("https://pastebin.com/raw/abc123")


# =============================================================================
# Tests for enrichment results
# =============================================================================


class TestEnrichmentResults:
    """Verify enrichment writes correct data to parts table."""

    def test_enrichment_updates_risk_columns(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """Enriched parts should have risk_score, risk_level, risk_reason set."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)
        worker.enrich_batch(limit=10)

        conn = enrichment_db.connect()

        # Check bash command was enriched with high risk
        result = conn.execute("""
            SELECT risk_score, risk_level, risk_reason 
            FROM parts WHERE id = 'prt_001'
        """).fetchone()

        assert result[0] == 70  # risk_score
        assert result[1] == "high"  # risk_level
        assert "delete" in result[2].lower()  # risk_reason

    def test_enrichment_sets_timestamp(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """Enriched parts should have security_enriched_at timestamp set."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        before = datetime.now()
        worker.enrich_batch(limit=10)
        after = datetime.now()

        conn = enrichment_db.connect()
        result = conn.execute("""
            SELECT security_enriched_at FROM parts WHERE id = 'prt_001'
        """).fetchone()

        enriched_at = result[0]
        assert isinstance(enriched_at, datetime)
        assert before <= enriched_at <= after

    def test_only_security_tools_are_enriched(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """Only bash/read/write/edit/webfetch should be enriched."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)
        worker.enrich_batch(limit=10)

        conn = enrichment_db.connect()

        # Glob and grep should NOT be enriched
        result = conn.execute("""
            SELECT id, security_enriched_at FROM parts 
            WHERE tool_name IN ('glob', 'grep')
        """).fetchall()

        for part_id, enriched_at in result:
            assert enriched_at is None, f"{part_id} should not be enriched"

        # But bash/read/write/edit/webfetch should be enriched
        result = conn.execute("""
            SELECT id, security_enriched_at FROM parts 
            WHERE tool_name IN ('bash', 'read', 'write', 'edit', 'webfetch')
        """).fetchall()

        for part_id, enriched_at in result:
            assert isinstance(enriched_at, datetime), f"{part_id} should be enriched"


# =============================================================================
# Tests for incremental enrichment (resume capability)
# =============================================================================


class TestIncrementalEnrichment:
    """Verify worker can resume and only processes unenriched parts."""

    def test_skips_already_enriched_parts(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """Parts with security_enriched_at set should be skipped."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        conn = enrichment_db.connect()

        # Pre-enrich one part
        conn.execute("""
            UPDATE parts SET 
                risk_score = 99, 
                risk_level = 'critical',
                security_enriched_at = CURRENT_TIMESTAMP
            WHERE id = 'prt_001'
        """)

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)
        worker.enrich_batch(limit=10)

        # The pre-enriched part should NOT have been changed
        result = conn.execute("""
            SELECT risk_score FROM parts WHERE id = 'prt_001'
        """).fetchone()

        assert result[0] == 99  # Original value preserved

    def test_returns_zero_when_all_enriched(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """enrich_batch returns 0 when nothing left to enrich."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        conn = enrichment_db.connect()

        # Mark all security-relevant parts as enriched
        conn.execute("""
            UPDATE parts SET security_enriched_at = CURRENT_TIMESTAMP
            WHERE tool_name IN ('bash', 'read', 'write', 'edit', 'webfetch')
        """)

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)
        enriched = worker.enrich_batch(limit=10)

        assert enriched == 0

    def test_detects_new_parts_after_indexing(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """Worker should detect and enrich new parts added by indexer."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        # First batch - enrich existing parts
        first_enriched = worker.enrich_batch(limit=10)

        # Simulate indexer adding new part
        conn = enrichment_db.connect()
        conn.execute("""
            INSERT INTO parts (id, session_id, message_id, tool_name, arguments)
            VALUES ('prt_new_001', 'ses_003', 'msg_004', 'bash', 
                    '{"command": "echo hello"}')
        """)

        # Second batch - should find and enrich the new part
        second_enriched = worker.enrich_batch(limit=10)

        assert second_enriched == 1

        # Verify new part was enriched
        result = conn.execute("""
            SELECT security_enriched_at FROM parts WHERE id = 'prt_new_001'
        """).fetchone()

        assert isinstance(result[0], datetime)


# =============================================================================
# Tests for progress tracking
# =============================================================================


class TestEnrichmentProgress:
    """Verify worker provides progress information."""

    def test_get_enrichment_progress(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """get_progress should return enriched/pending/total counts."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        # Before enrichment
        progress = worker.get_progress()
        assert progress["enriched"] == 0
        assert progress["pending"] == 5  # 5 security-relevant tools
        assert progress["total"] == 7  # All parts

        # After enrichment
        worker.enrich_batch(limit=10)

        progress = worker.get_progress()
        assert progress["enriched"] == 5
        assert progress["pending"] == 0
        assert progress["total"] == 7


# =============================================================================
# Tests for batch processing
# =============================================================================


class TestBatchProcessing:
    """Verify batch processing respects limits."""

    def test_respects_batch_limit(
        self, enrichment_db, sample_unenriched_parts, mock_analyzer
    ):
        """enrich_batch should only process up to limit parts."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        # Only enrich 2 at a time
        enriched = worker.enrich_batch(limit=2)

        assert enriched == 2

        # Progress should reflect partial enrichment
        progress = worker.get_progress()
        assert progress["enriched"] == 2
        assert progress["pending"] == 3  # 5 - 2 = 3 remaining


# =============================================================================
# Tests for error handling
# =============================================================================


class TestErrorHandling:
    """Verify worker handles errors gracefully."""

    def test_handles_invalid_json_arguments(self, enrichment_db, mock_analyzer):
        """Worker should skip parts with invalid JSON in arguments."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        conn = enrichment_db.connect()

        # Insert part with invalid JSON
        conn.execute("""
            INSERT INTO parts (id, tool_name, arguments)
            VALUES ('prt_invalid', 'bash', 'not valid json {{{')
        """)

        # Insert valid part
        conn.execute("""
            INSERT INTO parts (id, tool_name, arguments)
            VALUES ('prt_valid', 'bash', '{"command": "ls"}')
        """)

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        # Should not raise, should skip invalid and process valid
        enriched = worker.enrich_batch(limit=10)

        # At least the valid one should be enriched
        assert enriched >= 1

    def test_handles_missing_command_field(self, enrichment_db, mock_analyzer):
        """Worker should handle bash parts without command field."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        conn = enrichment_db.connect()

        # Insert bash part without command field
        conn.execute("""
            INSERT INTO parts (id, tool_name, arguments)
            VALUES ('prt_no_cmd', 'bash', '{"description": "no command"}')
        """)

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        # Should not raise
        enriched = worker.enrich_batch(limit=10)

        # Part should be marked as enriched (with low/no risk)
        result = conn.execute("""
            SELECT security_enriched_at FROM parts WHERE id = 'prt_no_cmd'
        """).fetchone()

        assert isinstance(result[0], datetime)


# =============================================================================
# Tests for worker lifecycle
# =============================================================================


class TestWorkerLifecycle:
    """Verify worker start/stop lifecycle."""

    def test_worker_can_start_and_stop(self, enrichment_db, mock_analyzer):
        """Worker should start background thread and stop cleanly."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        assert not worker.is_running()

        worker.start()
        assert worker.is_running()

        worker.stop()
        assert not worker.is_running()

    def test_worker_is_idempotent(self, enrichment_db, mock_analyzer):
        """Multiple start/stop calls should be safe."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        # Multiple starts should be safe
        worker.start()
        worker.start()
        worker.start()

        assert worker.is_running()

        # Multiple stops should be safe
        worker.stop()
        worker.stop()
        worker.stop()

        assert not worker.is_running()

    def test_default_poll_interval(self, enrichment_db, mock_analyzer):
        """Default poll interval should be 10 seconds (not aggressive)."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(db=enrichment_db, analyzer=mock_analyzer)

        assert worker._poll_interval == 10.0

    def test_custom_poll_interval(self, enrichment_db, mock_analyzer):
        """Should allow custom poll_interval."""
        from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

        worker = SecurityEnrichmentWorker(
            db=enrichment_db, analyzer=mock_analyzer, poll_interval=5.0
        )

        assert worker._poll_interval == 5.0
