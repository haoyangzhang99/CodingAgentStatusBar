# Test Isolation Architecture for Parallel Execution

**Version:** 1.0  
**Date:** January 12, 2026  
**Status:** Proposed  
**Author:** Winston (Architect Agent)

---

## Executive Summary

This document defines a comprehensive test isolation architecture to eliminate flakiness when running tests in parallel with pytest-xdist. The architecture addresses database isolation, filesystem isolation, network/port conflicts, Qt UI singleton management, and global state pollution.

**Key Goals:**
- ✅ Zero flaky tests in parallel execution
- ✅ 50%+ faster test execution with parallelization
- ✅ No resource leaks or state pollution
- ✅ Tests pass in random order

---

## Table of Contents

1. [Problem Analysis](#problem-analysis)
2. [Isolation Architecture](#isolation-architecture)
3. [Implementation Patterns](#implementation-patterns)
4. [Refactoring Roadmap](#refactoring-roadmap)
5. [Configuration Changes](#configuration-changes)
6. [Success Metrics](#success-metrics)

---

## Problem Analysis

### Current State

The project has ~100+ test files across `tests/unit/` and `tests/integration/` directories. Tests use:
- **DuckDB** for analytics database
- **Flask** for REST API
- **PyQt6** for dashboard UI
- **aiohttp** for async operations
- **pytest-xdist** for parallel execution

### Identified Flakiness Patterns

#### 1. Database State Leakage
**Problem:** Multiple test workers accessing the same DuckDB file causes:
- Lock contention
- Data pollution between tests
- Race conditions in file processing

**Evidence:**
```python
# tests/unit/analytics/test_db_isolation.py
def test_db_isolation_between_tests_part2(self, analytics_db):
    # Data from previous test should NOT be here
    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 0, "Data from previous test leaked!"
```

#### 2. Singleton State Pollution
**Problem:** Global singletons (QApplication, registries, caches) shared across tests

**Evidence:**
```python
# tests/conftest.py line 735
# Global Singleton Reset Fixture (CRITICAL for parallel test execution)
```

#### 3. Port Conflicts
**Problem:** Flask test servers and mock HTTP servers conflict on same ports

**Evidence:**
```python
# tests/conftest.py line 714
# Port Allocation Fixture (for parallel test execution)
```

#### 4. Race Conditions
**Problem:** File creation/processing races between bulk loader and file watcher

**Evidence:**
```python
# tests/unit/analytics/test_race_conditions.py
class TestRaceConditionScenarios:
    """Test race condition scenarios between bulk and realtime."""
```

#### 5. Timing Dependencies
**Problem:** Tests using `time.sleep()` and `qtbot.wait()` are fragile

**Evidence:**
```python
# Multiple test files use qtbot.wait(50) for synchronization
qtbot.wait(50)  # Fragile timing assumption
```

---

## Isolation Architecture

### Layer 1: Database Isolation

**Strategy:** Each pytest-xdist worker gets its own DuckDB file

```python
@pytest.fixture(scope="session")
def worker_db_path(tmp_path_factory, worker_id):
    """Worker-specific database path."""
    if worker_id == "master":
        # Not using xdist
        return tmp_path_factory.getbasetemp() / "test.duckdb"
    
    # Worker-specific database
    return tmp_path_factory.getbasetemp() / f"test_{worker_id}.duckdb"

@pytest.fixture
def analytics_db(worker_db_path):
    """Function-scoped database with automatic cleanup."""
    db = AnalyticsDB(db_path=worker_db_path, read_only=False)
    
    with db:
        db._create_schema()
    
    yield db
    
    # Explicit cleanup
    if db._conn is not None:
        db.close()
    
    # Verify cleanup
    assert db._conn is None, "Database connection not closed!"
```

**Key Principles:**
- ✅ Each worker has isolated database file
- ✅ Function scope by default (fresh DB per test)
- ✅ Explicit cleanup with verification
- ✅ Session scope only for read-only reference data

### Layer 2: Filesystem Isolation

**Strategy:** Each worker gets its own storage directory

```python
@pytest.fixture
def temp_storage(tmp_path, worker_id):
    """Worker-specific storage directory."""
    if worker_id == "master":
        storage = tmp_path / "storage"
    else:
        storage = tmp_path / f"storage_{worker_id}"
    
    storage.mkdir(parents=True, exist_ok=True)
    
    yield storage
    
    # Cleanup handled by tmp_path fixture

@pytest.fixture
def worker_temp_dir(tmp_path_factory, worker_id):
    """Worker-specific temporary directory for session-scoped resources."""
    if worker_id == "master":
        temp_dir = tmp_path_factory.getbasetemp()
    else:
        temp_dir = tmp_path_factory.getbasetemp() / worker_id
    
    temp_dir.mkdir(exist_ok=True)
    return temp_dir
```

**Key Principles:**
- ✅ No shared filesystem state between workers
- ✅ File watchers scoped to worker directories
- ✅ Use FileLock for any shared file operations

### Layer 3: Network/Port Isolation

**Strategy:** Allocate ports based on worker ID

```python
@pytest.fixture(scope="session")
def worker_port_base(worker_id):
    """Base port for this worker (each worker gets 100 ports)."""
    if worker_id == "master":
        return 5000
    
    worker_num = int(worker_id.replace("gw", ""))
    return 5000 + (worker_num * 100)

@pytest.fixture
def flask_test_port(worker_port_base):
    """Flask test server port."""
    return worker_port_base + 0

@pytest.fixture
def mock_http_port(worker_port_base):
    """Mock HTTP server port."""
    return worker_port_base + 1

@pytest.fixture
def api_client_real(flask_app_real, flask_test_port):
    """Flask test client with worker-specific port."""
    app = flask_app_real
    app.config['TESTING'] = True
    app.config['SERVER_NAME'] = f'localhost:{flask_test_port}'
    
    with app.test_client() as client:
        yield client
```

**Port Allocation Scheme:**
- Worker `master`: 5000-5099
- Worker `gw0`: 5100-5199
- Worker `gw1`: 5200-5299
- Worker `gw2`: 5300-5399
- etc.

### Layer 4: Qt/UI Isolation

**Strategy:** Session-scoped QApplication, function-scoped widgets

```python
@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication (singleton constraint)."""
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    yield app
    
    # QApplication cleanup handled by pytest-qt

@pytest.fixture
def dashboard_window(qapp, qtbot, mock_api_client):
    """Function-scoped dashboard window with automatic cleanup."""
    from opencode_status_bar.dashboard.window import DashboardWindow
    
    window = DashboardWindow(api_client=mock_api_client)
    qtbot.addWidget(window)  # Automatic cleanup
    
    yield window
    
    # Explicit cleanup
    window.close()
    
    # Verify cleanup
    assert not window.isVisible(), "Window not properly closed!"
```

**Key Principles:**
- ✅ QApplication is session-scoped (singleton)
- ✅ All widgets are function-scoped
- ✅ Use `qtbot.addWidget()` for automatic cleanup
- ✅ Explicit cleanup verification

### Layer 5: Singleton/Global State Isolation

**Strategy:** Registry-based singleton management with automatic reset

```python
# Global singleton registry
_SINGLETON_REGISTRY = {}

def register_singleton(name, instance, reset_func):
    """Register a singleton for automatic reset."""
    _SINGLETON_REGISTRY[name] = (instance, reset_func)

@pytest.fixture(autouse=True, scope="function")
def reset_singletons():
    """Automatically reset all singletons before each test."""
    # Reset before test
    for name, (instance, reset_func) in _SINGLETON_REGISTRY.items():
        reset_func(instance)
    
    yield
    
    # Verify after test (optional)
    # Could add verification logic here

# Example singleton registration
class CacheManager:
    _instance = None
    _cache = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._cache.clear()

# Register at module level
register_singleton('cache_manager', CacheManager, CacheManager.reset)
```

**Key Principles:**
- ✅ All singletons registered in central registry
- ✅ Automatic reset before each test
- ✅ Explicit reset functions for each singleton

### Layer 6: Mock Isolation

**Strategy:** Centralized mock registry with automatic cleanup

```python
class MockRegistry:
    """Central registry for all mocks with automatic cleanup."""
    
    def __init__(self):
        self._mocks = {}
        self._patches = []
    
    def register_mock(self, name, mock_obj):
        """Register a mock for tracking."""
        self._mocks[name] = mock_obj
        return mock_obj
    
    def patch(self, target, **kwargs):
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
            patcher.stop()
        
        self._patches.clear()

@pytest.fixture
def mock_registry():
    """Function-scoped mock registry."""
    registry = MockRegistry()
    yield registry
    registry.reset_all()

@pytest.fixture
def mock_api_client(mock_registry):
    """Function-scoped mock API client."""
    from unittest.mock import MagicMock
    from opencode_status_bar.api.client import APIClient
    
    mock = MagicMock(spec=APIClient)
    mock_registry.register_mock('api_client', mock)
    return mock
```

**Key Principles:**
- ✅ All mocks are function-scoped
- ✅ Centralized tracking and cleanup
- ✅ Automatic reset after each test

### Layer 7: Async/Threading Isolation

**Strategy:** Proper event loop and thread cleanup

```python
@pytest.fixture
async def async_client():
    """Async HTTP client with proper cleanup."""
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        yield session
    
    # Cleanup handled by context manager

@pytest.fixture
def background_thread():
    """Background thread with explicit join."""
    import threading
    
    threads = []
    
    def start_thread(target, *args, **kwargs):
        thread = threading.Thread(target=target, args=args, kwargs=kwargs)
        thread.start()
        threads.append(thread)
        return thread
    
    yield start_thread
    
    # Cleanup: join all threads
    for thread in threads:
        thread.join(timeout=5.0)
        assert not thread.is_alive(), f"Thread {thread.name} did not terminate!"
```

**Key Principles:**
- ✅ Each test gets its own event loop (pytest-asyncio)
- ✅ Background threads explicitly joined
- ✅ Use threading.Event instead of time.sleep
- ✅ All async tasks cancelled before test ends

### Layer 8: Resource Cleanup Verification

**Strategy:** Automatic verification of resource cleanup

```python
class ResourceTracker:
    """Track resources created during test."""
    
    def __init__(self):
        self.resources = []
    
    def track(self, resource):
        """Track a resource for cleanup."""
        self.resources.append(resource)
        return resource
    
    def cleanup_all(self):
        """Clean up all tracked resources."""
        for resource in reversed(self.resources):
            if hasattr(resource, 'cleanup'):
                resource.cleanup()
            elif hasattr(resource, 'close'):
                resource.close()
            elif hasattr(resource, '__exit__'):
                resource.__exit__(None, None, None)

@pytest.fixture
def resource_tracker():
    """Function-scoped resource tracker."""
    tracker = ResourceTracker()
    yield tracker
    tracker.cleanup_all()

@pytest.fixture(autouse=True)
def verify_cleanup():
    """Verify no resource leaks after each test."""
    import threading
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
```

**Key Principles:**
- ✅ Track all resources created during test
- ✅ Automatic cleanup in reverse order
- ✅ Verify no leaks after test

---

## Implementation Patterns

### Pattern 1: Dependency Injection

**Before (Hard to Test):**
```python
class AnalyticsService:
    def __init__(self):
        self.db = AnalyticsDB()  # Creates own connection
        self.api_client = APIClient("http://localhost:5000")
```

**After (Testable):**
```python
class AnalyticsService:
    def __init__(self, db: AnalyticsDB, api_client: APIClient):
        self.db = db
        self.api_client = api_client

# In tests
def test_service(analytics_db, mock_api_client):
    service = AnalyticsService(db=analytics_db, api_client=mock_api_client)
    # Test with isolated dependencies
```

### Pattern 2: Test Grouping

**Group tests by resource type:**

```python
# Group database-heavy tests together
@pytest.mark.xdist_group("database")
class TestDatabaseOperations:
    def test_insert(self, analytics_db):
        pass
    
    def test_query(self, analytics_db):
        pass

# Group UI tests together (share QApplication)
@pytest.mark.xdist_group("ui")
class TestDashboardUI:
    def test_window_creation(self, dashboard_window):
        pass
    
    def test_widget_interaction(self, dashboard_window):
        pass

# Group integration tests by subsystem
@pytest.mark.xdist_group("api_integration")
class TestAPIIntegration:
    def test_endpoint_a(self, api_client_real):
        pass
    
    def test_endpoint_b(self, api_client_real):
        pass
```

### Pattern 3: Explicit Cleanup Protocol

**Define cleanup protocol:**

```python
from typing import Protocol

class Cleanable(Protocol):
    """Protocol for resources that need cleanup."""
    
    def cleanup(self) -> None:
        """Clean up resources."""
        ...

class DatabaseConnection(Cleanable):
    def __init__(self, db_path: Path):
        self.conn = duckdb.connect(str(db_path))
    
    def cleanup(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

@pytest.fixture
def db_connection(worker_db_path):
    conn = DatabaseConnection(worker_db_path)
    yield conn
    conn.cleanup()
    
    # Verify cleanup
    assert conn.conn is None, "Connection not closed!"
```

### Pattern 4: State Verification

**Verify state unchanged:**

```python
def capture_global_state():
    """Capture current global state."""
    import threading
    
    return {
        'threads': threading.active_count(),
        'singletons': {k: id(v[0]) for k, v in _SINGLETON_REGISTRY.items()},
    }

@pytest.fixture(autouse=True)
def verify_no_state_leakage():
    """Verify no state leaks between tests."""
    initial_state = capture_global_state()
    
    yield
    
    final_state = capture_global_state()
    
    # Verify thread count
    if final_state['threads'] > initial_state['threads']:
        leaked = final_state['threads'] - initial_state['threads']
        pytest.fail(f"Test leaked {leaked} thread(s)")
```

### Pattern 5: Timing Without Sleep

**Before (Fragile):**
```python
def test_async_operation():
    start_operation()
    time.sleep(1.0)  # Hope it's done
    assert operation_complete()
```

**After (Robust):**
```python
def test_async_operation(qtbot):
    start_operation()
    
    # Wait for condition with timeout
    qtbot.waitUntil(lambda: operation_complete(), timeout=5000)
    
    assert operation_complete()

# Or with threading.Event
def test_background_task():
    completed = threading.Event()
    
    def task():
        do_work()
        completed.set()
    
    thread = threading.Thread(target=task)
    thread.start()
    
    # Wait for completion
    assert completed.wait(timeout=5.0), "Task did not complete"
    thread.join()
```

---

## Refactoring Roadmap

### Phase 1: Foundation (Week 1)

**Goal:** Implement core isolation infrastructure

**Tasks:**
1. ✅ Implement `worker_db_path` fixture
2. ✅ Implement `temp_storage` fixture with worker isolation
3. ✅ Implement `worker_port_base` fixture
4. ✅ Add `ResourceTracker` class
5. ✅ Add `verify_cleanup` autouse fixture

**Deliverables:**
- Updated `tests/conftest.py` with new fixtures
- Documentation in `tests/TESTING.md`

**Success Criteria:**
- All database tests use worker-specific DB files
- All storage tests use worker-specific directories
- All API tests use worker-specific ports

### Phase 2: Fixture Refactoring (Week 2)

**Goal:** Ensure proper fixture scoping and cleanup

**Tasks:**
1. ✅ Audit all session-scoped fixtures
2. ✅ Convert unnecessary session fixtures to function scope
3. ✅ Add explicit cleanup to all fixtures
4. ✅ Implement `Cleanable` protocol
5. ✅ Add cleanup verification to all fixtures

**Deliverables:**
- Fixture scope audit report
- Updated fixtures with cleanup
- Cleanup verification tests

**Success Criteria:**
- No resource leaks in fixture tests
- All fixtures have explicit cleanup
- Cleanup verification passes

### Phase 3: Singleton Management (Week 3)

**Goal:** Eliminate singleton state pollution

**Tasks:**
1. ✅ Identify all singletons in codebase
2. ✅ Implement `_SINGLETON_REGISTRY`
3. ✅ Add reset functions for each singleton
4. ✅ Implement `reset_singletons` autouse fixture
5. ✅ Test singleton isolation

**Deliverables:**
- Singleton registry in `tests/conftest.py`
- Reset functions for all singletons
- Singleton isolation tests

**Success Criteria:**
- All singletons registered
- Tests pass with random order
- No singleton state pollution

### Phase 4: Mock Management (Week 4)

**Goal:** Centralize and automate mock cleanup

**Tasks:**
1. ✅ Implement `MockRegistry` class
2. ✅ Refactor existing mocks to use registry
3. ✅ Ensure all mocks are function-scoped
4. ✅ Add mock cleanup verification
5. ✅ Document mock patterns

**Deliverables:**
- `MockRegistry` in `tests/mocks/__init__.py`
- Updated mock fixtures
- Mock pattern documentation

**Success Criteria:**
- All mocks use registry
- No mock state pollution
- Mock cleanup verification passes

### Phase 5: Test Grouping (Week 5)

**Goal:** Optimize parallel execution with test grouping

**Tasks:**
1. ✅ Add `xdist_group` markers to tests
2. ✅ Group database tests together
3. ✅ Group UI tests together
4. ✅ Group integration tests by resource
5. ✅ Update CI configuration

**Deliverables:**
- Test grouping markers
- Updated `pyproject.toml`
- CI configuration updates

**Success Criteria:**
- Tests grouped by resource type
- Parallel execution optimized
- CI runs reliably

### Phase 6: Validation & Documentation (Week 6)

**Goal:** Validate isolation and document patterns

**Tasks:**
1. ✅ Run full test suite with `pytest -n auto`
2. ✅ Run tests with random order
3. ✅ Measure test execution time improvement
4. ✅ Document all patterns
5. ✅ Create migration guide

**Deliverables:**
- Test execution report
- Pattern documentation
- Migration guide

**Success Criteria:**
- Zero flaky tests
- 50%+ faster execution
- Complete documentation

---

## Configuration Changes

### pyproject.toml Updates

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

# Stricter timeouts for parallel execution
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

# Warnings
filterwarnings = [
    "error",                   # Treat warnings as errors
    "ignore::DeprecationWarning",
    "ignore::PendingDeprecationWarning",
]
```

### Makefile Updates

```makefile
# Test execution targets
.PHONY: test test-unit test-integration test-parallel test-serial

# Fast unit tests (parallel)
test-unit:
	pytest tests/unit/ -n auto --dist loadgroup -v

# Integration tests (parallel)
test-integration:
	pytest tests/integration/ -n auto --dist loadgroup -v

# Full test suite (parallel)
test-parallel:
	pytest -n auto --dist loadgroup -v

# Serial execution (for debugging)
test-serial:
	pytest --dist no -v

# Random order (detect dependencies)
test-random:
	pytest -n auto --dist loadgroup --randomly-seed=auto -v

# Coverage with parallel execution
test-coverage:
	pytest -n auto --dist loadgroup --cov=src/opencode_status_bar --cov-report=html

# Specific worker count (for CI)
test-ci:
	pytest -n 4 --dist loadgroup -v
```

### CI Configuration (.github/workflows/test.yml)

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12"]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      
      - name: Run tests (parallel)
        run: |
          pytest -n 4 --dist loadgroup -v --cov=src/opencode_status_bar
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Success Metrics

### Primary Metrics

1. **Zero Flaky Tests**
   - Metric: Flaky test rate = 0%
   - Measurement: Run test suite 100 times, all must pass
   - Target: 100% pass rate

2. **Faster Execution**
   - Metric: Test execution time reduction
   - Baseline: Current serial execution time
   - Target: 50%+ reduction with parallel execution

3. **No Resource Leaks**
   - Metric: Resource leak count = 0
   - Measurement: Thread count, connection count, file handle count
   - Target: All resources cleaned up after each test

4. **Random Order Stability**
   - Metric: Tests pass in random order
   - Measurement: `pytest --randomly-seed=auto` (100 runs)
   - Target: 100% pass rate

### Secondary Metrics

5. **Fixture Scope Optimization**
   - Metric: % of fixtures that are function-scoped
   - Target: 80%+ function-scoped

6. **Test Grouping Coverage**
   - Metric: % of tests with xdist_group marker
   - Target: 100% of integration tests grouped

7. **Cleanup Verification Coverage**
   - Metric: % of fixtures with cleanup verification
   - Target: 100% of resource-creating fixtures

8. **Documentation Coverage**
   - Metric: All patterns documented
   - Target: 100% of patterns in TESTING.md

### Monitoring

**Continuous Monitoring:**
```bash
# Daily CI run with parallel execution
pytest -n auto --dist loadgroup -v

# Weekly random order test
pytest -n auto --dist loadgroup --randomly-seed=auto -v

# Monthly resource leak audit
pytest -n auto --dist loadgroup -v --resource-leak-check
```

**Alerts:**
- Alert if flaky test detected
- Alert if test execution time increases > 10%
- Alert if resource leak detected

---

## Risk Mitigation

### Risk 1: Breaking Existing Tests

**Mitigation:**
- Gradual rollout (unit tests first, then integration)
- Keep serial execution option for debugging
- Comprehensive testing before merge

**Rollback Plan:**
- Revert to serial execution if issues found
- Fix issues incrementally
- Re-enable parallel execution when stable

### Risk 2: Team Adoption

**Mitigation:**
- Comprehensive documentation
- Training sessions for team
- Code review guidelines
- Automated checks for common violations

**Support:**
- Office hours for questions
- Slack channel for support
- Pair programming sessions

### Risk 3: CI/CD Disruption

**Mitigation:**
- Test CI changes in feature branch
- Gradual rollout to CI
- Monitor CI stability closely

**Rollback Plan:**
- Revert CI configuration if unstable
- Fix issues in development
- Re-enable when stable

---

## Appendix A: Fixture Reference

### Core Isolation Fixtures

```python
# Worker identification
worker_id: str                    # "master", "gw0", "gw1", etc.
worker_port_base: int             # Base port for this worker

# Database isolation
worker_db_path: Path              # Worker-specific DB path
analytics_db: AnalyticsDB         # Function-scoped DB
enrichment_db: AnalyticsDB        # Function-scoped DB with security schema

# Filesystem isolation
temp_storage: Path                # Worker-specific storage directory
worker_temp_dir: Path             # Worker-specific temp directory

# Network isolation
flask_test_port: int              # Flask test server port
mock_http_port: int               # Mock HTTP server port

# Resource management
resource_tracker: ResourceTracker # Track resources for cleanup
mock_registry: MockRegistry       # Track mocks for cleanup

# Qt/UI
qapp: QApplication                # Session-scoped QApplication
dashboard_window: DashboardWindow # Function-scoped window

# Cleanup verification
verify_cleanup: None              # Autouse fixture for cleanup verification
reset_singletons: None            # Autouse fixture for singleton reset
```

### Fixture Scope Guidelines

**Session Scope:**
- `qapp` (QApplication singleton)
- `worker_id` (constant per worker)
- `worker_port_base` (constant per worker)
- `worker_db_path` (path, not connection)

**Function Scope (Default):**
- `analytics_db` (fresh DB per test)
- `temp_storage` (isolated per test)
- `dashboard_window` (fresh window per test)
- `mock_api_client` (fresh mock per test)
- All other fixtures unless documented otherwise

---

## Appendix B: Common Patterns

### Pattern: Worker-Specific Resource

```python
@pytest.fixture(scope="session")
def worker_resource_path(tmp_path_factory, worker_id):
    """Worker-specific resource path."""
    if worker_id == "master":
        return tmp_path_factory.getbasetemp() / "resource"
    return tmp_path_factory.getbasetemp() / f"resource_{worker_id}"
```

### Pattern: Shared Resource with FileLock

```python
@pytest.fixture(scope="session")
def shared_resource(tmp_path_factory, worker_id):
    """Shared resource created once across all workers."""
    from filelock import FileLock
    
    if worker_id == "master":
        # Not using xdist
        return create_resource()
    
    # Get shared temp directory
    root_tmp_dir = tmp_path_factory.getbasetemp().parent
    resource_file = root_tmp_dir / "shared_resource.json"
    lock_file = str(resource_file) + ".lock"
    
    with FileLock(lock_file):
        if resource_file.is_file():
            # Another worker already created it
            data = json.loads(resource_file.read_text())
        else:
            # First worker creates the resource
            data = create_resource()
            resource_file.write_text(json.dumps(data))
    
    return data
```

### Pattern: Cleanup Verification

```python
@pytest.fixture
def verified_resource():
    """Resource with cleanup verification."""
    resource = create_resource()
    
    yield resource
    
    # Cleanup
    resource.cleanup()
    
    # Verify
    assert resource.is_cleaned_up(), "Resource not cleaned up!"
```

---

## Appendix C: Migration Checklist

### For Each Test File

- [ ] Add `xdist_group` marker if needed
- [ ] Verify all fixtures are properly scoped
- [ ] Add cleanup verification to resource fixtures
- [ ] Replace `time.sleep()` with proper synchronization
- [ ] Ensure mocks are function-scoped
- [ ] Add explicit cleanup to teardown
- [ ] Test with `pytest -n auto`
- [ ] Test with `pytest --randomly-seed=auto`

### For Each Fixture

- [ ] Document scope and reason
- [ ] Add explicit cleanup
- [ ] Add cleanup verification
- [ ] Use worker-specific resources if needed
- [ ] Register singletons if applicable
- [ ] Test isolation with parallel execution

### For Each Class

- [ ] Add dependency injection
- [ ] Remove hard-coded resource creation
- [ ] Accept dependencies via constructor
- [ ] Document dependencies
- [ ] Update tests to inject dependencies

---

## Conclusion

This test isolation architecture provides a comprehensive solution for eliminating flakiness in parallel test execution. By implementing worker-specific resource isolation, proper fixture scoping, singleton management, and cleanup verification, we can achieve:

- ✅ **Zero flaky tests** in parallel execution
- ✅ **50%+ faster** test execution
- ✅ **No resource leaks** or state pollution
- ✅ **Reliable CI/CD** pipeline

The architecture is designed for gradual adoption with minimal disruption to existing workflows. Each phase builds on the previous one, allowing for incremental validation and rollback if needed.

**Next Steps:**
1. Review and approve this architecture document
2. Begin Phase 1 implementation (Foundation)
3. Monitor metrics and adjust as needed
4. Iterate based on team feedback

---

**Document Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-12 | Winston | Initial architecture document |

