from typing import Any, Optional

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt, pyqtSignal

from .tree_formatters import get_display_text, get_foreground_color, get_tooltip


class TreeNode:
    def __init__(self, data: dict, parent: Optional["TreeNode"] = None):
        self.data = data
        self.parent = parent
        self.children: list[TreeNode] = []

    def add_child(self, child: "TreeNode") -> None:
        child.parent = self
        self.children.append(child)

    def child(self, row: int) -> Optional["TreeNode"]:
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def child_count(self) -> int:
        return len(self.children)

    def row(self) -> int:
        if self.parent:
            return self.parent.children.index(self)
        return 0

    def get_data(self, column: int, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.UserRole:
            return self.data
        if role == Qt.ItemDataRole.DisplayRole:
            return get_display_text(self.data, column)
        if role == Qt.ItemDataRole.ForegroundRole:
            return get_foreground_color(self.data, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return get_tooltip(self.data, column)
        return None


class TracingTreeModel(QAbstractItemModel):
    fetch_more_requested = pyqtSignal(int, int)

    def __init__(self, parent=None, page_size: int = 80):
        super().__init__(parent)
        self._root = TreeNode({"node_type": "root"})
        self._column_count = 6
        self._headers = ["Name", "Time", "Duration", "In", "Out", ""]
        self._page_size = page_size
        self._has_more = False
        self._is_fetching = False
        self._total_loaded = 0

    def clear(self) -> None:
        self.beginResetModel()
        self._root = TreeNode({"node_type": "root"})
        self._has_more = False
        self._is_fetching = False
        self._total_loaded = 0
        self.endResetModel()

    def set_sessions(self, sessions: list[dict]) -> None:
        self.beginResetModel()
        self._root = TreeNode({"node_type": "root"})
        self._total_loaded = 0

        for session_data in sessions:
            root_data = {**session_data, "_is_tree_root": True}
            self._build_session_node(self._root, root_data)

        self._total_loaded = len(sessions)
        self.endResetModel()

    def append_sessions(self, sessions: list[dict]) -> int:
        if not sessions:
            return 0

        parent_index = QModelIndex()
        first_new_row = self._root.child_count()
        last_new_row = first_new_row + len(sessions) - 1

        self.beginInsertRows(parent_index, first_new_row, last_new_row)

        for session_data in sessions:
            root_data = {**session_data, "_is_tree_root": True}
            self._build_session_node(self._root, root_data)

        self.endInsertRows()
        self._total_loaded += len(sessions)

        return len(sessions)

    def set_pagination_state(self, has_more: bool) -> None:
        self._has_more = has_more
        self._is_fetching = False

    def _build_session_node(self, parent: TreeNode, session_data: dict) -> TreeNode:
        node = TreeNode(session_data, parent)
        parent.add_child(node)

        children = session_data.get("children", [])
        for child_data in children:
            child_type = child_data.get("node_type", "")

            if child_type in ("user_turn", "conversation", "exchange"):
                exchange_node = TreeNode(child_data, node)
                node.add_child(exchange_node)

                if "parts" in child_data:
                    for part_data in child_data["parts"]:
                        part_node = TreeNode(part_data, exchange_node)
                        exchange_node.add_child(part_node)
                elif "assistant" in child_data:
                    assistant = child_data.get("assistant", {})
                    for part_data in assistant.get("parts", []):
                        part_node = TreeNode(part_data, exchange_node)
                        exchange_node.add_child(part_node)

                for nested in child_data.get("children", []):
                    nested_type = nested.get("node_type", "")
                    if nested_type in ("agent", "delegation"):
                        self._build_session_node(exchange_node, nested)
                    elif nested_type in ("part", "tool"):
                        nested_node = TreeNode(nested, exchange_node)
                        exchange_node.add_child(nested_node)

            elif child_type in ("agent", "delegation"):
                self._build_session_node(node, child_data)

            elif child_type in ("part", "tool"):
                part_node = TreeNode(child_data, node)
                node.add_child(part_node)

        return node

    # =========================================================================
    # QAbstractItemModel Interface
    # =========================================================================

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_node = self._root
        else:
            parent_node = parent.internalPointer()

        child_node = parent_node.child(row)
        if child_node:
            return self.createIndex(row, column, child_node)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        child_node = index.internalPointer()
        parent_node = child_node.parent

        if parent_node == self._root or parent_node is None:
            return QModelIndex()

        return self.createIndex(parent_node.row(), 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_node = self._root
        else:
            parent_node = parent.internalPointer()

        return parent_node.child_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._column_count

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        node = index.internalPointer()
        return node.get_data(index.column(), role)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # =========================================================================
    # Lazy Loading - Qt Native canFetchMore/fetchMore
    # =========================================================================

    def canFetchMore(self, parent: QModelIndex) -> bool:
        if parent.isValid():
            return False
        return self._has_more and not self._is_fetching

    def fetchMore(self, parent: QModelIndex) -> None:
        if parent.isValid():
            return
        if not self._has_more or self._is_fetching:
            return

        self._is_fetching = True
        self.fetch_more_requested.emit(self._total_loaded, self._page_size)
