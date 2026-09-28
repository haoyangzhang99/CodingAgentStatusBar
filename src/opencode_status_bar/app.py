"""
OpenCode Status Bar - rumps menu bar application.

This module is a backwards-compatibility wrapper.
The actual implementation is in opencode_status_bar.app.core.

For new code, prefer importing from:
- opencode_status_bar.app.core (OpenCodeApp, main)
- opencode_status_bar.ui.menu (MenuBuilder, truncate_with_tooltip, constants)
"""

import warnings

# Re-export main entry point from refactored module
from .app.core import OpenCodeApp, main

# Re-export menu utilities for backwards compatibility
from .ui.menu import (
    MenuBuilder,
    truncate_with_tooltip,
    TITLE_MAX_LENGTH,
    TOOL_ARG_MAX_LENGTH,
    TODO_CURRENT_MAX_LENGTH,
    TODO_PENDING_MAX_LENGTH,
)

# Alias for backwards compatibility with tests
_truncate_with_tooltip = truncate_with_tooltip


# Deprecation warning for direct imports
def __getattr__(name: str):
    """Emit deprecation warning for legacy imports."""
    if name in ("OpenCodeApp", "main"):
        warnings.warn(
            f"Importing {name} from opencode_status_bar.app is deprecated. "
            f"Use opencode_status_bar.app.core instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if name == "OpenCodeApp":
            return OpenCodeApp
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "OpenCodeApp",
    "main",
    "MenuBuilder",
    "truncate_with_tooltip",
    "_truncate_with_tooltip",
    "TITLE_MAX_LENGTH",
    "TOOL_ARG_MAX_LENGTH",
    "TODO_CURRENT_MAX_LENGTH",
    "TODO_PENDING_MAX_LENGTH",
]
