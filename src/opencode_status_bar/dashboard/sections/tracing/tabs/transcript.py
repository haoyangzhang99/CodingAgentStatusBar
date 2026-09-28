"""
Transcript tab - Full conversation transcript.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QTextEdit,
)

from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from .base import BaseTab


class TranscriptTab(BaseTab):
    """Tab displaying full conversation transcript."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Scroll area for long transcripts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS["bg_surface"]};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS["border_default"]};
                border-radius: 4px;
                min-height: 30px;
            }}
        """)

        # Content widget
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        self._content_layout.setSpacing(SPACING["lg"])

        scroll.setWidget(self._content)
        self._layout.addWidget(scroll)

    def load_data(self, data: dict) -> None:
        """Load transcript data.

        Args:
            data: Dict with user_content and assistant_content
        """
        self._loaded = True

        # Clear existing content
        self._clear_layout(self._content_layout)

        user_content = data.get("user_content", "")
        assistant_content = data.get("assistant_content", "")

        # User section
        if user_content:
            user_header = QLabel("💬 User Prompt")
            user_header.setStyleSheet(f"""
                color: {COLORS.get("info", "#60A5FA")};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_semibold"]};
            """)
            self._content_layout.addWidget(user_header)

            user_text = QTextEdit()
            user_text.setPlainText(user_content)
            user_text.setReadOnly(True)
            user_text.setMinimumHeight(100)
            user_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {COLORS["bg_hover"]};
                    color: {COLORS["text_primary"]};
                    border: 1px solid {COLORS["border_default"]};
                    border-radius: {RADIUS["md"]}px;
                    padding: {SPACING["md"]}px;
                    font-family: {FONTS["family"]};
                    font-size: {FONTS["size_sm"]}px;
                }}
            """)
            self._content_layout.addWidget(user_text)

        # Assistant section
        if assistant_content:
            assistant_header = QLabel("🤖 Assistant Response")
            assistant_header.setStyleSheet(f"""
                color: {COLORS.get("success", "#34D399")};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_semibold"]};
                margin-top: {SPACING["md"]}px;
            """)
            self._content_layout.addWidget(assistant_header)

            assistant_text = QTextEdit()
            assistant_text.setPlainText(assistant_content)
            assistant_text.setReadOnly(True)
            assistant_text.setMinimumHeight(150)
            assistant_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {COLORS["bg_hover"]};
                    color: {COLORS["text_primary"]};
                    border: 1px solid {COLORS["border_default"]};
                    border-radius: {RADIUS["md"]}px;
                    padding: {SPACING["md"]}px;
                    font-family: {FONTS["family"]};
                    font-size: {FONTS["size_sm"]}px;
                }}
            """)
            self._content_layout.addWidget(assistant_text)

        self._content_layout.addStretch()

    def clear(self) -> None:
        super().clear()
        self._clear_layout(self._content_layout)
