"""Agent traces data loader."""

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..db import AnalyticsDB
from ..models import AgentTrace
from ...utils.logger import info
from ...utils.datetime import ms_to_datetime
from .enrichment import get_session_agent, get_first_user_message


# Constants for root session traces
ROOT_TRACE_PREFIX = "root_"
ROOT_AGENT_TYPE = "user"  # Root sessions are direct user conversations


@dataclass
class AgentSegment:
    """A segment of messages from a single agent within a session."""

    agent: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    message_count: int
    tokens_in: int
    tokens_out: int


@dataclass
class SessionData:
    """Raw session data before trace creation."""

    session_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    duration_ms: Optional[int]
    data: dict
    file_path: Path


def get_agent_segments(message_dir: Path, session_id: str) -> list[AgentSegment]:
    """Get agent segments for a session (detect agent changes mid-conversation).

    When a user switches agents mid-session (e.g., from @roadmap to @coordinateur),
    this function identifies each contiguous segment of messages from the same agent.

    Args:
        message_dir: Path to OpenCode message storage
        session_id: The session ID to analyze

    Returns:
        List of AgentSegment objects, one per contiguous agent block.
        Excludes internal agents like 'compaction', 'summarizer', 'title'.
    """
    session_msg_dir = message_dir / session_id
    if not session_msg_dir.exists():
        return []

    # Internal agents to skip (not user-visible)
    INTERNAL_AGENTS = {"compaction", "summarizer", "title"}

    # Load all messages with timing
    messages: list[tuple[int, dict]] = []
    for msg_file in session_msg_dir.glob("*.json"):
        try:
            with open(msg_file) as f:
                data = json.load(f)
            created = data.get("time", {}).get("created", 0)
            messages.append((created, data))
        except (json.JSONDecodeError, OSError):
            continue

    if not messages:
        return []

    # Sort by creation time
    messages.sort(key=lambda x: x[0])

    # Detect agent segments
    segments: list[AgentSegment] = []
    current_agent: Optional[str] = None
    segment_start: Optional[int] = None
    segment_end: Optional[int] = None
    segment_count = 0
    segment_tokens_in = 0
    segment_tokens_out = 0

    for created_ts, msg in messages:
        agent = msg.get("agent")
        if not agent or agent in INTERNAL_AGENTS:
            continue

        if agent != current_agent:
            # Save previous segment
            if current_agent and segment_count > 0:
                segments.append(
                    AgentSegment(
                        agent=current_agent,
                        start_time=ms_to_datetime(segment_start),
                        end_time=ms_to_datetime(segment_end),
                        message_count=segment_count,
                        tokens_in=segment_tokens_in,
                        tokens_out=segment_tokens_out,
                    )
                )

            # Start new segment
            current_agent = agent
            segment_start = created_ts
            segment_count = 0
            segment_tokens_in = 0
            segment_tokens_out = 0

        # Update segment stats
        segment_end = msg.get("time", {}).get("completed") or created_ts
        segment_count += 1
        tokens = msg.get("tokens", {})
        segment_tokens_in += tokens.get("input", 0)
        segment_tokens_out += tokens.get("output", 0)

    # Save last segment
    if current_agent and segment_count > 0:
        segments.append(
            AgentSegment(
                agent=current_agent,
                start_time=ms_to_datetime(segment_start),
                end_time=ms_to_datetime(segment_end),
                message_count=segment_count,
                tokens_in=segment_tokens_in,
                tokens_out=segment_tokens_out,
            )
        )

    return segments


