"""SessionOverviewPanel - Rich overview panel for root sessions.

Layout:
┌─────────────────────────────────────────────────────────────────────────┐
│ TIMELINE                                          TOOLS & FILES         │
│ ┌─────────────────────────────────────────┐  ┌────────────────────────┐ │
│ │ 10:30 💬 "Fix the auth bug..."          │  │ 🔧 Tools               │ │
│ │ 10:32 💬 "Now update the tests..."      │  │ ├─ read (15×)          │ │
│ │ 10:35 💬 "Run the full test suite"      │  │ ├─ edit (8×)           │ │
│ │ 10:38 💬 "Great, commit the changes"    │  │ └─ bash (3×)           │ │
│ │                                         │  ├────────────────────────┤ │
│ │                                         │  │ 📁 Files (12)          │ │
│ │                                         │  │ ├─ src/auth.py         │ │
│ │                                         │  │ └─ +10 more            │ │
│ └─────────────────────────────────────────┘  └────────────────────────┘ │
│ ⚠️ 1 error: mcp_bash failed at 10:36                                    │
└─────────────────────────────────────────────────────────────────────────┘
"""

import difflib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from opencode_status_bar.utils.logger import logger

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from opencode_status_bar.dashboard.sections.tracing.enriched_helpers import (
    get_tool_display_label,
)
from opencode_status_bar.dashboard.sections.tracing.helpers import format_tokens_short
from opencode_status_bar.dashboard.styles import COLORS, FONTS, RADIUS, SPACING
from opencode_status_bar.dashboard.widgets.controls import ClickableLabel


# ============================================================
# DATA CLASSES
# ============================================================


@dataclass
class Exchange:
    """Represents a user exchange in the timeline."""

    timestamp: str
    prompt: str
    agent: str = ""
    tool_count: int = 0


@dataclass
class ToolUsage:
    """Represents a tool usage."""

    name: str
    count: int
    targets: list[str] = field(default_factory=list)


@dataclass
class FileAction:
    """Represents a file action."""

    path: str
    action: str  # read, edit, write


@dataclass
class ErrorInfo:
    """Represents an error."""

    timestamp: str
    tool_name: str
    message: str


@dataclass
class SessionData:
    """Aggregated session data."""

    exchanges: list[Exchange] = field(default_factory=list)
    tools: Counter = field(default_factory=Counter)
    tool_targets: dict[str, list[str]] = field(default_factory=dict)
    files: dict[str, list[str]] = field(default_factory=dict)  # action -> [paths]
    errors: list[ErrorInfo] = field(default_factory=list)


# ============================================================
# HELPERS
# ============================================================


def format_time(datetime_str: str | None) -> str:
    """Format datetime to HH:MM."""
    if not datetime_str:
        return ""
    try:
        if "T" in datetime_str:
            dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(datetime_str)
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def truncate_text(text: str | None, max_length: int = 50) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def shorten_tool_name(name: str) -> str:
    """Shorten tool name by removing mcp_ prefix."""
    return name.replace("mcp_", "").replace("lsmcp-typescript_", "ts:")


def extract_file_from_display_info(display_info: str | None) -> str | None:
    """Extract file path from tool display_info."""
    if not display_info:
        return None
    # Handle formats like "src/file.py:L45" or just "src/file.py"
    path = display_info.split(":")[0].strip()
    # Skip if it looks like a command or not a path
    if " " in path or not path:
        return None
    return path


def classify_tool_action(tool_name: str) -> str | None:
    """Classify tool as read/edit/write action."""
    name_lower = tool_name.lower()
    if "read" in name_lower or "glob" in name_lower or "grep" in name_lower:
        return "read"
    if "edit" in name_lower:
        return "edit"
    if "write" in name_lower:
        return "write"
    return None


# ============================================================
# DATA EXTRACTION
# ============================================================


def extract_session_data(tree_data: dict) -> SessionData:
    """Extract structured data from tree_data recursively."""
    data = SessionData()
    _extract_from_node(tree_data, data)
    return data


