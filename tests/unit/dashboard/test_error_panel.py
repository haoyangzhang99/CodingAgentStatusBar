"""Tests for error panel components in session_overview.py"""

import pytest
from PyQt6.QtWidgets import QWidget


@pytest.fixture
def widget_parent(qapp):
    parent = QWidget()
    yield parent
    parent.deleteLater()


class TestClassifyErrorType:
    @pytest.mark.parametrize(
        "message,expected_type,expected_label",
        [
            ("Connection timeout after 30s", "timeout", "TIMEOUT"),
            ("Tool execution aborted", "timeout", "TIMEOUT"),
            ("AbortError: The operation was aborted.", "timeout", "TIMEOUT"),
            ("Request timed out", "timeout", "TIMEOUT"),
            ("Error: Request failed with status code: 401", "auth", "AUTH"),
            ("Error: Request failed with status code: 403", "auth", "AUTH"),
            ("Error: forbidden access", "auth", "AUTH"),
            ("Permission denied", "auth", "AUTH"),
            ("The user rejected permission", "auth", "AUTH"),
            ("Authentication failed", "auth", "AUTH"),
            ("Connection refused", "network", "NETWORK"),
            ("Network error occurred", "network", "NETWORK"),
            ("SSL certificate verify failed", "network", "NETWORK"),
            ("unknown certificate verification error", "network", "NETWORK"),
            ("DNS lookup failed", "network", "NETWORK"),
            ("Error: Request failed with status code: 404", "not_found", "NOT FOUND"),
            ("File not found: /path/to/file", "not_found", "NOT FOUND"),
            ("Resource not found", "not_found", "NOT FOUND"),
            ("Syntax error on line 42", "syntax", "SYNTAX"),
            ("Parse error: unexpected token", "syntax", "SYNTAX"),
            ("Error: Rate limit exceeded", "rate_limit", "RATE LIMIT"),
            ("Error: Request failed with status code: 429", "rate_limit", "RATE LIMIT"),
            ("Too many requests", "rate_limit", "RATE LIMIT"),
            ("Unknown error occurred", "unknown", "ERROR"),
            ("Something went wrong", "unknown", "ERROR"),
            ("", "unknown", "ERROR"),
        ],
    )
    def test_returns_correct_type_and_label(
        self, message, expected_type, expected_label
    ):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            classify_error_type,
            COLORS,
        )

        error_type, color, label = classify_error_type(message)

        assert error_type == expected_type
        assert label == expected_label
        assert color in COLORS.values(), f"Color {color} not in design system"

    def test_is_case_insensitive(self):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            classify_error_type,
        )

        results = [
            classify_error_type("TIMEOUT ERROR")[0],
            classify_error_type("timeout error")[0],
            classify_error_type("TimeOut Error")[0],
        ]

        assert all(r == "timeout" for r in results)


class TestErrorInfo:
    @pytest.mark.parametrize(
        "timestamp,tool_name,message",
        [
            ("2025-01-10T10:30:00", "bash", "Tool execution aborted"),
            ("2025-01-10T10:30:00", "webfetch", "Error: " + "x" * 500),
            ("", "edit", ""),
        ],
    )
    def test_stores_all_fields_without_modification(
        self, timestamp, tool_name, message
    ):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorInfo,
        )

        error = ErrorInfo(timestamp=timestamp, tool_name=tool_name, message=message)

        assert error.timestamp == timestamp
        assert error.tool_name == tool_name
        assert error.message == message
        assert len(error.message) == len(message)


class TestErrorItemWidget:
    def test_initializes_collapsed(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorItemWidget,
            ErrorInfo,
        )

        error = ErrorInfo("2025-01-10T10:30:00", "bash", "Tool execution aborted")
        widget = ErrorItemWidget(error, prefix="├─", parent=widget_parent)

        assert widget._error is error
        assert widget._prefix == "├─"
        assert widget._is_expanded is False
        assert widget._full_message.isHidden() is True
        assert widget._arrow.text() == "▶"

    def test_toggle_expand_shows_full_message(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorItemWidget,
            ErrorInfo,
        )

        full_msg = 'Error: The user has specified a rule [{"permission":"*"}]'
        error = ErrorInfo("2025-01-10T10:30:00", "todowrite", full_msg)
        widget = ErrorItemWidget(error, prefix="└─", parent=widget_parent)

        widget._toggle_expand()

        assert widget._is_expanded is True
        assert widget._full_message.isHidden() is False
        assert widget._arrow.text() == "▼"
        assert widget._full_message.text() == full_msg

    def test_double_toggle_returns_to_collapsed(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorItemWidget,
            ErrorInfo,
        )

        widget = ErrorItemWidget(
            ErrorInfo("2025-01-10T10:30:00", "bash", "Error"),
            prefix="─",
            parent=widget_parent,
        )

        widget._toggle_expand()
        widget._toggle_expand()

        assert widget._is_expanded is False
        assert widget._full_message.isHidden() is True
        assert widget._arrow.text() == "▶"


