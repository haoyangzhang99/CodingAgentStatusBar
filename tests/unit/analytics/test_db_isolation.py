"""
Tests to verify database isolation in the test suite.

These tests ensure that:
1. Test databases never connect to the production database
2. Each test gets a fresh, isolated database
3. No state leaks between tests
"""

import os
from pathlib import Path

import pytest


class TestDatabaseIsolation:
    """Verify that all database fixtures are properly isolated."""

    def test_analytics_db_not_in_home_config(self, analytics_db):
        """Verify analytics_db does NOT use ~/.config/opencode-status-bar."""
        db_path = analytics_db._db_path

        # The path should NOT be in the user's home config directory
        home_config = Path.home() / ".config" / "opencode-status-bar"
        assert not str(db_path).startswith(str(home_config)), (
            f"Test database {db_path} is in production path {home_config}!"
        )

    def test_analytics_db_uses_tmp_path(self, analytics_db, tmp_path):
        """Verify analytics_db uses the pytest tmp_path."""
        db_path = analytics_db._db_path

        # The path should be in tmp_path
        assert str(db_path).startswith(str(tmp_path)), (
            f"Test database {db_path} not in tmp_path {tmp_path}"
        )

    def test_each_test_gets_fresh_db(self, analytics_db):
        """Verify each test starts with an empty database."""
        conn = analytics_db.connect()

        # Check that tables exist but are empty
        sessions_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        messages_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        parts_count = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]

        assert sessions_count == 0, "Sessions table should be empty in fresh test"
        assert messages_count == 0, "Messages table should be empty in fresh test"
        assert parts_count == 0, "Parts table should be empty in fresh test"

    def test_db_isolation_between_tests_part1(self, analytics_db):
        """First test: insert data and verify it exists."""
        conn = analytics_db.connect()

        conn.execute("""
            INSERT INTO sessions (id, project_name, created_at)
            VALUES ('isolation_test_1', 'test_project', CURRENT_TIMESTAMP)
        """)

        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        assert count == 1

    def test_db_isolation_between_tests_part2(self, analytics_db):
        """Second test: verify previous test's data is NOT present."""
        conn = analytics_db.connect()

        # The data from part1 should NOT be here - this is a fresh database
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        assert count == 0, "Data from previous test leaked into this test!"

        # Specifically check for the test ID
        result = conn.execute("""
            SELECT COUNT(*) FROM sessions WHERE id = 'isolation_test_1'
        """).fetchone()[0]
        assert result == 0, "Specific row from previous test found!"


class TestEnrichmentDbIsolation:
    """Verify enrichment_db fixture isolation."""

    def test_enrichment_db_has_correct_schema(self, enrichment_db):
        """Verify enrichment_db has the security columns."""
        conn = enrichment_db.connect()

        # Check that parts table has security columns
        columns = conn.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'parts'
        """).fetchall()

        column_names = {col[0] for col in columns}

        required_columns = {
            "risk_score",
            "risk_level",
            "risk_reason",
            "mitre_techniques",
            "security_enriched_at",
        }

        for col in required_columns:
            assert col in column_names, f"Missing column: {col}"

    def test_enrichment_db_is_empty(self, enrichment_db):
        """Verify enrichment_db starts empty."""
        conn = enrichment_db.connect()

        count = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
        assert count == 0


class TestSampleDataGenerator:
    """Test the sample data generator utilities."""

    def test_create_session(self, sample_data_generator):
        """Verify session creation."""
        session = sample_data_generator.create_session(
            session_id="test-001",
            project_name="my-project",
        )

        assert session["id"] == "test-001"
        assert session["project_name"] == "my-project"
        assert "created_at" in session

    def test_create_bash_part(self, sample_data_generator):
        """Verify bash part creation."""
        part = sample_data_generator.create_bash_part(
            session_id="ses-001",
            message_id="msg-001",
            command="rm -rf /tmp/test",
            risk_score=85,
            risk_level="critical",
        )

        assert part["tool_name"] == "bash"
        assert '"command": "rm -rf /tmp/test"' in part["arguments"]
        assert part["risk_score"] == 85
        assert part["risk_level"] == "critical"

    def test_create_parts_with_different_risk_levels(self, sample_data_generator):
        """Verify creating parts with various risk levels."""
        parts = []

        # Critical
        parts.append(
            sample_data_generator.create_bash_part(
                "ses", "msg", "rm -rf /", risk_level="critical"
            )
        )
        # High
        parts.append(
            sample_data_generator.create_read_part(
                "ses", "msg", "/etc/passwd", risk_level="high"
            )
        )
        # Medium
        parts.append(
            sample_data_generator.create_write_part(
                "ses", "msg", "/tmp/test", risk_level="medium"
            )
        )
        # Low
        parts.append(
            sample_data_generator.create_webfetch_part(
                "ses", "msg", "https://example.com", risk_level="low"
            )
        )

        risk_levels = [p["risk_level"] for p in parts]
        assert risk_levels == ["critical", "high", "medium", "low"]


class TestPopulatedDatabase:
    """Test pre-populated database fixtures."""

    def test_populated_db_has_sessions(self, populated_analytics_db):
        """Verify populated DB contains sessions."""
        db, session_ids, _ = populated_analytics_db

        assert len(session_ids) == 2
        assert all(sid.startswith("ses_") for sid in session_ids)

    def test_populated_db_has_parts(self, populated_analytics_db):
        """Verify populated DB contains parts with different risk levels."""
        db, _, part_ids = populated_analytics_db
        conn = db.connect()

        # Check we have parts
        assert len(part_ids) > 0

        # Verify different risk levels exist
        levels = conn.execute("""
            SELECT DISTINCT risk_level FROM parts 
            WHERE risk_level IS NOT NULL
        """).fetchall()

        level_set = {l[0] for l in levels}
        assert "critical" in level_set
        assert "high" in level_set or "medium" in level_set or "low" in level_set

    def test_populated_db_has_unenriched_parts(self, populated_analytics_db):
        """Verify populated DB has both enriched and unenriched parts."""
        db, _, _ = populated_analytics_db
        conn = db.connect()

        # Count unenriched parts
        unenriched = conn.execute("""
            SELECT COUNT(*) FROM parts 
            WHERE security_enriched_at IS NULL
              AND tool_name IN ('bash', 'read', 'write', 'edit', 'webfetch')
        """).fetchone()[0]

        assert unenriched > 0, "Should have some unenriched security-relevant parts"

        # Count enriched parts
        enriched = conn.execute("""
            SELECT COUNT(*) FROM parts 
            WHERE security_enriched_at IS NOT NULL
        """).fetchone()[0]

        assert enriched > 0, "Should have some enriched parts"
