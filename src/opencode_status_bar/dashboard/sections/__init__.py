"""
Dashboard sections - Modern, minimal design.

Each section features:
- Clear page header with actions
- Metric cards with centered values
- Enhanced data tables
- Generous spacing (8px based)
"""

from .monitoring import MonitoringSection
from .security import SecuritySection
from .analytics import AnalyticsSection
from .tracing import TracingSection
from .colors import OPERATION_TYPE_COLORS, get_operation_variant

__all__ = [
    "MonitoringSection",
    "SecuritySection",
    "AnalyticsSection",
    "TracingSection",
    "OPERATION_TYPE_COLORS",
    "get_operation_variant",
]
