"""Example of how to use SchemaBuilder with table definitions.

This demonstrates the refactored approach vs the old monolithic _create_schema().

BEFORE (db.py - 657 lines of SQL):
    def _create_schema(self):
        conn.execute(\"\"\"CREATE TABLE IF NOT EXISTS sessions (...)\"\"\")
        conn.execute(\"\"\"CREATE TABLE IF NOT EXISTS messages (...)\"\"\")
        ...
        conn.execute(\"\"\"CREATE INDEX IF NOT EXISTS idx_...\"\"\")
        ...

AFTER (structured approach):
    from .schemas import SchemaBuilder, TABLES

    builder = SchemaBuilder(conn)
    builder.create_all(TABLES)
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


def create_schema_new_way(conn: "duckdb.DuckDBPyConnection") -> None:
    """Example of using SchemaBuilder instead of raw SQL."""
    from .builder import SchemaBuilder
    from .tables import TABLES

    builder = SchemaBuilder(conn)
    builder.create_all(TABLES)


def create_schema_old_way(conn: "duckdb.DuckDBPyConnection") -> None:
    """Old monolithic approach (657 lines in db.py)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id VARCHAR PRIMARY KEY,
            ...
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id VARCHAR PRIMARY KEY,
            ...
        )
    """)
