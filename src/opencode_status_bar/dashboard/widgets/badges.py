"""
Badge widgets for status and type indicators.
"""

from PyQt6.QtWidgets import QLabel, QWidget

from ..styles import COLORS, SPACING, FONTS, RADIUS


class Badge(QLabel):
    """Base badge with pill style."""

    def __init__(
        self,
        text: str,
        bg_color: str,
        text_color: str,
        parent: QWidget | None = None,
    ):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(f"""
            padding: {SPACING["xs"]}px {SPACING["sm"] + 4}px;
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_bold"]};
            background-color: {bg_color};
            color: {text_color};
            border-radius: {RADIUS["sm"]}px;
            letter-spacing: {FONTS["tracking_mid"]}px;
        """)


class RiskBadge(Badge):
    """Badge for risk levels."""

    VARIANTS = {
        "critical": (COLORS["risk_critical_bg"], COLORS["risk_critical"]),
        "high": (COLORS["risk_high_bg"], COLORS["risk_high"]),
        "medium": (COLORS["risk_medium_bg"], COLORS["risk_medium"]),
        "low": (COLORS["risk_low_bg"], COLORS["risk_low"]),
    }

    def __init__(
        self,
        level: str,
        parent: QWidget | None = None,
    ):
        level_lower = level.lower()
        bg, fg = self.VARIANTS.get(
            level_lower, (COLORS["bg_elevated"], COLORS["text_secondary"])
        )
        super().__init__(level, bg, fg, parent)


class TypeBadge(Badge):
    """Badge for operation types."""

    TYPE_MAP = {
        "command": ("type_command_bg", "type_command"),
        "bash": ("type_bash_bg", "type_bash"),
        "read": ("type_read_bg", "type_read"),
        "write": ("type_write_bg", "type_write"),
        "edit": ("type_edit_bg", "type_edit"),
        "webfetch": ("type_webfetch_bg", "type_webfetch"),
        "web_fetch": ("type_webfetch_bg", "type_webfetch"),
        "glob": ("type_glob_bg", "type_glob"),
        "grep": ("type_grep_bg", "type_grep"),
        "skill": ("type_skill_bg", "type_skill"),
    }

    def __init__(
        self,
        op_type: str,
        parent: QWidget | None = None,
    ):
        type_lower = op_type.lower()
        bg_key, fg_key = self.TYPE_MAP.get(
            type_lower, ("bg_elevated", "text_secondary")
        )
        bg = COLORS.get(bg_key, COLORS["bg_elevated"])
        fg = COLORS.get(fg_key, COLORS["text_secondary"])
        super().__init__(op_type, bg, fg, parent)


class StatusBadge(QLabel):
    """Status indicator with dot + text (no background)."""

    VARIANTS = {
        "success": COLORS["success"],
        "warning": COLORS["warning"],
        "error": COLORS["error"],
        "info": COLORS["info"],
        "neutral": COLORS["text_muted"],
        "critical": COLORS["risk_critical"],
        "high": COLORS["risk_high"],
        "medium": COLORS["risk_medium"],
        "low": COLORS["risk_low"],
    }

    def __init__(
        self,
        text: str,
        variant: str = "neutral",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._text = text
        self.set_variant(variant)

    def set_variant(self, variant: str) -> None:
        color = self.VARIANTS.get(variant, self.VARIANTS["neutral"])
        # Display as: ● TEXT (dot + text, colored, no background)
        self.setText(f"● {self._text}")
        self.setStyleSheet(f"""
            padding: {SPACING["xs"]}px {SPACING["sm"]}px;
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {color};
            background: transparent;
        """)
