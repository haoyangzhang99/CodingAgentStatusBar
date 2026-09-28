"""
DuckDB mock factory for isolated testing.

This module provides:
- In-memory DuckDB instances that are completely isolated
- Sample data generators matching the real schema
- Pre-populated database fixtures for different test scenarios

IMPORTANT: Tests must NEVER access the real DuckDB database at
~/.config/opencode-status-bar/analytics.duckdb. All test databases
use in-memory instances or temp directories.

Usage:
    from tests.mocks.duckdb import (
        create_test_analytics_db,
        populate_sample_parts,
        populate_sample_sessions,
        SampleDataGenerator,
    )
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4


def create_test_analytics_db(tmp_path: Optional[Path] = None):
    """Create an isolated AnalyticsDB instance for testing.

    Args:
        tmp_path: Optional path for the database file. If None, uses in-memory.
                 When provided, creates a unique DB file in that directory.

    Returns:
        AnalyticsDB instance with fresh schema, completely isolated from
        the production database.

    Example:
        db = create_test_analytics_db()  # In-memory
        db = create_test_analytics_db(tmp_path)  # File-based in tmp dir
    """
    from opencode_status_bar.analytics.db import AnalyticsDB

    if tmp_path is None:
        # Use in-memory database (most isolated)
        db_path = Path(":memory:")
    else:
        # Use unique file in tmp directory
        db_path = tmp_path / f"test_analytics_{uuid4().hex[:8]}.duckdb"

    db = AnalyticsDB(db_path=db_path)
    db.connect()
    return db


class SampleDataGenerator:
    """Generates sample data for testing with the real schema.

    This class provides methods to create realistic test data that
    matches the production schema. Use it for:
    - Testing security enrichment workflows
    - Testing query functionality
    - Integration tests

    Usage:
        gen = SampleDataGenerator()
        sessions = gen.create_sessions(count=3)
        parts = gen.create_parts_for_session("ses-001", tool_types=["bash", "read"])
    """

    def __init__(self):
        self._session_counter = 0
        self._message_counter = 0
        self._part_counter = 0

    def create_session(
        self,
        session_id: Optional[str] = None,
        project_name: str = "test-project",
        created_at: Optional[datetime] = None,
    ) -> dict:
        """Create a sample session record.

        Args:
            session_id: Optional custom ID. Auto-generated if not provided.
            project_name: Name of the project.
            created_at: Timestamp. Defaults to now.

        Returns:
            Dict with session data matching the sessions table schema.
        """
        self._session_counter += 1
        if session_id is None:
            session_id = f"ses_{self._session_counter:03d}"
        if created_at is None:
            created_at = datetime.now()

        return {
            "id": session_id,
            "project_id": f"proj_{self._session_counter:03d}",
            "directory": f"/home/user/{project_name}",
            "title": f"Session {self._session_counter}",
            "project_name": project_name,
            "created_at": created_at,
            "updated_at": created_at,
            "is_root": True,
        }

    def create_sessions(self, count: int = 3) -> list[dict]:
        """Create multiple sample sessions.

        Args:
            count: Number of sessions to create.

        Returns:
            List of session dicts.
        """
        return [self.create_session() for _ in range(count)]

    def create_message(
        self,
        session_id: str,
        message_id: Optional[str] = None,
        role: str = "assistant",
        created_at: Optional[datetime] = None,
    ) -> dict:
        """Create a sample message record.

        Args:
            session_id: Parent session ID.
            message_id: Optional custom ID.
            role: Message role (user, assistant, system).
            created_at: Timestamp.

        Returns:
            Dict with message data.
        """
        self._message_counter += 1
        if message_id is None:
            message_id = f"msg_{self._message_counter:03d}"
        if created_at is None:
            created_at = datetime.now()

        return {
            "id": message_id,
            "session_id": session_id,
            "parent_id": None,
            "role": role,
            "agent": "claude",
            "model_id": "claude-3-opus",
            "provider_id": "anthropic",
            "tokens_input": 100,
            "tokens_output": 200,
            "tokens_reasoning": 0,
            "tokens_cache_read": 50,
            "tokens_cache_write": 0,
            "created_at": created_at,
            "completed_at": created_at,
        }

    def create_part(
        self,
        session_id: str,
        message_id: str,
        tool_name: str,
        arguments: dict,
        part_id: Optional[str] = None,
        risk_score: Optional[int] = None,
        risk_level: Optional[str] = None,
        risk_reason: Optional[str] = None,
        security_enriched_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
    ) -> dict:
        """Create a sample part (tool call) record.

        Args:
            session_id: Parent session ID.
            message_id: Parent message ID.
            tool_name: Name of the tool (bash, read, write, edit, webfetch).
            arguments: Tool arguments as dict.
            part_id: Optional custom ID.
            risk_score: Security risk score (0-100).
            risk_level: Risk level (critical, high, medium, low).
            risk_reason: Reason for the risk assessment.
            security_enriched_at: When security enrichment was done.
            created_at: Creation timestamp.

        Returns:
            Dict with part data matching the parts table schema.
        """
        self._part_counter += 1
        if part_id is None:
            part_id = f"prt_{self._part_counter:03d}"
        if created_at is None:
            created_at = datetime.now()

        return {
            "id": part_id,
            "session_id": session_id,
            "message_id": message_id,
            "part_type": "tool",
            "tool_name": tool_name,
            "tool_status": "completed",
            "arguments": json.dumps(arguments),
            "content": None,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
            "mitre_techniques": "[]",
            "security_enriched_at": security_enriched_at,
            "created_at": created_at,
        }

    def create_bash_part(
        self,
        session_id: str,
        message_id: str,
        command: str,
        description: str = "test command",
        **kwargs,
    ) -> dict:
        """Create a bash tool part.

        Args:
            session_id: Parent session ID.
            message_id: Parent message ID.
            command: The bash command.
            description: Command description.
            **kwargs: Additional arguments for create_part.

        Returns:
            Dict with bash part data.
        """
        return self.create_part(
            session_id=session_id,
            message_id=message_id,
            tool_name="bash",
            arguments={"command": command, "description": description},
            **kwargs,
        )

    def create_read_part(
        self,
        session_id: str,
        message_id: str,
        file_path: str,
        **kwargs,
    ) -> dict:
        """Create a read tool part.

        Args:
            session_id: Parent session ID.
            message_id: Parent message ID.
            file_path: Path to the file being read.
            **kwargs: Additional arguments for create_part.

        Returns:
            Dict with read part data.
        """
        return self.create_part(
            session_id=session_id,
            message_id=message_id,
            tool_name="read",
            arguments={"filePath": file_path},
            **kwargs,
        )

    def create_write_part(
        self,
        session_id: str,
        message_id: str,
        file_path: str,
        content: str = "test content",
        **kwargs,
    ) -> dict:
        """Create a write tool part.

        Args:
            session_id: Parent session ID.
            message_id: Parent message ID.
            file_path: Path to the file being written.
            content: Content being written.
            **kwargs: Additional arguments for create_part.

        Returns:
            Dict with write part data.
        """
        return self.create_part(
            session_id=session_id,
            message_id=message_id,
            tool_name="write",
            arguments={"filePath": file_path, "content": content},
            **kwargs,
        )

    def create_edit_part(
        self,
        session_id: str,
        message_id: str,
        file_path: str,
        old_string: str = "old",
        new_string: str = "new",
        **kwargs,
    ) -> dict:
        """Create an edit tool part.

        Args:
            session_id: Parent session ID.
            message_id: Parent message ID.
            file_path: Path to the file being edited.
            old_string: String to replace.
            new_string: Replacement string.
            **kwargs: Additional arguments for create_part.

        Returns:
            Dict with edit part data.
        """
        return self.create_part(
            session_id=session_id,
            message_id=message_id,
            tool_name="edit",
            arguments={
                "filePath": file_path,
                "oldString": old_string,
                "newString": new_string,
            },
            **kwargs,
        )

    def create_webfetch_part(
        self,
        session_id: str,
        message_id: str,
        url: str,
        **kwargs,
    ) -> dict:
        """Create a webfetch tool part.

        Args:
            session_id: Parent session ID.
            message_id: Parent message ID.
            url: URL being fetched.
            **kwargs: Additional arguments for create_part.

        Returns:
            Dict with webfetch part data.
        """
        return self.create_part(
            session_id=session_id,
            message_id=message_id,
            tool_name="webfetch",
            arguments={"url": url, "format": "markdown"},
            **kwargs,
        )

    def create_glob_part(
        self,
        session_id: str,
        message_id: str,
        pattern: str = "**/*.py",
        **kwargs,
    ) -> dict:
        """Create a glob tool part (non-security tool).

        Args:
            session_id: Parent session ID.
            message_id: Parent message ID.
            pattern: Glob pattern.
            **kwargs: Additional arguments for create_part.

        Returns:
            Dict with glob part data.
        """
        return self.create_part(
            session_id=session_id,
            message_id=message_id,
            tool_name="glob",
            arguments={"pattern": pattern},
            **kwargs,
        )


def populate_sample_sessions(db, count: int = 3) -> list[str]:
    """Populate database with sample sessions.

    Args:
        db: AnalyticsDB instance.
        count: Number of sessions to create.

    Returns:
        List of created session IDs.
    """
    gen = SampleDataGenerator()
    conn = db.connect()
    session_ids = []

    for i in range(count):
        session = gen.create_session(
            created_at=datetime.now() - timedelta(days=count - i - 1)
        )
        session_ids.append(session["id"])

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, project_name,
                                  created_at, updated_at, is_root)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session["id"],
                session["project_id"],
                session["directory"],
                session["title"],
                session["project_name"],
                session["created_at"],
                session["updated_at"],
                session["is_root"],
            ],
        )

    return session_ids


def populate_sample_parts(
    db,
    session_id: str,
    include_enriched: bool = True,
    include_unenriched: bool = True,
    generator: Optional[SampleDataGenerator] = None,
) -> list[str]:
    """Populate database with sample parts for security testing.

    Creates a variety of parts with different:
    - Tool types: bash, read, write, edit, webfetch, glob
    - Risk levels: critical, high, medium, low
    - Enrichment states: enriched and unenriched

    Args:
        db: AnalyticsDB instance.
        session_id: Session to create parts for.
        include_enriched: Include parts that are already enriched.
        include_unenriched: Include parts without security enrichment.
        generator: Optional SampleDataGenerator to use (for unique IDs across calls).

    Returns:
        List of created part IDs.
    """
    gen = generator or SampleDataGenerator()
    conn = db.connect()
    now = datetime.now()
    part_ids = []

    # Create a unique message for the parts using session_id as base
    message = gen.create_message(session_id)
    # Ensure message ID is unique by including session suffix
    message["id"] = f"{message['id']}_{session_id[-3:]}"
    conn.execute(
        """
        INSERT INTO messages (id, session_id, role, created_at)
        VALUES (?, ?, ?, ?)
        """,
        [message["id"], session_id, message["role"], message["created_at"]],
    )

    # Sample parts data
    sample_parts = []

    if include_enriched:
        # Critical risk - bash rm command
        sample_parts.append(
            gen.create_bash_part(
                session_id,
                message["id"],
                command="rm -rf /tmp/important",
                risk_score=85,
                risk_level="critical",
                risk_reason="Recursive delete command",
                security_enriched_at=now,
            )
        )

        # High risk - read sensitive file
        sample_parts.append(
            gen.create_read_part(
                session_id,
                message["id"],
                file_path="/etc/passwd",
                risk_score=75,
                risk_level="high",
                risk_reason="System file access",
                security_enriched_at=now,
            )
        )

        # Medium risk - write to config file
        sample_parts.append(
            gen.create_write_part(
                session_id,
                message["id"],
                file_path="/home/user/.bashrc",
                risk_score=50,
                risk_level="medium",
                risk_reason="Config file modification",
                security_enriched_at=now,
            )
        )

        # Low risk - edit temp file
        sample_parts.append(
            gen.create_edit_part(
                session_id,
                message["id"],
                file_path="/tmp/test.txt",
                risk_score=10,
                risk_level="low",
                risk_reason="Temp file edit",
                security_enriched_at=now,
            )
        )

        # Critical risk - webfetch from suspicious URL
        sample_parts.append(
            gen.create_webfetch_part(
                session_id,
                message["id"],
                url="https://pastebin.com/raw/abc123",
                risk_score=90,
                risk_level="critical",
                risk_reason="Paste site URL",
                security_enriched_at=now,
            )
        )

    if include_unenriched:
        # Unenriched bash command
        sample_parts.append(
            gen.create_bash_part(
                session_id,
                message["id"],
                command="echo hello",
            )
        )

        # Unenriched read
        sample_parts.append(
            gen.create_read_part(
                session_id,
                message["id"],
                file_path="/home/user/project/README.md",
            )
        )

        # Unenriched webfetch
        sample_parts.append(
            gen.create_webfetch_part(
                session_id,
                message["id"],
                url="https://docs.python.org/3/",
            )
        )

    # Non-security tool (should never be enriched)
    sample_parts.append(
        gen.create_glob_part(
            session_id,
            message["id"],
            pattern="**/*.py",
        )
    )

    # Insert all parts
    for part in sample_parts:
        part_ids.append(part["id"])
        conn.execute(
            """
            INSERT INTO parts (
                id, session_id, message_id, part_type, tool_name, tool_status,
                arguments, risk_score, risk_level, risk_reason, mitre_techniques,
                security_enriched_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                part["id"],
                part["session_id"],
                part["message_id"],
                part["part_type"],
                part["tool_name"],
                part["tool_status"],
                part["arguments"],
                part["risk_score"],
                part["risk_level"],
                part["risk_reason"],
                part["mitre_techniques"],
                part["security_enriched_at"],
                part["created_at"],
            ],
        )

    return part_ids


def create_populated_test_db(tmp_path: Optional[Path] = None):
    """Create a test database with sample data pre-populated.

    Convenience function that creates an isolated database and populates
    it with sample sessions and parts for testing.

    Args:
        tmp_path: Optional path for database file.

    Returns:
        Tuple of (AnalyticsDB, session_ids, part_ids).
    """
    db = create_test_analytics_db(tmp_path)
    session_ids = populate_sample_sessions(db, count=2)

    # Use a shared generator to ensure unique IDs across all sessions
    gen = SampleDataGenerator()

    all_part_ids = []
    for session_id in session_ids:
        part_ids = populate_sample_parts(db, session_id, generator=gen)
        all_part_ids.extend(part_ids)

    return db, session_ids, all_part_ids
