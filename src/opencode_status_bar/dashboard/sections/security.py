"""
Security section - risk analysis.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QGridLayout,
)
from PyQt6.QtCore import Qt

from ..widgets import (
    MetricCard,
    DataTable,
    PageHeader,
    EmptyState,
    SectionCard,
    create_risk_badge,
    create_type_badge,
    create_score_badge,
)
from ..styles import SPACING, COL_WIDTH, UI
from .colors import get_operation_variant


class SecuritySection(QWidget):
    """Security section - risk analysis."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        layout.setSpacing(0)

        header = PageHeader("Security", "Risk analysis of executed operations")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, SPACING["md"], 0)
        content_layout.setSpacing(24)  # 24px gap between sections

        # ═══════════════════════════════════════════════════════════════════
        # Metrics Grid - Single row with 5 cards
        # ═══════════════════════════════════════════════════════════════════
        metrics_container = QWidget()
        metrics_grid = QGridLayout(metrics_container)
        metrics_grid.setContentsMargins(0, SPACING["sm"], 0, SPACING["sm"])
        metrics_grid.setHorizontalSpacing(16)  # 16px horizontal gap

        # Store metric cards for updates
        self._metric_cards: dict[str, MetricCard] = {}

        # Single row: Analyzed, Critical, High, Medium, Low
        self._metric_cards["total"] = MetricCard("0", "Analyzed", "primary")
        self._metric_cards["critical"] = MetricCard("0", "Critical", "error")
        self._metric_cards["high"] = MetricCard("0", "High", "warning")
        self._metric_cards["medium"] = MetricCard("0", "Medium", "warning")
        self._metric_cards["low"] = MetricCard("0", "Low", "success")

        metrics_grid.addWidget(self._metric_cards["total"], 0, 0)
        metrics_grid.addWidget(self._metric_cards["critical"], 0, 1)
        metrics_grid.addWidget(self._metric_cards["high"], 0, 2)
        metrics_grid.addWidget(self._metric_cards["medium"], 0, 3)
        metrics_grid.addWidget(self._metric_cards["low"], 0, 4)

        # Add stretch to prevent cards from expanding too much
        metrics_grid.setColumnStretch(5, 1)

        content_layout.addWidget(metrics_container)

        # ═══════════════════════════════════════════════════════════════════
        # Critical Alerts Section (in SectionCard)
        # ═══════════════════════════════════════════════════════════════════
        self._critical_card = SectionCard(
            "Critical Alerts", "High-risk operations requiring attention"
        )

        self._critical_table = DataTable(["Type", "Details", "Risk", "Reason"])
        self._critical_table.setColumnWidth(0, COL_WIDTH["type"])  # Operation type
        self._critical_table.setColumnWidth(1, COL_WIDTH["path"])  # Details/path
        self._critical_table.setColumnWidth(2, COL_WIDTH["risk"])  # Risk level
        self._critical_card.add_widget(self._critical_table)

        self._critical_empty = EmptyState(
            icon="✓",
            title="No critical alerts",
            subtitle="All operations within normal risk levels",
        )
        self._critical_empty.hide()
        self._critical_card.add_widget(self._critical_empty)

        content_layout.addWidget(self._critical_card)

        # ═══════════════════════════════════════════════════════════════════
        # Recent Commands Section (in SectionCard)
        # ═══════════════════════════════════════════════════════════════════
        self._commands_card = SectionCard(
            "Recent Commands", "Last analyzed shell commands"
        )

        self._commands_table = DataTable(["Command", "Risk", "Score", "Reason"])
        self._commands_table.setColumnWidth(0, COL_WIDTH["path"])  # Command (long text)
        self._commands_table.setColumnWidth(1, COL_WIDTH["risk"])  # Risk level
        self._commands_table.setColumnWidth(2, 80)  # Score
        self._commands_card.add_widget(self._commands_table)

        content_layout.addWidget(self._commands_card)

        # ═══════════════════════════════════════════════════════════════════
        # File Operations Section (in SectionCard)
        # ═══════════════════════════════════════════════════════════════════
        self._files_card = SectionCard(
            "File Operations", "Recent file reads and writes"
        )

        self._files_table = DataTable(["Operation", "Path", "Risk", "Score"])
        self._files_table.setColumnWidth(0, COL_WIDTH["type"])  # Operation type
        self._files_table.setColumnWidth(1, COL_WIDTH["path"])  # File path
        self._files_table.setColumnWidth(2, COL_WIDTH["risk"])  # Risk level
        self._files_table.setColumnWidth(3, COL_WIDTH["number_tiny"])  # Score
        self._files_card.add_widget(self._files_table)

        content_layout.addWidget(self._files_card)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        stats: dict,
        commands: list[dict],
        files: list[dict],
        critical_items: list[dict] | None = None,
    ) -> None:
        """Update security data."""
        self._metric_cards["total"].set_value(str(stats.get("total_scanned", 0)))
        self._metric_cards["critical"].set_value(str(stats.get("critical", 0)))
        self._metric_cards["high"].set_value(str(stats.get("high", 0)))
        self._metric_cards["medium"].set_value(str(stats.get("medium", 0)))
        self._metric_cards["low"].set_value(str(stats.get("low", 0)))

        # Critical alerts
        self._critical_table.clear_data()

        if critical_items:
            sorted_items = sorted(
                critical_items, key=lambda x: x.get("score", 0), reverse=True
            )

            if sorted_items:
                self._critical_table.show()
                self._critical_empty.hide()

                for item in sorted_items[: UI["table_row_limit"]]:
                    risk = item.get("risk", "low").lower()
                    risk_class = f"risk-{risk}"
                    details = item.get("details", "")
                    reason = item.get("reason", "")
                    item_type = item.get("type", "")
                    type_variant = get_operation_variant(item_type)

                    self._critical_table.add_row(
                        [
                            (item_type.upper(), type_variant)
                            if type_variant
                            else item_type.upper(),
                            details,
                            (risk.upper(), risk_class),
                            reason,
                        ],
                        full_values=[
                            item_type.upper(),
                            details,
                            risk.upper(),
                            reason,
                        ],
                    )

                    # Add badges for critical alerts (clear text first to avoid overlap)
                    row = self._critical_table.rowCount() - 1
                    # Type badge (column 0)
                    type_badge = create_type_badge(item_type)
                    self._critical_table.setCellWidget(row, 0, type_badge)
                    if (table_item := self._critical_table.item(row, 0)) is not None:
                        table_item.setText("")
                    # Risk badge (column 2)
                    risk_badge = create_risk_badge(risk)
                    self._critical_table.setCellWidget(row, 2, risk_badge)
                    if (table_item := self._critical_table.item(row, 2)) is not None:
                        table_item.setText("")
            else:
                self._critical_table.hide()
                self._critical_empty.show()
        else:
            self._critical_table.hide()
            self._critical_empty.show()

        # Commands
        self._commands_table.clear_data()
        for cmd in commands[: UI["table_row_limit"]]:
            risk = cmd.get("risk", "low").lower()
            risk_class = f"risk-{risk}"
            command = cmd.get("command", "")
            reason = cmd.get("reason", "")

            self._commands_table.add_row(
                [
                    command,
                    (risk.upper(), risk_class),
                    str(cmd.get("score", 0)),
                    reason,
                ],
                full_values=[command, risk.upper(), str(cmd.get("score", 0)), reason],
            )

            # Add badges for commands (clear text first to avoid overlap)
            row = self._commands_table.rowCount() - 1
            # Risk badge (column 1)
            risk_badge = create_risk_badge(risk)
            self._commands_table.setCellWidget(row, 1, risk_badge)
            if (table_item := self._commands_table.item(row, 1)) is not None:
                table_item.setText("")
            # Score badge (column 2)
            score_val = cmd.get("score", 0)
            score_badge = create_score_badge(score_val)
            self._commands_table.setCellWidget(row, 2, score_badge)
            if (table_item := self._commands_table.item(row, 2)) is not None:
                table_item.setText("")

        # Files
        self._files_table.clear_data()
        for f in files[: UI["table_row_limit"]]:
            risk = f.get("risk", "low").lower()
            risk_class = f"risk-{risk}"
            path = f.get("path", "")
            operation = f.get("operation", "")
            op_variant = get_operation_variant(operation)

            self._files_table.add_row(
                [
                    (operation.upper(), op_variant)
                    if op_variant
                    else operation.upper(),
                    path,
                    (risk.upper(), risk_class),
                    str(f.get("score", 0)),
                ],
                full_values=[
                    operation.upper(),
                    path,
                    risk.upper(),
                    str(f.get("score", 0)),
                ],
            )

            # Add badges for files (clear text first to avoid overlap)
            row = self._files_table.rowCount() - 1
            # Type badge (column 0)
            type_badge = create_type_badge(operation)
            self._files_table.setCellWidget(row, 0, type_badge)
            if (table_item := self._files_table.item(row, 0)) is not None:
                table_item.setText("")
            # Risk badge (column 2)
            risk_badge = create_risk_badge(risk)
            self._files_table.setCellWidget(row, 2, risk_badge)
            if (table_item := self._files_table.item(row, 2)) is not None:
                table_item.setText("")
            # Score badge (column 3)
            score_val = f.get("score", 0)
            score_badge = create_score_badge(score_val)
            self._files_table.setCellWidget(row, 3, score_badge)
            if (table_item := self._files_table.item(row, 3)) is not None:
                table_item.setText("")
