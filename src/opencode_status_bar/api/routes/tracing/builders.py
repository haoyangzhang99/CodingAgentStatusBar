"""
Tracing Builders - Functions that build data structures for tracing routes.
"""

from typing import Any, Callable

from .utils import (
    extract_display_info,
    extract_tool_display_info,
    get_sort_key,
    match_delegation_tokens,
)


# =============================================================================
# Tool Builders
# =============================================================================


def build_tools_by_session(
    conn: Any, all_session_ids: set, include_tools: bool
) -> dict:
    """Build dictionary of tools grouped by session_id.

    Args:
        conn: Database connection
        all_session_ids: Set of session IDs to fetch tools for
        include_tools: Whether to include tools in output

    Returns:
        Dictionary mapping session_id to list of tool dicts
    """
    tools_by_session: dict = {}

    if not include_tools or not all_session_ids:
        return tools_by_session

    # Placeholders are just "?" markers for parameterized query - safe
    placeholders = ",".join(["?" for _ in all_session_ids])
    tool_rows = conn.execute(
        f"""
        SELECT 
            id, session_id, tool_name, tool_status,
            arguments, created_at, duration_ms, result_summary,
            error_message
        FROM parts
        WHERE session_id IN ({placeholders})
          AND part_type = 'tool'
          AND tool_name IS NOT NULL
          AND tool_name != 'task'
        ORDER BY created_at ASC
        """,  # nosec B608
        list(all_session_ids),
    ).fetchall()

    for row in tool_rows:
        session_id = row[1]
        if session_id not in tools_by_session:
            tools_by_session[session_id] = []

        display_info = extract_tool_display_info(row[2], row[4])

        tools_by_session[session_id].append(
            {
                "id": row[0],
                "node_type": "tool",
                "tool_name": row[2],
                "status": row[3],
                "display_info": display_info,
                "created_at": row[5].isoformat() if row[5] else None,
                "duration_ms": row[6],
                "error": row[8],
            }
        )

    return tools_by_session


def build_tools_by_message(
    conn: Any, root_session_ids: set, include_tools: bool
) -> dict:
    """Build dictionary of tools grouped by message_id.

    Args:
        conn: Database connection
        root_session_ids: Set of root session IDs
        include_tools: Whether to include tools

    Returns:
        Dictionary mapping message_id to list of tool dicts
    """
    tools_by_message: dict = {}

    if not include_tools or not root_session_ids:
        return tools_by_message

    # Placeholders are just "?" markers for parameterized query - safe
    placeholders = ",".join(["?" for _ in root_session_ids])
    tool_rows = conn.execute(
        f"""
        SELECT 
            id, session_id, message_id, tool_name, tool_status,
            arguments, created_at, duration_ms, result_summary,
            error_message
        FROM parts
        WHERE session_id IN ({placeholders})
          AND part_type = 'tool'
          AND tool_name IS NOT NULL
          AND tool_name != 'task'
        ORDER BY created_at ASC
        """,  # nosec B608
        list(root_session_ids),
    ).fetchall()

    for trow in tool_rows:
        msg_id = trow[2]
        if msg_id:
            if msg_id not in tools_by_message:
                tools_by_message[msg_id] = []

            tool_name = trow[3]
            arguments = trow[5]
            display_info = extract_display_info(tool_name, arguments)

            tools_by_message[msg_id].append(
                {
                    "trace_id": f"tool_{trow[0]}",
                    "session_id": trow[1],
                    "node_type": "tool",
                    "tool_name": tool_name,
                    "tool_status": trow[4],
                    "arguments": arguments,
                    "display_info": display_info,
                    "started_at": trow[6].isoformat() if trow[6] else None,
                    "duration_ms": trow[7],
                    "result_summary": trow[8],
                    "error": trow[9],
                    "children": [],
                }
            )

    return tools_by_message


# =============================================================================
# Children Builders
# =============================================================================


