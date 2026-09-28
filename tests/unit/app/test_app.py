"""
Tests for OpenCodeApp (rumps menu bar application).

Tests the application logic, callbacks, state management, and security features.
Mocks rumps and external dependencies to test behavior without UI.

Consolidated tests: Each test validates multiple related assertions for better coverage.
"""

import sys
import os
import subprocess
import pytest
from typing import cast
from unittest.mock import MagicMock, patch

# Import RiskLevel at module level for parametrized tests
from opencode_status_bar.security.analyzer import RiskLevel

pytestmark = pytest.mark.xdist_group(name="app_tests_sequential")


# Create comprehensive rumps mock BEFORE importing app
class MockMenuItem:
    """Mock rumps.MenuItem with proper menu behavior."""

    def __init__(self, title="", callback=None, **kwargs):
        self.title = title
        self.callback = callback
        self._items = {}
        self.state = 0
        self._menuitem = MagicMock()
        self.parent = None

    def add(self, item):
        if isinstance(item, MockMenuItem):
            self._items[item.title] = item
            item.parent = self
        elif item is None:
            # Separator
            pass

    def clear(self):
        self._items = {}

    def values(self):
        return list(self._items.values())

    def __iter__(self):
        return iter(self._items.values())


class MockMenu:
    """Mock rumps menu with proper list-like and method behavior."""

    def __init__(self):
        self._items = []
        self._clear_called = False
        self._add_calls = []

    def clear(self):
        self._items = []
        self._clear_called = True

    def add(self, item):
        self._items.append(item)
        self._add_calls.append(item)

    def __setitem__(self, key, value):
        pass

    def __getitem__(self, key):
        return self._items[key] if isinstance(key, int) else None

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class MockApp:
    """Mock rumps.App base class."""

    def __init__(self, name="", title="", quit_button=None, **kwargs):
        self.name = name
        self.title = title
        self._menu = MockMenu()

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, value):
        # When assigning a list, convert to MockMenu items
        if isinstance(value, list):
            self._menu = MockMenu()
            for item in value:
                self._menu.add(item)
        else:
            self._menu = value

    def run(self):
        pass


