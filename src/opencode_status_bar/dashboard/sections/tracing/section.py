"""
TracingSection - Main tracing section widget.

Agent execution traces visualization with hierarchical view of agent delegations.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSplitter,
    QTreeView,
    QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from opencode_status_bar.dashboard.widgets import EmptyState
from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS, RADIUS

from .detail_panel import TraceDetailPanel, PanelController
from .tree_model import TracingTreeModel


class TracingSection(QWidget):
    open_terminal_requested = pyqtSignal(str)
    load_more_requested = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._session_hierarchy: list[dict] = []
        self._max_duration_ms: int = 1
        self._view_mode: str = "sessions"
        self._last_session_ids: set[str | None] = set()
        self._setup_ui()
        self._controller = PanelController(self._detail_panel)
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["sm"])

        title = QLabel("Traces")
        title.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
            padding-bottom: {SPACING["xs"]}px;
        """)
        layout.addWidget(title)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(8)
        self._splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS["border_default"]};
                margin: 4px 40px;
                border-radius: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {COLORS["accent_primary"]};
            }}
        """)

        top_panel = QWidget()
        top_panel.setMinimumHeight(200)
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        self._model = TracingTreeModel(page_size=80)
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setColumnWidth(0, 450)
        self._tree.setColumnWidth(1, 120)
        self._tree.setColumnWidth(2, 100)
        self._tree.setColumnWidth(3, 55)
        self._tree.setColumnWidth(4, 55)
        self._tree.setColumnWidth(5, 30)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(20)
        self._tree.setUniformRowHeights(True)

        palette = self._tree.palette()
        palette.setColor(palette.ColorRole.Base, QColor(COLORS["bg_surface"]))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
        self._tree.setPalette(palette)

        self._tree.setStyleSheet(f"""
            QTreeView {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
                outline: none;
            }}
            QTreeView::item {{
                padding: {SPACING["sm"]}px {SPACING["xs"]}px;
                border: none;
                min-height: 32px;
            }}
            QTreeView::item:selected {{
                background-color: {COLORS["sidebar_active"]};
                border-radius: {RADIUS["sm"]}px;
            }}
            QTreeView::item:hover:!selected {{
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
                border-top-left-radius: {RADIUS["lg"]}px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: {RADIUS["lg"]}px;
            }}
            QHeaderView::section:hover {{
                background-color: {COLORS["bg_hover"]};
                color: {COLORS["text_secondary"]};
            }}
        """)

        header = self._tree.header()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(True)
            header.setMinimumSectionSize(50)

        top_layout.addWidget(self._tree)

        self._empty = EmptyState(
            icon="◯",
            title="No traces found",
            subtitle="Traces will appear after agents are invoked via 'task' tool",
        )
        self._empty.hide()
        top_layout.addWidget(self._empty)

        self._splitter.addWidget(top_panel)

        self._detail_panel = TraceDetailPanel()
        self._detail_panel.setMinimumHeight(250)
        self._splitter.addWidget(self._detail_panel)

        self._splitter.setSizes([500, 500])

        layout.addWidget(self._splitter, stretch=1)

    def _connect_signals(self) -> None:
        self._tree.clicked.connect(self._on_index_clicked)
        self._tree.doubleClicked.connect(self._on_index_double_clicked)
        selection_model = self._tree.selectionModel()
        if selection_model:
            selection_model.currentChanged.connect(self._on_current_changed)
        self._model.fetch_more_requested.connect(self._on_fetch_more_requested)

    def _on_fetch_more_requested(self, offset: int, limit: int) -> None:
        self.load_more_requested.emit(offset, limit)

    def _on_current_changed(self, current, _previous):
        if current.isValid():
            self._on_index_clicked(current)

    def _on_index_clicked(self, index):
        if not index.isValid():
            return
        data = self._model.data(index, Qt.ItemDataRole.UserRole)
        if data:
            self._controller.handle_selection_data(data)

    def _on_index_double_clicked(self, index):
        if not index.isValid():
            return
        data = self._model.data(index, Qt.ItemDataRole.UserRole)
        if data:
            session_id = data.get("session_id", "")
            if session_id:
                self.open_terminal_requested.emit(session_id)

    def _populate_sessions_tree(self, sessions: list[dict]) -> None:
        session_ids = {s.get("session_id") for s in sessions}
        if hasattr(self, "_last_session_ids") and self._last_session_ids == session_ids:
            return
        self._last_session_ids = session_ids

        if not sessions:
            self._model.clear()
            self._tree.hide()
            self._empty.show()
            self._detail_panel.clear()
            return

        self._tree.show()
        self._empty.hide()
        self._model.set_sessions(sessions)

    def update_data(
        self,
        session_hierarchy: list[dict] | None = None,
        meta: dict | None = None,
        is_append: bool = False,
    ) -> None:
        sessions = session_hierarchy or []
        meta = meta or {}
        has_more = meta.get("has_more", True)

        if is_append:
            self._model.append_sessions(sessions)
            self._model.set_pagination_state(has_more)
        else:
            self._session_hierarchy = sessions
            self._populate_sessions_tree(sessions)
            self._model.set_pagination_state(has_more)
