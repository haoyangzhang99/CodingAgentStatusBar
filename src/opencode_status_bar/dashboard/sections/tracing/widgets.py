"""
Tracing widgets - Reusable UI components for tracing section.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
    QTextEdit,
)
from PyQt6.QtCore import Qt

from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS

from .helpers import format_tokens_short


class DurationBar(QProgressBar):
    """Custom progress bar for visualizing relative duration."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(6)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS["border_default"]};
                border: none;
                border-radius: 3px;
                margin: 0 {SPACING["sm"]}px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {COLORS["accent_primary"]},
                    stop: 1 {COLORS["accent_primary_hover"]}
                );
                border-radius: 3px;
            }}
        """)


class CollapsibleTextEdit(QFrame):
    """Collapsible text section with header."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])

        # Header with expand/collapse
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["sm"])

        self._arrow = QLabel("▼")
        self._arrow.setStyleSheet(f"""
            color: {COLORS["text_muted"]};
            font-size: 10px;
        """)
        self._arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self._arrow)

        self._title = QLabel(title)
        self._title.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_medium"]};
        """)
        self._title.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self._title)
        header_layout.addStretch()

        header.mousePressEvent = lambda a0: self.toggle()  # type: ignore[method-assign]
        layout.addWidget(header)

        # Text content
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS["bg_hover"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: 8px;
                padding: {SPACING["sm"]}px;
                color: {COLORS["text_primary"]};
                font-family: "SF Mono", Menlo, monospace;
                font-size: {FONTS["size_sm"]}px;
            }}
        """)
        self._text.setMinimumHeight(100)
        self._text.setMaximumHeight(300)
        layout.addWidget(self._text)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._text.setVisible(self._expanded)
        self._arrow.setText("▼" if self._expanded else "▶")

    def set_title(self, title: str) -> None:
        """Change the section title."""
        self._title.setText(title)

    def set_text(self, text: str) -> None:
        self._text.setPlainText(text)


class HorizontalBar(QFrame):
    """Horizontal bar chart for simple value visualization."""

    def __init__(
        self,
        value: int,
        max_value: int,
        label: str = "",
        color: str = COLORS["accent_primary"],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._value = value
        self._max_value = max_value
        self._label = label
        self._color = color

        self.setMinimumHeight(28)
        self.setMaximumHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(SPACING["sm"])

        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            min-width: 80px;
        """)
        layout.addWidget(label_widget)

        # Bar container
        bar_container = QFrame()
        bar_container.setStyleSheet(f"""
            background-color: {COLORS["bg_hover"]};
            border-radius: 4px;
        """)
        bar_container.setFixedHeight(16)

        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        # Bar fill
        percentage = min(100, int((value / max_value) * 100)) if max_value > 0 else 0
        bar_fill = QFrame()
        bar_fill.setStyleSheet(f"""
            background-color: {color};
            border-radius: 4px;
        """)
        bar_fill.setFixedHeight(16)
        bar_fill.setMinimumWidth(max(2, percentage * 2))
        bar_layout.addWidget(bar_fill)
        bar_layout.addStretch()

        layout.addWidget(bar_container, stretch=1)

        # Value
        value_widget = QLabel(format_tokens_short(value))
        value_widget.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_medium"]};
            min-width: 50px;
            text-align: right;
        """)
        value_widget.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(value_widget)
