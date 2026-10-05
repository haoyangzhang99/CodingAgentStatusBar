"""
Core StatusBarApp class - Main menu bar application.

This module provides the StatusBarApp class which:
- Manages application state and lifecycle
- Polls status snapshots written by the OpenCode desktop bridge plugin, and Codex and
  Claude Code hooks
- Combines MenuMixin and HandlersMixin for functionality
"""

import threading
import time
from typing import Optional

import rumps

from ..core.models import Agent, HookState, State, SessionStatus
from ..core.monitor.bridge import read_bridge_state
from ..core.monitor.hooks import read_claude_state, read_codex_state
from ..ui.menu import MenuBuilder
from ..utils.logger import info, error

from .handlers import HandlersMixin
from .menu import MenuMixin


def opencode_sessions(state: Optional[State]) -> list[Agent]:
    if state is None or not state.connected:
        return []
    return [agent for inst in state.instances for agent in inst.agents]


def hook_sessions(hooks: Optional[HookState]) -> list[Agent]:
    return hooks.sessions if hooks is not None and hooks.running else []


def status_for(
    state: Optional[State],
    codex: Optional[HookState] = None,
    claude: Optional[HookState] = None,
) -> tuple[str, str, bool]:
    """Return (menu bar label, SF Symbol name, needs attention) for all apps together."""
    if (state is None or not state.connected) and not any(
        hooks is not None and hooks.running for hooks in (codex, claude)
    ):
        return "Agents offline", "terminal", False
    sessions = opencode_sessions(state) + hook_sessions(codex) + hook_sessions(claude)
    approval = any(tool.may_need_permission for s in sessions for tool in s.tools)
    question = any(s.has_pending_ask_user for s in sessions)
    if approval and question:
        return "Needs attention", "exclamationmark.circle", True
    if approval:
        return "Awaiting approval", "hand.raised", True
    if question:
        return "Awaiting answer", "questionmark.circle", True
    busy = [s for s in sessions if s.status == SessionStatus.BUSY]
    if busy:
        # Count sessions, not sub-agents. Codex and Claude Code report sub-agents under
        # their session.
        root_count = sum(not s.is_subagent for s in busy)
        return (f"{root_count} working" if root_count > 1 else "Working..."), "terminal", False
    if sessions:
        return "Done", "checkmark.circle", False
    return "Agents idle", "terminal", False


def hook_fingerprint(hooks: Optional[HookState]) -> tuple:
    """Everything the menu displays about Codex or Claude Code, for change detection."""
    if hooks is None:
        return ()
    return (hooks.running,) + tuple(
        (
            s.id, s.full_dir, s.status, s.has_pending_ask_user,
            tuple(t.may_need_permission for t in s.tools),
        )
        for s in hooks.sessions
    )


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


def status_summary(
    state: Optional[State],
    codex: Optional[HookState] = None,
    claude: Optional[HookState] = None,
) -> str:
    """One log line describing the status, without session titles or paths."""
    title = status_for(state, codex, claude)[0]
    opencode, codex_list, claude_list = (
        opencode_sessions(state), hook_sessions(codex), hook_sessions(claude)
    )
    sessions = opencode + codex_list + claude_list
    busy = sum(s.status == SessionStatus.BUSY and not s.is_subagent for s in sessions)
    attention = sum(
        s.has_pending_ask_user or any(t.may_need_permission for t in s.tools)
        for s in sessions
    )
    return (
        f"{title} (OpenCode sessions: {len(opencode)}, Codex sessions: {len(codex_list)}, "
        f"Claude Code sessions: {len(claude_list)}, working: {busy}, "
        f"needing attention: {attention})"
    )


class StatusBarApp(HandlersMixin, MenuMixin, rumps.App):
    """Main menu bar application.

    Combines:
    - HandlersMixin: Callback handlers (must come first for MRO)
    - MenuMixin: Menu building and preferences
    - rumps.App: macOS menu bar functionality
    """

    POLL_INTERVAL = 2  # seconds

    def __init__(self):
        super().__init__(
            name="Coding Agent Status Bar",
            title="Agents",
            quit_button=None,  # type: ignore[arg-type]  # rumps accepts None to disable quit button
        )

        # State tracking
        self._state: Optional[State] = None
        self._codex: Optional[HookState] = None
        self._claude: Optional[HookState] = None
        self._state_lock = threading.Lock()
        self._running = True
        self._needs_refresh = True
        self._port_names: dict[int, str] = {}
        self._PORT_NAMES_LIMIT = 50

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
            codex = self._codex
            claude = self._claude

        title, symbol, attention = status_for(state, codex, claude)

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
        button.setAccessibilityLabel_(f"Agents: {title}")
        button.setNeedsDisplay_(True)

    def _run_monitor_loop(self):
        """Poll OpenCode, Codex and Claude Code status files; log and redraw only when
        something changes."""
        info("Coding Agent Status Bar started")
        last_fingerprint = None
        last_summary = None
        last_error = None

        while self._running:
            start_time = time.time()
            try:
                new_state = read_bridge_state()
                new_codex = read_codex_state()
                new_claude = read_claude_state()
                with self._state_lock:
                    self._state = new_state
                    self._codex = new_codex
                    self._claude = new_claude

                fingerprint = (
                    state_fingerprint(new_state),
                    hook_fingerprint(new_codex),
                    hook_fingerprint(new_claude),
                )
                if fingerprint != last_fingerprint:
                    last_fingerprint = fingerprint
                    self._needs_refresh = True

                summary = status_summary(new_state, new_codex, new_claude)
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

        info("Coding Agent Status Bar stopped")


def main():
    """Main entry point."""
    app = StatusBarApp()
    app.run()


if __name__ == "__main__":
    main()
