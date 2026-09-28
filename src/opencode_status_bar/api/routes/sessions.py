"""
Sessions Routes - Session listing and detail endpoints.
"""

import json
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, request

from ...analytics import get_analytics_db
from ...utils.logger import error
from ._context import get_db_lock, get_service

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/api/sessions", methods=["GET"])
def get_sessions():
    """Get list of sessions for tree view."""
    try:
        days = request.args.get("days", 30, type=int)
        limit = request.args.get("limit", 100, type=int)

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()

            # Calculate start date
            start_date = datetime.now() - timedelta(days=days)

            rows = conn.execute(
                """
                SELECT 
                    id,
                    title,
                    directory,
                    created_at,
                    updated_at
                FROM sessions
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                [start_date, limit],
            ).fetchall()

            sessions = [
                {
                    "id": row[0],
                    "title": row[1],
                    "directory": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None,
                }
                for row in rows
            ]

        return jsonify({"success": True, "data": sessions})
    except Exception as e:
        error(f"[API] Error getting sessions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/summary", methods=["GET"])
def get_session_summary(session_id: str):
    """Get session summary."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_summary(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/tokens", methods=["GET"])
def get_session_tokens(session_id: str):
    """Get session token details."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_tokens(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session tokens: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/tools", methods=["GET"])
def get_session_tools(session_id: str):
    """Get session tool details."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_tools(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session tools: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/files", methods=["GET"])
def get_session_files(session_id: str):
    """Get session file operations."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_files(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session files: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/agents", methods=["GET"])
def get_session_agents(session_id: str):
    """Get session agents."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_agents(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session agents: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/timeline", methods=["GET"])
def get_session_timeline(session_id: str):
    """Get session timeline events."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_timeline(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session timeline: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/prompts", methods=["GET"])
def get_session_prompts(session_id: str):
    """Get session prompts (first user prompt + last response)."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_prompts(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session prompts: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id: str):
    """Get messages with content for a session (optionally paginated).

    Query params:
        offset: Starting index (default: 0)
        limit: Max messages to return (optional, default: no limit, max: 5000)
    """
    try:
        offset = request.args.get("offset", 0, type=int)
        limit = request.args.get("limit", type=int)

        if limit is not None:
            limit = min(limit, 5000)

        with get_db_lock():
            service = get_service()
            data = service.get_session_messages(session_id, offset=offset, limit=limit)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session messages: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== Plan 34: Enriched Parts Endpoints =====


@sessions_bp.route("/api/session/<session_id>/reasoning", methods=["GET"])
def get_session_reasoning(session_id: str):
    """Get session reasoning parts (agent thought process).

    Returns the internal reasoning/thinking of the agent with
    Anthropic cryptographic signatures when available.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_reasoning(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session reasoning: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/steps", methods=["GET"])
def get_session_steps(session_id: str):
    """Get session step events with precise token counts and costs.

    Step events capture the beginning and end of each agent step,
    with accurate token counts and costs from step-finish events.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_steps(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session steps: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/git-history", methods=["GET"])
def get_session_git_history(session_id: str):
    """Get session git patches history.

    Returns all git commits made during the session with their
    affected files. Useful for understanding code changes.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_git_history(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session git history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/file-parts", methods=["GET"])
def get_session_file_parts(session_id: str):
    """Get session file parts (images, attachments).

    Returns file parts with their base64 data URLs, mime types,
    and filenames. Typically screenshots or pasted images.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_file_parts(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session file parts: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/precise-cost", methods=["GET"])
def get_session_precise_cost(session_id: str):
    """Get session cost calculated from step-finish events.

    This provides more accurate cost data than message-level estimates
    by using the actual cost values from step-finish events.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_precise_cost(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session precise cost: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== Plan 45: Timeline & Aggregation Endpoints =====


@sessions_bp.route("/api/session/<session_id>/timeline/full", methods=["GET"])
def get_session_timeline_full(session_id: str):
    """Get chronological timeline for a session with streaming JSON response.

    Query params:
        limit: Max timeline events to return (optional, default: 500, max: 5000)
        stream: Enable streaming response (default: true)
        include_children: Include child session events inline (default: false)
    """
    try:
        limit = request.args.get("limit", type=int)
        stream = request.args.get("stream", "true").lower() != "false"
        include_children = (
            request.args.get("include_children", "false").lower() == "true"
        )
        if limit is not None:
            limit = min(limit, 5000)

        with get_db_lock():
            service = get_service()

            if stream:
                session_info, events = service.iter_timeline_events(session_id, limit)

                if session_info is None:
                    return jsonify(
                        {"success": False, "error": f"Session {session_id} not found"}
                    ), 404

                def generate():
                    yield '{"success":true,"data":{"meta":{"session_id":"'
                    yield session_id
                    yield '","title":'
                    yield json.dumps(session_info.get("title", ""))
                    yield '},"timeline":['

                    first = True
                    for event in events:
                        if not first:
                            yield ","
                        yield json.dumps(event, separators=(",", ":"))
                        first = False

                    yield "]}}"

                return Response(
                    generate(),
                    mimetype="application/json",
                    headers={"X-Streaming": "true"},
                )
            else:
                result = service.get_session_timeline_full(
                    session_id, include_children=include_children, limit=limit
                )
                if result.get("success"):
                    return jsonify(result)
                return jsonify(result), 404

    except Exception as e:
        error(f"[API] Error getting session timeline: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/exchanges", methods=["GET"])
def get_session_exchanges(session_id: str):
    """Get conversation turns (user->assistant pairs) for a session (optionally paginated).

    Query params:
        offset: Starting exchange index (default: 0)
        limit: Max exchanges to return (optional, default: no limit, max: 1000)
    """
    try:
        offset = request.args.get("offset", 0, type=int)
        limit = request.args.get("limit", type=int)

        if limit is not None:
            limit = min(limit, 1000)

        with get_db_lock():
            service = get_service()
            data = service.get_session_exchanges(session_id, offset=offset, limit=limit)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session exchanges: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/delegations", methods=["GET"])
def get_session_delegations(session_id: str):
    """Get recursive delegation tree structure for a session.

    Returns the full tree of agent delegations starting from this session.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_delegation_tree(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session delegations: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/delegation-timeline", methods=["GET"])
def get_delegation_timeline(session_id: str):
    """Get complete timeline of a delegated agent session.

    Returns all parts (reasoning, text, tools) ordered chronologically.
    Used to display full activity of a sub-agent.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_delegation_timeline(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting delegation timeline: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
