"""
Tests for /api/security endpoint.

Tests cover:
- Endpoint returns proper structure (stats, commands, files, critical_items)
- Endpoint respects row_limit and top_limit query parameters
"""

from unittest.mock import MagicMock, patch

import pytest

from opencode_status_bar.api.routes.security import security_bp


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app():
    """Create Flask test app with security blueprint."""
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(security_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create test client for Flask app."""
    return app.test_client()


@pytest.fixture
def mock_auditor():
    """Create mock auditor with sample data."""
    auditor = MagicMock()

    # Stats
    auditor.get_stats.return_value = {
        "total_scanned": 100,
        "total_commands": 50,
        "critical": 5,
        "high": 10,
        "medium": 20,
        "low": 15,
    }

    # Commands - create mock objects with required attributes
    def make_command(cmd, risk_level, risk_score, risk_reason):
        mock = MagicMock()
        mock.command = cmd
        mock.risk_level = risk_level
        mock.risk_score = risk_score
        mock.risk_reason = risk_reason
        return mock

    def make_file_op(path, risk_level, risk_score, risk_reason):
        mock = MagicMock()
        mock.file_path = path
        mock.risk_level = risk_level
        mock.risk_score = risk_score
        mock.risk_reason = risk_reason
        mock.scope_verdict = "in_scope"
        mock.scope_resolved_path = path
        return mock

    def make_webfetch(url, risk_level, risk_score, risk_reason):
        mock = MagicMock()
        mock.url = url
        mock.risk_level = risk_level
        mock.risk_score = risk_score
        mock.risk_reason = risk_reason
        return mock

    # All commands (for table)
    auditor.get_all_commands.return_value = [
        make_command("ls -la", "low", 10, "List files"),
        make_command("rm -rf /tmp/*", "high", 80, "Recursive delete"),
        make_command("cat /etc/passwd", "critical", 95, "Read sensitive file"),
    ]

    # Critical/high commands
    auditor.get_critical_commands.return_value = [
        make_command("cat /etc/passwd", "critical", 95, "Read sensitive file"),
    ]
    auditor.get_commands_by_level.return_value = [
        make_command("rm -rf /tmp/*", "high", 80, "Recursive delete"),
    ]

    # File reads/writes
    auditor.get_all_reads.return_value = [
        make_file_op("/etc/passwd", "critical", 90, "Sensitive file"),
    ]
    auditor.get_all_writes.return_value = [
        make_file_op("/tmp/output.txt", "low", 10, "Temp file"),
    ]
    auditor.get_sensitive_reads.return_value = [
        make_file_op("/etc/passwd", "critical", 90, "Sensitive file"),
    ]
    auditor.get_sensitive_writes.return_value = []

    # Webfetches
    auditor.get_risky_webfetches.return_value = [
        make_webfetch("https://suspicious.com/malware", "high", 75, "Suspicious URL"),
    ]

    return auditor


# =============================================================================
# Tests for /api/security endpoint
# =============================================================================


class TestSecurityEndpoint:
    """Tests for GET /api/security endpoint."""

    def test_returns_stats_and_data(self, client, mock_auditor):
        """Endpoint returns success with stats, commands, files, critical_items."""
        with patch("opencode_status_bar.security.auditor.get_auditor") as mock_get_auditor:
            mock_get_auditor.return_value = mock_auditor

            response = client.get("/api/security")

            assert response.status_code == 200
            data = response.get_json()

            # Check success flag
            assert data["success"] is True

            # Check data structure
            assert "data" in data
            result = data["data"]

            # Verify all required keys present
            assert "stats" in result
            assert "commands" in result
            assert "files" in result
            assert "critical_items" in result

            # Verify stats structure
            stats = result["stats"]
            assert "total_scanned" in stats
            assert "total_commands" in stats
            assert "critical" in stats

            # Verify commands structure
            commands = result["commands"]
            assert isinstance(commands, list)
            if commands:
                assert "command" in commands[0]
                assert "risk" in commands[0]
                assert "score" in commands[0]

            # Verify files structure
            files = result["files"]
            assert isinstance(files, list)
            if files:
                assert "operation" in files[0]
                assert "path" in files[0]
                assert "risk" in files[0]

            # Verify critical_items structure
            critical_items = result["critical_items"]
            assert isinstance(critical_items, list)
            if critical_items:
                assert "type" in critical_items[0]
                assert "details" in critical_items[0]
                assert "risk" in critical_items[0]

    def test_respects_limits(self, client, mock_auditor):
        """Endpoint respects row_limit and top_limit query parameters."""
        with patch("opencode_status_bar.security.auditor.get_auditor") as mock_get_auditor:
            mock_get_auditor.return_value = mock_auditor

            # Request with specific limits
            response = client.get("/api/security?row_limit=5&top_limit=3")

            assert response.status_code == 200

            # Verify auditor was called with correct limits
            mock_auditor.get_all_commands.assert_called_with(limit=5)
            mock_auditor.get_all_reads.assert_called_with(limit=3)
            mock_auditor.get_all_writes.assert_called_with(limit=3)
            mock_auditor.get_critical_commands.assert_called_with(limit=5)
            mock_auditor.get_commands_by_level.assert_called_with("high", limit=5)

    def test_default_limits(self, client, mock_auditor):
        """Endpoint uses default limits when not specified."""
        with patch("opencode_status_bar.security.auditor.get_auditor") as mock_get_auditor:
            mock_get_auditor.return_value = mock_auditor

            response = client.get("/api/security")

            assert response.status_code == 200

            # Default row_limit=100, top_limit=10
            mock_auditor.get_all_commands.assert_called_with(limit=100)
            mock_auditor.get_all_reads.assert_called_with(limit=10)

    def test_handles_auditor_error(self, client):
        """Endpoint returns error response when auditor fails."""
        with patch("opencode_status_bar.security.auditor.get_auditor") as mock_get_auditor:
            mock_get_auditor.side_effect = Exception("Database error")

            response = client.get("/api/security")

            assert response.status_code == 500
            data = response.get_json()
            assert data["success"] is False
            assert "error" in data

    def test_files_sorted_by_score(self, client, mock_auditor):
        """Files are sorted by risk score descending."""
        with patch("opencode_status_bar.security.auditor.get_auditor") as mock_get_auditor:
            mock_get_auditor.return_value = mock_auditor

            response = client.get("/api/security")

            data = response.get_json()
            files = data["data"]["files"]

            # Verify files are sorted by score descending
            if len(files) >= 2:
                scores = [f.get("score", 0) for f in files]
                assert scores == sorted(scores, reverse=True)
