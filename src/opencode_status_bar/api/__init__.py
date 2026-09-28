"""
Analytics API - HTTP interface for dashboard to access DuckDB data.

Architecture:
- The menubar (writer) owns DuckDB and runs the API server
- The dashboard (reader) uses the API client to fetch data
- This solves DuckDB's lack of multi-process concurrency support
"""

from .server import AnalyticsAPIServer, start_api_server, stop_api_server
from .client import AnalyticsAPIClient, get_api_client
from .tree_builder import TracingTreeBuilder

__all__ = [
    "AnalyticsAPIServer",
    "start_api_server",
    "stop_api_server",
    "AnalyticsAPIClient",
    "get_api_client",
    "TracingTreeBuilder",
]
