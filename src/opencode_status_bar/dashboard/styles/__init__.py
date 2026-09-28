"""
Dashboard styles - Modern, minimal design system.

Design Philosophy:
- Dark theme with refined neutral palette
- Soft rounded corners (not sharp)
- Maximum clarity with generous spacing
- Strong typography hierarchy
- Subtle shadows for depth

This package provides:
- COLORS: Color palette dictionary
- SPACING, RADIUS, FONTS, UI, COL_WIDTH, ICONS: Dimension constants
- format_tokens, format_duration_ms: Formatting utilities
- get_stylesheet: QSS stylesheet generator
"""

from .colors import COLORS, AGENT_COLORS
from .dimensions import (
    SPACING,
    RADIUS,
    FONTS,
    UI,
    COL_WIDTH,
    ICONS,
    SHADOWS,
    OPACITY,
    Z_INDEX,
    COMPONENTS,
    TRANSITIONS,
)
from .utils import format_tokens, format_duration_ms
from .stylesheet import get_stylesheet

__all__ = [
    # Colors
    "COLORS",
    "AGENT_COLORS",
    # Dimensions
    "SPACING",
    "RADIUS",
    "FONTS",
    "UI",
    "COL_WIDTH",
    "ICONS",
    "SHADOWS",
    "OPACITY",
    "Z_INDEX",
    "COMPONENTS",
    "TRANSITIONS",
    # Utilities
    "format_tokens",
    "format_duration_ms",
    # Stylesheet
    "get_stylesheet",
]
