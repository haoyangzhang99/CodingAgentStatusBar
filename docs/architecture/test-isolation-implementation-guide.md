# Test Isolation Implementation Guide

**Companion to:** [Test Isolation Architecture](./test-isolation-architecture.md)  
**Version:** 1.0  
**Date:** January 12, 2026

---

## Quick Start

This guide provides practical, copy-paste code examples for implementing the test isolation architecture.

### Step 1: Update conftest.py

Add these fixtures to `tests/conftest.py`:

```python
"""
Enhanced pytest configuration with worker isolation for parallel execution.
"""

import os
import json
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Tuple
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Worker Isolation Infrastructure
# =============================================================================

@pytest.fixture(scope="session")
def worker_id(request):
    """
    Get the worker ID for this test process.
    
    Returns:
        - "master" if not using xdist
        - "gw0", "gw1", etc. for xdist workers
    """
    if hasattr(request.config, 'workerinput'):
        return request.config.workerinput['workerid']
    return "master"


@pytest.fixture(scope="session")
def worker_port_base(worker_id):
    """
    Base port for this worker (each worker gets 100 ports).
    
    Port allocation:
        - master: 5000-5099
        - gw0: 5100-5199
        - gw1: 5200-5299
        - etc.
    """
    if worker_id == "master":
        return 5000
    
    worker_num = int(worker_id.replace("gw", ""))
    return 5000 + (worker_num * 100)


# =============================================================================
# Database Isolation
# =============================================================================

@pytest.fixture(scope="session")
def worker_db_path(tmp_path_factory, worker_id):
    """
    Worker-specific database path for isolation.
    
    Each worker gets its own DuckDB file to prevent lock contention
    and data pollution.
    """
    if worker_id == "master":
        return tmp_path_factory.getbasetemp() / "test.duckdb"
    
    return tmp_path_factory.getbasetemp() / f"test_{worker_id}.duckdb"


@pytest.fixture
def analytics_db(worker_db_path):
    """
    Function-scoped analytics database with automatic cleanup.
    
    Each test gets a fresh database to ensure isolation.
    """
    from opencode_status_bar.analytics.db import AnalyticsDB
    
    db = AnalyticsDB(db_path=worker_db_path, read_only=False)
    
    # Initialize schema
    with db:
        db._create_schema()
    
    yield db
    
    # Explicit cleanup
    if db._conn is not None:
        db.close()
    
    # Verify cleanup
    assert db._conn is None, "Database connection not closed!"


@pytest.fixture
def enrichment_db(worker_db_path):
    """
    Function-scoped database with security enrichment schema.
    """
    from opencode_status_bar.analytics.db import AnalyticsDB
    
    db = AnalyticsDB(db_path=worker_db_path, read_only=False)
    
    with db:
        db._create_schema()
        # Add security columns
        conn = db.connect()
        conn.execute("""
            ALTER TABLE parts ADD COLUMN IF NOT EXISTS risk_score INTEGER;
            ALTER TABLE parts ADD COLUMN IF NOT EXISTS risk_level VARCHAR;
            ALTER TABLE parts ADD COLUMN IF NOT EXISTS risk_reason VARCHAR;
            ALTER TABLE parts ADD COLUMN IF NOT EXISTS mitre_techniques VARCHAR;
            ALTER TABLE parts ADD COLUMN IF NOT EXISTS security_enriched_at TIMESTAMP;
        """)
    
    yield db
    
    if db._conn is not None:
        db.close()
    
    assert db._conn is None, "Database connection not closed!"


# =============================================================================
# Filesystem Isolation
# =============================================================================

@pytest.fixture
def temp_storage(tmp_path, worker_id):
    """
    Worker-specific storage directory for file operations.
    
    Each worker gets its own storage directory to prevent
    file conflicts and race conditions.
    """
    if worker_id == "master":
        storage = tmp_path / "storage"
    else:
        storage = tmp_path / f"storage_{worker_id}"
    
    storage.mkdir(parents=True, exist_ok=True)
    
    yield storage
    
    # Cleanup handled by tmp_path fixture


@pytest.fixture(scope="session")
def worker_temp_dir(tmp_path_factory, worker_id):
    """
    Worker-specific temporary directory for session-scoped resources.
    """
    if worker_id == "master":
        temp_dir = tmp_path_factory.getbasetemp()
    else:
        temp_dir = tmp_path_factory.getbasetemp() / worker_id
    
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


# =============================================================================
# Network/Port Isolation
# =============================================================================

@pytest.fixture
def flask_test_port(worker_port_base):
    """Flask test server port (worker-specific)."""
    return worker_port_base + 0


@pytest.fixture
def mock_http_port(worker_port_base):
    """Mock HTTP server port (worker-specific)."""
    return worker_port_base + 1


# =============================================================================
# Resource Management
# =============================================================================

class ResourceTracker:
    """Track resources created during test for automatic cleanup."""
    
    def __init__(self):
        self.resources = []
    
    def track(self, resource):
        """Track a resource for cleanup."""
        self.resources.append(resource)
        return resource
    
    def cleanup_all(self):
        """Clean up all tracked resources in reverse order."""
        for resource in reversed(self.resources):
            try:
                if hasattr(resource, 'cleanup'):
                    resource.cleanup()
                elif hasattr(resource, 'close'):
                    resource.close()
                elif hasattr(resource, '__exit__'):
                    resource.__exit__(None, None, None)
            except Exception as e:
                # Log but don't fail cleanup
                print(f"Warning: Failed to cleanup {resource}: {e}")


@pytest.fixture
def resource_tracker():
    """Function-scoped resource tracker."""
    tracker = ResourceTracker()
    yield tracker
    tracker.cleanup_all()


# =============================================================================
# Mock Management
# =============================================================================

class MockRegistry:
    """Central registry for all mocks with automatic cleanup."""
    
    def __init__(self):
        self._mocks: Dict[str, Any] = {}
        self._patches = []
    
    def register_mock(self, name: str, mock_obj):
        """Register a mock for tracking."""
        self._mocks[name] = mock_obj
        return mock_obj
    
    def patch(self, target: str, **kwargs):
        """Create and track a patch."""
        from unittest.mock import patch
        
        patcher = patch(target, **kwargs)
        mock_obj = patcher.start()
        self._patches.append(patcher)
        return mock_obj
    
    def reset_all(self):
        """Reset all mocks and stop all patches."""
        for mock in self._mocks.values():
            if hasattr(mock, 'reset_mock'):
                mock.reset_mock()
        
        for patcher in self._patches:
            try:
                patcher.stop()
            except Exception:
                pass  # Already stopped
        
        self._patches.clear()


@pytest.fixture
def mock_registry():
    """Function-scoped mock registry."""
    registry = MockRegistry()
    yield registry
    registry.reset_all()


# =============================================================================
# Singleton Management
# =============================================================================

# Global singleton registry
_SINGLETON_REGISTRY: Dict[str, Tuple[Any, Callable]] = {}


def register_singleton(name: str, instance: Any, reset_func: Callable):
    """
    Register a singleton for automatic reset between tests.
    
    Args:
        name: Unique name for the singleton
        instance: The singleton instance
        reset_func: Function to reset the singleton state
    """
    _SINGLETON_REGISTRY[name] = (instance, reset_func)


@pytest.fixture(autouse=True, scope="function")
def reset_singletons():
    """Automatically reset all singletons before each test."""
    for name, (instance, reset_func) in _SINGLETON_REGISTRY.items():
        try:
            reset_func(instance)
        except Exception as e:
            print(f"Warning: Failed to reset singleton {name}: {e}")
    
    yield


# =============================================================================
# Cleanup Verification
# =============================================================================

@pytest.fixture(autouse=True)
def verify_cleanup():
    """
    Verify no resource leaks after each test.
    
    Checks:
        - Thread count
        - (Future: file handles, connections, etc.)
    """
    import gc
    
    # Record initial state
    initial_threads = threading.active_count()
    
    yield
    
    # Force garbage collection
    gc.collect()
    
    # Verify cleanup
    final_threads = threading.active_count()
    if final_threads > initial_threads:
        leaked = final_threads - initial_threads
        pytest.fail(f"Test leaked {leaked} thread(s)")


# =============================================================================
# Qt/UI Fixtures (if using PyQt6)
# =============================================================================

@pytest.fixture(scope="session")
def qapp():
    """
    Session-scoped QApplication (singleton constraint).
    
    QApplication can only be created once per process, so we use
    session scope and rely on pytest-qt for cleanup.
    """
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    yield app
    
    # Cleanup handled by pytest-qt


# =============================================================================
# Test Data Builders
# =============================================================================

class SampleDataGenerator:
    """Generate sample test data with proper isolation."""
    
    def __init__(self, db=None):
        self.db = db
    
    def create_session(self, session_id=None, **kwargs):
        """Create a test session."""
        import time
        
        if session_id is None:
            session_id = f"ses_{int(time.time() * 1000)}"
        
        return {
            "id": session_id,
            "project_name": kwargs.get("project_name", "test-project"),
            "created_at": kwargs.get("created_at", int(time.time() * 1000)),
            **kwargs
        }
    
    def create_bash_part(self, session_id, message_id, command, **kwargs):
        """Create a bash tool part."""
        return {
            "session_id": session_id,
            "message_id": message_id,
            "tool_name": "bash",
            "arguments": json.dumps({"command": command}),
            "risk_score": kwargs.get("risk_score"),
            "risk_level": kwargs.get("risk_level"),
            **kwargs
        }


@pytest.fixture
def sample_data_generator(analytics_db):
    """Sample data generator with database access."""
    return SampleDataGenerator(db=analytics_db)
```

