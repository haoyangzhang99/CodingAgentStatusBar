import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeView, QLabel

from opencode_status_bar.dashboard.widgets import EmptyState
from opencode_status_bar.dashboard.sections.tracing import TracingSection
from opencode_status_bar.dashboard.sections.tracing.detail_panel import TraceDetailPanel

from ..conftest import SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group(name="qt_tracing"),
]


class TestTracingSectionStructure:
    def test_tracing_section_structure(self, dashboard_window, qtbot, click_nav):
        assert isinstance(dashboard_window._tracing, TracingSection)
        tracing = dashboard_window._tracing

        assert isinstance(tracing._tree, QTreeView)
        assert tracing._model.columnCount() == 6

        assert isinstance(tracing._detail_panel, TraceDetailPanel)
        assert isinstance(tracing._empty, EmptyState)

        click_nav(dashboard_window, SECTION_TRACING)
        assert dashboard_window._pages.currentIndex() == SECTION_TRACING


class TestTracingEmptyState:
    def test_empty_state_displays_with_correct_message(
        self, dashboard_window, qtbot, click_nav
    ):
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        empty_data = {"session_hierarchy": []}
        dashboard_window._signals.tracing_updated.emit(empty_data)
        qtbot.waitUntil(lambda: tracing._tree.isHidden(), timeout=3000)

        assert not tracing._empty.isHidden()
        assert tracing._empty.isVisible()

        labels = tracing._empty.findChildren(QLabel)
        label_texts = [label.text() for label in labels]

        assert "No traces found" in label_texts
        assert any("task" in text.lower() for text in label_texts)


class TestTracingSessionList:
    def test_tracing_section_shows_session_list_with_data(
        self, dashboard_window, qtbot, click_nav
    ):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: not tracing._tree.isHidden(), timeout=3000)
        assert tracing._empty.isHidden()

        assert tracing._model.rowCount() == 1

    def test_session_tree_shows_hierarchy(self, dashboard_window, qtbot, click_nav):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() == 1, timeout=3000)

        root_index = tracing._model.index(0, 0)
        root_text = tracing._model.data(root_index, Qt.ItemDataRole.DisplayRole)
        assert root_text == "🌳 my-project: Implement feature X"

        expected_child_count = 2
        qtbot.waitUntil(
            lambda: tracing._model.rowCount(root_index) == expected_child_count,
            timeout=3000,
        )

        child0_index = tracing._model.index(0, 0, root_index)
        child1_index = tracing._model.index(1, 0, root_index)
        child0_text = tracing._model.data(child0_index, Qt.ItemDataRole.DisplayRole)
        child1_text = tracing._model.data(child1_index, Qt.ItemDataRole.DisplayRole)

        assert child0_text == "└─ user → executor"
        assert child1_text == "└─ executor → tester"


