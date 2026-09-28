"""
Agents tab - Agent hierarchy with delegation info.
"""

from PyQt6.QtWidgets import QListWidgetItem

from ..helpers import format_tokens_short
from .base import BaseTab


class AgentsTab(BaseTab):
    """Tab displaying agent hierarchy with delegation info."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Summary label
        self._add_summary_label()

        # Agents list with hover support
        self._list = self._add_styled_list(include_hover=True)

    def load_data(self, agents: list[dict]) -> None:
        """Load agents data from TracingDataService response."""
        self._loaded = True

        self._list.clear()

        if not agents:
            if self._summary:
                self._summary.setText("No agent data available")
            return

        # Update summary
        total_agents = len(agents)
        total_tokens = sum(a.get("tokens", 0) for a in agents)
        if self._summary:
            self._summary.setText(
                f"Agents: {total_agents}  •  "
                f"Total tokens: {format_tokens_short(total_tokens)}"
            )

        # Add agents to list
        for agent in agents:
            name = agent.get("agent", "unknown")
            tokens = agent.get("tokens", 0)
            msg_count = agent.get("message_count", 0)

            item = QListWidgetItem(
                f"🤖 {name}  •  {format_tokens_short(tokens)} tokens  •  {msg_count} messages"
            )
            self._list.addItem(item)

    def clear(self) -> None:
        super().clear()
        self._list.clear()
