"""
Delegations Routes - Agent delegation endpoints.
"""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from ...analytics import get_analytics_db
from ...utils.logger import error
from ._context import get_db_lock

delegations_bp = Blueprint("delegations", __name__)


@delegations_bp.route("/api/delegations", methods=["GET"])
def get_delegations():
    """Get agent delegations (parent-child session relationships)."""
    try:
        days = request.args.get("days", 30, type=int)
        limit = request.args.get("limit", 1000, type=int)

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()

            start_date = datetime.now() - timedelta(days=days)

            rows = conn.execute(
                """
                SELECT 
                    id,
                    session_id,
                    parent_agent,
                    child_agent,
                    child_session_id,
                    created_at
                FROM delegations
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                [start_date, limit],
            ).fetchall()

            delegations = [
                {
                    "id": row[0],
                    "parent_session_id": row[1],
                    "parent_agent": row[2],
                    "child_agent": row[3],
                    "child_session_id": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                for row in rows
            ]

        return jsonify({"success": True, "data": delegations})
    except Exception as e:
        error(f"[API] Error getting delegations: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