class TestSessionOverviewPanelTokens:
    def test_session_overview_panel_displays_tokens(
        self, dashboard_window, qtbot, click_nav
    ):
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_test_tokens",
                    "title": "Test Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 120,
                    "tokens": {
                        "input": 175,
                        "output": 4747,
                        "cache_read": 658693,
                        "cache_write": 61035,
                        "total": 724650,
                    },
                    "children": [],
                }
            ]
        }

        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=3000)

        root_index = tracing._model.index(0, 0)
        tracing._tree.setCurrentIndex(root_index)
        tracing._on_index_clicked(root_index)
        qtbot.waitUntil(
            lambda: hasattr(tracing._detail_panel._session_overview, "_tokens"),
            timeout=1000,
        )

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview

        assert hasattr(overview_panel, "_tokens")

        tokens_widget = overview_panel._tokens
        assert tokens_widget.isVisible() or not tokens_widget.isHidden()

        labels = tokens_widget.findChildren(QLabel)
        label_texts = [label.text() for label in labels]

        assert any("Input" in text for text in label_texts)
        assert any("Output" in text for text in label_texts)
        assert any("Cache Read" in text for text in label_texts)
        assert any("Cache Write" in text for text in label_texts)
        assert any("Total" in text for text in label_texts)

    def test_session_overview_panel_displays_agents(
        self, dashboard_window, qtbot, click_nav
    ):
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_test_agents",
                    "title": "Test Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 120,
                    "tokens": {"input": 100, "output": 200, "total": 300},
                    "children": [
                        {
                            "node_type": "user_turn",
                            "agent": "build",
                            "prompt_input": "Build the project",
                            "children": [],
                        },
                        {
                            "node_type": "user_turn",
                            "agent": "build",
                            "prompt_input": "Build again",
                            "children": [],
                        },
                        {
                            "node_type": "user_turn",
                            "agent": "build",
                            "prompt_input": "Final build",
                            "children": [],
                        },
                    ],
                }
            ]
        }

        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=3000)

        root_index = tracing._model.index(0, 0)
        tracing._tree.setCurrentIndex(root_index)
        tracing._on_index_clicked(root_index)
        qtbot.waitUntil(
            lambda: hasattr(tracing._detail_panel._session_overview, "_agents"),
            timeout=1000,
        )

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        agents_widget = overview_panel._agents

        assert agents_widget.isVisible() or not agents_widget.isHidden()

        header_text = agents_widget._header.text()
        assert "Agents" in header_text
        assert "(3)" in header_text

    def test_session_overview_panel_displays_tools(
        self, dashboard_window, qtbot, click_nav
    ):
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_test_tools",
                    "title": "Test Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 120,
                    "tokens": {"input": 100, "output": 200, "total": 300},
                    "children": [
                        *[
                            {
                                "node_type": "tool",
                                "tool_name": "mcp_bash",
                                "display_info": f"bash command {i}",
                                "status": "success",
                            }
                            for i in range(7)
                        ],
                        *[
                            {
                                "node_type": "tool",
                                "tool_name": "mcp_webfetch",
                                "display_info": f"fetch url {i}",
                                "status": "success",
                            }
                            for i in range(3)
                        ],
                    ],
                }
            ]
        }

        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=3000)

        root_index = tracing._model.index(0, 0)
        tracing._tree.setCurrentIndex(root_index)
        tracing._on_index_clicked(root_index)
        qtbot.waitUntil(
            lambda: hasattr(tracing._detail_panel._session_overview, "_tools"),
            timeout=1000,
        )

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        tools_widget = overview_panel._tools

        assert tools_widget.isVisible() or not tools_widget.isHidden()

        header_text = tools_widget._header.text()
        assert "Tools" in header_text
        assert "(10)" in header_text

        labels = tools_widget.findChildren(QLabel)
        label_texts = [label.text() for label in labels]

        assert any("bash" in text and "7" in text for text in label_texts)
        assert any("webfetch" in text and "3" in text for text in label_texts)

    def test_session_overview_panel_displays_timeline(
        self, dashboard_window, qtbot, click_nav
    ):
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_test_timeline",
                    "title": "Test Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 120,
                    "tokens": {"input": 100, "output": 200, "total": 300},
                    "children": [
                        {
                            "node_type": "user_turn",
                            "prompt_input": "Fix the auth bug",
                            "started_at": "2024-01-10T10:30:00Z",
                            "agent": "dev",
                            "children": [],
                        },
                        {
                            "node_type": "user_turn",
                            "prompt_input": "Now update the tests",
                            "started_at": "2024-01-10T10:32:00Z",
                            "agent": "tester",
                            "children": [],
                        },
                        {
                            "node_type": "user_turn",
                            "prompt_input": "Run the full test suite",
                            "started_at": "2024-01-10T10:35:00Z",
                            "agent": "tester",
                            "children": [],
                        },
                    ],
                }
            ]
        }

        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=3000)

        root_index = tracing._model.index(0, 0)
        tracing._tree.setCurrentIndex(root_index)
        tracing._on_index_clicked(root_index)
        qtbot.waitUntil(
            lambda: hasattr(tracing._detail_panel._session_overview, "_timeline"),
            timeout=1000,
        )

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        timeline_widget = overview_panel._timeline

        assert timeline_widget.isVisible() or not timeline_widget.isHidden()

        exchange_widgets = timeline_widget._exchange_widgets
        assert len(exchange_widgets) == 2

        all_prompts = []
        for widget in exchange_widgets:
            for event in widget._events:
                if event.get("type") == "user_prompt":
                    all_prompts.append(event.get("content", ""))

        assert any("refactor" in p.lower() for p in all_prompts)
        assert any("implement" in p.lower() for p in all_prompts)
