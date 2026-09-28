"""
Pytest configuration and fixtures for integration tests.

Provides:
- Mock API client that replaces the real HTTP client
- QApplication fixture for PyQt tests
- Dashboard fixtures with mocked dependencies

Architecture note:
The dashboard accesses data ONLY via the API client (get_api_client()).
It does NOT access DuckDB directly. The API client is mocked in tests
to provide controlled responses without network calls.
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import centralized mock client
from tests.mocks import MockAnalyticsAPIClient

from .fixtures import (
    MockAPIResponses,
    SECTION_MONITORING,
    SECTION_SECURITY,
    SECTION_ANALYTICS,
    SECTION_TRACING,
    EXPECTED_TRACING,
    process_qt_events,
)

# Import helpers (now as fixtures from helpers module)
from .helpers.assertions import assert_table_content, assert_widget_content
from .helpers.navigation import click_nav, click_tab, select_first_session
from .helpers.signals import wait_for_signal


# =============================================================================
# PyQt Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for the test session."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app


@pytest.fixture
def mock_api_client():
    """Create a mock API client with basic responses."""
    return MockAnalyticsAPIClient(MockAPIResponses.basic())


@pytest.fixture
def mock_api_client_empty():
    """Create a mock API client with empty responses."""
    return MockAnalyticsAPIClient(MockAPIResponses.empty())


@pytest.fixture
def mock_api_client_complex():
    """Create a mock API client with complex multi-session responses."""
    return MockAnalyticsAPIClient(MockAPIResponses.complex())


@pytest.fixture
def mock_api_factory():
    """Factory fixture to create mock API clients with custom responses."""

    def factory(responses: dict[str, Any] | None = None) -> MockAnalyticsAPIClient:
        return MockAnalyticsAPIClient(responses or MockAPIResponses.basic())

    return factory


@pytest.fixture
def patched_api_client(mock_api_client):
    """Patch get_api_client to return the mock client.

    This is the ONLY mock needed for the dashboard - it accesses
    all data through the API client, not directly to DuckDB.
    """
    with patch(
        "opencode_status_bar.api.client.get_api_client", return_value=mock_api_client
    ):
        with patch("opencode_status_bar.api.get_api_client", return_value=mock_api_client):
            yield mock_api_client


@pytest.fixture
def patched_monitoring():
    """Patch monitoring fetch to avoid real network calls."""
    from opencode_status_bar.core.models import State, Todos

    async def mock_fetch():
        return State(
            instances=[], todos=Todos(pending=0, in_progress=0), connected=False
        )

    mock = MagicMock(side_effect=lambda: mock_fetch())

    with patch("opencode_status_bar.core.monitor.fetch_all_instances", mock):
        yield


@pytest.fixture
def patched_security():
    """Patch security auditor to avoid real file scanning."""
    mock_auditor = MagicMock()
    mock_auditor.get_stats.return_value = {
        "total_scanned": 0,
        "total_commands": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    mock_auditor.get_all_commands.return_value = []
    mock_auditor.get_all_reads.return_value = []
    mock_auditor.get_all_writes.return_value = []
    mock_auditor.get_critical_commands.return_value = []
    mock_auditor.get_commands_by_level.return_value = []
    mock_auditor.get_sensitive_reads.return_value = []
    mock_auditor.get_sensitive_writes.return_value = []
    mock_auditor.get_risky_webfetches.return_value = []

    with patch(
        "opencode_status_bar.security.auditor.get_auditor", return_value=mock_auditor
    ):
        yield mock_auditor


@pytest.fixture
def dashboard_window(qtbot, patched_api_client, patched_monitoring, patched_security):
    """Create a dashboard window with all dependencies mocked.

    The dashboard accesses data ONLY via the API client, which is mocked
    by patched_api_client. No DuckDB access occurs.

    Args:
        qtbot: pytest-qt's qtbot fixture for UI interaction
        patched_api_client: Mock API client fixture
        patched_monitoring: Mock monitoring fixture
        patched_security: Mock security fixture

    Yields:
        DashboardWindow: Fully mocked dashboard window
    """
    from opencode_status_bar.dashboard.window import DashboardWindow

    window = DashboardWindow()
    qtbot.addWidget(window)

    # Stop timers BEFORE yield to avoid interference during tests
    # The 2000ms refresh timer could fire and overwrite manually emitted data
    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()

    window.show()
    qtbot.waitExposed(window)

    yield window

    window.close()
    window.deleteLater()
    from PyQt6.QtWidgets import QApplication

    QApplication.processEvents()
    import gc

    gc.collect()


@pytest.fixture
def dashboard_window_hidden(
    qtbot, patched_api_client, patched_monitoring, patched_security
):
    """Create a dashboard window without showing it."""
    from opencode_status_bar.dashboard.window import DashboardWindow

    window = DashboardWindow()
    qtbot.addWidget(window)

    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()

    yield window

    window.close()
    window.deleteLater()
    from PyQt6.QtWidgets import QApplication

    QApplication.processEvents()


@pytest.fixture
def dashboard_window_with_timers(
    qtbot, patched_api_client, patched_monitoring, patched_security
):
    """Create a dashboard window WITH timers running.

    Use this fixture ONLY for tests that specifically verify timer behavior.
    For all other tests, use dashboard_window which stops timers to avoid
    interference with manually emitted data.
    """
    from opencode_status_bar.dashboard.window import DashboardWindow

    window = DashboardWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    yield window

    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()
    window.close()
    window.deleteLater()
    from PyQt6.QtWidgets import QApplication

    QApplication.processEvents()


@pytest.fixture
def dashboard_window_hidden_with_timers(
    qtbot, patched_api_client, patched_monitoring, patched_security
):
    """Create a hidden dashboard window WITH timers running.

    Use this fixture ONLY for tests that verify timer behavior on hidden windows.
    """
    from opencode_status_bar.dashboard.window import DashboardWindow

    window = DashboardWindow()
    qtbot.addWidget(window)

    yield window

    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()
    window.close()
    window.deleteLater()
    from PyQt6.QtWidgets import QApplication

    QApplication.processEvents()


@pytest.fixture
def tracing_with_data(dashboard_window, qtbot, click_nav):
    """Tracing section with realistic data loaded.

    Navigates to tracing section and emits realistic tracing data.
    Returns tuple of (tracing_section, dashboard_window) for flexibility.

    Usage:
        def test_with_tracing(tracing_with_data, select_first_session):
            tracing, dashboard = tracing_with_data
            root_item = select_first_session(tracing)
    """
    click_nav(dashboard_window, SECTION_TRACING)
    data = MockAPIResponses.realistic_tracing()
    dashboard_window._signals.tracing_updated.emit(data)
    process_qt_events()
    return dashboard_window._tracing, dashboard_window


@pytest.fixture(params=["basic", "empty", "complex", "partial", "extreme"])
def mock_api_client_variants(request):
    """Parametrized fixture for testing multiple data states.

    Useful for testing dashboard behavior with different data shapes:
    - basic: Single session, minimal data
    - empty: No data, tests empty states
    - complex: Multiple sessions with agents
    - partial: Missing/null fields
    - extreme: Very large values, stress testing
    """
    responses_map = {
        "basic": MockAPIResponses.basic(),
        "empty": MockAPIResponses.empty(),
        "complex": MockAPIResponses.complex(),
        "partial": MockAPIResponses.partial_data(),
        "extreme": MockAPIResponses.extreme_data(),
    }
    return MockAnalyticsAPIClient(responses_map[request.param])


# =============================================================================
# Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")


@pytest.fixture(scope="session")
def duckdb_memory():
    import duckdb

    conn = duckdb.connect(":memory:")
    yield conn

    # CRITICAL: Aggressive cleanup to release file handles
    try:
        conn.close()
    except Exception as e:
        import warnings

        warnings.warn(f"DuckDB memory connection cleanup warning: {e}")
    finally:
        # Force garbage collection to release file handles
        import gc

        gc.collect()
        gc.collect()  # Double collect for cyclic references


@pytest.fixture
def analytics_db_real(tmp_path):
    from pathlib import Path
    from opencode_status_bar.analytics.db import AnalyticsDB

    db_path = Path(tmp_path) / "test_analytics.duckdb"
    db = AnalyticsDB(db_path=db_path, read_only=False)

    with db:
        db._create_schema()

    yield db

    # CRITICAL: Aggressive cleanup to release file handles
    try:
        if hasattr(db, "_conn") and db._conn:
            try:
                db._conn.close()
            except Exception:
                pass
        db.close()
    except Exception as e:
        import warnings

        warnings.warn(f"Analytics DB real cleanup warning: {e}")
    finally:
        # Force garbage collection to release file handles
        import gc

        gc.collect()
        gc.collect()  # Double collect for cyclic references

        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass


@pytest.fixture
def flask_app_real(analytics_db_real):
    import threading
    from flask import Flask
    from opencode_status_bar.api.routes import (
        health_bp,
        stats_bp,
        sessions_bp,
        tracing_bp,
        delegations_bp,
        security_bp,
    )
    from opencode_status_bar.api.routes._context import RouteContext
    from opencode_status_bar.analytics import TracingDataService
    from unittest.mock import patch

    app = Flask(__name__)
    app.config.update(
        {
            "TESTING": True,
        }
    )

    context = RouteContext.get_instance()
    service = TracingDataService(db=analytics_db_real)
    context.configure(db_lock=threading.Lock(), get_service=lambda: service)

    with patch(
        "opencode_status_bar.api.routes.sessions.get_analytics_db",
        return_value=analytics_db_real,
    ):
        with patch(
            "opencode_status_bar.api.routes.stats.get_analytics_db",
            return_value=analytics_db_real,
        ):
            app.register_blueprint(health_bp)
            app.register_blueprint(stats_bp)
            app.register_blueprint(sessions_bp)
            app.register_blueprint(tracing_bp)
            app.register_blueprint(delegations_bp)
            app.register_blueprint(security_bp)

            with app.app_context():
                yield app


@pytest.fixture
def api_client_real(flask_app_real):
    return flask_app_real.test_client()


@pytest.fixture
def mock_aioresponse():
    from aioresponses import aioresponses

    with aioresponses() as m:
        yield m


@pytest.fixture
def thread_barrier(request):
    import threading

    parties = getattr(request, "param", 2)
    return threading.Barrier(parties=parties)


@pytest.fixture
def freezer():
    from freezegun import freeze_time

    with freeze_time("2026-01-11 12:00:00") as frozen:
        yield frozen
