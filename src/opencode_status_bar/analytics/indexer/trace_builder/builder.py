"""
Real-time agent trace builder.

Creates agent_traces immediately when task tool parts are completed,
instead of waiting for batch processing.

Features:
- Immediate trace creation on task completion
- Parent trace resolution
- Token aggregation from child session
- Status tracking (running/completed/error)
"""

from datetime import datetime
from typing import Optional
import uuid

from ...db import AnalyticsDB
from ..parsers import ParsedDelegation, ParsedPart
from ....utils.logger import info

from .helpers import determine_status, extract_prompt
from .segments import SegmentBuilder


# Constants for root session traces
ROOT_TRACE_PREFIX = "root_"
ROOT_AGENT_TYPE = "user"


class TraceBuilder:
    """Builds agent traces in real-time from delegation events.

    Creates and updates agent_traces table when task tool parts
    are processed, enabling real-time trace visibility.
    """

    def __init__(self, db: AnalyticsDB):
        """Initialize the trace builder.

        Args:
            db: Database instance for reading/writing traces
        """
        self._db = db
        self._segment_builder = SegmentBuilder(db)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensure agent_traces table exists with all columns."""
        conn = self._db.connect()
        # Table should already exist from db.py schema, but ensure it
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_traces (
                    trace_id VARCHAR PRIMARY KEY,
                    session_id VARCHAR NOT NULL,
                    parent_trace_id VARCHAR,
                    parent_agent VARCHAR,
                    subagent_type VARCHAR NOT NULL,
                    prompt_input TEXT NOT NULL,
                    prompt_output TEXT,
                    started_at TIMESTAMP NOT NULL,
                    ended_at TIMESTAMP,
                    duration_ms INTEGER,
                    tokens_in INTEGER,
                    tokens_out INTEGER,
                    status VARCHAR DEFAULT 'running',
                    tools_used TEXT[],
                    child_session_id VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception:
            pass  # nosec B110 - table may already exist, ignore errors

    def create_trace_from_delegation(
        self,
        delegation: ParsedDelegation,
        part: ParsedPart,
    ) -> Optional[str]:
        """Create or update a trace from a delegation.

        Called when a task tool part is processed. Creates the trace
        immediately if completed, or updates an existing trace.

        Args:
            delegation: Parsed delegation data
            part: Parsed part data with timing info

        Returns:
            The trace_id if created/updated, None on error
        """
        if not delegation.child_agent:
            return None

        trace_id = delegation.id or str(uuid.uuid4())
        status = determine_status(part.tool_status)

        # Resolve parent agent from message
        parent_agent = self._resolve_parent_agent(delegation.message_id)

        # Get prompt from delegation
        prompt_input = extract_prompt(part.arguments)

        # Resolve parent trace immediately (don't wait for batch resolution)
        parent_trace_id = None
        if delegation.session_id:
            parent_trace_id = self._resolve_parent_trace_id(
                delegation.session_id, trace_id
            )

        conn = self._db.connect()

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_traces
                (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                 prompt_input, prompt_output, started_at, ended_at, duration_ms,
                 tokens_in, tokens_out, status, tools_used, child_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    trace_id,
                    delegation.session_id or "",
                    parent_trace_id,  # Resolved immediately
                    parent_agent,
                    delegation.child_agent,
                    prompt_input,
                    None,  # prompt_output
                    part.created_at or datetime.now(),
                    part.ended_at,
                    part.duration_ms,
                    None,  # tokens_in - resolved later
                    None,  # tokens_out - resolved later
                    status,
                    [],  # tools_used
                    delegation.child_session_id,
                ],
            )

            info(
                f"[TraceBuilder] Created trace {trace_id} for {delegation.child_agent}"
            )

            # Update tokens from child session messages (may already be indexed)
            if delegation.child_session_id:
                self.update_trace_tokens(delegation.child_session_id)

            return trace_id

        except Exception:
            return None

    def update_trace_tokens(self, child_session_id: str) -> None:
        """Update trace tokens from child session messages.

        Called after messages are indexed to aggregate token counts.

        Args:
            child_session_id: The child session ID to aggregate tokens from
        """
        conn = self._db.connect()

        try:
            # Get total tokens from child session
            result = conn.execute(
                """
                SELECT
                    COALESCE(SUM(tokens_input), 0),
                    COALESCE(SUM(tokens_output), 0)
                FROM messages
                WHERE session_id = ?
                """,
                [child_session_id],
            ).fetchone()

            if result and (result[0] > 0 or result[1] > 0):
                conn.execute(
                    """
                    UPDATE agent_traces
                    SET tokens_in = ?, tokens_out = ?
                    WHERE child_session_id = ?
                    """,
                    [result[0], result[1], child_session_id],
                )

        except Exception:
            pass

    def backfill_missing_tokens(self) -> int:
        """Backfill tokens for all traces with child_session_id but no tokens.

        This fixes traces that were created before their child session
        messages were indexed.

        Uses 2 queries (count + update) for efficiency - O(1) vs O(N) queries.

        Returns:
            Number of traces updated
        """
        conn = self._db.connect()

        try:
            # Count traces that will be updated (DuckDB doesn't return rowcount)
            count_result = conn.execute(
                """
                SELECT COUNT(*) FROM agent_traces t
                WHERE t.child_session_id IS NOT NULL
                  AND (t.tokens_in IS NULL OR t.tokens_in = 0)
                  AND (t.tokens_out IS NULL OR t.tokens_out = 0)
                  AND EXISTS (
                      SELECT 1 FROM messages m
                      WHERE m.session_id = t.child_session_id
                      GROUP BY m.session_id
                      HAVING SUM(m.tokens_input) > 0 OR SUM(m.tokens_output) > 0
                  )
                """
            ).fetchone()
            will_update = count_result[0] if count_result else 0

            if will_update == 0:
                return 0

            # Update traces with aggregated tokens from messages
            conn.execute(
                """
                UPDATE agent_traces
                SET tokens_in = agg.total_in,
                    tokens_out = agg.total_out
                FROM (
                    SELECT
                        session_id,
                        COALESCE(SUM(tokens_input), 0) as total_in,
                        COALESCE(SUM(tokens_output), 0) as total_out
                    FROM messages
                    GROUP BY session_id
                    HAVING SUM(tokens_input) > 0 OR SUM(tokens_output) > 0
                ) agg
                WHERE agent_traces.child_session_id = agg.session_id
                  AND agent_traces.child_session_id IS NOT NULL
                  AND (agent_traces.tokens_in IS NULL OR agent_traces.tokens_in = 0)
                  AND (agent_traces.tokens_out IS NULL OR agent_traces.tokens_out = 0)
                """
            )

            if will_update > 0:
                info(f"[TraceBuilder] Backfilled tokens for {will_update} traces")

            return will_update

        except Exception:
            return 0

    def resolve_parent_traces(self) -> int:
        """Resolve parent_trace_id for traces based on session membership.

        A trace's parent is the trace whose child_session_id matches
        the trace's session_id.

        Returns:
            Number of traces updated
        """
        conn = self._db.connect()
        total_updated = 0

        try:
            # Step 1: Set parent_trace_id for traces without one
            # IMPORTANT: Exclude root traces (root_% without _seg) - they should NEVER have a parent
            result = conn.execute("""
                UPDATE agent_traces t1
                SET parent_trace_id = (
                    SELECT t2.trace_id
                    FROM agent_traces t2
                    WHERE t2.child_session_id = t1.session_id
                      AND t2.trace_id != t1.trace_id
                    LIMIT 1
                )
                WHERE parent_trace_id IS NULL
                  AND NOT (t1.trace_id LIKE 'root_%' AND t1.trace_id NOT LIKE '%_seg%')
                  AND EXISTS (
                    SELECT 1 FROM agent_traces t2
                    WHERE t2.child_session_id = t1.session_id
                      AND t2.trace_id != t1.trace_id
                )
            """)
            updated = result.rowcount if hasattr(result, "rowcount") else 0
            total_updated += updated

            # Step 2: Update parent_agent from parent's subagent_type
            # This runs even if parent_trace_id was already set (to fix stale data)
            result = conn.execute("""
                UPDATE agent_traces t1
                SET parent_agent = (
                    SELECT t2.subagent_type
                    FROM agent_traces t2
                    WHERE t2.trace_id = t1.parent_trace_id
                )
                WHERE parent_trace_id IS NOT NULL
                  AND (
                    parent_agent IS NULL
                    OR parent_agent = 'user'
                    OR parent_agent != (
                        SELECT t2.subagent_type
                        FROM agent_traces t2
                        WHERE t2.trace_id = t1.parent_trace_id
                    )
                  )
            """)
            updated = result.rowcount if hasattr(result, "rowcount") else 0
            total_updated += updated

            if total_updated > 0:
                info(f"[TraceBuilder] Resolved {total_updated} parent traces")
            return total_updated

        except Exception:
            return 0

    def update_root_trace_agents(self) -> int:
        """Update root traces subagent_type from their session's first message.

        Root traces are created before messages are indexed, so they have
        subagent_type='user'. This method updates them with the actual agent
        type from the first assistant message in their session.

        Returns:
            Number of traces updated
        """
        conn = self._db.connect()

        try:
            # Update root traces with agent from first assistant message
            result = conn.execute("""
                UPDATE agent_traces
                SET subagent_type = (
                    SELECT m.agent
                    FROM messages m
                    WHERE m.session_id = agent_traces.child_session_id
                      AND m.role = 'assistant'
                      AND m.agent IS NOT NULL
                      AND m.agent != ''
                    ORDER BY m.created_at ASC
                    LIMIT 1
                )
                WHERE trace_id LIKE 'root_%'
                  AND subagent_type = 'user'
                  AND EXISTS (
                    SELECT 1 FROM messages m
                    WHERE m.session_id = agent_traces.child_session_id
                      AND m.role = 'assistant'
                      AND m.agent IS NOT NULL
                      AND m.agent != ''
                )
            """)

            updated = result.rowcount if hasattr(result, "rowcount") else 0
            if updated > 0:
                info(f"[TraceBuilder] Updated {updated} root trace agents")
            return updated

        except Exception:
            return 0

    def _resolve_parent_trace_id(self, session_id: str, trace_id: str) -> Optional[str]:
        """Resolve parent trace ID for a delegation trace.

        A delegation trace's parent is the trace whose child_session_id
        matches the delegation's session_id.

        Args:
            session_id: Session ID of the delegation trace
            trace_id: Trace ID to exclude from search

        Returns:
            Parent trace ID or None
        """
        conn = self._db.connect()
        try:
            result = conn.execute(
                """
                SELECT trace_id
                FROM agent_traces
                WHERE child_session_id = ?
                  AND trace_id != ?
                LIMIT 1
                """,
                [session_id, trace_id],
            ).fetchone()
            return result[0] if result else None
        except Exception:
            return None

    def _resolve_parent_agent(self, message_id: Optional[str]) -> Optional[str]:
        """Resolve parent agent from message.

        Args:
            message_id: Message ID containing the task tool call

        Returns:
            Agent name or None
        """
        if not message_id:
            return None

        conn = self._db.connect()
        try:
            result = conn.execute(
                "SELECT agent FROM messages WHERE id = ?",
                [message_id],
            ).fetchone()
            return result[0] if result else None
        except Exception:
            return None

    def create_root_trace(
        self,
        session_id: str,
        title: Optional[str],
        agent: Optional[str],
        first_message: Optional[str],
        created_at: Optional[datetime],
        updated_at: Optional[datetime],
    ) -> Optional[str]:
        """Create a trace for a root session (user-initiated).

        Root sessions are sessions without a parentID, representing
        direct user conversations.

        Args:
            session_id: Session ID
            title: Session title
            agent: Primary agent for the session
            first_message: First user message content
            created_at: Session creation time
            updated_at: Session update time

        Returns:
            The trace_id if created, None on error
        """
        trace_id = f"{ROOT_TRACE_PREFIX}{session_id}"

        # Calculate duration
        duration_ms = None
        if created_at and updated_at:
            delta = updated_at - created_at
            duration_ms = int(delta.total_seconds() * 1000)

        conn = self._db.connect()

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_traces
                (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                 prompt_input, prompt_output, started_at, ended_at, duration_ms,
                 tokens_in, tokens_out, status, tools_used, child_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    trace_id,
                    session_id,
                    None,  # Root has no parent
                    ROOT_AGENT_TYPE,  # "user"
                    agent or ROOT_AGENT_TYPE,
                    first_message or title or "(No prompt)",
                    None,
                    created_at or datetime.now(),
                    updated_at,
                    duration_ms,
                    None,
                    None,
                    "completed" if updated_at else "running",
                    [],
                    session_id,  # Root's child_session_id is itself
                ],
            )

            info(f"[TraceBuilder] Created root trace {trace_id}")
            return trace_id

        except Exception:
            return None

    def create_conversation_segments(self, session_id: str) -> int:
        """Create trace segments for agent changes within a session.

        Delegates to SegmentBuilder.

        Args:
            session_id: Session ID to analyze

        Returns:
            Number of segments created
        """
        return self._segment_builder.create_conversation_segments(session_id)

    def analyze_all_sessions_for_segments(self) -> int:
        """Analyze all root sessions and create segments where needed.

        Delegates to SegmentBuilder.

        Returns:
            Total number of segments created
        """
        return self._segment_builder.analyze_all_sessions_for_segments()

    def get_stats(self) -> dict:
        """Get trace statistics.

        Returns:
            Dict with trace counts by status
        """
        conn = self._db.connect()

        try:
            total_result = conn.execute("SELECT COUNT(*) FROM agent_traces").fetchone()
            total = total_result[0] if total_result else 0

            by_status = conn.execute("""
                SELECT status, COUNT(*) FROM agent_traces
                GROUP BY status
            """).fetchall()

            root_result = conn.execute("""
                SELECT COUNT(*) FROM agent_traces
                WHERE trace_id LIKE 'root_%'
            """).fetchone()
            root_count = root_result[0] if root_result else 0

            delegation_result = conn.execute("""
                SELECT COUNT(*) FROM agent_traces
                WHERE trace_id NOT LIKE 'root_%'
            """).fetchone()
            delegation_count = delegation_result[0] if delegation_result else 0

            return {
                "total": total,
                "by_status": {row[0]: row[1] for row in by_status},
                "root_traces": root_count,
                "delegation_traces": delegation_count,
            }

        except Exception:
            return {
                "total": 0,
                "by_status": {},
                "root_traces": 0,
                "delegation_traces": 0,
            }

    # Compatibility wrappers for tests - delegate to MaterializedTableManager
    def build_exchanges(self, session_id: Optional[str] = None) -> int:
        """Build exchanges table - delegates to MaterializedTableManager.

        Args:
            session_id: Optional session ID filter

        Returns:
            Number of exchanges created
        """
        from ...materialization import MaterializedTableManager

        manager = MaterializedTableManager(self._db)
        result = manager.refresh_exchanges(session_id=session_id, incremental=False)
        return result.get("rows_added", 0)

    def build_exchange_traces(self, session_id: Optional[str] = None) -> int:
        """Build exchange_traces table - delegates to MaterializedTableManager.

        Args:
            session_id: Optional session ID filter

        Returns:
            Number of exchange traces created
        """
        from ...materialization import MaterializedTableManager

        manager = MaterializedTableManager(self._db)
        result = manager.refresh_exchange_traces(session_id=session_id)
        return result.get("rows_added", 0)

    def build_session_traces(self, session_id: Optional[str] = None) -> int:
        """Build session_traces table - delegates to MaterializedTableManager.

        Args:
            session_id: Optional session ID filter

        Returns:
            Number of session traces created
        """
        from ...materialization import MaterializedTableManager

        manager = MaterializedTableManager(self._db)
        result = manager.refresh_session_traces(
            session_id=session_id, incremental=False
        )
        return result.get("rows_added", 0)

    def build_all(self, session_id: Optional[str] = None) -> dict:
        """Build all materialized tables - delegates to MaterializedTableManager.

        Args:
            session_id: Optional session ID filter

        Returns:
            Dictionary with counts for each table
        """
        exchanges = self.build_exchanges(session_id=session_id)
        exchange_traces = self.build_exchange_traces(session_id=session_id)
        session_traces = self.build_session_traces(session_id=session_id)

        return {
            "exchanges": exchanges,
            "exchange_traces": exchange_traces,
            "session_traces": session_traces,
        }
