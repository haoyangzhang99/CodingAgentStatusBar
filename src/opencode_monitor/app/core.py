"""
Core OpenCodeApp class - Main menu bar application.

This module provides the OpenCodeApp class which:
- Manages application state and lifecycle
- Polls status snapshots written by the OpenCode desktop bridge plugin
- Combines MenuMixin and HandlersMixin for functionality

Trimmed build: the dashboard, analytics indexer, security auditor, local API
server, Claude usage polling, and legacy port scanning are not started or
imported. Their code remains in the repository.
"""

import threading
import time
from typing import Optional

import rumps

from ..core.models import State, SessionStatus, Usage
from ..core.monitor.bridge import read_bridge_state
from ..ui.menu import MenuBuilder
from ..utils.logger import info, error

from .handlers import HandlersMixin
from .menu import MenuMixin


def status_for(state: Optional[State]) -> tuple[str, str, bool]:
    """Return (menu bar label, SF Symbol name, needs attention) for a state."""
    if state is None or not state.connected:
        return "OpenCode offline", "terminal", False
    agents = [agent for inst in state.instances for agent in inst.agents]
    approval = any(tool.may_need_permission for a in agents for tool in a.tools)
    question = any(a.has_pending_ask_user for a in agents)
    if approval and question:
        return "Needs attention", "exclamationmark.circle", True
    if approval:
        return "Awaiting approval", "hand.raised", True
    if question:
        return "Awaiting answer", "questionmark.circle", True
    busy = [a for a in agents if a.status == SessionStatus.BUSY]
    if busy:
        root_count = sum(not a.is_subagent for a in busy)
        return (f"{root_count} working" if root_count > 1 else "Working..."), "terminal", False
    if agents:
        return "Done", "checkmark.circle", False
    return "OpenCode idle", "terminal", False


def state_fingerprint(state: Optional[State]) -> tuple:
    """Everything the menu displays, excluding timestamps, for change detection."""
    if state is None:
        return ()
    return (state.connected,) + tuple(
        (
            inst.port,
            agent.id,
            agent.title,
            agent.full_dir,
            agent.parent_id,
            agent.status,
            agent.has_pending_ask_user,
            tuple((tool.name, tool.may_need_permission) for tool in agent.tools),
        )
        for inst in state.instances
        for agent in inst.agents
    )


def status_summary(state: Optional[State]) -> str:
    """One log line describing the status, without session titles or paths."""
    title = status_for(state)[0]
    agents = [a for inst in (state.instances if state else []) for a in inst.agents]
    busy = sum(a.status == SessionStatus.BUSY and not a.is_subagent for a in agents)
    attention = sum(
        a.has_pending_ask_user or any(t.may_need_permission for t in a.tools)
        for a in agents
    )
    return (
        f"{title} (sessions: {len(agents)}, working: {busy}, "
        f"needing attention: {attention})"
    )


class OpenCodeApp(HandlersMixin, MenuMixin, rumps.App):
    """Main menu bar application.

    Combines:
    - HandlersMixin: Callback handlers (must come first for MRO)
    - MenuMixin: Menu building and preferences
    - rumps.App: macOS menu bar functionality
    """

    POLL_INTERVAL = 2  # seconds

    def __init__(self):
        super().__init__(
            name="OpenCode Monitor",
            title="OpenCode",
            quit_button=None,  # type: ignore[arg-type]  # rumps accepts None to disable quit button
        )

        # State tracking
        self._state: Optional[State] = None
        self._usage: Optional[Usage] = None  # Usage polling is disabled
        self._state_lock = threading.Lock()
        self._running = True
        self._needs_refresh = True
        self._port_names: dict[int, str] = {}
        self._PORT_NAMES_LIMIT = 50

        # Security alerts raised while rendering tool rows in the dropdown
        self._security_alerts: list = []
        self._max_alerts = 20
        self._has_critical_alert = False

        # Menu builder
        self._menu_builder = MenuBuilder(self._port_names, self._PORT_NAMES_LIMIT)

        # Build initial menu
        self._build_static_menu()

        # Start background monitoring
        self._monitor_thread = threading.Thread(
            target=self._run_monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    @rumps.timer(2)
    def _ui_refresh(self, _):
        """Timer callback to refresh UI on main thread."""
        if not getattr(self, "_menu_bar_logged", False) and hasattr(self, "_nsapp"):
            item = self._nsapp.nsstatusitem
            window = item.button().window()
            if window is not None:
                info(f"Menu bar ready: visible={item.isVisible()}, frame={window.frame()}")
                self._menu_bar_logged = True
        if self._needs_refresh:
            self._build_menu()
            self._update_title()
            self._needs_refresh = False

    def _update_title(self):
        """Update the compact status label and native menu bar presentation."""
        with self._state_lock:
            state = self._state

        title, symbol, attention = status_for(state)

        # Keep rumps' plain title in sync before styling its native button.
        self.title = title
        nsapp = getattr(self, "_nsapp", None)
        item = getattr(nsapp, "nsstatusitem", None)
        if item is None:
            return
        button = item.button()
        if button is None:
            return

        import AppKit

        # Plain text and a template image let macOS adapt to each Space's menu bar.
        button.setTitle_(title)
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            symbol, title
        )
        if image is not None:
            image = image.copy()
            image.setSize_((16, 16))
            if attention:
                # Color only the icon's pixels; button tint also affects native text.
                colored = AppKit.NSImage.alloc().initWithSize_((16, 16))
                colored.lockFocus()
                try:
                    rect = ((0, 0), (16, 16))
                    image.drawInRect_fromRect_operation_fraction_(
                        rect, AppKit.NSZeroRect, AppKit.NSCompositingOperationSourceOver, 1.0
                    )
                    AppKit.NSColor.systemYellowColor().set()
                    AppKit.NSRectFillUsingOperation(rect, AppKit.NSCompositingOperationSourceIn)
                finally:
                    colored.unlockFocus()
                colored.setTemplate_(False)
                image = colored
            else:
                image.setTemplate_(True)
        button.setImage_(image)
        button.setImagePosition_(AppKit.NSImageLeft)
        button.setContentTintColor_(None)
        button.setAccessibilityLabel_(f"OpenCode: {title}")
        button.setNeedsDisplay_(True)

    def _run_monitor_loop(self):
        """Poll bridge snapshots; log and redraw only when something changes."""
        info("OpenCode Monitor started")
        last_fingerprint = None
        last_summary = None
        last_error = None

        while self._running:
            start_time = time.time()
            try:
                new_state = read_bridge_state()
                with self._state_lock:
                    self._state = new_state

                fingerprint = state_fingerprint(new_state)
                if fingerprint != last_fingerprint:
                    last_fingerprint = fingerprint
                    self._needs_refresh = True

                summary = status_summary(new_state)
                if summary != last_summary:
                    last_summary = summary
                    info(f"Status changed: {summary}")
                last_error = None
            except Exception as e:
                message = f"Monitor error: {e}"
                # Repeat failures every 2 seconds would flood the log.
                if message != last_error:
                    last_error = message
                    error(message)

            elapsed = time.time() - start_time
            time.sleep(max(0, self.POLL_INTERVAL - elapsed))

        info("OpenCode Monitor stopped")


def main():
    """Main entry point."""
    app = OpenCodeApp()
    app.run()


if __name__ == "__main__":
    main()
