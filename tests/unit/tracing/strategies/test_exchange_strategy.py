"""Unit tests for ExchangeStrategy."""

import pytest
from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
    TreeNodeData,
    ExchangeStrategy,
)


class TestExchangeStrategy:
    def test_handles_exchange_node_types(self):
        """ExchangeStrategy should handle exchange, user_turn, conversation."""
        assert "exchange" in ExchangeStrategy.handles()
        assert "user_turn" in ExchangeStrategy.handles()
        assert "conversation" in ExchangeStrategy.handles()

    def test_get_content_returns_tabs(self):
        """ExchangeStrategy should return content_type='tabs'."""
        data = {
            "node_type": "exchange",
            "tokens_in": 100,
            "tokens_out": 200,
            "prompt_input": "Hello",
            "prompt_output": "Hi there",
        }
        node = TreeNodeData(raw=data)
        strategy = ExchangeStrategy()
        content = strategy.get_content(node)

        assert content.get("content_type") == "tabs"
