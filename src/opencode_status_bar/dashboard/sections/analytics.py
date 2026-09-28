"""
Analytics section - usage statistics.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..widgets import (
    MetricsRow,
    DataTable,
    SectionHeader,
    Separator,
    PageHeader,
    EmptyState,
    SegmentedControl,
)
from ..styles import SPACING, COL_WIDTH, UI, format_tokens
from .colors import get_operation_variant


class AnalyticsSection(QWidget):
    """Analytics section - usage statistics."""

    period_changed = pyqtSignal(int)

    PERIODS = [
        ("24h", 1),
        ("7d", 7),
        ("30d", 30),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_days = 7
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        layout.setSpacing(0)

        # Header with period selector
        header = PageHeader("Analytics", "Usage statistics and metrics")

        # Segmented control for period selection
        period_labels = [label for label, _ in self.PERIODS]
        self._period_control = SegmentedControl(period_labels)
        self._period_control.set_current_index(1)  # Default to 7 days
        self._period_control.selection_changed.connect(self._on_period_changed)
        header.add_action(self._period_control)

        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, SPACING["md"], 0)
        content_layout.setSpacing(SPACING["xl"])

        # Usage Metrics (4 cards)
        self._metrics = MetricsRow()
        self._metrics.add_metric("sessions", "0", "Sessions", "primary")
        self._metrics.add_metric("messages", "0", "Messages", "primary")
        self._metrics.add_metric("tokens", "0", "Tokens", "warning")
        self._metrics.add_metric("cache_hit", "0%", "Cache Hit", "success")
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Agent Usage Section
        content_layout.addWidget(
            SectionHeader("Agent Usage", "Token consumption by agent")
        )

        self._agents_table = DataTable(["Agent", "Messages", "Tokens", "Share"])
        self._agents_table.setColumnWidth(0, COL_WIDTH["path"])  # Agent name (long)
        self._agents_table.setColumnWidth(
            1, COL_WIDTH["number_small"]
        )  # Messages count
        self._agents_table.setColumnWidth(
            2, COL_WIDTH["number_medium"]
        )  # Tokens (formatted)
        self._agents_table.setColumnWidth(3, COL_WIDTH["percentage"])  # Share %
        content_layout.addWidget(self._agents_table)

        self._agents_empty = EmptyState(
            icon="○",
            title="No usage data",
            subtitle="Analytics will appear after some activity",
        )
        self._agents_empty.hide()
        content_layout.addWidget(self._agents_empty)

        content_layout.addWidget(Separator())

        # Top Tools Section
        content_layout.addWidget(
            SectionHeader("Top Tools", "Most frequently used tools")
        )

        self._tools_table = DataTable(
            ["Tool", "Invocations", "Failures", "Failure Rate"]
        )
        self._tools_table.setColumnWidth(0, COL_WIDTH["name_short"])  # Tool name
        self._tools_table.setColumnWidth(1, COL_WIDTH["number_small"])  # Invocations
        self._tools_table.setColumnWidth(2, COL_WIDTH["number_tiny"])  # Failures
        self._tools_table.setColumnWidth(3, COL_WIDTH["percentage"])  # Failure rate
        content_layout.addWidget(self._tools_table)

        content_layout.addWidget(Separator())

        # Skills Section
        content_layout.addWidget(SectionHeader("Skills Loaded", "Custom skills used"))

        self._skills_table = DataTable(["Skill", "Load Count"])
        self._skills_table.setColumnWidth(0, COL_WIDTH["path"])  # Skill name
        self._skills_table.setColumnWidth(1, COL_WIDTH["number_small"])  # Load count
        content_layout.addWidget(self._skills_table)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        sessions: int,
        messages: int,
        tokens: str,
        cache_hit: str,
        agents: list[dict],
        tools: list[dict],
        skills: list[dict],
    ) -> None:
        """Update analytics data."""
        self._metrics.update_metric("sessions", str(sessions))
        self._metrics.update_metric("messages", str(messages))
        self._metrics.update_metric("tokens", tokens)
        self._metrics.update_metric("cache_hit", cache_hit)

        # Agents
        self._agents_table.clear_data()

        if agents:
            self._agents_table.show()
            self._agents_empty.hide()

            total_tokens = sum(a.get("tokens", 0) for a in agents)
            for agent in agents[: UI["top_items_limit"]]:
                tokens_val = agent.get("tokens", 0)
                share = (
                    f"{tokens_val / total_tokens * 100:.1f}%"
                    if total_tokens > 0
                    else "0%"
                )

                self._agents_table.add_row(
                    [
                        agent.get("agent", ""),
                        str(agent.get("messages", 0)),
                        format_tokens(tokens_val),
                        share,
                    ]
                )
        else:
            self._agents_table.hide()
            self._agents_empty.show()

        # Tools with type badges
        self._tools_table.clear_data()
        for tool in tools[: UI["top_items_limit"]]:
            invocations = tool.get("invocations", 0)
            failures = tool.get("failures", 0)
            # Use failure_rate from API if available, else calculate
            rate = tool.get(
                "failure_rate",
                f"{failures / invocations * 100:.1f}%" if invocations > 0 else "0%",
            )
            tool_name = tool.get("tool", "") or tool.get("tool_name", "")
            tool_variant = get_operation_variant(tool_name)

            self._tools_table.add_row(
                [
                    (tool_name, tool_variant) if tool_variant else tool_name,
                    str(invocations),
                    str(failures),
                    rate,
                ]
            )

        # Skills
        self._skills_table.clear_data()
        for skill in skills[: UI["top_items_limit"]]:
            self._skills_table.add_row(
                [
                    skill.get("skill", "") or skill.get("skill_name", ""),
                    str(skill.get("load_count", 0)),
                ]
            )

    def _on_period_changed(self, index: int) -> None:
        if 0 <= index < len(self.PERIODS):
            _, days = self.PERIODS[index]
            self._current_days = days
            self.period_changed.emit(days)

    def get_current_period(self) -> int:
        """Get the currently selected period in days."""
        return self._current_days
