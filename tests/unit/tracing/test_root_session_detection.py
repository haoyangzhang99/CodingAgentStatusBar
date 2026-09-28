"""
Unit tests for root session detection consistency.

Tests verify that:
- Root session detection is consistent across all components
- SessionOverviewPanel is displayed for root sessions (not tabs)
- Child sessions show tabs (not overview)
"""

import pytest


class TestRootSessionDetection:
    """Test that root session detection is consistent across components."""

    def test_true_root_session_is_detected_as_root(self):
        """A true root session (parent_agent=None, agent_type=user) should be root."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
            TreeNodeData,
            get_strategy_factory,
        )

        # True root session: no parent, agent_type can be "user" or None
        root_session_data = {
            "node_type": "session",
            "session_id": "ses_123",
            "parent_agent": None,
            "agent_type": "user",  # Root sessions have agent_type="user" or None
            "directory": "/path/to/project",
            "title": "Test session",
            "children": [],
            "duration_ms": 1000,
            "tokens_in": 100,
            "tokens_out": 200,
        }

        node = TreeNodeData(raw=root_session_data)

        # Verify is_root is True
        assert node.is_root, (
            f"Expected is_root=True for root session, got is_root={node.is_root}"
        )

        # Verify strategy returns overview content type
        factory = get_strategy_factory()
        strategy = factory.get(node.node_type)
        content = strategy.get_content(node)

        content_type = content.get("content_type")
        assert content_type == "overview", (
            f"Expected 'overview' for root session, got '{content_type}'"
        )

    def test_child_session_with_parent_user_is_not_root(self):
        """A child session with parent_agent='user' but agent_type set should NOT be root.

        This is the BUG case: sessions delegated by user to an agent.
        They have parent_agent='user' but should show tabs, not overview.
        """
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
            TreeNodeData,
            get_strategy_factory,
        )

        # Child session: delegated by user to executor
        child_session_data = {
            "node_type": "delegation",
            "session_id": "ses_child_001",
            "parent_agent": "user",  # Delegated by user
            "agent_type": "executor",  # But has an agent_type!
            "directory": "/path/to/project",
            "title": "Execute task",
            "children": [],
            "duration_ms": 500,
            "tokens_in": 50,
            "tokens_out": 100,
        }

        node = TreeNodeData(raw=child_session_data)

        # This should NOT be considered root - it's a delegation
        # The BUG: current code considers this root because parent_agent="user"
        assert not node.is_root, (
            f"Expected is_root=False for child session with agent_type='executor', "
            f"got is_root={node.is_root}. "
            f"BUG: parent_agent='user' should not make this a root session."
        )

        # Strategy should return tabs content type (not overview)
        factory = get_strategy_factory()
        strategy = factory.get(node.node_type)
        content = strategy.get_content(node)

        content_type = content.get("content_type")
        assert content_type == "tabs", (
            f"Expected 'tabs' for child session, got '{content_type}'"
        )

    def test_true_delegation_between_agents_is_not_root(self):
        """A delegation from one agent to another should NOT be root."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
            TreeNodeData,
            get_strategy_factory,
        )

        # Delegation: executor → tester
        delegation_data = {
            "node_type": "agent",
            "session_id": "ses_grandchild_001",
            "parent_agent": "executor",
            "agent_type": "tester",
            "directory": "/path/to/project",
            "title": "Run tests",
            "children": [],
            "duration_ms": 300,
            "tokens_in": 30,
            "tokens_out": 60,
        }

        node = TreeNodeData(raw=delegation_data)

        assert not node.is_root, f"Expected is_root=False for delegation between agents"

        factory = get_strategy_factory()
        strategy = factory.get(node.node_type)
        content = strategy.get_content(node)

        content_type = content.get("content_type")
        assert content_type == "tabs", (
            f"Expected 'tabs' for delegation, got '{content_type}'"
        )

    def test_root_session_without_agent_type_is_root(self):
        """A session with no agent_type and no parent_agent is definitely root."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
            TreeNodeData,
            get_strategy_factory,
        )

        root_data = {
            "node_type": "session",
            "session_id": "ses_123",
            "parent_agent": None,
            "agent_type": None,
            "directory": "/path/to/project",
            "title": "Test session",
            "children": [],
            "duration_ms": 1000,
            "tokens_in": 100,
            "tokens_out": 200,
        }

        node = TreeNodeData(raw=root_data)

        assert node.is_root

        factory = get_strategy_factory()
        strategy = factory.get(node.node_type)
        content = strategy.get_content(node)

        assert content.get("content_type") == "overview"

    def test_is_tree_root_flag_takes_priority_over_heuristic(self):
        """Le flag _is_tree_root doit prendre priorité sur l'heuristique agent_type/parent_agent."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies import (
            TreeNodeData,
        )

        # Cas : flag _is_tree_root=True mais heuristique dirait False
        data = {
            "node_type": "session",
            "_is_tree_root": True,
            "parent_agent": "executor",  # Normalement = NOT root
            "agent_type": "tester",  # Normalement = NOT root
        }
        node = TreeNodeData(raw=data)
        assert node.is_root, "Flag _is_tree_root should take priority"
