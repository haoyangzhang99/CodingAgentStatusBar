"""
Trace builder package.

Public API:
- TraceBuilder: Main class for building trace tables

TraceBuilder provides methods for:
1. Building agent_traces from delegation events (existing)
2. Building exchanges table (user->assistant conversation pairs)
3. Building exchange_traces (chronological event timeline per exchange)
4. Building session_traces (high-level session aggregations)

Constants:
- ROOT_TRACE_PREFIX: Prefix for root trace IDs
- ROOT_AGENT_TYPE: Agent type for root traces

Internal modules:
- builder: TraceBuilder class implementation
- helpers: Pure utility functions
- segments: Conversation segment building
"""

from .builder import TraceBuilder, ROOT_TRACE_PREFIX, ROOT_AGENT_TYPE

__all__ = [
    "TraceBuilder",
    "ROOT_TRACE_PREFIX",
    "ROOT_AGENT_TYPE",
]
