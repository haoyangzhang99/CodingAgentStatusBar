"""Handlers mixin for OpenCodeApp - Contains all callback methods."""

from typing import TYPE_CHECKING
import subprocess

from ..security.analyzer import SecurityAlert, RiskLevel
from ..ui.terminal import focus_iterm2
from ..utils.logger import info, error


if TYPE_CHECKING:
    pass


class HandlersMixin:
    """Mixin providing callback handlers for OpenCodeApp."""

    # Type hints for attributes from OpenCodeApp
    _security_alerts: list[SecurityAlert]
    _max_alerts: int
    _has_critical_alert: bool
    _needs_refresh: bool

    def _open_opencode(self, _):
        """Launch or foreground the installed OpenCode desktop app."""
        try:
            subprocess.run(
                ["/usr/bin/open", "-b", "ai.opencode.desktop"],
                check=True, capture_output=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            error(f"Could not open OpenCode: {exc}")

    def _focus_terminal(self, tty: str):
        """Focus iTerm2 on the given TTY."""
        focus_iterm2(tty)

    def _on_refresh(self, _):
        """Manual refresh callback."""
        info("Manual refresh requested")
        self._needs_refresh = True

    def _add_security_alert(self, alert: SecurityAlert):
        """Add a security alert to the history."""
        for existing in self._security_alerts:
            if existing.command == alert.command:
                return

        self._security_alerts.insert(0, alert)

        if len(self._security_alerts) > self._max_alerts:
            self._security_alerts = self._security_alerts[: self._max_alerts]

        if alert.level == RiskLevel.CRITICAL:
            self._has_critical_alert = True
            info(f"🔴 CRITICAL: {alert.reason} - {alert.command[:50]}")
        elif alert.level == RiskLevel.HIGH:
            info(f"🟠 HIGH: {alert.reason} - {alert.command[:50]}")