def _collect_root_sessions(session_dir: Path, cutoff: datetime) -> list[SessionData]:
    """Collect all root sessions from disk (Phase 1).

    Traverses the session directory structure and collects metadata for
    all root sessions (those without a parent) within the time cutoff.

    Args:
        session_dir: Path to session storage directory
        cutoff: Only include sessions created after this time

    Returns:
        List of SessionData objects, unsorted
    """
    sessions: list[SessionData] = []

    for project_dir in session_dir.iterdir():
        if not project_dir.is_dir():
            continue

        for session_file in project_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    data = json.load(f)

                # Only process root sessions (no parent)
                if data.get("parentID") is not None:
                    continue

                session_id = data.get("id")
                if not session_id:
                    continue

                # Check time filter
                time_data = data.get("time", {})
                created_ts = time_data.get("created")
                updated_ts = time_data.get("updated")
                created_at = ms_to_datetime(created_ts)

                if created_at and created_at < cutoff:
                    continue

                # Calculate duration
                duration_ms = None
                if created_ts and updated_ts:
                    duration_ms = updated_ts - created_ts

                sessions.append(
                    SessionData(
                        session_id=session_id,
                        created_at=created_at or datetime.min,
                        updated_at=ms_to_datetime(updated_ts),
                        duration_ms=duration_ms,
                        data=data,
                        file_path=session_file,
                    )
                )

            except (json.JSONDecodeError, OSError):
                continue

    return sessions


def _create_single_trace(
    session: SessionData,
    segments: list[AgentSegment],
    first_message: Optional[str],
) -> AgentTrace:
    """Create a single trace for a single-agent session.

    Args:
        session: Raw session data
        segments: Agent segments (0 or 1 expected)
        first_message: First user message as prompt

    Returns:
        AgentTrace for the session
    """
    session_agent = segments[0].agent if segments else None
    tokens_in = segments[0].tokens_in if segments else None
    tokens_out = segments[0].tokens_out if segments else None

    return AgentTrace(
        trace_id=f"{ROOT_TRACE_PREFIX}{session.session_id}",
        session_id=session.session_id,
        parent_trace_id=None,
        parent_agent=ROOT_AGENT_TYPE,
        subagent_type=session_agent or ROOT_AGENT_TYPE,
        prompt_input=first_message or session.data.get("title", "(No prompt)"),
        prompt_output=None,
        started_at=session.created_at,
        ended_at=session.updated_at,
        duration_ms=session.duration_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        status="completed" if session.updated_at else "running",
        tools_used=[],
        child_session_id=session.session_id,
    )


def _create_segment_traces(
    session: SessionData,
    segments: list[AgentSegment],
    first_message: Optional[str],
) -> list[AgentTrace]:
    """Create traces for a multi-agent session (one per segment).

    For sessions where the user switched agents mid-conversation,
    creates a trace for each contiguous agent segment, chained together.

    Args:
        session: Raw session data
        segments: Agent segments (2+ expected)
        first_message: First user message as prompt

    Returns:
        List of AgentTrace objects, one per segment
    """
    traces: list[AgentTrace] = []
    parent_trace_id = None
    previous_agent = ROOT_AGENT_TYPE

    for i, segment in enumerate(segments):
        segment_trace_id = f"{ROOT_TRACE_PREFIX}{session.session_id}_seg{i}"

        # Calculate segment duration
        segment_duration = None
        if segment.start_time and segment.end_time:
            delta = segment.end_time - segment.start_time
            segment_duration = int(delta.total_seconds() * 1000)

        prompt = (
            (first_message or "(No prompt)")
            if i == 0
            else f"(switched to @{segment.agent})"
        )

        trace = AgentTrace(
            trace_id=segment_trace_id,
            session_id=session.session_id,
            parent_trace_id=parent_trace_id,
            parent_agent=previous_agent,
            subagent_type=segment.agent,
            prompt_input=prompt,
            prompt_output=None,
            started_at=segment.start_time,
            ended_at=segment.end_time,
            duration_ms=segment_duration,
            tokens_in=segment.tokens_in,
            tokens_out=segment.tokens_out,
            status="completed",
            tools_used=[],
            child_session_id=session.session_id,
        )
        traces.append(trace)

        # Chain for next segment
        parent_trace_id = segment_trace_id
        previous_agent = segment.agent

    return traces


