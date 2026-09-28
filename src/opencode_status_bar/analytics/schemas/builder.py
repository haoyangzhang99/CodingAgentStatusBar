"""Schema builder for creating and managing database schema.

Provides methods to build tables and indexes from structured definitions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb
    from .tables import TableDef, IndexDef


class SchemaBuilder:
    """Builds database schema from table definitions."""

    def __init__(self, conn: "duckdb.DuckDBPyConnection"):
        self.conn = conn

    def create_all(self, tables: list["TableDef"]) -> None:
        """Create all tables and indexes.

        Args:
            tables: List of table definitions
        """
        for table in tables:
            self.create_table(table)

        for table in tables:
            self.create_indexes(table)

    def create_table(self, table: "TableDef") -> None:
        """Create a single table from definition.

        Args:
            table: Table definition with columns
        """
        table_name = table["name"]
        columns = table["columns"]

        column_defs = []
        for col in columns:
            col_def = f"{col['name']} {col['type']}"
            if col["constraints"]:
                col_def += f" {col['constraints']}"
            column_defs.append(col_def)

        sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {", ".join(column_defs)}
            )
        """
        self.conn.execute(sql)

    def create_indexes(self, table: "TableDef") -> None:
        """Create indexes for a table.

        Args:
            table: Table definition with indexes
        """
        for index in table.get("indexes", []):
            self.create_index(index)

    def create_index(self, index: "IndexDef") -> None:
        """Create a single index.

        Args:
            index: Index definition
        """
        index_name = index["name"]
        table_name = index["table"]
        columns = index["columns"]

        sql = f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {table_name}({", ".join(columns)})
        """
        self.conn.execute(sql)
