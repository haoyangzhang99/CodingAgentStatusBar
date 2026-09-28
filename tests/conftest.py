"""
Pytest configuration and shared fixtures for opencode_status_bar tests.

This module provides:
- rumps mocking infrastructure for UI tests
- Common fixtures for models, mocks, and test data factories
- Analytics DB and tracing service fixtures
- Qt application fixture (session scope)
- Pytest markers and configuration
"""

import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from unittest.mock import MagicMock, patch

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


# =============================================================================
# Pytest Configuration Hooks
# =============================================================================


def pytest_configure(config):
    """Configure pytest before any tests run.

    This hook runs ONCE per worker process in pytest-xdist, ensuring
    the rumps mock is set up before any module imports it.
    """
    pass


# =============================================================================
# Rumps Mock Infrastructure (shared by test_app.py and test_menu.py)
# =============================================================================


class MockMenuItem:
    """Mock for rumps.MenuItem with proper menu behavior."""

    def __init__(self, title="", callback=None, **kwargs):
        self.title = title
        self.callback = callback
        self._items = []
        self._items_dict = {}
        self.state = 0
        self._menuitem = MagicMock()
        self.parent = None

    def add(self, item):
        if isinstance(item, MockMenuItem):
            self._items.append(item)
            self._items_dict[item.title] = item
            item.parent = self
        elif item is None:
            self._items.append(None)

    def clear(self):
        self._items = []
        self._items_dict = {}

    def values(self):
        return [item for item in self._items if item is not None]

    def __iter__(self):
        return iter(self._items)

    def __repr__(self):
        return f"MockMenuItem({self.title!r})"


class MockMenu:
    """Mock rumps menu with proper list-like and method behavior."""

    def __init__(self):
        self._items = []
        self._clear_called = False
        self._add_calls = []

    def clear(self):
        self._items = []
        self._clear_called = True

    def add(self, item):
        self._items.append(item)
        self._add_calls.append(item)

    def __setitem__(self, key, value):
        pass

    def __getitem__(self, key):
        return self._items[key] if isinstance(key, int) else None

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class MockApp:
    """Mock rumps.App base class."""

    def __init__(self, name="", title="", quit_button=None, **kwargs):
        self.name = name
        self.title = title
        self._menu = MockMenu()

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, value):
        if isinstance(value, list):
            self._menu = MockMenu()
            for item in value:
                self._menu.add(item)
        else:
            self._menu = value

    def run(self):
        pass


@pytest.fixture
def mock_rumps():
    """Provide a mock rumps module for UI tests."""
    rumps_mock = MagicMock()
    rumps_mock.App = MockApp
    rumps_mock.MenuItem = MockMenuItem
    rumps_mock.timer = lambda interval: lambda f: f
    rumps_mock.quit_application = MagicMock()
    return rumps_mock


# Store original rumps module state at conftest import time
_original_rumps = sys.modules.get("rumps")
_rumps_was_real = _original_rumps is not None and hasattr(_original_rumps, "__file__")


def pytest_runtest_setup(item):
    """Reset rumps module before tests that need real/fresh imports.

    test_menu.py modifies sys.modules["rumps"] at import time with a mock.
    This pollutes subsequent tests. We reset it for affected test files.
    """
    # List of test files that need fresh rumps imports (not the mock from test_menu.py)
    needs_fresh_rumps = ["test_tooltips", "test_db_concurrency"]

    if any(name in str(item.fspath) for name in needs_fresh_rumps):
        # Remove any mock rumps before these tests
        if "rumps" in sys.modules:
            current = sys.modules["rumps"]
            if not hasattr(current, "__file__"):  # It's a mock
                del sys.modules["rumps"]
                # Only clear modules that actually import rumps (not all ui/app modules)
                # This prevents breaking unrelated tests like test_terminal
                rumps_dependent_modules = [
                    "opencode_status_bar.ui.menu",
                    "opencode_status_bar.app",
                    "opencode_status_bar.app.core",
                    "opencode_status_bar.app.menu",
                ]
                for mod in rumps_dependent_modules:
                    if mod in sys.modules:
                        del sys.modules[mod]


