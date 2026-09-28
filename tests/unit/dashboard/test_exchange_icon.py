import pytest
from PyQt6.QtWidgets import QWidget

from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
    ExchangeGroupWidget,
)


@pytest.fixture
def widget_parent(qapp):
    parent = QWidget()
    yield parent
    parent.deleteLater()


class TestExchangeHeaderIcon:
    @pytest.mark.parametrize(
        "events,expected_icon,description",
        [
            ([{"type": "user_prompt", "content": "Hello"}], "💬", "user_prompt"),
            (
                [{"type": "delegation_result", "content": "Done"}],
                "📥",
                "delegation_result",
            ),
            (
                [
                    {
                        "type": "user_prompt",
                        "content": "Task",
                        "from_child_session": "c1",
                    }
                ],
                "🔗",
                "child_session_prompt",
            ),
            (
                [
                    {"type": "reasoning", "from_child_session": "c1"},
                    {
                        "type": "user_prompt",
                        "content": "Task",
                        "from_child_session": "c1",
                    },
                ],
                "🔗",
                "mixed_child_events",
            ),
            (
                [
                    {
                        "type": "delegation_result",
                        "content": "R",
                        "from_child_session": "c1",
                    }
                ],
                "📥",
                "delegation_result_precedence",
            ),
        ],
    )
    def test_header_icon_selection(
        self, widget_parent, events, expected_icon, description
    ):
        widget = ExchangeGroupWidget(
            exchange_number=1, events=events, parent=widget_parent
        )

        header_event = widget._find_header_event()
        if header_event:
            actual_icon = widget._get_header_icon(header_event)
            assert actual_icon == expected_icon, description

        widget.deleteLater()


class TestIsFromChildSession:
    @pytest.mark.parametrize(
        "events,expected,description",
        [
            (
                [{"type": "user_prompt"}, {"type": "reasoning"}],
                False,
                "no_child_session",
            ),
            (
                [{"type": "user_prompt", "from_child_session": "c1"}],
                True,
                "has_child_session",
            ),
            (
                [
                    {"type": "reasoning"},
                    {"type": "tool_call", "from_child_session": "c2"},
                ],
                True,
                "mixed_one_child",
            ),
            (
                [{"type": "user_prompt", "from_child_session": ""}],
                False,
                "empty_string_falsy",
            ),
            (
                [{"type": "user_prompt", "from_child_session": None}],
                False,
                "none_falsy",
            ),
        ],
    )
    def test_is_from_child_session_detection(
        self, widget_parent, events, expected, description
    ):
        widget = ExchangeGroupWidget(
            exchange_number=1, events=events, parent=widget_parent
        )

        result = widget._is_from_child_session()
        assert result == expected, description

        widget.deleteLater()
