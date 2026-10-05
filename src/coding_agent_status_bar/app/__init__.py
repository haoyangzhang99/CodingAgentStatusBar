"""
Coding Agent Status Bar - rumps menu bar application.

Modules:
- core: StatusBarApp, status label and icon, polling loop
- menu: Dropdown menu building mixin
- handlers: Menu callback handlers mixin
"""

from ..ui.menu import truncate_with_tooltip
from .core import StatusBarApp, main

# Alias kept for tests
_truncate_with_tooltip = truncate_with_tooltip

__all__ = ["StatusBarApp", "main", "truncate_with_tooltip", "_truncate_with_tooltip"]
