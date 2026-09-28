"""
File handlers for processing different file types in realtime mode.

Each handler encapsulates the logic for parsing and persisting a specific
file type (session, message, part). This follows the Strategy pattern and
improves testability by allowing handlers to be mocked independently.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from ..path_matcher import DiffPathMatcher, build_diff_stats_map

if TYPE_CHECKING:
    from .parsers import FileParser
    from .trace_builder import TraceBuilder


class FileHandler(ABC):
    """
    Abstract base class for file handlers.

    Each handler processes a specific file type and persists it to the database.
    """

    @abstractmethod
    def process(
        self,
        file_path: Path,
        raw_data: Any,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        pass


class SessionHandler(FileHandler):
    """Handler for session files."""

    def process(
        self,
        file_path: Path,
        raw_data: dict,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        """Process a session file and persist to database."""
        parsed = parser.parse_session(raw_data)
        if not parsed:
            return None

        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
            (id, project_id, directory, title, parent_id, version,
             additions, deletions, files_changed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.project_id,
                parsed.directory,
                parsed.title,
                parsed.parent_id,
                parsed.version,
                parsed.additions,
                parsed.deletions,
                parsed.files_changed,
                parsed.created_at,
                parsed.updated_at,
            ],
        )

        # Create root trace if no parent
        if not parsed.parent_id:
            trace_builder.create_root_trace(
                session_id=parsed.id,
                title=parsed.title,
                agent=None,
                first_message=None,
                created_at=parsed.created_at,
                updated_at=parsed.updated_at,
            )

        return parsed.id


class MessageHandler(FileHandler):
    """Handler for message files."""

    def process(
        self,
        file_path: Path,
        raw_data: dict,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        """Process a message file and persist to database."""
        parsed = parser.parse_message(raw_data)
        if not parsed:
            return None

        conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, session_id, parent_id, role, agent, model_id, provider_id,
             mode, cost, finish_reason, working_dir,
             tokens_input, tokens_output, tokens_reasoning,
             tokens_cache_read, tokens_cache_write, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.session_id,
                parsed.parent_id,
                parsed.role,
                parsed.agent,
                parsed.model_id,
                parsed.provider_id,
                parsed.mode,
                parsed.cost,
                parsed.finish_reason,
                parsed.working_dir,
                parsed.tokens_input,
                parsed.tokens_output,
                parsed.tokens_reasoning,
                parsed.tokens_cache_read,
                parsed.tokens_cache_write,
                parsed.created_at,
                parsed.completed_at,
            ],
        )

        return parsed.id


class PartHandler(FileHandler):
    """Handler for part files."""

    def process(
        self,
        file_path: Path,
        raw_data: dict,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        """Process a part file and persist to database."""
        parsed = parser.parse_part(raw_data)
        if not parsed:
            return None

        conn.execute(
            """
            INSERT OR REPLACE INTO parts
            (id, session_id, message_id, part_type, content, tool_name, tool_status,
             call_id, created_at, ended_at, duration_ms, arguments, error_message, error_data,
             child_session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.session_id,
                parsed.message_id,
                parsed.part_type,
                parsed.content,
                parsed.tool_name,
                parsed.tool_status,
                parsed.call_id,
                parsed.created_at,
                parsed.ended_at,
                parsed.duration_ms,
                parsed.arguments,
                parsed.error_message,
                parsed.error_data,
                parsed.child_session_id,
            ],
        )

        # Handle file operations (read/write/edit) - populate file_operations table
        file_op = parser.parse_file_operation(raw_data)
        if file_op:
            conn.execute(
                """
                INSERT OR REPLACE INTO file_operations
                (id, session_id, trace_id, operation, file_path, timestamp, risk_level, risk_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    file_op.id,
                    file_op.session_id,
                    file_op.trace_id,
                    file_op.operation,
                    file_op.file_path,
                    file_op.timestamp,
                    file_op.risk_level,
                    file_op.risk_reason,
                ],
            )

        # Handle patches (git commits)
        if parsed.part_type == "patch":
            git_hash = raw_data.get("hash")
            files = raw_data.get("files", [])
            if git_hash:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO patches
                    (id, session_id, message_id, git_hash, files, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        parsed.id,
                        parsed.session_id,
                        parsed.message_id,
                        git_hash,
                        files,
                        parsed.created_at,
                    ],
                )

        # Handle task delegation
        if parsed.tool_name == "task" and parsed.tool_status == "completed":
            delegation = parser.parse_delegation(raw_data)
            if delegation:
                trace_builder.create_trace_from_delegation(delegation, parsed)

        return parsed.id


class SessionDiffHandler(FileHandler):
    """Handler for session_diff files - enriches file_operations with diff stats."""

    def process(
        self,
        file_path: Path,
        raw_data: Any,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        session_id = file_path.stem

        if not isinstance(raw_data, list):
            return None

        diff_by_file = build_diff_stats_map(raw_data)
        if not diff_by_file:
            return session_id

        matcher = DiffPathMatcher(diff_by_file)

        file_ops = conn.execute(
            """SELECT id, file_path FROM file_operations 
               WHERE session_id = ? AND operation IN ('write', 'edit')""",
            [session_id],
        ).fetchall()

        for op_id, op_file_path in file_ops:
            stats = matcher.match(op_file_path)
            if stats:
                conn.execute(
                    """UPDATE file_operations 
                       SET additions = ?, deletions = ? 
                       WHERE id = ?""",
                    [stats["additions"], stats["deletions"], op_id],
                )

        return session_id
