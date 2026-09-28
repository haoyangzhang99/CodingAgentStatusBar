import pytest
from PyQt6.QtCore import Qt, QModelIndex

from opencode_status_bar.dashboard.sections.tracing.tree_model import (
    TreeNode,
    TracingTreeModel,
)


class TestTreeNode:
    def test_init_stores_data(self):
        data = {"node_type": "session", "title": "Test"}
        node = TreeNode(data)
        assert node.data == data
        assert node.parent is None
        assert node.children == []

    def test_add_child(self):
        parent = TreeNode({"node_type": "session"})
        child = TreeNode({"node_type": "user_turn"})
        parent.add_child(child)
        assert child in parent.children
        assert child.parent == parent

    def test_child_returns_correct_child(self):
        parent = TreeNode({"node_type": "session"})
        child1 = TreeNode({"node_type": "user_turn"})
        child2 = TreeNode({"node_type": "agent"})
        parent.add_child(child1)
        parent.add_child(child2)
        assert parent.child(0) == child1
        assert parent.child(1) == child2

    def test_child_returns_none_for_invalid_row(self):
        parent = TreeNode({"node_type": "session"})
        assert parent.child(-1) is None
        assert parent.child(0) is None
        assert parent.child(100) is None

    def test_child_count(self):
        parent = TreeNode({"node_type": "session"})
        assert parent.child_count() == 0
        parent.add_child(TreeNode({"node_type": "user_turn"}))
        assert parent.child_count() == 1
        parent.add_child(TreeNode({"node_type": "agent"}))
        assert parent.child_count() == 2

    def test_row_returns_index_in_parent(self):
        parent = TreeNode({"node_type": "session"})
        child1 = TreeNode({"node_type": "user_turn"})
        child2 = TreeNode({"node_type": "agent"})
        parent.add_child(child1)
        parent.add_child(child2)
        assert child1.row() == 0
        assert child2.row() == 1

    def test_row_returns_zero_for_root(self):
        root = TreeNode({"node_type": "session"})
        assert root.row() == 0

    def test_get_data_user_role_returns_raw_data(self):
        data = {"node_type": "session", "session_id": "abc123"}
        node = TreeNode(data)
        result = node.get_data(0, Qt.ItemDataRole.UserRole)
        assert result == data

    def test_get_data_display_role_returns_formatted_text(self):
        data = {"node_type": "session", "directory": "/test/project"}
        node = TreeNode(data)
        result = node.get_data(0, Qt.ItemDataRole.DisplayRole)
        assert result == "🌳 project"

    def test_get_data_display_role_session_with_title(self):
        data = {"node_type": "session", "directory": "/test/myapp", "title": "Fix bug"}
        node = TreeNode(data)
        result = node.get_data(0, Qt.ItemDataRole.DisplayRole)
        assert result == "🌳 myapp: Fix bug"

    def test_get_data_foreground_role_returns_qcolor(self):
        from PyQt6.QtGui import QColor

        data = {"node_type": "session"}
        node = TreeNode(data)
        result = node.get_data(0, Qt.ItemDataRole.ForegroundRole)
        assert isinstance(result, QColor)

    def test_get_data_tooltip_role_returns_none_for_session(self):
        data = {"node_type": "session"}
        node = TreeNode(data)
        result = node.get_data(0, Qt.ItemDataRole.ToolTipRole)
        assert result is None

    def test_get_data_unknown_role_returns_none(self):
        data = {"node_type": "session"}
        node = TreeNode(data)
        result = node.get_data(0, Qt.ItemDataRole.DecorationRole)
        assert result is None


