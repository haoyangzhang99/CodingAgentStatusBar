"""
Base tab - Common functionality for all tracing tabs.

Provides:
- Standard initialization with layout
- Summary label factory
- Styled list factory
- Layout cleanup utilities
- is_loaded() / clear() interface
"""

from abc import abstractmethod

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget

from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS, RADIUS


class BaseTab(QWidget):
    """Base class for tracing detail tabs.

    Provides common initialization, styling, and interface methods.
    Subclasses must implement load_data() and may override clear().
    """

    def __init__(self, parent: QWidget | None = None, spacing: str = "md"):
        """Initialize the tab with standard layout.

        Args:
            parent: Parent widget
            spacing: Spacing key from SPACING dict (default "md")
        """
        super().__init__(parent)
        self._loaded = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, SPACING["md"], 0, 0)
        self._layout.setSpacing(SPACING.get(spacing, SPACING["md"]))

        # Optional summary label (created by _add_summary_label)
        self._summary: QLabel | None = None

    def _add_summary_label(self) -> QLabel:
        """Create and add a styled summary label.

        Returns:
            The created QLabel widget
        """
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: {SPACING["sm"]}px;
            background-color: {COLORS["bg_hover"]};
            border-radius: {RADIUS["sm"]}px;
        """)
        self._layout.addWidget(self._summary)
        return self._summary

    def _add_styled_list(self, include_hover: bool = False) -> QListWidget:
        """Create and add a styled list widget.

        Args:
            include_hover: Whether to include hover style

        Returns:
            The created QListWidget
        """
        list_widget = QListWidget()

        hover_style = ""
        if include_hover:
            hover_style = f"""
            QListWidget::item:hover {{
                background-color: {COLORS["bg_hover"]};
            }}
            """

        list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QListWidget::item {{
                padding: {SPACING["sm"]}px {SPACING["md"]}px;
                border-bottom: 1px solid {COLORS["border_subtle"]};
                color: {COLORS["text_secondary"]};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS["sidebar_active"]};
            }}
            {hover_style}
        """)
        self._layout.addWidget(list_widget)
        return list_widget

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        """Remove all widgets from a layout.

        Args:
            layout: The layout to clear
        """
        while layout.count():
            child = layout.takeAt(0)
            if child is not None:
                widget = child.widget()
                if widget is not None:
                    widget.deleteLater()

    def is_loaded(self) -> bool:
        """Check if data has been loaded.

        Returns:
            True if load_data() has been called
        """
        return self._loaded

    @abstractmethod
    def load_data(self, data) -> None:
        """Load data into the tab.

        Must be implemented by subclasses.

        Args:
            data: Data to display (type varies by tab)
        """
        pass

    def clear(self) -> None:
        """Reset the tab to empty state.

        Base implementation resets _loaded and clears summary.
        Subclasses should call super().clear() then clear their widgets.
        """
        self._loaded = False
        if self._summary is not None:
            self._summary.setText("")
