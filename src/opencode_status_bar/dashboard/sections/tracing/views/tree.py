"""
Delegation tree view component.

Displays the delegation hierarchy as an expandable tree, showing
how agents delegate tasks to sub-agents.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
    QVBoxLayout,
    QLabel,
    QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS, RADIUS

from ..helpers import format_duration, format_tokens_short


# Agent icons based on type
AGENT_ICONS = {
    "dev": "",
    "coder": "",
    "architect": "",
    "tester": "",
    "researcher": "",
    "reviewer": "",
    "planner": "",
    "pm": "",
    "designer": "",
    "default": "",
}


class DelegationTreeView(QTreeWidget):
    """Displays delegation hierarchy as expandable tree.

    Shows the parent-child relationships between sessions,
    with metrics for each node (duration, tokens, status).
    """

    session_selected = pyqtSignal(str)  # session_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tree_data: Optional[dict] = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Setup the tree widget UI."""
        # Configure columns: Agent | Duration | Tokens | Status
        self.setHeaderLabels(["Agent / Session", "Duration", "Tokens", "Status"])
        self.setColumnCount(4)

        # Column widths
        self.setColumnWidth(0, 280)
        self.setColumnWidth(1, 80)
        self.setColumnWidth(2, 80)
        self.setColumnWidth(3, 70)

        # Tree behavior
        self.setRootIsDecorated(True)
        self.setAnimated(True)
        self.setIndentation(24)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)

        # Palette for alternating colors
        palette = self.palette()
        palette.setColor(palette.ColorRole.Base, QColor(COLORS["bg_surface"]))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
        self.setPalette(palette)

        # Styling
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: {SPACING["sm"]}px {SPACING["xs"]}px;
                border: none;
                min-height: 32px;
            }}
            QTreeWidget::item:selected {{
                background-color: {COLORS["sidebar_active"]};
                border-radius: {RADIUS["sm"]}px;
            }}
            QTreeWidget::item:hover:!selected {{
                background-color: {COLORS["bg_hover"]};
            }}
            QHeaderView {{
                background-color: transparent;
            }}
            QHeaderView::section {{
                background-color: {COLORS["bg_elevated"]};
                color: {COLORS["text_muted"]};
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: {SPACING["sm"]}px {SPACING["md"]}px;
                border: none;
                border-bottom: 1px solid {COLORS["border_default"]};
            }}
            QHeaderView::section:first {{
                border-top-left-radius: {RADIUS["md"]}px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: {RADIUS["md"]}px;
            }}
        """)

        # Header configuration
        header = self.header()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(True)
            header.setMinimumSectionSize(50)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle item click."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            session_id = data.get("session_id")
            if session_id:
                self.session_selected.emit(session_id)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle item double-click (expand/collapse)."""
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def set_tree(self, tree: dict) -> None:
        """Set delegation tree data and render.

        Args:
            tree: Tree structure from /api/session/{id}/delegations
                  Expected format:
                  {
                      "session_id": "ses_root",
                      "agent": "dev",
                      "children": [...]
                  }
        """
        self._tree_data = tree
        self.clear()

        if not tree:
            return

        # Add root node
        root_item = self._create_tree_item(None, tree, is_root=True)
        self.addTopLevelItem(root_item)

        # Expand root by default
        root_item.setExpanded(True)

    def _create_tree_item(
        self,
        parent: Optional[QTreeWidgetItem],
        node: dict,
        is_root: bool = False,
    ) -> QTreeWidgetItem:
        """Create a tree widget item for a delegation node.

        Args:
            parent: Parent item (None for top-level)
            node: Node data dictionary
            is_root: Whether this is the root node

        Returns:
            Configured QTreeWidgetItem
        """
        if parent:
            item = QTreeWidgetItem(parent)
        else:
            item = QTreeWidgetItem()

        # Get node data
        session_id = node.get("session_id", "")
        agent = node.get("agent", "agent")
        duration_ms = node.get("duration_ms", 0)
        status = node.get("status", "completed")
        tokens_in = node.get("tokens_in", 0)
        tokens_out = node.get("tokens_out", 0)
        children = node.get("children", [])

        # Column 0: Agent name with icon
        icon = AGENT_ICONS.get(agent, AGENT_ICONS["default"])
        if is_root:
            label = f" {agent}"  # Tree icon for root
            item.setForeground(0, QColor(COLORS["tree_root"]))
        else:
            label = f"{icon} {agent}"
            item.setForeground(0, QColor(COLORS["tree_child"]))

        # Add child count indicator
        if children:
            label += f" ({len(children)})"

        item.setText(0, label)

        # Column 1: Duration
        if duration_ms:
            item.setText(1, format_duration(duration_ms))
        else:
            item.setText(1, "-")
        item.setForeground(1, QColor(COLORS["text_muted"]))

        # Column 2: Tokens
        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        if total_tokens:
            item.setText(2, format_tokens_short(total_tokens))
        else:
            item.setText(2, "-")
        item.setForeground(2, QColor(COLORS["text_muted"]))

        # Column 3: Status
        status_display = self._get_status_display(status)
        item.setText(3, status_display["text"])
        item.setForeground(3, QColor(status_display["color"]))

        # Store data for click handling
        item.setData(0, Qt.ItemDataRole.UserRole, node)

        # Tooltip with session ID
        if session_id:
            item.setToolTip(0, f"Session: {session_id}")

        # Add children recursively
        for child in children:
            self._add_node(item, child)

        return item

    def _add_node(self, parent: QTreeWidgetItem, node: dict) -> None:
        """Recursively add tree nodes.

        Args:
            parent: Parent tree widget item
            node: Child node data dictionary
        """
        self._create_tree_item(parent, node, is_root=False)
        # Children are added recursively in _create_tree_item

    def _get_status_display(self, status: str) -> dict:
        """Get status display text and color.

        Args:
            status: Status string (completed, error, running, etc.)

        Returns:
            Dict with 'text' and 'color' keys
        """
        status_map = {
            "completed": {"text": "", "color": COLORS["success"]},
            "success": {"text": "", "color": COLORS["success"]},
            "error": {"text": "", "color": COLORS["error"]},
            "failed": {"text": "", "color": COLORS["error"]},
            "running": {"text": "", "color": COLORS["warning"]},
            "pending": {"text": "", "color": COLORS["text_muted"]},
        }
        return status_map.get(status, {"text": "", "color": COLORS["text_muted"]})

    def expand_all(self) -> None:
        """Expand all tree nodes."""
        self.expandAll()

    def collapse_all(self) -> None:
        """Collapse all tree nodes except root."""
        self.collapseAll()
        # Keep root expanded
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item:
                item.setExpanded(True)

    def get_selected_session_id(self) -> Optional[str]:
        """Get the session ID of the currently selected item.

        Returns:
            Session ID string or None if nothing selected
        """
        items = self.selectedItems()
        if not items:
            return None
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if data:
            return data.get("session_id")
        return None


