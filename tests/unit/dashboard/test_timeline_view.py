import pytest
from unittest.mock import MagicMock, patch
from opencode_status_bar.dashboard.sections.tracing.views.timeline import EVENT_TYPE_CONFIG


class TestEventTypeConfig:
    def test_delegation_result_in_config(self):
        assert "delegation_result" in EVENT_TYPE_CONFIG

    def test_delegation_result_has_icon(self):
        icon, _, _ = EVENT_TYPE_CONFIG["delegation_result"]
        assert icon == "📥"

    def test_delegation_result_has_color(self):
        _, color, _ = EVENT_TYPE_CONFIG["delegation_result"]
        assert color == "#10b981"

    def test_delegation_result_has_bg_key(self):
        _, _, bg_key = EVENT_TYPE_CONFIG["delegation_result"]
        assert bg_key == "tree_child_bg"

    def test_all_standard_event_types_present(self):
        required_types = [
            "user_prompt",
            "reasoning",
            "tool_call",
            "assistant_response",
            "delegation_result",
        ]
        for event_type in required_types:
            assert event_type in EVENT_TYPE_CONFIG, f"Missing {event_type}"

    def test_config_tuple_structure(self):
        for event_type, config in EVENT_TYPE_CONFIG.items():
            assert isinstance(config, tuple), f"{event_type} config should be tuple"
            assert len(config) == 3, f"{event_type} should have 3 elements"
            icon, color, bg_key = config
            assert isinstance(icon, str), f"{event_type} icon should be string"
            assert color.startswith("#"), f"{event_type} color should be hex"
            assert isinstance(bg_key, str), f"{event_type} bg_key should be string"


class TestTimelineEventContent:
    def test_delegation_result_extracts_result_summary(self):
        from opencode_status_bar.dashboard.sections.tracing.views.timeline import (
            TimelineEventWidget,
        )

        event = {
            "type": "delegation_result",
            "result_summary": "Task completed successfully",
            "child_session_id": "ses_123",
        }

        with patch.object(TimelineEventWidget, "__init__", lambda x, y: None):
            widget = TimelineEventWidget.__new__(TimelineEventWidget)
            widget._event = event

            content = widget._get_content_preview()
            assert "Task completed successfully" in content

    def test_delegation_result_truncates_long_content(self):
        from opencode_status_bar.dashboard.sections.tracing.views.timeline import (
            TimelineEventWidget,
        )

        long_summary = "A" * 200
        event = {
            "type": "delegation_result",
            "result_summary": long_summary,
        }

        with patch.object(TimelineEventWidget, "__init__", lambda x, y: None):
            widget = TimelineEventWidget.__new__(TimelineEventWidget)
            widget._event = event

            content = widget._get_content_preview()
            assert len(content) <= 83