def build_children_by_parent(
    child_rows: list,
    tools_by_session: dict,
    subagent_by_time: list,
    include_tools: bool,
) -> dict:
    """Build dictionary mapping parent trace IDs to their children.

    Args:
        child_rows: List of child trace rows
        tools_by_session: Dictionary of tools by session
        subagent_by_time: List of subagent sessions with timestamps
        include_tools: Whether to include tools

    Returns:
        Dictionary mapping parent_trace_id to list of child dicts
    """
    children_by_parent: dict = {}

    for row in child_rows:
        parent_id = row[2]
        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []

        child_session_id = row[13]
        child_tools = (
            tools_by_session.get(child_session_id, []) if include_tools else []
        )

        delegation_start = row[5]
        delegation_agent = row[4]
        delegation_tokens = {"tokens_in": row[8], "tokens_out": row[9]}

        matched_tokens, matched_session = match_delegation_tokens(
            delegation_start, delegation_agent, delegation_tokens, subagent_by_time
        )
        if matched_session:
            child_session_id = matched_session
            delegation_tokens = matched_tokens

        children_by_parent[parent_id].append(
            {
                "trace_id": row[0],
                "session_id": row[1],
                "child_session_id": child_session_id,
                "node_type": "agent",
                "parent_trace_id": row[2],
                "parent_agent": row[3],
                "subagent_type": row[4],
                "started_at": row[5].isoformat() if row[5] else None,
                "ended_at": row[6].isoformat() if row[6] else None,
                "duration_ms": row[7],
                "tokens_in": delegation_tokens.get("tokens_in"),
                "tokens_out": delegation_tokens.get("tokens_out"),
                "cache_read": delegation_tokens.get("cache_read"),
                "status": row[10],
                "prompt_input": row[11],
                "prompt_output": row[12],
                "children": child_tools.copy(),
            }
        )

    return children_by_parent


def build_recursive_children(
    children_by_parent: dict, parent_trace_id: str, depth: int = 0
) -> list:
    """Build recursive tree of children for a parent trace.

    Args:
        children_by_parent: Dictionary mapping parent ID to children
        parent_trace_id: Parent trace ID to get children for
        depth: Current recursion depth

    Returns:
        Sorted list of children with nested children
    """
    if depth > 10:
        return []
    children = children_by_parent.get(parent_trace_id, [])
    for child in children:
        nested_agents = build_recursive_children(
            children_by_parent, child["trace_id"], depth + 1
        )
        child["children"].extend(nested_agents)
        child["children"].sort(key=get_sort_key)
    children.sort(key=get_sort_key)
    return children


# =============================================================================
# Segment & Timeline Builders
# =============================================================================


def build_segment_timeline(segments_by_session: dict) -> dict:
    """Build segment timeline per session for agent detection.

    Args:
        segments_by_session: Dictionary of segments by session

    Returns:
        Dictionary mapping session_id to sorted list of (timestamp, agent) tuples
    """
    segment_timeline: dict = {}
    for session_id, seg_list in segments_by_session.items():
        timeline = []
        for seg_row in seg_list:
            seg_ts = seg_row[4]
            seg_agent = seg_row[3]
            if seg_ts and seg_agent:
                timeline.append((seg_ts, seg_agent))
        timeline.sort(key=lambda x: x[0])
        segment_timeline[session_id] = timeline
    return segment_timeline


# =============================================================================
# Exchange Builders
# =============================================================================


def build_user_exchange(
    msg_id: str,
    session_id: str,
    created_at: Any,
    content: str,
    msg_agent: str | None,
    get_agent_at_time: Callable[[str, Any], str],
) -> dict:
    """Build a user exchange node.

    Args:
        msg_id: Message ID
        session_id: Session ID
        created_at: Created timestamp
        content: Message content
        msg_agent: Agent from message
        get_agent_at_time: Function to get agent at timestamp

    Returns:
        User exchange dictionary
    """
    agent_type = msg_agent or (
        get_agent_at_time(session_id, created_at) if created_at else "assistant"
    )
    prompt_preview = content[:500] if content else ""

    return {
        "trace_id": f"exchange_{msg_id}",
        "session_id": session_id,
        "node_type": "user_turn",
        "parent_agent": "user",
        "subagent_type": agent_type,
        "started_at": created_at.isoformat() if created_at else None,
        "prompt_input": prompt_preview,
        "children": [],
        "tokens_in": None,
        "tokens_out": None,
        "cache_read": None,
    }


