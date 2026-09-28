"""Unit tests for TextContentStrategy."""

import pytest
from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
    TreeNodeData,
    TextContentStrategy,
)


class TestTextContentStrategy:
    def test_handles_returns_empty_list(self):
        """TextContentStrategy is the fallback, handles() returns empty list."""
        handles = TextContentStrategy.handles()
        assert handles == []

    def test_get_content_returns_tabs(self):
        """TextContentStrategy should return content_type='tabs'."""
        data = {
            "node_type": "unknown_type",
            "prompt_output": "Some text content",
        }
        node = TreeNodeData(raw=data)
        content = TextContentStrategy().get_content(node)

        assert content.get("content_type") == "tabs"

    def test_get_content_with_prompt_output(self):
        """Transcript should contain the prompt_output in assistant_content."""
        data = {
            "node_type": "unknown",
            "prompt_output": "This is assistant reasoning",
        }
        node = TreeNodeData(raw=data)
        content = TextContentStrategy().get_content(node)

        transcript = content.get("transcript", {})
        assert transcript.get("assistant_content") == "This is assistant reasoning"
