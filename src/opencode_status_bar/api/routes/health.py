"""
Health Check Routes - Health and status endpoints.
"""

from datetime import datetime

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/sync/status", methods=["GET"])
def sync_status_v2():
    """Get indexer status.

    Returns:
        - running: True if indexer is running
        - files_processed: Number of files processed since start
    """
    try:
        from ...analytics.indexer.hybrid import IndexerRegistry

        indexer = IndexerRegistry.get()
        if indexer:
            stats = indexer.get_stats()
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "running": stats.get("running", False),
                        "files_processed": stats.get("files_processed", 0),
                        "is_ready": indexer.is_ready(),
                    },
                }
            )
        else:
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "running": False,
                        "files_processed": 0,
                        "is_ready": False,
                    },
                }
            )
    except Exception as e:
        return jsonify(
            {
                "success": True,
                "data": {
                    "running": False,
                    "files_processed": 0,
                    "is_ready": False,
                    "error": str(e),
                },
            }
        )


@health_bp.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify(
        {"success": True, "data": {"status": "ok", "service": "analytics-api"}}
    )


@health_bp.route("/api/sync_status", methods=["GET"])
def sync_status_legacy():
    """Legacy endpoint - always ready (no more backfill in app).

    DEPRECATED: Use /api/sync/status instead.
    """
    try:
        from ...analytics.indexer.hybrid import IndexerRegistry

        indexer = IndexerRegistry.get()
        is_ready = indexer.is_ready() if indexer else True

        return jsonify(
            {
                "success": True,
                "data": {
                    "backfill_active": False,
                    "initial_backfill_done": True,
                    "timestamp": datetime.now().isoformat(),
                    "is_ready": is_ready,
                },
            }
        )
    except Exception:
        return jsonify(
            {
                "success": True,
                "data": {
                    "backfill_active": False,
                    "initial_backfill_done": True,
                    "timestamp": datetime.now().isoformat(),
                    "is_ready": True,
                },
            }
        )
