"""
PartBuilder - Fluent builder for part test data.

Usage:
    # Create a text part
    part = PartBuilder().as_text("Hello world").build()

    # Create a tool part
    part = PartBuilder().as_tool("bash").with_arguments({"command": "ls"}).insert()

    # Create a file part (image)
    part = PartBuilder().as_file("image.png", "image/png").with_file_url(data_url).insert()
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode_status_bar.analytics.db import AnalyticsDB


class PartBuilder:
    """Fluent builder for creating part test data."""

    def __init__(self, db: AnalyticsDB | None = None):
        """Initialize builder with optional database connection."""
        self._db = db
        self._reset()

    def _reset(self) -> None:
        """Reset builder to default values."""
        self._id = f"part-{uuid.uuid4().hex[:8]}"
        self._session_id = f"sess-{uuid.uuid4().hex[:8]}"
        self._message_id = f"msg-{uuid.uuid4().hex[:8]}"
        self._part_type = "text"
        self._content: str | None = None
        self._created_at = datetime.now()

        # Tool-specific fields
        self._tool_name: str | None = None
        self._tool_status: str | None = None
        self._arguments: str | None = None
        self._duration_ms: int | None = None
        self._tool_title: str | None = None
        self._result_summary: str | None = None
        self._cost: float | None = None
        self._tokens_input: int | None = None
        self._tokens_output: int | None = None

        # File-specific fields
        self._file_name: str | None = None
        self._file_mime: str | None = None
        self._file_url: str | None = None

    # =========================================================================
    # Fluent setters - Identity
    # =========================================================================

    def with_id(self, part_id: str) -> PartBuilder:
        """Set part ID."""
        self._id = part_id
        return self

    def for_session(self, session_id: str) -> PartBuilder:
        """Set session ID."""
        self._session_id = session_id
        return self

    def for_message(self, message_id: str) -> PartBuilder:
        """Set message ID."""
        self._message_id = message_id
        return self

    def at_time(self, timestamp: datetime) -> PartBuilder:
        """Set creation timestamp."""
        self._created_at = timestamp
        return self

    # =========================================================================
    # Fluent setters - Part Types
    # =========================================================================

    def as_text(self, content: str) -> PartBuilder:
        """Configure as text part."""
        self._part_type = "text"
        self._content = content
        return self

    def as_tool(self, tool_name: str, status: str = "completed") -> PartBuilder:
        """Configure as tool part."""
        self._part_type = "tool"
        self._tool_name = tool_name
        self._tool_status = status
        return self

    def as_file(
        self, filename: str | None = None, mime_type: str | None = None
    ) -> PartBuilder:
        """Configure as file part (image, attachment)."""
        self._part_type = "file"
        self._file_name = filename
        self._file_mime = mime_type
        return self

    # =========================================================================
    # Fluent setters - Tool fields
    # =========================================================================

    def with_arguments(self, args: dict | str) -> PartBuilder:
        """Set tool arguments (dict or JSON string)."""
        import json

        self._arguments = json.dumps(args) if isinstance(args, dict) else args
        return self

    def with_content(self, content: str) -> PartBuilder:
        """Set part content (tool output or text)."""
        self._content = content
        return self

    def with_duration(self, duration_ms: int) -> PartBuilder:
        """Set tool execution duration in milliseconds."""
        self._duration_ms = duration_ms
        return self

    def with_tool_title(self, title: str) -> PartBuilder:
        """Set human-readable tool title."""
        self._tool_title = title
        return self

    def with_result_summary(self, summary: str) -> PartBuilder:
        """Set result summary."""
        self._result_summary = summary
        return self

    def with_cost(self, cost: float) -> PartBuilder:
        """Set tool cost."""
        self._cost = cost
        return self

    def with_tokens(self, input_tokens: int, output_tokens: int) -> PartBuilder:
        """Set token counts."""
        self._tokens_input = input_tokens
        self._tokens_output = output_tokens
        return self

    # =========================================================================
    # Fluent setters - File fields
    # =========================================================================

    def with_file_url(self, data_url: str) -> PartBuilder:
        """Set file data URL (base64 encoded)."""
        self._file_url = data_url
        return self

    # =========================================================================
    # Output methods
    # =========================================================================

    def build(self) -> dict[str, Any]:
        """Build part as a dictionary."""
        data: dict[str, Any] = {
            "id": self._id,
            "session_id": self._session_id,
            "message_id": self._message_id,
            "part_type": self._part_type,
            "created_at": self._created_at.isoformat(),
        }

        if self._content:
            data["content"] = self._content

        # Tool fields
        if self._tool_name:
            data["tool_name"] = self._tool_name
        if self._tool_status:
            data["tool_status"] = self._tool_status
        if self._arguments:
            data["arguments"] = self._arguments
        if self._duration_ms is not None:
            data["duration_ms"] = self._duration_ms
        if self._tool_title:
            data["tool_title"] = self._tool_title
        if self._result_summary:
            data["result_summary"] = self._result_summary
        if self._cost is not None:
            data["cost"] = self._cost
        if self._tokens_input is not None:
            data["tokens_input"] = self._tokens_input
        if self._tokens_output is not None:
            data["tokens_output"] = self._tokens_output

        # File fields
        if self._file_name:
            data["file_name"] = self._file_name
        if self._file_mime:
            data["file_mime"] = self._file_mime
        if self._file_url:
            data["file_url"] = self._file_url

        return data

    def insert(self) -> str:
        """Insert part into database.

        Returns:
            Part ID

        Raises:
            ValueError: If no database connection
        """
        if not self._db:
            raise ValueError("No database connection. Pass db to PartBuilder(db)")

        conn = self._db.connect()

        # Build column/value lists dynamically
        columns = ["id", "session_id", "message_id", "part_type", "created_at"]
        values: list[Any] = [
            self._id,
            self._session_id,
            self._message_id,
            self._part_type,
            self._created_at,
        ]

        optional_fields = [
            ("content", self._content),
            ("tool_name", self._tool_name),
            ("tool_status", self._tool_status),
            ("arguments", self._arguments),
            ("duration_ms", self._duration_ms),
            ("tool_title", self._tool_title),
            ("result_summary", self._result_summary),
            ("cost", self._cost),
            ("tokens_input", self._tokens_input),
            ("tokens_output", self._tokens_output),
            ("file_name", self._file_name),
            ("file_mime", self._file_mime),
            ("file_url", self._file_url),
        ]

        for col, val in optional_fields:
            if val is not None:
                columns.append(col)
                values.append(val)

        placeholders = ", ".join(["?"] * len(columns))
        column_names = ", ".join(columns)

        conn.execute(
            f"INSERT INTO parts ({column_names}) VALUES ({placeholders})",
            values,
        )
        return self._id

    @property
    def id(self) -> str:
        """Get the part ID."""
        return self._id

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self._session_id
