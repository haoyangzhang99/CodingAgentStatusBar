"""
Dashboard widgets - Modern, minimal design.

Design principles:
- Soft rounded corners
- Clear visual hierarchy
- Generous spacing
- Strong typography
- Semantic colors

This package provides re-exports for all widget classes to maintain
backwards compatibility with the original widgets.py module.
"""

# Navigation
from .navigation import NavItem, Sidebar

# Cards
from .cards import MetricCard, MetricsRow, Card, SectionCard

# Badges
from .badges import Badge, RiskBadge, TypeBadge, StatusBadge
from .cell_badge import (
    CellBadge,
    create_risk_badge,
    create_type_badge,
    create_score_badge,
)

# Tables
from .tables import DataTable

# Controls
from .controls import (
    ClickableLabel,
    PageHeader,
    SectionHeader,
    Separator,
    SegmentedControl,
    EmptyState,
)

# Expandable
from .expandable import ExpandableSection

# Factories
from .factories import create_header_label, create_value_label, create_content_label

__all__ = [
    # Navigation
    "NavItem",
    "Sidebar",
    # Cards
    "MetricCard",
    "MetricsRow",
    "Card",
    "SectionCard",
    # Badges
    "Badge",
    "RiskBadge",
    "TypeBadge",
    "StatusBadge",
    "CellBadge",
    "create_risk_badge",
    "create_type_badge",
    "create_score_badge",
    # Tables
    "DataTable",
    # Controls
    "ClickableLabel",
    "PageHeader",
    "SectionHeader",
    "Separator",
    "SegmentedControl",
    "EmptyState",
    # Expandable
    "ExpandableSection",
    # Label Factories
    "create_header_label",
    "create_value_label",
    "create_content_label",
]