class DelegationTreePanel(QWidget):
    """Panel wrapper for DelegationTreeView with header and summary.

    Provides a complete panel with header, summary stats, and the tree view.
    """

    session_selected = pyqtSignal(str)  # session_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])

        # Header
        header = QLabel(" Delegation Tree")
        header.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
            padding: {SPACING["sm"]}px;
        """)
        layout.addWidget(header)

        # Summary
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: 0 {SPACING["sm"]}px {SPACING["sm"]}px {SPACING["sm"]}px;
        """)
        layout.addWidget(self._summary)

        # Tree view
        self._tree = DelegationTreeView()
        self._tree.session_selected.connect(self.session_selected.emit)
        layout.addWidget(self._tree, stretch=1)

    def set_tree(self, tree: dict) -> None:
        """Set tree data and update summary.

        Args:
            tree: Delegation tree from API
        """
        self._tree.set_tree(tree)

        # Update summary
        if not tree:
            self._summary.setText("No delegations")
            return

        # Count nodes and max depth
        node_count, max_depth = self._count_nodes(tree)
        agents = self._collect_agents(tree)

        summary_parts = []
        if node_count > 1:
            summary_parts.append(f"{node_count} sessions")
        if max_depth > 0:
            summary_parts.append(f"depth {max_depth}")
        if agents:
            summary_parts.append(f"agents: {', '.join(sorted(agents)[:5])}")

        self._summary.setText("  |  ".join(summary_parts) if summary_parts else "")

    def _count_nodes(self, node: dict, depth: int = 0) -> tuple[int, int]:
        """Count total nodes and max depth in tree.

        Args:
            node: Tree node
            depth: Current depth

        Returns:
            Tuple of (node_count, max_depth)
        """
        count = 1
        max_d = depth
        for child in node.get("children", []):
            child_count, child_depth = self._count_nodes(child, depth + 1)
            count += child_count
            max_d = max(max_d, child_depth)
        return count, max_d

    def _collect_agents(self, node: dict) -> set[str]:
        """Collect unique agent names from tree.

        Args:
            node: Tree node

        Returns:
            Set of agent names
        """
        agents = set()
        agent = node.get("agent")
        if agent:
            agents.add(agent)
        for child in node.get("children", []):
            agents.update(self._collect_agents(child))
        return agents

    def clear(self) -> None:
        """Clear the tree view."""
        self._tree.clear()
        self._summary.setText("")
