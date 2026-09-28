"""
Dashboard color palette - Modern dark theme.

Design Philosophy:
- Dark theme with refined neutral palette
- Layered depth through background colors
- Strong semantic color system for risk levels and operation types
"""

COLORS = {
    # Backgrounds (layered depth) - IMPROVED CONTRAST
    "bg_base": "#0d0d0d",  # Deepest background (darker than before)
    "bg_surface": "#1a1a1a",  # Cards, panels
    "bg_elevated": "#222222",  # Elevated elements (MORE CONTRAST: was #252525)
    "bg_hover": "#2a2a2a",  # Hover states
    "bg_active": "#303030",  # Active/pressed states
    # NEW: Subtle accent backgrounds for cards
    "bg_surface_blue": "rgba(59, 130, 246, 0.04)",
    "bg_surface_green": "rgba(34, 197, 94, 0.04)",
    "bg_surface_amber": "rgba(245, 158, 11, 0.04)",
    # Text hierarchy - IMPROVED READABILITY
    "text_primary": "#f5f5f5",  # Primary text (MORE READABLE: was #ffffff)
    "text_secondary": "#b3b3b3",  # Secondary text (MORE READABLE: was #a0a0a0)
    "text_muted": "#737373",  # Muted/disabled (MORE READABLE: was #666666)
    "text_inverse": "#0d0d0d",  # Text on light backgrounds
    # Accent colors
    "accent_primary": "#3b82f6",  # Blue 500
    "accent_primary_hover": "#60a5fa",  # Blue 400
    "accent_primary_muted": "rgba(59, 130, 246, 0.15)",
    "accent_success": "#22c55e",  # Green 500
    "accent_warning": "#f59e0b",  # Amber 500
    "accent_error": "#ef4444",  # Red 500
    # Semantic colors with muted backgrounds
    "success": "#22c55e",
    "success_muted": "rgba(34, 197, 94, 0.25)",
    "warning": "#f59e0b",
    "warning_muted": "rgba(245, 158, 11, 0.25)",
    "error": "#ef4444",
    "error_muted": "rgba(239, 68, 68, 0.25)",
    "info": "#3b82f6",
    "info_muted": "rgba(59, 130, 246, 0.25)",
    # Risk levels (semantic)
    "risk_critical": "#ef4444",  # Red 500
    "risk_critical_bg": "rgba(239, 68, 68, 0.25)",
    "risk_high": "#f97316",  # Orange 500
    "risk_high_bg": "rgba(249, 115, 22, 0.25)",
    "risk_medium": "#eab308",  # Yellow 500
    "risk_medium_bg": "rgba(234, 179, 8, 0.25)",
    "risk_low": "#22c55e",  # Green 500
    "risk_low_bg": "rgba(34, 197, 94, 0.25)",
    # Operation type colors (for badges)
    "type_command": "#a855f7",  # Violet 500
    "type_command_bg": "rgba(168, 85, 247, 0.25)",
    "type_bash": "#a855f7",
    "type_bash_bg": "rgba(168, 85, 247, 0.25)",
    "type_read": "#3b82f6",  # Blue 500
    "type_read_bg": "rgba(59, 130, 246, 0.25)",
    "type_write": "#f97316",  # Orange 500
    "type_write_bg": "rgba(249, 115, 22, 0.25)",
    "type_edit": "#eab308",  # Yellow 500
    "type_edit_bg": "rgba(234, 179, 8, 0.25)",
    "type_webfetch": "#06b6d4",  # Cyan 500
    "type_webfetch_bg": "rgba(6, 182, 212, 0.25)",
    "type_glob": "#ec4899",  # Pink 500
    "type_glob_bg": "rgba(236, 72, 153, 0.25)",
    "type_grep": "#10b981",  # Emerald 500
    "type_grep_bg": "rgba(16, 185, 129, 0.25)",
    "type_skill": "#8b5cf6",  # Violet 500
    "type_skill_bg": "rgba(139, 92, 246, 0.25)",
    # Borders - MORE VISIBLE
    "border_subtle": "rgba(255, 255, 255, 0.08)",  # MORE VISIBLE (was 0.06)
    "border_default": "rgba(255, 255, 255, 0.12)",  # MORE VISIBLE (was 0.10)
    "border_strong": "rgba(255, 255, 255, 0.18)",  # MORE VISIBLE (was 0.15)
    "border_accent": "rgba(59, 130, 246, 0.4)",  # NEW: for highlights
    # Sidebar
    "sidebar_bg": "#111111",
    "sidebar_hover": "rgba(255, 255, 255, 0.04)",
    "sidebar_active": "rgba(59, 130, 246, 0.12)",
    "sidebar_active_border": "#3b82f6",
    # Shadows
    "shadow_sm": "rgba(0, 0, 0, 0.3)",
    "shadow_md": "rgba(0, 0, 0, 0.4)",
    # Tree hierarchy colors
    "tree_root": "#60a5fa",  # Blue 400 - root/project items
    "tree_root_bg": "rgba(96, 165, 250, 0.08)",
    "tree_child": "#a78bfa",  # Violet 400 - delegated agents
    "tree_child_bg": "rgba(167, 139, 250, 0.06)",
    "tree_depth_1": "#c4b5fd",  # Violet 300
    "tree_depth_2": "#ddd6fe",  # Violet 200
    # Agent type colors (for trace items)
    "agent_coder": "#22c55e",  # Green - coder agent
    "agent_designer": "#f59e0b",  # Amber - designer
    "agent_researcher": "#3b82f6",  # Blue - researcher
    "agent_default": "#94a3b8",  # Slate 400 - unknown
}

# Agent colors for badges (text_color, bg_color)
AGENT_COLORS = {
    "main": ("#3b82f6", "rgba(59, 130, 246, 0.15)"),  # Blue
    "executor": ("#22c55e", "rgba(34, 197, 94, 0.15)"),  # Green
    "tea": ("#f59e0b", "rgba(245, 158, 11, 0.15)"),  # Amber
    "subagent": ("#a855f7", "rgba(168, 85, 247, 0.15)"),  # Violet
    "coder": ("#22c55e", "rgba(34, 197, 94, 0.15)"),  # Green
    "analyst": ("#3b82f6", "rgba(59, 130, 246, 0.15)"),  # Blue
    "default": ("#6b7280", "rgba(107, 114, 128, 0.15)"),  # Gray
}
