from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

from ..styles import COLORS, SPACING, FONTS


class ExpandableSection(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(
        self,
        title: str,
        expanded: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._expanded = expanded
        self._title = title
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QFrame()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.mousePressEvent = lambda _: self.toggle()
        self._header.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: none;
                padding: {SPACING["sm"]}px;
            }}
            QFrame:hover {{
                background-color: {COLORS["bg_hover"]};
            }}
        """)

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["sm"])

        self._arrow = QLabel("▼" if self._expanded else "▶")
        self._arrow.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        self._arrow.setFixedWidth(16)
        header_layout.addWidget(self._arrow)

        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addWidget(self._header)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(SPACING["xs"])
        self._content.setVisible(self._expanded)
        layout.addWidget(self._content)

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def clear(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._arrow.setText("▼" if self._expanded else "▶")
        self.toggled.emit(self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != expanded:
            self.toggle()

    def is_expanded(self) -> bool:
        return self._expanded