def _extract_from_node(node: dict, data: SessionData) -> None:
    """Process a node and extract relevant data."""
    node_type = node.get("node_type", "")

    # Extract exchanges (user_turn)
    if node_type == "user_turn":
        prompt = node.get("prompt_input", "") or node.get("title", "")
        timestamp = node.get("started_at", "") or node.get("created_at", "")
        agent = node.get("agent", "")

        # Count tools in this exchange
        tool_count = sum(
            1 for child in node.get("children", []) if child.get("node_type") == "tool"
        )

        data.exchanges.append(
            Exchange(
                timestamp=timestamp,
                prompt=prompt,
                agent=agent,
                tool_count=tool_count,
            )
        )

    # Extract tools
    elif node_type == "tool":
        tool_name = (
            node.get("tool_name", "") or node.get("title", "") or node.get("name", "")
        )
        if tool_name:
            data.tools[tool_name] += 1

            # Track targets (display_info)
            display_info = node.get("display_info", "")
            if display_info:
                if tool_name not in data.tool_targets:
                    data.tool_targets[tool_name] = []
                if display_info not in data.tool_targets[tool_name]:
                    data.tool_targets[tool_name].append(display_info)

            # Extract file if applicable
            action = classify_tool_action(tool_name)
            if action:
                file_path = extract_file_from_display_info(display_info)
                if file_path:
                    if action not in data.files:
                        data.files[action] = []
                    if file_path not in data.files[action]:
                        data.files[action].append(file_path)

        tool_status = node.get("tool_status") or node.get("status") or ""
        is_error = tool_status == "error"
        if is_error:
            timestamp = node.get("started_at", "") or node.get("created_at", "")
            error_msg = node.get("error") or node.get("display_info") or ""
            if not error_msg:
                error_msg = f"{tool_name} failed"
            data.errors.append(
                ErrorInfo(
                    timestamp=timestamp,
                    tool_name=tool_name,
                    message=str(error_msg),
                )
            )

    elif node.get("status") == "error":
        timestamp = node.get("started_at", "") or node.get("created_at", "")
        title = node.get("subagent_type") or node.get("title") or node_type
        error_msg = node.get("error") or node.get("prompt_output") or ""
        if not error_msg:
            error_msg = f"{title} failed"
        data.errors.append(
            ErrorInfo(
                timestamp=timestamp,
                tool_name=title,
                message=str(error_msg),
            )
        )

    # Recurse into children
    for child in node.get("children", []):
        _extract_from_node(child, data)


# ============================================================
# EXPANDABLE TIMELINE WIDGET
# ============================================================


# Event type configuration for visual styling
EVENT_CONFIG = {
    "user_prompt": {"icon": "💬", "color": COLORS["accent_primary"]},
    "delegation_result": {"icon": "📥", "color": COLORS["tree_child"]},
    "reasoning": {"icon": "🧠", "color": COLORS["warning"]},
    "tool_call": {"icon": "🔧", "color": COLORS["info"]},
    "step_finish": {"icon": "⏱️", "color": COLORS["text_muted"]},
    "assistant_response": {"icon": "✅", "color": COLORS["success"]},
    "delegation": {"icon": "🤖", "color": COLORS["tree_child"]},
}


