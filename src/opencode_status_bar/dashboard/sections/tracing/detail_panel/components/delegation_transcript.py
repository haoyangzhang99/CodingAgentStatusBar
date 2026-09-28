"""
DelegationTranscriptPanel - Simple panel showing delegation prompt and response.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QTextEdit,
)
from PyQt6.QtCore import Qt

from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from ..handlers import DataLoaderMixin
from ..strategies.types import DelegationData


class DelegationTranscriptPanel(DataLoaderMixin, QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("delegation-transcript")

        self._child_session_id: Optional[str] = None
        self._subagent_type: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame#delegation-transcript {{
                background-color: {COLORS["bg_surface"]};
                border: none;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        self._content_layout.setSpacing(SPACING["lg"])

        scroll.setWidget(self._content)
        main_layout.addWidget(scroll, stretch=1)

    def load_delegation(self, delegation_data: DelegationData) -> None:
        self._child_session_id = delegation_data.get("child_session_id")
        self._subagent_type = delegation_data.get("subagent_type")

        self._clear_content()

        if self._child_session_id:
            self._load_timeline()
        else:
            self._show_message("No child session ID available")

    def _load_timeline(self) -> None:
        child_session_id = self._child_session_id
        if not child_session_id:
            return

        client = self._get_api_client()
        if not client.is_available:
            self._show_message("API not available")
            return

        data = client.get_session_prompts(child_session_id)
        if not data:
            self._show_message("No data available")
            return

        prompt_input = data.get("prompt_input", "")
        prompt_output = data.get("prompt_output", "")

        if prompt_input:
            self._add_section("📥 Prompt", prompt_input, COLORS.get("info", "#60A5FA"))

        if prompt_output:
            self._add_section(
                "📤 Response", prompt_output, COLORS.get("success", "#34D399")
            )

        if not prompt_input and not prompt_output:
            self._show_message("No content available")

        self._content_layout.addStretch()

    def _add_section(self, title: str, content: str, color: str) -> None:
        header = QLabel(title)
        header.setStyleSheet(f"""
            color: {color};
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
        """)
        self._content_layout.addWidget(header)

        text_edit = QTextEdit()
        text_edit.setPlainText(content)
        text_edit.setReadOnly(True)
        text_edit.setMinimumHeight(120)
        text_edit.setStyleSheet(f"""
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
        self._content_layout.addWidget(text_edit)

    def _show_message(self, message: str) -> None:
        label = QLabel(message)
        label.setStyleSheet(f"""
            color: {COLORS["text_muted"]};
            font-size: {FONTS["size_md"]}px;
            padding: {SPACING["xl"]}px;
        """)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(label)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

    def clear(self) -> None:
        self._child_session_id = None
        self._subagent_type = None
        self._clear_content()