class TestTracingTreeModel:
    def test_init_creates_empty_root(self):
        model = TracingTreeModel()
        assert model.rowCount() == 0
        assert model.columnCount() == 6

    def test_clear_resets_model(self):
        model = TracingTreeModel()
        model.set_sessions([{"node_type": "session", "children": []}])
        assert model.rowCount() == 1
        model.clear()
        assert model.rowCount() == 0

    def test_set_sessions_adds_root_flag(self):
        model = TracingTreeModel()
        sessions = [{"node_type": "session", "session_id": "s1", "children": []}]
        model.set_sessions(sessions)

        index = model.index(0, 0)
        data = model.data(index, Qt.ItemDataRole.UserRole)
        assert data.get("_is_tree_root") is True

    def test_set_sessions_builds_hierarchy(self):
        model = TracingTreeModel()
        sessions = [
            {
                "node_type": "session",
                "session_id": "s1",
                "children": [
                    {"node_type": "user_turn", "prompt_input": "Hello"},
                    {"node_type": "user_turn", "prompt_input": "World"},
                ],
            }
        ]
        model.set_sessions(sessions)

        assert model.rowCount() == 1
        session_index = model.index(0, 0)
        assert model.rowCount(session_index) == 2

    def test_index_creates_valid_index(self):
        model = TracingTreeModel()
        model.set_sessions([{"node_type": "session", "children": []}])

        index = model.index(0, 0)
        assert index.isValid()
        assert index.row() == 0
        assert index.column() == 0

    def test_index_returns_invalid_for_out_of_bounds(self):
        model = TracingTreeModel()
        model.set_sessions([{"node_type": "session", "children": []}])

        index = model.index(10, 0)
        assert not index.isValid()

    def test_parent_returns_invalid_for_root_items(self):
        model = TracingTreeModel()
        model.set_sessions([{"node_type": "session", "children": []}])

        session_index = model.index(0, 0)
        parent_index = model.parent(session_index)
        assert not parent_index.isValid()

    def test_parent_returns_valid_for_children(self):
        model = TracingTreeModel()
        model.set_sessions(
            [
                {
                    "node_type": "session",
                    "children": [{"node_type": "user_turn"}],
                }
            ]
        )

        session_index = model.index(0, 0)
        child_index = model.index(0, 0, session_index)
        parent_index = model.parent(child_index)

        assert parent_index.isValid()
        assert parent_index.row() == 0

    def test_data_returns_none_for_invalid_index(self):
        model = TracingTreeModel()
        result = model.data(QModelIndex(), Qt.ItemDataRole.DisplayRole)
        assert result is None

    def test_header_data_returns_column_names(self):
        model = TracingTreeModel()
        assert model.headerData(0, Qt.Orientation.Horizontal) == "Name"
        assert model.headerData(1, Qt.Orientation.Horizontal) == "Time"
        assert model.headerData(2, Qt.Orientation.Horizontal) == "Duration"
        assert model.headerData(3, Qt.Orientation.Horizontal) == "In"
        assert model.headerData(4, Qt.Orientation.Horizontal) == "Out"

    def test_flags_returns_selectable_enabled(self):
        model = TracingTreeModel()
        model.set_sessions([{"node_type": "session", "children": []}])

        index = model.index(0, 0)
        flags = model.flags(index)

        assert flags & Qt.ItemFlag.ItemIsEnabled
        assert flags & Qt.ItemFlag.ItemIsSelectable

    def test_builds_tool_children_from_parts(self):
        model = TracingTreeModel()
        model.set_sessions(
            [
                {
                    "node_type": "session",
                    "children": [
                        {
                            "node_type": "user_turn",
                            "parts": [
                                {"node_type": "tool", "tool_name": "bash"},
                            ],
                        },
                    ],
                }
            ]
        )

        session_index = model.index(0, 0)
        exchange_index = model.index(0, 0, session_index)
        tool_index = model.index(0, 0, exchange_index)

        data = model.data(tool_index, Qt.ItemDataRole.UserRole)
        assert data is not None
        assert data.get("tool_name") == "bash"

    def test_builds_agent_delegation_recursively(self):
        model = TracingTreeModel()
        model.set_sessions(
            [
                {
                    "node_type": "session",
                    "children": [
                        {
                            "node_type": "agent",
                            "subagent_type": "oracle",
                            "children": [
                                {"node_type": "user_turn"},
                            ],
                        },
                    ],
                }
            ]
        )

        session_index = model.index(0, 0)
        agent_index = model.index(0, 0, session_index)

        data = model.data(agent_index, Qt.ItemDataRole.UserRole)
        assert data.get("subagent_type") == "oracle"
        assert model.rowCount(agent_index) == 1

    def test_append_sessions_returns_count(self):
        model = TracingTreeModel()
        model.set_sessions(
            [{"node_type": "session", "session_id": "s1", "children": []}]
        )

        count = model.append_sessions(
            [
                {"node_type": "session", "session_id": "s2", "children": []},
                {"node_type": "session", "session_id": "s3", "children": []},
            ]
        )

        assert count == 2

    def test_append_sessions_adds_to_existing(self):
        model = TracingTreeModel()
        model.set_sessions(
            [{"node_type": "session", "session_id": "s1", "children": []}]
        )
        assert model.rowCount() == 1

        model.append_sessions(
            [
                {"node_type": "session", "session_id": "s2", "children": []},
            ]
        )

        assert model.rowCount() == 2

    def test_append_sessions_empty_list_returns_zero(self):
        model = TracingTreeModel()
        model.set_sessions(
            [{"node_type": "session", "session_id": "s1", "children": []}]
        )

        count = model.append_sessions([])

        assert count == 0
        assert model.rowCount() == 1

    def test_append_sessions_adds_root_flag(self):
        model = TracingTreeModel()
        model.set_sessions([])

        model.append_sessions(
            [{"node_type": "session", "session_id": "s1", "children": []}]
        )

        index = model.index(0, 0)
        data = model.data(index, Qt.ItemDataRole.UserRole)
        assert data.get("_is_tree_root") is True

    def test_append_sessions_preserves_existing_sessions(self):
        model = TracingTreeModel()
        model.set_sessions(
            [
                {"node_type": "session", "session_id": "first", "children": []},
            ]
        )

        model.append_sessions(
            [
                {"node_type": "session", "session_id": "second", "children": []},
            ]
        )

        first_index = model.index(0, 0)
        second_index = model.index(1, 0)

        first_data = model.data(first_index, Qt.ItemDataRole.UserRole)
        second_data = model.data(second_index, Qt.ItemDataRole.UserRole)

        assert first_data.get("session_id") == "first"
        assert second_data.get("session_id") == "second"
