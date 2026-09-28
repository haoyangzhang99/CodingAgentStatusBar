"""
OpenCode Monitor - rumps menu bar application.

This package provides the OpenCodeApp class for macOS menu bar monitoring.

Modules:
- core: Main OpenCodeApp class with state and lifecycle management
- menu: Menu building mixin
- handlers: Callback handlers mixin

Heavy optional features (PyQt6 dashboard, DuckDB analytics, security auditor,
Claude usage polling, legacy port scanning) are not imported at startup.
Their names remain available lazily for backwards compatibility.
"""

import importlib

# Lightweight re-exports for backwards compatibility with existing imports and tests
from ..core.models import State, SessionStatus, Usage
from ..utils.settings import get_settings, save_settings
from ..utils.logger import info, error
from ..security.analyzer import SecurityAlert, RiskLevel
from ..ui.terminal import focus_iterm2
from ..ui.menu import (
    MenuBuilder,
    truncate_with_tooltip,
    TITLE_MAX_LENGTH,
    TOOL_ARG_MAX_LENGTH,
    TODO_CURRENT_MAX_LENGTH,
    TODO_PENDING_MAX_LENGTH,
)

from .core import OpenCodeApp, main

# Re-export for backwards compatibility with tests
_truncate_with_tooltip = truncate_with_tooltip

_LAZY_EXPORTS = {
    "fetch_all_instances": "..core.monitor",
    "fetch_usage": "..core.usage",
    "get_auditor": "..security.auditor",
    "start_auditor": "..security.auditor",
    "AnalyticsDB": "..analytics",
    "load_opencode_data": "..analytics",
    "show_dashboard": "..dashboard",
}


def __getattr__(name: str):
    module = _LAZY_EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module, __name__), name)


__all__ = [
    "OpenCodeApp",
    "main",
    "State",
    "SessionStatus",
    "Usage",
    "get_settings",
    "save_settings",
    "info",
    "error",
    "SecurityAlert",
    "RiskLevel",
    "focus_iterm2",
    "MenuBuilder",
    "truncate_with_tooltip",
    "_truncate_with_tooltip",
    "TITLE_MAX_LENGTH",
    "TOOL_ARG_MAX_LENGTH",
    "TODO_CURRENT_MAX_LENGTH",
    "TODO_PENDING_MAX_LENGTH",
    *_LAZY_EXPORTS,
]
