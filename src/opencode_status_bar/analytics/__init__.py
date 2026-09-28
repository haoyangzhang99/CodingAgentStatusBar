"""
OpenCode Analytics module.

Provides analytics and reporting for OpenCode session data.

Structure:
- models.py: Data models (dataclasses)
- db.py: DuckDB database management
- indexer/: Background incremental data collection
- loader.py: Bulk data loading (legacy)
- queries.py: SQL queries
- tracing/: Centralized tracing data service package
"""

from .db import AnalyticsDB, get_analytics_db
from .loader import load_opencode_data
from .materialization import MaterializedTableManager
from .models import PeriodStats, TokenStats
from .queries import AnalyticsQueries
from .tracing import TracingDataService, TracingConfig

__all__ = [
    # Database
    "AnalyticsDB",
    "get_analytics_db",
    # Materialization
    "MaterializedTableManager",
    # Data loading (legacy bulk)
    "load_opencode_data",
    # Models
    "PeriodStats",
    "TokenStats",
    # Queries
    "AnalyticsQueries",
    # Tracing Service
    "TracingDataService",
    "TracingConfig",
]
