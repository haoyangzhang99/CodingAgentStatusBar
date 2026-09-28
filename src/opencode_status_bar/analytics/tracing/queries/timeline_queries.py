"""Timeline-related queries for sessions.

Handles timeline events, messages, prompts, and exchange tracking.
This is the most complex query module due to timeline aggregation logic.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseSessionQueries

if TYPE_CHECKING:
    pass


class TimelineQueries(BaseSessionQueries):
    """Queries for session timeline, messages, and exchange tracking.

    This module handles the most complex queries related to reconstructing
    the conversation timeline from various event sources.
    """

    def get_session_prompts(self, session_id: str) -> dict:
        """Get first user prompt and last assistant response for a session.

        Retrieves actual content from the parts table.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with prompt_input (first user message) and prompt_output (last response)
        """
        try:
            first_user = self._conn.execute(
                """
                SELECT p.content
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                WHERE p.session_id = ?
                  AND p.part_type = 'text'
                  AND m.role = 'user'
                  AND p.content IS NOT NULL
                ORDER BY p.created_at ASC
                LIMIT 1
                """,
                [session_id],
            ).fetchone()

            last_assistant = self._conn.execute(
                """
                SELECT p.content
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                WHERE p.session_id = ?
                  AND p.part_type = 'text'
                  AND m.role = 'assistant'
                  AND p.content IS NOT NULL
                ORDER BY p.created_at DESC
                LIMIT 1
                """,
                [session_id],
            ).fetchone()

            prompt_input = first_user[0] if first_user else None
            prompt_output = last_assistant[0] if last_assistant else None

            if not prompt_input:
                session = self._get_session_info(session_id)
                prompt_input = (
                    session.get("title", "(No prompt content)")
                    if session
                    else "(No prompt content)"
                )

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                },
                "prompt_input": prompt_input,
                "prompt_output": prompt_output or "(No response yet)",
            }
        except Exception as e:
            return {
                "meta": {"session_id": session_id, "error": str(e)},
                "prompt_input": "(Unable to load prompt data)",
                "prompt_output": None,
            }

    def get_session_messages(
        self, session_id: str, offset: int = 0, limit: int | None = None
    ) -> list[dict]:
        """Get paginated messages for a session with parts.

        Args:
            session_id: The session ID to query
            offset: Offset for pagination
            limit: Limit for pagination (None = no limit)

        Returns:
            List of message dicts with parts
        """
        try:
            if limit is None:
                query = """
                SELECT
                    m.id, m.role, m.agent, m.created_at,
                    m.tokens_input, m.tokens_output,
                    p.part_type, p.content, p.tool_name, p.tool_status,
                    p.error_name, p.error_data,
                    s.root_path, s.title as summary_title
                FROM messages m
                LEFT JOIN parts p ON m.id = p.message_id
                LEFT JOIN sessions s ON m.session_id = s.id
                WHERE m.session_id = ?
                ORDER BY m.created_at ASC, p.index ASC
                """
                results = self._conn.execute(query, [session_id]).fetchall()
            else:
                query = """
                SELECT
                    m.id, m.role, m.agent, m.created_at,
                    m.tokens_input, m.tokens_output,
                    p.part_type, p.content, p.tool_name, p.tool_status,
                    p.error_name, p.error_data,
                    s.root_path, s.title as summary_title
                FROM messages m
                LEFT JOIN parts p ON m.id = p.message_id
                LEFT JOIN sessions s ON m.session_id = s.id
                WHERE m.session_id = ?
                ORDER BY m.created_at ASC, p.index ASC
                LIMIT ? OFFSET ?
                """
                results = self._conn.execute(
                    query, [session_id, limit, offset]
                ).fetchall()

            messages: list[dict] = []
            seen_messages: set[str] = set()

            for row in results:
                (
                    msg_id,
                    role,
                    agent,
                    part_type,
                    content,
                    tool_name,
                    tool_status,
                    created_at,
                    tokens_in,
                    tokens_out,
                    error_name,
                    error_data,
                    root_path,
                    summary_title,
                ) = row

                entry_key = f"{msg_id}"

                if entry_key not in seen_messages:
                    seen_messages.add(entry_key)
                    msg = {
                        "id": msg_id,
                        "role": role,
                        "agent": agent,
                        "created_at": created_at.isoformat() if created_at else None,
                        "tokens_input": tokens_in or 0,
                        "tokens_output": tokens_out or 0,
                        "parts": [],
                    }
                    messages.append(msg)

                if messages and part_type:
                    messages[-1]["parts"].append(
                        {
                            "type": part_type,
                            "content": content,
                            "tool_name": tool_name,
                            "tool_status": tool_status,
                            "error_name": error_name,
                            "error_data": error_data,
                        }
                    )

            return messages

        except Exception:
            return []

    def get_session_timeline(self, session_id: str) -> list[dict]:
        """Get simplified timeline for a session.

        Args:
            session_id: The session ID to query

        Returns:
            List of timeline events (messages and tools)
        """
        try:
            events: list[dict] = []

            msg_results = self._conn.execute(
                """
                SELECT
                    m.id, m.role, m.created_at, m.agent,
                    p.content, p.part_type
                FROM messages m
                LEFT JOIN parts p ON m.id = p.message_id AND p.part_type = 'text'
                WHERE m.session_id = ?
                ORDER BY m.created_at ASC
                """,
                [session_id],
            ).fetchall()

            for row in msg_results:
                msg_event = {
                    "type": "message",
                    "message_id": row[0],
                    "role": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "agent": row[3],
                    "content": row[4] or "",
                }
                events.append(msg_event)

            tool_results = self._conn.execute(
                """
                SELECT
                    p.tool_name, p.created_at, p.tool_status, p.duration_ms
                FROM parts p
                WHERE p.session_id = ? AND p.tool_name IS NOT NULL
                ORDER BY p.created_at ASC
                """,
                [session_id],
            ).fetchall()

            for row in tool_results:
                tool_event = {
                    "type": "tool",
                    "tool_name": row[0],
                    "created_at": row[1].isoformat() if row[1] else None,
                    "status": row[2],
                    "duration_ms": row[3] or 0,
                }
                events.append(tool_event)

            events.sort(key=lambda x: x.get("created_at", ""))

            return events

        except Exception:
            return []

    """
    ARCHITECTURAL NOTE: Complex timeline methods not yet extracted
    
    get_session_timeline_full() and iter_timeline_events() remain in the legacy mixin
    due to their complexity (273 and 171 lines with recursive CTEs and nested generators).
    These require dedicated refactoring with timeline reconstruction testing before extraction.
    """
