"""
Table widgets for data display.
"""

from PyQt6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from ..styles import COLORS, FONTS, RADIUS, SPACING, UI


class DataTable(QTableWidget):
    """Enhanced data table with better styling."""

    ROW_HEIGHT = UI["row_height"]
    HEADER_HEIGHT = UI["header_height"]

    def __init__(
        self,
        headers: list[str],
        parent=None,
    ):
        super().__init__(parent)

        self._original_headers = headers.copy()
        self._current_sort_column = -1
        self._current_sort_order = Qt.SortOrder.AscendingOrder

        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.setSortingEnabled(True)

        # Alternating row colors - IMPROVED CONTRAST
        palette = self.palette()
        palette.setColor(palette.ColorRole.Base, QColor(COLORS["bg_surface"]))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
        self.setPalette(palette)

        # Styling - ADDED CUSTOM STYLESHEET
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QTableWidget::item {{
                padding: {SPACING["sm"]}px;
                color: {COLORS["text_secondary"]};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS["bg_active"]};
                color: {COLORS["text_primary"]};
            }}
            QHeaderView::section {{
                background-color: {COLORS["bg_elevated"]};
                color: {COLORS["text_secondary"]};
                border: none;
                border-bottom: 1px solid {COLORS["border_default"]};
                padding: {SPACING["sm"]}px;
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_bold"]};
                text-transform: uppercase;
                letter-spacing: {FONTS["tracking_wide"]}px;
            }}
        """)

        # Hide row numbers
        v_header = self.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(self.ROW_HEIGHT)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        header = self.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setDefaultSectionSize(150)
            header.setMinimumSectionSize(80)
            header.setFixedHeight(self.HEADER_HEIGHT)
            header.setSortIndicatorShown(False)
            header.sortIndicatorChanged.connect(self._on_sort_changed)

        self.setFixedHeight(self.HEADER_HEIGHT + 2)

    def _on_sort_changed(self, column: int, order: Qt.SortOrder) -> None:
        for i, text in enumerate(self._original_headers):
            item = self.horizontalHeaderItem(i)
            if item:
                item.setText(text)

        if 0 <= column < len(self._original_headers):
            arrow = " ↑" if order == Qt.SortOrder.AscendingOrder else " ↓"
            item = self.horizontalHeaderItem(column)
            if item:
                item.setText(f"{self._original_headers[column]}{arrow}")

        self._current_sort_column = column
        self._current_sort_order = order

    def add_row(
        self,
        data: list[str | tuple[str, str]],
        full_values: list[str] | None = None,
    ) -> None:
        # Disable sorting while adding rows to prevent data corruption
        self.setSortingEnabled(False)

        row = self.rowCount()
        self.insertRow(row)

        for col, item_data in enumerate(data):
            if isinstance(item_data, tuple):
                value, variant = item_data
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Color mapping for variants
                color_map = {
                    # Status colors
                    "status-busy": COLORS["success"],
                    "status-idle": COLORS["text_muted"],
                    # Risk levels
                    "risk-critical": COLORS["risk_critical"],
                    "risk-high": COLORS["risk_high"],
                    "risk-medium": COLORS["risk_medium"],
                    "risk-low": COLORS["risk_low"],
                    # Operation types
                    "type-command": COLORS["type_command"],
                    "type-bash": COLORS["type_bash"],
                    "type-read": COLORS["type_read"],
                    "type-write": COLORS["type_write"],
                    "type-edit": COLORS["type_edit"],
                    "type-webfetch": COLORS["type_webfetch"],
                    "type-glob": COLORS["type_glob"],
                    "type-grep": COLORS["type_grep"],
                }
                if variant in color_map:
                    item.setForeground(QColor(color_map[variant]))
                    font = item.font()
                    font.setWeight(QFont.Weight.DemiBold)
                    item.setFont(font)
            else:
                value = item_data
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor(COLORS["text_secondary"]))

            # Tooltip
            if full_values and col < len(full_values):
                tooltip = full_values[col]
            else:
                tooltip = (
                    value
                    if isinstance(item_data, str)
                    else item_data[0]
                    if isinstance(item_data, tuple)
                    else ""
                )
            if tooltip and len(tooltip) > 30:
                item.setToolTip(tooltip)

            self.setItem(row, col, item)

        self._update_height()

        # Re-enable sorting after adding row
        self.setSortingEnabled(True)

    def clear_data(self) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)
        self._update_height()
        self.setSortingEnabled(True)

    def _update_height(self) -> None:
        row_count = self.rowCount()
        header = self.horizontalHeader()
        header_height = header.height() if header else self.HEADER_HEIGHT
        content_height = row_count * self.ROW_HEIGHT
        self.setFixedHeight(header_height + content_height + 2)
