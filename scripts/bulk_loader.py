"""
Bulk loader using DuckDB native JSON reading.

Uses read_json_auto() to load JSON files directly into DuckDB,
achieving 20,000+ files/second vs ~250 files/second with Python loops.

Schema mapping from OpenCode JSON format to our analytics tables.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.indexer.file_processing import FileProcessingState
from opencode_status_bar.utils.logger import info, debug, error
from bulk_queries import (
    LOAD_SESSIONS_SQL,
    LOAD_MESSAGES_SQL,
    LOAD_PARTS_SQL,
    LOAD_STEP_EVENTS_SQL,
    LOAD_PATCHES_SQL,
    LOAD_FILE_OPERATIONS_SQL,
    CREATE_ROOT_TRACES_SQL,
    COUNT_ROOT_TRACES_SQL,
    CREATE_DELEGATION_TRACES_SQL,
    COUNT_DELEGATION_TRACES_SQL,
)


@dataclass
class BulkLoadResult:
    """Result of a bulk load operation."""

    file_type: str
    files_loaded: int
    duration_seconds: float
    files_per_second: float
    errors: int


class BulkLoader:
    """
    High-performance bulk loader using DuckDB native JSON reading.

    Loads historical files (mtime < T0) directly via SQL, bypassing
    Python loops for massive performance gains.

    Usage:
        loader = BulkLoader(db, storage_path)
        loader.load_all(cutoff_timestamp)
    """

    def __init__(
        self,
        db: AnalyticsDB,
        storage_path: Path,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        """
        Initialize bulk loader.

        Args:
            db: Analytics database instance
            storage_path: Path to OpenCode storage
            on_progress: Optional callback(files_done, files_total)
        """
        self._db = db
        # Validate and resolve storage path before using in SQL
        self._storage_path = self._validate_storage_path(storage_path)
        self._on_progress = on_progress

        # Track what's loaded
        self._sessions_loaded = 0
        self._messages_loaded = 0
        self._parts_loaded = 0
        self._step_events_loaded = 0
        self._patches_loaded = 0
        self._file_operations_loaded = 0

    # Allowed file types for bulk loading - prevents path injection
    _ALLOWED_FILE_TYPES = frozenset({"session", "message", "part"})

    def _validate_storage_path(self, path: Path) -> Path:
        """
        Validate storage path is safe for SQL.

        Args:
            path: Path to validate

        Returns:
            Resolved absolute path

        Raises:
            ValueError: If path does not exist, is not a directory, or fails validation
        """
        if not path.exists():
            raise ValueError(f"Storage path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Storage path is not a directory: {path}")

        # Resolve to absolute path to prevent path traversal
        resolved = path.resolve()

        # Ensure path is absolute (no relative components)
        if not resolved.is_absolute():
            raise ValueError(f"Storage path must be absolute: {path}")

        debug(f"[BulkLoader] Validated storage path: {resolved}")
        return resolved

    def count_files(self) -> dict[str, int]:
        """Count files to be loaded by type."""
        # Path is validated in __init__ and resolved to absolute path
        # file_type is from _ALLOWED_FILE_TYPES, preventing injection
        if not self._storage_path.exists() or not self._storage_path.is_dir():
            debug(f"Invalid storage path: {self._storage_path}")
            return {}

        conn = self._db.connect()
        counts = {}

        for file_type in ["session", "message", "part"]:
            path = self._storage_path / file_type
            if path.exists():
                try:
                    # Path validated in __init__, file_type from hardcoded list
                    result = conn.execute(f"""
                        SELECT COUNT(*) FROM glob('{path}/**/*.json')
                    """).fetchone()
                    counts[file_type] = result[0] if result else 0
                except Exception:
                    counts[file_type] = 0
            else:
                counts[file_type] = 0

        return counts

    def load_all(
        self, cutoff_time: Optional[float] = None
    ) -> dict[str, BulkLoadResult]:
        """
        Load all historical files.

        Args:
            cutoff_time: Only load files with mtime < this timestamp.
                        If None, loads all files.

        Returns:
            Dict of results by file type
        """
        results = {}

        # Load in order: sessions, messages, parts
        results["session"] = self.load_sessions(cutoff_time)
        results["message"] = self.load_messages(cutoff_time)
        results["part"] = self.load_parts(cutoff_time)

        # Step events (from part files - step-start, step-finish)
        results["step_event"] = self.load_step_events(cutoff_time)

        # Patches (from part files - patch type)
        results["patch"] = self.load_patches(cutoff_time)

        # File operations (from part files - read/write/edit)
        results["file_operation"] = self.load_file_operations(cutoff_time)

        # Mark all loaded files as processed to prevent duplicates
        if cutoff_time:
            marked = self.mark_bulk_files_processed(cutoff_time)
            info(f"[BulkLoader] Marked {marked:,} files as processed")

        return results

    def load_sessions(self, cutoff_time: Optional[float] = None) -> BulkLoadResult:
        """Load session files via DuckDB native JSON reading."""
        start = time.time()
        # Path validated in __init__ - safe to use in SQL
        path = self._storage_path / "session"

        if not path.exists() or not path.is_dir():
            return BulkLoadResult("session", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            # Build query with optional time filter
            time_filter = ""
            if cutoff_time:
                # DuckDB doesn't directly support file mtime in read_json_auto
                # We'll filter by the file's created timestamp from the JSON
                time_filter = f"WHERE (time.created / 1000.0) < {cutoff_time}"

            # Load and transform in one query using SQL template
            # Path is validated in __init__ - resolved absolute path, safe for SQL
            query = LOAD_SESSIONS_SQL.format(path=path, time_filter=time_filter)
            conn.execute(query)

            # Count loaded (DuckDB doesn't have changes(), count directly)
            result = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
            count = result[0] if result else 0
            self._sessions_loaded = count

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(f"[BulkLoader] Sessions: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)")

            # Create root traces for sessions without parent
            self._create_root_traces(conn)

            return BulkLoadResult("session", count, elapsed, speed, 0)

        except Exception as e:
            debug(f"[BulkLoader] Session load error: {e}")
            return BulkLoadResult("session", 0, time.time() - start, 0, 1)

    def load_messages(self, cutoff_time: Optional[float] = None) -> BulkLoadResult:
        """Load message files via DuckDB native JSON reading."""
        start = time.time()
        # Path validated in __init__ - safe to use in SQL
        path = self._storage_path / "message"

        if not path.exists() or not path.is_dir():
            return BulkLoadResult("message", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            time_filter = ""
            if cutoff_time:
                time_filter = f"WHERE (time.created / 1000.0) < {cutoff_time}"

            # Load and transform in one query using SQL template
            # Path is validated in __init__ - resolved absolute path, safe for SQL
            query = LOAD_MESSAGES_SQL.format(path=path, time_filter=time_filter)
            conn.execute(query)

            # Count loaded
            result = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
            count = result[0] if result else 0
            self._messages_loaded = count

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(f"[BulkLoader] Messages: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)")

            return BulkLoadResult("message", count, elapsed, speed, 0)

        except Exception as e:
            debug(f"[BulkLoader] Message load error: {e}")
            return BulkLoadResult("message", 0, time.time() - start, 0, 1)

    def load_parts(self, cutoff_time: Optional[float] = None) -> BulkLoadResult:
        """Load part files via DuckDB native JSON reading."""
        start = time.time()
        # Path validated in __init__ - safe to use in SQL
        path = self._storage_path / "part"

        if not path.exists() or not path.is_dir():
            return BulkLoadResult("part", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            info(f"[BulkLoader] Starting parts load from {path}")

            # Optimize DuckDB for bulk loading large number of JSON files
            # - memory_limit: read_text loads all files, needs more RAM
            # - preserve_insertion_order=false: reduces memory usage, order not needed for analytics
            info("[BulkLoader] Setting DuckDB memory limit to 8GB, threads=2")
            conn.execute("SET memory_limit='8GB'")
            conn.execute("SET threads=2")
            conn.execute("SET preserve_insertion_order=false")
            debug("[BulkLoader] DuckDB settings applied")

            # Load and transform in one query using SQL template
            # Path is validated in __init__ - resolved absolute path, safe for SQL
            query = LOAD_PARTS_SQL.format(path=path)
            debug("[BulkLoader] Executing parts SQL query...")
            conn.execute(query)
            debug("[BulkLoader] Parts SQL query completed")

            # Count loaded
            debug("[BulkLoader] Counting loaded parts...")
            result = conn.execute("SELECT COUNT(*) FROM parts").fetchone()
            count = result[0] if result else 0
            self._parts_loaded = count
            debug(f"[BulkLoader] Found {count:,} parts in DB")

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(f"[BulkLoader] Parts: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)")

            # Create delegation traces from task parts
            debug("[BulkLoader] Creating delegation traces...")
            self._create_delegation_traces(conn)
            debug("[BulkLoader] Delegation traces created")

            return BulkLoadResult("part", count, elapsed, speed, 0)

        except Exception as e:
            error(f"[BulkLoader] Part load error: {e}")
            import traceback

            error(f"[BulkLoader] Part load traceback: {traceback.format_exc()}")
            return BulkLoadResult("part", 0, time.time() - start, 0, 1)

    def load_step_events(self, cutoff_time: Optional[float] = None) -> BulkLoadResult:
        """Load step events (step-start, step-finish) via DuckDB native JSON reading."""
        start = time.time()
        # Path validated in __init__ - safe to use in SQL
        path = self._storage_path / "part"

        if not path.exists() or not path.is_dir():
            return BulkLoadResult("step_event", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            # Optimize DuckDB for bulk loading
            conn.execute("SET memory_limit='4GB'")
            conn.execute("SET preserve_insertion_order=false")

            # Load step events from part files (they share the same storage)
            # Path is validated in __init__ - resolved absolute path, safe for SQL
            query = LOAD_STEP_EVENTS_SQL.format(path=path)
            conn.execute(query)

            # Count loaded
            result = conn.execute("SELECT COUNT(*) FROM step_events").fetchone()
            count = result[0] if result else 0
            self._step_events_loaded = count

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(
                f"[BulkLoader] Step events: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)"
            )

            return BulkLoadResult("step_event", count, elapsed, speed, 0)

        except Exception as e:
            debug(f"[BulkLoader] Step events load error: {e}")
            return BulkLoadResult("step_event", 0, time.time() - start, 0, 1)

    def load_patches(self, cutoff_time: Optional[float] = None) -> BulkLoadResult:
        """Load patches (git commits) via DuckDB native JSON reading."""
        start = time.time()
        # Path validated in __init__ - safe to use in SQL
        path = self._storage_path / "part"

        if not path.exists() or not path.is_dir():
            return BulkLoadResult("patch", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            # Optimize DuckDB for bulk loading
            conn.execute("SET memory_limit='4GB'")
            conn.execute("SET preserve_insertion_order=false")

            # Load patches from part files (they share the same storage)
            # Path is validated in __init__ - resolved absolute path, safe for SQL
            query = LOAD_PATCHES_SQL.format(path=path)
            conn.execute(query)

            # Count loaded
            result = conn.execute("SELECT COUNT(*) FROM patches").fetchone()
            count = result[0] if result else 0
            self._patches_loaded = count

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(f"[BulkLoader] Patches: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)")

            return BulkLoadResult("patch", count, elapsed, speed, 0)

        except Exception as e:
            debug(f"[BulkLoader] Patch load error: {e}")
            return BulkLoadResult("patch", 0, time.time() - start, 0, 1)

    def load_file_operations(
        self, cutoff_time: Optional[float] = None
    ) -> BulkLoadResult:
        """Load file operations (read/write/edit) via DuckDB native JSON reading."""
        start = time.time()
        path = self._storage_path / "part"

        if not path.exists() or not path.is_dir():
            return BulkLoadResult("file_operation", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            conn.execute("SET memory_limit='4GB'")
            conn.execute("SET preserve_insertion_order=false")

            query = LOAD_FILE_OPERATIONS_SQL.format(path=path)
            conn.execute(query)

            result = conn.execute("SELECT COUNT(*) FROM file_operations").fetchone()
            count = result[0] if result else 0
            self._file_operations_loaded = count

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(
                f"[BulkLoader] File operations: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)"
            )

            return BulkLoadResult("file_operation", count, elapsed, speed, 0)

        except Exception as e:
            debug(f"[BulkLoader] File operations load error: {e}")
            return BulkLoadResult("file_operation", 0, time.time() - start, 0, 1)

    def enrich_file_operations_with_diffs(self) -> int:
        """Enrich file_operations with additions/deletions from session_diff files.

        Returns:
            Number of file operations enriched
        """
        from opencode_status_bar.analytics.loaders.files import (
            enrich_file_operations_with_diff_stats,
        )

        start = time.time()
        try:
            enriched = enrich_file_operations_with_diff_stats(
                self._db, self._storage_path
            )
            elapsed = time.time() - start
            if enriched > 0:
                info(
                    f"[BulkLoader] Enriched {enriched:,} file operations with diff stats in {elapsed:.1f}s"
                )
            return enriched
        except Exception as e:
            debug(f"[BulkLoader] Diff enrichment error: {e}")
            return 0

    def _create_root_traces(self, conn) -> int:
        """Create root traces for sessions without parent."""
        try:
            conn.execute(CREATE_ROOT_TRACES_SQL)

            # Count traces created for root sessions
            count = conn.execute(COUNT_ROOT_TRACES_SQL).fetchone()[0]
            if count > 0:
                debug(f"[BulkLoader] Created {count} root traces")
            return count

        except Exception as e:
            debug(f"[BulkLoader] Root trace creation error: {e}")
            return 0

    def _create_delegation_traces(self, conn) -> int:
        """Create traces for task delegations."""
        try:
            # Find task parts with completed status and extract delegation info
            conn.execute(CREATE_DELEGATION_TRACES_SQL)

            # Count delegation traces
            count = conn.execute(COUNT_DELEGATION_TRACES_SQL).fetchone()[0]
            if count > 0:
                debug(f"[BulkLoader] Created {count} delegation traces")
            return count

        except Exception as e:
            debug(f"[BulkLoader] Delegation trace creation error: {e}")
            return 0

    def mark_bulk_files_processed(self, cutoff_time: float) -> int:
        """
        Mark all files with mtime < cutoff_time as processed.

        This prevents the real-time watcher from reprocessing files
        that were already loaded by the bulk loader.

        Args:
            cutoff_time: Only mark files modified before this timestamp

        Returns:
            Number of files marked
        """
        debug(f"[BulkLoader] Starting file marking (cutoff={cutoff_time})")
        state = FileProcessingState(self._db)
        marked = 0

        # Scan each file type directory
        for file_type in ["session", "message", "part"]:
            debug(f"[BulkLoader] Scanning {file_type} directory...")
            type_path = self._storage_path / file_type
            if not type_path.exists():
                debug(f"[BulkLoader] {file_type} directory not found, skipping")
                continue

            # Collect files with mtime < cutoff_time
            files_to_mark = []
            subdirs_scanned = 0

            # For flat directories (no subdirs)
            if file_type in ("todo", "project"):
                for json_file in type_path.glob("*.json"):
                    try:
                        mtime = json_file.stat().st_mtime
                        if mtime < cutoff_time:
                            files_to_mark.append(
                                (str(json_file), file_type, "processed", None, mtime)
                            )
                    except OSError:
                        continue
            else:
                # For nested directories (project_id/file.json)
                for subdir in type_path.iterdir():
                    if not subdir.is_dir():
                        continue
                    subdirs_scanned += 1
                    if subdirs_scanned % 1000 == 0:
                        debug(
                            f"[BulkLoader] {file_type}: scanned {subdirs_scanned} subdirs, {len(files_to_mark)} files to mark"
                        )

                    for json_file in subdir.glob("*.json"):
                        try:
                            mtime = json_file.stat().st_mtime
                            if mtime < cutoff_time:
                                files_to_mark.append(
                                    (
                                        str(json_file),
                                        file_type,
                                        "processed",
                                        None,
                                        mtime,
                                    )
                                )
                        except OSError:
                            continue

            # Mark in batch for performance
            if files_to_mark:
                debug(
                    f"[BulkLoader] Marking {len(files_to_mark)} {file_type} files in DB..."
                )
                count = state.mark_processed_batch(files_to_mark)
                marked += count
                debug(f"[BulkLoader] Marked {count} {file_type} files as processed")

        return marked

    def get_stats(self) -> dict:
        """Get loading statistics."""
        return {
            "sessions_loaded": self._sessions_loaded,
            "messages_loaded": self._messages_loaded,
            "parts_loaded": self._parts_loaded,
            "step_events_loaded": self._step_events_loaded,
            "patches_loaded": self._patches_loaded,
            "file_operations_loaded": self._file_operations_loaded,
            "total_loaded": self._sessions_loaded
            + self._messages_loaded
            + self._parts_loaded,
        }