### Step 2: Update pyproject.toml

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
qt_api = "pyqt6"
testpaths = ["tests"]
pythonpath = ["src"]

# Parallel execution configuration
addopts = [
    "-n", "auto",              # Use all CPU cores
    "--dist", "loadgroup",     # Distribute by xdist_group marker
    "--maxfail", "3",          # Stop after 3 failures
    "--tb", "short",           # Shorter tracebacks
]

# Stricter timeouts
timeout = 30
timeout_func_only = true

# Markers for test grouping
markers = [
    "xdist_group(name): group tests to run in same worker",
    "serial: run test serially (not in parallel)",
    "database: tests that use database",
    "ui: tests that use Qt UI",
    "integration: integration tests",
    "unit: unit tests",
    "slow: slow tests (> 1s)",
]
```

### Step 3: Update Existing Tests

#### Example: Database Test Migration

**Before:**
```python
def test_database_operation():
    db = AnalyticsDB()  # Creates own connection
    db.store_session({"id": "test"})
    result = db.get_session("test")
    assert result["id"] == "test"
```

**After:**
```python
def test_database_operation(analytics_db):
    """Test database operation with isolated DB."""
    analytics_db.store_session({"id": "test"})
    result = analytics_db.get_session("test")
    assert result["id"] == "test"