class TestErrorsWidget:
    def test_initializes_empty_and_collapsed(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)

        assert widget._is_expanded is False
        assert widget._errors == []
        assert widget._scroll.isHidden() is True
        assert widget._container_layout.count() == 0

    def test_load_errors_populates_container(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
            ErrorItemWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)
        errors = [
            ErrorInfo("2025-01-10T10:30:00", "bash", "Error 1"),
            ErrorInfo("2025-01-10T10:31:00", "webfetch", "Error 2"),
        ]

        widget.load_errors(errors)

        assert widget._errors is errors
        assert widget._container_layout.count() == 3  # 2 errors + stretch
        first_item = widget._container_layout.itemAt(0).widget()
        assert isinstance(first_item, ErrorItemWidget)
        assert first_item._error is errors[0]

    def test_load_empty_list_hides_widget(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)
        widget.load_errors([])

        assert widget._errors == []
        assert widget._container_layout.count() == 0
        assert widget.isHidden() is True

    def test_toggle_without_errors_stays_collapsed(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)
        widget._toggle_expand()

        assert widget._is_expanded is False

    def test_toggle_with_errors_expands_scroll(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
        )

        widget = ErrorsWidget(parent=widget_parent)
        widget.load_errors([ErrorInfo("2025-01-10T10:30:00", "bash", "Error")])

        widget._toggle_expand()

        assert widget._is_expanded is True
        assert widget._scroll.isHidden() is False
        assert widget._arrow.text() == "▼"

    def test_reload_clears_previous_items(self, qapp, widget_parent):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
        )

        widget = ErrorsWidget(parent=widget_parent)
        widget.load_errors(
            [
                ErrorInfo("2025-01-10T10:30:00", "bash", "Error 1"),
                ErrorInfo("2025-01-10T10:31:00", "bash", "Error 2"),
            ]
        )
        initial_count = widget._container_layout.count()

        widget.load_errors([ErrorInfo("2025-01-10T10:32:00", "bash", "Error 3")])

        assert widget._container_layout.count() < initial_count
        assert widget._container_layout.count() == 2  # 1 error + stretch

    @pytest.mark.parametrize(
        "error_count,expected_prefixes",
        [
            (1, ["└─"]),
            (2, ["├─", "└─"]),
            (3, ["├─", "├─", "└─"]),
        ],
    )
    def test_assigns_correct_tree_prefixes(
        self, qapp, widget_parent, error_count, expected_prefixes
    ):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
            ErrorItemWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)
        errors = [
            ErrorInfo(f"2025-01-10T10:3{i}:00", "bash", f"Error {i}")
            for i in range(error_count)
        ]

        widget.load_errors(errors)

        for i, expected_prefix in enumerate(expected_prefixes):
            item_widget = widget._container_layout.itemAt(i).widget()
            assert isinstance(item_widget, ErrorItemWidget)
            assert item_widget._prefix == expected_prefix


class TestExtractFromNode:
    @pytest.mark.parametrize(
        "error_value,display_info,expected_message",
        [
            ("Tool execution aborted", None, "Tool execution aborted"),
            (None, "https://example.com", "https://example.com"),
            ("", "", "bash failed"),
            (None, None, "bash failed"),
        ],
    )
    def test_extracts_tool_error_with_fallback_chain(
        self, error_value, display_info, expected_message
    ):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "tool",
            "tool_name": "bash",
            "tool_status": "error",
            "error": error_value,
            "display_info": display_info,
            "created_at": "2025-01-10T10:30:00",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 1
        assert data.errors[0].tool_name == "bash"
        assert data.errors[0].message == expected_message
        assert data.errors[0].timestamp == "2025-01-10T10:30:00"

    def test_extracts_non_tool_error(self):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "delegation",
            "status": "error",
            "subagent_type": "oracle",
            "error": "Agent crashed",
            "created_at": "2025-01-10T10:30:00",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 1
        assert data.errors[0].tool_name == "oracle"
        assert data.errors[0].message == "Agent crashed"

    def test_extracts_errors_recursively_from_children(self):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "user_turn",
            "children": [
                {
                    "node_type": "tool",
                    "tool_name": "bash",
                    "tool_status": "error",
                    "error": "Error 1",
                    "created_at": "2025-01-10T10:30:00",
                    "children": [],
                },
                {
                    "node_type": "tool",
                    "tool_name": "read",
                    "tool_status": "success",
                    "children": [],
                },
                {
                    "node_type": "tool",
                    "tool_name": "webfetch",
                    "tool_status": "error",
                    "error": "Error 2",
                    "created_at": "2025-01-10T10:31:00",
                    "children": [],
                },
            ],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 2
        assert [e.tool_name for e in data.errors] == ["bash", "webfetch"]

    def test_ignores_successful_tools(self):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "tool",
            "tool_name": "bash",
            "tool_status": "success",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 0

    def test_preserves_full_message_without_truncation(self):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        long_error = "Error: " + "x" * 500

        node = {
            "node_type": "tool",
            "tool_name": "bash",
            "tool_status": "error",
            "error": long_error,
            "created_at": "2025-01-10T10:30:00",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert data.errors[0].message == long_error
        assert len(data.errors[0].message) == 507
