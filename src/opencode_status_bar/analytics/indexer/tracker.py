"""
File change tracker for efficient indexing.

Uses mtime + size comparison to detect file changes and skip
already-indexed files. Persists tracking info in a file_index table.

Performance:
- O(1) lookup per file via DB index
- Avoids re-reading unchanged files
- Persists across restarts
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..db import AnalyticsDB



@dataclass
class FileInfo:
    """File metadata for change detection."""

    file_path: str
    file_type: str  # session, message, part, todo, project
    mtime: float
    size: int
    record_id: Optional[str] = None
    indexed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class FileTracker:
    """Tracks indexed files to detect changes.

    Uses mtime + size for fast change detection without reading file contents.
    Persists tracking info in the database for cross-restart persistence.
    """

    def __init__(self, db: AnalyticsDB):
        """Initialize the file tracker.

        Args:
            db: Database instance for persisting file index
        """
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the file_index table if it doesn't exist."""
        conn = self._db.connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                file_path VARCHAR PRIMARY KEY,
                file_type VARCHAR NOT NULL,
                mtime DOUBLE NOT NULL,
                size INTEGER NOT NULL,
                record_id VARCHAR,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_message VARCHAR
            )
        """)
        # Indexes for efficient queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_index_type
            ON file_index(file_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_index_mtime
            ON file_index(mtime DESC)
        """)

    def needs_indexing(self, path: Path | str) -> bool:
        """Check if a file needs (re)indexing based on mtime and size.

        Fast check that avoids reading file contents.

        Args:
            path: Path to the file to check (accepts Path or str)

        Returns:
            True if file needs indexing (new or changed), False otherwise
        """
        # Convert str to Path for compatibility
        path = Path(path) if isinstance(path, str) else path

        if not path.exists():
            return False

        try:
            stat = path.stat()
            current_mtime = stat.st_mtime
            current_size = stat.st_size
        except OSError:
            return False

        conn = self._db.connect()
        result = conn.execute(
            """
            SELECT mtime, size FROM file_index
            WHERE file_path = ?
            """,
            [str(path)],
        ).fetchone()

        if result is None:
            # File not in index -> needs indexing
            return True

        stored_mtime, stored_size = result
        # Changed if mtime OR size differs
        return current_mtime != stored_mtime or current_size != stored_size

    def get_file_info(self, path: Path) -> Optional[FileInfo]:
        """Get stored info for a file.

        Args:
            path: Path to the file

        Returns:
            FileInfo if file is in index, None otherwise
        """
        conn = self._db.connect()
        result = conn.execute(
            """
            SELECT file_path, file_type, mtime, size, record_id, indexed_at, error_message
            FROM file_index WHERE file_path = ?
            """,
            [str(path)],
        ).fetchone()

        if result is None:
            return None

        return FileInfo(
            file_path=result[0],
            file_type=result[1],
            mtime=result[2],
            size=result[3],
            record_id=result[4],
            indexed_at=result[5],
            error_message=result[6],
        )

    def mark_indexed(
        self,
        path: Path,
        file_type: str,
        record_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a file as indexed with its current mtime and size.

        Args:
            path: Path to the file
            file_type: Type of file (session, message, part, todo, project)
            record_id: ID of the created/updated record
            error_message: Error message if indexing failed
        """
        try:
            stat = path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            return

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO file_index
            (file_path, file_type, mtime, size, record_id, indexed_at, error_message)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
            [str(path), file_type, mtime, size, record_id, error_message],
        )

    def mark_error(self, path: Path, file_type: str, error: str) -> None:
        """Mark a file as having an indexing error.

        The file's mtime/size are still stored so we don't retry unchanged
        files that consistently fail.

        Args:
            path: Path to the file
            file_type: Type of file
            error: Error message describing the failure
        """
        self.mark_indexed(path, file_type, record_id=None, error_message=error)

    def mark_indexed_batch(
        self,
        items: list[tuple[Path, str, str | None]],
    ) -> int:
        """Mark multiple files as indexed in a single batch INSERT.

        Much faster than individual mark_indexed calls for large batches.

        Args:
            items: List of (path, file_type, record_id) tuples

        Returns:
            Number of files successfully marked
        """
        if not items:
            return 0

        records = []
        for path, file_type, record_id in items:
            try:
                stat = path.stat()
                records.append(
                    (
                        str(path),
                        file_type,
                        stat.st_mtime,
                        stat.st_size,
                        record_id,
                        None,  # error_message
                    )
                )
            except OSError:
                continue

        if not records:
            return 0

        conn = self._db.connect()
        conn.executemany(
            """
            INSERT OR REPLACE INTO file_index
            (file_path, file_type, mtime, size, record_id, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        return len(records)

    def get_unindexed_files(
        self,
        directory: Path,
        file_type: str,
        limit: int = 100,
        max_mtime: Optional[float] = None,
        only_new: bool = False,
    ) -> list[Path]:
        """Get files not yet indexed or changed since last indexing.

        Efficiently finds files needing indexing by comparing filesystem
        with database index.

        Args:
            max_mtime: If provided, only include files with mtime <= this value.
                      Used by backfill to ignore files created after indexer start.
            only_new: If True, only return files that have NEVER been indexed.
                     Ignores modified files. Used by backfill to avoid
                     re-processing files that the watcher should handle.

        Args:
            directory: Directory to scan
            file_type: Type of files to look for
            limit: Maximum number of files to return

        Returns:
            List of paths needing indexing, sorted by mtime DESC (recent first)
        """
        if not directory.exists():
            return []

        # Collect all JSON files with their mtime
        files_with_mtime: list[tuple[float, Path]] = []

        if file_type in ("todo", "project"):
            # Flat directory (no subdirs)
            for json_file in directory.glob("*.json"):
                try:
                    mtime = json_file.stat().st_mtime
                    files_with_mtime.append((mtime, json_file))
                except OSError:
                    continue
        else:
            # Nested directory structure (project_id/file.json)
            for subdir in directory.iterdir():
                if not subdir.is_dir():
                    continue
                for json_file in subdir.glob("*.json"):
                    try:
                        mtime = json_file.stat().st_mtime
                        files_with_mtime.append((mtime, json_file))
                    except OSError:
                        continue

        # Filter by max_mtime if provided (backfill cutoff)
        if max_mtime is not None:
            files_with_mtime = [(m, p) for m, p in files_with_mtime if m <= max_mtime]

        # Sort by mtime DESC (most recent first)
        files_with_mtime.sort(key=lambda x: x[0], reverse=True)

        # Load ALL indexed files for this type in ONE query (much faster than per-file)
        conn = self._db.connect()
        indexed_files = {}
        try:
            rows = conn.execute(
                """
                SELECT file_path, mtime, size FROM file_index
                WHERE file_type = ?
                """,
                [file_type],
            ).fetchall()
            for row in rows:
                indexed_files[row[0]] = (row[1], row[2])
        finally:
            pass  # Connection managed by pool

        # Filter to only files needing indexing (in-memory comparison)
        unindexed: list[Path] = []
        for mtime, path in files_with_mtime:
            if len(unindexed) >= limit:
                break
            path_str = str(path)
            if path_str not in indexed_files:
                # New file - needs indexing
                unindexed.append(path)
            elif not only_new:
                # Check if changed (only if we're not in "only_new" mode)
                # In only_new mode, we skip modified files - watcher handles those
                stored_mtime, stored_size = indexed_files[path_str]
                try:
                    current_size = path.stat().st_size
                    if mtime != stored_mtime or current_size != stored_size:
                        unindexed.append(path)
                except OSError:
                    continue

        return unindexed

    def get_stats(self) -> dict:
        """Get indexing statistics.

        Returns:
            Dict with counts by file type and error stats
        """
        conn = self._db.connect()

        # Count by type
        type_counts = conn.execute("""
            SELECT file_type, COUNT(*) as count
            FROM file_index
            GROUP BY file_type
        """).fetchall()

        # Count errors
        error_result = conn.execute("""
            SELECT COUNT(*) FROM file_index
            WHERE error_message IS NOT NULL
        """).fetchone()
        error_count = error_result[0] if error_result else 0

        # Total count
        total_result = conn.execute("SELECT COUNT(*) FROM file_index").fetchone()
        total = total_result[0] if total_result else 0

        return {
            "total_files": total,
            "by_type": {row[0]: row[1] for row in type_counts if row},
            "errors": error_count,
        }

    def clear(self) -> None:
        """Clear all tracking data (for testing/reset)."""
        conn = self._db.connect()
        conn.execute("DELETE FROM file_index")
