import pytest
from PyQt6.QtGui import QColor

from opencode_status_bar.dashboard.sections.tracing.tree_formatters import (
    get_display_text,
    get_foreground_color,
    get_tooltip,
)
from opencode_status_bar.dashboard.styles import COLORS


class TestGetDisplayTextNameColumn:
    def test_session_with_title(self):
        data = {
            "node_type": "session",
            "directory": "/Users/test/project",
            "title": "Fix bug #123",
        }
        result = get_display_text(data, 0)
        assert result == "🌳 project: Fix bug #123"

    def test_session_without_title(self):
        data = {"node_type": "session", "directory": "/Users/test/myapp"}
        result = get_display_text(data, 0)
        assert result == "🌳 myapp"

    def test_session_no_directory(self):
        data = {"node_type": "session", "directory": None}
        result = get_display_text(data, 0)
        assert result == "🌳 Unknown"

    def test_user_turn_with_short_prompt(self):
        data = {
            "node_type": "user_turn",
            "prompt_input": "Hello world",
            "agent": "assistant",
        }
        result = get_display_text(data, 0)
        assert result == '💬 user → assistant: "Hello world"'

    def test_user_turn_compaction_uses_box_icon(self):
        data = {"node_type": "user_turn", "agent": "compaction", "prompt_input": "test"}
        result = get_display_text(data, 0)
        assert result == '📦 user → compaction: "test"'

    def test_user_turn_without_prompt(self):
        data = {"node_type": "user_turn", "agent": "oracle"}
        result = get_display_text(data, 0)
        assert result == "💬 user → oracle"

    def test_user_turn_truncates_at_60_chars(self):
        prompt = "A" * 70
        data = {"node_type": "user_turn", "prompt_input": prompt, "agent": "assistant"}
        result = get_display_text(data, 0)
        expected = f'💬 user → assistant: "{"A" * 60}..."'
        assert result == expected

    def test_user_turn_replaces_newlines(self):
        data = {
            "node_type": "user_turn",
            "prompt_input": "line1\nline2",
            "agent": "assistant",
        }
        result = get_display_text(data, 0)
        assert result == '💬 user → assistant: "line1 line2"'

    def test_agent_with_parent(self):
        data = {
            "node_type": "agent",
            "subagent_type": "oracle",
            "parent_agent": "build",
            "depth": 1,
        }
        result = get_display_text(data, 0)
        assert "build → oracle" in result

    def test_agent_without_parent(self):
        data = {"node_type": "agent", "subagent_type": "explore", "depth": 0}
        result = get_display_text(data, 0)
        assert "explore" in result
        assert (
            "→" not in result
            or result.count("→") == 0
            or "explore" == result.split()[-1]
        )

    def test_tool_with_display_info(self):
        data = {"node_type": "tool", "tool_name": "bash", "display_info": "git status"}
        result = get_display_text(data, 0)
        assert result == "  🔧 Bash: git status"

    def test_tool_without_display_info(self):
        data = {"node_type": "tool", "tool_name": "bash"}
        result = get_display_text(data, 0)
        assert result == "  🔧 Bash"

    def test_tool_truncates_display_info_at_50_chars(self):
        display_info = "X" * 60
        data = {"node_type": "tool", "tool_name": "read", "display_info": display_info}
        result = get_display_text(data, 0)
        assert result == f"  📖 Read: {'X' * 50}..."

    def test_text_part_with_content(self):
        data = {"node_type": "part", "type": "text", "content": "Hello"}
        result = get_display_text(data, 0)
        assert result == "  💭 Hello"

    def test_text_part_empty_content(self):
        data = {"node_type": "part", "type": "text", "content": ""}
        result = get_display_text(data, 0)
        assert result == "  💭 (text)"

    def test_unknown_part_type(self):
        data = {"node_type": "part", "type": "unknown_type"}
        result = get_display_text(data, 0)
        assert result == "  ○ unknown_type"


