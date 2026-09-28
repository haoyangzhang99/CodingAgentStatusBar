"""
Monitoring section - real-time agents and tools.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..widgets import (
    MetricCard,
    DataTable,
    PageHeader,
    EmptyState,
    StatusBadge,
    SectionCard,
    create_type_badge,
)
from ..styles import SPACING, COL_WIDTH, format_duration_ms
from .colors import get_operation_variant


class MonitoringSection(QWidget):
    """Monitoring section - real-time agents and tools."""

    # Signal emitted when user double-clicks to open terminal
    open_terminal_requested = pyqtSignal(str)  # agent_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_table_signals()

    def _connect_table_signals(self) -> None:
        """Connect double-click signals for opening terminal."""
        self._agents_table.cellDoubleClicked.connect(self._on_agents_double_click)
        self._waiting_table.cellDoubleClicked.connect(self._on_waiting_double_click)

        # Set pointing hand cursor to indicate clickable rows
        self._agents_table.setCursor(Qt.CursorShape.PointingHandCursor)
        self._waiting_table.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_agents_double_click(self, row: int, _col: int) -> None:
        """Handle double-click on agents table."""
        item = self._agents_table.item(row, 0)
        if item:
            agent_id = item.data(Qt.ItemDataRole.UserRole)
            if agent_id:
                self.open_terminal_requested.emit(agent_id)

    def _on_waiting_double_click(self, row: int, _col: int) -> None:
        """Handle double-click on waiting table."""
        item = self._waiting_table.item(row, 0)
        if item:
            agent_id = item.data(Qt.ItemDataRole.UserRole)
            if agent_id:
                self.open_terminal_requested.emit(agent_id)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        layout.setSpacing(0)

        # Header
        header = PageHeader("Monitoring", "Real-time view of active agents and tools")
        layout.addWidget(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, SPACING["md"], 0)
        content_layout.setSpacing(24)  # 24px gap between sections

        # ═══════════════════════════════════════════════════════════════════
        # Metrics Grid - Single row with 6 cards
        # ═══════════════════════════════════════════════════════════════════
        metrics_container = QWidget()
        metrics_grid = QGridLayout(metrics_container)
        metrics_grid.setContentsMargins(0, SPACING["sm"], 0, SPACING["sm"])
        metrics_grid.setHorizontalSpacing(16)  # 16px horizontal gap

        # Store metric cards for updates
        self._metric_cards: dict[str, MetricCard] = {}

        # Single row: Instances, Agents, Busy, Waiting, Idle, Todos
        self._metric_cards["instances"] = MetricCard("0", "Instances", "primary")
        self._metric_cards["agents"] = MetricCard("0", "Agents", "primary")
        self._metric_cards["busy"] = MetricCard("0", "Busy", "success")
        self._metric_cards["waiting"] = MetricCard("0", "Waiting", "warning")
        self._metric_cards["idle"] = MetricCard("0", "Idle", "muted")
        self._metric_cards["todos"] = MetricCard("0", "Todos", "warning")

        metrics_grid.addWidget(self._metric_cards["instances"], 0, 0)
        metrics_grid.addWidget(self._metric_cards["agents"], 0, 1)
        metrics_grid.addWidget(self._metric_cards["busy"], 0, 2)
        metrics_grid.addWidget(self._metric_cards["waiting"], 0, 3)
        metrics_grid.addWidget(self._metric_cards["idle"], 0, 4)
        metrics_grid.addWidget(self._metric_cards["todos"], 0, 5)

        # Add stretch to prevent cards from expanding too much
        metrics_grid.setColumnStretch(6, 1)

        content_layout.addWidget(metrics_container)

        # ═══════════════════════════════════════════════════════════════════
        # Active Agents Section (in SectionCard)
        # ═══════════════════════════════════════════════════════════════════
        agents_card = SectionCard("Active Agents", "Currently running sessions")

        self._agents_table = DataTable(
            ["Agent", "Directory", "Status", "Tools", "Todos"]
        )
        self._agents_table.setColumnWidth(0, COL_WIDTH["name_long"])  # Agent name
        self._agents_table.setColumnWidth(1, COL_WIDTH["path"])  # Directory
        self._agents_table.setColumnWidth(2, COL_WIDTH["status"])  # Status (BUSY/IDLE)
        self._agents_table.setColumnWidth(3, COL_WIDTH["number_tiny"])  # Tools count
        agents_card.add_widget(self._agents_table)

        self._agents_empty = EmptyState(
            icon="○",
            title="No active agents",
            subtitle="Start a Claude session to see it here",
        )
        self._agents_empty.hide()
        agents_card.add_widget(self._agents_empty)

        content_layout.addWidget(agents_card)

        # ═══════════════════════════════════════════════════════════════════
        # Running Tools Section (in SectionCard)
        # ═══════════════════════════════════════════════════════════════════
        tools_card = SectionCard("Running Tools", "Tools currently executing")

        self._tools_table = DataTable(["Tool", "Agent", "Arguments", "Duration"])
        self._tools_table.setColumnWidth(0, COL_WIDTH["type"])  # Tool type
        self._tools_table.setColumnWidth(1, COL_WIDTH["name_short"])  # Agent name
        self._tools_table.setColumnWidth(2, COL_WIDTH["path"])  # Arguments
        tools_card.add_widget(self._tools_table)

        self._tools_empty = EmptyState(
            icon="○",
            title="No tools currently running",
            subtitle="Tools will appear here when executing",
        )
        self._tools_empty.hide()
        tools_card.add_widget(self._tools_empty)

        content_layout.addWidget(tools_card)

        # ═══════════════════════════════════════════════════════════════════
        # Waiting for Response Section (in SectionCard)
        # ═══════════════════════════════════════════════════════════════════
        waiting_card = SectionCard(
            "Waiting for Response", "Agents waiting for user input"
        )

        self._waiting_table = DataTable(["Title", "Question", "Options", "Context"])
        self._waiting_table.setColumnWidth(0, COL_WIDTH["name_short"])  # Title
        self._waiting_table.setColumnWidth(1, COL_WIDTH["path"])  # Question (truncated)
        self._waiting_table.setColumnWidth(2, COL_WIDTH["name_short"])  # Options
        self._waiting_table.setColumnWidth(
            3, COL_WIDTH["name_short"]
        )  # Context (repo @ branch)
        waiting_card.add_widget(self._waiting_table)

        self._waiting_empty = EmptyState(
            icon="✓",
            title="No agents waiting",
            subtitle="Agents will appear here when asking for user input",
        )
        self._waiting_empty.hide()
        waiting_card.add_widget(self._waiting_empty)

        content_layout.addWidget(waiting_card)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        instances: int,
        agents: int,
        busy: int,
        waiting: int,
        idle: int,
        todos: int,
        agents_data: list[dict],
        tools_data: list[dict],
        waiting_data: list[dict] | None = None,
    ) -> None:
        """Update monitoring data."""
        self._metric_cards["instances"].set_value(str(instances))
        self._metric_cards["agents"].set_value(str(agents))
        self._metric_cards["busy"].set_value(str(busy))
        self._metric_cards["waiting"].set_value(str(waiting))
        self._metric_cards["idle"].set_value(str(idle))
        self._metric_cards["todos"].set_value(str(todos))

        # Agents table
        self._agents_table.clear_data()

        if agents_data:
            self._agents_table.show()
            self._agents_empty.hide()

            for agent in agents_data:
                status = agent.get("status", "idle")
                title = agent.get("title") or "Unknown"
                directory = agent.get("dir") or ""
                agent_id = agent.get("agent_id") or ""
                tools = agent.get("tools") or []
                todos_total = agent.get("todos_total") or 0

                # Add row with placeholder for status (will be replaced by widget)
                self._agents_table.add_row(
                    [
                        title,
                        directory,
                        "",  # Placeholder for status badge
                        str(len(tools)),
                        str(todos_total),
                    ],
                    full_values=[title, directory, "", "", ""],
                )

                # Replace status cell with StatusBadge widget
                row = self._agents_table.rowCount() - 1
                status_badge = StatusBadge(
                    "BUSY" if status == "busy" else "IDLE",
                    "success" if status == "busy" else "neutral",
                )
                self._agents_table.setCellWidget(row, 2, status_badge)
                if item := self._agents_table.item(row, 2):
                    item.setText("")

                # Store agent_id for double-click handling
                first_item = self._agents_table.item(row, 0)
                if first_item:
                    first_item.setData(Qt.ItemDataRole.UserRole, agent_id)
        else:
            self._agents_table.hide()
            self._agents_empty.show()

        # Tools table
        self._tools_table.clear_data()

        if tools_data:
            self._tools_table.show()
            self._tools_empty.hide()

            for tool in tools_data:
                duration = format_duration_ms(tool.get("elapsed_ms", 0))
                tool_name = tool.get("name", "")
                tool_variant = get_operation_variant(tool_name)
                arg = tool.get("arg", "")

                self._tools_table.add_row(
                    [
                        (tool_name.upper(), tool_variant)
                        if tool_variant
                        else tool_name,
                        tool.get("agent", ""),
                        arg,
                        duration,
                    ],
                    full_values=[
                        tool_name,
                        tool.get("agent", ""),
                        arg,
                        duration,
                    ],
                )

                # Add type badge for tool name (column 0) - clear text to avoid overlap
                row = self._tools_table.rowCount() - 1
                type_badge = create_type_badge(tool_name)
                self._tools_table.setCellWidget(row, 0, type_badge)
                if item := self._tools_table.item(row, 0):
                    item.setText("")
        else:
            self._tools_table.hide()
            self._tools_empty.show()

        # Waiting for Response table
        self._waiting_table.clear_data()

        if waiting_data:
            self._waiting_table.show()
            self._waiting_empty.hide()

            for agent in waiting_data:
                title = agent.get("title", "Unknown")
                question = agent.get("question", "")
                options = agent.get("options", "")
                context = agent.get("context", "")
                agent_id = agent.get("agent_id", "")

                # Truncate question to 80 chars for display
                question_display = (
                    question[:80] + "..." if len(question) > 80 else question
                )

                self._waiting_table.add_row(
                    [title, question_display, options, context],
                    full_values=[title, question, options, context],
                )

                # Store agent_id for double-click handling
                row = self._waiting_table.rowCount() - 1
                first_item = self._waiting_table.item(row, 0)
                if first_item:
                    first_item.setData(Qt.ItemDataRole.UserRole, agent_id)
        else:
            self._waiting_table.hide()
            self._waiting_empty.show()