# =============================================================================
# Security Auditor Mock Infrastructure
# =============================================================================


def create_default_auditor_stats() -> dict:
    """Create default stats dict for auditor mocking.

    Note: This is also available from tests.mocks.create_default_auditor_stats
    """
    return {
        "total_scanned": 0,
        "total_commands": 0,
        "total_reads": 0,
        "total_writes": 0,
        "total_webfetches": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "reads_critical": 0,
        "reads_high": 0,
        "reads_medium": 0,
        "writes_critical": 0,
        "writes_high": 0,
        "writes_medium": 0,
        "webfetches_critical": 0,
        "webfetches_high": 0,
        "webfetches_medium": 0,
    }


@pytest.fixture
def mock_db():
    """Create a mock SecurityDatabase with default configuration."""
    db = MagicMock()
    db.get_stats.return_value = create_default_auditor_stats()
    db.get_all_scanned_ids.return_value = set()
    db.get_commands_by_level.return_value = []
    db.get_reads_by_level.return_value = []
    db.get_writes_by_level.return_value = []
    db.get_webfetches_by_level.return_value = []
    db.get_all_commands.return_value = []
    db.get_all_reads.return_value = []
    db.get_all_writes.return_value = []
    db.get_all_webfetches.return_value = []
    db.insert_command.return_value = True
    db.insert_read.return_value = True
    db.insert_write.return_value = True
    db.insert_webfetch.return_value = True
    return db


@pytest.fixture
def mock_auditor(mock_db):
    """Create a mock SecurityAuditor with default configuration."""
    auditor = MagicMock()
    auditor.get_stats.return_value = create_default_auditor_stats()
    auditor.get_critical_commands.return_value = []
    auditor.get_sensitive_reads.return_value = []
    auditor.get_sensitive_writes.return_value = []
    auditor.get_risky_webfetches.return_value = []
    auditor.get_all_commands.return_value = []
    auditor.get_all_reads.return_value = []
    auditor.get_all_writes.return_value = []
    auditor.get_all_webfetches.return_value = []
    auditor.generate_report.return_value = "Security Report"
    auditor._db = mock_db
    return auditor


# =============================================================================
# Tool File Content Factory (for auditor tests)
# =============================================================================


def create_tool_file_content(
    tool: str,
    session_id: str = "sess-001",
    timestamp: int = 1703001000000,
    **input_args,
) -> dict:
    """
    Factory to create tool file content for auditor tests.

    Args:
        tool: Tool name (bash, read, write, edit, webfetch)
        session_id: Session ID
        timestamp: Timestamp in milliseconds
        **input_args: Additional input arguments for the tool

    Examples:
        >>> create_tool_file_content("bash", command="ls -la")
        >>> create_tool_file_content("read", filePath="/etc/passwd")
        >>> create_tool_file_content("webfetch", url="https://example.com")
    """
    return {
        "type": "tool",
        "tool": tool,
        "sessionID": session_id,
        "state": {
            "input": input_args,
            "time": {"start": timestamp},
        },
    }


@pytest.fixture
def tool_content_factory():
    """Fixture providing the tool content factory function."""
    return create_tool_file_content


# =============================================================================
# Model Fixtures
# =============================================================================


@pytest.fixture
def sample_agent():
    """Create a sample Agent for testing."""
    from opencode_status_bar.core.models import Agent, SessionStatus

    return Agent(
        id="agent-test-1",
        title="Test Agent",
        dir="project",
        full_dir="/home/user/project",
        status=SessionStatus.BUSY,
    )


@pytest.fixture
def sample_idle_agent():
    """Create a sample idle Agent for testing."""
    from opencode_status_bar.core.models import Agent, SessionStatus

    return Agent(
        id="agent-idle-1",
        title="Idle Agent",
        dir="project",
        full_dir="/home/user/project",
        status=SessionStatus.IDLE,
    )


