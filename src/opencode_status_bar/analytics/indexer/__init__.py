"""
Realtime Indexer for OpenCode analytics.

Watches the OpenCode storage directory and processes files in realtime.
Bulk/historical loading is handled separately by scripts/backfill.py.

Usage:
    from opencode_status_bar.analytics.indexer import start_indexer, stop_indexer

    start_indexer()
    # ... runs in background ...
    stop_indexer()
"""

from .hybrid import (
    HybridIndexer,
    IndexerRegistry,
    get_hybrid_indexer,
    start_hybrid_indexer,
    stop_hybrid_indexer,
)
from .tracker import FileTracker, FileInfo
from .parsers import (
    FileParser,
    ParsedSession,
    ParsedMessage,
    ParsedPart,
    ParsedDelegation,
    ParsedSkill,
    ParsedTodo,
    ParsedProject,
    ParsedFileOperation,
)
from .trace_builder import TraceBuilder
from .watcher import FileWatcher, ProcessingQueue


def start_indexer():
    """Start the indexer."""
    start_hybrid_indexer()


def stop_indexer():
    """Stop the indexer."""
    stop_hybrid_indexer()


def get_indexer():
    """Get the indexer instance."""
    return get_hybrid_indexer()


__all__ = [
    "HybridIndexer",
    "IndexerRegistry",
    "get_indexer",
    "start_indexer",
    "stop_indexer",
    "get_hybrid_indexer",
    "start_hybrid_indexer",
    "stop_hybrid_indexer",
    "FileTracker",
    "FileInfo",
    "FileParser",
    "TraceBuilder",
    "FileWatcher",
    "ProcessingQueue",
    "ParsedSession",
    "ParsedMessage",
    "ParsedPart",
    "ParsedDelegation",
    "ParsedSkill",
    "ParsedTodo",
    "ParsedProject",
    "ParsedFileOperation",
]