```

#### Example: UI Test Migration

**Before:**
```python
def test_dashboard_window():
    window = DashboardWindow()
    window.show()
    # Test window
    window.close()
```

**After:**
```python
@pytest.mark.xdist_group("ui")
def test_dashboard_window(qapp, qtbot, mock_api_client):
    """Test dashboard window with isolated dependencies."""
    window = DashboardWindow(api_client=mock_api_client)
    qtbot.addWidget(window)  # Automatic cleanup
    
    window.show()
    qtbot.waitExposed(window)
    
    # Test window
    assert window.isVisible()
```

#### Example: API Test Migration

**Before:**
```python
def test_api_endpoint():
    client = APIClient("http://localhost:5000")
    response = client.get("/api/sessions")
    assert response.status_code == 200
```

**After:**
```python
def test_api_endpoint(api_client_real, analytics_db):
    """Test API endpoint with isolated client and DB."""
    # Populate test data
    analytics_db.store_session({"id": "test"})
    
    # Test endpoint
    response = api_client_real.get("/api/sessions")
    assert response.status_code == 200
    assert len(response.json) == 1
```

---

## Common Patterns

### Pattern 1: Test with Worker-Specific Port

```python
def test_flask_server(flask_test_port, analytics_db):
    """Test Flask server on worker-specific port."""
    from flask import Flask
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    @app.route('/health')
    def health():
        return {'status': 'ok'}
    
    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
