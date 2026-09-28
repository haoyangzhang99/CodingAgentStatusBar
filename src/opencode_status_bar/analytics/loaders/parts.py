"""Parts (text, tool, reasoning, step, patch, compaction, file) data loader.

Plan 34: Enriched parts loading - handles all 7 part types from OpenCode storage.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..db import AnalyticsDB
from ...utils.logger import error
from ...utils.datetime import ms_to_datetime


@dataclass
class LoaderStats:
    """Statistics for parts loading."""

    text: int = 0
    tool: int = 0
    reasoning: int = 0
    step_start: int = 0
    step_finish: int = 0
    patch: int = 0
    compaction: int = 0
    file: int = 0

    @property
    def total(self) -> int:
        return (
            self.text
            + self.tool
            + self.reasoning
            + self.step_start
            + self.step_finish
            + self.patch
            + self.compaction
            + self.file
        )

    def __str__(self) -> str:
        parts = []
        if self.text:
            parts.append(f"{self.text} text")
        if self.tool:
            parts.append(f"{self.tool} tools")
        if self.reasoning:
            parts.append(f"{self.reasoning} reasoning")
        if self.step_start or self.step_finish:
            parts.append(f"{self.step_start + self.step_finish} steps")
        if self.patch:
            parts.append(f"{self.patch} patches")
        if self.compaction:
            parts.append(f"{self.compaction} compactions")
        if self.file:
            parts.append(f"{self.file} files")
        return ", ".join(parts) if parts else "0"


def load_parts_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load part data by iterating through message directories.

    Loads all part types:
    - text: User prompts, assistant responses
    - tool: Tool invocations
    - reasoning: Agent thought process (with Anthropic signature)
    - step-start/step-finish: Step events with tokens and cost
    - patch: Git commits with hash and files
    - compaction: Context compaction events
    - file: File attachments (metadata only, not base64 content)

    Uses Python file iteration instead of DuckDB's read_json_auto
    for better performance with large numbers of files.
    """
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_days)
    cutoff_ts = cutoff.timestamp()

    stats = LoaderStats()
    batch_size = 500

    # Separate batches for each table
    parts_batch: list[tuple[Any, ...]] = []
    step_events_batch: list[tuple[Any, ...]] = []
    patches_batch: list[tuple[Any, ...]] = []

    def flush_batches() -> None:
        """Insert all batches into database."""
        nonlocal parts_batch, step_events_batch, patches_batch

        if parts_batch:
            conn.executemany(
                """INSERT OR REPLACE INTO parts 
                   (id, session_id, message_id, part_type, content, tool_name, tool_status, 
                    created_at, arguments, call_id, ended_at, duration_ms, error_message,
                    reasoning_text, anthropic_signature, compaction_auto, file_mime, file_name,
                    result_summary, child_session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                parts_batch,
            )
            parts_batch = []

        if step_events_batch:
            conn.executemany(
                """INSERT OR REPLACE INTO step_events
                   (id, session_id, message_id, event_type, reason, snapshot_hash,
                    cost, tokens_input, tokens_output, tokens_reasoning,
                    tokens_cache_read, tokens_cache_write, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                step_events_batch,
            )
            step_events_batch = []

        if patches_batch:
            conn.executemany(
                """INSERT OR REPLACE INTO patches
                   (id, session_id, message_id, git_hash, files, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                patches_batch,
            )
            patches_batch = []

    try:
        # Iterate through message directories
        for msg_dir in part_dir.iterdir():
            if not msg_dir.is_dir():
                continue

            # Check directory modification time for quick filtering
            try:
                if msg_dir.stat().st_mtime < cutoff_ts:
                    continue
            except OSError:
                continue

            # Process part files in this message directory
            for part_file in msg_dir.iterdir():
                if not part_file.suffix == ".json":
                    continue

                try:
                    with open(part_file, "r") as f:
                        data = json.load(f)

                    part_id = data.get("id")
                    if not part_id:
                        continue

                    session_id = data.get("sessionID")
                    message_id = data.get("messageID")
                    part_type = data.get("type")

                    # Get timestamp
                    time_data = data.get("time", {})
                    ts = time_data.get("start") or time_data.get("created")
                    created_at = ms_to_datetime(ts) if ts else None

                    # Process by part type
                    if part_type == "text":
                        _process_text_part(
                            data,
                            part_id,
                            session_id,
                            message_id,
                            created_at,
                            parts_batch,
                            stats,
                        )

                    elif part_type == "tool":
                        _process_tool_part(
                            data,
                            part_id,
                            session_id,
                            message_id,
                            time_data,
                            created_at,
                            parts_batch,
                            stats,
                        )

                    elif part_type == "reasoning":
                        _process_reasoning_part(
                            data,
                            part_id,
                            session_id,
                            message_id,
                            created_at,
                            parts_batch,
                            stats,
                        )

                    elif part_type == "step-start":
                        _process_step_start_part(
                            data,
                            part_id,
                            session_id,
                            message_id,
                            created_at,
                            step_events_batch,
                            stats,
                        )

                    elif part_type == "step-finish":
                        _process_step_finish_part(
                            data,
                            part_id,
                            session_id,
                            message_id,
                            created_at,
                            step_events_batch,
                            stats,
                        )

                    elif part_type == "patch":
                        _process_patch_part(
                            data,
                            part_id,
                            session_id,
                            message_id,
                            created_at,
                            patches_batch,
                            stats,
                        )

                    elif part_type == "compaction":
                        _process_compaction_part(
                            data,
                            part_id,
                            session_id,
                            message_id,
                            created_at,
                            parts_batch,
                            stats,
                        )

                    elif part_type == "file":
                        _process_file_part(
                            data,
                            part_id,
                            session_id,
                            message_id,
                            created_at,
                            parts_batch,
                            stats,
                        )

                    # Flush when any batch is full
                    total_batch = (
                        len(parts_batch) + len(step_events_batch) + len(patches_batch)
                    )
                    if total_batch >= batch_size:
                        flush_batches()

                except (json.JSONDecodeError, OSError):
                    continue

        # Insert remaining batches
        flush_batches()

        return stats.total

    except Exception as e:  # Intentional catch-all: various errors possible
        error(f"Parts load failed: {e}")
        return 0


def _process_text_part(
    data: dict,
    part_id: str,
    session_id: str,
    message_id: str,
    created_at: datetime | None,
    batch: list[tuple[Any, ...]],
    stats: LoaderStats,
) -> None:
    """Process a text part (user prompt or assistant response)."""
    content = data.get("text")
    if not content:
        return

    batch.append(
        (
            part_id,
            session_id,
            message_id,
            "text",
            content,  # content
            None,  # tool_name
            None,  # tool_status
            created_at,
            None,  # arguments
            None,  # call_id
            None,  # ended_at
            None,  # duration_ms
            None,  # error_message
            None,  # reasoning_text
            None,  # anthropic_signature
            None,  # compaction_auto
            None,  # file_mime
            None,  # file_name
            None,  # result_summary
            None,  # child_session_id
        )
    )
    stats.text += 1


def _process_tool_part(
    data: dict,
    part_id: str,
    session_id: str,
    message_id: str,
    time_data: dict,
    created_at: datetime | None,
    batch: list[tuple[Any, ...]],
    stats: LoaderStats,
) -> None:
    """Process a tool invocation part."""
    tool_name = data.get("tool")
    if not tool_name:
        return

    state = data.get("state", {})
    tool_status = state.get("status") if isinstance(state, dict) else None
    tool_input = state.get("input", {}) if isinstance(state, dict) else {}
    arguments = json.dumps(tool_input) if tool_input else None
    call_id = data.get("callID")

    # Timing
    start_ts = time_data.get("start")
    end_ts = time_data.get("end")
    ended_at = ms_to_datetime(end_ts) if end_ts else None
    duration_ms = (end_ts - start_ts) if (start_ts and end_ts) else None

    # Error message
    error_message = state.get("error") if isinstance(state, dict) else None

    # Result summary - FULL output, NO TRUNCATION (Plan 45)
    tool_output = state.get("output") if isinstance(state, dict) else None
    if tool_output is None:
        result_summary = None
    elif isinstance(tool_output, str):
        result_summary = tool_output
    else:
        result_summary = json.dumps(tool_output)

    # Child session ID for task delegations
    metadata = state.get("metadata", {}) if isinstance(state, dict) else {}
    child_session_id = metadata.get("sessionId") if isinstance(metadata, dict) else None

    batch.append(
        (
            part_id,
            session_id,
            message_id,
            "tool",
            None,  # content
            tool_name,
            tool_status,
            created_at,
            arguments,
            call_id,
            ended_at,
            duration_ms,
            error_message,
            None,  # reasoning_text
            None,  # anthropic_signature
            None,  # compaction_auto
            None,  # file_mime
            None,  # file_name
            result_summary,  # FULL tool output
            child_session_id,
        )
    )
    stats.tool += 1


def _process_reasoning_part(
    data: dict,
    part_id: str,
    session_id: str,
    message_id: str,
    created_at: datetime | None,
    batch: list[tuple[Any, ...]],
    stats: LoaderStats,
) -> None:
    """Process a reasoning part (agent thought process)."""
    # Support both 'reasoning' (Claude extended thinking) and 'text' (OpenCode format)
    reasoning_text = data.get("reasoning") or data.get("text", "")
    metadata = data.get("metadata", {})
    anthropic_data = metadata.get("anthropic", {}) if isinstance(metadata, dict) else {}
    anthropic_signature = (
        anthropic_data.get("signature") if isinstance(anthropic_data, dict) else None
    )

    batch.append(
        (
            part_id,
            session_id,
            message_id,
            "reasoning",
            None,  # content
            None,  # tool_name
            None,  # tool_status
            created_at,
            None,  # arguments
            None,  # call_id
            None,  # ended_at
            None,  # duration_ms
            None,  # error_message
            reasoning_text,
            anthropic_signature,
            None,  # compaction_auto
            None,  # file_mime
            None,  # file_name
            None,  # result_summary
            None,  # child_session_id
        )
    )
    stats.reasoning += 1


def _process_step_start_part(
    data: dict,
    part_id: str,
    session_id: str,
    message_id: str,
    created_at: datetime | None,
    batch: list[tuple[Any, ...]],
    stats: LoaderStats,
) -> None:
    """Process a step-start event."""
    snapshot_hash = data.get("snapshot")

    batch.append(
        (
            part_id,
            session_id,
            message_id,
            "start",  # event_type
            None,  # reason
            snapshot_hash,
            0,  # cost
            0,  # tokens_input
            0,  # tokens_output
            0,  # tokens_reasoning
            0,  # tokens_cache_read
            0,  # tokens_cache_write
            created_at,
        )
    )
    stats.step_start += 1


def _process_step_finish_part(
    data: dict,
    part_id: str,
    session_id: str,
    message_id: str,
    created_at: datetime | None,
    batch: list[tuple[Any, ...]],
    stats: LoaderStats,
) -> None:
    """Process a step-finish event with tokens and cost."""
    reason = data.get("reason")
    snapshot_hash = data.get("snapshot")
    cost = data.get("cost", 0) or 0

    tokens = data.get("tokens", {})
    if not isinstance(tokens, dict):
        tokens = {}

    batch.append(
        (
            part_id,
            session_id,
            message_id,
            "finish",  # event_type
            reason,
            snapshot_hash,
            cost,
            tokens.get("input", 0) or 0,
            tokens.get("output", 0) or 0,
            tokens.get("reasoning", 0) or 0,
            tokens.get("cacheRead", 0) or 0,
            tokens.get("cacheWrite", 0) or 0,
            created_at,
        )
    )
    stats.step_finish += 1


def _process_patch_part(
    data: dict,
    part_id: str,
    session_id: str,
    message_id: str,
    created_at: datetime | None,
    batch: list[tuple[Any, ...]],
    stats: LoaderStats,
) -> None:
    """Process a patch part (git commit)."""
    git_hash = data.get("hash")
    if not git_hash:
        return

    files = data.get("files", [])
    if not isinstance(files, list):
        files = []

    batch.append(
        (
            part_id,
            session_id,
            message_id,
            git_hash,
            files,  # DuckDB will handle list -> VARCHAR[]
            created_at,
        )
    )
    stats.patch += 1


def _process_compaction_part(
    data: dict,
    part_id: str,
    session_id: str,
    message_id: str,
    created_at: datetime | None,
    batch: list[tuple[Any, ...]],
    stats: LoaderStats,
) -> None:
    """Process a compaction part (context compaction event)."""
    compaction_auto = data.get("auto", False)

    batch.append(
        (
            part_id,
            session_id,
            message_id,
            "compaction",
            None,  # content
            None,  # tool_name
            None,  # tool_status
            created_at,
            None,  # arguments
            None,  # call_id
            None,  # ended_at
            None,  # duration_ms
            None,  # error_message
            None,  # reasoning_text
            None,  # anthropic_signature
            compaction_auto,
            None,  # file_mime
            None,  # file_name
            None,  # result_summary
            None,  # child_session_id
        )
    )
    stats.compaction += 1


def _process_file_part(
    data: dict,
    part_id: str,
    session_id: str,
    message_id: str,
    created_at: datetime | None,
    batch: list[tuple[Any, ...]],
    stats: LoaderStats,
) -> None:
    """Process a file part (attachment metadata only, skip base64 content)."""
    file_mime = data.get("mime")
    file_name = data.get("filename")

    # Skip if no metadata available
    if not file_mime and not file_name:
        return

    batch.append(
        (
            part_id,
            session_id,
            message_id,
            "file",
            None,  # content (skip base64)
            None,  # tool_name
            None,  # tool_status
            created_at,
            None,  # arguments
            None,  # call_id
            None,  # ended_at
            None,  # duration_ms
            None,  # error_message
            None,  # reasoning_text
            None,  # anthropic_signature
            None,  # compaction_auto
            file_mime,
            file_name,
            None,  # result_summary
            None,  # child_session_id
        )
    )
    stats.file += 1
