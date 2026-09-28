"""Database utilities with context managers."""

from contextlib import contextmanager
from typing import Generator
import sqlite3


@contextmanager
def db_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database connections.

    Args:
        db_path: Path to the SQLite database

    Yields:
        Database connection that auto-closes
    """
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def db_cursor(conn: sqlite3.Connection) -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for database cursor with auto-commit.

    Args:
        conn: Database connection

    Yields:
        Database cursor that auto-commits on success
    """
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
