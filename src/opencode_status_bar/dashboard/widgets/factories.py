from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt

from ..styles import COLORS, FONTS


def create_header_label(
    text: str,
    parent: QWidget | None = None,
) -> QLabel:
    label = QLabel(text.upper(), parent)
    label.setStyleSheet(f"""
        font-size: {FONTS["size_xs"]}px;
        font-weight: {FONTS["weight_semibold"]};
        color: {COLORS["text_muted"]};
        letter-spacing: {FONTS["tracking_wide"]}px;
    """)
    return label


def create_value_label(
    text: str,
    color: str = "text_primary",
    size: str = "size_xl",
    parent: QWidget | None = None,
) -> QLabel:
    label = QLabel(text, parent)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(f"""
        font-size: {FONTS[size]}px;
        font-weight: {FONTS["weight_bold"]};
        color: {COLORS[color]};
    """)
    return label


def create_content_label(
    text: str,
    variant: str = "secondary",
    mono: bool = False,
    parent: QWidget | None = None,
) -> QLabel:
    color_map = {
        "primary": COLORS["text_primary"],
        "secondary": COLORS["text_secondary"],
        "muted": COLORS["text_muted"],
    }

    font_family = FONTS["mono"] if mono else FONTS["family"]
    color = color_map.get(variant, COLORS["text_secondary"])

    label = QLabel(text, parent)
    label.setStyleSheet(f"""
        font-size: {FONTS["size_xs"]}px;
        color: {color};
        font-family: {font_family};
    """)
    return label
