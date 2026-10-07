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
from ..core.settings import visible_states
from ..ui.menu import MenuBuilder, set_menu_symbol


class MenuMixin:
    """Mixin providing menu building methods for StatusBarApp."""

    # Type hints for attributes from StatusBarApp
    _state: Optional[State]
    _codex: Optional[HookState]
    _claude: Optional[HookState]
    _settings: dict[str, bool]
    _state_lock: threading.Lock
    _menu_builder: MenuBuilder

    # Menu items (will be set by _build_static_menu)
    _open_opencode_item: rumps.MenuItem
    _open_codex_item: rumps.MenuItem
    _open_claude_item: rumps.MenuItem
    _refresh_item: rumps.MenuItem
    _settings_item: rumps.MenuItem
    _quit_item: rumps.MenuItem

    # Handlers (will be provided by HandlersMixin)
    def _on_refresh(self, _): ...
    def _open_opencode(self, _): ...
    def _open_codex(self, _): ...
    def _open_claude(self, _): ...
    def _open_settings(self, _): ...

    def _build_static_menu(self):
        """Build the static menu items."""
        self._open_opencode_item = rumps.MenuItem(
            "Show OpenCode", callback=self._open_opencode
        )
        self._open_codex_item = rumps.MenuItem("Show Codex", callback=self._open_codex)
        self._open_claude_item = rumps.MenuItem("Show Claude", callback=self._open_claude)
        self._refresh_item = rumps.MenuItem("Refresh", callback=self._on_refresh)
        set_menu_symbol(self._refresh_item, "arrow.clockwise")
        self._settings_item = rumps.MenuItem("Settings...", callback=self._open_settings)
        set_menu_symbol(self._settings_item, "gearshape")
        self._quit_item = rumps.MenuItem("Quit", callback=rumps.quit_application)

        # Initial menu
        self.menu = [
            *self._buttons(self._settings),
            None,
            rumps.MenuItem("Loading...", callback=None),
            None,
            *self._footer(self._settings),
        ]

    def _buttons(self, settings: dict[str, bool]) -> list:
        """The Show buttons that are turned on in Settings."""
        return [
            item
            for item, key in (
                (self._open_opencode_item, "show_opencode"),
                (self._open_codex_item, "show_codex"),
                (self._open_claude_item, "show_claude"),
            )
            if settings[key]
        ]

    def _footer(self, settings: dict[str, bool]) -> list:
        """Refresh if it's turned on, then Settings and Quit, which always show."""
        refresh = [self._refresh_item] if settings["refresh"] else []
        return [*refresh, self._settings_item, None, self._quit_item]

    def _build_menu(self):
        """Build the menu from current state."""
        with self._state_lock:
            state = self._state
            codex = self._codex
            claude = self._claude
            settings = self._settings

        state, codex, claude = visible_states(settings, state, codex, claude)

        # Clicking a session row brings its app to the front. An app turned off in Settings
        # has no section.
        sections = [
            self._menu_builder.build_dynamic_items(state, on_select=self._open_opencode)
            if settings["opencode"] else [],
            self._menu_builder.build_hook_items(codex, "Codex", on_select=self._open_codex),
            self._menu_builder.build_hook_items(
                claude, "Claude Code", on_select=self._open_claude
            ),
        ]

        # Rebuild complete menu (rumps.App.menu has .add()/.clear() but no type stubs)
        self.menu.clear()  # type: ignore[attr-defined]
        buttons = self._buttons(settings)
        for item in buttons:
            self.menu.add(item)  # type: ignore[attr-defined]
        for items in (section for section in sections if section):
            if len(self.menu):  # type: ignore[arg-type]
                self.menu.add(None)  # type: ignore[attr-defined]
            for item in items:
                self.menu.add(item)  # type: ignore[attr-defined]

        if len(self.menu):  # type: ignore[arg-type]
            self.menu.add(None)  # type: ignore[attr-defined]
        for item in self._footer(settings):
            self.menu.add(item)  # type: ignore[attr-defined]
