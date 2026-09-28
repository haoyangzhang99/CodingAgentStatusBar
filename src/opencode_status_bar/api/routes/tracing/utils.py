"""
Tracing Utils - Helper functions and constants for tracing routes.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Callable


# =============================================================================
# Constants
# =============================================================================

MIN_TIMESTAMP = "0000-01-01T00:00:00"


# =============================================================================
# Public Helper Functions
# =============================================================================


def get_sort_key(item: dict) -> str:
    """Get a sortable timestamp from an item."""
    ts = item.get("started_at") or item.get("created_at")
    return ts if ts else MIN_TIMESTAMP


def extract_display_info(tool_name: str, arguments: str | None) -> str | None:
    """Extract human-readable display info from tool arguments."""
    if not arguments:
        return None
    try:
        args = json.loads(arguments)

        # URL-based tools
        if tool_name in ("webfetch", "context7_query-docs"):
            url = args.get("url") or args.get("libraryId", "")
            return url[:80] if url else None

        # File-based tools
        if tool_name in ("read", "write", "edit", "glob"):
            path = args.get("filePath") or args.get("path", "")
            return path[:80] if path else None

        # Command-based tools
        if tool_name == "bash":
            cmd = args.get("command", "")
            return cmd[:60] if cmd else None

        # Search tools
        if tool_name == "grep":
            pattern = args.get("pattern", "")
            return f"/{pattern}/"[:40] if pattern else None

        # Task/delegation tools - show subagent and description
        if tool_name == "task":
            subagent = args.get("subagent_type", "")
            desc = args.get("description", "")
            if subagent and desc:
                return f"{subagent}: {desc}"[:100]
            elif desc:
                return desc[:100]
            elif subagent:
                return subagent
            return None

    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None


# =============================================================================
# Private Helper Functions
# =============================================================================


def extract_tool_display_info(tool_name: str, args: str | None) -> str:
    """Extract display info from tool arguments for inline display.

    Args:
        tool_name: Name of the tool
        args: JSON string of tool arguments

    Returns:
        Human-readable display info string
    """
    if not args:
        return ""

    try:
        args_dict = json.loads(args)
        if tool_name == "bash":
            cmd = args_dict.get("command", "")
            return cmd[:100] + "..." if len(cmd) > 100 else cmd
        elif tool_name in ("read", "write", "edit"):
            return args_dict.get("filePath", args_dict.get("path", ""))
        elif tool_name == "glob":
            return args_dict.get("pattern", "")
        elif tool_name == "grep":
            return args_dict.get("pattern", "")
        elif tool_name == "task":
            subagent = args_dict.get("subagent_type", "")
            desc = args_dict.get("description", "")
            if subagent and desc:
                return f"{subagent}: {desc}"[:100]
            elif desc:
                return desc[:100]
            elif subagent:
                return subagent
            return ""
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    return ""


def collect_session_ids(root_rows: list, child_rows: list) -> tuple[set, set]:
    """Collect all session IDs from root and child traces.

    Args:
        root_rows: List of root trace rows
        child_rows: List of child trace rows

    Returns:
        Tuple of (all_session_ids, root_session_ids)
    """
    all_session_ids: set = set()
    root_session_ids: set = set()

    for row in root_rows:
        root_session_ids.add(row[1])
        all_session_ids.add(row[1])
        if row[13]:  # child_session_id
            all_session_ids.add(row[13])

    for row in child_rows:
        if row[13]:
            all_session_ids.add(row[13])

    return all_session_ids, root_session_ids


def match_delegation_tokens(
    delegation_start: Any,
    delegation_agent: str,
    delegation_tokens: dict,
    subagent_by_time: list,
) -> tuple[dict, str | None]:
    """Match delegation with subagent session to get tokens.

    Args:
        delegation_start: Start timestamp of delegation
        delegation_agent: Agent type of delegation
        delegation_tokens: Current token dict
        subagent_by_time: List of subagent sessions with timestamps

    Returns:
        Tuple of (updated tokens dict, matched session_id or None)
    """
    if delegation_tokens.get("tokens_in") or not delegation_start:
        return delegation_tokens, None

    for sa in subagent_by_time:
        if sa["agent_type"] == delegation_agent:
            time_diff = abs((sa["created_at"] - delegation_start).total_seconds())
            if time_diff < 5:
                return {
                    "tokens_in": sa["tokens"].get("tokens_in"),
                    "tokens_out": sa["tokens"].get("tokens_out"),
                    "cache_read": sa["tokens"].get("cache_read"),
                }, sa["session_id"]

    return delegation_tokens, None


def create_agent_at_time_getter(
    initial_agent: dict, segment_timeline: dict
) -> Callable[[str, Any], str]:
    """Create a closure function to get active agent at a given timestamp.

    Args:
        initial_agent: Dictionary of initial agents by session
        segment_timeline: Dictionary of segment timelines by session

    Returns:
        Function that returns agent type for a session at a given time
    """

    def get_agent_at_time(session_id: str, timestamp: Any) -> str:
        """Get the active agent type at a given timestamp."""
        agent = initial_agent.get(session_id, "assistant")
        timeline = segment_timeline.get(session_id, [])
        for seg_ts, seg_agent in timeline:
            if timestamp >= seg_ts:
                agent = seg_agent
            else:
                break
        return agent

    return get_agent_at_time


def calculate_exchange_end_time(
    ex: dict, sorted_exchanges: list, index: int, session_end: Any
) -> str | None:
    """Calculate end time for a single exchange.

    Args:
        ex: Exchange dictionary
        sorted_exchanges: Sorted list of exchanges
        index: Index of current exchange
        session_end: Session end timestamp

    Returns:
        End time as ISO string or None
    """
    ended_at_str = None
    children = ex.get("children", [])

    # Try to get end time from children
    if children:
        for child in reversed(children):
            child_end = child.get("ended_at")
            if child_end:
                ended_at_str = child_end
                break
            child_start = child.get("started_at")
            child_duration = child.get("duration_ms")
            if child_start and child_duration:
                try:
                    start_dt = datetime.fromisoformat(child_start)
                    end_dt = start_dt + timedelta(milliseconds=child_duration)
                    ended_at_str = end_dt.isoformat()
                    break
                except (ValueError, TypeError):
                    pass

    # Fall back to next exchange start
    if not ended_at_str and index + 1 < len(sorted_exchanges):
        next_start = sorted_exchanges[index + 1].get("started_at")
        if next_start:
            ended_at_str = next_start

    # Fall back to session end
    if not ended_at_str and session_end:
        ended_at_str = session_end.isoformat()

    return ended_at_str


def calculate_exchange_durations(session_exchanges: list, session_end: Any) -> None:
    """Calculate duration for each exchange based on next exchange start.

    Args:
        session_exchanges: List of exchanges to update (modified in place)
        session_end: Session end timestamp
    """
    sorted_for_duration = sorted(
        session_exchanges,
        key=lambda x: x.get("started_at") or "",
    )

    for i, ex in enumerate(sorted_for_duration):
        ex_start_str = ex.get("started_at")
        if not ex_start_str:
            continue

        ended_at_str = calculate_exchange_end_time(
            ex, sorted_for_duration, i, session_end
        )

        ex["ended_at"] = ended_at_str

        if ex_start_str and ended_at_str:
            try:
                start_dt = datetime.fromisoformat(ex_start_str)
                end_dt = datetime.fromisoformat(ended_at_str)
                duration = int((end_dt - start_dt).total_seconds() * 1000)
                ex["duration_ms"] = duration
            except (ValueError, TypeError):
                pass
