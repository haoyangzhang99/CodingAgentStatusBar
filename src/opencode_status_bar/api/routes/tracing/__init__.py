"""
Tracing Routes - Agent trace tree and hierarchy endpoints.

This module contains the complex tracing tree endpoints that build
hierarchical views of agent traces, conversations, and tool usage.
"""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from ....analytics import get_analytics_db
from ....utils.logger import error
from .._context import get_db_lock
from .builders import (
    attach_delegations_to_exchanges,
    build_children_by_parent,
    build_exchanges_from_messages,
    build_recursive_children,
    build_segment_timeline,
    build_session_node,
    build_tools_by_message,
    build_tools_by_session,
)
from .fetchers import (
    fetch_child_traces,
    fetch_messages_for_exchanges,
    fetch_root_traces,
    fetch_segment_traces,
    fetch_subagent_tokens,
    fetch_tokens_by_session,
    get_initial_agents,
)
from .utils import (
    calculate_exchange_durations,
    collect_session_ids,
    create_agent_at_time_getter,
    get_sort_key,
)

tracing_bp = Blueprint("tracing", __name__)


# =============================================================================
# Routes
# =============================================================================


@tracing_bp.route("/api/tracing/tree", methods=["GET"])
def get_tracing_tree():
    """Get hierarchical tracing tree for dashboard display.

    Returns sessions with their child traces and tools in a tree structure.
    All hierarchy logic is done in SQL, no client-side aggregation needed.

    Structure:
    - Session (user -> agent)
      - Agent trace (agent -> subagent)
        - Tool (bash, read, edit, etc.)
        - Tool ...
      - Agent trace ...
    """
    try:
        days = request.args.get("days", 30, type=int)
        include_tools = request.args.get("include_tools", "true").lower() == "true"
        limit = request.args.get("limit", 80, type=int)
        offset = request.args.get("offset", 0, type=int)

        limit = min(limit, 1000)
        offset = max(offset, 0)

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()
            start_date = datetime.now() - timedelta(days=days)

            root_rows = fetch_root_traces(conn, start_date, limit=limit, offset=offset)
            segments_by_session = fetch_segment_traces(conn, start_date)
            child_rows = fetch_child_traces(conn, start_date)

            # Step 2: Collect session IDs and build tools
            all_session_ids, root_session_ids = collect_session_ids(
                root_rows, child_rows
            )
            tools_by_session = build_tools_by_session(
                conn, all_session_ids, include_tools
            )

            # Step 3: Fetch subagent tokens for delegations
            _, subagent_by_time = fetch_subagent_tokens(conn, start_date)

            # Step 4: Build children lookup
            children_by_parent = build_children_by_parent(
                child_rows, tools_by_session, subagent_by_time, include_tools
            )

            # Step 5: Build exchanges for root sessions
            exchanges_by_session: dict = {}
            tokens_by_session: dict = {}

            if root_session_ids:
                # Fetch messages and build tools by message
                all_msg_rows = fetch_messages_for_exchanges(conn, root_session_ids)
                tools_by_message = build_tools_by_message(
                    conn, root_session_ids, include_tools
                )

                # Build timeline and agent detection
                segment_timeline = build_segment_timeline(segments_by_session)
                initial_agent = get_initial_agents(conn, root_session_ids)
                get_agent_at_time = create_agent_at_time_getter(
                    initial_agent, segment_timeline
                )

                # Build exchanges
                exchanges_by_session = build_exchanges_from_messages(
                    all_msg_rows, tools_by_message, get_agent_at_time
                )

                # Fetch token aggregation
                tokens_by_session = fetch_tokens_by_session(conn, root_session_ids)

            # Step 6: Build final session tree
            sessions = []
            for row in root_rows:
                trace_id = row[0]
                session_id = row[1]

                # Build recursive children from delegations
                agent_children = build_recursive_children(children_by_parent, trace_id)

                # Add children from segments
                session_segments = segments_by_session.get(session_id, [])
                for seg_row in session_segments:
                    seg_trace_id = seg_row[0]
                    seg_children = build_recursive_children(
                        children_by_parent, seg_trace_id
                    )
                    agent_children.extend(seg_children)

                # Get exchanges for this session
                session_exchanges = exchanges_by_session.get(session_id, [])

                if session_exchanges:
                    # Attach delegations to their parent exchanges
                    agent_children = attach_delegations_to_exchanges(
                        session_exchanges, agent_children
                    )

                    # Calculate duration for each exchange
                    calculate_exchange_durations(session_exchanges, row[5])

                    # Merge exchanges into children
                    agent_children = session_exchanges + agent_children
                    agent_children.sort(key=get_sort_key)

                # Build session node
                session_tokens = tokens_by_session.get(session_id, {})
                session = build_session_node(row, agent_children, session_tokens)
                sessions.append(session)

        has_more = len(root_rows) == limit

        return jsonify(
            {
                "success": True,
                "data": sessions,
                "meta": {
                    "limit": limit,
                    "offset": offset,
                    "count": len(sessions),
                    "has_more": has_more,
                },
            }
        )
    except Exception as e:
        error(f"[API] Error getting tracing tree: {e}")
        import traceback

        error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