def _get_session_segments(
    session: SessionData,
    message_dir: Path,
    segment_cutoff: datetime,
) -> list[AgentSegment]:
    """Get agent segments for a session with cutoff optimization.

    Full segment analysis is only done for recent sessions.
    Older sessions just get a fast single-agent lookup.

    Args:
        session: Raw session data
        message_dir: Path to message storage
        segment_cutoff: Sessions before this time use fast path

    Returns:
        List of agent segments (may be empty)
    """
    if session.created_at >= segment_cutoff:
        return get_agent_segments(message_dir, session.session_id)

    # Fast path for older sessions
    agent = get_session_agent(message_dir, session.session_id)
    if not agent:
        return []

    return [
        AgentSegment(
            agent=agent,
            start_time=session.created_at,
            end_time=session.updated_at,
            message_count=0,
            tokens_in=0,
            tokens_out=0,
        )
    ]


def _process_session(
    session: SessionData,
    message_dir: Path,
    segment_cutoff: datetime,
) -> list[AgentTrace]:
    """Process a single session into trace(s).

    Orchestrates segment analysis and trace creation for one session.

    Args:
        session: Raw session data
        message_dir: Path to message storage
        segment_cutoff: Sessions before this time use fast segment lookup

    Returns:
        List of AgentTrace objects (1 for single-agent, N for multi-agent)
    """
    first_message = get_first_user_message(message_dir, session.session_id)
    segments = _get_session_segments(session, message_dir, segment_cutoff)

    if len(segments) <= 1:
        return [_create_single_trace(session, segments, first_message)]

    return _create_segment_traces(session, segments, first_message)


def extract_root_sessions(
    storage_path: Path,
    max_days: int = 30,
    throttle_ms: int = 10,
    segment_analysis_days: int = 1,
) -> list[AgentTrace]:
    """Extract root sessions (direct conversations, not delegations).

    Root sessions are sessions where parentID is null, meaning they were
    started directly by the user rather than created via task delegation.

    Uses a pipeline pattern:
    1. Collect: Gather all root sessions from disk
    2. Sort: Order by date (most recent first)
    3. Process: Convert each session to trace(s) with throttling

    Args:
        storage_path: Path to OpenCode storage
        max_days: Only extract sessions from the last N days
        throttle_ms: Milliseconds to sleep between processing sessions
        segment_analysis_days: Only do full segment analysis for sessions
            within this many days (older sessions just get first agent)

    Returns:
        List of AgentTrace objects representing root sessions
    """
    session_dir = storage_path / "session"
    message_dir = storage_path / "message"

    if not session_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=max_days)
    segment_cutoff = datetime.now() - timedelta(days=segment_analysis_days)

    # Phase 1: Collect all root sessions
    sessions = _collect_root_sessions(session_dir, cutoff)

    # Phase 2: Sort by date descending (most recent first)
    sessions.sort(key=lambda x: x.created_at, reverse=True)
    info(f"Processing {len(sessions)} root sessions (newest first)")

    # Phase 3: Process sessions with throttling
    traces: list[AgentTrace] = []
    for session in sessions:
        traces.extend(_process_session(session, message_dir, segment_cutoff))

        if throttle_ms > 0:
            time.sleep(throttle_ms / 1000.0)

    info(f"Extracted {len(traces)} root sessions")
    return traces


