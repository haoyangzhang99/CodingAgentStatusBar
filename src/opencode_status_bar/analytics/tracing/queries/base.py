"""Base class for session query modules.

Provides common functionality and database access for all query classes.
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import TracingConfig
    import duckdb


class BaseSessionQueries:
    """Base class providing database access and common utilities.

    All session query classes inherit from this to get:
    - Database connection access via _conn property
    - Config access via _config attribute
    - Common helper methods
    """

    def __init__(self, conn: "duckdb.DuckDBPyConnection", config: "TracingConfig"):
        """Initialize with database connection and config.

        Args:
            conn: DuckDB connection instance
            config: Tracing configuration with cost models
        """
        self._conn_instance = conn
        self._config = config

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get database connection."""
        return self._conn_instance

    def _empty_response(self, session_id: str) -> dict:
        """Generate empty response for missing session.

        Args:
            session_id: The session ID being queried

        Returns:
            Dict with error metadata
        """
        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
                "error": "Session not found",
            },
            "summary": {},
            "details": {},
            "charts": {},
        }

    def _get_session_info(self, session_id: str) -> dict | None:
        """Get basic session information.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with session fields or None if not found
        """
        result = self._conn.execute(
            """
            SELECT 
                id, title, directory, project_path, status,
                created_at, additions, deletions
            FROM sessions
            WHERE id = ?
            """,
            [session_id],
        ).fetchone()

        if not result:
            return None

        return {
            "id": result[0],
            "title": result[1],
            "directory": result[2],
            "project_path": result[3],
            "status": result[4],
            "created_at": result[5],
            "additions": result[6],
            "deletions": result[7],
        }
