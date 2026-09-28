"""
TraceDetailPanel - Panel showing detailed trace/session information with tabs.

Features:
- 6 tabs: Transcript, Tokens, Tools, Files, Agents, Timeline
- Lazy loading: only loads data for the active tab
- TracingDataService integration
- Scrollable content for overflow handling
"""

import os
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QTabWidget,
    QScrollArea,
    QStackedWidget,
)
from PyQt6.QtCore import Qt

from opencode_status_bar.dashboard.styles import COLORS, SPACING, FONTS, RADIUS

from ..helpers import format_duration, format_tokens_short
from ..tabs import (
    TokensTab,
    ToolsTab,
    FilesTab,
    AgentsTab,
    TimelineTab,
    TranscriptTab,
    DelegationsTab,
)
from .components import SessionOverviewPanel, DelegationTranscriptPanel
from .handlers import DataLoaderMixin
from .strategies import PanelContent

if TYPE_CHECKING:
    from opencode_status_bar.analytics import TracingDataService


class TraceDetailPanel(DataLoaderMixin, QFrame):
    """Panel showing detailed trace/session information with tabbed sections."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("trace-detail")
        self.setMinimumWidth(400)

        # State
        self._service: Optional["TracingDataService"] = None
        self._current_session_id: Optional[str] = None
        self._current_data: dict = {}
        self._tree_data: dict = {}

        self._setup_styles()
        self._setup_ui()

    def _setup_styles(self) -> None:
        """Apply panel styles."""
        self.setStyleSheet(f"""
            QFrame#trace-detail {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
        """)

    def _setup_ui(self) -> None:
        """Setup the main UI structure."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"]
        )
        main_layout.setSpacing(SPACING["xs"])

        self._setup_breadcrumb(main_layout)

        self._content_stack = QStackedWidget()

        self._overview_scroll = self._create_scroll_area()
        overview_content = QWidget()
        overview_content.setStyleSheet("background-color: transparent;")
        overview_layout = QVBoxLayout(overview_content)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(0)
        overview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._session_overview = SessionOverviewPanel()
        overview_layout.addWidget(self._session_overview)
        self._overview_scroll.setWidget(overview_content)
        self._content_stack.addWidget(self._overview_scroll)

        self._tabs_scroll = self._create_scroll_area()
        tabs_content = QWidget()
        tabs_content.setStyleSheet("background-color: transparent;")
        tabs_layout = QVBoxLayout(tabs_content)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(0)
        self._setup_tabs(tabs_layout)
        self._tabs_scroll.setWidget(tabs_content)
        self._content_stack.addWidget(self._tabs_scroll)

        self._delegation_panel = DelegationTranscriptPanel()
        self._content_stack.addWidget(self._delegation_panel)

        main_layout.addWidget(self._content_stack, stretch=1)

    def _create_scroll_area(self) -> QScrollArea:
        """Create styled scroll area."""
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
        return scroll

    def _setup_breadcrumb(self, layout: QVBoxLayout) -> None:
        """Setup breadcrumb navigation."""
        self._breadcrumb = QLabel("")
        self._breadcrumb.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_muted"]};
            padding: {SPACING["xs"]}px 0;
        """)
        self._breadcrumb.setWordWrap(True)
        self._breadcrumb.hide()
        layout.addWidget(self._breadcrumb)

    def _update_breadcrumb(self, path: list[str]) -> None:
        """Update breadcrumb with navigation path."""
        if not path:
            self._breadcrumb.hide()
            return

        self._breadcrumb.setText(" › ".join(path))
        self._breadcrumb.show()

    def _setup_tabs(self, layout: QVBoxLayout) -> None:
        """Setup tab widget with 6 sections."""
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
                background-color: {COLORS["bg_surface"]};
                padding: {SPACING["sm"]}px;
            }}
            QTabBar::tab {{
                background-color: {COLORS["bg_elevated"]};
                color: {COLORS["text_secondary"]};
                padding: {SPACING["md"]}px {SPACING["lg"]}px;
                margin-right: 4px;
                border-top-left-radius: {RADIUS["sm"]}px;
                border-top-right-radius: {RADIUS["sm"]}px;
                font-size: 16px;
                min-width: 32px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS["accent_primary_muted"]};
                color: {COLORS["accent_primary"]};
                font-weight: {FONTS["weight_semibold"]};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS["bg_hover"]};
                color: {COLORS["text_primary"]};
            }}
        """)

        # Create tabs
        self._transcript_tab = TranscriptTab()
        self._tokens_tab = TokensTab()
        self._tools_tab = ToolsTab()
        self._files_tab = FilesTab()
        self._agents_tab = AgentsTab()
        self._timeline_tab = TimelineTab()
        self._timeline_tab.event_selected.connect(self._on_timeline_event_selected)

        # Delegations tab
        self._delegations_tab = DelegationsTab()
        self._delegations_tab.session_selected.connect(
            self._on_delegation_session_selected
        )

        # Add tabs with icons
        self._tabs.addTab(self._transcript_tab, "📜")
        self._tabs.addTab(self._tokens_tab, "📊")
        self._tabs.addTab(self._tools_tab, "🔧")
        self._tabs.addTab(self._files_tab, "📁")
        self._tabs.addTab(self._agents_tab, "🤖")
        self._tabs.addTab(self._timeline_tab, "⏱")
        self._tabs.addTab(self._delegations_tab, "🌲")

        # Tooltips
        tooltips = [
            "Transcript - Full conversation",
            "Tokens - Usage breakdown",
            "Tools - Tool calls",
            "Files - File operations",
            "Agents - Agent hierarchy",
            "Timeline - Event timeline",
            "Delegations - Agent tree",
        ]
        for i, tip in enumerate(tooltips):
            self._tabs.setTabToolTip(i, tip)

        # Connect tab change for lazy loading
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

    # ===== Display Methods =====

    def show_session_summary(
        self, session_id: str, tree_data: dict | None = None
    ) -> None:
        """Show session summary - main entry point for displaying session details."""
        self._current_session_id = session_id
        self._tree_data = tree_data or {}
        self._clear_tabs()

        agent_type = self._tree_data.get("agent_type")
        is_root = agent_type is None or agent_type == "user"

        if is_root:
            self._show_root_session(session_id, self._tree_data)
        else:
            self._show_child_session(self._tree_data)

    def _show_root_session(self, session_id: str, tree_data: dict) -> None:
        """Show root session with SessionOverviewPanel."""
        client = self._get_api_client()
        if not client.is_available:
            return

        summary = client.get_session_summary(session_id)

        if summary is None:
            summary = {"meta": {}, "summary": {}, "details": {}}

        self._current_data = summary
        meta = summary.get("meta", {})
        summary.get("summary", {})

        directory = meta.get("directory", "")
        project_name = os.path.basename(directory) if directory else "Session"

        self._update_breadcrumb([f"🌳 {project_name}"])

        # Ensure session_id is in tree_data for timeline loading
        tree_data["session_id"] = session_id
        self._session_overview.load_session(tree_data)
        self._content_stack.setCurrentIndex(0)

    def _show_child_session(self, tree_data: dict) -> None:
        """Show details for a child session (sub-agent trace)."""
        self._content_stack.setCurrentIndex(1)

        agent_type = tree_data.get("agent_type", "agent")
        parent_agent = tree_data.get("parent_agent", "user")
        title = tree_data.get("title", "")
        status = tree_data.get("status", "completed")

        # Breadcrumb
        breadcrumb_path = ["🌳 ROOT"]
        if parent_agent and parent_agent != "user":
            breadcrumb_path.append(f"🔗 {parent_agent}")
        breadcrumb_path.append(f"🤖 {agent_type}")
        self._update_breadcrumb(breadcrumb_path)

        # Extract tokens from 'tokens' object (new format) or flat fields (legacy)
        duration_ms = tree_data.get("duration_ms") or 0
        tokens_obj = tree_data.get("tokens", {})
        tokens_in = tokens_obj.get("input") or tree_data.get("tokens_in") or 0
        tokens_out = tokens_obj.get("output") or tree_data.get("tokens_out") or 0

        # Transcript data
        prompt_input = (
            tree_data.get("prompt_input") or title or f"Task delegated to {agent_type}"
        )
        prompt_output = tree_data.get("prompt_output") or (
            f"Agent: {agent_type}\n"
            f"Duration: {format_duration(duration_ms)}\n"
            f"Tokens: {format_tokens_short(tokens_in)} in / {format_tokens_short(tokens_out)} out\n"
            f"Status: {status}"
        )

        self._current_data = {
            "user_content": prompt_input,
            "assistant_content": prompt_output,
        }
        self._transcript_tab.load_data(self._current_data)  # type: ignore[attr-defined]
        self._tabs.setCurrentIndex(0)

    def show_message(
        self,
        role: str,
        content: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display message content (user prompt or assistant response)."""
        self._prepare_display()

        user = content if role == "user" else ""
        assistant = content if role == "assistant" else ""
        self._show_transcript(user, assistant)

    def show_tool(
        self,
        tool_name: str,
        display_info: str,
        status: str = "completed",
        duration_ms: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display tool operation details."""
        self._prepare_display()

        self._breadcrumb.hide()

        tool_info = f"Tool: {tool_name}\n"
        if display_info:
            tool_info += f"Target: {display_info}\n"
        tool_info += f"Status: {status}\n"
        if duration_ms:
            tool_info += f"Duration: {format_duration(duration_ms)}\n"
        if timestamp:
            tool_info += f"Timestamp: {timestamp}\n"

        self._show_transcript(f"Tool: {tool_name}", tool_info)

    # ===== Utility Methods =====

    def _prepare_display(self) -> None:
        """Prepare panel for new display (clear state)."""
        self._current_session_id = None
        self._clear_tabs()
        self._content_stack.setCurrentIndex(1)

    def _show_transcript(self, user_content: str, assistant_content: str) -> None:
        """Load transcript and switch to transcript tab."""
        self._current_data = {
            "user_content": user_content,
            "assistant_content": assistant_content,
        }
        self._transcript_tab.load_data(self._current_data)  # type: ignore[attr-defined]
        self._tabs.setCurrentIndex(0)

    def _clear_tabs(self) -> None:
        """Clear all tab data."""
        self._transcript_tab.clear()  # type: ignore[attr-defined]
        self._tokens_tab.clear()  # type: ignore[attr-defined]
        self._tools_tab.clear()  # type: ignore[attr-defined]
        self._files_tab.clear()  # type: ignore[attr-defined]
        self._agents_tab.clear()  # type: ignore[attr-defined]
        self._timeline_tab.clear()  # type: ignore[attr-defined]
        self._delegations_tab.clear()  # type: ignore[attr-defined]

    def clear(self) -> None:
        """Clear all trace details."""
        self._current_session_id = None
        self._current_data = {}

        self._clear_tabs()
        self._session_overview.clear()
        self._content_stack.setCurrentIndex(1)

    # ===== Event Handlers =====

    def _on_timeline_event_selected(self, event: dict) -> None:
        """Handle timeline event click - show details in panel."""
        event_type = event.get("type", "")

        if event_type == "tool_call":
            self.show_tool(
                tool_name=event.get("tool_name", ""),
                display_info=event.get("arguments", ""),
                status=event.get("status", "completed"),
                duration_ms=event.get("duration_ms", 0),
                timestamp=event.get("timestamp"),
            )
        elif event_type == "reasoning":
            # Show reasoning as assistant message
            self.show_message(
                role="assistant",
                content=event.get("content", ""),
                timestamp=event.get("timestamp"),
            )
        elif event_type in ("user_prompt", "assistant_response"):
            self.show_message(
                role="user" if event_type == "user_prompt" else "assistant",
                content=event.get("content", ""),
                tokens_in=event.get("tokens_in", 0),
                tokens_out=event.get("tokens_out", 0),
                timestamp=event.get("timestamp"),
            )
        elif event_type == "delegation_result":
            self.show_message(
                role="assistant",
                content=event.get("result_summary", ""),
                timestamp=event.get("timestamp"),
            )

    def _on_delegation_session_selected(self, session_id: str) -> None:
        """Handle delegation session selection - navigate to that session."""
        # Load the selected session's details
        self.show_session_summary(session_id)

    # ===== Strategy-based Rendering =====

    def render(self, content: PanelContent) -> None:
        """Render panel content from strategy."""
        self._current_session_id = None
        self._clear_tabs()

        breadcrumb = content.get("breadcrumb", [])
        self._update_breadcrumb(breadcrumb)

        content_type = content.get("content_type", "tabs")
        if content_type == "overview":
            overview_data = content.get("overview_data")
            if overview_data:
                self._session_overview.load_session(overview_data)
            self._content_stack.setCurrentIndex(0)
        elif content_type == "delegation_transcript":
            delegation_data = content.get("delegation_data")
            if delegation_data:
                status = delegation_data.get("status", "")
                duration_ms = delegation_data.get("duration_ms", 0)
                status_icon = (
                    "✓" if status == "completed" else "✗" if status == "error" else "◐"
                )
                status_text = f"{status_icon} {status} • {format_duration(duration_ms)}"
                if breadcrumb:
                    breadcrumb = breadcrumb + [status_text]
                    self._update_breadcrumb(breadcrumb)
                self._delegation_panel.load_delegation(delegation_data)
            self._content_stack.setCurrentIndex(2)
        else:
            transcript = content.get("transcript")
            if transcript:
                self._current_data = {
                    "user_content": transcript.get("user_content", ""),
                    "assistant_content": transcript.get("assistant_content", ""),
                }
                self._transcript_tab.load_data(self._current_data)  # type: ignore[attr-defined]
            initial_tab = content.get("initial_tab", 0)
            self._tabs.setCurrentIndex(initial_tab)
            self._content_stack.setCurrentIndex(1)
