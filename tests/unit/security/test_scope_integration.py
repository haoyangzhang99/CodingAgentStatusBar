"""Integration tests for scope-aware security with enrichment worker."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock

from opencode_status_bar.security.scope import ScopeDetector, ScopeVerdict


class TestScopeDetectorWithRealPaths:
    """Integration tests with real filesystem paths."""

    @pytest.fixture
    def project_with_files(self, tmp_path):
        """Create a realistic project structure."""
        project = tmp_path / "myproject"
        project.mkdir()

        # Create typical project structure
        (project / "src").mkdir()
        (project / "src" / "main.py").write_text("# main")
        (project / "src" / "utils").mkdir()
        (project / "src" / "utils" / "helpers.py").write_text("# helpers")

        (project / "tests").mkdir()
        (project / "tests" / "test_main.py").write_text("# tests")

        (project / ".vscode").mkdir()
        (project / ".vscode" / "settings.json").write_text("{}")

        (project / ".git").mkdir()
        (project / ".gitignore").write_text("*.pyc")
        (project / "README.md").write_text("# Project")

        return project

    def test_full_project_scan(self, project_with_files):
        """All project files should be in scope."""
        detector = ScopeDetector(project_with_files)

        # Test all project files
        in_scope_paths = [
            "src/main.py",
            "src/utils/helpers.py",
            "tests/test_main.py",
            ".vscode/settings.json",
            ".gitignore",
            "README.md",
        ]

        for path in in_scope_paths:
            result = detector.detect(path)
            assert result.verdict == ScopeVerdict.IN_SCOPE, f"{path} should be in scope"
            assert result.score_modifier == 0

    def test_absolute_paths_matching_project(self, project_with_files):
        """Absolute paths within project should be recognized."""
        detector = ScopeDetector(project_with_files)

        abs_path = project_with_files / "src" / "main.py"
        result = detector.detect(str(abs_path))
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestScopeWithMultipleProjects:
    """Tests for scope detection with multiple projects."""

    @pytest.fixture
    def two_projects(self, tmp_path):
        """Create two separate projects."""
        proj_a = tmp_path / "project_a"
        proj_a.mkdir()
        (proj_a / "src").mkdir()
        (proj_a / "src" / "a.py").write_text("# a")

        proj_b = tmp_path / "project_b"
        proj_b.mkdir()
        (proj_b / "src").mkdir()
        (proj_b / "src" / "b.py").write_text("# b")

        return proj_a, proj_b

    def test_cross_project_access_detected(self, two_projects):
        """Accessing files from another project should be out of scope."""
        proj_a, proj_b = two_projects

        detector_a = ScopeDetector(proj_a)

        # Access file from project B while in project A's scope
        result = detector_a.detect(str(proj_b / "src" / "b.py"))
        assert result.verdict != ScopeVerdict.IN_SCOPE


class TestEnrichmentIntegration:
    """Test scope detection integration with security enrichment."""

    @pytest.fixture
    def enrichment_db_with_parts(self, enrichment_db, tmp_path):
        """Create test parts with various scope scenarios."""
        conn = enrichment_db.connect()

        project_root = str(tmp_path / "project")

        # Insert session with directory
        conn.execute(
            """
            INSERT INTO sessions (id, directory, project_name, created_at)
            VALUES ('ses_scope_test', ?, 'test-project', CURRENT_TIMESTAMP)
        """,
            [project_root],
        )

        # Insert message
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, created_at)
            VALUES ('msg_001', 'ses_scope_test', 'assistant', CURRENT_TIMESTAMP)
        """
        )

        # Insert parts with different scope scenarios
        parts = [
            ("prt_in_scope", "read", json.dumps({"filePath": "./src/main.py"})),
            ("prt_sensitive", "read", json.dumps({"filePath": "~/.ssh/id_rsa"})),
            ("prt_allowed", "write", json.dumps({"filePath": "/tmp/cache.txt"})),
            (
                "prt_suspicious",
                "read",
                json.dumps({"filePath": "~/Downloads/script.sh"}),
            ),
        ]

        for part_id, tool, args in parts:
            conn.execute(
                """
                INSERT INTO parts (id, session_id, message_id, part_type, tool_name, arguments, created_at)
                VALUES (?, 'ses_scope_test', 'msg_001', 'tool', ?, ?, CURRENT_TIMESTAMP)
            """,
                [part_id, tool, args],
            )

        return enrichment_db, project_root

    def test_scope_analysis_per_path(self, enrichment_db_with_parts, tmp_path):
        """Test scope analysis on extracted paths."""
        db, project_root = enrichment_db_with_parts

        # Create detector
        project = Path(project_root)
        project.mkdir(parents=True, exist_ok=True)
        detector = ScopeDetector(project)

        # Verify scope analysis for each path type using detector's real home
        # This ensures tests work across different systems
        paths_and_expected = [
            ("./src/main.py", ScopeVerdict.IN_SCOPE),
            (
                str(detector.home / ".ssh" / "id_rsa"),
                ScopeVerdict.OUT_OF_SCOPE_SENSITIVE,
            ),
            ("/tmp/cache.txt", ScopeVerdict.OUT_OF_SCOPE_ALLOWED),
            (
                str(detector.home / "Downloads" / "script.sh"),
                ScopeVerdict.OUT_OF_SCOPE_SUSPICIOUS,
            ),
        ]

        for path, expected_verdict in paths_and_expected:
            result = detector.detect(path)
            assert result.verdict == expected_verdict, (
                f"Path {path} expected {expected_verdict}, got {result.verdict}"
            )


