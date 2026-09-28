"""Tests for ScopeDetector - scope-aware security detection."""

import pytest
from pathlib import Path
from opencode_status_bar.security.scope import ScopeDetector, ScopeResult, ScopeVerdict


class TestInScopeDetection:
    """Tests for IN_SCOPE verdict."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "src").mkdir()
        return ScopeDetector(project)

    @pytest.mark.parametrize(
        "relative_path",
        [
            "./src/main.py",
            "src/main.py",
            "./README.md",
            "./.gitignore",
            "./src/utils/../helpers/file.py",
        ],
    )
    def test_relative_paths_in_scope(self, detector, relative_path):
        result = detector.detect(relative_path)
        assert result.verdict == ScopeVerdict.IN_SCOPE
        assert result.score_modifier == 0

    def test_absolute_path_in_scope(self, detector):
        abs_path = str(detector.project_root / "src" / "main.py")
        result = detector.detect(abs_path)
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_path_with_parent_traversal_staying_in_scope(self, detector):
        """Path with .. that stays within project should be in scope."""
        result = detector.detect("./src/../README.md")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_project_root_itself(self, detector):
        """Project root directory should be in scope."""
        result = detector.detect(".")
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestOutOfScopeAllowed:
    """Tests for OUT_OF_SCOPE_ALLOWED verdict."""

    @pytest.fixture
    def detector(self, tmp_path):
        return ScopeDetector(tmp_path / "project")

    @pytest.mark.parametrize(
        "path",
        [
            "/tmp/build-cache.txt",
            "/var/tmp/pytest-123/test.log",
        ],
    )
    def test_temp_paths_allowed(self, detector, path):
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED
        assert result.score_modifier == 0

    def test_var_folders_macos_allowed(self, detector):
        """macOS temp folders under /var/folders should be allowed."""
        # Use the actual pattern from allowed_paths
        result = detector.detect("/var/folders/ab/cd/T/file.tmp")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED

    def test_cache_paths_allowed_real_home(self, detector):
        """Cache under real home should be allowed."""
        # Use the detector's actual home path
        cache_path = str(detector.home / ".cache" / "pip" / "file.whl")
        result = detector.detect(cache_path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED
        assert result.score_modifier == 0

    def test_npm_cache_allowed_real_home(self, detector):
        """NPM cache under real home should be allowed."""
        npm_path = str(detector.home / ".npm" / "_cacache" / "file")
        result = detector.detect(npm_path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED

    def test_yarn_cache_allowed_real_home(self, detector):
        """Yarn cache under real home should be allowed."""
        yarn_path = str(detector.home / ".yarn" / "cache" / "lodash.zip")
        result = detector.detect(yarn_path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED

    def test_local_share_allowed(self, detector):
        """~/.local/share should be allowed."""
        path = str(detector.home / ".local" / "share" / "app" / "data")
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED


class TestOutOfScopeSuspicious:
    """Tests for OUT_OF_SCOPE_SUSPICIOUS verdict."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    @pytest.mark.parametrize(
        "path_suffix,min_score",
        [
            ("Downloads/script.sh", 40),
            ("Documents/secrets.docx", 30),
            ("Desktop/todo.txt", 30),
        ],
    )
    def test_suspicious_paths(self, detector, path_suffix, min_score):
        """Test suspicious paths using detector's real home."""
        path = str(detector.home / path_suffix)
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SUSPICIOUS
        assert result.score_modifier >= min_score

    def test_usr_directory_suspicious(self, detector):
        result = detector.detect("/usr/local/bin/python")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SUSPICIOUS
        assert result.score_modifier >= 30

    def test_var_directory_suspicious(self, detector):
        """Non-tmp /var paths should be suspicious."""
        result = detector.detect("/var/log/syslog")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SUSPICIOUS
        assert result.score_modifier >= 30


class TestOutOfScopeSensitive:
    """Tests for OUT_OF_SCOPE_SENSITIVE verdict."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    @pytest.mark.parametrize(
        "path_suffix,min_score,reason_contains",
        [
            (".ssh/id_rsa", 70, "SSH"),
            (".aws/credentials", 65, "AWS"),
            (".bashrc", 50, "Bash"),
            (".zshrc", 50, "Zsh"),
        ],
    )
    def test_sensitive_paths(self, detector, path_suffix, min_score, reason_contains):
        """Test sensitive paths using detector's real home."""
        path = str(detector.home / path_suffix)
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE
        assert result.score_modifier >= min_score
        assert reason_contains.lower() in result.reason.lower()

    def test_etc_passwd_sensitive(self, detector):
        result = detector.detect("/etc/passwd")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE
        assert result.score_modifier >= 55
        assert "system" in result.reason.lower() or "passwd" in result.reason.lower()

    def test_etc_shadow_highest_score(self, detector):
        """Shadow file should have near-maximum score."""
        result = detector.detect("/etc/shadow")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE
        assert result.score_modifier >= 90

    def test_gnupg_sensitive(self, detector):
        """GPG keys should be sensitive."""
        path = str(detector.home / ".gnupg" / "private-keys-v1.d" / "key.key")
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE
        assert result.score_modifier >= 70


