"""
Dashboard window package.

This package provides the main dashboard window and related utilities.
All public symbols are re-exported here for backwards compatibility.
"""

from .signals import DataSignals
from .sync import SyncChecker
from .launcher import show_dashboard
from .main import DashboardWindow

__all__ = [
    "DataSignals",
    "SyncChecker",
    "DashboardWindow",
    "show_dashboard",
]
