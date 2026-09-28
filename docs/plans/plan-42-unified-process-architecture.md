# Plan 42 - Unified Process Architecture

**Status**: Draft  
**Priority**: High  
**Effort**: Medium (3-5 days)

## Problem Statement

OpenCode Status Bar currently runs the menu bar and dashboard as **separate processes**, communicating via HTTP API. This adds unnecessary complexity and overhead:

| Overhead | Impact |
|----------|--------|
| JSON serialization | CPU overhead on every request |
| HTTP/TCP stack | ~2-10ms latency per request |
| Two Python interpreters | Double memory footprint |
| Subprocess management | Complexity in launcher.py |
| API maintenance | Routes, client, server code |

## Current Architecture (Two Processes)

```
┌─────────────────────────────────────────────────────────────┐
│                    MENUBAR PROCESS                          │
│  ┌───────────────┐    ┌────────────────┐    ┌───────────┐  │
│  │   OpenCodeApp │───▶│   Flask API    │───▶│  DuckDB   │  │
│  │    (rumps)    │    │  Server :19876 │    │           │  │
│  └───────────────┘    └────────────────┘    └───────────┘  │
└─────────────────────────────────────────────────────────────┘
                               │
                          HTTP/JSON
                               │
┌─────────────────────────────────────────────────────────────┐
│                   DASHBOARD PROCESS                         │
│  ┌────────────────┐    ┌─────────────────┐                  │
│  │  DashboardMain │◀───│ AnalyticsClient │                  │
│  │    (PyQt6)     │    │   HTTP Client   │                  │
│  └────────────────┘    └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

**Why two processes?**
- Historical: rumps and PyQt6 have different event loops
- Assumed conflict between AppKit (rumps) and Qt event loops

## Target Architecture (Single Process)

```
┌─────────────────────────────────────────────────────────────┐
│                    SINGLE PROCESS                           │
│                                                             │
│  ┌───────────────┐         ┌────────────────────────────┐  │
│  │   OpenCodeApp │         │     Dashboard Thread       │  │
│  │    (rumps)    │         │  ┌────────────────────┐    │  │
│  │  Main Thread  │────────▶│  │   DashboardWindow  │    │  │
│  └───────────────┘         │  │      (PyQt6)       │    │  │
│         │                  │  └─────────┬──────────┘    │  │
│         │                  └────────────┼───────────────┘  │
│         │                               │                  │
│         ▼                               ▼                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Shared Service Module                   │   │
│  │         (TracingDataService - singleton)             │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                               │
│                     ┌──────▼──────┐                        │
│                     │   DuckDB    │                        │
│                     └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Key Benefits

| Aspect | Before (2 processes) | After (1 process) |
|--------|---------------------|-------------------|
| **Latency** | ~2-10ms (HTTP) | ~0.01ms (function call) |
| **Memory** | ~200MB x 2 | ~250MB total |
| **Complexity** | Flask + routes + client | Direct import |
| **Startup** | Subprocess spawn | Thread start |
| **Data sharing** | Serialization | Direct Python objects |

## Technical Approach

### 1. Qt in Separate Thread

PyQt6 can run in a non-main thread if we:
1. Create `QApplication` in the thread
2. Keep all Qt operations in that thread
3. Use signals/slots for cross-thread communication

```python
# src/opencode_status_bar/dashboard/thread.py
import threading
from PyQt6.QtWidgets import QApplication
from .window.main import DashboardWindow

class DashboardThread(threading.Thread):
    """Run PyQt dashboard in a separate thread."""
    
    def __init__(self, service: TracingDataService):
        super().__init__(daemon=True)
        self._service = service
        self._app = None
        self._window = None
    
    def run(self):
        """Thread entry point - runs Qt event loop."""
        self._app = QApplication([])
        self._window = DashboardWindow(data_source=self._service)
        self._window.show()
        self._app.exec()
    
    def show(self):
        """Show dashboard window (thread-safe)."""
        if self._window:
            # Use Qt's thread-safe mechanism
            QMetaObject.invokeMethod(
                self._window, "show", 
                Qt.ConnectionType.QueuedConnection
            )
```

### 2. Shared Service Module

The dashboard imports the service directly instead of using HTTP:

```python
# src/opencode_status_bar/services/shared.py
from ..analytics.tracing.service import TracingDataService

# Singleton instance shared between menu bar and dashboard
_service_instance: TracingDataService | None = None

def get_shared_service() -> TracingDataService:
    """Get the shared service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = TracingDataService()
    return _service_instance
```

### 3. Dashboard Data Source

Replace HTTP client with direct service calls:

```python
# src/opencode_status_bar/dashboard/data_source.py
from opencode_status_bar.services.shared import get_shared_service

class DirectDataSource:
    """Data source using shared service (no HTTP)."""
    
    def __init__(self):
        self._service = get_shared_service()
    
    @property
    def is_available(self) -> bool:
        return True  # Always available in same process
    
    def get_tracing_tree(self, days: int = 30) -> list[dict]:
        return self._service.get_tracing_tree(days=days)
    
    def get_global_stats(self, days: int = 30) -> dict:
        return self._service.get_global_stats(days=days)
    
    # ... other methods delegate to self._service
```

