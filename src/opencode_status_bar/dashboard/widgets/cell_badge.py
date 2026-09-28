"""
Cell badges for colored table cells.

Provides lightweight badge widgets with translucent backgrounds
for risk levels, operation types, and scores.
"""

from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt

from ..styles import COLORS, FONTS, RADIUS, COMPONENTS


class CellBadge(QLabel):
    """Lightweight badge for table cells with translucent background."""

    def __init__(
        self,
        text: str,
        fg_color: str,
        bg_color: str,
        parent: QWidget | None = None,
    ):
        super().__init__(text.upper(), parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                color: {fg_color};
                background-color: {bg_color};
                padding: {COMPONENTS["badge"]["padding_y"]}px {COMPONENTS["badge"]["padding_x"]}px;
                border-radius: {RADIUS["sm"]}px;
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                letter-spacing: {FONTS["tracking_mid"]}px;
            }}
        """)
        self.setFixedHeight(22)


def create_risk_badge(level: str) -> CellBadge:
    """Create a badge for risk level."""
    level_lower = level.lower()
    config = {
        "critical": (COLORS["risk_critical"], COLORS["risk_critical_bg"]),
        "high": (COLORS["risk_high"], COLORS["risk_high_bg"]),
        "medium": (COLORS["risk_medium"], COLORS["risk_medium_bg"]),
        "low": (COLORS["risk_low"], COLORS["risk_low_bg"]),
    }
    fg, bg = config.get(level_lower, (COLORS["text_secondary"], COLORS["bg_elevated"]))
    return CellBadge(level, fg, bg)


def create_type_badge(op_type: str) -> CellBadge:
    """Create a badge for operation type."""
    type_lower = op_type.lower()
    config = {
        "bash": (COLORS["type_bash"], COLORS["type_bash_bg"]),
        "command": (COLORS["type_command"], COLORS["type_command_bg"]),
        "read": (COLORS["type_read"], COLORS["type_read_bg"]),
        "write": (COLORS["type_write"], COLORS["type_write_bg"]),
        "edit": (COLORS["type_edit"], COLORS["type_edit_bg"]),
        "webfetch": (COLORS["type_webfetch"], COLORS["type_webfetch_bg"]),
        "web_fetch": (COLORS["type_webfetch"], COLORS["type_webfetch_bg"]),
        "glob": (COLORS["type_glob"], COLORS["type_glob_bg"]),
        "grep": (COLORS["type_grep"], COLORS["type_grep_bg"]),
        "skill": (COLORS["type_skill"], COLORS["type_skill_bg"]),
    }
    fg, bg = config.get(type_lower, (COLORS["text_secondary"], COLORS["bg_elevated"]))
    return CellBadge(op_type, fg, bg)


def create_score_badge(score: int) -> CellBadge:
    """Create a badge for score with color based on value."""
    if score >= 80:
        fg, bg = COLORS["risk_critical"], COLORS["risk_critical_bg"]
    elif score >= 60:
        fg, bg = COLORS["risk_high"], COLORS["risk_high_bg"]
    elif score >= 40:
        fg, bg = COLORS["risk_medium"], COLORS["risk_medium_bg"]
    else:
        fg, bg = COLORS["risk_low"], COLORS["risk_low_bg"]
    return CellBadge(str(score), fg, bg)