class TimelineEventWidget(QFrame):
    """Single event item (reasoning, tool_call, response)."""

    def __init__(
        self,
        event: dict,
        parent: QWidget | None = None,
        is_delegation: bool = False,
        child_timeline: list[dict] | None = None,
        depth: int = 0,
    ):
        super().__init__(parent)
        self._event = event
        self._is_delegation = is_delegation
        self._child_timeline = child_timeline
        self._depth = depth
        self._child_container: QWidget | None = None
        self._is_child_expanded = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        event_type = self._event.get("type", "unknown")

        # Check if this is a delegation (tool_call with child_session_id)
        if event_type == "tool_call" and self._event.get("child_session_id"):
            event_type = "delegation"
            self._is_delegation = True

        config = EVENT_CONFIG.get(
            event_type, {"icon": "•", "color": COLORS["text_muted"]}
        )
        icon = config["icon"]
        color = config["color"]

        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 2px 0;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Row container
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SPACING["sm"], 2, SPACING["xs"], 2)
        row_layout.setSpacing(SPACING["xs"])

        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {FONTS['size_sm']}px;")
        icon_label.setFixedWidth(20)
        row_layout.addWidget(icon_label)

        # Content based on type
        content = self._get_content_text(event_type)
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {color};
            font-family: {FONTS["mono"]};
        """)
        row_layout.addWidget(content_label, 1)

        # Expand button for delegations with child timeline
        if self._is_delegation and self._child_timeline:
            expand_btn = QLabel("▶")
            expand_btn.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
            """)
            expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            expand_btn.mousePressEvent = lambda ev: self._toggle_child()
            self._expand_btn = expand_btn
            row_layout.addWidget(expand_btn)

        main_layout.addWidget(row)

        # Child timeline container (hidden by default)
        if self._is_delegation and self._child_timeline:
            self._child_container = QFrame()
            self._child_container.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS["tree_child_bg"]};
                    border-left: 2px solid {COLORS["tree_child"]};
                    margin-left: {SPACING["md"]}px;
                }}
            """)
            child_layout = QVBoxLayout(self._child_container)
            child_layout.setContentsMargins(
                SPACING["sm"], SPACING["xs"], 0, SPACING["xs"]
            )
            child_layout.setSpacing(2)

            # Add child events (limit depth)
            if self._depth < 2:  # Max 2 levels of nesting
                for child_event in self._child_timeline[:10]:  # Limit to 10 events
                    child_widget = TimelineEventWidget(
                        event=child_event,
                        parent=self._child_container,
                        depth=self._depth + 1,
                    )
                    child_layout.addWidget(child_widget)

                if len(self._child_timeline) > 10:
                    more_label = QLabel(
                        f"... +{len(self._child_timeline) - 10} more events"
                    )
                    more_label.setStyleSheet(f"""
                        font-size: {FONTS["size_xs"]}px;
                        color: {COLORS["text_muted"]};
                        padding-left: {SPACING["md"]}px;
                    """)
                    child_layout.addWidget(more_label)

            self._child_container.hide()
            main_layout.addWidget(self._child_container)

        # Add tooltip with full details
        self._set_tooltip(event_type)

    def _toggle_child(self) -> None:
        """Toggle child timeline visibility."""
        if self._child_container:
            self._is_child_expanded = not self._is_child_expanded
            self._child_container.setVisible(self._is_child_expanded)
            if hasattr(self, "_expand_btn"):
                self._expand_btn.setText("▼" if self._is_child_expanded else "▶")

    def _get_content_text(self, event_type: str) -> str:
        """Get display text based on event type.

        Note: No truncation here - this content is shown in expanded view
        where users want to see the full content. Word wrap handles display.
        """
        if event_type == "user_prompt":
            return self._event.get("content", "") or ""

        elif event_type == "delegation_result":
            return self._event.get("content", "") or ""

        elif event_type == "reasoning":
            entries = self._event.get("entries", [])
            if entries:
                # Show all reasoning entries, not just the first one
                return "\n\n".join(e.get("text", "") for e in entries if e.get("text"))
            return "Thinking..."

        elif event_type == "tool_call":
            tool_name = self._event.get("tool_name", "")
            if tool_name == "task":
                return get_tool_display_label(self._event)
            tool_name = shorten_tool_name(tool_name)
            display = self._event.get("display_info", "") or self._event.get(
                "arguments", ""
            )
            if display:
                return f"{tool_name}: {display}"
            return tool_name

        elif event_type == "delegation":
            tool_name = self._event.get("tool_name", "agent")
            if tool_name == "task":
                return f"→ {get_tool_display_label(self._event)}"
            return f"→ {shorten_tool_name(tool_name)}"

        elif event_type == "step_finish":
            tokens = self._event.get("tokens", {})
            total = tokens.get("total", 0) if isinstance(tokens, dict) else 0
            cost = self._event.get("cost", 0)
            if total and cost:
                return f"tokens: {format_tokens_short(total)} · ${cost:.4f}"
            elif total:
                return f"tokens: {format_tokens_short(total)}"
            return "step complete"

        elif event_type == "assistant_response":
            return self._event.get("content", "") or ""

        return str(self._event)

    def _set_tooltip(self, event_type: str) -> None:
        """Set tooltip with full details."""
        if event_type == "reasoning":
            entries = self._event.get("entries", [])
            if entries:
                full_text = "\n\n".join(
                    (e.get("text") or "")[:500] for e in entries[:3]
                )
                self.setToolTip(full_text)

        elif event_type in ["tool_call", "delegation"]:
            tool = self._event.get("tool_name", "")
            args = self._event.get("arguments", "")
            result = self._event.get("result_summary", "")
            tooltip = f"Tool: {tool}"
            if args:
                tooltip += f"\nArgs: {str(args)[:200]}"
            if result:
                tooltip += f"\nResult: {str(result)[:200]}"
            self.setToolTip(tooltip)

        elif event_type == "assistant_response":
            content = self._event.get("content", "")
            self.setToolTip(content[:500] if content else "")


class ExchangeGroupWidget(QFrame):
    """Single exchange with collapse/expand functionality."""

    def __init__(
        self,
        exchange_number: int,
        events: list[dict],
        parent: QWidget | None = None,
        is_expanded: bool = False,
        delegations: dict | None = None,
    ):
        super().__init__(parent)
        self._exchange_number = exchange_number
        self._events = events
        self._is_expanded = is_expanded
        self._delegations = delegations or {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame#exchangeGroup {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["sm"]}px;
                margin-bottom: 2px;
            }}
            QFrame#exchangeGroup:hover {{
                border-color: {COLORS["border_default"]};
            }}
        """)
        self.setObjectName("exchangeGroup")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header (clickable)
        self._header = QFrame()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.mousePressEvent = lambda a0: self.toggle()
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(
            SPACING["xs"], SPACING["xs"], SPACING["sm"], SPACING["xs"]
        )
        header_layout.setSpacing(SPACING["xs"])

        # Toggle arrow
        self._arrow = QLabel("▶")
        self._arrow.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        self._arrow.setFixedWidth(16)
        header_layout.addWidget(self._arrow)

        # Find user_prompt or delegation_result for header content
        header_event = self._find_header_event()
        if header_event:
            time_str = format_time(header_event.get("timestamp", ""))
            prompt_text = truncate_text(header_event.get("content", ""), 60)
            icon = self._get_header_icon(header_event)
            header_text = (
                f"{time_str}  {icon} {prompt_text}"
                if time_str
                else f"{icon} {prompt_text}"
            )
        else:
            header_text = f"Exchange #{self._exchange_number}"

        self._header_label = QLabel(header_text)
        self._header_label.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_primary"]};
        """)
        self._header_label.setWordWrap(True)
        header_layout.addWidget(self._header_label, 1)

        # Event count badge (exclude header events)
        non_prompt_events = [
            e
            for e in self._events
            if e.get("type") not in ("user_prompt", "delegation_result")
        ]
        if non_prompt_events:
            count_label = QLabel(f"({len(non_prompt_events)})")
            count_label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
            """)
            header_layout.addWidget(count_label)

        main_layout.addWidget(self._header)

        # Content (expandable)
        self._content = QFrame()
        self._content.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_elevated"]};
                border-top: 1px solid {COLORS["border_subtle"]};
            }}
        """)
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(
            SPACING["md"], SPACING["xs"], SPACING["xs"], SPACING["xs"]
        )
        content_layout.setSpacing(0)

        event_count = 0
        for event in self._events:
            event_type = event.get("type")
            is_from_child = event.get("from_child_session")

            if event_type == "delegation_result" and is_from_child:
                continue

            child_timeline = None
            child_session_id = event.get("child_session_id")
            if child_session_id and child_session_id in self._delegations:
                child_timeline = self._delegations[child_session_id].get("timeline", [])

            event_widget = TimelineEventWidget(
                event=event,
                parent=self,
                child_timeline=child_timeline,
            )
            content_layout.addWidget(event_widget)
            event_count += 1

        main_layout.addWidget(self._content)

        # Initial state
        self._update_state()

    def _find_header_event(self) -> dict | None:
        for event in self._events:
            if event.get("type") in ("user_prompt", "delegation_result"):
                return event
        return None

    def _is_from_child_session(self) -> bool:
        return any(event.get("from_child_session") for event in self._events)

    def _get_header_icon(self, header_event: dict) -> str:
        if header_event.get("type") == "delegation_result":
            return "📥"
        if self._is_from_child_session():
            return "🔗"
        return "💬"

    def toggle(self) -> None:
        """Toggle expand/collapse state."""
        self._is_expanded = not self._is_expanded
        self._update_state()

    def _update_state(self) -> None:
        """Update visual state based on expanded/collapsed."""
        self._content.setVisible(self._is_expanded)
        self._arrow.setText("▼" if self._is_expanded else "▶")


class ExpandableTimelineWidget(QFrame):
    """Timeline with expandable exchange groups."""

    exchange_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._exchange_widgets: list[ExchangeGroupWidget] = []
        self._delegations: dict = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        header = QLabel("💬 Timeline")
        header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(SPACING["xs"])
        self._container_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

    def load_timeline_full(self, data: dict) -> None:
        """Load from /timeline/full API response."""
        # Clear existing
        self._clear_content()

        timeline = data.get("timeline", [])
        self._delegations = {
            d.get("child_session_id"): d
            for d in data.get("delegations", [])
            if d.get("child_session_id")
        }

        if not timeline:
            self._show_empty_state()
            return

        # Group events by exchange_number
        groups = self._group_by_exchange(timeline)

        # Create exchange widgets
        for exchange_num in sorted(groups.keys()):
            events = groups[exchange_num]
            widget = ExchangeGroupWidget(
                exchange_number=exchange_num,
                events=events,
                parent=self._container,
                is_expanded=False,
                delegations=self._delegations,
            )
            # Insert before the stretch
            self._container_layout.insertWidget(
                self._container_layout.count() - 1, widget
            )
            self._exchange_widgets.append(widget)

    def _group_by_exchange(self, timeline: list[dict]) -> dict[int, list[dict]]:
        """Group events by exchange_number, preserving API order."""
        groups: dict[int, list[dict]] = {}
        for event in timeline:
            num = event.get("exchange_number", 0)
            if num not in groups:
                groups[num] = []
            groups[num].append(event)

        return groups

    def _clear_content(self) -> None:
        """Clear all exchange widgets."""
        for widget in self._exchange_widgets:
            widget.deleteLater()
        self._exchange_widgets.clear()

    def _show_empty_state(self) -> None:
        """Show empty state message."""
        label = QLabel("No timeline events")
        label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
            padding: {SPACING["sm"]}px;
        """)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._container_layout.insertWidget(0, label)

    def clear(self) -> None:
        """Clear the timeline and show empty state."""
        self._clear_content()
        self._show_empty_state()


