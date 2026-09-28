"""
Realtime Indexer - File watching and processing for OpenCode storage.

Watches the OpenCode storage directory and processes files in realtime.
Bulk/historical loading is handled separately by scripts/backfill.py.
"""

import threading
import time
from pathlib import Path
from typing import Optional

from ..db import AnalyticsDB
from ..materialization import MaterializedTableManager
from .watcher import FileWatcher
from .parsers import FileParser
from .tracker import FileTracker
from .trace_builder import TraceBuilder
from .file_processing import FileProcessingState
from .handlers import (
    FileHandler,
    SessionHandler,
    MessageHandler,
    PartHandler,
    SessionDiffHandler,
)
from ...utils.logger import info


OPENCODE_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage"


class HybridIndexer:
    """
    Realtime indexer using file watching.

    Watches the OpenCode storage directory and processes files as they change.
    Historical/bulk loading is done separately via `make backfill`.

    Usage:
        indexer = HybridIndexer()
        indexer.start()
        # ... runs in background ...
        indexer.stop()
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        db: Optional[AnalyticsDB] = None,
        tracker: Optional[FileTracker] = None,
        parser: Optional[FileParser] = None,
        trace_builder: Optional[TraceBuilder] = None,
        **kwargs,  # Accept but ignore deprecated params
    ):
        self._storage_path = storage_path or OPENCODE_STORAGE

        self._db = db or AnalyticsDB(db_path)
        self._db_injected = db is not None

        self._injected_tracker = tracker
        self._injected_parser = parser
        self._injected_trace_builder = trace_builder

        self._watcher: Optional[FileWatcher] = None
        self._tracker: Optional[FileTracker] = None
        self._parser: Optional[FileParser] = None
        self._trace_builder: Optional[TraceBuilder] = None
        self._file_processing: Optional[FileProcessingState] = None
        self._materialization_manager: Optional[MaterializedTableManager] = None

        self._handlers: dict[str, FileHandler] = {
            "session": SessionHandler(),
            "message": MessageHandler(),
            "part": PartHandler(),
            "session_diff": SessionDiffHandler(),
        }

        self._running = False
        self._t0: Optional[float] = None
        self._files_processed = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the realtime indexer."""
        if self._running:
            return

        self._running = True
        self._t0 = time.time()

        info("[Indexer] Starting")
        info(f"[Indexer] Storage: {self._storage_path}")

        self._db.connect()

        self._tracker = self._injected_tracker or FileTracker(self._db)
        self._parser = self._injected_parser or FileParser()
        self._trace_builder = self._injected_trace_builder or TraceBuilder(self._db)
        self._file_processing = FileProcessingState(self._db)
        self._materialization_manager = MaterializedTableManager(self._db)

        self._materialization_manager.initialize_indexes()

        self._watcher = FileWatcher(
            self._storage_path,
            self._on_file_event,
        )
        self._watcher.start()

        info("[Indexer] Ready")

    def stop(self) -> None:
        """Stop the realtime indexer."""
        self._running = False

        if self._watcher:
            self._watcher.stop()

        self._db.close()
        info("[Indexer] Stopped")

    def _extract_session_id(self, path: Path) -> Optional[str]:
        """Extract session ID from file path."""
        try:
            if "messages" in path.parts:
                idx = path.parts.index("messages")
                if idx + 1 < len(path.parts):
                    return path.parts[idx + 1]

            parts = path.stem.split("_")
            if len(parts) >= 2 and parts[0] == "session":
                return "_".join(parts[1:])

            return None
        except Exception:
            return None

    def _on_file_event(self, file_type: str, path: Path) -> None:
        """Handle file event from watcher - process immediately."""
        processed = self._process_file(file_type, path)

        if processed and file_type in ("message", "part"):
            session_id = self._extract_session_id(path)
            if session_id and self._materialization_manager:
                try:
                    self._materialization_manager.refresh_exchanges(
                        session_id=session_id, incremental=True
                    )
                    self._materialization_manager.refresh_session_traces(
                        session_id=session_id, incremental=True
                    )
                except Exception:
                    pass

    def _process_file(self, file_type: str, path: Path) -> bool:
        """Process a single file."""
        try:
            if not self._tracker or not self._parser or not self._trace_builder:
                return False

            if self._t0 and self._file_processing:
                try:
                    file_mtime = path.stat().st_mtime
                    if file_mtime < self._t0:
                        if self._file_processing.is_already_processed(str(path)):
                            return True
                except (OSError, FileNotFoundError):
                    pass

            if not self._tracker.needs_indexing(path):
                return True

            handler = self._handlers.get(file_type)
            if not handler:
                return False

            raw_data = self._parser.read_json(path)
            if raw_data is None:
                self._tracker.mark_error(path, file_type, "Failed to read JSON")
                return False

            conn = self._db.connect()
            record_id = handler.process(
                file_path=path,
                raw_data=raw_data,
                conn=conn,
                parser=self._parser,
                trace_builder=self._trace_builder,
            )

            if record_id:
                self._tracker.mark_indexed(path, file_type, record_id)
                if self._file_processing:
                    self._file_processing.mark_processed(
                        str(path), file_type, status="processed"
                    )
                with self._lock:
                    self._files_processed += 1
                return True
            else:
                self._tracker.mark_error(path, file_type, "Invalid data")
                if self._file_processing:
                    self._file_processing.mark_processed(
                        str(path), file_type, status="failed"
                    )
                return False

        except Exception as e:
            if self._tracker:
                self._tracker.mark_error(path, file_type, str(e))
            return False

    def is_ready(self) -> bool:
        """Check if indexer is ready (always True once started)."""
        return self._running

    def get_stats(self) -> dict:
        """Get indexer statistics."""
        with self._lock:
            return {
                "running": self._running,
                "files_processed": self._files_processed,
            }


class IndexerRegistry:
    """Registry for managing HybridIndexer instance."""

    _instance: Optional[HybridIndexer] = None

    @classmethod
    def get(cls) -> Optional[HybridIndexer]:
        """Get the current indexer instance (may be None)."""
        return cls._instance

    @classmethod
    def get_or_create(
        cls,
        storage_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        **kwargs,
    ) -> HybridIndexer:
        """Get existing indexer or create a new one."""
        if cls._instance is None:
            cls._instance = HybridIndexer(
                storage_path=storage_path,
                db_path=db_path,
                **kwargs,
            )
        return cls._instance

    @classmethod
    def set(cls, indexer: HybridIndexer) -> None:
        """Set the indexer instance (useful for tests with mocks)."""
        cls._instance = indexer

    @classmethod
    def clear(cls) -> None:
        """Clear the registry."""
        if cls._instance:
            cls._instance.stop()
        cls._instance = None

    @classmethod
    def create(
        cls,
        storage_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        db: Optional[AnalyticsDB] = None,
        **kwargs,
    ) -> HybridIndexer:
        cls.clear()
        indexer = HybridIndexer(
            storage_path=storage_path,
            db_path=db_path,
            db=db,
            **kwargs,
        )
        cls._instance = indexer
        return indexer


def get_hybrid_indexer() -> HybridIndexer:
    """Get or create the global hybrid indexer instance."""
    return IndexerRegistry.get_or_create()


def start_hybrid_indexer() -> None:
    """Start the global hybrid indexer."""
    get_hybrid_indexer().start()


def stop_hybrid_indexer() -> None:
    """Stop the global hybrid indexer."""
    IndexerRegistry.clear()
