"""
Files tab - File operations with risk indicators.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QFrame, QGridLayout, QVBoxLayout
from PyQt6.QtCore import Qt

from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from .base import BaseTab


class FilesTab(BaseTab):
    """Tab displaying file operations with risk indicators."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Summary label
        self._add_summary_label()

        # Operations breakdown
        self._operations_container = QWidget()
        ops_layout = QGridLayout(self._operations_container)
        ops_layout.setContentsMargins(0, SPACING["sm"], 0, 0)
        ops_layout.setSpacing(SPACING["md"])

        # Create operation cards
        self._reads_card = self._create_op_card("📖 Reads", "0", COLORS["type_read"])
        self._writes_card = self._create_op_card("✏️ Writes", "0", COLORS["type_write"])
        self._edits_card = self._create_op_card("📝 Edits", "0", COLORS["type_edit"])
        self._risk_card = self._create_op_card("⚠️ High Risk", "0", COLORS["error"])

        ops_layout.addWidget(self._reads_card, 0, 0)
        ops_layout.addWidget(self._writes_card, 0, 1)
        ops_layout.addWidget(self._edits_card, 1, 0)
        ops_layout.addWidget(self._risk_card, 1, 1)

        self._layout.addWidget(self._operations_container)
        self._layout.addStretch()

    def _create_op_card(self, label: str, value: str, color: str) -> QFrame:
        """Create a small operation card."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_hover"]};
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["md"]}px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        card_layout.setSpacing(SPACING["xs"])

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"""
            font-size: {FONTS["size_xl"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {color};
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(value_label)

        text_label = QLabel(label)
        text_label.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_muted"]};
        """)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(text_label)

        return card

    def _update_card_value(self, card: QFrame, value: str) -> None:
        """Update the value in an operation card."""
        value_label = card.findChild(QLabel, "value")
        if value_label:
            value_label.setText(value)

    def load_data(self, data: dict) -> None:
        """Load files data from TracingDataService response."""
        self._loaded = True

        summary = data.get("summary", {})

        reads = summary.get("total_reads", 0)
        writes = summary.get("total_writes", 0)
        edits = summary.get("total_edits", 0)
        high_risk = summary.get("high_risk_count", 0)

        if self._summary:
            self._summary.setText(
                f"Total operations: {reads + writes + edits}  •  High risk: {high_risk}"
            )

        self._update_card_value(self._reads_card, str(reads))
        self._update_card_value(self._writes_card, str(writes))
        self._update_card_value(self._edits_card, str(edits))
        self._update_card_value(self._risk_card, str(high_risk))

    def clear(self) -> None:
        super().clear()
        self._update_card_value(self._reads_card, "0")
        self._update_card_value(self._writes_card, "0")
        self._update_card_value(self._edits_card, "0")
        self._update_card_value(self._risk_card, "0")
