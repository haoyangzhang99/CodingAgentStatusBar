"""
Delegations tab - Hierarchical view of agent delegations.
"""

from PyQt6.QtCore import pyqtSignal

from opencode_status_bar.dashboard.sections.tracing.views import DelegationTreePanel
from .base import BaseTab


class DelegationsTab(BaseTab):
    """Tab displaying delegation tree hierarchy."""

    session_selected = pyqtSignal(str)  # Emitted when user selects a session

    def __init__(self, parent=None):
        super().__init__(parent)
        self._add_summary_label()

        # Use DelegationTreePanel component
        self._tree_panel = DelegationTreePanel()
        self._tree_panel.session_selected.connect(self._on_session_selected)
        self._layout.addWidget(self._tree_panel)

    def load_data(self, tree: dict) -> None:
        """Load delegation tree data."""
        self._loaded = True
        self._tree_panel.set_tree(tree)
        self._update_summary(tree)

    def _update_summary(self, tree: dict) -> None:
        """Update summary with delegation stats."""
        if not self._summary:
            return

        # Count nodes in tree
        def count_nodes(node: dict) -> int:
            count = 1
            for child in node.get("children", []):
                count += count_nodes(child)
            return count

        total = count_nodes(tree) if tree else 0
        depth = self._calculate_depth(tree) if tree else 0
        self._summary.setText(f"Sessions: {total}  |  Max depth: {depth}")

    def _calculate_depth(self, node: dict, current: int = 0) -> int:
        """Calculate max depth of tree."""
        if not node:
            return current
        max_depth = current
        for child in node.get("children", []):
            child_depth = self._calculate_depth(child, current + 1)
            max_depth = max(max_depth, child_depth)
        return max_depth

    def _on_session_selected(self, session_id: str) -> None:
        """Handle session selection in tree."""
        self.session_selected.emit(session_id)

    def clear(self) -> None:
        """Clear the tab."""
        super().clear()
        self._tree_panel.set_tree({})
