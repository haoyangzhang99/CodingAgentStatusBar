"""
Control widgets for user interaction and layout.
"""

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..styles import COLORS, SPACING, FONTS, RADIUS, COMPONENTS


class PageHeader(QWidget):
    """Page header with title, subtitle and actions."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING["lg"])
        layout.setSpacing(SPACING["xs"])

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(SPACING["lg"])

        self._title = QLabel(title)
        self._title.setStyleSheet(f"""
            font-size: {FONTS["size_xl"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
            letter-spacing: -0.3px;
        """)
        title_row.addWidget(self._title)
        title_row.addStretch()

        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(SPACING["sm"])
        title_row.addLayout(self._actions_layout)

        layout.addLayout(title_row)

        if subtitle:
            self._subtitle = QLabel(subtitle)
            self._subtitle.setStyleSheet(f"""
                font-size: {FONTS["size_base"]}px;
                color: {COLORS["text_muted"]};
            """)
            layout.addWidget(self._subtitle)

    def add_action(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)


class SectionHeader(QWidget):
    """Section header with title and optional subtitle."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, SPACING["lg"])
        layout.setSpacing(0)

        # Left side: title and subtitle
        left_layout = QVBoxLayout()
        left_layout.setSpacing(SPACING["xs"])

        self._title = QLabel(title)
        self._title.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        left_layout.addWidget(self._title)

        if subtitle:
            self._subtitle = QLabel(subtitle)
            self._subtitle.setStyleSheet(f"""
                font-size: {FONTS["size_base"]}px;
                color: {COLORS["text_muted"]};
            """)
            left_layout.addWidget(self._subtitle)

        layout.addLayout(left_layout)
        layout.addStretch()

        # Right side: for actions
        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(SPACING["sm"])
        layout.addLayout(self._actions_layout)

    def add_action(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)


class Separator(QFrame):
    """Horizontal separator with generous margin."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"""
            background-color: {COLORS["border_subtle"]};
            margin: {SPACING["lg"]}px 0;
        """)


class SegmentedControl(QWidget):
    """Modern segmented control for period selection."""

    selection_changed = pyqtSignal(int)

    def __init__(
        self,
        options: list[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._options = options
        self._current_index = 0
        self._buttons: list[QPushButton] = []

        # Container styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS["bg_elevated"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["sm"]}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xs"], SPACING["xs"], SPACING["xs"], SPACING["xs"]
        )
        layout.setSpacing(SPACING["xs"])

        for i, option in enumerate(options):
            btn = QPushButton(option)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setMinimumHeight(COMPONENTS["button"]["height"])
            btn.setMinimumWidth(80)
            btn.clicked.connect(lambda _checked, idx=i: self._on_button_clicked(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)
            self._update_button_style(btn, i == 0)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def _on_button_clicked(self, index: int) -> None:
        if index == self._current_index:
            self._buttons[index].setChecked(True)
            return

        self._current_index = index
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
            self._update_button_style(btn, i == index)
        self.selection_changed.emit(index)

    def _update_button_style(self, btn: QPushButton, selected: bool) -> None:
        if selected:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS["accent_primary"]};
                    color: white;
                    border: none;
                    border-radius: {RADIUS["sm"] - 2}px;
                    font-size: {FONTS["size_sm"]}px;
                    font-weight: {FONTS["weight_medium"]};
                    padding: 0 {SPACING["md"]}px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS["accent_primary_hover"]};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS["text_muted"]};
                    border: none;
                    border-radius: {RADIUS["sm"] - 2}px;
                    font-size: {FONTS["size_sm"]}px;
                    font-weight: {FONTS["weight_normal"]};
                    padding: 0 {SPACING["md"]}px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS["bg_hover"]};
                    color: {COLORS["text_primary"]};
                }}
            """)

    def set_current_index(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._on_button_clicked(index)

    def current_index(self) -> int:
        return self._current_index


class ClickableLabel(QLabel):
    """A QLabel that emits a clicked signal when pressed."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


class EmptyState(QWidget):
    """Empty state placeholder with icon."""

    def __init__(
        self,
        icon: str = "○",
        title: str = "No data",
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["2xl"], SPACING["xl"], SPACING["2xl"], SPACING["xl"]
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING["sm"])

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"""
            font-size: 36px;
            color: {COLORS["text_muted"]};
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_medium"]};
            color: {COLORS["text_secondary"]};
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet(f"""
                font-size: {FONTS["size_base"]}px;
                color: {COLORS["text_muted"]};
            """)
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(subtitle_label)
