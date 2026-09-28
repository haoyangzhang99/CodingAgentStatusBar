"""Tests for enriched helpers module."""

import pytest

from opencode_status_bar.dashboard.sections.tracing.enriched_helpers import (
    get_tool_display_label,
    format_result_tooltip,
    get_agent_color,
    format_cost,
    format_tokens_short,
)


class TestGetToolDisplayLabel:
    """Tests for get_tool_display_label function."""

    def test_returns_title_when_present(self):
        """Should return title when available."""
        tool_data = {"title": "Check git status", "tool_name": "bash"}
        assert get_tool_display_label(tool_data) == "Check git status"

    def test_returns_formatted_tool_name_when_no_title(self):
        """Should return formatted tool_name when title is missing."""
        tool_data = {"tool_name": "bash"}
        assert get_tool_display_label(tool_data) == "Bash"

    def test_handles_underscore_in_tool_name(self):
        """Should format tool_name with underscores properly."""
        tool_data = {"tool_name": "webfetch_url"}
        assert get_tool_display_label(tool_data) == "Webfetch Url"

    def test_returns_unknown_when_both_missing(self):
        """Should return 'Unknown' when both title and tool_name are missing."""
        tool_data = {}
        assert get_tool_display_label(tool_data) == "Unknown"

    def test_prefers_title_over_tool_name(self):
        """Title should take priority over tool_name."""
        tool_data = {"title": "Read config file", "tool_name": "read"}
        assert get_tool_display_label(tool_data) == "Read config file"

    def test_handles_empty_title(self):
        """Empty title should fallback to tool_name."""
        tool_data = {"title": "", "tool_name": "grep"}
        assert get_tool_display_label(tool_data) == "Grep"

    def test_handles_none_title(self):
        """None title should fallback to tool_name."""
        tool_data = {"title": None, "tool_name": "glob"}
        assert get_tool_display_label(tool_data) == "Glob"


class TestFormatResultTooltip:
    """Tests for format_result_tooltip function."""

    def test_returns_empty_when_no_enriched_data(self):
        """Should return empty string when no enriched data."""
        tool_data = {"tool_name": "bash"}
        assert format_result_tooltip(tool_data) == ""

    def test_formats_result_summary_only(self):
        """Should format just result_summary."""
        tool_data = {"result_summary": "File read successfully (245 lines)"}
        result = format_result_tooltip(tool_data)
        assert "File read successfully (245 lines)" in result

    def test_formats_cost_only(self):
        """Should format just cost."""
        tool_data = {"cost": 0.0012}
        result = format_result_tooltip(tool_data)
        assert "Cost:" in result
        assert "$0.0012" in result

    def test_formats_tokens_only(self):
        """Should format just tokens."""
        tool_data = {"tokens_in": 1200, "tokens_out": 500}
        result = format_result_tooltip(tool_data)
        assert "Tokens:" in result
        assert "1.2K" in result

    def test_formats_all_fields(self):
        """Should format all enriched fields together."""
        tool_data = {
            "result_summary": "Files matched: 3",
            "cost": 0.05,
            "tokens_in": 5000,
            "tokens_out": 200,
        }
        result = format_result_tooltip(tool_data)
        assert "Files matched: 3" in result
        assert "Cost:" in result
        assert "Tokens:" in result

    def test_truncates_long_result_summary(self):
        """Should truncate result_summary longer than 150 chars."""
        long_summary = "A" * 200
        tool_data = {"result_summary": long_summary}
        result = format_result_tooltip(tool_data)
        assert len(result) < 200
        assert "..." in result


class TestGetAgentColor:
    """Tests for get_agent_color function."""

    def test_returns_colors_for_known_agents(self):
        """Should return correct colors for known agent types."""
        text, bg = get_agent_color("executor")
        assert text == "#22c55e"  # Green
        assert "rgba" in bg

    def test_returns_default_for_unknown_agent(self):
        """Should return default colors for unknown agent types."""
        text, bg = get_agent_color("custom_agent")
        assert text == "#6b7280"  # Gray

    def test_case_insensitive(self):
        """Should handle different cases."""
        text1, _ = get_agent_color("EXECUTOR")
        text2, _ = get_agent_color("executor")
        assert text1 == text2

    def test_main_agent_is_blue(self):
        """Main agent should have blue color."""
        text, _ = get_agent_color("main")
        assert text == "#3b82f6"  # Blue

    def test_tea_agent_is_amber(self):
        """Tea agent should have amber color."""
        text, _ = get_agent_color("tea")
        assert text == "#f59e0b"  # Amber


class TestFormatCost:
    """Tests for format_cost function."""

    def test_none_returns_dash(self):
        """Should return '-' for None cost."""
        assert format_cost(None) == "-"

    def test_zero_cost(self):
        """Should format zero cost."""
        result = format_cost(0.0)
        assert "$" in result

    def test_small_cost_shows_more_decimals(self):
        """Costs < $0.01 should show more precision."""
        result = format_cost(0.001)
        assert result == "$0.0010"

    def test_medium_cost(self):
        """Costs between $0.01 and $1.00."""
        result = format_cost(0.05)
        assert result == "$0.050"

    def test_large_cost(self):
        """Costs >= $1.00."""
        result = format_cost(1.50)
        assert result == "$1.50"


class TestFormatTokensShort:
    """Tests for format_tokens_short function."""

    def test_none_returns_dash(self):
        """Should return '-' for None."""
        assert format_tokens_short(None) == "-"

    def test_zero_returns_zero(self):
        """Should return '0' for zero."""
        assert format_tokens_short(0) == "0"

    def test_small_number_no_suffix(self):
        """Numbers < 1000 should not have suffix."""
        assert format_tokens_short(500) == "500"

    def test_thousands_with_k_suffix(self):
        """Numbers >= 1000 should have K suffix."""
        assert format_tokens_short(1200) == "1.2K"

    def test_millions_with_m_suffix(self):
        """Numbers >= 1000000 should have M suffix."""
        assert format_tokens_short(1500000) == "1.5M"

    def test_rounds_correctly(self):
        """Should round to one decimal place."""
        assert format_tokens_short(1550) == "1.6K"
