# Developer Tools

`pycode/` is a code navigation and quality CLI; see `.opencode/AGENTS.md` for its commands.

The profilers below measure the **inherited dashboard and local API**, which the menu bar app
no longer runs. They need the `legacy` dependencies (`uv sync`) and a running dashboard or API server.

## Prerequisites

```bash
pip install psutil requests
```

## Tools

### 1. API Performance Profiler

Tests API endpoints and measures response times and payload sizes.

```bash
python tools/profile_api.py

python tools/profile_api.py --endpoint /api/tracing/tree --requests 20

python tools/profile_api.py --url http://localhost:5050
```

**Output**:
- Response time percentiles (min, avg, p95, p99, max)
- Payload sizes
- Identification of slow endpoints (> 1s) and critical ones (> 5s)
- Large payload detection (> 1MB)

### 2. Dashboard Performance Profiler

Profiles dashboard CPU and memory usage during normal operation.

```bash
python tools/profile_dashboard.py --duration 30

python tools/profile_dashboard.py --duration 60 --output custom_report.txt
```

**Output**:
- CPU profiling (top functions by cumulative time)
- Memory allocation tracking (top 20 allocations)
- Full profile saved to file for detailed analysis

**Note**: Requires PyQt6. Dashboard will open - interact normally (switch tabs, refresh) during profiling.

### 3. DuckDB Query Analyzer

Analyzes common database queries and shows execution plans.

```bash
python tools/analyze_queries.py

python tools/analyze_queries.py --db ~/.config/opencode-status-bar/analytics.duckdb
```

**Output**:
- EXPLAIN ANALYZE output for each query
- Row counts and table statistics
- Index usage verification
- Optimization recommendations

## Using Profiling Decorators in Code

### API Endpoints

```python
from opencode_status_bar.utils.profiling import profile_api_endpoint

@stats_bp.route("/api/stats")
@profile_api_endpoint
def get_stats():
    return jsonify({"data": ...})
```

### Dashboard Methods

```python
from opencode_status_bar.utils.profiling import profile_dashboard_fetch

@profile_dashboard_fetch("monitoring")
def _fetch_monitoring_data(self):
    pass
```

### Database Queries

```python
from opencode_status_bar.utils.profiling import QueryProfiler

with QueryProfiler("fetch_traces") as profiler:
    result = conn.execute("SELECT ...").fetchall()
    profiler.set_row_count(len(result))
```

### Memory Tracking

```python
from opencode_status_bar.utils.profiling import MemoryProfiler

with MemoryProfiler("tree_building"):
    build_large_tree()
```

## Performance Report

Collect metrics over time and generate reports:

```python
from opencode_status_bar.utils.profiling import get_performance_report

report = get_performance_report()

report.record("api_call", duration_ms=245.3, size_kb=150.2)

report.print_report()
```

## Interpreting Results

### API Profiler

- **CRITICAL** (P95 > 5s): Requires immediate attention
- **SLOW** (avg > 1s): Should be optimized
- **LARGE** (> 1MB): Consider pagination

### Dashboard Profiler

- Look for functions with high cumulative time
- Check for memory leaks (growing allocations)
- Identify widget creation hotspots

### Query Analyzer

- Check for full table scans (SCAN instead of INDEX_SCAN)
- Look for missing indexes
- Identify cartesian joins (high row counts)

## Best Practices

1. **Baseline First**: Profile before changes to establish baseline
2. **Isolate**: Test one component at a time
3. **Repeat**: Run multiple times to account for variance
4. **Document**: Save reports and compare over time
5. **Fix Priority**: Critical > Slow > Optimization

## Example Workflow

```bash
# 1. Profile API endpoints
python tools/profile_api.py --requests 20

# 2. Analyze slow queries
python tools/analyze_queries.py

# 3. Profile dashboard
python tools/profile_dashboard.py --duration 30

# 4. Implement fixes

# 5. Re-run profilers to verify improvement
```

## Common Issues

### "Import could not be resolved"

LSP type checking errors - ignore them. Scripts work at runtime:

```bash
# Verify imports work
python -c "from opencode_status_bar.dashboard.window import DashboardWindow"
```

### "Connection refused"

Make sure the menubar app is running before profiling API:

```bash
# Start menubar first
make run

# Then profile API
python tools/profile_api.py
```

### "Database not found"

Run the menubar app first to create the analytics database:

```bash
make run
```

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| API response (p95) | < 500ms | > 5s |
| Dashboard refresh | < 100ms | > 500ms |
| Query execution | < 100ms | > 1s |
| Memory per refresh | < 10MB | > 100MB |
| Payload size | < 1MB | > 10MB |
