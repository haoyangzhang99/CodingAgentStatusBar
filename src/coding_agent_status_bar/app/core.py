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
from ..core.reminders import dismiss, load_dismissed, reminder_for, save_dismissed
from ..core.settings import load_settings, visible_states
from ..ui.menu import MenuBuilder, tint_yellow
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
    dismissed: Optional[list[dict]] = None,
) -> tuple[str, str, bool]:
    """Return (menu bar label, SF Symbol name, needs attention) for all apps together.

    Priority: approvals and questions, then a low-usage reminder not yet dismissed, then
    working, done and idle.
    """
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
    reminder = reminder_for({"Codex": codex, "Claude Code": claude}, dismissed or [])
    if reminder:
        return reminder, "gauge.with.dots.needle.0percent", True
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
    usage = hooks.usage
    return (hooks.running,) + tuple(
        (
            s.id, s.full_dir, s.status, s.has_pending_ask_user,
            tuple(t.may_need_permission for t in s.tools),
        )
        for s in hooks.sessions
    ) + (
        # The reset time isn't shown, but a new window can bring back a dismissed reminder.
        tuple((limit.name, limit.left, limit.resets_at) for limit in usage.limits)
        if usage else None,
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
    dismissed: Optional[list[dict]] = None,
) -> str:
    """One log line describing the status, without session titles or paths."""
    title = status_for(state, codex, claude, dismissed)[0]
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
        # Low-usage reminders you've seen; guarded by _state_lock.
        self._dismissed: list[dict] = load_dismissed()
        # Replaced, never changed in place; guarded by _state_lock.
        self._settings: dict[str, bool] = load_settings()
        self._settings_window = None

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
        if not getattr(self, "_menu_watched", False) and hasattr(self, "_nsapp"):
            self._menu_watched = True
            try:
                self._watch_menu()
            except Exception as exc:
                error(f"Could not watch the menu for low-usage reminders: {exc}")
        if self._needs_refresh:
            self._build_menu()
            self._update_title()
            self._needs_refresh = False

    def _watch_menu(self):
        """Opening the menu dismisses low-usage reminders. rumps has no callback for it."""
        import AppKit

        menu = self._nsapp.nsstatusitem.menu()
        self._menu_observer = (
            AppKit.NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
                AppKit.NSMenuDidBeginTrackingNotification, menu, None,
                lambda _notification: self._on_menu_open(),
            )
        )

    def _on_menu_open(self):
        """Move low-usage reminders out of the menu bar; their rows stay yellow."""
        with self._state_lock:
            _, codex, claude = visible_states(self._settings, None, self._codex, self._claude)
            apps = {"Codex": codex, "Claude Code": claude}
            changed = dismiss(apps, self._dismissed, time.time())
            dismissed = list(self._dismissed)
        if not changed:
            return
        try:
            save_dismissed(dismissed)
        except OSError as exc:
            error(f"Could not save dismissed reminders: {exc}")
        self._update_title()

    def _update_title(self):
        """Update the compact status label and native menu bar presentation."""
        with self._state_lock:
            state, codex, claude = visible_states(
                self._settings, self._state, self._codex, self._claude
            )
            dismissed = list(self._dismissed)

        title, symbol, attention = status_for(state, codex, claude, dismissed)

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
                image = tint_yellow(image, (16, 16))
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
                    dismissed = list(self._dismissed)
                    settings = self._settings

                fingerprint = (
                    state_fingerprint(new_state),
                    hook_fingerprint(new_codex),
                    hook_fingerprint(new_claude),
                )
                if fingerprint != last_fingerprint:
                    last_fingerprint = fingerprint
                    self._needs_refresh = True

                summary = status_summary(
                    *visible_states(settings, new_state, new_codex, new_claude), dismissed
                )
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