class TestScopeWithSessionContext:
    """Tests for scope detection using session context."""

    @pytest.fixture
    def session_with_directory(self, analytics_db, tmp_path):
        """Create session with working directory."""
        project = tmp_path / "session_project"
        project.mkdir()
        (project / "src").mkdir()

        conn = analytics_db.connect()
        conn.execute(
            """
            INSERT INTO sessions (id, directory, project_name, created_at)
            VALUES ('ses_001', ?, 'test-project', CURRENT_TIMESTAMP)
        """,
            [str(project)],
        )

        return analytics_db, project

    def test_scope_from_session_directory(self, session_with_directory):
        """Scope should use session's working directory."""
        db, project = session_with_directory

        # Query session to get directory
        conn = db.connect()
        row = conn.execute(
            "SELECT directory FROM sessions WHERE id = 'ses_001'"
        ).fetchone()
        directory = row[0]

        # Create detector with session's directory
        detector = ScopeDetector(Path(directory))

        # Paths relative to session directory should be in scope
        result = detector.detect("./src/file.py")
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestPathResolution:
    """Tests for path resolution edge cases."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    def test_double_dots_escape_attempt(self, detector, tmp_path):
        """Attempts to escape project with .. should be detected."""
        # Trying to access parent directory
        result = detector.detect("../sensitive.txt")
        assert result.verdict != ScopeVerdict.IN_SCOPE

    def test_multiple_double_dots(self, detector, tmp_path):
        """Multiple .. attempts to escape should be detected."""
        result = detector.detect("../../../../../../etc/passwd")
        assert result.verdict != ScopeVerdict.IN_SCOPE
        # Should still be classified as sensitive
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE

    def test_hidden_escape_with_valid_prefix(self, detector, tmp_path):
        """Escape attempt hidden in valid-looking path."""
        result = detector.detect("./src/../../../secret.txt")
        assert result.verdict != ScopeVerdict.IN_SCOPE


class TestRiskScoreAccumulation:
    """Tests for risk score calculation from scope analysis."""

    @pytest.fixture
    def detector(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        (fake_home / ".ssh").mkdir()
        (fake_home / ".aws").mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    def test_score_ordering(self, detector):
        """Scores should follow severity ordering."""
        paths = [
            (str(detector.project_root / "file.py"), "in_scope"),
            ("/tmp/cache.txt", "allowed"),
            ("/usr/local/bin/tool", "suspicious"),
            (str(detector.home / ".ssh" / "id_rsa"), "sensitive"),
        ]

        scores = []
        for path, _ in paths:
            result = detector.detect(path)
            scores.append(result.score_modifier)

        # In-scope and allowed should be 0
        assert scores[0] == 0
        assert scores[1] == 0

        # Suspicious < Sensitive
        assert scores[2] < scores[3]

    def test_write_always_increases_score(self, detector):
        """Write operations should always have higher scores than reads."""
        test_paths = [
            str(detector.home / ".bashrc"),
            "/usr/local/bin/tool",
        ]

        for path in test_paths:
            read_result = detector.detect(path, "read")
            write_result = detector.detect(path, "write")
            assert write_result.score_modifier > read_result.score_modifier, (
                f"Write to {path} should have higher score than read"
            )
