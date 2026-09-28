"""
MessageBuilder - Fluent builder for message test data.

Usage:
    # Create a dict
    message = MessageBuilder().with_agent("executor").build()

    # Insert into database
    message_id = MessageBuilder(db).for_session("sess-001").insert()

    # Create file in storage
    MessageBuilder().with_id("msg-001").write_file(storage_path)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode_status_bar.analytics.db import AnalyticsDB


class MessageBuilder:
    """Fluent builder for creating message test data."""

    def __init__(self, db: AnalyticsDB | None = None):
        """Initialize builder with optional database connection.

        Args:
            db: Optional AnalyticsDB for insert operations
        """
        self._db = db
        self._reset()

    def _reset(self) -> None:
        """Reset builder to default values."""
        self._id = f"msg-{uuid.uuid4().hex[:8]}"
        self._session_id = f"sess-{uuid.uuid4().hex[:8]}"
        self._parent_id: str | None = None
        self._role = "assistant"
        self._agent = "main"
        self._model_id = "claude-sonnet"
        self._provider_id = "anthropic"
        self._created_at = datetime.now()
        self._completed_at: datetime | None = None
        self._tokens_input = 100
        self._tokens_output = 50
        self._tokens_reasoning = 0
        self._tokens_cache_read = 0
        self._tokens_cache_write = 0
        self._cost = 0.0
        self._content: str | None = None
        self._summary: dict | None = None

    # =========================================================================
    # Fluent setters
    # =========================================================================

    def with_id(self, message_id: str) -> MessageBuilder:
        """Set message ID."""
        self._id = message_id
        return self

    def for_session(self, session_id: str) -> MessageBuilder:
        """Set session ID."""
        self._session_id = session_id
        return self

    def with_parent(self, parent_id: str) -> MessageBuilder:
        """Set parent message ID."""
        self._parent_id = parent_id
        return self

    def with_role(self, role: str) -> MessageBuilder:
        """Set message role (user, assistant, system)."""
        self._role = role
        return self

    def with_agent(self, agent: str) -> MessageBuilder:
        """Set agent type."""
        self._agent = agent
        return self

    def with_model(
        self, model_id: str, provider_id: str = "anthropic"
    ) -> MessageBuilder:
        """Set model information."""
        self._model_id = model_id
        self._provider_id = provider_id
        return self

    def with_tokens(
        self,
        input_tokens: int = 100,
        output_tokens: int = 50,
        reasoning_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> MessageBuilder:
        """Set token counts."""
        self._tokens_input = input_tokens
        self._tokens_output = output_tokens
        self._tokens_reasoning = reasoning_tokens
        self._tokens_cache_read = cache_read
        self._tokens_cache_write = cache_write
        return self

    def with_cost(self, cost: float) -> MessageBuilder:
        """Set message cost."""
        self._cost = cost
        return self

    def with_timestamps(
        self,
        created_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> MessageBuilder:
        """Set timestamps."""
        if created_at:
            self._created_at = created_at
        if completed_at:
            self._completed_at = completed_at
        return self

    def with_content(self, content: str) -> MessageBuilder:
        """Set message content."""
        self._content = content
        return self

    def with_summary(self, summary: dict) -> MessageBuilder:
        """Set message summary."""
        self._summary = summary
        return self

    def as_user(self) -> MessageBuilder:
        """Configure as user message."""
        self._role = "user"
        return self

    def as_assistant(self, agent: str = "main") -> MessageBuilder:
        """Configure as assistant message."""
        self._role = "assistant"
        self._agent = agent
        return self

    # =========================================================================
    # Output methods
    # =========================================================================

    def build(self) -> dict[str, Any]:
        """Build message as a dictionary.

        Returns:
            Message data dict
        """
        data = {
            "id": self._id,
            "session_id": self._session_id,
            "role": self._role,
            "agent": self._agent,
            "model_id": self._model_id,
            "provider_id": self._provider_id,
            "created_at": self._created_at.isoformat(),
            "tokens_input": self._tokens_input,
            "tokens_output": self._tokens_output,
            "tokens_reasoning": self._tokens_reasoning,
            "tokens_cache_read": self._tokens_cache_read,
            "tokens_cache_write": self._tokens_cache_write,
            "cost": self._cost,
        }
        if self._parent_id:
            data["parent_id"] = self._parent_id
        if self._completed_at:
            data["completed_at"] = self._completed_at.isoformat()
        if self._content:
            data["content"] = self._content
        if self._summary:
            data["summary"] = self._summary
        return data

    def build_json(self) -> dict[str, Any]:
        """Build message as JSON file format (OpenCode storage format).

        Returns:
            Message data in OpenCode JSON format
        """
        created_ts = int(self._created_at.timestamp() * 1000)
        completed_ts = (
            int(self._completed_at.timestamp() * 1000)
            if self._completed_at
            else created_ts + 1000
        )

        data: dict[str, Any] = {
            "id": self._id,
            "sessionID": self._session_id,
            "parentID": self._parent_id,
            "role": self._role,
            "agent": self._agent,
            "modelID": self._model_id,
            "providerID": self._provider_id,
            "tokens": {
                "input": self._tokens_input,
                "output": self._tokens_output,
                "reasoning": self._tokens_reasoning,
                "cache": {
                    "read": self._tokens_cache_read,
                    "write": self._tokens_cache_write,
                },
            },
            "time": {"created": created_ts, "completed": completed_ts},
        }
        if self._summary:
            data["summary"] = self._summary
        return data

    def insert(self) -> str:
        """Insert message into database.

        Returns:
            Message ID

        Raises:
            ValueError: If no database connection
        """
        if not self._db:
            raise ValueError("No database connection. Pass db to MessageBuilder(db)")

        conn = self._db.connect()
        conn.execute(
            """
            INSERT INTO messages (
                id, session_id, role, agent, created_at,
                tokens_input, tokens_output, cost, model_id, provider_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                self._id,
                self._session_id,
                self._role,
                self._agent,
                self._created_at,
                self._tokens_input,
                self._tokens_output,
                self._cost,
                self._model_id,
                self._provider_id,
            ],
        )
        return self._id

    def write_file(self, storage_path: Path) -> Path:
        """Write message JSON file to storage.

        Args:
            storage_path: Base storage path

        Returns:
            Path to created message file
        """
        message_dir = storage_path / "messages" / self._session_id
        message_dir.mkdir(parents=True, exist_ok=True)

        message_file = message_dir / f"{self._id}.json"
        message_file.write_text(json.dumps(self.build_json()))

        return message_file

    @property
    def id(self) -> str:
        """Get the message ID."""
        return self._id

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self._session_id