def build_exchanges_from_messages(
    all_msg_rows: list,
    tools_by_message: dict,
    get_agent_at_time: Callable[[str, Any], str],
) -> dict:
    """Build exchanges dictionary from message rows.

    Args:
        all_msg_rows: List of message rows
        tools_by_message: Dictionary of tools by message
        get_agent_at_time: Function to get agent at timestamp

    Returns:
        Dictionary mapping session_id to list of exchange dicts
    """
    exchanges_by_session: dict = {}
    current_user_msg = None

    for row in all_msg_rows:
        msg_id = row[0]
        session_id = row[1]
        created_at = row[2]
        role = row[3]
        msg_agent = row[4]
        content = row[5] or ""
        tokens_input = row[6]
        tokens_output = row[7]
        tokens_cache_read = row[8]
        tokens_cache_write = row[9]

        if role == "user":
            current_user_msg = build_user_exchange(
                msg_id, session_id, created_at, content, msg_agent, get_agent_at_time
            )

            if session_id not in exchanges_by_session:
                exchanges_by_session[session_id] = []
            exchanges_by_session[session_id].append(current_user_msg)

        elif role == "assistant" and current_user_msg:
            msg_tools = tools_by_message.get(msg_id, [])
            if msg_tools:
                current_user_msg["children"].extend(msg_tools)

            current_user_msg["tokens_in"] = tokens_input
            current_user_msg["tokens_out"] = tokens_output
            current_user_msg["cache_read"] = tokens_cache_read
            current_user_msg["cache_write"] = tokens_cache_write

            if msg_agent and msg_agent != current_user_msg.get("subagent_type"):
                current_user_msg["subagent_type"] = msg_agent

    return exchanges_by_session


def attach_delegations_to_exchanges(
    session_exchanges: list, agent_children: list
) -> list:
    """Attach delegation children to their parent exchanges.

    Args:
        session_exchanges: List of exchanges for a session
        agent_children: List of delegation children

    Returns:
        Updated agent_children list (empty if all attached to exchanges)
    """
    if not agent_children:
        return agent_children

    sorted_exchanges = sorted(
        session_exchanges,
        key=lambda x: x.get("started_at") or "",
    )

    exchanges_with_children = set()

    for delegation in agent_children:
        deleg_start = delegation.get("started_at") or ""

        parent_exchange = None
        for ex in sorted_exchanges:
            ex_start = ex.get("started_at") or ""
            if ex_start <= deleg_start:
                parent_exchange = ex
            else:
                break

        if parent_exchange:
            if "children" not in parent_exchange:
                parent_exchange["children"] = []
            parent_exchange["children"].append(delegation)
            exchanges_with_children.add(id(parent_exchange))
        else:
            session_exchanges.append(delegation)

    for ex in sorted_exchanges:
        if id(ex) in exchanges_with_children and "children" in ex:
            ex["children"].sort(key=get_sort_key)

    return []  # All delegations attached


# =============================================================================
# Session Builders
# =============================================================================


def build_session_node(
    row: tuple,
    agent_children: list,
    session_tokens: dict,
) -> dict:
    """Build a single session node for the tree.

    Args:
        row: Root trace row tuple
        agent_children: List of children (exchanges + delegations)
        session_tokens: Token counts for session

    Returns:
        Session node dictionary
    """
    session_id = row[1]
    trace_id = row[0]
    agent_type = row[3]

    # Extract token values
    tokens_in = session_tokens.get("tokens_in") or row[7] or 0
    tokens_out = session_tokens.get("tokens_out") or row[8] or 0
    cache_read = session_tokens.get("cache_read") or 0
    cache_write = session_tokens.get("cache_write") or 0
    total_tokens = tokens_in + tokens_out + cache_read + cache_write

    session = {
        "session_id": session_id,
        "trace_id": trace_id,
        "node_type": "session",
        "parent_agent": row[2] or "user",
        "agent_type": agent_type,
        "started_at": row[4].isoformat() if row[4] else None,
        "ended_at": row[5].isoformat() if row[5] else None,
        "duration_ms": row[6],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cache_read": cache_read,
        "cache_write": cache_write,
        # Add structured tokens object for dashboard
        "tokens": {
            "input": tokens_in,
            "output": tokens_out,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "total": total_tokens,
        },
        "status": row[9],
        "prompt_input": row[10],
        "title": row[11] or "",
        "directory": row[12] or "",
        "children": agent_children,
    }

    def count_traces(node: dict) -> int:
        return 1 + sum(count_traces(c) for c in node.get("children", []))

    session["trace_count"] = count_traces(session) - 1

    return session
