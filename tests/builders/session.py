"""
SessionBuilder - Fluent builder for session test data.

Usage:
    # Create a dict
    session = SessionBuilder().with_tokens(1000, 500).build()

    # Insert into database
    session_id = SessionBuilder(db).with_title("Test").insert()

    # Create file in storage
    SessionBuilder().with_id("sess-001").write_file(storage_path)
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode_status_bar.analytics.db import AnalyticsDB


class SessionBuilder:
    """Fluent builder for creating session test data."""

    def __init__(self, db: AnalyticsDB | None = None):
        """Initialize builder with optional database connection.

        Args:
            db: Optional AnalyticsDB for insert operations
        """
        self._db = db
        self._reset()

    def _reset(self) -> None:
        """Reset builder to default values."""
        self._id = f"sess-{uuid.uuid4().hex[:8]}"
        self._title = "Test Session"
        self._directory = "/home/user/project"
        self._project_id = f"proj-{uuid.uuid4().hex[:8]}"
        self._parent_id: str | None = None
        self._created_at = datetime.now()
        self._updated_at = datetime.now()
        self._tokens_in = 1000
        self._tokens_out = 500
        self._tokens_cache_read = 0
        self._tokens_cache_write = 0
        self._additions = 0
        self._deletions = 0
        self._files_changed = 0

    # =========================================================================
    # Fluent setters
    # =========================================================================

    def with_id(self, session_id: str) -> SessionBuilder:
        """Set session ID."""
        self._id = session_id
        return self

    def with_title(self, title: str) -> SessionBuilder:
        """Set session title."""
        self._title = title
        return self

    def with_directory(self, directory: str) -> SessionBuilder:
        """Set working directory."""
        self._directory = directory
        return self

    def with_project(self, project_id: str) -> SessionBuilder:
        """Set project ID."""
        self._project_id = project_id
        return self

    def with_parent(self, parent_id: str) -> SessionBuilder:
        """Set parent session ID (for sub-sessions)."""
        self._parent_id = parent_id
        return self

    def with_tokens(
        self,
        input_tokens: int = 1000,
        output_tokens: int = 500,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> SessionBuilder:
        """Set token counts."""
        self._tokens_in = input_tokens
        self._tokens_out = output_tokens
        self._tokens_cache_read = cache_read
        self._tokens_cache_write = cache_write
        return self

    def with_timestamps(
        self,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> SessionBuilder:
        """Set timestamps."""
        if created_at:
            self._created_at = created_at
        if updated_at:
            self._updated_at = updated_at
        return self

    def with_git_stats(
        self,
        additions: int = 0,
        deletions: int = 0,
        files_changed: int = 0,
    ) -> SessionBuilder:
        """Set git statistics."""
        self._additions = additions
        self._deletions = deletions
        self._files_changed = files_changed
        return self

    def as_subsession(self, parent_id: str) -> SessionBuilder:
        """Configure as a sub-session with parent."""
        self._parent_id = parent_id
        return self

    # =========================================================================
    # Output methods
    # =========================================================================

    def build(self) -> dict[str, Any]:
        """Build session as a dictionary.

        Returns:
            Session data dict
        """
        data = {
            "id": self._id,
            "title": self._title,
            "directory": self._directory,
            "project_id": self._project_id,
            "created_at": self._created_at.isoformat(),
            "updated_at": self._updated_at.isoformat(),
            "tokens_in": self._tokens_in,
            "tokens_out": self._tokens_out,
            "tokens_cache_read": self._tokens_cache_read,
            "tokens_cache_write": self._tokens_cache_write,
            "additions": self._additions,
            "deletions": self._deletions,
            "files_changed": self._files_changed,
        }
        if self._parent_id:
            data["parent_id"] = self._parent_id
        return data

    def build_json(self) -> dict[str, Any]:
        """Build session as JSON file format (OpenCode storage format).

        Returns:
            Session data in OpenCode JSON format
        """
        created_ts = int(self._created_at.timestamp() * 1000)
        updated_ts = int(self._updated_at.timestamp() * 1000)

        return {
            "id": self._id,
            "projectID": self._project_id,
            "directory": self._directory,
            "title": self._title,
            "parentID": self._parent_id,
            "time": {"created": created_ts, "updated": updated_ts},
        }

    def insert(self) -> str:
        """Insert session into database.

        Returns:
            Session ID

        Raises:
            ValueError: If no database connection
        """
        if not self._db:
            raise ValueError("No database connection. Pass db to SessionBuilder(db)")

        conn = self._db.connect()
        conn.execute(
            """
            INSERT INTO sessions (
                id, directory, title, created_at, updated_at,
                parent_id, project_id, additions, deletions, files_changed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                self._id,
                self._directory,
                self._title,
                self._created_at,
                self._updated_at,
                self._parent_id,
                self._project_id,
                self._additions,
                self._deletions,
                self._files_changed,
            ],
        )
        return self._id

    def write_file(self, storage_path: Path) -> Path:
        """Write session JSON file to storage.

        Args:
            storage_path: Base storage path

        Returns:
            Path to created session file
        """
        session_dir = storage_path / "sessions" / self._id
        session_dir.mkdir(parents=True, exist_ok=True)

        session_file = session_dir / "session.json"
        session_file.write_text(json.dumps(self.build_json()))

        return session_file

    @property
    def id(self) -> str:
        """Get the session ID."""
        return self._id
