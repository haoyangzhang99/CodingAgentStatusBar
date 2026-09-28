"""
Dashboard main window with sidebar navigation.

Modern design with:
- Sidebar navigation instead of tabs
- Page-based content switching
- Status indicators and header
- Real-time data refresh

Note: Dashboard operates in read-only mode. Data sync is handled by
the menubar app which has write access to the database. The dashboard
polls sync_meta table to detect when new data is available.
"""

import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QApplication,
    QFrame,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QCloseEvent, QIcon, QPixmap, QPainter, QFont

from ..styles import get_stylesheet, COLORS, UI
from ..widgets import Sidebar
from ..sections import (
    MonitoringSection,
    SecuritySection,
    AnalyticsSection,
    TracingSection,
)
from .signals import DataSignals
from .sync import SyncChecker
from ...utils.logger import error, info


class DashboardWindow(QMainWindow):
    """Main dashboard window with sidebar navigation."""

    # Secondary data (security, analytics, tracing) refreshes every N iterations
    # With refresh_interval_ms=2000 and divisor=5, secondary refreshes every 10s
    SECONDARY_REFRESH_DIVISOR = 5

    def __init__(self, parent: QWidget | None = None):
        """Initialize dashboard window.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)

        self._signals = DataSignals()
        self._refresh_timer: Optional[QTimer] = None
        self._agent_tty_map: dict[str, str] = {}
        self._sync_checker: Optional[SyncChecker] = None
        self._refresh_count = 0
        self._monitoring_fetch_in_progress = False
        self._current_section_index = 0

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._start_refresh()

        info("[Dashboard] Window opened")

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("OpenCode Status Bar")
        self.setMinimumSize(UI["window_min_width"], UI["window_min_height"])
        self.resize(UI["window_default_width"], UI["window_default_height"])

        # Create app icon
        self._set_app_icon()

        # Apply stylesheet
        self.setStyleSheet(get_stylesheet())

    def _set_app_icon(self) -> None:
        """Create and set a custom app icon."""
        size = UI["app_icon_size"]
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont("Apple Color Emoji", 96)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🤖")
        painter.end()

        icon = QIcon(pixmap)
        self.setWindowIcon(icon)

        # Set as application icon
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setWindowIcon(icon)

    def _setup_ui(self) -> None:
        """Build the user interface with sidebar layout."""
        central = QWidget()
        self.setCentralWidget(central)

        # Main horizontal layout: sidebar + content
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.section_changed.connect(self._on_section_changed)
        main_layout.addWidget(self._sidebar)

        # Content area
        content_frame = QFrame()
        content_frame.setObjectName("content-area")
        content_frame.setStyleSheet(f"""
            QFrame#content-area {{
                background-color: {COLORS["bg_base"]};
            }}
        """)

        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stacked widget for page switching
        self._pages = QStackedWidget()

        # Create sections
        self._monitoring = MonitoringSection()
        self._security = SecuritySection()
        self._analytics = AnalyticsSection()
        self._tracing = TracingSection()

        self._pages.addWidget(self._monitoring)
        self._pages.addWidget(self._security)
        self._pages.addWidget(self._analytics)
        self._pages.addWidget(self._tracing)

        content_layout.addWidget(self._pages)
        main_layout.addWidget(content_frame)

    def _on_section_changed(self, index: int) -> None:
        """Handle sidebar navigation.

        Lazy-loads tracing data when user navigates to Tracing tab to avoid
        expensive queries during auto-refresh cycles. Tracing data fetches
        194+ root sessions, causing UI lag when done every 10s.
        """
        section_names = ["Monitoring", "Security", "Analytics", "Tracing"]
        if self._current_section_index != index:
            old_name = section_names[self._current_section_index]
            new_name = section_names[index]
            info(f"[Dashboard] Section changed: {old_name} → {new_name}")
            self._current_section_index = index

        self._pages.setCurrentIndex(index)

        # Load tracing data on-demand when user clicks Tracing tab
        # Index mapping: 0=Monitoring, 1=Security, 2=Analytics, 3=Tracing
        if index == 3:
            threading.Thread(target=self._fetch_tracing_data, daemon=True).start()

    def _connect_signals(self) -> None:
        """Connect data signals to UI updates."""
        self._signals.monitoring_updated.connect(self._on_monitoring_data)
        self._signals.security_updated.connect(self._on_security_data)
        self._signals.analytics_updated.connect(self._on_analytics_data)
        self._signals.tracing_updated.connect(self._on_tracing_data)

        # Connect period change to trigger analytics refresh
        self._analytics.period_changed.connect(self._on_analytics_period_changed)

        self._monitoring.open_terminal_requested.connect(self._on_open_terminal)
        self._tracing.open_terminal_requested.connect(self._on_open_terminal_session)
        self._tracing.load_more_requested.connect(self._on_tracing_load_more)

    def _on_open_terminal(self, agent_id: str) -> None:
        """Handle request to open terminal for an agent."""
        info(f"[Monitoring] Terminal opened for agent: {agent_id}")
        tty = self._agent_tty_map.get(agent_id)
        if tty:
            from ...ui.terminal import focus_iterm2

            focus_iterm2(tty)

    def _on_open_terminal_session(self, session_id: str) -> None:
        info(f"[Tracing] Terminal opened for session: {session_id[:12]}...")

    def _on_tracing_load_more(self, offset: int, limit: int) -> None:
        threading.Thread(
            target=self._fetch_tracing_data,
            args=(offset, limit),
            daemon=True,
        ).start()

    def _on_analytics_period_changed(self, days: int) -> None:
        """Handle analytics period change - refresh data immediately."""
        threading.Thread(target=self._fetch_analytics_data, daemon=True).start()

    def _start_refresh(self) -> None:
        """Start periodic data refresh.

        Note: Dashboard operates in read-only mode. Data sync is handled by
        the menubar app which has write access to the database.
        """
        # Initial data load from DB (read-only)
        self._refresh_all_data()

        # Periodic refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_all_data)
        self._refresh_timer.start(UI["refresh_interval_ms"])

        # Start sync checker to detect when menubar syncs new data
        self._sync_checker = SyncChecker(on_sync_detected=self._refresh_all_data)

    def _refresh_all_data(self) -> None:
        """Refresh all section data in background threads.

        Performance optimization: Uses adaptive polling to reduce CPU usage.
        - Monitoring data refreshes every 2s (real-time agent detection)
        - Secondary data (security, analytics) refreshes every 10s
        - Tracing data loads on-demand when user clicks Tracing tab
        """
        # Always refresh monitoring (real-time requirement for agent detection)
        threading.Thread(target=self._fetch_monitoring_data, daemon=True).start()

        # Secondary data refreshes less frequently (every SECONDARY_REFRESH_DIVISOR iterations)
        # Tracing removed from auto-refresh to reduce CPU usage (loads on-demand)
        if self._refresh_count % self.SECONDARY_REFRESH_DIVISOR == 0:
            threading.Thread(target=self._fetch_security_data, daemon=True).start()
            threading.Thread(target=self._fetch_analytics_data, daemon=True).start()

        self._refresh_count += 1

    def _fetch_monitoring_data(self) -> None:
        """Fetch monitoring data from core module."""
        if self._monitoring_fetch_in_progress:
            return
        self._monitoring_fetch_in_progress = True
        try:
            import asyncio
            from ...core.monitor import fetch_all_instances
            from ...core.models import SessionStatus

            loop = asyncio.new_event_loop()
            state = loop.run_until_complete(fetch_all_instances())
            loop.close()

            # Build data dict
            agents_data = []
            tools_data = []
            waiting_data = []
            agent_tty_map: dict[str, str] = {}  # Temporary map to update after loop
            busy_count = 0
            waiting_count = 0  # Sessions with pending ask_user
            idle_instances = 0  # Instances with no busy agents
            total_todos = 0

            for instance in state.instances:
                # Count idle instances (instances where no agent is busy)
                if instance.busy_count == 0:
                    idle_instances += 1

                for agent in instance.agents:
                    is_busy = agent.status == SessionStatus.BUSY
                    if is_busy:
                        busy_count += 1

                    # Store TTY mapping for terminal focus
                    if instance.tty:
                        agent_tty_map[agent.id] = instance.tty

                    # Count agents waiting for user response
                    if agent.has_pending_ask_user:
                        waiting_count += 1

                        # Build context string: "agent @ branch" or "repo @ branch" or just "repo"
                        context_parts = []
                        if agent.ask_user_agent:
                            context_parts.append(agent.ask_user_agent)
                        elif agent.ask_user_repo:
                            context_parts.append(agent.ask_user_repo)
                        if agent.ask_user_branch:
                            context_parts.append(agent.ask_user_branch)
                        context = " @ ".join(context_parts) if context_parts else ""

                        waiting_data.append(
                            {
                                "agent_id": agent.id,
                                "title": agent.ask_user_title
                                or agent.title
                                or f"Agent {agent.id[:8]}",
                                "question": agent.ask_user_question
                                or "Waiting for response...",
                                "options": " | ".join(agent.ask_user_options)
                                if agent.ask_user_options
                                else "",
                                "context": context,
                            }
                        )

                    todos_total = agent.todos.pending + agent.todos.in_progress
                    total_todos += todos_total

                    agents_data.append(
                        {
                            "agent_id": agent.id,
                            "title": agent.title or f"Agent {agent.id[:8]}",
                            "dir": agent.dir or "",
                            "status": "busy" if is_busy else "idle",
                            "tools": agent.tools,
                            "todos_total": todos_total,
                        }
                    )

                    for tool in agent.tools:
                        tools_data.append(
                            {
                                "name": tool.name,
                                "agent": agent.title or agent.id[:8],
                                "arg": tool.arg or "",
                                "elapsed_ms": tool.elapsed_ms,
                            }
                        )

            data = {
                "instances": state.instance_count,
                "agents": len(agents_data),
                "busy": busy_count,
                "waiting": waiting_count,
                "idle": idle_instances,
                "todos": total_todos,
                "agents_data": agents_data,
                "tools_data": tools_data,
                "waiting_data": waiting_data,
            }

            # Update TTY mapping (thread-safe assignment)
            self._agent_tty_map = agent_tty_map

            self._signals.monitoring_updated.emit(data)

            # Note: Sidebar status update removed - was using signals improperly
            # Could be re-implemented via self._signals if needed

        except Exception as e:
            error(f"[Dashboard] Monitoring fetch error: {e}")
        finally:
            self._monitoring_fetch_in_progress = False

    def _fetch_security_data(self) -> None:
        """Fetch security data via API to avoid DuckDB lock conflicts.

        Uses the menubar's API server instead of directly accessing the
        security auditor, which would cause DuckDB lock errors since the
        menubar process holds the write lock.
        """
        try:
            from ...api import get_api_client

            client = get_api_client()

            # Check if API is available
            if not client.is_available:
                return

            row_limit = UI["table_row_limit"]
            top_limit = UI["top_items_limit"]

            # Fetch security data from API (data is already formatted)
            data = client.get_security_data(row_limit=row_limit, top_limit=top_limit)

            if not data:
                return

            self._signals.security_updated.emit(data)

        except (
            Exception
        ) as e:  # Intentional catch-all: dashboard fetch errors logged, UI continues
            error(f"[Dashboard] Security fetch error: {e}")

    def _fetch_analytics_data(self) -> None:
        """Fetch analytics data via API to avoid DuckDB concurrency issues."""
        try:
            from ...api import get_api_client

            client = get_api_client()

            # Check if API is available
            if not client.is_available:
                return

            days = self._analytics.get_current_period()
            global_stats = client.get_global_stats(days=days)

            if not global_stats:
                return

            summary = global_stats.get("summary", {})
            details = global_stats.get("details", {})
            tokens_detail = details.get("tokens", {})

            total_tokens = summary.get("total_tokens", 0)
            input_tokens = tokens_detail.get("input", 0)
            cache_tokens = tokens_detail.get("cache_read", 0)

            # Format tokens
            if total_tokens < 1000:
                tokens_str = str(total_tokens)
            elif total_tokens < 1000000:
                tokens_str = f"{total_tokens / 1000:.1f}K"
            else:
                tokens_str = f"{total_tokens / 1000000:.1f}M"

            # Calculate cache hit ratio
            total_input = input_tokens + cache_tokens
            cache_hit = (
                f"{(cache_tokens / total_input * 100):.0f}%"
                if total_input > 0
                else "0%"
            )

            data = {
                "sessions": summary.get("total_sessions", 0),
                "messages": summary.get("total_messages", 0),
                "tokens": tokens_str,
                "cache_hit": cache_hit,
                # Use detailed breakdowns from API
                "agents": global_stats.get("agents", []),
                "tools": global_stats.get("tools", []),
                "skills": global_stats.get("skills", []),
            }

            self._signals.analytics_updated.emit(data)

        except (
            Exception
        ) as e:  # Intentional catch-all: dashboard fetch errors logged, UI continues
            error(f"[Dashboard] Analytics fetch error: {e}")

    def _on_monitoring_data(self, data: dict) -> None:
        """Handle monitoring data update."""
        self._monitoring.update_data(
            instances=data.get("instances", 0),
            agents=data.get("agents", 0),
            busy=data.get("busy", 0),
            waiting=data.get("waiting", 0),
            idle=data.get("idle", 0),
            todos=data.get("todos", 0),
            agents_data=data.get("agents_data", []),
            tools_data=data.get("tools_data", []),
            waiting_data=data.get("waiting_data", []),
        )

        # Update sidebar status
        agents_count = data.get("agents", 0)
        self._sidebar.set_status(
            agents_count > 0,
            f"{agents_count} agent{'s' if agents_count != 1 else ''}"
            if agents_count > 0
            else "Idle",
        )

    def _on_security_data(self, data: dict) -> None:
        """Handle security data update."""
        self._security.update_data(
            stats=data.get("stats", {}),
            commands=data.get("commands", []),
            files=data.get("files", []),
            critical_items=data.get("critical_items", []),
        )

    def _on_analytics_data(self, data: dict) -> None:
        """Handle analytics data update."""
        self._analytics.update_data(
            sessions=data.get("sessions", 0),
            messages=data.get("messages", 0),
            tokens=data.get("tokens", "0"),
            cache_hit=data.get("cache_hit", "0%"),
            agents=data.get("agents", []),
            tools=data.get("tools", []),
            skills=data.get("skills", []),
        )

    def _fetch_tracing_data(self, offset: int = 0, limit: int = 80) -> None:
        try:
            from ...api import get_api_client

            client = get_api_client()

            if not client.is_available:
                return

            result = client.get_tracing_tree(days=60, limit=limit, offset=offset)
            if not result:
                return

            sessions = result.get("data", [])
            meta = result.get("meta", {})

            self._signals.tracing_updated.emit(
                {
                    "session_hierarchy": sessions,
                    "meta": meta,
                    "is_append": offset > 0,
                }
            )

        except Exception as e:
            error(f"[Dashboard] Tracing fetch error: {e}")

    def _on_tracing_data(self, data: dict) -> None:
        self._tracing.update_data(
            session_hierarchy=data.get("session_hierarchy", []),
            meta=data.get("meta"),
            is_append=data.get("is_append", False),
        )

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Handle window close."""
        info("[Dashboard] Window closed")
        if self._refresh_timer:
            self._refresh_timer.stop()
        if self._sync_checker:
            self._sync_checker.stop()
        if a0:
            a0.accept()
