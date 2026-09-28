"""Database schema management modules.

Provides structured table definitions and schema building.
"""

from .builder import SchemaBuilder
from .tables import TABLES, TABLE_DEFINITIONS

__all__ = ["SchemaBuilder", "TABLES", "TABLE_DEFINITIONS"]
