"""
Qt signals for thread-safe data updates in the dashboard.

DataSignals provides typed signals for each data section,
enabling thread-safe communication between background fetchers
and the Qt UI thread.
"""

from PyQt6.QtCore import QObject, pyqtSignal


class DataSignals(QObject):
    """Signals for thread-safe data updates."""

    monitoring_updated = pyqtSignal(dict)
    security_updated = pyqtSignal(dict)
    analytics_updated = pyqtSignal(dict)
    tracing_updated = pyqtSignal(dict)
