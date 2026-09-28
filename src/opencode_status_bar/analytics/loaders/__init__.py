"""
Loaders package for OpenCode data.

This package provides modular data loaders for different types of OpenCode data.
Each loader is optimized for its specific data type and uses DuckDB's native
JSON reading or chunked Python processing for maximum performance.

Main entry point:
    load_opencode_data() - Load all data types into the analytics database

Individual loaders:
    - sessions: load_sessions_fast(), get_opencode_storage_path()
    - messages: load_messages_fast()
    - parts: load_parts_fast()
    - skills: load_skills()
    - delegations: load_delegations()
    - traces: load_traces(), extract_traces(), extract_root_sessions()
    - files: load_file_operations()
    - enrichment: enrich_sessions_metadata()
"""

from pathlib import Path
from typing import Optional

from ..db import AnalyticsDB
from ...utils.logger import info, error

# Re-export all public functions for backwards compatibility
from .sessions import get_opencode_storage_path, load_sessions_fast
from .messages import load_messages_fast
from .parts import load_parts_fast
from .skills import load_skills
from .delegations import load_delegations
from .traces import (
    AgentSegment,
    ROOT_TRACE_PREFIX,
    ROOT_AGENT_TYPE,
    get_agent_segments,
    extract_traces,
    extract_root_sessions,
    load_traces,
)
from .files import load_file_operations
from .enrichment import (
    get_session_agent,
    get_first_user_message,
    enrich_sessions_metadata,
)
from .utils import chunked, collect_recent_part_files

# For backwards compatibility, also expose internal helpers with underscore prefix
_chunked = chunked
_collect_recent_part_files = collect_recent_part_files


__all__ = [
    # Main entry point
    "load_opencode_data",
    # Sessions
    "get_opencode_storage_path",
    "load_sessions_fast",
    # Messages
    "load_messages_fast",
    # Parts
    "load_parts_fast",
    # Skills
    "load_skills",
    # Delegations
    "load_delegations",
    # Traces
    "AgentSegment",
    "ROOT_TRACE_PREFIX",
    "ROOT_AGENT_TYPE",
    "get_agent_segments",
    "extract_traces",
    "extract_root_sessions",
    "load_traces",
    # Files
    "load_file_operations",
    # Enrichment
    "get_session_agent",
    "get_first_user_message",
    "enrich_sessions_metadata",
    # Utils (for backwards compatibility)
    "_chunked",
    "_collect_recent_part_files",
]


def load_opencode_data(
    db: Optional[AnalyticsDB] = None,
    storage_path: Optional[Path] = None,
    clear_first: bool = True,
    max_days: int = 30,
    skip_parts: bool = True,
) -> dict:
    """Load OpenCode data into the analytics database.

    Uses DuckDB's native JSON reading for fast bulk loading.

    Args:
        db: Analytics database instance (creates new if not provided)
        storage_path: Path to OpenCode storage (uses default if not provided)
        clear_first: Whether to clear existing data before loading
        max_days: Only load data from the last N days (default 30)
        skip_parts: Skip loading parts (slow with many files), default True

    Returns:
        Dict with counts of loaded items
    """
    if db is None:
        db = AnalyticsDB()

    if storage_path is None:
        storage_path = get_opencode_storage_path()

    if not storage_path.exists():
        error(f"OpenCode storage not found: {storage_path}")
        return {"sessions": 0, "messages": 0, "parts": 0, "error": "Storage not found"}

    info(f"Loading OpenCode data (last {max_days} days)...")

    if clear_first:
        db.clear_data()

    sessions = load_sessions_fast(db, storage_path, max_days)

    # Enrich sessions with computed metadata (Plan 36)
    enrich_sessions_metadata(db)

    messages = load_messages_fast(db, storage_path, max_days)

    # Parts loading is slow (can be 70k+ files) - skip by default
    if skip_parts:
        parts = 0
        info("Skipping parts (use skip_parts=False to load)")
    else:
        parts = load_parts_fast(db, storage_path, max_days)

    delegations = load_delegations(db, storage_path, max_days)
    skills = load_skills(db, storage_path, max_days)
    traces = load_traces(db, storage_path, max_days)

    # Load file operations (from parts, relatively fast)
    file_operations = load_file_operations(db, storage_path, max_days)

    result = {
        "sessions": sessions,
        "messages": messages,
        "parts": parts,
        "delegations": delegations,
        "skills": skills,
        "traces": traces,
        "file_operations": file_operations,
    }

    info(
        f"Total: {sessions} sessions, {messages} messages, {parts} parts, "
        f"{delegations} delegations, {skills} skills, {traces} traces, "
        f"{file_operations} file_operations"
    )
    return result
