"""Unit tests for DelegationSpanStrategy and is_delegation_span."""

import pytest
from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
    TreeNodeData,
)
from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies.delegation import (
    DelegationSpanStrategy,
    is_delegation_span,
)


class TestDelegationSpanStrategy:
    def test_handles_delegation_span_type(self):
        assert "delegation_span" in DelegationSpanStrategy.handles()

    def test_get_content_returns_delegation_transcript_type(self):
        data = {
            "node_type": "agent",
            "child_session_id": "sess-child-001",
            "subagent_type": "explore",
            "status": "completed",
            "duration_ms": 5000,
        }
        node = TreeNodeData(raw=data)
        strategy = DelegationSpanStrategy()
        content = strategy.get_content(node)

        assert content.get("content_type") == "delegation_transcript"

    def test_get_content_includes_delegation_data(self):
        data = {
            "node_type": "agent",
            "child_session_id": "sess-child-002",
            "subagent_type": "librarian",
            "status": "completed",
            "duration_ms": 12000,
            "title": "Research API docs",
        }
        node = TreeNodeData(raw=data)
        strategy = DelegationSpanStrategy()
        content = strategy.get_content(node)

        delegation_data = content.get("delegation_data")
        assert delegation_data is not None
        assert delegation_data["child_session_id"] == "sess-child-002"
        assert delegation_data["subagent_type"] == "librarian"
        assert delegation_data["status"] == "completed"
        assert delegation_data["duration_ms"] == 12000

    def test_get_content_breadcrumb_includes_agent_type(self):
        data = {
            "node_type": "agent",
            "child_session_id": "sess-001",
            "subagent_type": "oracle",
        }
        node = TreeNodeData(raw=data)
        strategy = DelegationSpanStrategy()
        content = strategy.get_content(node)

        breadcrumb = content.get("breadcrumb")
        assert "🤖 Delegation" in breadcrumb
        assert "→ oracle" in breadcrumb

    def test_extract_subagent_type_from_arguments_json(self):
        data = {
            "node_type": "tool",
            "tool_name": "task",
            "child_session_id": "sess-001",
            "arguments": '{"subagent_type": "frontend-ui-ux-engineer", "prompt": "Fix styling"}',
        }
        node = TreeNodeData(raw=data)
        strategy = DelegationSpanStrategy()
        content = strategy.get_content(node)

        assert content["delegation_data"]["subagent_type"] == "frontend-ui-ux-engineer"

    def test_extract_subagent_type_from_input_dict(self):
        data = {
            "node_type": "tool",
            "tool_name": "task",
            "child_session_id": "sess-001",
            "input": {"subagent_type": "document-writer"},
        }
        node = TreeNodeData(raw=data)
        strategy = DelegationSpanStrategy()
        content = strategy.get_content(node)

        assert content["delegation_data"]["subagent_type"] == "document-writer"

    def test_extract_subagent_type_from_display_info(self):
        data = {
            "node_type": "tool",
            "tool_name": "task",
            "child_session_id": "sess-001",
            "display_info": "task → explore",
        }
        node = TreeNodeData(raw=data)
        strategy = DelegationSpanStrategy()
        content = strategy.get_content(node)

        assert content["delegation_data"]["subagent_type"] == "explore"


class TestIsDelegationSpan:
    def test_agent_node_with_child_session_is_delegation(self):
        data = {
            "node_type": "agent",
            "child_session_id": "sess-child-001",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is True

    def test_agent_node_without_child_session_is_not_delegation(self):
        data = {
            "node_type": "agent",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is False

    def test_tool_task_with_child_session_is_delegation(self):
        data = {
            "node_type": "tool",
            "tool_name": "task",
            "child_session_id": "sess-child-002",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is True

    def test_tool_task_without_child_session_is_not_delegation(self):
        data = {
            "node_type": "tool",
            "tool_name": "task",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is False

    def test_tool_non_task_is_not_delegation(self):
        data = {
            "node_type": "tool",
            "tool_name": "mcp_read",
            "child_session_id": "sess-001",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is False

    def test_part_task_with_child_session_is_delegation(self):
        data = {
            "node_type": "part",
            "tool_name": "task",
            "child_session_id": "sess-child-003",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is True

    def test_exchange_node_is_not_delegation(self):
        data = {
            "node_type": "exchange",
            "child_session_id": "sess-001",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is False

    def test_session_node_is_not_delegation(self):
        data = {
            "node_type": "session",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is False

    def test_empty_child_session_id_is_not_delegation(self):
        data = {
            "node_type": "agent",
            "child_session_id": "",
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is False

    def test_none_child_session_id_is_not_delegation(self):
        data = {
            "node_type": "agent",
            "child_session_id": None,
        }
        node = TreeNodeData(raw=data)

        assert is_delegation_span(node) is False