def extract_traces(storage_path: Path, max_days: int = 30) -> list[AgentTrace]:
    """Extract agent traces from task tool invocations.

    Parses the part files to find tool calls with name="task",
    extracts full prompt input/output, timing, and nested tool usage.

    Uses mtime-based directory filtering for performance.

    Args:
        storage_path: Path to OpenCode storage
        max_days: Only extract traces from the last N days

    Returns:
        List of AgentTrace objects with full execution context
    """
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=max_days)
    cutoff_ts = cutoff.timestamp()
    traces: list[AgentTrace] = []

    # Phase 1: Filter directories by mtime (fast)
    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        try:
            if msg_dir.stat().st_mtime < cutoff_ts:
                continue
        except OSError:
            continue

        # Phase 2: Read only task tool files from recent directories
        for part_file in msg_dir.iterdir():
            if not part_file.suffix == ".json":
                continue

            try:
                with open(part_file, "r") as f:
                    data = json.load(f)

                if data.get("tool") != "task":
                    continue

                state = data.get("state", {})
                input_data = state.get("input", {})
                subagent_type = input_data.get("subagent_type")
                if not subagent_type:
                    continue

                # Extract timing
                time_data = state.get("time", {})
                start_ts = time_data.get("start")
                end_ts = time_data.get("end")
                started_at = ms_to_datetime(start_ts)
                ended_at = ms_to_datetime(end_ts)

                # Calculate duration
                duration_ms = None
                if start_ts and end_ts:
                    duration_ms = end_ts - start_ts

                # Determine status
                status = state.get("status", "running")
                if status == "completed":
                    status = "completed"
                elif status == "error" or status == "failed":
                    status = "error"
                else:
                    status = "running"

                # Extract tools used from metadata.summary
                tools_used = []
                metadata = state.get("metadata", {})
                summary = metadata.get("summary", [])
                for item in summary:
                    tool_name = item.get("tool")
                    if tool_name:
                        tools_used.append(tool_name)

                # Create trace
                trace = AgentTrace(
                    trace_id=data.get("id", str(uuid.uuid4())),
                    session_id=data.get("sessionID", ""),
                    parent_trace_id=None,  # Will be resolved later
                    parent_agent=None,  # Will be resolved from message
                    subagent_type=subagent_type,
                    prompt_input=input_data.get("prompt", ""),
                    prompt_output=state.get("output"),
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=duration_ms,
                    tokens_in=None,  # Would need message lookup
                    tokens_out=None,
                    status=status,
                    tools_used=tools_used,
                    child_session_id=metadata.get("sessionId"),
                )
                traces.append(trace)

            except (json.JSONDecodeError, OSError):
                continue

    info(f"Extracted {len(traces)} agent traces")
    return traces


def _ensure_traces_table(conn) -> None:
    """Ensure agent_traces table exists (DDL).

    Creates the agent_traces table if it doesn't exist. Used for legacy
    databases that were created before the traces feature was added.

    Args:
        conn: Database connection
    """
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


def _resolve_parent_traces(traces: list[AgentTrace]) -> None:
    """Resolve parent_trace_id for each trace (in-place).

    Builds a mapping from child_session_id to parent trace, then uses it
    to set parent_trace_id and parent_agent for traces that belong to
    delegated sessions.

    Args:
        traces: List of traces to resolve (modified in-place)
    """
    # Build child_session_id -> parent_trace mapping
    parent_trace_by_child_session: dict[str, AgentTrace] = {}
    for trace in traces:
        if trace.child_session_id:
            parent_trace_by_child_session[trace.child_session_id] = trace

    # Resolve parent_trace_id based on session membership
    for trace in traces:
        # Skip segment traces - they already have correct parent_trace_id
        if "_seg" in trace.trace_id:
            continue

        if trace.session_id in parent_trace_by_child_session:
            parent = parent_trace_by_child_session[trace.session_id]
            # Skip self-references (root traces have child_session_id = session_id)
            if parent.trace_id != trace.trace_id:
                trace.parent_trace_id = parent.trace_id
                trace.parent_agent = parent.subagent_type


def _enrich_parent_agents(conn, traces: list[AgentTrace]) -> None:
    """Batch resolve parent_agent from messages table.

    For traces that don't have a parent_agent set (typically root traces),
    looks up the agent from the corresponding message in the database.

    Args:
        conn: Database connection
        traces: List of traces to enrich (modified in-place)
    """
    traces_needing_parent = [t for t in traces if not t.parent_agent]
    if not traces_needing_parent:
        return

    msg_ids = [t.session_id.replace("ses_", "msg_") for t in traces_needing_parent]
    try:
        # Placeholders are just "?" markers for parameterized query - safe
        placeholders = ",".join(["?" for _ in msg_ids])
        results = conn.execute(
            f"SELECT id, agent FROM messages WHERE id IN ({placeholders})",  # nosec B608
            msg_ids,
        ).fetchall()
        agent_by_msg = {r[0]: r[1] for r in results if r[1]}
        for trace in traces_needing_parent:
            msg_id = trace.session_id.replace("ses_", "msg_")
            if msg_id in agent_by_msg:
                trace.parent_agent = agent_by_msg[msg_id]
    except Exception:
        pass  # nosec B110 - batch lookup is optional enrichment


