"""
Tests for DashboardWindow sync functionality.

Coverage target: SyncChecker and read-only dashboard architecture.

The dashboard operates in read-only mode. The menubar handles all DB writes
and updates sync_meta table. The dashboard polls the API via SyncChecker
to detect when new data is available.
"""

import pytest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client():
    """Mock API client to avoid real API calls."""
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.get_stats.return_value = {"sessions": 0}
    mock_client.get_sync_status.return_value = {"backfill_active": False}

    with patch("opencode_status_bar.api.get_api_client") as mock_get:
        mock_get.return_value = mock_client
        yield mock_client


@contextmanager
def patched_dashboard_window():
    """Context manager for DashboardWindow with all fetch methods patched."""
    from opencode_status_bar.dashboard.window import DashboardWindow

    with (
        patch.object(DashboardWindow, "_fetch_monitoring_data"),
        patch.object(DashboardWindow, "_fetch_security_data"),
        patch.object(DashboardWindow, "_fetch_analytics_data"),
        patch.object(DashboardWindow, "_fetch_tracing_data"),
    ):
        window = DashboardWindow()
        try:
            yield window
        finally:
            window.close()
            window.deleteLater()


@pytest.fixture
def dashboard_window(qapp, mock_api_client):
    """Create a DashboardWindow with mocked fetch methods."""
    with patched_dashboard_window() as window:
        yield window


# =============================================================================
# SyncChecker Tests
# =============================================================================


class TestSyncChecker:
    """Tests for SyncChecker class - constants, callback, and timer behavior."""

    def test_constants_have_correct_values_and_relationships(self):
        """SyncChecker poll constants are correctly defined."""
        from opencode_status_bar.dashboard.window import SyncChecker

        # Verify constant values
        assert SyncChecker.POLL_FAST_MS == 2000
        assert SyncChecker.POLL_SLOW_MS == 5000
        assert SyncChecker.IDLE_THRESHOLD_S == 30

        # Verify relationships make sense
        assert SyncChecker.POLL_FAST_MS < SyncChecker.POLL_SLOW_MS
        assert SyncChecker.IDLE_THRESHOLD_S > 0

    def test_initialization_and_cleanup(self, qapp, mock_api_client):
        """SyncChecker initializes correctly and cleans up on stop."""
        from opencode_status_bar.dashboard.window import SyncChecker

        callback_calls = []
        checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))

        try:
            # Verify initial state
            assert checker._timer.interval() == SyncChecker.POLL_FAST_MS
            assert checker._timer.isActive()
            assert callable(checker._on_sync)
            assert checker._known_sync is None  # No sync detected yet
            assert checker._last_change_time > 0

            # Stop and verify cleanup
            checker.stop()
            assert not checker._timer.isActive()
        finally:
            checker.stop()

    def test_detects_session_count_changes(self, qapp, mock_api_client):
        """SyncChecker triggers callback when session count changes."""
        from opencode_status_bar.dashboard.window import SyncChecker

        callback_calls = []
        checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))

        try:
            # First check initializes _known_sync but skips callback
            checker._check()
            assert callback_calls == []
            assert checker._known_sync == 0

            # Same count - no callback
            checker._check()
            assert callback_calls == []

            # Count changes - callback triggered
            mock_api_client.get_stats.return_value = {"sessions": 10}
            checker._check()
            assert callback_calls == [True]
            assert checker._known_sync == 10

            # Another change
            mock_api_client.get_stats.return_value = {"sessions": 15}
            checker._check()
            assert callback_calls == [True, True]
            assert checker._known_sync == 15
        finally:
            checker.stop()


# =============================================================================
# DashboardWindow Read-Only Architecture Tests
# =============================================================================


class TestDashboardReadOnly:
    """Tests for read-only dashboard architecture."""

    def test_uses_sync_checker_not_legacy_attributes(self, dashboard_window):
        """DashboardWindow uses SyncChecker, not legacy sync attributes."""
        # New architecture: has SyncChecker
        assert hasattr(dashboard_window, "_sync_checker")
        from opencode_status_bar.dashboard.window import SyncChecker

        assert isinstance(dashboard_window._sync_checker, SyncChecker)

        # Legacy attributes removed
        assert not hasattr(dashboard_window, "_sync_config")
        assert not hasattr(dashboard_window, "_sync_opencode_data")

    def test_close_stops_sync_checker(self, dashboard_window):
        """DashboardWindow.closeEvent stops the sync checker timer."""
        sync_checker = dashboard_window._sync_checker

        # Timer active before close
        assert sync_checker._timer.isActive()

        # Close triggers timer stop
        dashboard_window.close()
        assert not sync_checker._timer.isActive()


# =============================================================================
# DataSignals Tests
# =============================================================================


class TestDataSignals:
    """Tests for DataSignals class."""

    def test_has_required_signals_not_legacy(self):
        """DataSignals has all required update signals but not legacy ones."""
        from opencode_status_bar.dashboard.window import DataSignals

        signals = DataSignals()

        # Required signals exist
        assert hasattr(signals, "monitoring_updated")
        assert hasattr(signals, "security_updated")
        assert hasattr(signals, "analytics_updated")
        assert hasattr(signals, "tracing_updated")

        # Legacy signal removed (dashboard uses SyncChecker now)
        assert not hasattr(signals, "sync_completed")


# =============================================================================
# Integration Tests
# =============================================================================


class TestSyncCheckerIntegration:
    """Integration tests for SyncChecker with dashboard."""

    def test_triggers_dashboard_refresh_on_change(self, qapp, mock_api_client):
        """SyncChecker triggers dashboard refresh when sync detected."""
        from opencode_status_bar.dashboard.window import DashboardWindow, SyncChecker

        refresh_calls = []

        with (
            patch.object(DashboardWindow, "_start_refresh"),
            patch.object(
                DashboardWindow,
                "_refresh_all_data",
                lambda self: refresh_calls.append(1),
            ),
        ):
            with patched_dashboard_window():
                checker = SyncChecker(on_sync_detected=lambda: refresh_calls.append(1))

                try:
                    # Initial check skips callback (avoids duplicate refresh)
                    checker._check()
                    assert refresh_calls == []

                    # Session count change triggers refresh
                    mock_api_client.get_stats.return_value = {"sessions": 5}
                    checker._check()
                    assert refresh_calls == [1]

                    # Another change triggers another refresh
                    mock_api_client.get_stats.return_value = {"sessions": 10}
                    checker._check()
                    assert refresh_calls == [1, 1]
                finally:
                    checker.stop()
