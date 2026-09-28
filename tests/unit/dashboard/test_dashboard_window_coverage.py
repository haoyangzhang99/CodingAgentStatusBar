"""
Tests for DashboardWindow coverage improvement.

Target: Improve dashboard/window/ module coverage from 49% to 80%+.
Refactored for better assertion density (target ratio > 4.0).
"""

import threading
import time
import subprocess
from unittest.mock import patch, MagicMock
import pytest


# =============================================================================
# Factories
# =============================================================================


def make_mock_state(
    agents=None,
    pending_todos=0,
    in_progress_todos=0,
    port=8080,
    tty="/dev/ttys001",
):
    """Factory for creating mock State objects."""
    from opencode_status_bar.core.models import State, Instance, Todos

    if agents is None:
        agents = []

    return State(
        instances=[Instance(port=port, tty=tty, agents=agents)],
        todos=Todos(pending=pending_todos, in_progress=in_progress_todos),
    )


def make_mock_agent(
    agent_id="agent-1",
    title="Test Agent",
    status=None,
    tools=None,
    has_pending_ask_user=False,
    ask_user_title="",
    ask_user_question="",
    ask_user_options=None,
    ask_user_agent="",
    ask_user_repo="",
    ask_user_branch="",
):
    """Factory for creating mock Agent objects."""
    from opencode_status_bar.core.models import Agent, SessionStatus

    if status is None:
        status = SessionStatus.BUSY
    if tools is None:
        tools = []
    if ask_user_options is None:
        ask_user_options = []

    return Agent(
        id=agent_id,
        title=title,
        dir="project",
        full_dir="/home/user/project",
        status=status,
        tools=tools,
        has_pending_ask_user=has_pending_ask_user,
        ask_user_title=ask_user_title,
        ask_user_question=ask_user_question,
        ask_user_options=ask_user_options,
        ask_user_agent=ask_user_agent,
        ask_user_repo=ask_user_repo,
        ask_user_branch=ask_user_branch,
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client():
    """Mock API client with comprehensive default responses."""
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.get_stats.return_value = {"sessions": 0}
    mock_client.get_sync_status.return_value = {"backfill_active": False}
    mock_client.get_global_stats.return_value = {
        "summary": {"total_sessions": 10, "total_messages": 100, "total_tokens": 5000},
        "details": {"tokens": {"input": 2000, "cache_read": 3000}},
    }
    mock_client.get_tracing_tree.return_value = {
        "data": [{"session_id": "sess-1", "title": "Test Session"}],
        "meta": {"limit": 500, "offset": 0, "count": 1, "has_more": False},
    }
    mock_client.get_security_data.return_value = {
        "stats": {"critical": 0, "high": 1},
        "commands": [
            {"command": "rm -rf", "risk": "high", "score": 80, "reason": "dangerous"}
        ],
        "files": [],
        "critical_items": [],
    }

    with patch("opencode_status_bar.api.get_api_client") as mock_get:
        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture
def dashboard_window(qapp, mock_api_client):
    """DashboardWindow with mocked refresh for isolated testing."""
    from opencode_status_bar.dashboard.window import DashboardWindow

    with patch.object(DashboardWindow, "_start_refresh"):
        window = DashboardWindow()
        yield window
        window.close()
        window.deleteLater()


@pytest.fixture
def dashboard_with_mock_sections(qapp, mock_api_client):
    """DashboardWindow with mocked sections for handler testing."""
    from opencode_status_bar.dashboard.window import DashboardWindow

    with patch.object(DashboardWindow, "_fetch_monitoring_data"):
        with patch.object(DashboardWindow, "_fetch_security_data"):
            with patch.object(DashboardWindow, "_fetch_analytics_data"):
                with patch.object(DashboardWindow, "_fetch_tracing_data"):
                    window = DashboardWindow()
                    mock_sections = {
                        "monitoring": MagicMock(),
                        "security": MagicMock(),
                        "analytics": MagicMock(),
                        "tracing": MagicMock(),
                    }
                    window._monitoring = mock_sections["monitoring"]
                    window._security = mock_sections["security"]
                    window._analytics = mock_sections["analytics"]
                    window._tracing = mock_sections["tracing"]
                    window._sidebar = MagicMock()

                    yield window, mock_sections
                    window.close()
                    window.deleteLater()


# =============================================================================
# launcher.py Tests - Consolidated
# =============================================================================


class TestLauncherShowDashboard:
    """Tests for launcher.py show_dashboard() function."""

    @pytest.mark.parametrize(
        "existing_process_state,should_terminate,should_kill",
        [
            pytest.param(None, False, False, id="no_existing_process"),
            pytest.param("dead", False, False, id="dead_process"),
            pytest.param("running", True, False, id="running_terminates"),
            pytest.param("stuck", True, True, id="stuck_requires_kill"),
        ],
    )
    def test_show_dashboard_process_management(
        self, existing_process_state, should_terminate, should_kill
    ):
        """show_dashboard() handles existing process states correctly."""
        import opencode_status_bar.dashboard.window.launcher as launcher

        mock_existing = None
        if existing_process_state:
            mock_existing = MagicMock()
            if existing_process_state == "dead":
                mock_existing.poll.return_value = 0
            else:
                mock_existing.poll.return_value = None
                if existing_process_state == "stuck":
                    mock_existing.wait.side_effect = subprocess.TimeoutExpired(
                        "test", 2
                    )

        launcher._dashboard_process = mock_existing

        with patch("subprocess.Popen") as mock_popen:
            mock_new = MagicMock()
            mock_popen.return_value = mock_new

            launcher.show_dashboard()

            # Verify Popen was called with correct args
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert "-m" in call_args[0][0], "Should use -m flag"
            assert "opencode_status_bar.dashboard" in call_args[0][0], (
                "Should launch dashboard module"
            )
            assert call_args[1]["start_new_session"] == True, "Should start new session"

            # Verify process management
            if mock_existing and should_terminate:
                mock_existing.terminate.assert_called_once()
                if should_kill:
                    mock_existing.kill.assert_called_once()
            elif mock_existing:
                mock_existing.terminate.assert_not_called()


# =============================================================================
# Signal Handlers Tests - Consolidated
# =============================================================================


class TestDashboardSignalHandlers:
    """Tests for DashboardWindow signal handler methods."""

    def test_on_section_changed(self, dashboard_with_mock_sections):
        """_on_section_changed updates pages stack index."""
        window, _ = dashboard_with_mock_sections
        window._pages = MagicMock()

        for index in [0, 1, 2, 3]:
            window._on_section_changed(index)
            assert window._pages.setCurrentIndex.called, (
                "setCurrentIndex should be called"
            )
            assert window._pages.setCurrentIndex.call_args[0][0] == index

        assert window._pages.setCurrentIndex.call_count == 4, "Should be called 4 times"

    @pytest.mark.parametrize(
        "agent_id,tty_map,should_focus",
        [
            pytest.param(
                "agent-123", {"agent-123": "/dev/ttys001"}, True, id="known_agent"
            ),
            pytest.param(
                "unknown", {"agent-123": "/dev/ttys001"}, False, id="unknown_agent"
            ),
            pytest.param("agent-123", {}, False, id="empty_map"),
        ],
    )
    def test_on_open_terminal(
        self, dashboard_with_mock_sections, agent_id, tty_map, should_focus
    ):
        """_on_open_terminal focuses terminal only for known agents."""
        window, _ = dashboard_with_mock_sections
        window._agent_tty_map = tty_map

        with patch("opencode_status_bar.ui.terminal.focus_iterm2") as mock_focus:
            window._on_open_terminal(agent_id)

            if should_focus:
                mock_focus.assert_called_once_with(tty_map[agent_id])
            else:
                mock_focus.assert_not_called()

        window._on_open_terminal_session("session-abc")

    def test_on_analytics_period_changed(self, dashboard_with_mock_sections):
        """_on_analytics_period_changed triggers analytics data fetch in thread."""
        window, _ = dashboard_with_mock_sections

        # Use threading.Event to detect when fetch is called
        fetch_called = threading.Event()

        def mock_fetch():
            fetch_called.set()

        with patch.object(window, "_fetch_analytics_data", side_effect=mock_fetch):
            window._on_analytics_period_changed(30)

            # Verify fetch was called in thread (wait up to 2 seconds)
            assert fetch_called.wait(timeout=2.0), (
                "Analytics fetch should have been called in thread"
            )


# =============================================================================
# Data Handlers Tests - Consolidated
# =============================================================================


class TestDashboardDataHandlers:
    """Tests for DashboardWindow data update handlers."""

    @pytest.mark.parametrize(
        "agents,expected_status_text,expected_active",
        [
            pytest.param(0, "Idle", False, id="no_agents_idle"),
            pytest.param(1, "1 agent", True, id="singular_agent"),
            pytest.param(3, "3 agents", True, id="plural_agents"),
        ],
    )
    def test_on_monitoring_data_status(
        self,
        dashboard_with_mock_sections,
        agents,
        expected_status_text,
        expected_active,
    ):
        """_on_monitoring_data updates sidebar status correctly."""
        window, sections = dashboard_with_mock_sections

        data = {
            "instances": 1 if agents else 0,
            "agents": agents,
            "busy": agents,
            "waiting": 0,
            "idle": 0,
            "todos": 0,
            "agents_data": [{"agent_id": f"a{i}"} for i in range(agents)],
            "tools_data": [],
            "waiting_data": [],
        }

        window._on_monitoring_data(data)

        # Verify section update was called
        sections["monitoring"].update_data.assert_called_once()
        call_kwargs = sections["monitoring"].update_data.call_args[1]
        assert "agents" in call_kwargs, "Should have agents"
        assert call_kwargs["agents"] == agents
        assert call_kwargs["busy"] == agents
        assert call_kwargs["waiting"] == 0
        assert call_kwargs["idle"] == 0
        assert call_kwargs["todos"] == 0

        # Verify sidebar status
        window._sidebar.set_status.assert_called_once()
        status_call = window._sidebar.set_status.call_args[0]
        assert status_call[0] is expected_active
        assert status_call[1] == expected_status_text

    def test_on_security_data(self, dashboard_with_mock_sections):
        """_on_security_data updates security section with all fields."""
        window, sections = dashboard_with_mock_sections

        data = {
            "stats": {"critical": 2, "high": 3},
            "commands": [{"command": "ls"}, {"command": "rm"}],
            "files": [{"path": "/etc/passwd"}],
            "critical_items": [{"type": "COMMAND", "details": "rm -rf"}],
        }

        window._on_security_data(data)

        sections["security"].update_data.assert_called_once()
        call_kwargs = sections["security"].update_data.call_args[1]
        assert "stats" in call_kwargs, "Should have stats"
        assert call_kwargs["stats"]["critical"] == 2
        assert call_kwargs["stats"]["high"] == 3
        assert "commands" in call_kwargs, "Should have commands"
        assert call_kwargs["commands"] == [{"command": "ls"}, {"command": "rm"}]
        assert call_kwargs["files"] == [{"path": "/etc/passwd"}]
        assert call_kwargs["critical_items"] == [
            {"type": "COMMAND", "details": "rm -rf"}
        ]

    def test_on_analytics_data(self, dashboard_with_mock_sections):
        """_on_analytics_data updates analytics section with all fields."""
        window, sections = dashboard_with_mock_sections

        data = {
            "sessions": 10,
            "messages": 100,
            "tokens": "5K",
            "cache_hit": "60%",
            "agents": [{"name": "agent1"}],
            "tools": [{"tool": "bash"}],
            "skills": [{"skill": "testing"}],
        }

        window._on_analytics_data(data)

        sections["analytics"].update_data.assert_called_once()
        call_kwargs = sections["analytics"].update_data.call_args[1]
        assert "sessions" in call_kwargs, "Should have sessions"
        assert call_kwargs["sessions"] == 10
        assert call_kwargs["messages"] == 100
        assert call_kwargs["tokens"] == "5K"
        assert call_kwargs["cache_hit"] == "60%"
        assert "agents" in call_kwargs, "Should have agents"
        assert call_kwargs["agents"] == [{"name": "agent1"}]
        assert call_kwargs["tools"] == [{"tool": "bash"}]
        assert call_kwargs["skills"] == [{"skill": "testing"}]

    def test_on_tracing_data(self, dashboard_with_mock_sections):
        """_on_tracing_data updates tracing section."""
        window, sections = dashboard_with_mock_sections

        data = {"session_hierarchy": [{"session_id": "s1"}, {"session_id": "s2"}]}

        window._on_tracing_data(data)

        sections["tracing"].update_data.assert_called_once()
        call_kwargs = sections["tracing"].update_data.call_args[1]
        assert "session_hierarchy" in call_kwargs, "Should have session_hierarchy"
        assert call_kwargs["session_hierarchy"] == [
            {"session_id": "s1"},
            {"session_id": "s2"},
        ]


# =============================================================================
# Fetch Methods Tests - Consolidated with Parametrize
# =============================================================================


class TestFetchMethods:
    """Tests for DashboardWindow fetch methods."""

    @pytest.mark.parametrize(
        "patch_target,method_name,error_msg_contains",
        [
            pytest.param(
                "asyncio.new_event_loop",
                "_fetch_monitoring_data",
                "Monitoring fetch error",
                id="monitoring",
            ),
            pytest.param(
                "opencode_status_bar.api.get_api_client",
                "_fetch_security_data",
                "Security fetch error",
                id="security",
            ),
            pytest.param(
                "opencode_status_bar.api.get_api_client",
                "_fetch_analytics_data",
                "Analytics fetch error",
                id="analytics",
            ),
        ],
    )
    def test_fetch_handles_exception(
        self, dashboard_window, patch_target, method_name, error_msg_contains
    ):
        """Fetch methods log error and continue on exception."""
        with patch(patch_target, side_effect=RuntimeError("Test error")):
            with patch("opencode_status_bar.dashboard.window.main.error") as mock_error:
                getattr(dashboard_window, method_name)()
                mock_error.assert_called()
                assert any(
                    error_msg_contains in str(call)
                    for call in mock_error.call_args_list
                )


class TestFetchApiUnavailable:
    """Parameterized tests for API unavailable handling."""

    @pytest.mark.parametrize(
        "method_name,signal_name",
        [
            pytest.param("_fetch_analytics_data", "analytics_updated", id="analytics"),
            pytest.param("_fetch_tracing_data", "tracing_updated", id="tracing"),
        ],
    )
    def test_fetch_returns_early_when_api_unavailable(
        self, qapp, method_name, signal_name
    ):
        """Fetch methods return early when API is unavailable."""
        from opencode_status_bar.dashboard.window import DashboardWindow

        mock_client = MagicMock()
        mock_client.is_available = False

        with patch("opencode_status_bar.api.get_api_client", return_value=mock_client):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    getattr(window._signals, signal_name).connect(
                        lambda d: received_data.append(d)
                    )
                    getattr(window, method_name)()
                    assert received_data == [], (
                        f"{method_name} should not emit when API unavailable"
                    )
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_monitoring_data_success(self, qapp, mock_api_client):
        """_fetch_monitoring_data fetches and emits complete monitoring data."""
        from opencode_status_bar.dashboard.window import DashboardWindow
        from opencode_status_bar.core.models import Tool

        agent = make_mock_agent(tools=[Tool(name="bash", arg="ls -la", elapsed_ms=100)])
        mock_state = make_mock_state(
            agents=[agent], pending_todos=2, in_progress_todos=1
        )

        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()
            mock_loop.run_until_complete.return_value = mock_state
            mock_loop_factory.return_value = mock_loop

            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.monitoring_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_monitoring_data()

                    assert len(received_data) == 1
                    data = received_data[0]
                    assert data["instances"] == 1
                    assert data["agents"] == 1
                    assert data["busy"] == 1
                    assert data["waiting"] == 0
                    assert data["idle"] == 0
                    assert data["todos"] == 0  # Agent doesn't have todos in mock
                    # Verify agents_data structure
                    assert len(data["agents_data"]) == 1
                    assert data["agents_data"][0]["agent_id"] == "agent-1"
                    assert data["agents_data"][0]["status"] == "busy"
                    # Verify tools_data contains name, arg, elapsed_ms from Tool model
                    assert len(data["tools_data"]) == 1
                    assert data["tools_data"][0]["name"] == "bash"
                    assert data["tools_data"][0]["arg"] == "ls -la"
                    assert data["tools_data"][0]["elapsed_ms"] == 100
                    assert data["waiting_data"] == []
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_security_data_success(self, qapp, mock_api_client):
        """_fetch_security_data fetches and emits security data via API."""
        from opencode_status_bar.dashboard.window import DashboardWindow

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow()
            try:
                received_data = []
                window._signals.security_updated.connect(
                    lambda d: received_data.append(d)
                )

                window._fetch_security_data()

                assert len(received_data) == 1
                data = received_data[0]
                assert "stats" in data
                assert data["stats"] == {"critical": 0, "high": 1}
                assert "commands" in data
                assert data["commands"] == [
                    {
                        "command": "rm -rf",
                        "risk": "high",
                        "score": 80,
                        "reason": "dangerous",
                    }
                ]
                assert data["files"] == []
                assert data["critical_items"] == []
            finally:
                window.close()
                window.deleteLater()

    @pytest.mark.parametrize(
        "total_tokens,expected_str",
        [
            pytest.param(500, "500", id="small"),
            pytest.param(5000, "5.0K", id="thousands"),
            pytest.param(1500000, "1.5M", id="millions"),
        ],
    )
    def test_fetch_analytics_data_token_formatting(
        self, qapp, total_tokens, expected_str
    ):
        """_fetch_analytics_data formats tokens correctly for different scales."""
        from opencode_status_bar.dashboard.window import DashboardWindow

        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.get_global_stats.return_value = {
            "summary": {
                "total_sessions": 1,
                "total_messages": 1,
                "total_tokens": total_tokens,
            },
            "details": {"tokens": {"input": total_tokens, "cache_read": 0}},
        }

        with patch("opencode_status_bar.api.get_api_client", return_value=mock_client):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    window._analytics = MagicMock()
                    window._analytics.get_current_period.return_value = 7

                    received_data = []
                    window._signals.analytics_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_analytics_data()

                    assert len(received_data) == 1
                    data = received_data[0]
                    assert data["tokens"] == expected_str
                    assert data["sessions"] == 1
                    assert data["messages"] == 1
                    assert data["cache_hit"] == "0%"  # cache_read is 0 in mock
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_tracing_data_success(self, dashboard_window):
        received_data = []
        dashboard_window._signals.tracing_updated.connect(
            lambda d: received_data.append(d)
        )

        dashboard_window._fetch_tracing_data()

        assert len(received_data) == 1
        data = received_data[0]
        assert "session_hierarchy" in data
        assert data["session_hierarchy"] == [
            {"session_id": "sess-1", "title": "Test Session"}
        ]
        assert "meta" in data
        assert data["is_append"] == False

    def test_fetch_tracing_data_handles_exception(self, qapp):
        """_fetch_tracing_data logs error with traceback on exception."""
        from opencode_status_bar.dashboard.window import DashboardWindow

        with patch(
            "opencode_status_bar.api.get_api_client",
            side_effect=RuntimeError("Tracing error"),
        ):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    with patch(
                        "opencode_status_bar.dashboard.window.main.error"
                    ) as mock_error:
                        window._fetch_tracing_data()
                        assert mock_error.call_count == 1
                        mock_error.assert_called_once()
                        assert "Tracing fetch error" in str(mock_error.call_args)
                finally:
                    window.close()
                    window.deleteLater()


# =============================================================================
# Monitoring Data Processing - Edge Cases
# =============================================================================


class TestMonitoringDataProcessing:
    """Tests for monitoring data edge cases."""

    def test_fetch_monitoring_with_waiting_agents(self, qapp, mock_api_client):
        """_fetch_monitoring_data correctly processes agents with pending ask_user."""
        from opencode_status_bar.dashboard.window import DashboardWindow

        agent = make_mock_agent(
            agent_id="agent-wait",
            has_pending_ask_user=True,
            ask_user_title="Need Input",
            ask_user_question="What next?",
            ask_user_options=["Option A", "Option B"],
            ask_user_agent="my-agent",
            ask_user_branch="main",
        )
        mock_state = make_mock_state(agents=[agent], tty="")

        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()
            mock_loop.run_until_complete.return_value = mock_state
            mock_loop_factory.return_value = mock_loop

            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.monitoring_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_monitoring_data()

                    data = received_data[0]
                    assert data["waiting"] == 1
                    assert len(data["waiting_data"]) == 1
                    waiting = data["waiting_data"][0]
                    assert waiting["agent_id"] == "agent-wait"
                    assert waiting["title"] == "Need Input"
                    assert waiting["question"] == "What next?"
                    assert waiting["options"] == "Option A | Option B"
                    assert waiting["context"] == "my-agent @ main"
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_monitoring_with_repo_context(self, qapp, mock_api_client):
        """_fetch_monitoring_data uses repo when agent name not available."""
        from opencode_status_bar.dashboard.window import DashboardWindow

        agent = make_mock_agent(
            has_pending_ask_user=True,
            ask_user_title="Input needed",
            ask_user_question="Question?",
            ask_user_agent="",
            ask_user_repo="my-repo",
            ask_user_branch="feature",
        )
        mock_state = make_mock_state(agents=[agent], tty="")

        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()
            mock_loop.run_until_complete.return_value = mock_state
            mock_loop_factory.return_value = mock_loop

            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.monitoring_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_monitoring_data()

                    data = received_data[0]
                    assert data["waiting"] == 1
                    assert len(data["waiting_data"]) == 1
                    waiting = data["waiting_data"][0]
                    assert waiting["title"] == "Input needed"
                    assert waiting["question"] == "Question?"
                    assert waiting["options"] == ""  # Empty list becomes empty string
                    assert waiting["context"] == "my-repo @ feature"
                finally:
                    window.close()
                    window.deleteLater()


# =============================================================================
# SyncChecker Tests - Consolidated
# =============================================================================


class TestSyncChecker:
    """Tests for SyncChecker idle mode transition."""

    def test_sync_checker_mode_transitions(self, qapp):
        """SyncChecker transitions between fast and slow polling modes."""
        from opencode_status_bar.dashboard.window import SyncChecker

        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.get_stats.return_value = {"sessions": 5}
        mock_client.get_sync_status.return_value = {"backfill_active": False}

        callback_calls = []

        with patch("opencode_status_bar.api.get_api_client", return_value=mock_client):
            checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
            assert checker._timer is not None, "Timer should be created"
            try:
                # Initial check - should be in fast mode, no callback on first check
                checker._check()
                assert checker._timer.interval() == SyncChecker.POLL_FAST_MS
                assert callback_calls == []

                # Change data - should stay fast and trigger callback
                mock_client.get_stats.return_value = {"sessions": 6}
                checker._check()
                assert checker._timer.interval() == SyncChecker.POLL_FAST_MS
                assert callback_calls == [True]

                # Simulate idle threshold exceeded
                checker._last_change_time = (
                    time.time() - SyncChecker.IDLE_THRESHOLD_S - 1
                )
                checker._check()
                assert checker._timer.interval() == SyncChecker.POLL_SLOW_MS
            finally:
                checker.stop()

    def test_sync_checker_api_availability(self, qapp):
        """SyncChecker handles API availability correctly."""
        from opencode_status_bar.dashboard.window import SyncChecker

        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.get_stats.return_value = {"sessions": 1}
        mock_client.get_sync_status.return_value = {"backfill_active": False}

        callback_calls = []

        with patch("opencode_status_bar.api.get_api_client", return_value=mock_client):
            checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
            try:
                # First check skips callback
                checker._check()
                assert callback_calls == []
                assert checker._known_sync == 1

                # Change triggers callback
                mock_client.get_stats.return_value = {"sessions": 5}
                checker._check()
                assert callback_calls == [True]
                assert checker._known_sync == 5
            finally:
                checker.stop()

    def test_sync_checker_api_unavailable(self, qapp):
        """SyncChecker does not callback when API unavailable."""
        from opencode_status_bar.dashboard.window import SyncChecker

        mock_client = MagicMock()
        mock_client.is_available = False

        callback_calls = []

        with patch("opencode_status_bar.api.get_api_client", return_value=mock_client):
            checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
            try:
                checker._check()
                assert callback_calls == []
                assert checker._known_sync is None
            finally:
                checker.stop()

    def test_sync_checker_handles_exception(self, qapp):
        """SyncChecker handles exceptions gracefully without crashing."""
        from opencode_status_bar.dashboard.window import SyncChecker

        callback_calls = []

        with patch(
            "opencode_status_bar.api.get_api_client",
            side_effect=RuntimeError("Connection error"),
        ):
            checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
            try:
                # Should not crash
                checker._check()
                assert callback_calls == [], "No callbacks on error"
                # Verify checker is still functional
                assert checker._timer is not None, "Timer should exist"
                assert checker._timer.isActive(), "Timer should still be active"
            finally:
                checker.stop()


# =============================================================================
# AnalyticsSection Tests - Key Format Compatibility
# =============================================================================


class TestAnalyticsSectionKeyFormats:
    """Tests for AnalyticsSection handling of different key formats."""

    @pytest.fixture
    def analytics_section(self, qapp):
        """Create AnalyticsSection for testing."""
        from opencode_status_bar.dashboard.sections.analytics import AnalyticsSection

        section = AnalyticsSection()
        yield section
        section.deleteLater()

    @pytest.mark.parametrize(
        "key_name,key_value",
        [
            pytest.param("tool", "bash", id="tool_key"),
            pytest.param("tool_name", "write", id="tool_name_key"),
        ],
    )
    def test_update_data_tool_keys(self, analytics_section, key_name, key_value):
        """AnalyticsSection accepts both 'tool' and 'tool_name' keys."""
        tools = [
            {
                key_name: key_value,
                "invocations": 10,
                "failures": 1,
                "failure_rate": "10.0%",
            }
        ]

        analytics_section.update_data(
            sessions=10,
            messages=100,
            tokens="5K",
            cache_hit="60%",
            agents=[],
            tools=tools,
            skills=[],
        )

        assert analytics_section._tools_table.rowCount() == 1
        assert analytics_section._tools_table.item(0, 0).text() == key_value
        assert analytics_section._tools_table.item(0, 1).text() == "10"  # invocations
        assert analytics_section._tools_table.item(0, 2).text() == "1"  # failures
        assert (
            analytics_section._tools_table.item(0, 3).text() == "10.0%"
        )  # failure_rate

    @pytest.mark.parametrize(
        "key_name,key_value",
        [
            pytest.param("skill", "functional-testing", id="skill_key"),
            pytest.param("skill_name", "agentic-flow", id="skill_name_key"),
        ],
    )
    def test_update_data_skill_keys(self, analytics_section, key_name, key_value):
        """AnalyticsSection accepts both 'skill' and 'skill_name' keys."""
        skills = [{key_name: key_value, "load_count": 5}]

        analytics_section.update_data(
            sessions=10,
            messages=100,
            tokens="5K",
            cache_hit="60%",
            agents=[],
            tools=[],
            skills=skills,
        )

        assert analytics_section._skills_table.rowCount() == 1
        assert analytics_section._skills_table.item(0, 0).text() == key_value
        assert analytics_section._skills_table.item(0, 1).text() == "5"  # load_count

    def test_update_data_all_fields(self, analytics_section):
        """AnalyticsSection updates all tables correctly."""
        analytics_section.update_data(
            sessions=42,
            messages=256,
            tokens="10.5K",
            cache_hit="75%",
            agents=[{"agent": "agent1", "messages": 50, "tokens": 1000}],
            tools=[
                {
                    "tool": "bash",
                    "invocations": 100,
                    "failures": 5,
                    "failure_rate": "5.0%",
                }
            ],
            skills=[{"skill": "testing", "load_count": 10}],
        )

        # Verify tables are populated with correct data
        assert analytics_section._agents_table.rowCount() == 1
        assert analytics_section._agents_table.item(0, 0).text() == "agent1"
        assert analytics_section._agents_table.item(0, 1).text() == "50"  # messages
        assert (
            analytics_section._agents_table.item(0, 2).text() == "1K"
        )  # tokens (formatted)

        assert analytics_section._tools_table.rowCount() == 1
        assert analytics_section._tools_table.item(0, 0).text() == "bash"
        assert analytics_section._tools_table.item(0, 1).text() == "100"  # invocations
        assert analytics_section._tools_table.item(0, 2).text() == "5"  # failures
        assert (
            analytics_section._tools_table.item(0, 3).text() == "5.0%"
        )  # failure_rate

        assert analytics_section._skills_table.rowCount() == 1
        assert analytics_section._skills_table.item(0, 0).text() == "testing"
        assert analytics_section._skills_table.item(0, 1).text() == "10"  # load_count