class TestGetDisplayTextOtherColumns:
    def test_time_column_formats_correctly(self):
        data = {"created_at": "2026-01-13T14:30:45"}
        result = get_display_text(data, 1)
        assert result == "01-13 14:30"

    def test_time_column_uses_started_at_fallback(self):
        data = {"started_at": "2026-02-20T09:15:00"}
        result = get_display_text(data, 1)
        assert result == "02-20 09:15"

    def test_time_column_empty_when_no_timestamp(self):
        data = {}
        result = get_display_text(data, 1)
        assert result == ""

    def test_duration_column_formats_ms(self):
        data = {"duration_ms": 5000}
        result = get_display_text(data, 2)
        assert result == "5.0s"

    def test_duration_column_returns_dash_when_zero(self):
        data = {"duration_ms": 0}
        result = get_display_text(data, 2)
        assert result == "-"

    def test_tokens_in_column(self):
        data = {"tokens_in": 1500}
        result = get_display_text(data, 3)
        assert result == "1.5K"

    def test_tokens_in_column_returns_dash_when_zero(self):
        data = {"tokens_in": 0}
        result = get_display_text(data, 3)
        assert result == "-"

    def test_tokens_out_column(self):
        data = {"tokens_out": 2500}
        result = get_display_text(data, 4)
        assert result == "2.5K"

    def test_status_completed(self):
        data = {"node_type": "tool", "tool_status": "completed"}
        result = get_display_text(data, 5)
        assert result == "✓"

    def test_status_error(self):
        data = {"node_type": "tool", "tool_status": "error"}
        result = get_display_text(data, 5)
        assert result == "✗"

    def test_status_running(self):
        data = {"node_type": "tool", "tool_status": "running"}
        result = get_display_text(data, 5)
        assert result == "◐"

    def test_status_empty_for_non_tool(self):
        data = {"node_type": "session"}
        result = get_display_text(data, 5)
        assert result == ""


class TestGetForegroundColor:
    def test_session_returns_tree_root_color(self):
        data = {"node_type": "session"}
        result = get_foreground_color(data, 0)
        expected = QColor(COLORS["tree_root"])
        assert result.name() == expected.name()

    def test_agent_returns_accent_color(self):
        data = {"node_type": "agent"}
        result = get_foreground_color(data, 0)
        expected = QColor(COLORS.get("accent_primary", "#3B82F6"))
        assert result.name() == expected.name()

    def test_tool_error_returns_error_color(self):
        data = {"node_type": "tool", "tool_status": "error"}
        result = get_foreground_color(data, 0)
        expected = QColor(COLORS["error"])
        assert result.name() == expected.name()

    def test_tool_with_name_returns_secondary_color(self):
        data = {"node_type": "tool", "tool_name": "bash", "tool_status": "completed"}
        result = get_foreground_color(data, 0)
        expected = QColor(COLORS["text_secondary"])
        assert result.name() == expected.name()

    def test_status_column_completed_returns_success(self):
        data = {"node_type": "tool", "tool_status": "completed"}
        result = get_foreground_color(data, 5)
        expected = QColor(COLORS["success"])
        assert result.name() == expected.name()

    def test_status_column_error_returns_error(self):
        data = {"node_type": "tool", "tool_status": "error"}
        result = get_foreground_color(data, 5)
        expected = QColor(COLORS["error"])
        assert result.name() == expected.name()

    def test_time_column_returns_secondary(self):
        data = {"node_type": "session"}
        result = get_foreground_color(data, 1)
        expected = QColor(COLORS["text_secondary"])
        assert result.name() == expected.name()

    def test_default_returns_muted(self):
        data = {"node_type": "session"}
        result = get_foreground_color(data, 3)
        expected = QColor(COLORS["text_muted"])
        assert result.name() == expected.name()


class TestGetTooltip:
    def test_user_turn_returns_full_prompt(self):
        prompt = "This is the full prompt text"
        data = {"node_type": "user_turn", "prompt_input": prompt}
        result = get_tooltip(data, 0)
        assert result == f"User:\n{prompt}"

    def test_user_turn_truncates_at_500_chars(self):
        prompt = "A" * 600
        data = {"node_type": "user_turn", "prompt_input": prompt}
        result = get_tooltip(data, 0)
        assert result == f"User:\n{'A' * 500}..."

    def test_user_turn_no_tooltip_without_prompt(self):
        data = {"node_type": "user_turn"}
        result = get_tooltip(data, 0)
        assert result is None

    def test_session_returns_none(self):
        data = {"node_type": "session"}
        result = get_tooltip(data, 0)
        assert result is None

    def test_non_name_column_returns_none(self):
        data = {"node_type": "user_turn", "prompt_input": "test"}
        assert get_tooltip(data, 1) is None
        assert get_tooltip(data, 2) is None
        assert get_tooltip(data, 3) is None
        assert get_tooltip(data, 4) is None
        assert get_tooltip(data, 5) is None

    def test_exchange_with_user_dict_format(self):
        data = {
            "node_type": "exchange",
            "user": {"content": "Question from user"},
        }
        result = get_tooltip(data, 0)
        assert result == "User:\nQuestion from user"
