"""
Timeline view component for session tracing.

Displays a chronological timeline of session events with rich styling
based on event type (user_prompt, reasoning, tool_call, etc.).
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QLabel,
    QFrame,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal

from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS, RADIUS

from ..helpers import format_duration
from ..enriched_helpers import get_tool_display_label, build_tool_tooltip
from ..enriched_widgets import AgentBadge, ErrorIndicator
from ..image_widgets import ImageThumbnail, ImagePreviewDialog


# Event type configuration: (icon, border_color, bg_color_key)
EVENT_TYPE_CONFIG = {
    "user_prompt": ("", "#3b82f6", "info_muted"),  # Blue - user icon
    "reasoning": ("", "#eab308", "warning_muted"),  # Yellow/gold - brain icon
    "tool_call": ("", "#22c55e", "success_muted"),  # Green - wrench icon
    "tool_result": ("", "#22c55e", "success_muted"),  # Green - checkmark
    "assistant_response": ("", "#a855f7", "type_skill_bg"),  # Purple
    "patch": ("", "#f97316", "risk_high_bg"),  # Orange - git icon
    "step_finish": ("", "#6b7280", "bg_hover"),  # Gray - smaller
    "step_start": ("", "#6b7280", "bg_hover"),  # Gray
    "delegation_start": ("", "#a78bfa", "tree_child_bg"),  # Violet - delegate
    "delegation_end": ("", "#a78bfa", "tree_child_bg"),  # Violet
    "delegation_result": ("📥", "#10b981", "tree_child_bg"),  # Teal - inbox
    "compaction": ("", "#06b6d4", "type_webfetch_bg"),  # Cyan - compress
    "file_attachment": ("", "#ec4899", "type_glob_bg"),  # Pink
}

# Default config for unknown event types
DEFAULT_EVENT_CONFIG = ("", "#6b7280", "bg_hover")


class TimelineEventWidget(QFrame):
    """Widget for a single timeline event.

    Displays event information with icon, timestamp, content preview,
    and styling based on event type.
    """

    clicked = pyqtSignal(dict)

    def __init__(self, event: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._event = event
        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self) -> None:
        """Setup the event widget UI."""
        event_type = self._event.get("type", "")
        icon, border_color, bg_key = EVENT_TYPE_CONFIG.get(
            event_type, DEFAULT_EVENT_CONFIG
        )

        # Get background color from COLORS dict
        bg_color = COLORS.get(bg_key, COLORS["bg_hover"])

        # Smaller styling for step events
        is_step_event = event_type in ("step_finish", "step_start")
        padding = SPACING["xs"] if is_step_event else SPACING["sm"]
        min_height = 28 if is_step_event else 48

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-left: 3px solid {border_color};
                border-radius: {RADIUS["sm"]}px;
                margin: 2px 0;
            }}
            QFrame:hover {{
                background-color: {COLORS["bg_active"]};
            }}
        """)
        self.setMinimumHeight(min_height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(SPACING["sm"])

        # Icon
        icon_label = QLabel(icon)
        icon_label.setFixedWidth(24)
        icon_label.setStyleSheet(f"""
            font-size: {FONTS["size_md"] if not is_step_event else FONTS["size_sm"]}px;
        """)
        layout.addWidget(icon_label)

        # Content container
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)

        # Header row (type + timestamp)
        header_row = QHBoxLayout()
        header_row.setSpacing(SPACING["sm"])

        # Type label
        type_label = QLabel(self._format_type_label(event_type))
        type_label.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_semibold"]};
        """)
        header_row.addWidget(type_label)

        # Agent badge (for message events)
        agent = self._event.get("agent")
        if agent and event_type in (
            "user_prompt",
            "assistant_response",
            "reasoning",
        ):
            self._agent_badge = AgentBadge(agent)
            header_row.addWidget(self._agent_badge)

        # Error indicator (for any event with error)
        error_info = self._event.get("error")
        if error_info:
            self._error_indicator = ErrorIndicator()
            self._error_indicator.set_error(error_info)
            header_row.addWidget(self._error_indicator)

        header_row.addStretch()

        # Timestamp
        timestamp = self._event.get("timestamp", "")
        if timestamp:
            time_label = QLabel(self._format_timestamp(timestamp))
            time_label.setStyleSheet(f"""
                color: {COLORS["text_muted"]};
                font-size: {FONTS["size_xs"]}px;
            """)
            header_row.addWidget(time_label)

        # Duration (if available)
        duration_ms = self._event.get("duration_ms")
        if duration_ms:
            dur_label = QLabel(format_duration(duration_ms))
            dur_label.setStyleSheet(f"""
                color: {COLORS["text_secondary"]};
                font-size: {FONTS["size_xs"]}px;
            """)
            header_row.addWidget(dur_label)

        content_layout.addLayout(header_row)

        # Content preview (not for step events)
        if not is_step_event:
            preview = self._get_content_preview()
            if preview:
                preview_label = QLabel(preview)
                preview_label.setStyleSheet(f"""
                    color: {COLORS["text_secondary"]};
                    font-size: {FONTS["size_sm"]}px;
                    font-family: {FONTS["mono"]};
                """)
                preview_label.setWordWrap(True)
                preview_label.setMaximumHeight(40)
                content_layout.addWidget(preview_label)

        layout.addLayout(content_layout, stretch=1)

        # Tokens indicator (for step_finish)
        if event_type == "step_finish":
            tokens_in = self._event.get("tokens_in", 0)
            tokens_out = self._event.get("tokens_out", 0)
            if tokens_in or tokens_out:
                tokens_label = QLabel(f"{tokens_in}/{tokens_out}")
                tokens_label.setStyleSheet(f"""
                    color: {COLORS["text_muted"]};
                    font-size: {FONTS["size_xs"]}px;
                """)
                layout.addWidget(tokens_label)

        # Setup enriched tooltip for tool events
        if event_type == "tool_call":
            tooltip = build_tool_tooltip(self._event)
            if tooltip:
                self.setToolTip(tooltip)

        # Image thumbnail (for file_attachment events)
        file_url = self._event.get("file_url")
        if file_url and file_url.startswith("data:image"):
            self._thumbnail = ImageThumbnail()
            self._thumbnail.set_image_url(file_url)
            self._thumbnail.clicked.connect(self._show_image_preview)
            layout.addWidget(self._thumbnail)

    def _format_type_label(self, event_type: str) -> str:
        """Format event type for display."""
        labels = {
            "user_prompt": "User Prompt",
            "reasoning": "Reasoning",
            "tool_call": "Tool Call",
            "tool_result": "Tool Result",
            "assistant_response": "Response",
            "patch": "Git Commit",
            "step_finish": "Step",
            "step_start": "Step Start",
            "delegation_start": "Delegation",
            "delegation_end": "Delegation End",
            "compaction": "Compaction",
            "file_attachment": "File",
        }
        return labels.get(event_type, event_type.replace("_", " ").title())

    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display (HH:MM:SS)."""
        if not timestamp:
            return ""
        # Handle ISO format: 2026-01-07T10:00:00Z
        if "T" in timestamp:
            time_part = timestamp.split("T")[1]
            return time_part[:8]  # HH:MM:SS
        return timestamp[:8] if len(timestamp) >= 8 else timestamp

    def _get_content_preview(self) -> str:
        """Get content preview based on event type."""
        event_type = self._event.get("type", "")
        event_data = self._event.get("event_data", {})

        if event_type == "user_prompt":
            content = event_data.get("content", "") or self._event.get("content", "")
            return self._truncate(content, 80)

        elif event_type == "reasoning":
            text = event_data.get("text", "") or self._event.get("text", "")
            return self._truncate(text, 80)

        elif event_type == "tool_call":
            # Use enriched title if available, fallback to tool_name
            label = get_tool_display_label(self._event)

            status = event_data.get("status", "") or self._event.get("status", "")
            status_icon = (
                "" if status == "completed" else "" if status == "error" else ""
            )
            return f"{label} {status_icon}"

        elif event_type == "assistant_response":
            content = event_data.get("content", "") or self._event.get("content", "")
            return self._truncate(content, 80)

        elif event_type == "patch":
            git_hash = event_data.get("git_hash", "") or self._event.get("git_hash", "")
            files = event_data.get("files", []) or self._event.get("files", [])
            file_count = len(files) if isinstance(files, list) else 0
            return f"{git_hash[:7]} ({file_count} files)" if git_hash else ""

        elif event_type in ("delegation_start", "delegation_end"):
            child_id = event_data.get("child_session_id", "")
            return f"Session: {child_id[:16]}..." if child_id else ""

        elif event_type == "delegation_result":
            result = event_data.get("result_summary", "") or self._event.get(
                "result_summary", ""
            )
            return self._truncate(result, 80)

        return ""

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if not text:
            return ""
        text = text.replace("\n", " ").strip()
        if len(text) > max_len:
            return text[: max_len - 3] + "..."
        return text

    def _show_image_preview(self, data_url: str) -> None:
        """Show full-size image preview dialog."""
        dialog = ImagePreviewDialog(data_url, self)
        dialog.exec()

    def mousePressEvent(self, event) -> None:
        """Handle click event."""
        self.clicked.emit(self._event)
        super().mousePressEvent(event)


