"""
Filesystem watcher for real-time file detection.

Uses watchdog to monitor OpenCode storage directories and
queue files for processing with debouncing.

Performance:
- Debounce: 500ms to avoid event flooding
- Thread-safe queue for file processing
- Priority to recent files
"""

import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional
from queue import Queue, Empty

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
)

from ...utils.logger import info, error


# Debounce delay in seconds
DEBOUNCE_DELAY = 0.5

# File types by directory name
FILE_TYPE_MAP = {
    "session": "session",
    "message": "message",
    "part": "part",
    "todo": "todo",
    "project": "project",
    "session_diff": "session_diff",
}


class DebouncedEventHandler(FileSystemEventHandler):
    """Handle filesystem events with debouncing.

    Aggregates rapid-fire events for the same file into a single
    processing request after a delay.
    """

    def __init__(self, on_file_ready: Callable[[str, Path], None]):
        """Initialize the handler.

        Args:
            on_file_ready: Callback when a file is ready to process.
                          Args: (file_type, path)
        """
        super().__init__()
        self._on_file_ready = on_file_ready
        self._pending: dict[str, float] = {}  # path -> last_event_time
        self._lock = threading.Lock()
        self._debounce_thread: Optional[threading.Thread] = None
        self._running = True

        # Start debounce processor thread
        self._debounce_thread = threading.Thread(
            target=self._debounce_loop, daemon=True
        )
        self._debounce_thread.start()

    def stop(self) -> None:
        """Stop the debounce processor."""
        self._running = False
        if self._debounce_thread:
            self._debounce_thread.join(timeout=2)

    def _debounce_loop(self) -> None:
        """Process debounced events in a loop."""
        while self._running:
            now = time.time()
            ready_paths: list[str] = []

            with self._lock:
                # Find paths that have been quiet long enough
                for path_str, last_time in list(self._pending.items()):
                    if now - last_time >= DEBOUNCE_DELAY:
                        ready_paths.append(path_str)
                        del self._pending[path_str]

            # Process ready files outside the lock
            batch_counts: dict[str, int] = {}
            for path_str in ready_paths:
                path = Path(path_str)
                file_type = self._get_file_type(path)
                if file_type:
                    try:
                        self._on_file_ready(file_type, path)
                        batch_counts[file_type] = batch_counts.get(file_type, 0) + 1
                    except Exception:
                        pass

            if batch_counts:
                parts = [f"{count} {ftype}" for ftype, count in batch_counts.items()]
                info(f"[Indexer] Processed batch: {', '.join(parts)}")

            time.sleep(0.1)  # Short sleep between checks

    def _get_file_type(self, path: Path) -> Optional[str]:
        """Determine file type from path.

        Args:
            path: File path

        Returns:
            File type string or None if unknown
        """
        for part in path.parts:
            if part in FILE_TYPE_MAP:
                return FILE_TYPE_MAP[part]
        return None

    def _queue_file(self, path: Path) -> None:
        """Queue a file for debounced processing.

        Args:
            path: Path to the file
        """
        if path.suffix != ".json":
            return

        with self._lock:
            self._pending[str(path)] = time.time()

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        """Handle file creation."""
        if event.is_directory:
            return
        src_path = (
            event.src_path
            if isinstance(event.src_path, str)
            else event.src_path.decode()
        )
        self._queue_file(Path(src_path))

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        """Handle file modification."""
        if event.is_directory:
            return
        src_path = (
            event.src_path
            if isinstance(event.src_path, str)
            else event.src_path.decode()
        )
        self._queue_file(Path(src_path))


class FileWatcher:
    """Watches OpenCode storage directories for changes.

    Uses watchdog to monitor file creation/modification and
    queues files for processing with debouncing.
    """

    def __init__(
        self,
        storage_path: Path,
        on_file_ready: Callable[[str, Path], None],
    ):
        """Initialize the watcher.

        Args:
            storage_path: Path to OpenCode storage directory
            on_file_ready: Callback when a file is ready to process
        """
        self._storage_path = storage_path
        self._on_file_ready = on_file_ready
        self._observer: Any = None  # watchdog.observers.Observer
        self._handler: Optional[DebouncedEventHandler] = None
        self._running = False
        self._stats = {
            "events_received": 0,
            "files_queued": 0,
        }

    def start(self) -> bool:
        """Start watching for file changes.

        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            return True

        if not self._storage_path.exists():
            return False

        try:
            # Wrap callback to track stats
            def tracked_callback(file_type: str, path: Path) -> None:
                self._stats["files_queued"] += 1
                self._on_file_ready(file_type, path)

            self._handler = DebouncedEventHandler(tracked_callback)
            self._observer = Observer()

            # Watch each subdirectory
            for subdir in ["session", "message", "part", "todo", "project"]:
                path = self._storage_path / subdir
                if path.exists():
                    self._observer.schedule(self._handler, str(path), recursive=True)
                    info(f"[Watcher] Watching {path}")

            self._observer.start()
            self._running = True
            info("[Watcher] Started filesystem watcher")
            return True

        except Exception as e:
            error(f"[Watcher] Failed to start: {e}")
            return False

    def stop(self) -> None:
        """Stop watching for file changes."""
        self._running = False

        if self._handler:
            self._handler.stop()

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)

        info("[Watcher] Stopped filesystem watcher")

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running

    def get_stats(self) -> dict:
        """Get watcher statistics.

        Returns:
            Dict with event/queue counts
        """
        return self._stats.copy()


class ProcessingQueue:
    """Thread-safe queue for file processing with priority.

    Prioritizes files by modification time (most recent first)
    and provides batch retrieval for efficient processing.
    """

    def __init__(self, max_size: int = 10000):
        """Initialize the queue.

        Args:
            max_size: Maximum queue size (drops oldest if exceeded)
        """
        self._queue: Queue[tuple[float, str, Path]] = Queue(maxsize=max_size)
        self._lock = threading.Lock()
        self._seen: set[str] = set()  # Dedupe within queue

    def put(self, file_type: str, path: Path) -> bool:
        """Add a file to the queue.

        Args:
            file_type: Type of file
            path: Path to file

        Returns:
            True if added, False if duplicate or queue full
        """
        path_str = str(path)

        with self._lock:
            if path_str in self._seen:
                return False
            self._seen.add(path_str)

        try:
            # Get mtime for priority (higher = more recent = higher priority)
            mtime = path.stat().st_mtime if path.exists() else 0
            self._queue.put_nowait((mtime, file_type, path))
            return True
        except Exception:
            return False

    def get_batch(
        self, max_items: int = 50, timeout: float = 0.1
    ) -> list[tuple[str, Path]]:
        """Get a batch of files from the queue.

        Args:
            max_items: Maximum items to retrieve
            timeout: Wait timeout in seconds

        Returns:
            List of (file_type, path) tuples
        """
        batch: list[tuple[str, Path]] = []

        for _ in range(max_items):
            try:
                _, file_type, path = self._queue.get(timeout=timeout)
                batch.append((file_type, path))

                # Remove from seen set
                with self._lock:
                    self._seen.discard(str(path))

            except Empty:
                break

        return batch

    def clear(self) -> None:
        """Clear the queue."""
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except Empty:
                    break
            self._seen.clear()

    @property
    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
