"""
Tracing tabs - Tab widgets for TraceDetailPanel.
"""

from .base import BaseTab
from .tokens import TokensTab
from .tools import ToolsTab
from .files import FilesTab
from .agents import AgentsTab
from .timeline import TimelineTab
from .transcript import TranscriptTab
from .delegations import DelegationsTab

__all__ = [
    "BaseTab",
    "TokensTab",
    "ToolsTab",
    "FilesTab",
    "AgentsTab",
    "TimelineTab",
    "TranscriptTab",
    "DelegationsTab",
]