@pytest.fixture
def sample_instance(sample_agent, available_port):
    """Create a sample Instance with one agent."""
    from opencode_status_bar.core.models import Instance

    return Instance(
        port=available_port,
        tty="/dev/ttys001",
        agents=[sample_agent],
    )


@pytest.fixture
def sample_state(sample_instance):
    """Create a sample State with one instance."""
    from opencode_status_bar.core.models import State, Todos

    return State(
        instances=[sample_instance],
        todos=Todos(pending=3, in_progress=1),
        connected=True,
    )


# =============================================================================
# Async Test Helpers
# =============================================================================


def run_async(coro):
    """Helper to run async coroutines in sync tests."""
    import asyncio

    return asyncio.run(coro)


@pytest.fixture
def async_runner():
    """Fixture providing the async runner function."""
    return run_async


# =============================================================================
# Temporary Storage Helpers
# =============================================================================


@pytest.fixture
def mock_storage(tmp_path):
    """Create a mock OpenCode storage directory structure."""
    storage = tmp_path / "opencode_storage"
    storage.mkdir(parents=True)
    return storage


def create_prt_file(storage: Path, msg_id: str, file_id: str, content: dict) -> Path:
    """Helper to create a prt_*.json file in storage."""
    msg_dir = storage / msg_id
    msg_dir.mkdir(parents=True, exist_ok=True)
    file_path = msg_dir / f"prt_{file_id}.json"
    file_path.write_text(json.dumps(content))
    return file_path


@pytest.fixture
def prt_file_factory(mock_storage):
    """Fixture providing a factory to create prt files in mock storage."""

    def factory(msg_id: str, file_id: str, content: dict) -> Path:
        return create_prt_file(mock_storage, msg_id, file_id, content)

    return factory


# =============================================================================
# Analytics Database Fixtures
# =============================================================================


@pytest.fixture
def analytics_db(tmp_path: Path):
    """Create a fresh AnalyticsDB (DuckDB) for each test.

    IMPORTANT: This fixture creates an ISOLATED database in tmp_path.
    Tests NEVER connect to ~/.config/opencode-status-bar/analytics.duckdb.

    This fixture is shared across all tests needing AnalyticsDB.
    Uses a unique path per test to ensure isolation.
    """
    from opencode_status_bar.analytics.db import AnalyticsDB
    import opencode_status_bar.analytics.db as db_module

    db_path = tmp_path / "test_analytics.duckdb"
    db = AnalyticsDB(db_path)
    db.connect()

    old_singleton = db_module._db_instance
    db_module._db_instance = db

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

        warnings.warn(f"Database cleanup warning: {e}")
    finally:
        db_module._db_instance = old_singleton

        # Force garbage collection to release file handles
        import gc

        gc.collect()
        gc.collect()  # Double collect for cyclic references


# Alias for backward compatibility - tests can use either name
@pytest.fixture
def db(analytics_db):
    """Alias for analytics_db - backward compatible fixture name."""
    return analytics_db


@pytest.fixture
def populated_analytics_db(tmp_path: Path):
    """Create an analytics DB pre-populated with sample test data.

    This fixture provides:
    - 2 sample sessions
    - Parts with different tool types: bash, read, write, edit, webfetch
    - Parts with different risk levels: critical, high, medium, low
    - Both enriched and unenriched parts

    IMPORTANT: Completely isolated from production database.

    Returns:
        Tuple of (AnalyticsDB, session_ids, part_ids)
    """
    from tests.mocks.duckdb import create_populated_test_db

    db, session_ids, part_ids = create_populated_test_db(tmp_path)
    yield db, session_ids, part_ids

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

        warnings.warn(f"Database cleanup warning: {e}")
    finally:
        # Force garbage collection to release file handles
        import gc

        gc.collect()
        gc.collect()  # Double collect for cyclic references


