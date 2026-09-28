"""
Conversation segment builder.

Creates trace segments when users switch agents mid-session
(e.g., from @build to @plan). Each agent block becomes a separate trace.
"""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ...db import AnalyticsDB


# Constants (shared with builder.py)
ROOT_TRACE_PREFIX = "root_"
ROOT_AGENT_TYPE = "user"


class SegmentBuilder:
    """Builds conversation segments for multi-agent sessions.

    When a user switches agents within a session, this creates
    separate trace segments for each agent block.
    """

    def __init__(self, db: "AnalyticsDB"):
        """Initialize the segment builder.

        Args:
            db: Database instance for reading/writing traces
        """
        self._db = db

    def create_conversation_segments(self, session_id: str) -> int:
        """Create trace segments for agent changes within a session.

        When a user switches agents mid-session (e.g., from @build to @plan),
        this creates separate trace segments for each agent block.

        Args:
            session_id: Session ID to analyze

        Returns:
            Number of segments created
        """
        conn = self._db.connect()

        try:
            # Get all assistant messages for this session, ordered by time
            messages = conn.execute(
                """
                SELECT id, agent, created_at, completed_at,
                       tokens_input, tokens_output
                FROM messages
                WHERE session_id = ?
                  AND role = 'assistant'
                  AND agent IS NOT NULL
                  AND agent != ''
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            if not messages:
                return 0

            # Detect agent segments
            segments = []
            current_agent = None
            segment_start = None
            segment_end = None
            segment_tokens_in = 0
            segment_tokens_out = 0

            for msg in messages:
                msg_agent = msg[1]
                msg_created = msg[2]
                msg_completed = msg[3] or msg_created
                msg_tokens_in = msg[4] or 0
                msg_tokens_out = msg[5] or 0

                # Skip internal agents
                if msg_agent in ("compaction", "summarizer", "title"):
                    continue

                if msg_agent != current_agent:
                    # Save previous segment
                    if current_agent is not None:
                        segments.append(
                            {
                                "agent": current_agent,
                                "start": segment_start,
                                "end": segment_end,
                                "tokens_in": segment_tokens_in,
                                "tokens_out": segment_tokens_out,
                            }
                        )

                    # Start new segment
                    current_agent = msg_agent
                    segment_start = msg_created
                    segment_tokens_in = 0
                    segment_tokens_out = 0

                # Update segment
                segment_end = msg_completed
                segment_tokens_in += msg_tokens_in
                segment_tokens_out += msg_tokens_out

            # Save last segment
            if current_agent is not None:
                segments.append(
                    {
                        "agent": current_agent,
                        "start": segment_start,
                        "end": segment_end,
                        "tokens_in": segment_tokens_in,
                        "tokens_out": segment_tokens_out,
                    }
                )

            # Only create segment traces if there are multiple agents
            if len(segments) <= 1:
                # Single agent - update root trace with correct agent
                if segments:
                    self._update_root_trace_agent(session_id, segments[0])
                return 0

            # Delete old root trace (will be replaced by segments)
            root_trace_id = f"{ROOT_TRACE_PREFIX}{session_id}"

            # Create segment traces
            created = 0
            for i, seg in enumerate(segments):
                segment_trace_id = f"{ROOT_TRACE_PREFIX}{session_id}_seg{i}"

                # Calculate duration
                duration_ms = None
                if seg["start"] and seg["end"]:
                    delta = seg["end"] - seg["start"]
                    duration_ms = int(delta.total_seconds() * 1000)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO agent_traces
                    (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                     prompt_input, prompt_output, started_at, ended_at, duration_ms,
                     tokens_in, tokens_out, status, tools_used, child_session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        segment_trace_id,
                        session_id,
                        root_trace_id if i > 0 else None,  # First segment has no parent
                        ROOT_AGENT_TYPE if i == 0 else segments[i - 1]["agent"],
                        seg["agent"],
                        f"(segment {i}: @{seg['agent']})",
                        None,
                        seg["start"],
                        seg["end"],
                        duration_ms,
                        seg["tokens_in"],
                        seg["tokens_out"],
                        "completed",
                        [],
                        session_id,
                    ],
                )
                created += 1

            # Update root trace to point to first segment
            if created > 0:
                conn.execute(
                    """
                    UPDATE agent_traces
                    SET subagent_type = ?
                    WHERE trace_id = ?
                    """,
                    [segments[0]["agent"], root_trace_id],
                )

            return created

        except Exception:
            return 0

    def analyze_all_sessions_for_segments(self) -> int:
        """Analyze all root sessions and create segments where needed.

        Finds sessions with multiple agents and creates segment traces.
        Only processes sessions that haven't been segmented yet.

        Returns:
            Total number of segments created
        """
        conn = self._db.connect()

        try:
            # Find root sessions that might need segmentation
            # (have messages with different agents)
            # EXCLUDE sessions that already have segment traces
            sessions = conn.execute(
                """
                SELECT DISTINCT m.session_id
                FROM messages m
                JOIN agent_traces t ON t.session_id = m.session_id
                WHERE t.trace_id LIKE 'root_%'
                  AND t.trace_id NOT LIKE '%_seg%'
                  AND m.role = 'assistant'
                  AND m.agent IS NOT NULL
                  AND m.agent NOT IN ('compaction', 'summarizer', 'title')
                  AND NOT EXISTS (
                      SELECT 1 FROM agent_traces seg
                      WHERE seg.session_id = m.session_id
                        AND seg.trace_id LIKE '%_seg%'
                  )
                GROUP BY m.session_id
                HAVING COUNT(DISTINCT m.agent) > 1
                """
            ).fetchall()

            total_created = 0
            for (session_id,) in sessions:
                created = self.create_conversation_segments(session_id)
                total_created += created

            return total_created

        except Exception:
            return 0

    def _update_root_trace_agent(self, session_id: str, segment: dict) -> None:
        """Update root trace with agent and timing from single segment."""
        conn = self._db.connect()
        trace_id = f"{ROOT_TRACE_PREFIX}{session_id}"

        duration_ms = None
        if segment["start"] and segment["end"]:
            delta = segment["end"] - segment["start"]
            duration_ms = int(delta.total_seconds() * 1000)

        try:
            conn.execute(
                """
                UPDATE agent_traces
                SET subagent_type = ?,
                    tokens_in = ?,
                    tokens_out = ?,
                    duration_ms = COALESCE(duration_ms, ?)
                WHERE trace_id = ?
                """,
                [
                    segment["agent"],
                    segment["tokens_in"],
                    segment["tokens_out"],
                    duration_ms,
                    trace_id,
                ],
            )
        except Exception:
            pass
