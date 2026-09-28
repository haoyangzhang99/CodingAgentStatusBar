"""
Security Routes - Security audit data endpoints.

Exposes security auditor data via API to avoid DuckDB lock conflicts
when the dashboard queries security data.
"""

from flask import Blueprint, jsonify, request

from ...utils.logger import error

security_bp = Blueprint("security", __name__)


@security_bp.route("/api/security", methods=["GET"])
def get_security_data():
    """Get security audit data for dashboard.

    Returns formatted data ready for dashboard consumption:
    - stats: Risk level counts
    - commands: List of audited commands
    - files: Combined reads and writes
    - critical_items: High and critical risk items

    Query params:
    - row_limit: Max rows for commands table (default: 100)
    - top_limit: Max items for top lists (default: 10)
    """
    try:
        from ...security.auditor import get_auditor

        row_limit = request.args.get("row_limit", 100, type=int)
        top_limit = request.args.get("top_limit", 10, type=int)

        auditor = get_auditor()
        stats = auditor.get_stats()

        # Fetch all data
        commands = auditor.get_all_commands(limit=row_limit)
        reads = auditor.get_all_reads(limit=top_limit)
        writes = auditor.get_all_writes(limit=top_limit)

        # Get critical/high items
        critical_cmds = auditor.get_critical_commands(limit=row_limit)
        high_cmds = auditor.get_commands_by_level("high", limit=row_limit)
        sensitive_reads = auditor.get_sensitive_reads(limit=top_limit)
        sensitive_writes = auditor.get_sensitive_writes(limit=top_limit)
        risky_fetches = auditor.get_risky_webfetches(limit=top_limit)

        # Build critical items list
        critical_items = []
        for c in critical_cmds + high_cmds:
            critical_items.append(
                {
                    "type": "COMMAND",
                    "details": c.command,
                    "risk": c.risk_level,
                    "reason": c.risk_reason,
                    "score": c.risk_score,
                }
            )
        for r in sensitive_reads:
            critical_items.append(
                {
                    "type": "READ",
                    "details": r.file_path,
                    "risk": r.risk_level,
                    "reason": r.risk_reason,
                    "score": r.risk_score,
                    "scope_verdict": r.scope_verdict,
                }
            )
        for w in sensitive_writes:
            critical_items.append(
                {
                    "type": "WRITE",
                    "details": w.file_path,
                    "risk": w.risk_level,
                    "reason": w.risk_reason,
                    "score": w.risk_score,
                    "scope_verdict": w.scope_verdict,
                }
            )
        for f in risky_fetches:
            critical_items.append(
                {
                    "type": "WEBFETCH",
                    "details": f.url,
                    "risk": f.risk_level,
                    "reason": f.risk_reason,
                    "score": f.risk_score,
                }
            )

        # Combine file operations
        files = []
        for r in reads:
            files.append(
                {
                    "operation": "READ",
                    "path": r.file_path,
                    "risk": r.risk_level,
                    "score": r.risk_score,
                    "reason": r.risk_reason,
                    "scope_verdict": r.scope_verdict,
                    "scope_resolved_path": r.scope_resolved_path,
                }
            )
        for w in writes:
            files.append(
                {
                    "operation": "WRITE",
                    "path": w.file_path,
                    "risk": w.risk_level,
                    "reason": w.risk_reason,
                    "score": w.risk_score,
                    "scope_verdict": w.scope_verdict,
                    "scope_resolved_path": w.scope_resolved_path,
                }
            )

        files.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Format commands
        cmds = []
        for c in commands:
            cmds.append(
                {
                    "command": c.command,
                    "risk": c.risk_level,
                    "score": c.risk_score,
                    "reason": c.risk_reason,
                }
            )

        data = {
            "stats": stats,
            "commands": cmds,
            "files": files[:row_limit],
            "critical_items": critical_items,
        }

        return jsonify({"success": True, "data": data})

    except Exception as e:
        error(f"[API] Error getting security data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