### 4. Menu Bar Integration

Launch dashboard as thread instead of subprocess:

```python
# src/opencode_status_bar/app/handlers.py
from ..dashboard.thread import DashboardThread
from ..services.shared import get_shared_service

class OpenCodeAppHandlers:
    def __init__(self):
        self._dashboard_thread: DashboardThread | None = None
    
    def _show_dashboard(self, _):
        """Open the Dashboard window in a thread."""
        if self._dashboard_thread is None or not self._dashboard_thread.is_alive():
            service = get_shared_service()
            self._dashboard_thread = DashboardThread(service)
            self._dashboard_thread.start()
        else:
            self._dashboard_thread.show()
```

## Thread Safety

### DuckDB Access

DuckDB supports concurrent reads. Current locking strategy remains:

```python
class TracingDataService:
    def __init__(self):
        self._lock = threading.RLock()
    
    def get_tracing_tree(self, days: int = 30) -> list[dict]:
        with self._lock:
            # Query DuckDB
            ...
```

### Qt Thread Rules

1. **All Qt widgets** must be created/accessed from the dashboard thread
2. **Signals/slots** handle cross-thread communication safely
3. **No direct widget access** from main thread

## Migration Plan

### Phase 1: Create Thread Infrastructure (1 day)

1. Create `DashboardThread` class
2. Create `DirectDataSource` class
3. Create `get_shared_service()` singleton

**Files to create:**
```
src/opencode_status_bar/dashboard/thread.py
src/opencode_status_bar/dashboard/data_source.py
src/opencode_status_bar/services/__init__.py
src/opencode_status_bar/services/shared.py
```

### Phase 2: Refactor Dashboard (1-2 days)

1. Make `DashboardWindow` accept `data_source` parameter
2. Replace all `AnalyticsAPIClient` calls with `data_source` calls
3. Ensure all Qt operations stay in dashboard thread

**Files to modify:**
```
src/opencode_status_bar/dashboard/window/main.py
src/opencode_status_bar/dashboard/window/sync.py
src/opencode_status_bar/dashboard/sections/*.py
```

### Phase 3: Integrate with Menu Bar (1 day)

1. Replace `subprocess.Popen` with `DashboardThread`
2. Update `_show_dashboard` handler
3. Handle dashboard close/reopen

**Files to modify:**
```
src/opencode_status_bar/app/handlers.py
src/opencode_status_bar/dashboard/window/launcher.py (delete)
```

### Phase 4: Cleanup (1 day)

1. Remove Flask API server (optional - keep for debugging?)
2. Remove HTTP client
3. Update tests

**Files to potentially remove:**
```
src/opencode_status_bar/api/server.py
src/opencode_status_bar/api/client.py
src/opencode_status_bar/api/routes/
```

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Qt/AppKit event loop conflict | Low | High | Qt runs in separate thread, no conflict |
| Dashboard crash affects menu bar | Medium | Medium | Wrap thread in try/catch, restart capability |
| Thread safety bugs | Medium | Medium | Use RLock, Qt signals, code review |
| Memory leaks | Low | Medium | Proper cleanup on dashboard close |

## Testing Strategy

### Unit Tests

```python
def test_dashboard_thread_starts():
    """Dashboard thread starts without blocking main thread."""

def test_shared_service_singleton():
    """get_shared_service() returns same instance."""

def test_direct_data_source():
    """DirectDataSource returns data from service."""
```

### Integration Tests

```python
def test_dashboard_opens_from_menu():
    """Clicking Dashboard menu item opens window."""

def test_dashboard_receives_data():
    """Dashboard displays data from shared service."""

def test_dashboard_close_reopen():
    """Dashboard can be closed and reopened."""
```

## Success Criteria

- [ ] Dashboard opens as thread, not subprocess
- [ ] No HTTP calls between menu bar and dashboard
- [ ] Dashboard displays data correctly
- [ ] Memory usage reduced (~25-50%)
- [ ] Startup time improved
- [ ] All existing tests pass
- [ ] No crashes or hangs

## Effort Estimation

| Phase | Effort |
|-------|--------|
| Phase 1: Thread Infrastructure | S (1 day) |
| Phase 2: Refactor Dashboard | M (1-2 days) |
| Phase 3: Menu Bar Integration | S (1 day) |
| Phase 4: Cleanup | S (1 day) |
| **Total** | **M (3-5 days)** |

## Open Questions

1. **Keep Flask API for debugging?**
   - Pro: Useful for curl testing, external tools
   - Con: Extra code to maintain
   - Recommendation: Keep as optional, disabled by default

2. **Dashboard window management?**
   - Single instance vs multiple windows
   - Recommendation: Single instance, bring to front if exists

3. **Graceful shutdown?**
   - How to handle app quit with dashboard open
   - Recommendation: Dashboard thread is daemon, dies with main

## References

- [PyQt Threading](https://doc.qt.io/qt-6/thread-basics.html)
- [rumps Documentation](https://github.com/jaredks/rumps)
- [Plan 26 - DB Concurrency](../archive/plans/plan-26-db-concurrency.md)