```

### Pattern 2: Test with Resource Tracking

```python
def test_with_resource_tracking(resource_tracker, temp_storage):
    """Test with automatic resource cleanup."""
    # Create resources
    file1 = temp_storage / "test1.txt"
    file1.write_text("test")
    resource_tracker.track(file1)
    
    file2 = temp_storage / "test2.txt"
    file2.write_text("test")
    resource_tracker.track(file2)
    
    # Test code here
    
    # Cleanup happens automatically via fixture
```

### Pattern 3: Test with Mock Registry

```python
def test_with_mocks(mock_registry):
    """Test with centralized mock management."""
    from opencode_status_bar.api.client import APIClient
    
    # Create mock
    mock_client = MagicMock(spec=APIClient)
    mock_registry.register_mock('api_client', mock_client)
    
    # Configure mock
    mock_client.get_sessions.return_value = []
    
    # Test code here
    
    # Mock reset happens automatically via fixture
```

### Pattern 4: Test Grouping by Resource

```python
@pytest.mark.xdist_group("database")
class TestDatabaseOperations:
    """Group database tests to run in same worker."""
    
    def test_insert(self, analytics_db):
        analytics_db.store_session({"id": "test1"})
        assert analytics_db.get_session("test1") is not None
    
    def test_query(self, analytics_db):
        analytics_db.store_session({"id": "test2"})
        result = analytics_db.get_session("test2")
        assert result["id"] == "test2"


@pytest.mark.xdist_group("ui")
class TestDashboardUI:
    """Group UI tests to share QApplication."""
    
    def test_window_creation(self, qapp, qtbot, mock_api_client):
        from opencode_status_bar.dashboard.window import DashboardWindow
        
        window = DashboardWindow(api_client=mock_api_client)
        qtbot.addWidget(window)
        
        assert window is not None
    
    def test_widget_interaction(self, qapp, qtbot, mock_api_client):
        from opencode_status_bar.dashboard.window import DashboardWindow
        
        window = DashboardWindow(api_client=mock_api_client)
        qtbot.addWidget(window)
        
        # Test widget interaction
        window.show()
        qtbot.waitExposed(window)