@pytest.fixture
def enrichment_db(analytics_db):
    """Create database with parts table optimized for security enrichment tests.

    This fixture recreates the parts table with all security enrichment columns
    explicitly defined, making it suitable for testing the SecurityEnrichmentWorker.

    IMPORTANT: Uses the isolated analytics_db fixture - never connects to
    the production database.
    """
    conn = analytics_db.connect()

    # Drop and recreate parts table with all security columns
    conn.execute("DROP TABLE IF EXISTS parts")
    conn.execute("""
        CREATE TABLE parts (
            id VARCHAR PRIMARY KEY,
            session_id VARCHAR,
            message_id VARCHAR,
            part_type VARCHAR,
            tool_name VARCHAR,
            tool_status VARCHAR,
            arguments VARCHAR,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            -- Security enrichment columns
            risk_score INTEGER,
            risk_level VARCHAR,
            risk_reason VARCHAR,
            mitre_techniques VARCHAR,
            security_enriched_at TIMESTAMP
        )
    """)

    yield analytics_db

    # CRITICAL: Aggressive cleanup to release file handles
    try:
        if hasattr(analytics_db, "_conn") and analytics_db._conn:
            try:
                analytics_db._conn.close()
            except Exception:
                pass
    except Exception as e:
        import warnings

        warnings.warn(f"Enrichment DB cleanup warning: {e}")
    finally:
        # Force garbage collection to release file handles
        import gc

        gc.collect()
        gc.collect()  # Double collect for cyclic references


@pytest.fixture
def sample_data_generator():
    """Provide a SampleDataGenerator for creating test data.

    Usage:
        def test_example(sample_data_generator):
            gen = sample_data_generator
            session = gen.create_session()
            part = gen.create_bash_part("ses-001", "msg-001", "ls -la")
    """
    from tests.mocks.duckdb import SampleDataGenerator

    return SampleDataGenerator()


# =============================================================================
# Tracing Data Service Fixtures
# =============================================================================


@pytest.fixture
def tracing_service(analytics_db):
    """Create a TracingDataService instance with analytics_db."""
    from opencode_status_bar.analytics.tracing import TracingDataService

    return TracingDataService(db=analytics_db)


# =============================================================================
# Security Analyzer Fixtures
# =============================================================================


@pytest.fixture
def risk_analyzer():
    """Create a fresh RiskAnalyzer for security tests."""
    from opencode_status_bar.security.analyzer import RiskAnalyzer

    return RiskAnalyzer()


# =============================================================================
# Time-based Test Fixtures
# =============================================================================


@pytest.fixture
def base_time() -> float:
    """Base timestamp for event-based tests (correlator, sequences, etc.)."""
    return time.time()


# =============================================================================
# Qt Application Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for the test session.

    Session-scoped to avoid multiple QApplication instances.
    Works for both unit tests and integration tests.
    """
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app


# =============================================================================
# Aliases for compatibility
# =============================================================================


@pytest.fixture
def temp_db(analytics_db):
    """Alias for analytics_db - preferred name for new tests."""
    return analytics_db


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage directory structure."""
    storage_path = tmp_path / "opencode_storage"
    for subdir in ["session", "message", "part", "todo", "project"]:
        (storage_path / subdir).mkdir(parents=True, exist_ok=True)
    return storage_path


# =============================================================================
# Builder-based Fixtures (from tests.builders)
# =============================================================================


@pytest.fixture
def session_builder(analytics_db):
    """Create a SessionBuilder with database connection.

    Usage:
        def test_example(session_builder):
            session_id = session_builder.with_title("Test").insert()
    """
    from tests.builders import SessionBuilder

    return SessionBuilder(db=analytics_db)


@pytest.fixture
def message_builder(analytics_db):
    """Create a MessageBuilder with database connection.

    Usage:
        def test_example(message_builder, session_builder):
            sess_id = session_builder.insert()
            msg_id = message_builder.for_session(sess_id).insert()
    """
    from tests.builders import MessageBuilder

    return MessageBuilder(db=analytics_db)


@pytest.fixture
def trace_builder(analytics_db):
    """Create a TraceBuilder with database connection.

    Usage:
        def test_example(trace_builder):
            trace_builder.with_root("sess-001", "Main")
            trace_builder.add_delegation("trace-001", "executor")
            trace_builder.insert()
    """
    from tests.builders import TraceBuilder

    return TraceBuilder(db=analytics_db)


