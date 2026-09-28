"""
Sidebar navigation widgets.
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

from ..styles import COLORS, SPACING, FONTS, ICONS, UI


class NavItem(QPushButton):
    """Sidebar navigation item."""

    def __init__(
        self,
        icon: str,
        text: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(UI["nav_item_height"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], 0, SPACING["lg"], 0)
        layout.setSpacing(SPACING["md"])

        # Icon
        self._icon = QLabel(icon)
        self._icon.setFixedWidth(24)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        # Text
        self._text = QLabel(text)
        layout.addWidget(self._text)
        layout.addStretch()

        self._update_style()
        self.toggled.connect(self._update_style)

    def _update_style(self) -> None:
        """Update style based on state."""
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS["sidebar_active"]};
                    border: none;
                    border-left: 3px solid {COLORS["sidebar_active_border"]};
                    border-radius: 0;
                    text-align: left;
                }}
            """)
            self._icon.setStyleSheet(
                f"color: {COLORS['accent_primary']}; font-size: {FONTS['size_md']}px;"
            )
            self._text.setStyleSheet(f"""
                color: {COLORS["text_primary"]};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_medium"]};
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {COLORS["sidebar_hover"]};
                }}
            """)
            self._icon.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: {FONTS['size_md']}px;"
            )
            self._text.setStyleSheet(f"""
                color: {COLORS["text_secondary"]};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_normal"]};
            """)


class Sidebar(QFrame):
    """Sidebar navigation panel."""

    section_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(UI["sidebar_width"])

        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {COLORS["sidebar_bg"]};
                border-right: 1px solid {COLORS["border_default"]};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["xl"], 0, SPACING["lg"])
        layout.setSpacing(0)

        # Logo
        logo_container = QWidget()
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(SPACING["lg"], 0, SPACING["lg"], SPACING["2xl"])
        logo_layout.setSpacing(SPACING["sm"])

        logo_icon = QLabel("⬡")
        logo_icon.setStyleSheet(
            f"font-size: {FONTS['size_2xl']}px; color: {COLORS['accent_primary']};"
        )
        logo_layout.addWidget(logo_icon)

        logo_text = QLabel("OpenCode")
        logo_text.setStyleSheet(f"""
            font-size: {FONTS["size_xl"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {COLORS["text_primary"]};
            letter-spacing: -0.5px;
        """)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        layout.addWidget(logo_container)

        # Section label
        section_label = QLabel("NAVIGATION")
        section_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            padding: 0 {SPACING["lg"]}px {SPACING["sm"]}px;
            letter-spacing: 1px;
        """)
        layout.addWidget(section_label)

        # Nav items
        self._nav_items: list[NavItem] = []
        nav_data = [
            (ICONS["monitoring"], "Monitoring"),
            (ICONS["security"], "Security"),
            (ICONS["analytics"], "Analytics"),
            (ICONS["tracing"], "Traces"),
        ]

        for i, (icon, text) in enumerate(nav_data):
            item = NavItem(icon, text)
            item.clicked.connect(lambda _checked, idx=i: self._on_item_clicked(idx))
            self._nav_items.append(item)
            layout.addWidget(item)

        layout.addStretch()

        # Status
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], 0)
        status_layout.setSpacing(SPACING["sm"])

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(
            f"font-size: {FONTS['size_xxs']}px; color: {COLORS['success']};"
        )
        status_layout.addWidget(self._status_dot)

        self._status_text = QLabel("Live")
        self._status_text.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_muted"]};
        """)
        status_layout.addWidget(self._status_text)
        status_layout.addStretch()
        layout.addWidget(status_container)

        # Select first by default
        if self._nav_items:
            self._nav_items[0].setChecked(True)

    def _on_item_clicked(self, index: int) -> None:
        for i, item in enumerate(self._nav_items):
            item.setChecked(i == index)
        self.section_changed.emit(index)

    def set_status(self, active: bool, text: str = "") -> None:
        color = COLORS["success"] if active else COLORS["text_muted"]
        self._status_dot.setStyleSheet(
            f"font-size: {FONTS['size_xxs']}px; color: {color};"
        )
        if text:
            self._status_text.setText(text)
