"""Handlers mixin for OpenCodeApp - Contains all callback methods."""

import subprocess

from ..utils.logger import info, error


class HandlersMixin:
    """Mixin providing callback handlers for OpenCodeApp."""

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

    def _on_refresh(self, _):
        """Manual refresh callback."""
        info("Manual refresh requested")
        self._needs_refresh = True
