"""
Tracing section package - Agent execution traces visualization.

This package provides the TracingSection widget for visualizing
agent delegations and session hierarchies in the dashboard.

Components:
- TracingSection: Main section widget with tree and detail panel
- TimelineView: Chronological timeline of session events
- DelegationTreeView: Expandable tree of agent delegations
"""

from .section import TracingSection
from .views import (
    TimelineView,
    TimelineEventWidget,
    DelegationTreeView,
    DelegationTreePanel,
)

__all__ = [
    "TracingSection",
    "TimelineView",
    "TimelineEventWidget",
    "DelegationTreeView",
    "DelegationTreePanel",
]