```

### Pattern 5: Singleton Registration

```python
# In your application code (e.g., src/opencode_status_bar/cache.py)
class CacheManager:
    """Singleton cache manager."""
    
    _instance = None
    _cache = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset cache state (for testing)."""
        cls._cache.clear()
    
    def get(self, key):
        return self._cache.get(key)
    
    def set(self, key, value):
        self._cache[key] = value


# In tests/conftest.py (at module level)
from opencode_status_bar.cache import CacheManager

register_singleton('cache_manager', CacheManager, CacheManager.reset)
```

### Pattern 6: Timing Without Sleep

```python
def test_async_operation(qtbot):
    """Test async operation without time.sleep."""
    operation_started = False
    operation_complete = False
    
    def start_operation():
        nonlocal operation_started
        operation_started = True
        # Simulate async work
        import threading
        def work():
            nonlocal operation_complete
            # Do work
            operation_complete = True
        
        thread = threading.Thread(target=work)
        thread.start()
    
    start_operation()
    
    # Wait for condition with timeout
    qtbot.waitUntil(lambda: operation_complete, timeout=5000)
    
    assert operation_complete
```

### Pattern 7: Dependency Injection

```python
# Application code
class AnalyticsService:
    """Service with injected dependencies."""
    
    def __init__(self, db, api_client):
        self.db = db
        self.api_client = api_client
    
    def get_session_data(self, session_id):
        # Use injected dependencies
        return self.db.get_session(session_id)


# Test code
def test_analytics_service(analytics_db, mock_api_client):
    """Test service with injected dependencies."""
    service = AnalyticsService(db=analytics_db, api_client=mock_api_client)
    
    # Populate test data
    analytics_db.store_session({"id": "test"})
    
    # Test service
    result = service.get_session_data("test")
    assert result["id"] == "test"
```

---

## Troubleshooting

### Issue: Tests fail with "Database is locked"

**Cause:** Multiple workers accessing same database file

**Solution:** Ensure using `analytics_db` fixture (not creating own DB)

```python
# BAD
def test_something():
    db = AnalyticsDB()  # Creates shared DB

# GOOD
def test_something(analytics_db):
    # Uses worker-specific DB
```

### Issue: Tests fail with "Port already in use"

**Cause:** Multiple workers using same port

**Solution:** Use `flask_test_port` or `mock_http_port` fixtures

```python
# BAD
def test_server():
    server = create_server(port=5000)  # Conflicts

# GOOD
def test_server(flask_test_port):
    server = create_server(port=flask_test_port)
```

### Issue: Tests fail randomly with "QApplication already exists"

**Cause:** Creating multiple QApplication instances

**Solution:** Use `qapp` fixture (session-scoped)

```python
# BAD
def test_ui():
    app = QApplication([])  # Creates new instance

# GOOD
def test_ui(qapp, qtbot):
    # Uses session-scoped QApplication
```

### Issue: Tests leak threads

**Cause:** Background threads not joined

**Solution:** Explicitly join threads in teardown

```python
def test_background_task():
    import threading
    
    completed = threading.Event()
    
    def task():
        # Do work
        completed.set()
    
    thread = threading.Thread(target=task)
    thread.start()
    
    # Wait for completion
    assert completed.wait(timeout=5.0)
    
    # Explicitly join
    thread.join(timeout=1.0)
    assert not thread.is_alive()
```

### Issue: Tests fail with "Singleton state pollution"

**Cause:** Singleton not registered for reset

**Solution:** Register singleton in conftest.py

```python
# In conftest.py
from myapp.singleton import MySingleton

register_singleton('my_singleton', MySingleton, MySingleton.reset)
```

---

## Validation Checklist

Before merging changes, verify:

- [ ] All tests pass with `pytest -n auto --dist loadgroup`
- [ ] All tests pass with `pytest --randomly-seed=auto`
- [ ] No resource leaks (threads, connections, files)
- [ ] Test execution time improved by 50%+
- [ ] All fixtures have proper scope documented
- [ ] All resource-creating fixtures have cleanup
- [ ] All singletons registered for reset
- [ ] All mocks are function-scoped
- [ ] Test grouping markers added where appropriate
- [ ] CI configuration updated

---

## Next Steps

1. **Review this guide** with the team
2. **Start with Phase 1** (Foundation) from the architecture document
3. **Migrate tests incrementally** (unit tests first)
4. **Monitor metrics** (execution time, flakiness rate)
5. **Iterate** based on feedback

---

## Resources

- [Test Isolation Architecture](./test-isolation-architecture.md) - Full architecture document
- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/)
- [pytest-qt documentation](https://pytest-qt.readthedocs.io/)
- [DuckDB concurrency](https://duckdb.org/docs/connect/concurrency)