class TimelineView(QWidget):
    """Displays chronological timeline of session events.

    Shows a scrollable list of TimelineEventWidget items,
    each styled according to its event type.
    """

    event_clicked = pyqtSignal(dict)  # Emitted when event is clicked

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._events: list[dict] = []
        self._event_widgets: list[TimelineEventWidget] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the main UI structure."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("Timeline")
        header.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
            padding: {SPACING["sm"]}px;
        """)
        layout.addWidget(header)

        # Summary label
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: 0 {SPACING["sm"]}px {SPACING["sm"]}px {SPACING["sm"]}px;
        """)
        layout.addWidget(self._summary)

        # Scroll area for events
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
            QScrollBar::handle:vertical:hover {{
                background-color: {COLORS["text_muted"]};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # Container for event widgets
        self._container = QWidget()
        self._container.setStyleSheet("background-color: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(
            SPACING["sm"], 0, SPACING["sm"], SPACING["sm"]
        )
        self._container_layout.setSpacing(SPACING["xs"])
        self._container_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll, stretch=1)

        # Empty state
        self._empty = QLabel("No events to display")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"""
            color: {COLORS["text_muted"]};
            font-size: {FONTS["size_sm"]}px;
            padding: {SPACING["xl"]}px;
        """)
        self._empty.hide()
        layout.addWidget(self._empty)

    def set_timeline(self, timeline: list[dict]) -> None:
        """Set timeline data and render events.

        Args:
            timeline: List of event dictionaries with type, timestamp, etc.
        """
        self._events = timeline or []
        self._clear_events()

        if not self._events:
            self._empty.show()
            self._summary.setText("No events recorded")
            return

        self._empty.hide()

        # Update summary
        event_counts = {}
        for event in self._events:
            event_type = event.get("type", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        summary_parts = [f"{len(self._events)} events"]
        if "tool_call" in event_counts:
            summary_parts.append(f"{event_counts['tool_call']} tools")
        if "reasoning" in event_counts:
            summary_parts.append(f"{event_counts['reasoning']} reasoning")
        self._summary.setText("  |  ".join(summary_parts))

        # Remove stretch before adding widgets
        if self._container_layout.count() > 0:
            item = self._container_layout.takeAt(self._container_layout.count() - 1)
            if item:
                del item

        # Create event widgets (limit to prevent UI freeze)
        max_events = 100
        for event in self._events[:max_events]:
            widget = self._create_event_widget(event)
            self._container_layout.addWidget(widget)
            self._event_widgets.append(widget)

        # Show truncation notice if needed
        if len(self._events) > max_events:
            notice = QLabel(f"... and {len(self._events) - max_events} more events")
            notice.setStyleSheet(f"""
                color: {COLORS["text_muted"]};
                font-size: {FONTS["size_sm"]}px;
                padding: {SPACING["sm"]}px;
            """)
            notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._container_layout.addWidget(notice)

        # Re-add stretch at the end
        self._container_layout.addStretch()

    def _create_event_widget(self, event: dict) -> TimelineEventWidget:
        """Create widget for a single event based on type.

        Args:
            event: Event dictionary with type, timestamp, content, etc.

        Returns:
            TimelineEventWidget configured for the event.
        """
        widget = TimelineEventWidget(event, self._container)
        widget.clicked.connect(self._on_event_clicked)
        return widget

    def _on_event_clicked(self, event: dict) -> None:
        """Handle event widget click."""
        self.event_clicked.emit(event)

    def _clear_events(self) -> None:
        """Clear all event widgets."""
        for widget in self._event_widgets:
            widget.deleteLater()
        self._event_widgets.clear()

        # Clear layout (except stretch)
        while self._container_layout.count() > 0:
            item = self._container_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def clear(self) -> None:
        """Clear the timeline view."""
        self._events = []
        self._clear_events()
        self._summary.setText("")
        self._empty.show()

    def get_events(self) -> list[dict]:
        """Get the current timeline events."""
        return self._events
