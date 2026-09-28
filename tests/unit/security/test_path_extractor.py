"""Tests for PathExtractor - extracting file paths from bash commands."""

import pytest
from opencode_status_bar.security.scope.path_extractor import PathExtractor


class TestPathExtractor:
    """Test path extraction from bash commands."""

    @pytest.mark.parametrize(
        "command,expected",
        [
            ("cat /etc/passwd", ["/etc/passwd"]),
            ("rm -rf /tmp/test", ["/tmp/test"]),
            ("cp ~/.ssh/id_rsa /tmp/", ["~/.ssh/id_rsa", "/tmp/"]),
            ("ls -la", []),
            ("echo hello", []),
            ("cat file.txt | grep pattern", ["file.txt"]),
        ],
    )
    def test_extract_from_command(self, command, expected):
        """Test extraction of paths from various commands."""
        result = PathExtractor.extract_from_command(command)
        assert result == expected

    def test_empty_command(self):
        """Test with empty or whitespace commands."""
        assert PathExtractor.extract_from_command("") == []
        assert PathExtractor.extract_from_command("   ") == []
        assert PathExtractor.extract_from_command(None) == []

    def test_sudo_prefix(self):
        """Test commands with sudo prefix."""
        result = PathExtractor.extract_from_command("sudo cat /etc/shadow")
        assert result == ["/etc/shadow"]

    def test_env_vars(self):
        """Test commands with environment variables."""
        result = PathExtractor.extract_from_command("FOO=bar cat /tmp/file.txt")
        assert result == ["/tmp/file.txt"]

    def test_piped_commands(self):
        """Test piped command chains."""
        result = PathExtractor.extract_from_command(
            "cat /etc/passwd | grep root | head -n 1"
        )
        assert result == ["/etc/passwd"]

    def test_relative_paths(self):
        """Test relative path detection."""
        result = PathExtractor.extract_from_command("cat ./config.json")
        assert result == ["./config.json"]

        result = PathExtractor.extract_from_command("cat ../parent/file.txt")
        assert result == ["../parent/file.txt"]

    def test_home_expansion(self):
        """Test tilde home directory paths."""
        result = PathExtractor.extract_from_command("cat ~/.bashrc")
        assert result == ["~/.bashrc"]

    def test_multiple_files(self):
        """Test commands with multiple file arguments."""
        result = PathExtractor.extract_from_command("cat /etc/passwd /etc/shadow")
        assert result == ["/etc/passwd", "/etc/shadow"]

    def test_unknown_command_path_extraction(self):
        """Test path extraction from unknown commands."""
        result = PathExtractor.extract_from_command("mycommand /path/to/file.txt")
        assert result == ["/path/to/file.txt"]


class TestPathExtractorTool:
    """Test extract_from_tool method."""

    def test_read_tool(self):
        """Test extraction from read tool."""
        result = PathExtractor.extract_from_tool(
            "read", {"filePath": "/home/user/file.txt"}
        )
        assert result == ["/home/user/file.txt"]

    def test_write_tool(self):
        """Test extraction from write tool."""
        result = PathExtractor.extract_from_tool(
            "write", {"filePath": "/tmp/output.txt"}
        )
        assert result == ["/tmp/output.txt"]

    def test_edit_tool(self):
        """Test extraction from edit tool."""
        result = PathExtractor.extract_from_tool(
            "edit", {"filePath": "/project/src/main.py"}
        )
        assert result == ["/project/src/main.py"]

    def test_bash_tool(self):
        """Test extraction from bash tool."""
        result = PathExtractor.extract_from_tool("bash", {"command": "cat /etc/passwd"})
        assert result == ["/etc/passwd"]

    def test_glob_tool(self):
        """Test extraction from glob tool."""
        result = PathExtractor.extract_from_tool(
            "glob", {"pattern": "**/*.py", "path": "/project"}
        )
        assert result == ["**/*.py", "/project"]

    def test_empty_args(self):
        """Test with empty or missing arguments."""
        assert PathExtractor.extract_from_tool("read", {}) == []
        assert PathExtractor.extract_from_tool("read", {"filePath": ""}) == []
        assert PathExtractor.extract_from_tool("bash", {"command": ""}) == []

    def test_unknown_tool(self):
        """Test with unknown tool."""
        result = PathExtractor.extract_from_tool("unknown", {"foo": "bar"})
        assert result == []


class TestLooksLikePath:
    """Test the _looks_like_path helper."""

    def test_absolute_paths(self):
        """Test absolute path detection."""
        assert PathExtractor._looks_like_path("/etc/passwd")
        assert PathExtractor._looks_like_path("/home/user/file.txt")

    def test_relative_paths(self):
        """Test relative path detection."""
        assert PathExtractor._looks_like_path("./file.txt")
        assert PathExtractor._looks_like_path("../file.txt")

    def test_home_paths(self):
        """Test home directory path detection."""
        assert PathExtractor._looks_like_path("~/.bashrc")
        assert PathExtractor._looks_like_path("~/Documents/file.txt")

    def test_file_extensions(self):
        """Test file extension detection."""
        assert PathExtractor._looks_like_path("file.txt")
        assert PathExtractor._looks_like_path("script.py")
        assert PathExtractor._looks_like_path("config.json")

    def test_urls_excluded(self):
        """Test that URLs are excluded."""
        assert not PathExtractor._looks_like_path("http://example.com/path")
        assert not PathExtractor._looks_like_path("https://example.com/path")

    def test_non_paths(self):
        """Test non-path strings."""
        assert not PathExtractor._looks_like_path("")
        assert not PathExtractor._looks_like_path("hello")
        assert not PathExtractor._looks_like_path("-v")