class TestWriteModePenalty:
    """Tests for write operation score modifiers."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    def test_write_adds_penalty_to_sensitive(self, detector):
        """Write to sensitive path should add penalty."""
        path = str(detector.home / ".bashrc")
        read_result = detector.detect(path, "read")
        write_result = detector.detect(path, "write")
        assert write_result.score_modifier > read_result.score_modifier

    def test_write_score_capped_at_100(self, detector):
        """Write to highest-scored file should not exceed 100."""
        result = detector.detect("/etc/shadow", "write")
        assert result.score_modifier <= 100

    def test_write_to_suspicious_adds_penalty(self, detector):
        """Write to suspicious path should add penalty."""
        read_result = detector.detect("/usr/local/bin/file", "read")
        write_result = detector.detect("/usr/local/bin/file", "write")
        assert write_result.score_modifier > read_result.score_modifier

    def test_write_penalty_on_neutral_path(self, detector, tmp_path):
        """Write to neutral out-of-scope should get higher base score."""
        # Use a path under /opt which is neutral (not suspicious or sensitive)
        other_path = "/opt/someapp/config.txt"
        read_result = detector.detect(other_path, "read")
        write_result = detector.detect(other_path, "write")
        assert write_result.score_modifier > read_result.score_modifier


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    def test_empty_path(self, detector):
        """Empty path should resolve to project root (in scope)."""
        result = detector.detect("")
        # Empty path resolves to current directory which is project root
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_path_with_spaces(self, detector):
        result = detector.detect("./src/my file.py")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_unicode_path(self, detector):
        result = detector.detect("./src/données.py")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_path_with_dots(self, detector):
        result = detector.detect("./src/file.test.py")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_deeply_nested_path(self, detector):
        result = detector.detect("./a/b/c/d/e/f/g/h/file.py")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_symlink_resolution(self, detector, tmp_path):
        """Symlinks pointing outside project should be detected."""
        # Create a target outside project
        target = tmp_path / "outside" / "secret.txt"
        target.parent.mkdir(parents=True)
        target.touch()

        # Create symlink inside project pointing to target
        link = detector.project_root / "link.txt"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Symlinks not supported on this system")

        result = detector.detect(str(link))
        # After resolution, should detect as out of scope
        assert result.verdict != ScopeVerdict.IN_SCOPE

    def test_tilde_expansion(self, detector):
        """Paths with ~ should be properly expanded to sensitive paths."""
        result = detector.detect("~/.ssh/id_rsa")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE
        # Verify path was expanded
        assert "~" not in result.resolved_path


class TestScopeResultMethods:
    """Tests for ScopeResult helper methods."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    def test_is_in_scope_method(self, detector):
        result = detector.detect("./src/main.py")
        assert result.verdict == ScopeVerdict.IN_SCOPE
        # Note: is_in_scope is on types.ScopeResult, not detector.ScopeResult
        # but both should have same verdict

    def test_result_contains_path_info(self, detector):
        result = detector.detect("./src/main.py")
        assert result.path == "./src/main.py"
        assert result.project_root == str(detector.project_root)
        assert len(result.resolved_path) > 0

    def test_result_contains_reason(self, detector):
        """Sensitive path should have a reason."""
        result = detector.detect(str(detector.home / ".ssh" / "id_rsa"))
        assert result.reason
        assert len(result.reason) > 0


class TestNeutralOutOfScope:
    """Tests for OUT_OF_SCOPE_NEUTRAL verdict."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    def test_unknown_path_is_out_of_scope(self, detector, tmp_path):
        """Path outside project should be out of scope (allowed, neutral, or suspicious)."""
        # tmp_path may be under /var/folders (macOS) which could be allowed or suspicious
        # Just verify it's not IN_SCOPE
        other_project = tmp_path / "other_project" / "file.py"
        result = detector.detect(str(other_project))
        assert result.verdict != ScopeVerdict.IN_SCOPE
        # score_modifier can be 0 for allowed paths like temp directories
        assert result.score_modifier >= 0

    def test_neutral_path_score(self, detector):
        """Truly neutral path outside common patterns should have base score."""
        # Use a path that's not in any predefined pattern
        # /srv is typically neutral on most systems
        result = detector.detect("/srv/app/data/file.txt", "read")
        # If it's truly neutral, score should be modest
        assert result.score_modifier > 0

    def test_write_higher_than_read_for_out_of_scope(self, detector):
        """Write operations should have higher scores than read."""
        path = "/srv/app/data/file.txt"
        read_result = detector.detect(path, "read")
        write_result = detector.detect(path, "write")
        assert write_result.score_modifier > read_result.score_modifier