# ============================================================
# TOOLS BREAKDOWN WIDGET
# ============================================================


class ToolsBreakdownWidget(QFrame):
    """List of tools used with counts."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        self._header = QLabel("🔧 Tools")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self._header)

        # Container for tool labels
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidget(self._container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

    def load_tools(self, tools: Counter, tool_targets: dict[str, list[str]]) -> None:
        """Load tools into the breakdown."""
        # Clear existing
        count = self._container_layout.count()
        for _ in range(count):
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not tools:
            label = QLabel("No tools used")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)
            self._container_layout.addStretch()
            return

        total = sum(tools.values())
        self._header.setText(f"🔧 Tools ({total})")

        # Sort by count descending
        sorted_tools = tools.most_common()
        for i, (tool_name, count) in enumerate(sorted_tools):
            short_name = shorten_tool_name(tool_name)
            targets = tool_targets.get(tool_name, [])
            prefix = "└─" if i == len(sorted_tools) - 1 else "├─"

            label = QLabel(f"{prefix} {short_name} ({count}×)")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)

            # Tooltip with targets
            if targets:
                tooltip = f"{tool_name}\n\nTargets:\n" + "\n".join(
                    f"  • {t}" for t in targets[:5]
                )
                if len(targets) > 5:
                    tooltip += f"\n  ... +{len(targets) - 5} more"
                label.setToolTip(tooltip)
            else:
                label.setToolTip(tool_name)

            self._container_layout.addWidget(label)

        self._container_layout.addStretch()


# ============================================================
# FILES LIST WIDGET
# ============================================================


class FilesListWidget(QFrame):
    """List of files touched by actions."""

    diff_requested = pyqtSignal(str)  # Emits session_id when diff export is requested

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._files: list[dict] = []
        self._total_additions: int = 0
        self._total_deletions: int = 0
        self._session_id: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["xs"])

        self._header = QLabel("📁 Files")
        self._header.setStyleSheet(f"""
            QLabel {{
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                color: {COLORS["text_muted"]};
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: {SPACING["xs"]}px;
            }}
        """)
        header_layout.addWidget(self._header, 1)

        self._export_btn = ClickableLabel("📋")
        self._export_btn.setStyleSheet(f"""
            QLabel {{
                font-size: {FONTS["size_sm"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
            }}
            QLabel:hover {{
                background-color: {COLORS["bg_hover"]};
                color: {COLORS["text_primary"]};
            }}
        """)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setToolTip("Export diff")
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.hide()
        header_layout.addWidget(self._export_btn)

        layout.addWidget(header_container)

        # Container
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._container)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._scroll, 1)

    def _on_export_clicked(self) -> None:
        if self._session_id:
            self.diff_requested.emit(self._session_id)

    def _update_header_text(self, total_files: int) -> None:
        base_text = f"📁 Files ({total_files})"

        if self._total_additions > 0 or self._total_deletions > 0:
            stats_html = f'<span style="color: {COLORS["success"]};">+{self._total_additions}</span> <span style="color: {COLORS["error"]};">-{self._total_deletions}</span>'
            self._header.setText(f"{base_text} {stats_html}")
        else:
            self._header.setText(base_text)

    def load_files(
        self,
        files: list[dict],
        session_id: str | None = None,
    ) -> None:
        self._files = files
        self._session_id = session_id
        self._total_additions = sum(f.get("additions", 0) for f in files)
        self._total_deletions = sum(f.get("deletions", 0) for f in files)

        has_diff_stats = self._total_additions > 0 or self._total_deletions > 0
        if has_diff_stats:
            self._export_btn.show()
        else:
            self._export_btn.hide()

        self._render_files()

    def _render_files(self) -> None:
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._files:
            label = QLabel("No files accessed")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)
            self._container_layout.addStretch()
            self._header.setText("📁 Files")
            return

        self._update_header_text(len(self._files))

        action_config = {
            "read": ("📖", COLORS["type_read"]),
            "edit": ("✏️", COLORS["type_edit"]),
            "write": ("📝", COLORS["type_write"]),
        }

        sorted_files = sorted(
            self._files,
            key=lambda f: (
                0
                if f.get("operation") == "edit"
                else 1
                if f.get("operation") == "write"
                else 2
            ),
        )

        for file_info in sorted_files:
            path = file_info.get("path", "")
            operation = file_info.get("operation", "read")
            additions = file_info.get("additions", 0)
            deletions = file_info.get("deletions", 0)

            icon, color = action_config.get(operation, ("📄", COLORS["text_secondary"]))
            short_path = "/".join(path.split("/")[-2:]) if "/" in path else path

            if additions > 0 or deletions > 0:
                stats_text = f'<span style="color: {COLORS["success"]};">+{additions}</span> <span style="color: {COLORS["error"]};">-{deletions}</span>'
                label = QLabel(f"{icon} {short_path}  {stats_text}")
            else:
                label = QLabel(f"{icon} {short_path}")

            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {color};
                padding: 2px {SPACING["xs"]}px;
            """)
            label.setToolTip(f"{operation.capitalize()}: {path}")
            self._container_layout.addWidget(label)

        self._container_layout.addStretch()


# ============================================================
# TOKENS WIDGET
# ============================================================


class TokensWidget(QFrame):
    """Display token usage breakdown."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        self._header = QLabel("🎫 Tokens")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self._header)

        # Container
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)
        layout.addWidget(self._container)

    def load_tokens(
        self,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cache_read: int | None = None,
        cache_write: int | None = None,
    ) -> None:
        """Load token stats."""
        # Clear existing
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if (
            tokens_in is None
            and tokens_out is None
            and cache_read is None
            and cache_write is None
        ):
            label = QLabel("No token data")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)
            return

        # Calculate total
        total = (
            (tokens_in or 0)
            + (tokens_out or 0)
            + (cache_read or 0)
            + (cache_write or 0)
        )

        # Add token breakdown
        if tokens_in is not None and tokens_in > 0:
            label = QLabel(f"├─ Input: {format_tokens_short(tokens_in)}")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        if tokens_out is not None and tokens_out > 0:
            label = QLabel(f"├─ Output: {format_tokens_short(tokens_out)}")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        if cache_read is not None and cache_read > 0:
            label = QLabel(f"├─ Cache Read: {format_tokens_short(cache_read)}")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        if cache_write is not None and cache_write > 0:
            label = QLabel(f"├─ Cache Write: {format_tokens_short(cache_write)}")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        # Total
        total_label = QLabel(f"└─ Total: {format_tokens_short(total)}")
        total_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-family: {FONTS["mono"]};
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
            padding: 2px {SPACING["xs"]}px;
        """)
        self._container_layout.addWidget(total_label)


