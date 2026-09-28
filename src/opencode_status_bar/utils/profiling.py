"""Performance profiling utilities.

Provides decorators and helpers for measuring performance bottlenecks:
- API endpoint timing
- Database query profiling
- Memory usage tracking
- Response size monitoring
"""

import functools
import time
from typing import Callable, Any, Optional
from datetime import datetime

from .logger import info, warning, debug


# =============================================================================
# API Profiling
# =============================================================================


def profile_api_endpoint(f: Callable) -> Callable:
    """Decorator to profile Flask endpoint performance.

    Logs:
    - Request duration
    - Response size
    - Database query count (if available)
    - Memory delta

    Usage:
        @stats_bp.route("/api/stats")
        @profile_api_endpoint
        def get_stats():
            ...
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        endpoint_name = f.__name__
        start_time = time.perf_counter()
        start_memory = _get_memory_usage()

        try:
            result = f(*args, **kwargs)

            # Measure after execution
            duration_ms = (time.perf_counter() - start_time) * 1000
            end_memory = _get_memory_usage()
            memory_delta_mb = (end_memory - start_memory) / (1024 * 1024)

            # Estimate response size
            response_size_kb = _estimate_response_size(result) / 1024

            # Log performance metrics
            _log_api_metrics(
                endpoint=endpoint_name,
                duration_ms=duration_ms,
                response_size_kb=response_size_kb,
                memory_delta_mb=memory_delta_mb,
            )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            warning(f"[PROFILE] {endpoint_name} failed after {duration_ms:.1f}ms: {e}")
            raise

    return wrapper


def _get_memory_usage() -> int:
    """Get current process memory usage in bytes."""
    try:
        import psutil
        import os

        process = psutil.Process(os.getpid())
        return process.memory_info().rss
    except ImportError:
        # psutil not available, return 0
        return 0


def _estimate_response_size(result: Any) -> int:
    """Estimate response size in bytes.

    Args:
        result: Flask response object or data

    Returns:
        Estimated size in bytes
    """
    try:
        # If it's a Flask response
        if hasattr(result, "get_data"):
            return len(result.get_data())
        # If it's raw data, estimate JSON size
        import json

        return len(json.dumps(result, default=str))
    except Exception:
        return 0


def _log_api_metrics(
    endpoint: str,
    duration_ms: float,
    response_size_kb: float,
    memory_delta_mb: float,
) -> None:
    """Log API performance metrics.

    Args:
        endpoint: Endpoint name
        duration_ms: Request duration in milliseconds
        response_size_kb: Response size in kilobytes
        memory_delta_mb: Memory delta in megabytes
    """
    # Color-code based on duration
    if duration_ms > 5000:  # > 5s = CRITICAL
        log_fn = warning
        severity = "CRITICAL"
    elif duration_ms > 1000:  # > 1s = SLOW
        log_fn = warning
        severity = "SLOW"
    elif duration_ms > 500:  # > 500ms = WARNING
        log_fn = info
        severity = "WARNING"
    else:
        log_fn = info
        severity = "OK"

    log_fn(
        f"[PROFILE] {severity} | {endpoint} | "
        f"{duration_ms:.1f}ms | "
        f"{response_size_kb:.1f}KB | "
        f"mem: {memory_delta_mb:+.1f}MB"
    )

    # Alert on large responses
    if response_size_kb > 10240:  # > 10MB
        warning(
            f"[PROFILE] LARGE RESPONSE: {endpoint} returned {response_size_kb / 1024:.1f}MB"
        )


# =============================================================================
# Database Query Profiling
# =============================================================================


class QueryProfiler:
    """Context manager for profiling DuckDB queries.

    Usage:
        with QueryProfiler("fetch_traces") as profiler:
            result = conn.execute("SELECT ...").fetchall()
        # Logs: [QUERY] fetch_traces | 245.3ms | 1000 rows
    """

    def __init__(self, query_name: str):
        self.query_name = query_name
        self.start_time: float = 0
        self.row_count: int = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000

        if exc_type is None:
            # Success
            log_fn = info if duration_ms < 500 else warning
            log_fn(
                f"[QUERY] {self.query_name} | "
                f"{duration_ms:.1f}ms | "
                f"{self.row_count} rows"
            )
        else:
            # Error
            warning(f"[QUERY] {self.query_name} failed after {duration_ms:.1f}ms")

        return False  # Don't suppress exceptions

    def set_row_count(self, count: int) -> None:
        """Set row count after query execution."""
        self.row_count = count


# =============================================================================
# Memory Profiling
# =============================================================================


class MemoryProfiler:
    """Context manager for tracking memory usage.

    Usage:
        with MemoryProfiler("tree_building"):
            build_large_tree()
        # Logs: [MEMORY] tree_building | +25.3MB | peak: 150.2MB
    """

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_memory: int = 0
        self.peak_memory: int = 0

    def __enter__(self):
        self.start_memory = _get_memory_usage()
        self.peak_memory = self.start_memory
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb):
        end_memory = _get_memory_usage()
        delta_mb = (end_memory - self.start_memory) / (1024 * 1024)
        peak_mb = self.peak_memory / (1024 * 1024)

        if delta_mb > 100:  # > 100MB delta
            log_fn = warning
            severity = "HIGH"
        elif delta_mb > 50:  # > 50MB delta
            log_fn = info
            severity = "MEDIUM"
        else:
            log_fn = info
            severity = "OK"

        log_fn(
            f"[MEMORY] {severity} | {self.operation_name} | "
            f"{delta_mb:+.1f}MB | peak: {peak_mb:.1f}MB"
        )

        return False

    def update_peak(self) -> None:
        """Update peak memory if current is higher."""
        current = _get_memory_usage()
        if current > self.peak_memory:
            self.peak_memory = current


# =============================================================================
# Dashboard Profiling
# =============================================================================


def profile_dashboard_fetch(section_name: str):
    """Decorator for dashboard data fetch methods.

    Usage:
        @profile_dashboard_fetch("monitoring")
        def _fetch_monitoring_data(self):
            ...
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()

            try:
                result = f(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                log_fn = info if duration_ms < 500 else info
                log_fn(f"[DASHBOARD] {section_name} fetch | {duration_ms:.1f}ms")

                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                warning(
                    f"[DASHBOARD] {section_name} fetch failed after {duration_ms:.1f}ms: {e}"
                )
                raise

        return wrapper

    return decorator


# =============================================================================
# Performance Report
# =============================================================================


class PerformanceReport:
    """Collect and report performance metrics over time."""

    def __init__(self):
        self.metrics: list[dict] = []

    def record(
        self,
        operation: str,
        duration_ms: float,
        size_kb: Optional[float] = None,
        memory_mb: Optional[float] = None,
    ) -> None:
        """Record a performance metric.

        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            size_kb: Optional size in kilobytes
            memory_mb: Optional memory delta in megabytes
        """
        self.metrics.append(
            {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "duration_ms": duration_ms,
                "size_kb": size_kb,
                "memory_mb": memory_mb,
            }
        )

    def get_summary(self) -> dict:
        """Get summary statistics.

        Returns:
            Dictionary with min/max/avg/p95/p99 for each metric
        """
        if not self.metrics:
            return {}

        # Group by operation
        by_operation: dict = {}
        for metric in self.metrics:
            op = metric["operation"]
            if op not in by_operation:
                by_operation[op] = []
            by_operation[op].append(metric)

        # Calculate stats for each operation
        summary = {}
        for op, metrics_list in by_operation.items():
            durations = [m["duration_ms"] for m in metrics_list]
            durations.sort()

            count = len(durations)
            p50_idx = int(count * 0.5)
            p95_idx = int(count * 0.95)
            p99_idx = int(count * 0.99)

            summary[op] = {
                "count": count,
                "min_ms": min(durations),
                "max_ms": max(durations),
                "avg_ms": sum(durations) / count,
                "p50_ms": durations[p50_idx],
                "p95_ms": durations[p95_idx],
                "p99_ms": durations[p99_idx],
            }

        return summary

    def print_report(self) -> None:
        """Print formatted performance report."""
        summary = self.get_summary()

        debug("=" * 80)
        debug("PERFORMANCE REPORT")
        debug("=" * 80)

        for op, stats in summary.items():
            debug(f"\n{op}:")
            debug(f"  Count: {stats['count']}")
            debug(f"  Min:   {stats['min_ms']:.1f}ms")
            debug(f"  Avg:   {stats['avg_ms']:.1f}ms")
            debug(f"  P50:   {stats['p50_ms']:.1f}ms")
            debug(f"  P95:   {stats['p95_ms']:.1f}ms")
            debug(f"  P99:   {stats['p99_ms']:.1f}ms")
            debug(f"  Max:   {stats['max_ms']:.1f}ms")

        debug("=" * 80)


# Global performance report instance
_global_report = PerformanceReport()


def get_performance_report() -> PerformanceReport:
    """Get the global performance report instance."""
    return _global_report
