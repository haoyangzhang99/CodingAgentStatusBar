"""
Dashboard dimensions - Spacing, typography, and UI constants.

Design Philosophy:
- 8px base spacing system
- Soft rounded corners (not sharp)
- Strong typography hierarchy
"""

# ============================================================
# SPACING SYSTEM (8px base)
# ============================================================

SPACING = {
    "xs": 4,  # Tight spacing
    "sm": 8,  # Small spacing (base)
    "md": 16,  # Medium spacing (2x)
    "lg": 24,  # Large spacing (3x)
    "xl": 32,  # Extra large (4x)
    "2xl": 48,  # 2x extra large (6x)
    "3xl": 64,  # 3x extra large (8x)
}

# ============================================================
# BORDER RADIUS (soft, not sharp)
# ============================================================

RADIUS = {
    "xs": 2,  # Extra small (timeline, separators, progress bars)
    "sm": 4,  # Small radius (badges, buttons)
    "md": 6,  # Medium radius (cards, inputs)
    "lg": 8,  # Large radius (containers)
    "xl": 12,  # Extra large (modals)
    "full": 9999,  # Fully rounded (pills)
}

# ============================================================
# TYPOGRAPHY
# ============================================================

FONTS = {
    "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "mono": "ui-monospace, 'SF Mono', Menlo, Monaco, 'Courier New', monospace",
    # Sizes
    "size_xxs": 10,  # Micro text (status dots, timeline markers)
    "size_xs": 11,  # Labels, badges
    "size_sm": 12,  # Secondary text
    "size_base": 13,  # Body text
    "size_md": 14,  # Emphasized body
    "size_lg": 16,  # Subtitles
    "size_xl": 18,  # Section headers
    "size_2xl": 28,  # Page titles
    "size_3xl": 36,  # Large values in cards
    "size_4xl": 48,  # Hero numbers
    # Weights
    "weight_normal": 400,
    "weight_medium": 500,
    "weight_semibold": 600,
    "weight_bold": 700,
    "weight_extrabold": 800,
    # Letter spacing
    "tracking_tighter": -0.8,
    "tracking_tight": -0.5,
    "tracking_normal": 0,
    "tracking_mid": 0.3,
    "tracking_wide": 0.5,
    "tracking_wider": 1.0,
    # Line heights
    "line_height_tight": 1.2,
    "line_height_normal": 1.5,
    "line_height_relaxed": 1.6,
    "line_height_mono": 1.4,
}

# ============================================================
# UI CONSTANTS
# ============================================================

UI = {
    # Refresh rates (milliseconds)
    "refresh_interval_ms": 2000,
    # Icon sizes
    "app_icon_size": 128,
    # Sidebar
    "sidebar_width": 220,
    "nav_item_height": 48,
    # Cards - MORE COMPACT
    "card_min_width": 110,  # REDUCED (was 130)
    "card_min_height": 80,  # REDUCED (was 90)
    "card_max_width": 140,  # REDUCED (was 160)
    # Tables - MORE DENSE
    "row_height": 36,  # REDUCED for better data density (was 40)
    "header_height": 32,  # REDUCED to align with row height (was 36)
    # NEW: Grid layout gaps
    "grid_gap_sm": 12,
    "grid_gap_md": 16,
    "grid_gap_lg": 24,
    # Limits for data display
    "table_row_limit": 20,
    "top_items_limit": 10,
    # Window
    "window_min_width": 1000,
    "window_min_height": 700,
    "window_default_width": 1200,
    "window_default_height": 800,
}

# ============================================================
# COLUMN WIDTHS (based on data type)
# ============================================================

COL_WIDTH = {
    # Text columns
    "name_short": 180,  # Tool names, short agent names
    "name_long": 280,  # Full agent names, descriptions
    "path": 320,  # File paths, directories
    # Numeric columns
    "number_tiny": 60,  # Single digit or small numbers (0-99)
    "number_small": 80,  # Small numbers (0-9999)
    "number_medium": 100,  # Medium numbers with formatting (10K, 1.2M)
    # Status/Type columns
    "status": 100,  # BUSY, IDLE (badge)
    "risk": 110,  # LOW, MEDIUM, HIGH, CRITICAL (badge)
    "type": 120,  # COMMAND, READ, WRITE, etc. (badge)
    # Other
    "duration": 90,  # 1m 30s, 500ms
    "percentage": 80,  # 48.2%, 100%
    "reason": 200,  # Short explanations
}

# ============================================================
# ICONS (Simple Unicode)
# ============================================================

ICONS = {
    # Navigation
    "monitoring": "●",
    "security": "◆",
    "analytics": "■",
    "tracing": "◎",
    # Status
    "status_active": "●",
    "status_idle": "○",
    # Actions
    "arrow_up": "↑",
    "arrow_down": "↓",
    "check": "✓",
    "warning": "!",
    "error": "×",
    # Types
    "command": "⌘",
    "read": "◉",
    "write": "✎",
    "edit": "✏",
    "webfetch": "⬡",
    "glob": "⊕",
    "grep": "⊗",
}

# ============================================================
# SHADOWS (elevation system)
# ============================================================

SHADOWS = {
    "none": {"blur": 0, "offset_y": 0, "opacity": 0.0},
    "sm": {"blur": 8, "offset_y": 2, "opacity": 0.3},
    "md": {"blur": 12, "offset_y": 4, "opacity": 0.4},
    "lg": {"blur": 16, "offset_y": 8, "opacity": 0.5},
}

# ============================================================
# OPACITY (semantic transparency levels)
# ============================================================

OPACITY = {
    "invisible": 0.0,
    "subtle": 0.06,
    "hover": 0.08,
    "active": 0.12,
    "focus": 0.15,
    "badge": 0.25,
    "disabled": 0.4,
    "overlay": 0.6,
}

# ============================================================
# Z-INDEX (layering system)
# ============================================================

Z_INDEX = {
    "base": 0,
    "dropdown": 1000,
    "sticky": 1050,
    "fixed": 1100,
    "modal_backdrop": 2000,
    "modal": 2010,
    "tooltip": 3000,
}

# ============================================================
# COMPONENTS (component-specific dimensions)
# ============================================================

COMPONENTS = {
    "button": {"height": 32, "padding_x": 12, "padding_y": 8},
    "badge": {"height": 20, "padding_x": 8, "padding_y": 2},
    "input": {"height": 32, "padding_x": 12},
    "separator": {"height": 1},
    "scrollbar": {"width": 8},
    "avatar": {"size_sm": 24, "size_md": 32, "size_lg": 48},
}

# ============================================================
# TRANSITIONS (animation durations in milliseconds)
# ============================================================

TRANSITIONS = {
    "fast": 150,
    "normal": 200,
    "slow": 300,
    "slowest": 400,
}
