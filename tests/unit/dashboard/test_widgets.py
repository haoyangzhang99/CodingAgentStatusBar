"""Tests for enriched tracing widgets."""

import pytest
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt


class TestAgentBadge:
    """Tests for AgentBadge widget."""

    def test_set_agent_shows_badge(self, qtbot):
        """Badge should be visible when agent is set."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            AgentBadge,
        )

        badge = AgentBadge()
        qtbot.addWidget(badge)
        badge.set_agent("executor")

        assert badge.isVisible()
        assert badge.text() == "exec"

    def test_empty_agent_hides_badge(self, qtbot):
        """Badge should be hidden when agent is empty."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            AgentBadge,
        )

        badge = AgentBadge("executor")
        qtbot.addWidget(badge)
        badge.set_agent("")

        assert not badge.isVisible()

    def test_none_agent_hides_badge(self, qtbot):
        """Badge should be hidden when agent is None."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            AgentBadge,
        )

        badge = AgentBadge("executor")
        qtbot.addWidget(badge)
        badge.set_agent(None)

        assert not badge.isVisible()

    def test_unknown_agent_uses_truncated_name(self, qtbot):
        """Unknown agent should show truncated name."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            AgentBadge,
        )

        badge = AgentBadge()
        qtbot.addWidget(badge)
        badge.set_agent("custom_agent")

        assert badge.isVisible()
        assert badge.text() == "cust"  # First 4 chars

    def test_agent_type_property(self, qtbot):
        """Should return correct agent type."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            AgentBadge,
        )

        badge = AgentBadge("executor")
        qtbot.addWidget(badge)

        assert badge.agent_type() == "executor"

    def test_init_with_agent(self, qtbot):
        """Should display agent on initialization."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            AgentBadge,
        )

        badge = AgentBadge("main")
        qtbot.addWidget(badge)

        assert badge.isVisible()
        assert badge.text() == "main"

    def test_tooltip_shows_agent_type(self, qtbot):
        """Tooltip should show full agent type."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            AgentBadge,
        )

        badge = AgentBadge("executor")
        qtbot.addWidget(badge)

        assert "executor" in badge.toolTip()

    def test_agent_labels_mapping(self, qtbot):
        """Known agents should use short labels."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            AgentBadge,
        )

        test_cases = [
            ("main", "main"),
            ("executor", "exec"),
            ("tea", "tea"),
            ("subagent", "sub"),
            ("coder", "coder"),
            ("analyst", "analyst"),
        ]

        for agent_type, expected_label in test_cases:
            badge = AgentBadge(agent_type)
            qtbot.addWidget(badge)
            assert badge.text() == expected_label, f"Failed for {agent_type}"


class TestErrorIndicator:
    """Tests for ErrorIndicator widget."""

    def test_set_error_shows_indicator(self, qtbot):
        """Indicator should be visible when error is set."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            ErrorIndicator,
        )

        indicator = ErrorIndicator()
        qtbot.addWidget(indicator)
        indicator.set_error({"name": "FileNotFoundError", "data": "File not found"})

        assert indicator.isVisible()
        assert indicator.text() == "!"

    def test_none_error_hides_indicator(self, qtbot):
        """Indicator should be hidden when error is None."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            ErrorIndicator,
        )

        indicator = ErrorIndicator()
        qtbot.addWidget(indicator)
        indicator.set_error({"name": "Error"})
        indicator.set_error(None)

        assert not indicator.isVisible()

    def test_empty_dict_hides_indicator(self, qtbot):
        """Indicator should be hidden for empty error dict."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            ErrorIndicator,
        )

        indicator = ErrorIndicator()
        qtbot.addWidget(indicator)
        indicator.set_error({})

        assert not indicator.isVisible()

    def test_has_error_method(self, qtbot):
        """has_error should return correct state."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            ErrorIndicator,
        )

        indicator = ErrorIndicator()
        qtbot.addWidget(indicator)

        assert not indicator.has_error()

        indicator.set_error({"name": "Error"})
        assert indicator.has_error()

        indicator.set_error(None)
        assert not indicator.has_error()

    def test_tooltip_shows_error_name(self, qtbot):
        """Tooltip should show error name."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            ErrorIndicator,
        )

        indicator = ErrorIndicator()
        qtbot.addWidget(indicator)
        indicator.set_error({"name": "FileNotFoundError"})

        assert "FileNotFoundError" in indicator.toolTip()

    def test_tooltip_shows_error_data(self, qtbot):
        """Tooltip should show error data/message."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            ErrorIndicator,
        )

        indicator = ErrorIndicator()
        qtbot.addWidget(indicator)
        indicator.set_error({"name": "Error", "data": "Something went wrong"})

        tooltip = indicator.toolTip()
        assert "Something went wrong" in tooltip

    def test_long_error_data_is_truncated(self, qtbot):
        """Long error data should be truncated in tooltip."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            ErrorIndicator,
        )

        indicator = ErrorIndicator()
        qtbot.addWidget(indicator)

        long_error = "A" * 300
        indicator.set_error({"name": "Error", "data": long_error})

        tooltip = indicator.toolTip()
        assert "..." in tooltip
        assert len(tooltip) < 300

    def test_hidden_by_default(self, qtbot):
        """Indicator should be hidden by default."""
        from opencode_status_bar.dashboard.sections.tracing.enriched_widgets import (
            ErrorIndicator,
        )

        indicator = ErrorIndicator()
        qtbot.addWidget(indicator)

        assert not indicator.isVisible()
