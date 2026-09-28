"""
Panel strategy protocol - Interface for panel content strategies.
"""

from typing import Protocol, runtime_checkable

from .types import PanelContent, TreeNodeData


@runtime_checkable
class PanelStrategy(Protocol):
    @staticmethod
    def handles() -> list[str]:
        """Return list of node_types this strategy handles."""
        ...

    def get_content(self, node: TreeNodeData) -> PanelContent:
        """Generate panel content for the given node."""
        ...
