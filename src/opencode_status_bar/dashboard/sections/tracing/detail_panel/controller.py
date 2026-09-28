from typing import TYPE_CHECKING, Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem

from .strategies import TreeNodeData, get_strategy_factory, is_delegation_span
from opencode_status_bar.utils.logger import error, info

if TYPE_CHECKING:
    from .panel import TraceDetailPanel


class PanelController:
    def __init__(self, panel: "TraceDetailPanel") -> None:
        self._panel = panel
        self._factory = get_strategy_factory()

    def handle_selection(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        self.handle_selection_data(data)

    def handle_selection_data(self, data: Optional[Any]) -> None:
        if not data:
            return

        node = TreeNodeData(raw=data)

        node_type = node.node_type
        if is_delegation_span(node):
            node_type = "delegation_span"

        session_id = data.get("session_id", "")
        if session_id:
            info(f"[Tracing] Session selected: {session_id[:12]}...")

        try:
            strategy = self._factory.get(node_type)
            content = strategy.get_content(node)
            self._panel.render(content)
        except Exception as e:
            error(f"[Tracing] handle_selection error: {e}")
            import traceback

            error(traceback.format_exc())
