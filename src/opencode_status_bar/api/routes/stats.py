"""
Statistics Routes - Database and global statistics endpoints.
"""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from ...analytics import get_analytics_db
from ...utils.logger import error
from ._context import get_db_lock, get_service

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/api/stats", methods=["GET"])
def get_stats():
    """Get database statistics."""
    try:
        with get_db_lock():
            db = get_analytics_db()
            stats = db.get_stats()
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        error(f"[API] Error getting stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stats_bp.route("/api/global-stats", methods=["GET"])
def get_global_stats():
    """Get global statistics from TracingDataService."""
    try:
        days = request.args.get("days", 30, type=int)
        end = datetime.now()
        start = end - timedelta(days=days)

        with get_db_lock():
            service = get_service()
            data = service.get_global_stats(start=start, end=end)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting global stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
