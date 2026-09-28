"""
Dashboard QSS stylesheet generation.

Provides the complete Qt StyleSheet for the dashboard with modern dark theme styling.
"""

from .colors import COLORS
from .dimensions import SPACING, RADIUS, FONTS


def get_stylesheet() -> str:
    """Get the complete QSS stylesheet for the dashboard."""
    return f"""
/* ========================================
   Global Reset & Base
   ======================================== */

* {{
    outline: none;
}}

QWidget {{
    font-family: {FONTS["family"]};
    font-size: {FONTS["size_base"]}px;
    color: {COLORS["text_primary"]};
    background-color: transparent;
}}

/* ========================================
   Main Window
   ======================================== */

QMainWindow {{
    background-color: {COLORS["bg_base"]};
}}

/* ========================================
   Sidebar
   ======================================== */

QFrame#sidebar {{
    background-color: {COLORS["sidebar_bg"]};
    border-right: 1px solid {COLORS["border_default"]};
}}

/* ========================================
   Scroll Areas
   ======================================== */

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["border_strong"]};
    min-height: 40px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS["text_muted"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS["border_strong"]};
    min-width: 40px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS["text_muted"]};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ========================================
   Tables
   ======================================== */

QTableWidget {{
    background-color: {COLORS["bg_surface"]};
    border: 1px solid {COLORS["border_default"]};
    border-radius: {RADIUS["md"]}px;
    gridline-color: transparent;
    selection-background-color: {COLORS["bg_hover"]};
    outline: none;
}}

QTableWidget QTableCornerButton::section {{
    background-color: {COLORS["bg_elevated"]};
    border: none;
    border-top-left-radius: {RADIUS["md"]}px;
}}

QTableWidget::item {{
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    border: none;
    border-bottom: 1px solid {COLORS["border_subtle"]};
}}

QTableWidget::item:selected {{
    background-color: {COLORS["sidebar_active"]};
    color: {COLORS["text_primary"]};
}}

QHeaderView {{
    background-color: transparent;
}}

QHeaderView::section {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_muted"]};
    padding: {SPACING["md"]}px {SPACING["md"]}px;
    border: none;
    border-bottom: 1px solid {COLORS["border_default"]};
    font-weight: {FONTS["weight_semibold"]};
    font-size: {FONTS["size_xs"]}px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QHeaderView::section:first {{
    border-top-left-radius: {RADIUS["md"]}px;
}}

QHeaderView::section:last {{
    border-top-right-radius: {RADIUS["md"]}px;
}}

QHeaderView::section:hover {{
    background-color: {COLORS["bg_hover"]};
    color: {COLORS["text_secondary"]};
}}

/* ========================================
   Buttons
   ======================================== */

QPushButton {{
    background-color: {COLORS["accent_primary"]};
    color: white;
    border: none;
    border-radius: {RADIUS["sm"]}px;
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    font-weight: {FONTS["weight_medium"]};
    font-size: {FONTS["size_sm"]}px;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {COLORS["accent_primary_hover"]};
}}

QPushButton:pressed {{
    background-color: #1d4ed8;
}}

QPushButton:disabled {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_muted"]};
}}

/* ========================================
   ComboBox
   ======================================== */

QComboBox {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border_default"]};
    border-radius: {RADIUS["sm"]}px;
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    padding-right: 28px;
    min-width: 140px;
    min-height: 32px;
    font-size: {FONTS["size_sm"]}px;
}}

QComboBox:hover {{
    border-color: {COLORS["border_strong"]};
}}

QComboBox:focus {{
    border-color: {COLORS["accent_primary"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border: none;
}}

QComboBox::down-arrow {{
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS["text_muted"]};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["bg_surface"]};
    border: 1px solid {COLORS["border_default"]};
    border-radius: {RADIUS["sm"]}px;
    selection-background-color: {COLORS["bg_hover"]};
    selection-color: {COLORS["text_primary"]};
    outline: none;
    padding: {SPACING["xs"]}px;
}}

QComboBox QAbstractItemView::item {{
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    min-height: 32px;
    border-radius: {RADIUS["sm"]}px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {COLORS["bg_hover"]};
}}

/* ========================================
   Tooltips
   ======================================== */

QToolTip {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border_default"]};
    border-radius: {RADIUS["sm"]}px;
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    font-size: {FONTS["size_sm"]}px;
}}
"""
