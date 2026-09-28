"""
Integration tests for dashboard window launch and lifecycle.

Tests:
- Window creation and initialization
- Window properties (title, size, icon)
- Timer setup and cleanup
- Section creation and signal configuration
"""

import pytest

from PyQt6.QtWidgets import QStackedWidget
from PyQt6.QtCore import QTimer

from opencode_status_bar.dashboard.widgets import Sidebar
from opencode_status_bar.dashboard.sections import (
    MonitoringSection,
    SecuritySection,
    AnalyticsSection,
    TracingSection,
)

pytestmark = pytest.mark.integration


class TestDashboardWindowLifecycle:
    """Test dashboard window lifecycle: creation, properties, cleanup."""

    def test_window_properties(self, dashboard_window):
        """Test that the dashboard window has correct properties on creation.

        Verifies:
        - Window is visible after show()
        - Title is set correctly
        - Minimum size constraints (800x600)
        - Current size respects minimums
        - Icon is set (not null)
        """
        # Visibility
        assert dashboard_window.isVisible(), "Window should be visible after show()"

        # Title
        assert dashboard_window.windowTitle() == "OpenCode Status Bar"

        # Minimum size constraints (as defined in dimensions.py)
        min_width = dashboard_window.minimumWidth()
        min_height = dashboard_window.minimumHeight()
        assert min_width == 1000, f"Expected min width == 1000, got {min_width}"
        assert min_height == 700, f"Expected min height == 700, got {min_height}"

        # Current size respects minimums
        assert dashboard_window.width() >= min_width
        assert dashboard_window.height() >= min_height

        # Icon is set
        icon = dashboard_window.windowIcon()
        assert not icon.isNull(), "Window should have an icon set"

    def test_timers_are_running(self, dashboard_window_with_timers):
        """Test that background timers are active after window creation.

        Uses dashboard_window_with_timers fixture to verify production behavior
        where timers run for background data refresh.

        Verifies:
        - refresh_timer is a QTimer and is active
        - sync_checker exists and has internal timer active
        """
        # Refresh timer
        refresh_timer = dashboard_window_with_timers._refresh_timer
        assert isinstance(refresh_timer, QTimer), "refresh_timer should be QTimer"
        assert refresh_timer.isActive(), "refresh_timer should be active"

        # Sync checker (has internal timer)
        sync_checker = dashboard_window_with_timers._sync_checker
        assert sync_checker is not None, "sync_checker should exist"
        assert isinstance(sync_checker._timer, QTimer), (
            "sync_checker should have _timer"
        )
        assert sync_checker._timer.isActive(), "sync_checker timer should be active"

    def test_timers_stop_on_close(self, dashboard_window_with_timers, qtbot):
        """Test that timers are properly stopped when window is closed.

        Uses dashboard_window_with_timers to verify cleanup of running timers.
        This validates cleanup to prevent resource leaks.
        """
        window = dashboard_window_with_timers

        # Get references before close
        refresh_timer = window._refresh_timer
        sync_checker = window._sync_checker

        # Verify they're running first
        assert refresh_timer.isActive()
        assert sync_checker._timer.isActive()

        # Close the window
        window.close()

        # Timers should be stopped
        assert not refresh_timer.isActive(), "refresh_timer should stop on close"
        assert not sync_checker._timer.isActive(), "sync_checker should stop on close"


class TestDashboardComponents:
    """Test dashboard UI components: sections, pages, signals."""

    def test_sections_and_pages(self, dashboard_window):
        """Test that all sections are created with correct types.

        Verifies:
        - All 4 sections exist with correct types
        - Sidebar exists with correct type
        - Pages stack exists with exactly 4 pages
        """
        # Monitoring section
        monitoring = dashboard_window._monitoring
        assert isinstance(monitoring, MonitoringSection), (
            f"Expected MonitoringSection, got {type(monitoring).__name__}"
        )

        # Security section
        security = dashboard_window._security
        assert isinstance(security, SecuritySection), (
            f"Expected SecuritySection, got {type(security).__name__}"
        )

        # Analytics section
        analytics = dashboard_window._analytics
        assert isinstance(analytics, AnalyticsSection), (
            f"Expected AnalyticsSection, got {type(analytics).__name__}"
        )

        # Tracing section
        tracing = dashboard_window._tracing
        assert isinstance(tracing, TracingSection), (
            f"Expected TracingSection, got {type(tracing).__name__}"
        )

        # Sidebar
        sidebar = dashboard_window._sidebar
        assert isinstance(sidebar, Sidebar), (
            f"Expected Sidebar, got {type(sidebar).__name__}"
        )

        # Pages stack
        pages = dashboard_window._pages
        assert isinstance(pages, QStackedWidget), (
            f"Expected QStackedWidget, got {type(pages).__name__}"
        )
        assert pages.count() == 4, f"Expected 4 pages, got {pages.count()}"

    def test_signals_are_configured(self, dashboard_window):
        """Test that data update signals are properly configured.

        Verifies:
        - Signals object exists
        - All 4 data signals are accessible (not just hasattr)
        - Signals can be connected (valid pyqtSignal)
        """
        signals = dashboard_window._signals
        assert signals is not None, "signals object should exist"

        # Access signals directly (will raise AttributeError if missing)
        monitoring_signal = signals.monitoring_updated
        security_signal = signals.security_updated
        analytics_signal = signals.analytics_updated
        tracing_signal = signals.tracing_updated

        # Verify they are connectable signals (have 'connect' method)
        assert callable(getattr(monitoring_signal, "connect", None)), (
            "monitoring_updated should be a connectable signal"
        )
        assert callable(getattr(security_signal, "connect", None)), (
            "security_updated should be a connectable signal"
        )
        assert callable(getattr(analytics_signal, "connect", None)), (
            "analytics_updated should be a connectable signal"
        )
        assert callable(getattr(tracing_signal, "connect", None)), (
            "tracing_updated should be a connectable signal"
        )


class TestDashboardHidden:
    """Test dashboard creation without showing - validates headless init."""

    def test_hidden_window_initializes_fully(self, dashboard_window_hidden_with_timers):
        """Test that hidden window initializes all components correctly.

        Use case: background data loading, headless testing, pre-caching.
        Uses dashboard_window_hidden_with_timers to verify production behavior.

        Verifies:
        - Window is NOT visible
        - All sections are created with correct types
        - Timers are running (for background refresh)
        """
        window = dashboard_window_hidden_with_timers

        # Not visible
        assert not window.isVisible(), "Hidden window should not be visible"

        # All sections created with correct types
        assert isinstance(window._monitoring, MonitoringSection)
        assert isinstance(window._security, SecuritySection)
        assert isinstance(window._analytics, AnalyticsSection)
        assert isinstance(window._tracing, TracingSection)

        # Timers running for background refresh
        assert isinstance(window._refresh_timer, QTimer)
        assert window._refresh_timer.isActive(), (
            "refresh_timer should run even for hidden window"
        )