def _enrich_tokens(conn, traces: list[AgentTrace]) -> None:
    """Batch resolve tokens from child session messages.

    Aggregates token counts from all messages in each trace's child session
    and updates the trace with the totals.

    Args:
        conn: Database connection
        traces: List of traces to enrich (modified in-place)
    """
    child_sessions = list({t.child_session_id for t in traces if t.child_session_id})
    if not child_sessions:
        return

    try:
        # Placeholders are just "?" markers for parameterized query - safe
        placeholders = ",".join(["?" for _ in child_sessions])
        results = conn.execute(
            f"""SELECT session_id,
                COALESCE(SUM(tokens_input), 0) as total_in,
                COALESCE(SUM(tokens_output), 0) as total_out
            FROM messages 
            WHERE session_id IN ({placeholders})
            GROUP BY session_id""",  # nosec B608
            child_sessions,
        ).fetchall()
        tokens_by_session = {r[0]: (r[1], r[2]) for r in results}
        for trace in traces:
            if trace.child_session_id in tokens_by_session:
                tokens = tokens_by_session[trace.child_session_id]
                if tokens[0] > 0 or tokens[1] > 0:
                    trace.tokens_in = tokens[0]
                    trace.tokens_out = tokens[1]
    except Exception:
        pass  # nosec B110 - batch lookup is optional enrichment


def _insert_traces(conn, traces: list[AgentTrace]) -> int:
    """Insert traces into database, return success count.

    Inserts or replaces each trace in the database. Individual insert
    failures are logged but don't block other traces from being inserted.

    Args:
        conn: Database connection
        traces: List of traces to insert

    Returns:
        Total count of traces in the table after insertion
    """
    for trace in traces:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO agent_traces
                (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                 prompt_input, prompt_output, started_at, ended_at, duration_ms,
                 tokens_in, tokens_out, status, tools_used, child_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    trace.trace_id,
                    trace.session_id,
                    trace.parent_trace_id,
                    trace.parent_agent,
                    trace.subagent_type,
                    trace.prompt_input,
                    trace.prompt_output,
                    trace.started_at,
                    trace.ended_at,
                    trace.duration_ms,
                    trace.tokens_in,
                    trace.tokens_out,
                    trace.status,
                    trace.tools_used,
                    trace.child_session_id,
                ],
            )
        except Exception:  # Intentional catch-all: skip individual failures
            continue

    return conn.execute("SELECT COUNT(*) FROM agent_traces").fetchone()[0]


def load_traces(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load agent traces into the database.

    Orchestrates the trace loading pipeline:
    1. Ensure schema exists
    2. Extract traces from task tools and root sessions
    3. Resolve parent hierarchy
    4. Enrich with parent agents and tokens from DB
    5. Insert into database

    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage
        max_days: Only load traces from the last N days

    Returns:
        Number of traces loaded
    """
    conn = db.connect()

    # 1. Ensure schema
    _ensure_traces_table(conn)

    # 2. Extract traces
    traces = extract_root_sessions(storage_path, max_days)
    traces.extend(extract_traces(storage_path, max_days))

    if not traces:
        info("No traces found")
        return 0

    # 3. Resolve hierarchy
    _resolve_parent_traces(traces)

    # 4. Enrich from DB
    _enrich_parent_agents(conn, traces)
    _enrich_tokens(conn, traces)

    # 5. Insert
    count = _insert_traces(conn, traces)
    return count
