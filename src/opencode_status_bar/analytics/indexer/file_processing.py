"""
File processing state management for race condition prevention.

Tracks which files have been processed to prevent duplicates between
bulk loading and real-time watching phases.

This is separate from file_index (which tracks file changes) and focuses
on preventing race conditions during the bulk->realtime handoff.
"""

import threading
from pathlib import Path
from typing import Optional

from ..db import AnalyticsDB



class FileProcessingState:
    """
    Manages file processing state to prevent race conditions.

    Tracks files processed by bulk loader so that real-time watcher
    can skip them. Thread-safe for concurrent access.

    Usage:
        state = FileProcessingState(db)

        # Check if file needs processing
        if not state.is_already_processed(file_path):
            process_file(file_path)
            state.mark_processed(file_path, "session", "processed")
    """

    def __init__(self, db: AnalyticsDB):
        """
        Initialize file processing state.

        Args:
            db: Analytics database instance
        """
        self._db = db
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create file_processing_state table if not exists."""
        conn = self._db.connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_processing_state (
                file_path VARCHAR PRIMARY KEY,
                file_type VARCHAR NOT NULL,
                last_modified DOUBLE,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'processed'
            )
        """)

        # Indexes for performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_processing_type
            ON file_processing_state(file_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_processing_status
            ON file_processing_state(status)
        """)


    def is_already_processed(self, file_path: str | Path) -> bool:
        """
        Check if a file has already been processed.

        Returns True for any status (processed, failed, skipped) since we don't want to
        retry files that have already been attempted.

        Args:
            file_path: Path to the file

        Returns:
            True if file was already processed (any status), False otherwise
        """
        with self._lock:
            conn = self._db.connect()
            result = conn.execute(
                """
                SELECT 1 FROM file_processing_state
                WHERE file_path = ?
                """,
                [str(file_path)],
            ).fetchone()
            return result is not None

    def mark_processed(
        self,
        file_path: str | Path,
        file_type: str,
        status: str = "processed",
        checksum: Optional[str] = None,
        last_modified: Optional[float] = None,
    ) -> None:
        """
        Mark a file as processed.

        Args:
            file_path: Path to the file
            file_type: Type of file (session, message, part, etc.)
            status: Processing status ('processed', 'failed', 'skipped')
            checksum: Optional file checksum for verification
            last_modified: Optional last modified timestamp
        """
        with self._lock:
            conn = self._db.connect()
            conn.execute(
                """
                INSERT OR REPLACE INTO file_processing_state
                (file_path, file_type, last_modified, processed_at, checksum, status)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
                """,
                [str(file_path), file_type, last_modified, checksum, status],
            )

    def mark_processed_batch(
        self,
        files: list[tuple[str, str, str, Optional[str], Optional[float]]],
    ) -> int:
        """
        Mark multiple files as processed in a single batch.

        Much faster than calling mark_processed() for each file individually.

        Args:
            files: List of (file_path, file_type, status, checksum, last_modified) tuples

        Returns:
            Number of files marked
        """
        if not files:
            return 0

        with self._lock:
            conn = self._db.connect()
            conn.executemany(
                """
                INSERT OR REPLACE INTO file_processing_state
                (file_path, file_type, status, checksum, last_modified)
                VALUES (?, ?, ?, ?, ?)
                """,
                files,
            )
            return len(files)

    def get_file_info(self, file_path: str | Path) -> Optional[dict]:
        """
        Get processing info for a file.

        Args:
            file_path: Path to the file

        Returns:
            Dict with file info, or None if not found
        """
        with self._lock:
            conn = self._db.connect()
            result = conn.execute(
                """
                SELECT file_path, file_type, last_modified, processed_at, checksum, status
                FROM file_processing_state
                WHERE file_path = ?
                """,
                [str(file_path)],
            ).fetchone()

            if result is None:
                return None

            return {
                "file_path": result[0],
                "file_type": result[1],
                "last_modified": result[2],
                "processed_at": result[3],
                "checksum": result[4],
                "status": result[5],
            }

    def get_stats(self) -> dict:
        """
        Get processing statistics.

        Returns:
            Dict with counts by type and status
        """
        with self._lock:
            conn = self._db.connect()

            # Total count
            total_result = conn.execute(
                "SELECT COUNT(*) FROM file_processing_state"
            ).fetchone()
            total = total_result[0] if total_result else 0

            # Count by status
            status_counts = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM file_processing_state
                GROUP BY status
            """).fetchall()

            # Count by type
            type_counts = conn.execute("""
                SELECT file_type, COUNT(*) as count
                FROM file_processing_state
                GROUP BY file_type
            """).fetchall()

            return {
                "total_files": total,
                "by_status": {row[0]: row[1] for row in status_counts if row},
                "by_type": {row[0]: row[1] for row in type_counts if row},
            }

    def clear(self) -> None:
        """Clear all processing state (for testing/reset)."""
        with self._lock:
            conn = self._db.connect()
            conn.execute("DELETE FROM file_processing_state")


# Convenience functions for backward compatibility
def is_already_processed(db: AnalyticsDB, file_path: str | Path) -> bool:
    """Check if a file has already been processed."""
    state = FileProcessingState(db)
    return state.is_already_processed(file_path)


def mark_processed(
    db: AnalyticsDB,
    file_path: str | Path,
    file_type: str,
    status: str = "processed",
    checksum: Optional[str] = None,
    last_modified: Optional[float] = None,
) -> None:
    """Mark a file as processed."""
    state = FileProcessingState(db)
    state.mark_processed(file_path, file_type, status, checksum, last_modified)


def mark_processed_batch(
    db: AnalyticsDB,
    files: list[tuple[str, str, str, Optional[str], Optional[float]]],
) -> int:
    """Mark multiple files as processed in batch."""
    state = FileProcessingState(db)
    return state.mark_processed_batch(files)
