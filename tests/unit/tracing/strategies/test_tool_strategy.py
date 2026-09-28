"""Unit tests for ToolStrategy."""

import pytest
from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
    TreeNodeData,
    ToolStrategy,
)


class TestToolStrategy:
    def test_handles_tool_node_type(self):
        """ToolStrategy should handle 'tool' and 'part' node types."""
        assert "tool" in ToolStrategy.handles()
        assert "part" in ToolStrategy.handles()

    def test_get_content_returns_tabs(self):
        """ToolStrategy should return content_type='tabs'."""
        data = {
            "node_type": "tool",
            "tool_name": "mcp_read",
            "display_info": "src/main.py",
            "status": "completed",
        }
        node = TreeNodeData(raw=data)
        content = ToolStrategy().get_content(node)

        assert content.get("content_type") == "tabs"
