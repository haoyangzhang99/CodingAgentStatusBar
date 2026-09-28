"""Tests ensuring common dev patterns don't trigger false alerts."""

import pytest
from pathlib import Path
from opencode_status_bar.security.scope import ScopeDetector, ScopeVerdict


class TestPackageManagerCaches:
    """Package manager caches should not trigger alerts."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    @pytest.mark.parametrize(
        "path_suffix",
        [
            ".npm/_cacache/content-v2/sha512/abc",
            ".cache/pip/wheels/ab/cd/file.whl",
            ".yarn/cache/lodash-npm-4.17.21.zip",
        ],
    )
    def test_package_caches_allowed(self, detector, path_suffix):
        """Package caches using real home should be allowed."""
        path = str(detector.home / path_suffix)
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED
        assert result.score_modifier == 0

    def test_npm_global_cache(self, detector):
        """NPM global cache should be allowed."""
        path = str(detector.home / ".npm" / "registry" / "package.json")
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED

    def test_yarn_berry_cache(self, detector):
        """Yarn Berry cache should be allowed."""
        path = str(detector.home / ".yarn" / "berry" / "cache" / "pkg.zip")
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED

    def test_local_share_allowed(self, detector):
        """~/.local/share should be allowed."""
        path = str(detector.home / ".local" / "share" / "data")
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED


class TestBuildArtifacts:
    """Build artifacts in temp should not trigger alerts."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    @pytest.mark.parametrize(
        "path",
        [
            "/tmp/pytest-of-user/pytest-123/test0/output.log",
            "/tmp/npm-cache-abc123/package.json",
            "/var/tmp/gradle-build/output",
        ],
    )
    def test_build_temps_allowed(self, detector, path):
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED

    def test_var_folders_macos_temp(self, detector):
        """macOS temp folders under /var/folders should be allowed."""
        result = detector.detect("/var/folders/ab/cd/T/tmp_file.txt")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED


class TestIDEConfigs:
    """IDE configurations should be in scope when inside project."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / ".vscode").mkdir()
        (project / ".idea").mkdir()
        return ScopeDetector(project)

    def test_vscode_settings_in_scope(self, detector):
        result = detector.detect("./.vscode/settings.json")
        assert result.verdict == ScopeVerdict.IN_SCOPE
        assert result.score_modifier == 0

    def test_vscode_launch_in_scope(self, detector):
        result = detector.detect("./.vscode/launch.json")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_vscode_extensions_in_scope(self, detector):
        result = detector.detect("./.vscode/extensions.json")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_idea_settings_in_scope(self, detector):
        result = detector.detect("./.idea/workspace.xml")
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestPythonEnvironments:
    """Python virtual environments and caches."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / ".venv").mkdir()
        return ScopeDetector(project)

    def test_project_venv_in_scope(self, detector):
        """Local .venv should be in scope."""
        result = detector.detect("./.venv/bin/python")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_pip_cache_allowed(self, detector):
        """Pip cache (using real home) should be allowed."""
        path = str(detector.home / ".cache" / "pip" / "http" / "cache.db")
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED

    def test_uv_cache_allowed(self, detector):
        """UV cache (using real home) should be allowed."""
        path = str(detector.home / ".cache" / "uv" / "archives" / "pkg.tar.gz")
        result = detector.detect(path)
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED


class TestGitOperations:
    """Git-related operations should be handled correctly."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / ".git" / "hooks").mkdir()
        return ScopeDetector(project)

    def test_git_directory_in_scope(self, detector):
        result = detector.detect("./.git/config")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_git_hooks_in_scope(self, detector):
        result = detector.detect("./.git/hooks/pre-commit")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_gitignore_in_scope(self, detector):
        result = detector.detect("./.gitignore")
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestDockerOperations:
    """Docker-related files should be handled correctly."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    def test_dockerfile_in_scope(self, detector):
        result = detector.detect("./Dockerfile")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_docker_compose_in_scope(self, detector):
        result = detector.detect("./docker-compose.yml")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_dockerignore_in_scope(self, detector):
        result = detector.detect("./.dockerignore")
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestNodeModules:
    """Node modules handling."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / "node_modules").mkdir()
        (project / "node_modules" / "lodash").mkdir()
        return ScopeDetector(project)

    def test_node_modules_in_scope(self, detector):
        """node_modules inside project is in scope."""
        result = detector.detect("./node_modules/lodash/index.js")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_package_json_in_scope(self, detector):
        result = detector.detect("./package.json")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_package_lock_in_scope(self, detector):
        result = detector.detect("./package-lock.json")
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestConfigurationFiles:
    """Project configuration files should be in scope."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    @pytest.mark.parametrize(
        "config_file",
        [
            "./pyproject.toml",
            "./setup.py",
            "./setup.cfg",
            "./requirements.txt",
            "./.env.example",
            "./tsconfig.json",
            "./.eslintrc.json",
            "./.prettierrc",
            "./Makefile",
        ],
    )
    def test_config_files_in_scope(self, detector, config_file):
        result = detector.detect(config_file)
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestMultiLanguageProjects:
    """Tests for typical multi-language project structures."""

    @pytest.fixture
    def monorepo(self, tmp_path):
        """Create a monorepo-style project structure."""
        root = tmp_path / "monorepo"
        root.mkdir()

        # Backend (Python)
        (root / "backend" / "src").mkdir(parents=True)
        (root / "backend" / "tests").mkdir()

        # Frontend (Node)
        (root / "frontend" / "src").mkdir(parents=True)
        (root / "frontend" / "node_modules").mkdir()

        # Infrastructure
        (root / "infra" / "terraform").mkdir(parents=True)

        # Shared
        (root / "shared" / "proto").mkdir(parents=True)

        return root

    def test_all_monorepo_paths_in_scope(self, monorepo):
        detector = ScopeDetector(monorepo)

        paths = [
            "./backend/src/main.py",
            "./frontend/src/App.tsx",
            "./frontend/node_modules/react/index.js",
            "./infra/terraform/main.tf",
            "./shared/proto/service.proto",
        ]

        for path in paths:
            result = detector.detect(path)
            assert result.verdict == ScopeVerdict.IN_SCOPE, f"{path} should be in scope"


class TestRealisticReadPatterns:
    """Tests for realistic AI assistant read patterns."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / "src").mkdir()
        return ScopeDetector(project)

    def test_reading_source_file(self, detector):
        """Reading source files is common and should be allowed."""
        result = detector.detect("./src/components/Button.tsx", "read")
        assert result.verdict == ScopeVerdict.IN_SCOPE
        assert result.score_modifier == 0

    def test_reading_test_file(self, detector):
        result = detector.detect("./tests/test_api.py", "read")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_reading_readme(self, detector):
        result = detector.detect("./README.md", "read")
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestRealisticWritePatterns:
    """Tests for realistic AI assistant write patterns."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / "src").mkdir()
        return ScopeDetector(project)

    def test_writing_new_source_file(self, detector):
        """Writing new source files should be allowed."""
        result = detector.detect("./src/new_feature.py", "write")
        assert result.verdict == ScopeVerdict.IN_SCOPE
        assert result.score_modifier == 0

    def test_editing_existing_file(self, detector):
        result = detector.detect("./src/existing.py", "write")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_creating_test_file(self, detector):
        result = detector.detect("./tests/test_new_feature.py", "write")
        assert result.verdict == ScopeVerdict.IN_SCOPE


class TestEdgeCasesNoFalsePositives:
    """Edge cases that shouldn't trigger false positives."""

    @pytest.fixture
    def detector(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        return ScopeDetector(project)

    def test_deep_nesting(self, detector):
        """Deeply nested paths should work correctly."""
        result = detector.detect("./src/components/ui/forms/inputs/TextInput.tsx")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_file_with_special_chars(self, detector):
        """Files with special characters should work."""
        result = detector.detect("./docs/API_v2.0_spec.md")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_hidden_files(self, detector):
        """Hidden files in project should be in scope."""
        result = detector.detect("./.env.local")
        assert result.verdict == ScopeVerdict.IN_SCOPE

    def test_file_without_extension(self, detector):
        """Files without extensions should work."""
        result = detector.detect("./Makefile")
        assert result.verdict == ScopeVerdict.IN_SCOPE
        result = detector.detect("./Dockerfile")
        assert result.verdict == ScopeVerdict.IN_SCOPE
