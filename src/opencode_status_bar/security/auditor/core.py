"""
Security Auditor - Query-only service for security data

This auditor queries the `parts` table which is enriched by the
SecurityEnrichmentWorker with risk scores. It no longer scans files
or manages its own database tables.

The public API is preserved for backwards compatibility.
"""

import threading
from typing import Any, Dict, List, Optional

from ..db import (
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)
from ..sequences import SequenceMatch
from ..correlator import Correlation
from ...analytics.db import AnalyticsDB
from ...utils.logger import info

from ._edr_handler import EDRHandler


class SecurityAuditor:
    """Query-only security auditor for parts table.

    This class provides the same public API as the original auditor,
    but queries the unified `parts` table instead of separate
    security_* tables. The enrichment is handled by SecurityEnrichmentWorker.
    """

    def __init__(self, db: Optional[AnalyticsDB] = None):
        """Initialize the auditor.

        Args:
            db: Optional AnalyticsDB instance. Creates one if not provided.
        """
        self._db = db or AnalyticsDB()
        self._owns_db = db is None  # Track if we created the DB
        self._lock = threading.Lock()
        self._running = False
        self._thread = None  # Kept for backwards compatibility

        # EDR handler (kept for sequence/correlation analysis)
        self._edr_handler = EDRHandler(
            buffer_size=100,
            correlator_buffer_size=200,
            window_seconds=300.0,
            max_recent=50,
        )

        # Stats cache
        self._stats: Dict[str, Any] = self._load_stats()

        info("Security auditor initialized (query-only mode)")

    def _load_stats(self) -> Dict[str, Any]:
        """Load stats from parts table."""
        conn = self._db.connect()
        try:
            result = conn.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE security_enriched_at IS NOT NULL) as total_scanned,
                    COUNT(*) FILTER (WHERE tool_name = 'bash' AND security_enriched_at IS NOT NULL) as total_commands,
                    COUNT(*) FILTER (WHERE tool_name = 'read' AND security_enriched_at IS NOT NULL) as total_reads,
                    COUNT(*) FILTER (WHERE tool_name IN ('write', 'edit') AND security_enriched_at IS NOT NULL) as total_writes,
                    COUNT(*) FILTER (WHERE tool_name = 'webfetch' AND security_enriched_at IS NOT NULL) as total_webfetches,
                    COUNT(*) FILTER (WHERE risk_level = 'critical') as critical,
                    COUNT(*) FILTER (WHERE risk_level = 'high') as high,
                    COUNT(*) FILTER (WHERE risk_level = 'medium') as medium,
                    COUNT(*) FILTER (WHERE risk_level = 'low') as low,
                    MAX(security_enriched_at) as last_scan,
                    COUNT(*) FILTER (WHERE scope_verdict = 'in_scope') as scope_in_scope,
                    COUNT(*) FILTER (WHERE scope_verdict = 'out_of_scope_allowed') as scope_allowed,
                    COUNT(*) FILTER (WHERE scope_verdict = 'out_of_scope_neutral') as scope_neutral,
                    COUNT(*) FILTER (WHERE scope_verdict = 'out_of_scope_suspicious') as scope_suspicious,
                    COUNT(*) FILTER (WHERE scope_verdict = 'out_of_scope_sensitive') as scope_sensitive
                FROM parts
            """).fetchone()

            return {
                "total_scanned": result[0] or 0,
                "total_commands": result[1] or 0,
                "total_reads": result[2] or 0,
                "total_writes": result[3] or 0,
                "total_webfetches": result[4] or 0,
                "critical": result[5] or 0,
                "high": result[6] or 0,
                "medium": result[7] or 0,
                "low": result[8] or 0,
                "last_scan": result[9].isoformat() if result[9] else None,
                "sequences_detected": 0,
                "correlations_detected": 0,
                "scope_in_scope": result[10] or 0,
                "scope_allowed": result[11] or 0,
                "scope_neutral": result[12] or 0,
                "scope_suspicious": result[13] or 0,
                "scope_sensitive": result[14] or 0,
            }
        except Exception:
            return {
                "total_scanned": 0,
                "total_commands": 0,
                "total_reads": 0,
                "total_writes": 0,
                "total_webfetches": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "last_scan": None,
                "sequences_detected": 0,
                "correlations_detected": 0,
            }

    def start(self):
        """Start the auditor (no-op in query-only mode)."""
        self._running = True
        info("Security auditor started (query-only mode)")

    def stop(self):
        """Stop the auditor."""
        self._running = False
        if self._owns_db:
            self._db.close()
        info("Security auditor stopped")

    # ===== Public API =====

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        # Refresh stats from DB
        self._stats = self._load_stats()
        with self._lock:
            return self._stats.copy()

    def get_critical_commands(self, limit: int = 20) -> List[AuditedCommand]:
        """Get recent critical and high risk commands."""
        return self.get_commands_by_level(
            "critical", limit // 2
        ) + self.get_commands_by_level("high", limit // 2)

    def get_commands_by_level(
        self, level: str, limit: int = 50
    ) -> List[AuditedCommand]:
        """Get commands by risk level."""
        levels = [level] if isinstance(level, str) else level
        conn = self._db.connect()

        # Build IN clause for levels
        placeholders = ",".join(["?" for _ in levels])

        rows = conn.execute(
            f"""
            SELECT 
                id, id as file_id, session_id, tool_name,
                arguments->>'$.command' as command,
                risk_score, risk_level, risk_reason,
                EXTRACT(EPOCH FROM created_at)::BIGINT as timestamp,
                security_enriched_at::VARCHAR as scanned_at,
                COALESCE(mitre_techniques, '[]') as mitre_techniques
            FROM parts
            WHERE tool_name = 'bash'
              AND risk_level IN ({placeholders})
              AND security_enriched_at IS NOT NULL
            ORDER BY risk_score DESC, created_at DESC
            LIMIT ?
        """,
            levels + [limit],
        ).fetchall()

        return [
            AuditedCommand(
                id=i,
                file_id=row[1] or "",
                session_id=row[2] or "",
                tool=row[3] or "bash",
                command=row[4] or "",
                risk_score=row[5] or 0,
                risk_level=row[6] or "low",
                risk_reason=row[7] or "",
                timestamp=row[8] or 0,
                scanned_at=row[9] or "",
                mitre_techniques=row[10] or "[]",
            )
            for i, row in enumerate(rows)
        ]

    def get_all_commands(
        self, limit: int = 100, offset: int = 0
    ) -> List[AuditedCommand]:
        """Get all commands with pagination."""
        conn = self._db.connect()

        rows = conn.execute(
            """
            SELECT 
                id, id as file_id, session_id, tool_name,
                arguments->>'$.command' as command,
                risk_score, risk_level, risk_reason,
                EXTRACT(EPOCH FROM created_at)::BIGINT as timestamp,
                security_enriched_at::VARCHAR as scanned_at,
                COALESCE(mitre_techniques, '[]') as mitre_techniques
            FROM parts
            WHERE tool_name = 'bash'
              AND security_enriched_at IS NOT NULL
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """,
            [limit, offset],
        ).fetchall()

        return [
            AuditedCommand(
                id=i,
                file_id=row[1] or "",
                session_id=row[2] or "",
                tool=row[3] or "bash",
                command=row[4] or "",
                risk_score=row[5] or 0,
                risk_level=row[6] or "low",
                risk_reason=row[7] or "",
                timestamp=row[8] or 0,
                scanned_at=row[9] or "",
                mitre_techniques=row[10] or "[]",
            )
            for i, row in enumerate(rows)
        ]

    def get_sensitive_reads(self, limit: int = 20) -> List[AuditedFileRead]:
        """Get recent sensitive file reads."""
        return self._get_reads_by_level(["critical", "high"], limit)

    def get_all_reads(self, limit: int = 10000) -> List[AuditedFileRead]:
        """Get all file reads."""
        return self._get_reads_by_level(["critical", "high", "medium", "low"], limit)

    def _get_reads_by_level(
        self, levels: List[str], limit: int
    ) -> List[AuditedFileRead]:
        """Get file reads by risk levels."""
        conn = self._db.connect()
        placeholders = ",".join(["?" for _ in levels])

        rows = conn.execute(
            f"""
            SELECT 
                id, id as file_id, session_id,
                arguments->>'$.filePath' as file_path,
                risk_score, risk_level, risk_reason,
                EXTRACT(EPOCH FROM created_at)::BIGINT as timestamp,
                security_enriched_at::VARCHAR as scanned_at,
                COALESCE(mitre_techniques, '[]') as mitre_techniques,
                scope_verdict,
                scope_resolved_path
            FROM parts
            WHERE tool_name = 'read'
              AND risk_level IN ({placeholders})
              AND security_enriched_at IS NOT NULL
            ORDER BY risk_score DESC, created_at DESC
            LIMIT ?
        """,
            levels + [limit],
        ).fetchall()

        return [
            AuditedFileRead(
                id=i,
                file_id=row[1] or "",
                session_id=row[2] or "",
                file_path=row[3] or "",
                risk_score=row[4] or 0,
                risk_level=row[5] or "low",
                risk_reason=row[6] or "",
                timestamp=row[7] or 0,
                scanned_at=row[8] or "",
                mitre_techniques=row[9] or "[]",
                scope_verdict=row[10] or "",
                scope_resolved_path=row[11] or "",
            )
            for i, row in enumerate(rows)
        ]

    def get_sensitive_writes(self, limit: int = 20) -> List[AuditedFileWrite]:
        """Get recent sensitive file writes."""
        return self._get_writes_by_level(["critical", "high"], limit)

    def get_all_writes(self, limit: int = 10000) -> List[AuditedFileWrite]:
        """Get all file writes."""
        return self._get_writes_by_level(["critical", "high", "medium", "low"], limit)

    def _get_writes_by_level(
        self, levels: List[str], limit: int
    ) -> List[AuditedFileWrite]:
        """Get file writes by risk levels."""
        conn = self._db.connect()
        placeholders = ",".join(["?" for _ in levels])

        rows = conn.execute(
            f"""
            SELECT 
                id, id as file_id, session_id, tool_name,
                arguments->>'$.filePath' as file_path,
                risk_score, risk_level, risk_reason,
                EXTRACT(EPOCH FROM created_at)::BIGINT as timestamp,
                security_enriched_at::VARCHAR as scanned_at,
                COALESCE(mitre_techniques, '[]') as mitre_techniques,
                scope_verdict,
                scope_resolved_path
            FROM parts
            WHERE tool_name IN ('write', 'edit')
              AND risk_level IN ({placeholders})
              AND security_enriched_at IS NOT NULL
            ORDER BY risk_score DESC, created_at DESC
            LIMIT ?
        """,
            levels + [limit],
        ).fetchall()

        return [
            AuditedFileWrite(
                id=i,
                file_id=row[1] or "",
                session_id=row[2] or "",
                file_path=row[4] or "",
                operation=row[3] or "write",
                risk_score=row[5] or 0,
                risk_level=row[6] or "low",
                risk_reason=row[7] or "",
                timestamp=row[8] or 0,
                scanned_at=row[9] or "",
                mitre_techniques=row[10] or "[]",
                scope_verdict=row[11] or "",
                scope_resolved_path=row[12] or "",
            )
            for i, row in enumerate(rows)
        ]

    def get_risky_webfetches(self, limit: int = 20) -> List[AuditedWebFetch]:
        """Get recent risky webfetch operations."""
        return self._get_webfetches_by_level(["critical", "high"], limit)

    def get_all_webfetches(self, limit: int = 10000) -> List[AuditedWebFetch]:
        """Get all webfetches."""
        return self._get_webfetches_by_level(
            ["critical", "high", "medium", "low"], limit
        )

    def _get_webfetches_by_level(
        self, levels: List[str], limit: int
    ) -> List[AuditedWebFetch]:
        """Get webfetches by risk levels."""
        conn = self._db.connect()
        placeholders = ",".join(["?" for _ in levels])

        rows = conn.execute(
            f"""
            SELECT 
                id, id as file_id, session_id,
                arguments->>'$.url' as url,
                risk_score, risk_level, risk_reason,
                EXTRACT(EPOCH FROM created_at)::BIGINT as timestamp,
                security_enriched_at::VARCHAR as scanned_at,
                COALESCE(mitre_techniques, '[]') as mitre_techniques
            FROM parts
            WHERE tool_name = 'webfetch'
              AND risk_level IN ({placeholders})
              AND security_enriched_at IS NOT NULL
            ORDER BY risk_score DESC, created_at DESC
            LIMIT ?
        """,
            levels + [limit],
        ).fetchall()

        return [
            AuditedWebFetch(
                id=i,
                file_id=row[1] or "",
                session_id=row[2] or "",
                url=row[3] or "",
                risk_score=row[4] or 0,
                risk_level=row[5] or "low",
                risk_reason=row[6] or "",
                timestamp=row[7] or 0,
                scanned_at=row[8] or "",
                mitre_techniques=row[9] or "[]",
            )
            for i, row in enumerate(rows)
        ]

    # ===== EDR API (kept for backwards compatibility) =====

    def get_recent_sequences(self) -> List[SequenceMatch]:
        """Get recently detected kill chain sequences."""
        return self._edr_handler.get_recent_sequences()

    def get_recent_correlations(self) -> List[Correlation]:
        """Get recently detected event correlations."""
        return self._edr_handler.get_recent_correlations()

    def get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all tracked events for a session."""
        return self._edr_handler.get_session_events(session_id)

    def get_edr_stats(self) -> Dict[str, Any]:
        """Get EDR-specific statistics."""
        edr_stats = self._edr_handler.get_stats()
        with self._lock:
            return {
                "sequences_detected": self._stats.get("sequences_detected", 0)
                + edr_stats["sequences_detected"],
                "correlations_detected": self._stats.get("correlations_detected", 0)
                + edr_stats["correlations_detected"],
                "active_sessions": edr_stats["active_sessions"],
                "recent_sequences": edr_stats["recent_sequences"],
                "recent_correlations": edr_stats["recent_correlations"],
            }

    def clear_edr_buffers(self) -> None:
        """Clear all EDR analyzer buffers."""
        self._edr_handler.clear_all()

    # ===== Legacy EDR properties for backwards compatibility =====

    @property
    def _sequence_analyzer(self):
        """Access to sequence analyzer for backwards compatibility."""
        return self._edr_handler._sequence_analyzer

    @property
    def _event_correlator(self):
        """Access to event correlator for backwards compatibility."""
        return self._edr_handler._event_correlator

    @property
    def _recent_sequences(self) -> List[SequenceMatch]:
        """Access to recent sequences for backwards compatibility."""
        return self._edr_handler._recent_sequences

    @property
    def _recent_correlations(self) -> List[Correlation]:
        """Access to recent correlations for backwards compatibility."""
        return self._edr_handler._recent_correlations

    @property
    def _max_recent(self) -> int:
        """Access to max_recent for backwards compatibility."""
        return self._edr_handler._max_recent


# Global instance
_auditor: Optional[SecurityAuditor] = None


def get_auditor() -> SecurityAuditor:
    """Get or create the global auditor instance."""
    global _auditor
    if _auditor is None:
        _auditor = SecurityAuditor()
    return _auditor


def start_auditor():
    """Start the security auditor."""
    get_auditor().start()


def stop_auditor():
    """Stop the security auditor."""
    global _auditor
    if _auditor:
        _auditor.stop()
        _auditor = None