@pytest.fixture
def part_builder(analytics_db):
    """Create a PartBuilder with database connection.

    Usage:
        def test_example(part_builder, session_builder, message_builder):
            sess_id = session_builder.insert()
            msg_id = message_builder.for_session(sess_id).insert()
            part_id = part_builder.for_session(sess_id).for_message(msg_id).as_tool("bash").insert()
    """
    from tests.builders import PartBuilder

    return PartBuilder(db=analytics_db)


# =============================================================================
# API Test Fixtures
# =============================================================================


@pytest.fixture
def sessions_app():
    """Create Flask test app with sessions blueprint."""
    from flask import Flask
    from opencode_status_bar.api.routes.sessions import sessions_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(sessions_bp)
    return app


@pytest.fixture
def sessions_client(sessions_app):
    """Create test client for sessions API."""
    return sessions_app.test_client()


@pytest.fixture
def mock_tracing_service():
    """Create mock tracing service for API tests."""
    return MagicMock()


@pytest.fixture
def api_mocks(mock_tracing_service):
    """Context manager for mocking API dependencies.

    Usage:
        def test_api(sessions_client, api_mocks, mock_tracing_service):
            mock_tracing_service.get_session_file_parts.return_value = {...}
            with api_mocks:
                response = sessions_client.get("/api/session/test/file-parts")
    """
    from contextlib import ExitStack

    class APIMockContext:
        def __init__(self, service):
            self._service = service
            self._stack = None

        def __enter__(self):
            self._stack = ExitStack()
            mock_lock = self._stack.enter_context(
                patch("opencode_status_bar.api.routes.sessions.get_db_lock")
            )
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()
            self._stack.enter_context(
                patch(
                    "opencode_status_bar.api.routes.sessions.get_service",
                    return_value=self._service,
                )
            )
            return self

        def __exit__(self, *args):
            if self._stack:
                self._stack.__exit__(*args)

    return APIMockContext(mock_tracing_service)


@pytest.fixture
def mock_aioresponse():
    from aioresponses import aioresponses

    with aioresponses() as m:
        yield m


# =============================================================================
# Port Allocation Fixture (for parallel test execution)
# =============================================================================


@pytest.fixture
def available_port(worker_id):
    """Allocate ports from worker-specific ranges to prevent collisions.

    Each worker gets a 100-port range:
    - master: 9000-9099
    - gw0: 9100-9199
    - gw1: 9200-9299
    - etc.
    """
    import socket

    if worker_id == "master":
        base_port = 9000
    else:
        # Extract number from 'gw0', 'gw1', etc.
        worker_num = int(worker_id.replace("gw", ""))
        base_port = 9000 + ((worker_num + 1) * 100)

    # Find first available port in worker's range
    for offset in range(100):
        port = base_port + offset
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("localhost", port))
            sock.close()
            return port
        except OSError:
            continue

    raise RuntimeError(
        f"No available ports in range {base_port}-{base_port + 99} "
        f"for worker {worker_id}"
    )


# =============================================================================
# Global Singleton Reset Fixture (CRITICAL for parallel test execution)
# =============================================================================


