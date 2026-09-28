"""
Enriched tracing widgets - AgentBadge and ErrorIndicator.

Provides visual components for displaying agent types and error states
in the tracing timeline and tree views.
"""

from typing import Optional

from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt

from opencode_status_bar.dashboard.styles import COLORS, FONTS, RADIUS, AGENT_COLORS


class AgentBadge(QLabel):
    """Pill badge showing agent type with color coding.

    Visual:
        +------------+
        |  executor  |  <- Green pill with text
        +------------+

    Usage:
        badge = AgentBadge("executor")
        layout.addWidget(badge)
    """

    # Short labels for display
    AGENT_LABELS = {
        "main": "main",
        "executor": "exec",
        "tea": "tea",
        "subagent": "sub",
        "coder": "coder",
        "analyst": "analyst",
    }

    def __init__(
        self, agent_type: Optional[str] = None, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._agent_type = ""
        if agent_type:
            self.set_agent(agent_type)
        else:
            self.hide()

    def set_agent(self, agent_type: Optional[str]) -> None:
        """Update displayed agent type.

        Args:
            agent_type: Agent type string or None/empty to hide
        """
        if not agent_type:
            self.hide()
            return

        self._agent_type = agent_type.lower()

        # Get display label (shortened)
        label = self.AGENT_LABELS.get(self._agent_type, self._agent_type[:4])

        # Get colors
        text_color, bg_color = AGENT_COLORS.get(
            self._agent_type, AGENT_COLORS["default"]
        )

        self.setText(label)
        self.setStyleSheet(f"""
            QLabel {{
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_medium"]};
                padding: 2px 6px;
                border-radius: {RADIUS["full"]}px;
                background-color: {bg_color};
                color: {text_color};
            }}
        """)
        self.setToolTip(f"Agent: {agent_type}")
        self.show()

    def agent_type(self) -> str:
        """Return current agent type."""
        return self._agent_type


class ErrorIndicator(QLabel):
    """Error indicator icon with tooltip.

    Visual:
        !  <- Warning icon in error color
        +-- Tooltip: "FileNotFoundError: File not found"

    Usage:
        indicator = ErrorIndicator()
        indicator.set_error({"name": "FileNotFoundError", "data": "..."})
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setText("")
        self.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["error"]};
                font-size: {FONTS["size_sm"]}px;
                font-weight: {FONTS["weight_bold"]};
            }}
        """)
        self.hide()

    def set_error(self, error_info: Optional[dict]) -> None:
        """Update error display.

        Args:
            error_info: Dict with 'name' and optional 'data' keys, or None to hide
        """
        if not error_info or not error_info.get("name"):
            self.hide()
            return

        error_name = error_info.get("name", "Error")
        error_data = error_info.get("data", "")

        self.setText("!")

        # Build tooltip
        tooltip = f"Error: {error_name}"
        if error_data:
            # Truncate long error messages
            data_preview = (
                error_data[:200] + "..." if len(error_data) > 200 else error_data
            )
            tooltip += f"\n{data_preview}"

        self.setToolTip(tooltip)
        self.show()

    def has_error(self) -> bool:
        """Return True if error is displayed."""
        return self.isVisible()
