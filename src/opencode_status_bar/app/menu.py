"""
Menu mixin for OpenCodeApp - Contains menu building methods.

This module provides the MenuMixin class with:
- Static menu building (_build_static_menu)
- Dynamic menu building (_build_menu)

The Dashboard entry and Preferences submenu (Claude usage refresh and the
legacy ask_user timeout) were removed along with the features they controlled.
"""

import threading
from typing import Optional

import rumps

from ..core.models import State, Usage
from ..ui.menu import MenuBuilder, set_menu_symbol


class MenuMixin:
    """Mixin providing menu building methods for OpenCodeApp."""

    # Type hints for attributes from OpenCodeApp
    _state: Optional[State]
    _usage: Optional[Usage]
    _state_lock: threading.Lock
    _menu_builder: MenuBuilder
    _has_critical_alert: bool

    # Menu items (will be set by _build_static_menu)
    _open_opencode_item: rumps.MenuItem
    _refresh_item: rumps.MenuItem
    _quit_item: rumps.MenuItem

    # Handlers (will be provided by HandlersMixin)
    def _focus_terminal(self, tty: str): ...
    def _add_security_alert(self, alert): ...
    def _on_refresh(self, _): ...
    def _open_opencode(self, _): ...

    def _build_static_menu(self):
        """Build the static menu items."""
        self._open_opencode_item = rumps.MenuItem(
            "Show OpenCode", callback=self._open_opencode
        )
        self._refresh_item = rumps.MenuItem("Refresh", callback=self._on_refresh)
        set_menu_symbol(self._refresh_item, "arrow.clockwise")
        self._quit_item = rumps.MenuItem("Quit", callback=rumps.quit_application)

        # Initial menu
        self.menu = [
            self._open_opencode_item,
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
            usage = self._usage

        # Build dynamic items using MenuBuilder
        dynamic_items = self._menu_builder.build_dynamic_items(
            state,
            usage,
            focus_callback=self._focus_terminal,
            alert_callback=self._add_security_alert,
        )

        # Rebuild complete menu (rumps.App.menu has .add()/.clear() but no type stubs)
        self.menu.clear()  # type: ignore[attr-defined]
        self.menu.add(self._open_opencode_item)  # type: ignore[attr-defined]
        self.menu.add(None)  # type: ignore[attr-defined]
        for item in dynamic_items:
            self.menu.add(item)  # type: ignore[attr-defined]

        self.menu.add(None)  # type: ignore[attr-defined]
        self.menu.add(self._refresh_item)  # type: ignore[attr-defined]
        self.menu.add(None)  # type: ignore[attr-defined]
        self.menu.add(self._quit_item)  # type: ignore[attr-defined]
