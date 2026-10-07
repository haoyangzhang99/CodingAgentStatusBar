"""
Tests for StatusBarApp (rumps menu bar application).

Tests the application logic, callbacks, and state management.
Mocks rumps and external dependencies to test behavior without UI.

Consolidated tests: Each test validates multiple related assertions for better coverage.
"""

import json
import sys
import os
import subprocess
import time
import pytest
from typing import cast
from unittest.mock import MagicMock, patch

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
        if "coding_agent_status_bar.app" in sys.modules:
            del sys.modules["coding_agent_status_bar.app"]


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for StatusBarApp.

    Strategy: Patch at SOURCE level BEFORE reloading the app module.
    This ensures that when the module is reloaded, all imports resolve
    to our mocks rather than the real functions.
    """
    # Create mock objects
    mock_menu_builder = MagicMock()
    mock_read_state = MagicMock()
    mock_info = MagicMock()
    mock_error = MagicMock()
    mock_debug = MagicMock()

    # Configure mocks

    mock_builder_instance = MagicMock()
    mock_builder_instance.build_dynamic_items.return_value = []
    mock_builder_instance.build_hook_items.return_value = []
    mock_menu_builder.return_value = mock_builder_instance

    from coding_agent_status_bar.core.models import HookState

    # Tests must never see the real Codex or Claude apps or status files.
    mock_read_codex = MagicMock(return_value=HookState())
    mock_read_claude = MagicMock(return_value=HookState())

    # Patch at SOURCE level (where functions are defined)
    # Then reload the app module so imports resolve to mocks
    with (
        patch("coding_agent_status_bar.ui.menu.MenuBuilder", mock_menu_builder),
        patch("coding_agent_status_bar.core.monitor.bridge.read_bridge_state", mock_read_state),
        patch("coding_agent_status_bar.core.monitor.hooks.read_codex_state", mock_read_codex),
        patch("coding_agent_status_bar.core.monitor.hooks.read_claude_state", mock_read_claude),
        patch("coding_agent_status_bar.utils.logger.info", mock_info),
        patch("coding_agent_status_bar.utils.logger.error", mock_error),
        patch("coding_agent_status_bar.utils.logger.debug", mock_debug),
    ):
        # Remove ALL cached app modules so they get re-imported with mocks
        # The app package has: __init__, core, menu, handlers
        modules_to_remove = [
            "coding_agent_status_bar.app",
            "coding_agent_status_bar.app.core",
            "coding_agent_status_bar.app.menu",
            "coding_agent_status_bar.app.handlers",
        ]
        for mod_name in modules_to_remove:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        # Now import the app module - imports will resolve to mocks
        import coding_agent_status_bar.app  # noqa: F401

        yield {
            "menu_builder": mock_menu_builder,
            "builder_instance": mock_builder_instance,
            "read_state": mock_read_state,
            "read_codex": mock_read_codex,
            "read_claude": mock_read_claude,
            "info": mock_info,
            "error": mock_error,
            "debug": mock_debug,
        }

        # Clean up - remove all app modules so next test gets fresh ones
        for mod_name in modules_to_remove:
            if mod_name in sys.modules:
                del sys.modules[mod_name]


def create_app_with_mocks(mock_dependencies, skip_monitor=True):
    """Helper to create StatusBarApp with proper mocking."""
    from coding_agent_status_bar.app import StatusBarApp

    if skip_monitor:
        with patch.object(StatusBarApp, "_run_monitor_loop"):
            app = StatusBarApp()
    else:
        app = StatusBarApp()

    return app


def get_title(app) -> str:
    """Get app title as string (handles None case for type checker)."""
    return str(app.title) if app.title else ""


# =============================================================================
# Group 1: Init (2 → 1 test)
# =============================================================================


class TestStatusBarAppInit:
    """Tests for StatusBarApp.__init__"""

    def test_init_full(self, mock_dependencies):
        """App should initialize state and the monitor thread, and nothing else."""
        from coding_agent_status_bar.app import StatusBarApp

        app = create_app_with_mocks(mock_dependencies)

        # State initialization
        assert app._state is None
        assert app._codex is None
        assert app._claude is None
        assert app.title == "Agents"
        assert app._running  # Direct boolean assertion
        assert app._needs_refresh  # Direct boolean assertion

        # Class constants
        assert StatusBarApp.POLL_INTERVAL == 2
        assert app._PORT_NAMES_LIMIT == 50

        mock_dependencies["menu_builder"].assert_called_once()
        # Status is only read by the background loop, never during startup.
        mock_dependencies["read_state"].assert_not_called()
        mock_dependencies["read_codex"].assert_not_called()
        mock_dependencies["read_claude"].assert_not_called()
        # Verify thread exists and is configured correctly
        assert hasattr(app, "_monitor_thread")
        assert app._monitor_thread.daemon  # Direct boolean assertion


@pytest.mark.skipif(sys.platform != "darwin", reason="rumps requires macOS")
def test_app_imports_in_a_fresh_process():
    """The real app package imports cleanly, catching references to removed code."""
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
    script = (
        "import coding_agent_status_bar.app as app\n"
        "assert callable(app.main)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONPATH": src},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr


# =============================================================================
# Group 2: Static Menu (1 test - unchanged)
# =============================================================================


class TestBuildStaticMenu:
    """Tests for StatusBarApp._build_static_menu"""

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
    """Tests for StatusBarApp._ui_refresh"""

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
    """Tests for StatusBarApp._build_menu"""

    def test_open_opencode_is_first_and_launches_desktop(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        assert app.menu[0].title == "Show OpenCode"
        app._build_menu()
        assert app.menu[0] is app._open_opencode_item
        with patch("coding_agent_status_bar.app.handlers.subprocess.run") as run:
            app.menu[0].callback(None)
        run.assert_called_once_with(
            ["/usr/bin/open", "-b", "ai.opencode.desktop"],
            check=True, capture_output=True, timeout=5,
        )

    def test_open_opencode_failure_does_not_crash_menu(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        with patch("coding_agent_status_bar.app.handlers.subprocess.run", side_effect=OSError("Unavailable")), \
             patch("coding_agent_status_bar.app.handlers.error") as log_error:
            app._open_opencode(None)
        log_error.assert_called_once()

    def test_show_codex_is_second_and_launches_desktop(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        assert app.menu[1].title == "Show Codex"
        app._build_menu()
        assert app.menu[1] is app._open_codex_item
        with patch("coding_agent_status_bar.app.handlers.subprocess.run") as run:
            app.menu[1].callback(None)
        run.assert_called_once_with(
            ["/usr/bin/open", "-b", "com.openai.codex"],
            check=True, capture_output=True, timeout=5,
        )
        with patch("coding_agent_status_bar.app.handlers.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("open", 5)), \
             patch("coding_agent_status_bar.app.handlers.error") as log_error:
            app._open_codex(None)
        log_error.assert_called_once()

    def test_show_claude_is_third_and_launches_desktop(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        assert app.menu[2].title == "Show Claude"
        app._build_menu()
        assert app.menu[2] is app._open_claude_item
        with patch("coding_agent_status_bar.app.handlers.subprocess.run") as run:
            app.menu[2].callback(None)
        run.assert_called_once_with(
            ["/usr/bin/open", "-b", "com.anthropic.claudefordesktop"],
            check=True, capture_output=True, timeout=5,
        )
        with patch("coding_agent_status_bar.app.handlers.subprocess.run",
                   side_effect=OSError("Unavailable")), \
             patch("coding_agent_status_bar.app.handlers.error") as log_error:
            app._open_claude(None)
        log_error.assert_called_once()

    def test_codex_and_claude_sections_follow_opencode_rows(self, mock_dependencies):
        opencode_row = MockMenuItem("OpenCode session")
        codex_rows = [MockMenuItem("Codex"), MockMenuItem("project")]
        claude_rows = [MockMenuItem("Claude Code"), MockMenuItem("other")]
        builder = mock_dependencies["builder_instance"]
        builder.build_dynamic_items.return_value = [opencode_row]
        builder.build_hook_items.side_effect = (
            lambda state, name, on_select: codex_rows if name == "Codex" else claude_rows
        )

        app = create_app_with_mocks(mock_dependencies)
        app._build_menu()

        assert builder.build_hook_items.call_args_list == [
            ((app._codex, "Codex"), {"on_select": app._open_codex}),
            ((app._claude, "Claude Code"), {"on_select": app._open_claude}),
        ]
        assert cast(MockMenu, app.menu)._items == [
            app._open_opencode_item, app._open_codex_item, app._open_claude_item,
            None, opencode_row, None, *codex_rows, None, *claude_rows,
            None, app._refresh_item, app._settings_item, None, app._quit_item,
        ]

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
        mock_dependencies["builder_instance"].build_dynamic_items.assert_called_with(
            app._state, on_select=app._open_opencode
        )

        # Menu cleared and items added (cast to MockMenu for test access)
        menu = cast(MockMenu, app.menu)
        assert menu._clear_called  # Direct boolean assertion
        assert menu._items == [
            app._open_opencode_item, app._open_codex_item, app._open_claude_item,
            None, mock_item1, mock_item2, None, app._refresh_item, app._settings_item, None,
            app._quit_item,
        ]



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
        ],
    )
    def test_update_title_default(self, mock_dependencies, state_config):
        """Should distinguish disconnected state from connected without sessions."""
        from coding_agent_status_bar.core.models import State

        app = create_app_with_mocks(mock_dependencies)

        if "state" in state_config:
            app._state = None
        elif state_config.get("connected") is False:
            app._state = State(connected=False)
        elif state_config.get("empty_parts"):
            app._state = State(connected=True)

        app._update_title()

        title = get_title(app)
        expected = "Agents idle" if app._state and app._state.connected else "Agents offline"
        assert title == expected


# =============================================================================
# Group 9: Update Title - Permission (2 → 1 test)
# =============================================================================


class TestUpdateTitlePermission:
    """Tests for approval detection in StatusBarApp._update_title"""

    @pytest.mark.parametrize(
        "tool_name,pending,expected_lock",
        [
            ("Approval required", True, True),
            ("bash", False, False),
            (None, False, False),
        ],
    )
    def test_update_title_permission_full(
        self, mock_dependencies, tool_name, pending, expected_lock
    ):
        """A pending approval from the plugin takes priority over busy status."""
        from coding_agent_status_bar.core.models import (
            State,
            Instance,
            Agent,
            Tool,
            SessionStatus,
        )

        app = create_app_with_mocks(mock_dependencies)

        if tool_name:
            tool = Tool(name=tool_name, permission_pending=pending)
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
        app._state = State(instances=[instance], connected=True)

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
            (0, 0, False, False, False, False, "Agents offline", "terminal"),
            (0, 0, False, False, False, True, "Agents idle", "terminal"),
            (0, 0, True, False, False, True, "Done", "checkmark.circle"),
            (1, 2, True, False, False, True, "Working...", "terminal"),
            (2, 2, False, False, False, True, "2 working", "terminal"),
            (0, 2, True, False, False, True, "Working...", "terminal"),
            (1, 1, False, True, False, True, "Awaiting approval", "hand.raised"),
            (1, 1, False, False, True, True, "Awaiting answer", "questionmark.circle"),
            (2, 1, False, True, True, True, "Needs attention", "exclamationmark.circle"),
            (0, 1, False, True, True, False, "Agents offline", "terminal"),
        ],
    )
    def test_native_status(
        self, mock_dependencies, roots, children, idle, approval, question,
        connected, title, symbol,
    ):
        """Use native colors; child attention wins without inflating counts."""
        from coding_agent_status_bar.core.models import Agent, Instance, SessionStatus, State, Tool

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
        button.setAccessibilityLabel_.assert_called_once_with(f"Agents: {title}")
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
        assert title == "Agents offline"
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
        button.setAccessibilityLabel_.assert_called_once_with(f"Agents: {title}")
        button.setNeedsDisplay_.assert_called_once_with(True)


class TestUpdateTitleIdle:
    """Tests for idle instances in StatusBarApp._update_title"""

    @pytest.mark.parametrize(
        "idle_count", [2, 1, 0],
    )
    def test_update_title_idle_instances(
        self, mock_dependencies, idle_count
    ):
        """Empty instances must not dilute the busy status."""
        from coding_agent_status_bar.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
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
            connected=True,
        )

        app._update_title()

        title = get_title(app)
        assert title == "Working..."


def hook_session(sid="ses", status="BUSY", permission=False, question=False):
    """A Codex or Claude Code session as read from its status file."""
    from coding_agent_status_bar.core.models import Agent, SessionStatus, Tool

    return Agent(
        id=sid, title="project", dir="project", full_dir="/work/project",
        status=getattr(SessionStatus, status),
        tools=[Tool(name="Approval required", permission_pending=True)] if permission else [],
        has_pending_ask_user=question,
    )


def opencode_state(*statuses, connected=True, question=False):
    """An OpenCode state with one root session per status; "SUB" adds a working sub-agent."""
    from coding_agent_status_bar.core.models import Agent, Instance, SessionStatus, State

    agents = [
        Agent(
            id=str(i), title="Session", dir=".", full_dir="/test",
            status=SessionStatus.BUSY if status == "SUB" else getattr(SessionStatus, status),
            parent_id="0" if status == "SUB" else None,
        )
        for i, status in enumerate(statuses)
    ]
    if question:
        agents[-1].has_pending_ask_user = True
    return State(instances=[Instance(port=-1, agents=agents)], connected=connected)


class TestCombinedStatus:
    """One status for OpenCode, Codex and Claude Code together, without app names."""

    @pytest.mark.parametrize(
        "opencode,codex_running,codex,title,symbol,attention",
        [
            # Neither app running
            (None, False, [], "Agents offline", "terminal", False),
            (opencode_state(connected=False), False, [("BUSY", False)],
             "Agents offline", "terminal", False),
            # Idle, or one idle and the other not running
            (opencode_state(), False, [], "Agents idle", "terminal", False),
            (None, True, [], "Agents idle", "terminal", False),
            (opencode_state(), True, [], "Agents idle", "terminal", False),
            # One session working, in either app
            (None, True, [("BUSY", False)], "Working...", "terminal", False),
            (opencode_state("BUSY"), True, [], "Working...", "terminal", False),
            # Sessions add up across both apps; sub-agents don't count
            (opencode_state("BUSY", "SUB", "SUB"), True, [], "Working...", "terminal", False),
            (opencode_state("BUSY"), True, [("BUSY", False)], "2 working", "terminal", False),
            (opencode_state("IDLE"), True, [("BUSY", False)] * 2, "2 working", "terminal", False),
            (opencode_state("BUSY", "SUB"), True, [("BUSY", False)] * 2,
             "3 working", "terminal", False),
            # Done in either app, nothing working
            (opencode_state("IDLE"), True, [], "Done", "checkmark.circle", False),
            (None, True, [("IDLE", False)], "Done", "checkmark.circle", False),
            # Attention wins over working, from either app
            (opencode_state("BUSY"), True, [("BUSY", True)],
             "Awaiting approval", "hand.raised", True),
            (opencode_state("BUSY", question=True), True, [("BUSY", False)],
             "Awaiting answer", "questionmark.circle", True),
            (opencode_state("BUSY", question=True), True, [("BUSY", True)],
             "Needs attention", "exclamationmark.circle", True),
            # A Codex that isn't running contributes nothing
            (opencode_state("IDLE"), False, [("BUSY", True)], "Done", "checkmark.circle", False),
        ],
    )
    def test_status(self, mock_dependencies, opencode, codex_running, codex, title, symbol,
                    attention):
        from coding_agent_status_bar.app.core import status_for
        from coding_agent_status_bar.core.models import HookState

        state = HookState(running=codex_running, sessions=[
            hook_session(str(i), status, permission)
            for i, (status, permission) in enumerate(codex)
        ])
        assert status_for(opencode, state) == (title, symbol, attention)

    @pytest.mark.parametrize(
        "codex,claude_running,claude,title,symbol,attention",
        [
            # Claude Code alone decides offline or idle, like Codex
            ([], False, [], "Agents offline", "terminal", False),
            ([], True, [], "Agents idle", "terminal", False),
            ([], False, [("BUSY", False, False)], "Agents offline", "terminal", False),
            # Sessions add up across all three apps
            ([], True, [("BUSY", False, False)], "Working...", "terminal", False),
            ([("BUSY", False)], True, [("BUSY", False, False)] * 2,
             "4 working", "terminal", False),
            ([], True, [("IDLE", False, False)], "Done", "checkmark.circle", False),
            # Claude Code can wait for an answer, and its attention wins over working
            ([("BUSY", False)], True, [("BUSY", False, True)],
             "Awaiting answer", "questionmark.circle", True),
            ([], True, [("BUSY", True, False)], "Awaiting approval", "hand.raised", True),
            ([("BUSY", True)], True, [("BUSY", False, True)],
             "Needs attention", "exclamationmark.circle", True),
        ],
    )
    def test_claude_code_joins_the_status(
        self, mock_dependencies, codex, claude_running, claude, title, symbol, attention,
    ):
        from coding_agent_status_bar.app.core import status_for
        from coding_agent_status_bar.core.models import HookState

        codex_state = HookState(running=bool(codex), sessions=[
            hook_session(f"c{i}", status, permission)
            for i, (status, permission) in enumerate(codex)
        ])
        claude_state = HookState(running=claude_running, sessions=[
            hook_session(f"a{i}", status, permission, question)
            for i, (status, permission, question) in enumerate(claude)
        ])
        opencode = opencode_state("BUSY") if title == "4 working" else None
        assert status_for(opencode, codex_state, claude_state) == (title, symbol, attention)

    def test_codex_approval_turns_icon_yellow(self, mock_dependencies):
        from coding_agent_status_bar.core.models import HookState, State

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(connected=True)
        app._codex = HookState(running=True, sessions=[hook_session(permission=True)])
        app._nsapp = MagicMock()
        native = MagicMock()
        with patch.dict(sys.modules, {"AppKit": native}):
            app._update_title()

        title = "Awaiting approval"
        assert app.title == title
        native.NSImage.imageWithSystemSymbolName_accessibilityDescription_.assert_called_once_with(
            "hand.raised", title
        )
        native.NSColor.systemYellowColor.return_value.set.assert_called_once()
        button = app._nsapp.nsstatusitem.button.return_value
        button.setTitle_.assert_called_once_with(title)
        button.setAccessibilityLabel_.assert_called_once_with(f"Agents: {title}")


def usage_app(*limits, sessions=(), running=True):
    """A running Codex or Claude Code with a usage reading."""
    from coding_agent_status_bar.core.models import HookState, Usage

    return HookState(running=running, sessions=list(sessions), usage=Usage(list(limits), time.time()))


def weekly(left, resets=None):
    from coding_agent_status_bar.core.models import UsageLimit

    return UsageLimit("Weekly", left, resets or time.time() + 86400)


class TestUsageReminder:
    """A low limit shows in the menu bar until the menu is opened."""

    GAUGE = "gauge.with.dots.needle.0percent"

    def test_reminder_comes_after_requests_and_before_working(self, mock_dependencies):
        from coding_agent_status_bar.app.core import status_for

        codex = usage_app(weekly(8), sessions=[hook_session()])
        assert status_for(None, codex) == ("Codex: 8% left", self.GAUGE, True)
        waiting = usage_app(weekly(8), sessions=[hook_session(permission=True)])
        assert status_for(None, waiting) == ("Awaiting approval", "hand.raised", True)
        asking = usage_app(weekly(8), sessions=[hook_session(question=True)])
        assert status_for(None, None, asking)[0] == "Awaiting answer"

    def test_dismissed_reminder_leaves_the_menu_bar(self, mock_dependencies):
        from coding_agent_status_bar.app.core import status_for

        limit = weekly(8)
        codex = usage_app(limit, sessions=[hook_session()])
        dismissed = [{"app": "Codex", "limit": "Weekly", "resets_at": limit.resets_at}]
        assert status_for(None, codex, None, dismissed) == ("Working...", "terminal", False)

    def test_opening_the_menu_dismisses_and_remembers(self, mock_dependencies, tmp_path, monkeypatch):
        from coding_agent_status_bar.core import reminders

        path = tmp_path / "dismissed.json"
        monkeypatch.setattr(reminders, "dismissed_file", lambda: path)
        app = create_app_with_mocks(mock_dependencies)
        app._codex = usage_app(weekly(8))
        app._update_title()
        assert get_title(app) == "Codex: 8% left"
        app._on_menu_open()
        assert get_title(app) == "Agents idle"
        assert json.loads(path.read_text())[0]["limit"] == "Weekly"

        restarted = create_app_with_mocks(mock_dependencies)
        restarted._codex = app._codex
        restarted._update_title()
        assert get_title(restarted) == "Agents idle"

    def test_opening_the_menu_without_reminders_changes_nothing(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        app._codex = usage_app(weekly(50))
        app._update_title = MagicMock()
        with patch("coding_agent_status_bar.app.core.save_dismissed") as save:
            app._on_menu_open()
        save.assert_not_called()
        app._update_title.assert_not_called()

    def test_menu_is_watched_once(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = False
        app._nsapp = MagicMock()
        app._on_menu_open = MagicMock()
        native = MagicMock()
        with patch.dict(sys.modules, {"AppKit": native}):
            app._ui_refresh(None)
            app._ui_refresh(None)
        add = native.NSNotificationCenter.defaultCenter.return_value.addObserverForName_object_queue_usingBlock_
        add.assert_called_once()
        name, menu, queue, block = add.call_args.args
        assert name is native.NSMenuDidBeginTrackingNotification
        assert menu is app._nsapp.nsstatusitem.menu.return_value and queue is None
        block(object())
        app._on_menu_open.assert_called_once_with()

    def test_failing_to_watch_the_menu_is_logged_once(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = False
        app._nsapp = MagicMock()
        native = MagicMock()
        native.NSNotificationCenter.defaultCenter.side_effect = RuntimeError("No center")
        with patch.dict(sys.modules, {"AppKit": native}), \
             patch("coding_agent_status_bar.app.core.error") as log_error:
            app._ui_refresh(None)
            app._ui_refresh(None)
        log_error.assert_called_once()

    def test_usage_changes_redraw_the_menu(self, mock_dependencies):
        from coding_agent_status_bar.app.core import hook_fingerprint

        now = time.time()
        reading = usage_app(weekly(50, now + 100))
        assert hook_fingerprint(reading) != hook_fingerprint(usage_app(weekly(49, now + 100)))
        # A newer reading with the same numbers changes nothing shown.
        newer = usage_app(weekly(50, now + 100))
        newer.usage.updated = now + 600
        assert hook_fingerprint(reading) == hook_fingerprint(newer)
        # A new window can bring back a dismissed reminder, so it redraws too.
        assert hook_fingerprint(reading) != hook_fingerprint(usage_app(weekly(50, now + 7 * 86400)))


class TestSettings:
    """The Settings button and the switches in its window."""

    @pytest.fixture
    def saved(self, tmp_path, monkeypatch):
        from coding_agent_status_bar.core import settings

        path = tmp_path / "settings.json"
        monkeypatch.setattr(settings, "settings_file", lambda: path)
        return path

    def test_settings_button_sits_above_quit(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        assert app._settings_item.title == "Settings..."
        assert app._settings_item.callback == app._open_settings
        assert app._settings_item._menuitem.setImage_.call_args.args[0].isTemplate()
        app._build_menu()
        items = cast(MockMenu, app.menu)._items
        assert items[-4:] == [app._refresh_item, app._settings_item, None, app._quit_item]

    def test_turned_off_parts_leave_the_dropdown(self, mock_dependencies):
        codex_rows = [MockMenuItem("Codex")]
        builder = mock_dependencies["builder_instance"]
        builder.build_dynamic_items.return_value = [MockMenuItem("OpenCode")]
        builder.build_hook_items.side_effect = (
            lambda state, name, on_select: codex_rows if name == "Codex" and state else []
        )
        app = create_app_with_mocks(mock_dependencies)
        app._codex = usage_app(weekly(50))
        app._settings = {
            **app._settings, "show_opencode": False, "show_codex": False,
            "show_claude": False, "opencode": False, "codex": False, "refresh": False,
        }
        app._build_menu()
        builder.build_dynamic_items.assert_not_called()
        assert builder.build_hook_items.call_args_list[0].args[0] is None
        assert cast(MockMenu, app.menu)._items == [app._settings_item, None, app._quit_item]

        app._settings = {**app._settings, "codex": True}
        app._build_menu()
        assert cast(MockMenu, app.menu)._items == [
            *codex_rows, None, app._settings_item, None, app._quit_item,
        ]

    def test_turned_off_apps_leave_the_menu_bar(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        app._codex = usage_app(weekly(8), sessions=[hook_session()])
        app._update_title()
        assert get_title(app) == "Codex: 8% left"
        app._settings = {**app._settings, "codex_usage": False}
        app._update_title()
        assert get_title(app) == "Working..."
        app._settings = {**app._settings, "codex": False}
        app._update_title()
        assert get_title(app) == "Agents offline"

    def test_hidden_reminders_are_not_dismissed(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        app._codex = usage_app(weekly(8))
        app._settings = {**app._settings, "codex_usage": False}
        with patch("coding_agent_status_bar.app.core.save_dismissed") as save:
            app._on_menu_open()
        save.assert_not_called()
        assert app._dismissed == []

    def test_switch_change_is_saved_and_shown(self, mock_dependencies, saved):
        from coding_agent_status_bar.core.settings import load_settings

        app = create_app_with_mocks(mock_dependencies)
        app._settings_window = MagicMock()
        app._build_menu = MagicMock()
        app._update_title = MagicMock()
        app._on_setting_changed("refresh", False)
        assert app._settings["refresh"] is False
        assert json.loads(saved.read_text())["refresh"] is False
        assert load_settings()["refresh"] is False
        app._settings_window.update.assert_called_once_with(app._settings)
        app._build_menu.assert_called_once_with()
        app._update_title.assert_called_once_with()

    def test_failing_to_save_still_applies_the_change(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        app._build_menu = MagicMock()
        app._update_title = MagicMock()
        with patch("coding_agent_status_bar.app.handlers.save_settings",
                   side_effect=OSError("Read-only")), \
             patch("coding_agent_status_bar.app.handlers.error") as log_error:
            app._on_setting_changed("codex", False)
        log_error.assert_called_once()
        assert app._settings["codex"] is False
        app._build_menu.assert_called_once_with()

    def test_window_is_made_once(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        with patch("coding_agent_status_bar.app.handlers.SettingsWindow") as window_class:
            app._open_settings(None)
            app._open_settings(None)
        window_class.assert_called_once_with(app._on_setting_changed)
        assert window_class.return_value.show.call_count == 2
        window_class.return_value.show.assert_called_with(app._settings)

    def test_window_failure_is_logged(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        with patch("coding_agent_status_bar.app.handlers.SettingsWindow",
                   side_effect=RuntimeError("No AppKit")), \
             patch("coding_agent_status_bar.app.handlers.error") as log_error:
            app._open_settings(None)
        log_error.assert_called_once()


# =============================================================================
# Group 12: Main (1 test - unchanged)
# =============================================================================


class TestMain:
    """Tests for main() entry point"""

    def test_main_creates_and_runs_app(self, mock_dependencies):
        """Should create StatusBarApp instance and call run()."""
        from coding_agent_status_bar.app import main, StatusBarApp

        with (
            patch.object(StatusBarApp, "_run_monitor_loop"),
            patch.object(StatusBarApp, "run") as mock_run,
        ):
            main()

            mock_run.assert_called_once()


# =============================================================================
# Group 14: Monitor Loop (4 → 2 tests)
# =============================================================================


@pytest.mark.xdist_group(name="app_monitor_loop")
class TestMonitorLoop:
    """Tests for StatusBarApp._run_monitor_loop"""

    @staticmethod
    def _run(app, results, codex=None, claude=None):
        """Run the loop over a scripted sequence of states or exceptions."""
        from coding_agent_status_bar.core.models import HookState

        remaining = list(results)
        codex_remaining = list(codex or [HookState()] * len(remaining))
        claude_remaining = list(claude or [HookState()] * len(remaining))
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
            patch("coding_agent_status_bar.app.core.read_bridge_state", side_effect=read),
            patch("coding_agent_status_bar.app.core.read_codex_state",
                  side_effect=lambda: codex_remaining.pop(0)),
            patch("coding_agent_status_bar.app.core.read_claude_state",
                  side_effect=lambda: claude_remaining.pop(0)),
            patch("coding_agent_status_bar.app.core.time.sleep", side_effect=sleep),
        ):
            app._running = True
            app._run_monitor_loop()
        return refreshes

    @staticmethod
    def _state(status, updated, title="Private title"):
        from coding_agent_status_bar.core.models import Agent, Instance, SessionStatus, State

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
            "Status changed: Working... (OpenCode sessions: 1, Codex sessions: 0, "
            "Claude Code sessions: 0, working: 1, needing attention: 0)",
            "Status changed: Done (OpenCode sessions: 1, Codex sessions: 0, "
            "Claude Code sessions: 0, working: 0, needing attention: 0)",
        ]
        # Nothing identifying a session is written to the log.
        logged = str(mock_dependencies["info"].call_args_list)
        assert "Private title" not in logged and "/private/p" not in logged
        assert "State updated" not in logged

    def test_codex_and_claude_changes_redraw_and_log_without_paths(self, mock_dependencies):
        from coding_agent_status_bar.core.models import HookState

        app = create_app_with_mocks(mock_dependencies)

        def busy(question=False):
            return HookState(running=True, sessions=[hook_session(question=question)])

        refreshes = self._run(
            app,
            [self._state("BUSY", i) for i in range(5)],
            codex=[HookState(), busy(), busy(), HookState(running=True), HookState(running=True)],
            claude=[HookState(), HookState(), HookState(), busy(), busy(question=True)],
        )
        assert app._codex is not None and app._codex.running
        assert app._claude is not None and app._claude.sessions[0].has_pending_ask_user
        assert refreshes == [True, True, False, True, True]
        changes = [
            c.args[0] for c in mock_dependencies["info"].call_args_list
            if c.args[0].startswith("Status changed")
        ]
        assert changes == [
            "Status changed: Working... (OpenCode sessions: 1, Codex sessions: 0, "
            "Claude Code sessions: 0, working: 1, needing attention: 0)",
            "Status changed: 2 working (OpenCode sessions: 1, Codex sessions: 1, "
            "Claude Code sessions: 0, working: 2, needing attention: 0)",
            "Status changed: 2 working (OpenCode sessions: 1, Codex sessions: 0, "
            "Claude Code sessions: 1, working: 2, needing attention: 0)",
            "Status changed: Awaiting answer (OpenCode sessions: 1, Codex sessions: 0, "
            "Claude Code sessions: 1, working: 2, needing attention: 1)",
        ]
        assert "/work/project" not in str(mock_dependencies["info"].call_args_list)

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
        """State access should use lock, and refresh should set flag and log."""
        from coding_agent_status_bar.core.models import State

        app = create_app_with_mocks(mock_dependencies)

        # Verify lock exists and works
        assert hasattr(app, "_state_lock")

        with app._state_lock:
            app._state = State(connected=True)
            state = app._state

        assert state.connected  # Direct boolean assertion

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

    def test_question_title_and_empty_state(self, mock_dependencies):
        """A pending question wins over working; no sessions means idle."""
        from coding_agent_status_bar.core.models import State, Instance, Agent, SessionStatus

        app = create_app_with_mocks(mock_dependencies)
        agent = Agent(
            id="1", title="test", dir=".", full_dir="/test", status=SessionStatus.BUSY,
            has_pending_ask_user=True, ask_user_title="OpenCode needs your answer",
        )
        app._state = State(instances=[Instance(port=-1, agents=[agent])], connected=True)
        app._update_title()
        assert get_title(app) == "Awaiting answer"

        app._state = State(instances=[], connected=True)
        app._update_title()
        assert get_title(app) == "Agents idle"

    def test_removed_features_are_gone(self, mock_dependencies):
        app = create_app_with_mocks(mock_dependencies)
        for attr in ("_usage", "_security_alerts", "_add_security_alert", "_focus_terminal"):
            assert not hasattr(app, attr)
