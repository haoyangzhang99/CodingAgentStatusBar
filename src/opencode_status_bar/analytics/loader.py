"""
JSON data loader for OpenCode storage.

DEPRECATED: This module is deprecated in favor of the indexer.
Use `opencode_status_bar.analytics.indexer` instead:

    from opencode_status_bar.analytics.indexer import (
        start_indexer,
        stop_indexer,
    )

This module is kept for backwards compatibility and batch operations
but will be removed in a future version.

Note: This module now re-exports from the modular loaders package.
Import directly from opencode_status_bar.analytics.loaders for new code.
"""

import warnings

# Deprecation warning
warnings.warn(
    "loader.py is deprecated. Use opencode_status_bar.analytics.loaders instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new loaders package for backwards compatibility
from .loaders import (  # noqa: E402
    # Main entry point
    load_opencode_data,
    # Sessions
    get_opencode_storage_path,
    load_sessions_fast,
    # Messages
    load_messages_fast,
    # Parts
    load_parts_fast,
    # Skills
    load_skills,
    # Delegations
    load_delegations,
    # Traces
    AgentSegment,
    ROOT_TRACE_PREFIX,
    ROOT_AGENT_TYPE,
    get_agent_segments,
    extract_traces,
    extract_root_sessions,
    load_traces,
    # Files
    load_file_operations,
    # Enrichment
    get_session_agent,
    get_first_user_message,
    enrich_sessions_metadata,
    # Utils (internal, with underscore for backwards compat)
    _chunked,
    _collect_recent_part_files,
)

__all__ = [
    "load_opencode_data",
    "get_opencode_storage_path",
    "load_sessions_fast",
    "load_messages_fast",
    "load_parts_fast",
    "load_skills",
    "load_delegations",
    "AgentSegment",
    "ROOT_TRACE_PREFIX",
    "ROOT_AGENT_TYPE",
    "get_agent_segments",
    "extract_traces",
    "extract_root_sessions",
    "load_traces",
    "load_file_operations",
    "get_session_agent",
    "get_first_user_message",
    "enrich_sessions_metadata",
    "_chunked",
    "_collect_recent_part_files",
]