@pytest.fixture(scope="function", autouse=True)
def setup_rumps_mock():
    """Setup rumps mock for each test function.

    Function-scoped to prevent test pollution in parallel execution.
    Each test gets fresh mocks instead of sharing module-level state.
    """
    original_rumps = sys.modules.get("rumps", None)

    rumps_mock = MagicMock()
    rumps_mock.App = MockApp
    rumps_mock.MenuItem = MockMenuItem
    rumps_mock.timer = lambda interval: lambda f: f
    rumps_mock.quit_application = MagicMock()

    sys.modules["rumps"] = rumps_mock

    yield rumps_mock

    if original_rumps is not None:
        sys.modules["rumps"] = original_rumps
        if "opencode_status_bar.app" in sys.modules:
            del sys.modules["opencode_status_bar.app"]


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for OpenCodeApp.

    Strategy: Patch at SOURCE level BEFORE reloading the app module.
    This ensures that when the module is reloaded, all imports resolve
    to our mocks rather than the real functions.
    """
    # Create mock objects
    mock_menu_builder = MagicMock()
    mock_get_settings = MagicMock()
    mock_save_settings = MagicMock()
    mock_focus_iterm2 = MagicMock()
    mock_read_state = MagicMock()
    mock_info = MagicMock()
    mock_error = MagicMock()
    mock_debug = MagicMock()

    # Configure mocks
    mock_settings = MagicMock()
    mock_settings.permission_threshold_seconds = 5  # 5 seconds threshold
    mock_get_settings.return_value = mock_settings

    mock_builder_instance = MagicMock()
    mock_builder_instance.build_dynamic_items.return_value = []
    mock_menu_builder.return_value = mock_builder_instance

    # Patch at SOURCE level (where functions are defined)
    # Then reload the app module so imports resolve to mocks
    with (
        patch("opencode_status_bar.ui.menu.MenuBuilder", mock_menu_builder),
        patch("opencode_status_bar.utils.settings.get_settings", mock_get_settings),
        patch("opencode_status_bar.utils.settings.save_settings", mock_save_settings),
        patch("opencode_status_bar.ui.terminal.focus_iterm2", mock_focus_iterm2),
        patch("opencode_status_bar.core.monitor.bridge.read_bridge_state", mock_read_state),
        patch("opencode_status_bar.utils.logger.info", mock_info),
        patch("opencode_status_bar.utils.logger.error", mock_error),
        patch("opencode_status_bar.utils.logger.debug", mock_debug),
    ):
        # Remove ALL cached app modules so they get re-imported with mocks
        # The app package has: __init__, core, menu, handlers
        # NOTE: Do NOT remove indexer modules - we need the mock to stay applied
        modules_to_remove = [
            "opencode_status_bar.app",
            "opencode_status_bar.app.core",
            "opencode_status_bar.app.menu",
            "opencode_status_bar.app.handlers",
        ]
        for mod_name in modules_to_remove:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        # Now import the app module - imports will resolve to mocks
        import opencode_status_bar.app  # noqa: F401

        yield {
            "menu_builder": mock_menu_builder,
            "builder_instance": mock_builder_instance,
            "get_settings": mock_get_settings,
            "save_settings": mock_save_settings,
            "settings": mock_settings,
            "focus_iterm2": mock_focus_iterm2,
            "read_state": mock_read_state,
            "info": mock_info,
            "error": mock_error,
            "debug": mock_debug,
        }

        # Clean up - remove all app modules so next test gets fresh ones
        for mod_name in modules_to_remove:
            if mod_name in sys.modules:
                del sys.modules[mod_name]


def create_app_with_mocks(mock_dependencies, skip_monitor=True):
    """Helper to create OpenCodeApp with proper mocking."""
    from opencode_status_bar.app import OpenCodeApp

    if skip_monitor:
        with patch.object(OpenCodeApp, "_run_monitor_loop"):
            app = OpenCodeApp()
    else:
        app = OpenCodeApp()

    return app


def get_title(app) -> str:
    """Get app title as string (handles None case for type checker)."""
    return str(app.title) if app.title else ""


# =============================================================================
# Group 1: Init (2 → 1 test)
# =============================================================================


class TestOpenCodeAppInit:
    """Tests for OpenCodeApp.__init__"""

    def test_init_full(self, mock_dependencies):
        """App should initialize state and the monitor thread, and nothing else."""
        from opencode_status_bar.app import OpenCodeApp

        app = create_app_with_mocks(mock_dependencies)

        # State initialization
        assert app._state is None
        assert app.title == "OpenCode"
        assert app._usage is None
        assert app._running  # Direct boolean assertion
        assert app._needs_refresh  # Direct boolean assertion
        assert app._security_alerts == []
        assert not app._has_critical_alert  # Direct boolean assertion

        # Class constants
        assert OpenCodeApp.POLL_INTERVAL == 2
        assert app._PORT_NAMES_LIMIT == 50

        mock_dependencies["menu_builder"].assert_called_once()
        # Status is only read by the background loop, never during startup.
        mock_dependencies["read_state"].assert_not_called()
        # Verify thread exists and is configured correctly
        assert hasattr(app, "_monitor_thread")
        assert app._monitor_thread.daemon  # Direct boolean assertion


@pytest.mark.skipif(sys.platform != "darwin", reason="rumps requires macOS")
def test_app_import_skips_heavy_optional_features():
    """Starting the menu bar app must not load the dashboard, analytics or HTTP stack."""
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
    script = (
        "import sys, opencode_status_bar.app\n"
        "heavy = [m for m in ('PyQt6', 'duckdb', 'aiohttp', 'flask', 'watchdog') if m in sys.modules]\n"
        "print(','.join(heavy))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONPATH": src},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


# =============================================================================
# Group 2: Static Menu (1 test - unchanged)
# =============================================================================


class TestBuildStaticMenu:
    """Tests for OpenCodeApp._build_static_menu"""

    def test_build_static_menu_creates_all_items(self, mock_dependencies):
        """Should create Show OpenCode, refresh and quit, without removed features."""
        app = create_app_with_mocks(mock_dependencies)

        # All menu items exist
        assert hasattr(app, "_open_opencode_item")
        assert hasattr(app, "_refresh_item")
        assert app._refresh_item.title == "Refresh"
        refresh_image = app._refresh_item._menuitem.setImage_.call_args.args[0]
        assert refresh_image.isTemplate()
        assert hasattr(app, "_quit_item")
        assert hasattr(app, "menu")
        titles = [getattr(item, "title", None) for item in app.menu]
        assert not any("Dashboard" in str(t) or "Preferences" in str(t) for t in titles)
        assert not hasattr(app, "_make_interval_callback")
        assert not hasattr(app, "_make_ask_timeout_callback")
        assert not hasattr(app, "_show_dashboard")


# =============================================================================
# Group 5: UI Refresh (1 test - unchanged)
# =============================================================================


class TestUIRefresh:
    """Tests for OpenCodeApp._ui_refresh"""

    @pytest.mark.parametrize(
        "needs_refresh,should_rebuild",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_ui_refresh_behavior(
        self, mock_dependencies, needs_refresh, should_rebuild
    ):
        """Should rebuild menu only when _needs_refresh is True."""
        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = needs_refresh

        app._build_menu = MagicMock()
        app._update_title = MagicMock()

        app._ui_refresh(None)

        if should_rebuild:
            app._build_menu.assert_called_once()
            app._update_title.assert_called_once()
            assert not app._needs_refresh  # Direct boolean assertion
        else:
            app._build_menu.assert_not_called()
            app._update_title.assert_not_called()


# =============================================================================
# Group 6: Build Menu (2 → 1 test)
# =============================================================================


class TestBuildMenu:
    """Tests for OpenCodeApp._build_menu"""

    def test_open_opencode_is_first_and_launches_desktop(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        assert app.menu[0].title == "Show OpenCode"
        app._build_menu()
        assert app.menu[0] is app._open_opencode_item
        with patch("opencode_status_bar.app.handlers.subprocess.run") as run:
            app.menu[0].callback(None)
        run.assert_called_once_with(
            ["/usr/bin/open", "-b", "ai.opencode.desktop"],
            check=True, capture_output=True, timeout=5,
        )

    def test_open_opencode_failure_does_not_crash_menu(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        with patch("opencode_status_bar.app.handlers.subprocess.run", side_effect=OSError("Unavailable")), \
             patch("opencode_status_bar.app.handlers.error") as log_error:
            app._open_opencode(None)
        log_error.assert_called_once()

    def test_build_menu_full(self, mock_dependencies):
        """Should use MenuBuilder, clear menu, and add dynamic plus static items."""
        mock_item1 = MockMenuItem("Item 1")
        mock_item2 = MockMenuItem("Item 2")
        mock_dependencies["builder_instance"].build_dynamic_items.return_value = [
            mock_item1,
            mock_item2,
        ]

        app = create_app_with_mocks(mock_dependencies)

        app._build_menu()

        # Uses MenuBuilder
        mock_dependencies["builder_instance"].build_dynamic_items.assert_called()

        # Menu cleared and items added (cast to MockMenu for test access)
        menu = cast(MockMenu, app.menu)
        assert menu._clear_called  # Direct boolean assertion
        assert menu._items == [
            app._open_opencode_item, None, mock_item1, mock_item2,
            None, app._refresh_item, None, app._quit_item,
        ]


# =============================================================================
# Group 7: Update Title - Usage (1 test - unchanged)
# =============================================================================


class TestUpdateTitleUsage:
    """Usage belongs in the dropdown, not the status title."""

    @pytest.mark.parametrize(
        "utilization", [95, 75, 55, 30],
    )
    def test_update_title_usage_levels(
        self, mock_dependencies, utilization
    ):
        """Usage levels should not affect the compact status label."""
        from opencode_status_bar.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(), connected=True)
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=utilization),
            seven_day=UsagePeriod(utilization=50),
        )

        app._update_title()

        title = get_title(app)
        assert title == "OpenCode idle"


# =============================================================================
# Group 8: Update Title - Default (1 test - unchanged)
# =============================================================================


class TestUpdateTitleDefault:
    """Tests for neutral offline and idle labels."""

    @pytest.mark.parametrize(
        "state_config",
        [
            {"state": None},  # No state
            {"connected": False},  # Not connected
            {"connected": True, "empty_parts": True},  # Connected but no data
            {"usage_error": True},  # Usage has error
        ],
    )
    def test_update_title_default(self, mock_dependencies, state_config):
        """Should distinguish disconnected state from connected without sessions."""
        from opencode_status_bar.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)

        if "state" in state_config:
            app._state = None
        elif state_config.get("connected") is False:
            app._state = State(connected=False)
        elif state_config.get("empty_parts"):
            app._state = State(todos=Todos(pending=0, in_progress=0), connected=True)
            app._usage = None
        elif state_config.get("usage_error"):
            app._state = State(todos=Todos(), connected=True)
            app._usage = Usage(five_hour=UsagePeriod(utilization=50), error="API error")

        app._update_title()

        title = get_title(app)
        expected = "OpenCode idle" if app._state and app._state.connected else "OpenCode offline"
        assert title == expected
        if state_config.get("usage_error"):
            assert "%" not in title


# =============================================================================
# Group 9: Update Title - Permission (2 → 1 test)
# =============================================================================


class TestUpdateTitlePermission:
    """Tests for permission detection in OpenCodeApp._update_title"""

    @pytest.mark.parametrize(
        "tool_name,elapsed_ms,expected_lock",
        [
            ("bash", 10000, True),
            ("bash", 2000, False),
            ("task", 60000, False),
            (None, 0, False),
        ],
    )
    def test_update_title_permission_full(
        self, mock_dependencies, tool_name, elapsed_ms, expected_lock
    ):
        """Existing permission signals should take priority over busy status."""
        from opencode_status_bar.core.models import (
            State,
            Instance,
            Agent,
            Tool,
            SessionStatus,
            Todos,
        )

        app = create_app_with_mocks(mock_dependencies)

        if tool_name:
            tool = Tool(name=tool_name, arg="test", elapsed_ms=elapsed_ms)
            tools = [tool]
        else:
            tools = []

        agent = Agent(
            id="1",
            title="test",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
            tools=tools,
        )
        instance = Instance(port=1234, agents=[agent])
        app._state = State(instances=[instance], todos=Todos(), connected=True)

        app._update_title()

        title = get_title(app)
        assert title == ("Awaiting approval" if expected_lock else "Working...")


# =============================================================================
# Group 10: Update Title - Idle (1 test - unchanged)
# =============================================================================


class TestNativeStatusTitle:
    @pytest.mark.parametrize(
        "roots,children,idle,approval,question,connected,title,symbol",
        [
            (0, 0, False, False, False, False, "OpenCode offline", "terminal"),
            (0, 0, False, False, False, True, "OpenCode idle", "terminal"),
            (0, 0, True, False, False, True, "Done", "checkmark.circle"),
            (1, 2, True, False, False, True, "Working...", "terminal"),
            (2, 2, False, False, False, True, "2 working", "terminal"),
            (0, 2, True, False, False, True, "Working...", "terminal"),
            (1, 1, False, True, False, True, "Awaiting approval", "hand.raised"),
            (1, 1, False, False, True, True, "Awaiting answer", "questionmark.circle"),
            (2, 1, False, True, True, True, "Needs attention", "exclamationmark.circle"),
            (0, 1, False, True, True, False, "OpenCode offline", "terminal"),
        ],
    )
    def test_native_status(
        self, mock_dependencies, roots, children, idle, approval, question,
        connected, title, symbol,
    ):
        """Use native colors; child attention wins without inflating counts."""
        from opencode_status_bar.core.models import Agent, Instance, SessionStatus, State, Tool

        app = create_app_with_mocks(mock_dependencies)
        agents = [
            Agent(
                id=str(i), title="Session", dir=".", full_dir="/test",
                status=SessionStatus.BUSY,
                parent_id="root" if i >= roots else None,
            )
            for i in range(roots + children)
        ]
        if idle:
            agents.append(Agent(
                id="idle", title="Recent session", dir=".", full_dir="/test",
                status=SessionStatus.IDLE,
            ))
        if approval:
            agents[-1].tools = [Tool(name="bash", permission_pending=True)]
        if question:
            agents[-1].has_pending_ask_user = True
        app._state = State(instances=[Instance(port=1234, agents=agents)], connected=connected)

        native = MagicMock()
        with patch.dict(sys.modules, {"AppKit": native}):
            # Before rumps creates the status item, only the plain title is set.
            app._update_title()
            assert app.title == title
            native.NSColor.assert_not_called()
            assert native.mock_calls == []

            app._nsapp = MagicMock()
            button = app._nsapp.nsstatusitem.button.return_value
            app._update_title()

        assert native.NSAttributedString.mock_calls == []
        assert native.NSFont.mock_calls == []
        button.setAttributedTitle_.assert_not_called()
        native.NSImage.imageWithSystemSymbolName_accessibilityDescription_.assert_called_once_with(symbol, title)
        native.NSImage.imageWithSystemSymbolName_accessibilityDescription_.return_value.copy.assert_called_once_with()
        image = native.NSImage.imageWithSystemSymbolName_accessibilityDescription_.return_value.copy.return_value
        image.setSize_.assert_called_once_with((16, 16))
        if connected and (approval or question):
            colored = native.NSImage.alloc.return_value.initWithSize_.return_value
            native.NSImage.alloc.return_value.initWithSize_.assert_called_once_with((16, 16))
            colored.lockFocus.assert_called_once()
            image.drawInRect_fromRect_operation_fraction_.assert_called_once_with(
                ((0, 0), (16, 16)), native.NSZeroRect,
                native.NSCompositingOperationSourceOver, 1.0,
            )
            native.NSColor.systemYellowColor.return_value.set.assert_called_once()
            native.NSRectFillUsingOperation.assert_called_once_with(
                ((0, 0), (16, 16)), native.NSCompositingOperationSourceIn,
            )
            colored.unlockFocus.assert_called_once()
            colored.setTemplate_.assert_called_once_with(False)
            image = colored
        else:
            assert native.NSColor.mock_calls == []
            image.setTemplate_.assert_called_once_with(True)
            native.NSImage.alloc.assert_not_called()
            image.drawInRect_fromRect_operation_fraction_.assert_not_called()
            native.NSRectFillUsingOperation.assert_not_called()
        button.setTitle_.assert_called_once_with(title)
        button.setImagePosition_.assert_called_once_with(native.NSImageLeft)
        button.setImage_.assert_called_once_with(image)
        button.setContentTintColor_.assert_called_once_with(None)
        button.setAccessibilityLabel_.assert_called_once_with(f"OpenCode: {title}")
        button.setNeedsDisplay_.assert_called_once_with(True)
        assert app.title == title

    def test_missing_symbol_clears_image_preserving_text(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        app._nsapp = MagicMock()
        native = MagicMock()
        native.NSImage.imageWithSystemSymbolName_accessibilityDescription_.return_value = None
        with patch.dict(sys.modules, {"AppKit": native}):
            app._update_title()
        title = get_title(app)
        assert title == "OpenCode offline"
        native.NSImage.imageWithSystemSymbolName_accessibilityDescription_.assert_called_once_with("terminal", title)
        assert native.NSAttributedString.mock_calls == []
        assert native.NSColor.mock_calls == []
        assert native.NSFont.mock_calls == []
        native.NSImage.alloc.assert_not_called()
        native.NSRectFillUsingOperation.assert_not_called()
        button = app._nsapp.nsstatusitem.button.return_value
        button.setAttributedTitle_.assert_not_called()
        button.setTitle_.assert_called_once_with(title)
        button.setImage_.assert_called_once_with(None)
        button.setImagePosition_.assert_called_once_with(native.NSImageLeft)
        button.setContentTintColor_.assert_called_once_with(None)
        button.setAccessibilityLabel_.assert_called_once_with(f"OpenCode: {title}")
        button.setNeedsDisplay_.assert_called_once_with(True)


class TestUpdateTitleIdle:
    """Tests for idle instances in OpenCodeApp._update_title"""

    @pytest.mark.parametrize(
        "idle_count", [2, 1, 0],
    )
    def test_update_title_idle_instances(
        self, mock_dependencies, idle_count
    ):
        """Empty instances must not dilute the busy status."""
        from opencode_status_bar.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
        )

        app = create_app_with_mocks(mock_dependencies)

        # Create busy instance
        busy_agent = Agent(
            id="busy-1",
            title="Busy",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
        )
        busy_instance = Instance(port=1234, agents=[busy_agent])

        # Create idle instances
        idle_instances = [Instance(port=1235 + i, agents=[]) for i in range(idle_count)]

        app._state = State(
            instances=[busy_instance] + idle_instances,
            todos=Todos(),
            connected=True,
        )

        app._update_title()

        title = get_title(app)
        assert title == "Working..."


# =============================================================================
# Group 11: Security Alerts (3 → 1 test)
# =============================================================================


class TestAddSecurityAlert:
    """Tests for OpenCodeApp._add_security_alert"""

    @pytest.mark.parametrize(
        "level,expected_log_text",
        [
            (RiskLevel.CRITICAL, "CRITICAL"),
            (RiskLevel.HIGH, "HIGH"),
        ],
    )
    def test_add_security_alert_full(self, mock_dependencies, level, expected_log_text):
        """Should store alerts, limit max, prevent duplicates, set critical flag, and log."""
        from opencode_status_bar.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)
        app._max_alerts = 5

        # Add multiple alerts to test storage and limiting
        for i in range(7):
            alert = SecurityAlert(
                command=f"command_{i}",
                tool="bash",
                score=100 if level == RiskLevel.CRITICAL else 60,
                level=level,
                reason="Test",
            )
            app._add_security_alert(alert)

        # Limited to max_alerts
        assert len(app._security_alerts) == 5

        # Newest at front
        assert app._security_alerts[0].command == "command_6"

        # Critical flag set correctly
        expected_critical = level == RiskLevel.CRITICAL
        assert app._has_critical_alert is expected_critical

        # Logging with correct level
        mock_dependencies["info"].assert_called()
        call_args = str(mock_dependencies["info"].call_args)
        assert expected_log_text in call_args

        # Test duplicate prevention
        duplicate_alert = SecurityAlert(
            command="command_6",  # Same as last added
            tool="bash",
            score=100,
            level=level,
            reason="Duplicate",
        )
        initial_count = len(app._security_alerts)
        app._add_security_alert(duplicate_alert)
        assert len(app._security_alerts) == initial_count  # No change


# =============================================================================
# Group 12: Main (1 test - unchanged)
# =============================================================================


class TestMain:
    """Tests for main() entry point"""

    def test_main_creates_and_runs_app(self, mock_dependencies):
        """Should create OpenCodeApp instance and call run()."""
        from opencode_status_bar.app import main, OpenCodeApp

        with (
            patch.object(OpenCodeApp, "_run_monitor_loop"),
            patch.object(OpenCodeApp, "run") as mock_run,
        ):
            main()

            mock_run.assert_called_once()


# =============================================================================
# Group 14: Monitor Loop (4 → 2 tests)
# =============================================================================


@pytest.mark.xdist_group(name="app_monitor_loop")
class TestMonitorLoop:
    """Tests for OpenCodeApp._run_monitor_loop"""

    @staticmethod
    def _run(app, results):
        """Run the loop over a scripted sequence of states or exceptions."""
        remaining = list(results)
        refreshes = []

        def read():
            if len(remaining) == 1:
                app._running = False
            item = remaining.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        def sleep(_):
            refreshes.append(app._needs_refresh)
            app._needs_refresh = False

        with (
            patch("opencode_status_bar.app.core.read_bridge_state", side_effect=read),
            patch("opencode_status_bar.app.core.time.sleep", side_effect=sleep),
        ):
            app._running = True
            app._run_monitor_loop()
        return refreshes

    @staticmethod
    def _state(status, updated, title="Private title"):
        from opencode_status_bar.core.models import Agent, Instance, SessionStatus, State

        agent = Agent(
            id="ses_1", title=title, dir="p", full_dir="/private/p",
            status=getattr(SessionStatus, status),
        )
        return State(instances=[Instance(port=-1, agents=[agent])], connected=True, updated=updated)

    def test_logs_and_redraws_only_when_status_changes(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        states = [
            self._state("BUSY", 1), self._state("BUSY", 2), self._state("BUSY", 3),
            self._state("IDLE", 4), self._state("IDLE", 5),
        ]
        refreshes = self._run(app, states)

        assert app._state is states[-1]
        # Timestamps alone never trigger a redraw.
        assert refreshes == [True, False, False, True, False]
        changes = [
            c.args[0] for c in mock_dependencies["info"].call_args_list
            if c.args[0].startswith("Status changed")
        ]
        assert changes == [
            "Status changed: Working... (sessions: 1, working: 1, needing attention: 0)",
            "Status changed: Done (sessions: 1, working: 0, needing attention: 0)",
        ]
        # Nothing identifying a session is written to the log.
        logged = str(mock_dependencies["info"].call_args_list)
        assert "Private title" not in logged and "/private/p" not in logged
        assert "State updated" not in logged

    def test_title_change_redraws_menu_without_logging(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        refreshes = self._run(app, [
            self._state("BUSY", 1, "First"), self._state("BUSY", 2, "Renamed"),
        ])
        assert refreshes == [True, True]
        changes = [
            c for c in mock_dependencies["info"].call_args_list
            if c.args[0].startswith("Status changed")
        ]
        assert len(changes) == 1

    def test_repeated_errors_are_logged_once(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        self._run(app, [
            OSError("Unreadable"), OSError("Unreadable"), OSError("Unreadable"),
            self._state("BUSY", 1), OSError("Unreadable"), ValueError("Other"),
        ])
        messages = [c.args[0] for c in mock_dependencies["error"].call_args_list]
        assert messages == [
            "Monitor error: Unreadable",
            "Monitor error: Unreadable",
            "Monitor error: Other",
        ]


# =============================================================================
# Group 15: Thread Safety & On Refresh (2 → 1 test)
# =============================================================================


class TestThreadSafetyAndRefresh:
    """Tests for thread safety and refresh behavior"""

    def test_state_access_and_refresh(self, mock_dependencies):
        """State/usage access should use lock, and refresh should set flag and log."""
        from opencode_status_bar.core.models import State, Usage, UsagePeriod

        app = create_app_with_mocks(mock_dependencies)

        # Verify lock exists and works
        assert hasattr(app, "_state_lock")

        with app._state_lock:
            app._state = State(connected=True)
            state = app._state

        assert state.connected  # Direct boolean assertion

        with app._state_lock:
            app._usage = Usage(five_hour=UsagePeriod(utilization=75))
            usage = app._usage

        assert usage.five_hour.utilization == 75

        # Test refresh behavior
        app._needs_refresh = False
        app._on_refresh(None)

        mock_dependencies["info"].assert_called()
        assert app._needs_refresh  # Direct boolean assertion


# =============================================================================
# Group 16: Additional Coverage (5 → 2 tests)
# =============================================================================


class TestAdditionalCoverage:
    """Additional tests for complete coverage"""

    def test_title_with_all_elements_and_edge_cases(self, mock_dependencies):
        """Should handle complex title, empty instances, and focus terminal."""
        from opencode_status_bar.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
            Usage,
            UsagePeriod,
        )

        app = create_app_with_mocks(mock_dependencies)

        # Test complex title with all elements
        agent = Agent(
            id="1",
            title="test",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
            has_pending_ask_user=True,
            ask_user_title="Validation requise",
        )
        instance = Instance(port=1234, agents=[agent])
        app._state = State(
            instances=[instance], todos=Todos(pending=3, in_progress=1), connected=True
        )
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=60), seven_day=UsagePeriod(utilization=40)
        )

        app._update_title()

        title = get_title(app)
        assert title == "Awaiting answer"

        # Test empty state
        app._state = State(instances=[], todos=Todos(), connected=True)
        app._usage = None
        app._update_title()
        assert get_title(app) == "OpenCode idle"

        # Test focus terminal
        app._focus_terminal("/dev/ttys001")
        mock_dependencies["focus_iterm2"].assert_called_once_with("/dev/ttys001")

    def test_max_alerts(self, mock_dependencies):
        """Should handle max alerts boundary correctly."""
        from opencode_status_bar.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)

        # Test max alerts boundary
        app._max_alerts = 3
        app._security_alerts = []

        for i in range(3):
            alert = SecurityAlert(
                command=f"cmd_{i}",
                tool="bash",
                score=50,
                level=RiskLevel.HIGH,
                reason="Test",
            )
            app._add_security_alert(alert)

        assert len(app._security_alerts) == 3

        # Add one more - should trim oldest
        alert = SecurityAlert(
            command="cmd_new",
            tool="bash",
            score=50,
            level=RiskLevel.HIGH,
            reason="Test",
        )
        app._add_security_alert(alert)

        assert len(app._security_alerts) == 3
        assert app._security_alerts[0].command == "cmd_new"
