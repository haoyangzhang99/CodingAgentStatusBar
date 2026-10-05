"""Tests for tooltips feature on truncated elements."""

import pytest
from unittest.mock import MagicMock, patch

# Constants from app.py
TITLE_MAX_LENGTH = 40
TOOL_ARG_MAX_LENGTH = 30
TODO_CURRENT_MAX_LENGTH = 35
TODO_PENDING_MAX_LENGTH = 30


@pytest.fixture
def mock_menu_item():
    """Create a mock rumps.MenuItem with _menuitem attribute."""
    with patch("rumps.MenuItem") as MockMenuItem:
        mock_instance = MagicMock()
        mock_instance._menuitem = MagicMock()
        MockMenuItem.return_value = mock_instance
        yield MockMenuItem, mock_instance


def _get_truncate_function():
    """Import the function under test (after mocking rumps)."""
    from coding_agent_status_bar.app import _truncate_with_tooltip

    return _truncate_with_tooltip


class TestTruncateWithTooltip:
    """Tests for the _truncate_with_tooltip function."""

    BOUNDARY_CASES = [
        ("Short title", TITLE_MAX_LENGTH, False),
        ("x" * TITLE_MAX_LENGTH, TITLE_MAX_LENGTH, False),  # Exact length
        ("x" * (TITLE_MAX_LENGTH + 1), TITLE_MAX_LENGTH, True),  # Above limit
        ("a" * 29, TOOL_ARG_MAX_LENGTH, False),
        ("a" * 30, TOOL_ARG_MAX_LENGTH, False),
        ("a" * 31, TOOL_ARG_MAX_LENGTH, True),
        ("a" * 35, TODO_CURRENT_MAX_LENGTH, False),
        ("a" * 36, TODO_CURRENT_MAX_LENGTH, True),
        ("a" * 30, TODO_PENDING_MAX_LENGTH, False),
        ("a" * 31, TODO_PENDING_MAX_LENGTH, True),
    ]

    @pytest.mark.parametrize("text,max_length,should_truncate", BOUNDARY_CASES)
    def test_truncation_at_boundary(
        self, mock_menu_item, text, max_length, should_truncate
    ):
        """Test truncation behavior at various boundary conditions."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = _get_truncate_function()

        result = _truncate_with_tooltip(text, max_length)
        call_args = MockMenuItem.call_args[0][0]

        # Verify MenuItem was created correctly
        MockMenuItem.assert_called_once()
        assert isinstance(result, MagicMock)
        assert isinstance(call_args, str)
        assert len(call_args) <= max_length
        if should_truncate:
            # Truncated: tooltip set, ends with ..., correct length
            mock_instance._menuitem.setToolTip_.assert_called_once()
            assert call_args.endswith("...")
            assert len(call_args) == max_length
        else:
            # Not truncated: no tooltip, original text
            mock_instance._menuitem.setToolTip_.assert_not_called()
            assert call_args == text

    LONG_TEXT_CASES = [
        ("This is a very long title that exceeds the maximum length", 30),
        ("A" * 100, 25),
        ("Hello World", 8),
    ]

    @pytest.mark.parametrize("text,max_length", LONG_TEXT_CASES)
    def test_long_text_truncation(self, mock_menu_item, text, max_length):
        """Long text is truncated with '...' and has tooltip with full text."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = _get_truncate_function()

        result = _truncate_with_tooltip(text, max_length)
        call_args = MockMenuItem.call_args[0][0]

        # Verify truncation
        assert len(call_args) == max_length
        assert call_args.endswith("...")
        assert isinstance(call_args, str)
        # Verify tooltip contains full original text
        mock_instance._menuitem.setToolTip_.assert_called_once_with(text)
        assert isinstance(result, MagicMock)
        MockMenuItem.assert_called_once()

    PREFIX_CASES = [
        ("Short", "  -> ", 40, False),
        (
            "This is a very long text that will definitely be truncated",
            "    ",
            25,
            True,
        ),
        ("A" * 35, "ICON ", 30, True),
        ("Very long todo item description here", "    -> ", 20, True),
    ]

    @pytest.mark.parametrize("text,prefix,max_length,should_truncate", PREFIX_CASES)
    def test_prefix_handling(
        self, mock_menu_item, text, prefix, max_length, should_truncate
    ):
        """Prefix is prepended correctly to both short and truncated text."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = _get_truncate_function()

        result = _truncate_with_tooltip(text, max_length, prefix=prefix)
        call_args = MockMenuItem.call_args[0][0]

        # Prefix always prepended
        assert call_args.startswith(prefix)
        assert isinstance(result, MagicMock)
        MockMenuItem.assert_called_once()
        assert isinstance(call_args, str)
        if should_truncate:
            assert call_args.endswith("...")
            mock_instance._menuitem.setToolTip_.assert_called_once()

    def test_callback_passed_correctly(self, mock_menu_item):
        """Callback is passed to MenuItem."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = _get_truncate_function()

        callback = MagicMock()
        result = _truncate_with_tooltip("Click me", 40, callback=callback)

        assert MockMenuItem.call_args[1]["callback"] == callback
        assert isinstance(result, MagicMock)
        MockMenuItem.assert_called_once()
        assert isinstance(mock_instance, MagicMock)

    def test_empty_text_no_tooltip(self, mock_menu_item):
        """Empty text handled properly - no tooltip set."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = _get_truncate_function()

        result = _truncate_with_tooltip("", 40)

        MockMenuItem.assert_called_once_with("", callback=None)
        mock_instance._menuitem.setToolTip_.assert_not_called()
        assert isinstance(result, MagicMock)

    def test_empty_prefix_works(self, mock_menu_item):
        """Empty prefix should work correctly."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = _get_truncate_function()

        result = _truncate_with_tooltip("Some text", 40, prefix="")

        MockMenuItem.assert_called_once_with("Some text", callback=None)
        assert isinstance(result, MagicMock)
        mock_instance._menuitem.setToolTip_.assert_not_called()

    def test_unicode_text_handled_by_char_count(self, mock_menu_item):
        """Unicode characters are handled by character count, not bytes."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = _get_truncate_function()

        text = "Japanese file name.py"
        result = _truncate_with_tooltip(text, 15)
        call_args = MockMenuItem.call_args[0][0]

        # Truncated by char count
        assert len(call_args) == 15
        mock_instance._menuitem.setToolTip_.assert_called_once_with(text)
        assert isinstance(result, MagicMock)
        assert call_args.endswith("...")


class TestTruncationConstants:
    """Tests to verify truncation constants are correctly defined."""

    CONSTANTS = [
        ("TITLE_MAX_LENGTH", 40),
        ("TOOL_ARG_MAX_LENGTH", 30),
    ]

    @pytest.mark.parametrize("constant_name,expected_value", CONSTANTS)
    def test_truncation_constants(self, constant_name, expected_value):
        """Verify truncation constants have correct values."""
        from coding_agent_status_bar.ui import menu

        actual = getattr(menu, constant_name)
        assert actual == expected_value
        assert isinstance(actual, int)


class TestRealWorldScenarios:
    """Integration-like tests with realistic data."""

    SCENARIOS = [
        # Long file path (tool)
        (
            "Read: /Users/developer/projects/opencode-swiftbar-monitor/src/coding_agent_status_bar/app.py",
            TOOL_ARG_MAX_LENGTH,
            "    ",
            True,
        ),
        # Long todo
        (
            "Implement the authentication flow with OAuth2 and JWT tokens",
            TODO_CURRENT_MAX_LENGTH,
            "    ",
            True,
        ),
        # Short agent title
        ("my-project", TITLE_MAX_LENGTH, " ", False),
        # Long agent title with path
        (
            "opencode-swiftbar-monitor (feature/add-tooltips)",
            TITLE_MAX_LENGTH,
            " ",
            True,
        ),
    ]

    @pytest.mark.parametrize("text,max_length,prefix,should_truncate", SCENARIOS)
    def test_real_world_scenario(
        self, mock_menu_item, text, max_length, prefix, should_truncate
    ):
        """Test realistic menu item scenarios."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = _get_truncate_function()

        result = _truncate_with_tooltip(text, max_length, prefix=prefix)
        call_args = MockMenuItem.call_args[0][0]

        # Always valid result
        assert isinstance(result, MagicMock)
        MockMenuItem.assert_called_once()
        assert call_args.startswith(prefix)
        assert isinstance(call_args, str)
        if should_truncate:
            assert call_args.endswith("...")
            mock_instance._menuitem.setToolTip_.assert_called_once_with(text)
        else:
            assert call_args == f"{prefix}{text}"
            mock_instance._menuitem.setToolTip_.assert_not_called()
