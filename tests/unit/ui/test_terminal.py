"""
Tests for terminal focus functionality.
"""

import subprocess
from unittest.mock import MagicMock, patch


from opencode_status_bar.ui.terminal import focus_iterm2


class TestFocusIterm2:
    """Tests for the focus_iterm2 function."""

    # =========================================================
    # TTY Path Normalization Tests
    # =========================================================

    def test_focus_iterm2_adds_dev_prefix_when_missing(self):
        """TTY without /dev/ prefix should have it added."""
        with patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()

            result = focus_iterm2("ttys001")

            assert result
            mock_run.assert_called_once()
            # Verify the script contains the normalized path
            call_args = mock_run.call_args
            script = call_args[0][0][2]  # ["osascript", "-e", script]
            assert "/dev/ttys001" in script

    def test_focus_iterm2_keeps_dev_prefix_when_present(self):
        """TTY with /dev/ prefix should be kept as-is."""
        with patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()

            result = focus_iterm2("/dev/ttys002")

            assert result
            mock_run.assert_called_once()
            # Verify the script contains the path unchanged
            call_args = mock_run.call_args
            script = call_args[0][0][2]
            assert "/dev/ttys002" in script
            # Ensure no double /dev/
            assert "/dev//dev/" not in script

    # =========================================================
    # AppleScript Execution Tests
    # =========================================================

    def test_focus_iterm2_calls_osascript_with_correct_args(self):
        """Should call osascript with correct arguments."""
        with patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()

            focus_iterm2("ttys001")

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0][0] == "osascript"
            assert call_args[0][0][1] == "-e"
            assert call_args.kwargs["capture_output"]
            assert call_args.kwargs["timeout"] == 5

    def test_focus_iterm2_returns_true_on_success(self):
        """Should return True when subprocess succeeds."""
        with patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()

            result = focus_iterm2("ttys001")

            assert result

    # =========================================================
    # Error Handling Tests
    # =========================================================

    def test_focus_iterm2_returns_false_on_timeout(self):
        """Should return False and log error when subprocess times out."""
        with (
            patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run,
            patch("opencode_status_bar.ui.terminal.error") as mock_error,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="osascript", timeout=5)

            result = focus_iterm2("ttys001")

            assert not result
            mock_error.assert_called_once()
            assert "Focus terminal failed" in mock_error.call_args[0][0]

    def test_focus_iterm2_returns_false_on_subprocess_error(self):
        """Should return False and log error when subprocess raises an error."""
        with (
            patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run,
            patch("opencode_status_bar.ui.terminal.error") as mock_error,
        ):
            mock_run.side_effect = subprocess.SubprocessError("Command failed")

            result = focus_iterm2("ttys001")

            assert not result
            mock_error.assert_called_once()
            assert "Focus terminal failed" in mock_error.call_args[0][0]

    def test_focus_iterm2_returns_false_on_file_not_found(self):
        """Should return False when osascript is not found."""
        with (
            patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run,
            patch("opencode_status_bar.ui.terminal.error") as mock_error,
        ):
            mock_run.side_effect = FileNotFoundError("osascript not found")

            result = focus_iterm2("ttys001")

            assert not result
            mock_error.assert_called_once()

    def test_focus_iterm2_returns_false_on_generic_exception(self):
        """Should return False on any generic exception."""
        with (
            patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run,
            patch("opencode_status_bar.ui.terminal.error") as mock_error,
        ):
            mock_run.side_effect = Exception("Unexpected error")

            result = focus_iterm2("ttys001")

            assert not result
            mock_error.assert_called_once()
            assert "Unexpected error" in mock_error.call_args[0][0]

    # =========================================================
    # AppleScript Content Tests
    # =========================================================

    def test_focus_iterm2_script_contains_iterm2_commands(self):
        """AppleScript should contain iTerm2 specific commands."""
        with patch("opencode_status_bar.ui.terminal.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()

            focus_iterm2("ttys001")

            call_args = mock_run.call_args
            script = call_args[0][0][2]
            assert 'tell application "iTerm2"' in script
            assert "activate" in script
            assert "windows" in script
            assert "tabs" in script
            assert "current session" in script
            assert "tty of s" in script
