"""Handlers mixin for StatusBarApp - Contains all callback methods."""

import subprocess
import threading
from typing import Any, Callable, Optional

from ..core.settings import save_settings
from ..ui.settings import SettingsWindow
from ..utils.logger import info, error


class HandlersMixin:
    """Mixin providing callback handlers for StatusBarApp."""

    _needs_refresh: bool
    _settings: dict[str, bool]
    _settings_window: Optional[Any]
    _state_lock: threading.Lock
    # Provided by MenuMixin and StatusBarApp; stubs here would override them.
    _build_menu: Callable[[], None]
    _update_title: Callable[[], None]

    def _open_opencode(self, _):
        """Launch or foreground the installed OpenCode desktop app."""
        try:
            subprocess.run(
                ["/usr/bin/open", "-b", "ai.opencode.desktop"],
                check=True, capture_output=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            error(f"Could not open OpenCode: {exc}")

    def _open_codex(self, _):
        """Launch or foreground the installed Codex desktop app."""
        try:
            subprocess.run(
                ["/usr/bin/open", "-b", "com.openai.codex"],
                check=True, capture_output=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            error(f"Could not open Codex: {exc}")

    def _open_claude(self, _):
        """Launch or foreground the installed Claude desktop app."""
        try:
            subprocess.run(
                ["/usr/bin/open", "-b", "com.anthropic.claudefordesktop"],
                check=True, capture_output=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            error(f"Could not open Claude: {exc}")

    def _on_refresh(self, _):
        """Manual refresh callback."""
        info("Manual refresh requested")
        self._needs_refresh = True

    def _open_settings(self, _):
        """Open the Settings window, where each part of the dropdown can be turned off."""
        try:
            if self._settings_window is None:
                self._settings_window = SettingsWindow(self._on_setting_changed)
            self._settings_window.show(self._settings)
        except Exception as exc:
            error(f"Could not open Settings: {exc}")

    def _on_setting_changed(self, key: str, enabled: bool):
        """Save a switch change from the Settings window and redraw right away."""
        with self._state_lock:
            self._settings = {**self._settings, key: enabled}
            settings = self._settings
        info(f"Setting changed: {key} {'on' if enabled else 'off'}")
        try:
            save_settings(settings)
        except OSError as exc:
            error(f"Could not save settings: {exc}")
        if self._settings_window is not None:
            self._settings_window.update(settings)
        self._build_menu()
        self._update_title()