@pytest.fixture(autouse=True)
def reset_global_singletons():
    """Reset all global singletons before and after each test.

    This fixture prevents test pollution when running tests in parallel with pytest-xdist.

    CRITICAL: Without this, tests share state through:
    - Database singleton (_db_instance)
    - IndexerRegistry singleton
    - RouteContext singleton
    - ThumbnailCache singleton
    - SecurityAuditor singleton

    The autouse=True ensures this runs for EVERY test automatically,
    even if the test doesn't explicitly request the fixture.
    """
    # Import modules that have singletons
    import sys

    # Reset BEFORE test
    if "opencode_status_bar.analytics.db" in sys.modules:
        import opencode_status_bar.analytics.db as db_module

        db_module._db_instance = None

    if "opencode_status_bar.analytics.indexer.hybrid" in sys.modules:
        import opencode_status_bar.analytics.indexer.hybrid as indexer_module

        if hasattr(indexer_module, "IndexerRegistry"):
            indexer_module.IndexerRegistry._instance = None

    if "opencode_status_bar.api.routes._context" in sys.modules:
        import opencode_status_bar.api.routes._context as context_module

        if hasattr(context_module, "RouteContext"):
            context_module.RouteContext._instance = None

    if "opencode_status_bar.dashboard.sections.tracing.image_cache" in sys.modules:
        import opencode_status_bar.dashboard.sections.tracing.image_cache as cache_module

        cache_module._thumbnail_cache = None

    if "opencode_status_bar.security.auditor.core" in sys.modules:
        import opencode_status_bar.security.auditor.core as auditor_core

        auditor_core._auditor = None

    # Reset settings singleton
    if "opencode_status_bar.utils.settings" in sys.modules:
        import opencode_status_bar.utils.settings as settings_module

        settings_module._settings = None

    # Reset risk analyzer singleton
    if "opencode_status_bar.security.analyzer.risk" in sys.modules:
        import opencode_status_bar.security.analyzer.risk as risk_module

        risk_module._analyzer = None

    # Reset API client singleton
    if "opencode_status_bar.api.client" in sys.modules:
        import opencode_status_bar.api.client as client_module

        client_module._api_client = None

    # Reset API server singleton
    if "opencode_status_bar.api.server" in sys.modules:
        import opencode_status_bar.api.server as server_module

        server_module._api_server = None

    # Reset dashboard process singleton
    if "opencode_status_bar.dashboard.window.launcher" in sys.modules:
        import opencode_status_bar.dashboard.window.launcher as launcher_module

        launcher_module._dashboard_process = None

    # Reset factory singleton
    if (
        "opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies"
        in sys.modules
    ):
        import opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies as strategies_module

        strategies_module._factory_instance = None

    yield

    # Reset AFTER test (even if test crashes)
    if "opencode_status_bar.analytics.db" in sys.modules:
        import opencode_status_bar.analytics.db as db_module

        db_module._db_instance = None

    if "opencode_status_bar.analytics.indexer.hybrid" in sys.modules:
        import opencode_status_bar.analytics.indexer.hybrid as indexer_module

        if hasattr(indexer_module, "IndexerRegistry"):
            indexer_module.IndexerRegistry._instance = None

    if "opencode_status_bar.api.routes._context" in sys.modules:
        import opencode_status_bar.api.routes._context as context_module

        if hasattr(context_module, "RouteContext"):
            context_module.RouteContext._instance = None

    if "opencode_status_bar.dashboard.sections.tracing.image_cache" in sys.modules:
        import opencode_status_bar.dashboard.sections.tracing.image_cache as cache_module

        cache_module._thumbnail_cache = None

    if "opencode_status_bar.security.auditor.core" in sys.modules:
        import opencode_status_bar.security.auditor.core as auditor_core

        auditor_core._auditor = None

    # Reset settings singleton
    if "opencode_status_bar.utils.settings" in sys.modules:
        import opencode_status_bar.utils.settings as settings_module

        settings_module._settings = None

    # Reset risk analyzer singleton
    if "opencode_status_bar.security.analyzer.risk" in sys.modules:
        import opencode_status_bar.security.analyzer.risk as risk_module

        risk_module._analyzer = None

    # Reset API client singleton
    if "opencode_status_bar.api.client" in sys.modules:
        import opencode_status_bar.api.client as client_module

        client_module._api_client = None

    # Reset API server singleton
    if "opencode_status_bar.api.server" in sys.modules:
        import opencode_status_bar.api.server as server_module

        server_module._api_server = None

    # Reset dashboard process singleton
    if "opencode_status_bar.dashboard.window.launcher" in sys.modules:
        import opencode_status_bar.dashboard.window.launcher as launcher_module

        launcher_module._dashboard_process = None

    # Reset factory singleton
    if (
        "opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies"
        in sys.modules
    ):
        import opencode_status_bar.dashboard.sections.tracing.detail_panel.strategies as strategies_module

        strategies_module._factory_instance = None
