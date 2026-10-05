"""
Menu mixin for StatusBarApp - Contains menu building methods.

This module provides the MenuMixin class with:
- Static menu building (_build_static_menu)
- Dynamic menu building (_build_menu)
"""

import threading
from typing import Optional

import rumps

from ..core.models import HookState, State
from ..ui.menu import MenuBuilder, set_menu_symbol


class MenuMixin:
    """Mixin providing menu building methods for StatusBarApp."""

    # Type hints for attributes from StatusBarApp
    _state: Optional[State]
    _codex: Optional[HookState]
    _claude: Optional[HookState]
    _state_lock: threading.Lock
    _menu_builder: MenuBuilder

    # Menu items (will be set by _build_static_menu)
    _open_opencode_item: rumps.MenuItem
    _open_codex_item: rumps.MenuItem
    _open_claude_item: rumps.MenuItem
    _refresh_item: rumps.MenuItem
    _quit_item: rumps.MenuItem

    # Handlers (will be provided by HandlersMixin)
    def _on_refresh(self, _): ...
    def _open_opencode(self, _): ...
    def _open_codex(self, _): ...
    def _open_claude(self, _): ...

    def _build_static_menu(self):
        """Build the static menu items."""
        self._open_opencode_item = rumps.MenuItem(
            "Show OpenCode", callback=self._open_opencode
        )
        self._open_codex_item = rumps.MenuItem("Show Codex", callback=self._open_codex)
        self._open_claude_item = rumps.MenuItem("Show Claude", callback=self._open_claude)
        self._refresh_item = rumps.MenuItem("Refresh", callback=self._on_refresh)
        set_menu_symbol(self._refresh_item, "arrow.clockwise")
        self._quit_item = rumps.MenuItem("Quit", callback=rumps.quit_application)

        # Initial menu
        self.menu = [
            self._open_opencode_item,
            self._open_codex_item,
            self._open_claude_item,
            None,
            rumps.MenuItem("Loading...", callback=None),
            None,
            self._refresh_item,
            None,
            self._quit_item,
        ]

    def _build_menu(self):
        """Build the menu from current state."""
        with self._state_lock:
            state = self._state
            codex = self._codex
            claude = self._claude

        # Clicking a session row brings its app to the front.
        sections = [
            self._menu_builder.build_dynamic_items(state, on_select=self._open_opencode),
            self._menu_builder.build_hook_items(codex, "Codex", on_select=self._open_codex),
            self._menu_builder.build_hook_items(
                claude, "Claude Code", on_select=self._open_claude
            ),
        ]

        # Rebuild complete menu (rumps.App.menu has .add()/.clear() but no type stubs)
        self.menu.clear()  # type: ignore[attr-defined]
        self.menu.add(self._open_opencode_item)  # type: ignore[attr-defined]
        self.menu.add(self._open_codex_item)  # type: ignore[attr-defined]
        self.menu.add(self._open_claude_item)  # type: ignore[attr-defined]
        for items in sections:
            if items:
                self.menu.add(None)  # type: ignore[attr-defined]
                for item in items:
                    self.menu.add(item)  # type: ignore[attr-defined]

        self.menu.add(None)  # type: ignore[attr-defined]
        self.menu.add(self._refresh_item)  # type: ignore[attr-defined]
        self.menu.add(None)  # type: ignore[attr-defined]
        self.menu.add(self._quit_item)  # type: ignore[attr-defined]
