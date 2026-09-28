"""
Panel strategies package - Strategy pattern for panel content generation.
"""

from .types import PanelContent, TreeNodeData, TranscriptData, DelegationData
from .protocol import PanelStrategy
from .session import SessionStrategy
from .exchange import ExchangeStrategy
from .tool import ToolStrategy
from .text import TextContentStrategy
from .delegation import DelegationSpanStrategy, is_delegation_span


class StrategyFactory:
    def __init__(self):
        self._strategies: dict[str, PanelStrategy] = {}
        self._default: PanelStrategy | None = None

    def register(self, strategy: PanelStrategy) -> None:
        for node_type in strategy.handles():
            self._strategies[node_type] = strategy

    def set_default(self, strategy: PanelStrategy) -> None:
        self._default = strategy

    def get(self, node_type: str) -> PanelStrategy:
        if node_type in self._strategies:
            return self._strategies[node_type]
        if self._default is not None:
            return self._default
        raise ValueError(f"No strategy for node_type={node_type} and no default set")


_factory_instance: StrategyFactory | None = None


def create_default_factory() -> StrategyFactory:
    factory = StrategyFactory()
    factory.register(SessionStrategy())
    factory.register(ExchangeStrategy())
    factory.register(ToolStrategy())
    factory.register(DelegationSpanStrategy())
    factory.set_default(TextContentStrategy())
    return factory


def get_strategy_factory() -> StrategyFactory:
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = create_default_factory()
    return _factory_instance


__all__ = [
    "PanelContent",
    "TreeNodeData",
    "TranscriptData",
    "DelegationData",
    "PanelStrategy",
    "SessionStrategy",
    "ExchangeStrategy",
    "ToolStrategy",
    "TextContentStrategy",
    "DelegationSpanStrategy",
    "is_delegation_span",
    "StrategyFactory",
    "create_default_factory",
    "get_strategy_factory",
]