# ============================================================
# AGENTS WIDGET
# ============================================================


class AgentsWidget(QFrame):
    """Display agents/delegations used."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        self._header = QLabel("🤖 Agents")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self._header)

        # Container
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidget(self._container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

    def load_agents(self, agents: list[dict[str, Any]]) -> None:
        """Load agents from tree data.

        Args:
            agents: List of dicts with 'agent_type' and optional 'count'
        """
        # Clear existing
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not agents:
            label = QLabel("No agents used")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)
            self._container_layout.addStretch()
            return

        # Count agents
        agent_counter: Counter = Counter()
        for agent in agents:
            agent_type = agent.get("agent_type", "unknown")
            agent_counter[agent_type] += 1

        total = len(agents)
        self._header.setText(f"🤖 Agents ({total})")

        # Display agents with counts
        agents_list = agent_counter.most_common()
        for i, (agent_type, count) in enumerate(agents_list):
            prefix = "├─" if i < len(agents_list) - 1 else "└─"
            text = f"{prefix} {agent_type}"
            if count > 1:
                text += f" ({count}×)"

            label = QLabel(text)
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        self._container_layout.addStretch()


# ============================================================
# ERRORS WIDGET
# ============================================================


def classify_error_type(message: str) -> tuple[str, str, str]:
    msg_lower = message.lower()

    if "timeout" in msg_lower or "aborted" in msg_lower or "timed out" in msg_lower:
        return ("timeout", COLORS["warning"], "TIMEOUT")
    elif any(
        kw in msg_lower
        for kw in ("auth", "permission", "403", "401", "forbidden", "rejected")
    ):
        return ("auth", COLORS["error"], "AUTH")
    elif any(
        kw in msg_lower for kw in ("network", "connection", "certificate", "ssl", "dns")
    ):
        return ("network", COLORS["warning"], "NETWORK")
    elif "not found" in msg_lower or "404" in msg_lower:
        return ("not_found", COLORS["info"], "NOT FOUND")
    elif "syntax" in msg_lower or "parse" in msg_lower:
        return ("syntax", COLORS["warning"], "SYNTAX")
    elif "rate" in msg_lower or "429" in msg_lower or "too many" in msg_lower:
        return ("rate_limit", COLORS["warning"], "RATE LIMIT")
    else:
        return ("unknown", COLORS["text_muted"], "ERROR")


class ErrorItemWidget(QFrame):
    def __init__(self, error: ErrorInfo, prefix: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._error = error
        self._prefix = prefix
        self._is_expanded = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        row = QFrame()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.mousePressEvent = lambda a0: self._toggle_expand()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SPACING["xs"], 2, SPACING["xs"], 2)
        row_layout.setSpacing(SPACING["xs"])

        prefix_label = QLabel(self._prefix)
        prefix_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-family: {FONTS["mono"]};
            color: {COLORS["border_default"]};
        """)
        prefix_label.setFixedWidth(20)
        row_layout.addWidget(prefix_label)

        time_str = format_time(self._error.timestamp)
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-family: {FONTS["mono"]};
            color: {COLORS["text_muted"]};
        """)
        time_label.setFixedWidth(40)
        row_layout.addWidget(time_label)

        tool_short = shorten_tool_name(self._error.tool_name)
        tool_label = QLabel(truncate_text(tool_short, 20))
        tool_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-family: {FONTS["mono"]};
            color: {COLORS["text_secondary"]};
        """)
        tool_label.setFixedWidth(120)
        tool_label.setToolTip(self._error.tool_name)
        row_layout.addWidget(tool_label)

        error_type, error_color, badge_text = classify_error_type(self._error.message)
        badge = QLabel(badge_text)
        badge.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-family: {FONTS["mono"]};
            font-weight: {FONTS["weight_semibold"]};
            color: {error_color};
            padding: 2px 6px;
            border-radius: {RADIUS["sm"]}px;
        """)
        row_layout.addWidget(badge)

        preview = truncate_text(self._error.message, 50)
        self._preview_label = QLabel(preview)
        self._preview_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_secondary"]};
        """)
        self._preview_label.setWordWrap(False)
        row_layout.addWidget(self._preview_label, 1)

        self._arrow = QLabel("▶")
        self._arrow.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        self._arrow.setFixedWidth(16)
        row_layout.addWidget(self._arrow)

        layout.addWidget(row)

        self._full_message = QLabel(self._error.message)
        self._full_message.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-family: {FONTS["mono"]};
            color: {error_color};
            background-color: {COLORS["bg_elevated"]};
            padding: {SPACING["xs"]}px;
            border-radius: {RADIUS["sm"]}px;
            margin-left: 40px;
        """)
        self._full_message.setWordWrap(True)
        self._full_message.hide()
        layout.addWidget(self._full_message)

    def _toggle_expand(self) -> None:
        self._is_expanded = not self._is_expanded
        self._full_message.setVisible(self._is_expanded)
        self._arrow.setText("▼" if self._is_expanded else "▶")


class ErrorsWidget(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._errors: list[ErrorInfo] = []
        self._is_expanded = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        header_frame = QFrame()
        header_frame.setCursor(Qt.CursorShape.PointingHandCursor)
        header_frame.mousePressEvent = lambda a0: self._toggle_expand()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["xs"])

        self._header = QLabel("⚠️ ERRORS")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(self._header, 1)

        self._arrow = QLabel("▶")
        self._arrow.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        header_layout.addWidget(self._arrow)

        layout.addWidget(header_frame)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._container)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMinimumHeight(300)
        self._scroll.setMaximumHeight(400)
        self._scroll.hide()
        layout.addWidget(self._scroll)

    def _toggle_expand(self) -> None:
        if not self._errors:
            return

        self._is_expanded = not self._is_expanded
        self._scroll.setVisible(self._is_expanded)
        self._arrow.setText("▼" if self._is_expanded else "▶")

    def load_errors(self, errors: list[ErrorInfo]) -> None:
        self._errors = errors

        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not errors:
            self.hide()
            return

        count = len(errors)
        self._header.setText(f"⚠️ ERRORS ({count})")

        for i, error in enumerate(errors):
            prefix = "└─" if i == len(errors) - 1 else "├─"
            item = ErrorItemWidget(error, prefix, self._container)
            self._container_layout.addWidget(item)

        self._container_layout.addStretch()

        self._is_expanded = False
        self._scroll.hide()
        self._arrow.setText("▶")

        self.show()


# ============================================================
# DATA AGGREGATION HELPERS
# ============================================================


def _collect_agents_recursive(node: dict, agents: list[dict], depth: int = 0) -> None:
    """Recursively collect all agents/delegations from tree.

    Args:
        node: Current tree node
        agents: List to append found agents to (mutated)
        depth: Current recursion depth (for logging)
    """
    node_type = node.get("node_type", "")
    agent_type = node.get("agent_type", "")

    # Collect agent/delegation nodes (old way - kept for compatibility)
    if node_type in ["delegation", "agent"]:
        if agent_type:
            agents.append(node)

    # NEW: Collect agents from user_turn nodes (where agent responds)
    if node_type == "user_turn":
        agent = node.get("agent") or node.get("subagent_type")
        if agent:
            # Only add if not "assistant" (which is the default)
            if agent != "assistant":
                agents.append({"agent_type": agent, "node_type": "user_turn_agent"})

    # Recurse into children
    for child in node.get("children", []):
        _collect_agents_recursive(child, agents, depth + 1)


# ============================================================
# MAIN PANEL
# ============================================================


class SessionOverviewPanel(QFrame):
    """Rich overview panel for root sessions with timeline, tools, and files."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame#sessionOverview {{
                background-color: {COLORS["bg_base"]};
                border: none;
            }}
        """)
        self.setObjectName("sessionOverview")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(SPACING["xs"])

        # Main content: 2 columns
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent;
                width: 4px;
            }
        """)

        # Left column: Timeline (60%) - Use expandable widget
        self._timeline = ExpandableTimelineWidget()
        splitter.addWidget(self._timeline)

        # Right column: Tools + Files + Tokens + Agents (40%)
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACING["xs"])

        self._tools = ToolsBreakdownWidget()
        right_layout.addWidget(self._tools, 1)

        self._files = FilesListWidget()
        self._files.diff_requested.connect(self._on_diff_requested)
        right_layout.addWidget(self._files, 1)

        self._tokens = TokensWidget()
        right_layout.addWidget(self._tokens)

        self._agents = AgentsWidget()
        right_layout.addWidget(self._agents, 1)

        right_layout.addStretch()  # Push widgets to top

        splitter.addWidget(right_column)

        # Set initial sizes (60/40 ratio)
        splitter.setSizes([600, 400])
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter, 1)

        # Bottom: Errors (conditional)
        self._errors = ErrorsWidget()
        self._errors.hide()
        main_layout.addWidget(self._errors)

    def load_session(self, tree_data: dict) -> None:
        """Load session data and display rich overview."""
        data = extract_session_data(tree_data)

        tokens = tree_data.get("tokens") or {}
        tokens_in = tokens.get("input", 0) if isinstance(tokens, dict) else 0
        tokens_out = tokens.get("output", 0) if isinstance(tokens, dict) else 0
        cache_read = tokens.get("cache_read", 0) if isinstance(tokens, dict) else 0
        cache_write = tokens.get("cache_write", 0) if isinstance(tokens, dict) else 0

        agents = []
        _collect_agents_recursive(tree_data, agents)

        session_id = tree_data.get("session_id")
        if session_id:
            self._load_extended_timeline(session_id)
            files_with_stats = self._load_files_from_api(session_id)
        else:
            logger.warning("[Timeline] No session_id in tree_data")
            self._timeline.clear()
            files_with_stats = []

        self._tools.load_tools(data.tools, data.tool_targets)
        self._files.load_files(files_with_stats, session_id)
        self._tokens.load_tokens(tokens_in, tokens_out, cache_read, cache_write)
        self._agents.load_agents(agents)
        self._errors.load_errors(data.errors)

    def _load_files_from_api(self, session_id: str) -> list[dict]:
        from opencode_status_bar.api import get_api_client

        client = get_api_client()
        if not client.is_available:
            return []

        data = client.get_session_files(session_id)
        if not data:
            return []

        details = data.get("details", {})
        return details.get("files_with_stats", [])

    def _load_extended_timeline(self, session_id: str) -> None:
        """Load full timeline from API.

        Args:
            session_id: Session ID to load
        """
        from opencode_status_bar.api import get_api_client

        client = get_api_client()
        if not client.is_available:
            logger.warning("[Timeline] API not available")
            return

        data = client.get_session_timeline_full(session_id)
        if not data:
            logger.warning(f"[Timeline] No data returned for session {session_id}")
            return

        self._timeline.load_timeline_full(data)

    def clear(self) -> None:
        """Reset the panel to empty state."""
        self._timeline.clear()
        self._tools.load_tools(Counter(), {})
        self._files.load_files([])
        self._tokens.load_tokens()
        self._agents.load_agents([])
        self._errors.load_errors([])

    def _on_diff_requested(self, session_id: str) -> None:
        """Handle diff export request - load diff and copy to clipboard as git patch."""
        OPENCODE_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage"
        diff_file = OPENCODE_STORAGE / "session_diff" / f"{session_id}.json"

        if not diff_file.exists():
            logger.warning(f"[Diff] No diff file found: {diff_file}")
            return

        try:
            with open(diff_file) as f:
                diff_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"[Diff] Failed to load diff file: {e}")
            return

        if not diff_data:
            logger.info("[Diff] No changes in session")
            return

        patch_lines: list[str] = []
        for entry in diff_data:
            file_path = entry.get("file", "unknown")
            before = entry.get("before", "")
            after = entry.get("after", "")

            before_lines = before.splitlines(keepends=True)
            after_lines = after.splitlines(keepends=True)

            if before_lines and not before_lines[-1].endswith("\n"):
                before_lines[-1] += "\n"
            if after_lines and not after_lines[-1].endswith("\n"):
                after_lines[-1] += "\n"

            patch_lines.append(f"diff --git a/{file_path} b/{file_path}\n")

            diff = difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
            patch_lines.extend(diff)

        if not patch_lines:
            logger.info("[Diff] No differences found")
            return

        patch_text = "".join(patch_lines)

        # Copy to clipboard
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(patch_text)
            logger.info(f"[Diff] Copied {len(patch_lines)} lines to clipboard")
