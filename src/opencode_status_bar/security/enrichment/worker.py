"""
Security Enrichment Worker - Async enrichment for parts table.

IMPORTANT: This worker NEVER reads files from disk!
All data comes from querying the parts table (populated by indexer).

Flow:
1. Query: SELECT unenriched rows FROM parts
2. Analyze: Python risk analyzer on data from DB
3. Update: UPDATE parts SET risk_score, risk_level, etc.

This is the unified path from Plan 42 - one reader (indexer), one enricher
(this worker), one table (parts).
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Protocol

from ...utils.logger import info
from ..scope import ScopeDetector


# Protocol for the database interface (allows mocking in tests)
class DatabaseProtocol(Protocol):
    def connect(self) -> Any: ...


# Protocol for the analyzer interface (allows mocking in tests)
class AnalyzerProtocol(Protocol):
    def analyze_command(self, command: str) -> Any: ...

    def analyze_file_path(self, path: str, write_mode: bool = False) -> Any: ...

    def analyze_url(self, url: str) -> Any: ...


# Security-relevant tools that should be enriched
SECURITY_TOOLS = frozenset({"bash", "read", "write", "edit", "webfetch"})


class SecurityEnrichmentWorker:
    """Async worker that enriches parts with security scores.

    IMPORTANT: This worker NEVER reads files from disk!
    All data comes from querying the parts table (populated by indexer).

    Flow:
    1. Query: SELECT unenriched rows FROM parts
    2. Analyze: Python risk analyzer on data from DB
    3. Update: UPDATE parts SET risk_score, risk_level, etc.
    """

    def __init__(
        self,
        db: DatabaseProtocol,
        analyzer: Optional[AnalyzerProtocol] = None,
        poll_interval: float = 10.0,
        batch_size: int = 500,
    ):
        """Initialize the enrichment worker.

        Args:
            db: Database instance (AnalyticsDB or compatible)
            analyzer: Risk analyzer instance. If None, uses default.
            poll_interval: Seconds to wait when no work available
            batch_size: Default batch size for enrichment
        """
        self._db = db
        self._analyzer = analyzer
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._scope_cache: dict[str, ScopeDetector] = {}

    def _get_scope_detector(self, project_root: str | None) -> ScopeDetector | None:
        """Get or create a ScopeDetector for the given project root.

        Args:
            project_root: Project root directory path

        Returns:
            ScopeDetector instance or None if project_root is None
        """
        if not project_root:
            return None
        if project_root not in self._scope_cache:
            self._scope_cache[project_root] = ScopeDetector(Path(project_root))
        return self._scope_cache[project_root]

    def _get_analyzer(self) -> AnalyzerProtocol:
        """Get the analyzer, creating default if needed."""
        if self._analyzer is None:
            # Lazy import to avoid circular dependencies
            from ..analyzer import get_risk_analyzer, analyze_command

            # Create a wrapper that provides the unified interface
            class UnifiedAnalyzer:
                def __init__(self):
                    self._risk_analyzer = get_risk_analyzer()

                def analyze_command(self, command: str) -> Any:
                    result = analyze_command(command)
                    # Convert SecurityAlert to RiskResult-like interface
                    return type(
                        "RiskResult",
                        (),
                        {
                            "score": result.score,
                            "level": result.level.value,  # Enum to string
                            "reason": result.reason,
                            "mitre_techniques": result.mitre_techniques,
                        },
                    )()

                def analyze_file_path(self, path: str, write_mode: bool = False) -> Any:
                    return self._risk_analyzer.analyze_file_path(path, write_mode)

                def analyze_url(self, url: str) -> Any:
                    return self._risk_analyzer.analyze_url(url)

            self._analyzer = UnifiedAnalyzer()
        return self._analyzer

    def is_running(self) -> bool:
        """Check if the worker is running."""
        with self._lock:
            return self._running

    def start(self) -> None:
        """Start background enrichment thread (idempotent)."""
        with self._lock:
            if self._running:
                return  # Already running, idempotent
            self._running = True
            self._thread = threading.Thread(
                target=self._enrichment_loop, daemon=True, name="SecurityEnrichment"
            )
            self._thread.start()
            info("Security enrichment worker started")

    def stop(self) -> None:
        """Stop background enrichment thread (idempotent)."""
        with self._lock:
            if not self._running:
                return  # Already stopped, idempotent
            self._running = False

        # Wait for thread to finish outside the lock
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        info("Security enrichment worker stopped")

    def _enrichment_loop(self) -> None:
        """Main loop: find unenriched parts, score them, update DB."""
        while self._running:
            try:
                enriched = self.enrich_batch(limit=self._batch_size)
                if enriched == 0:
                    time.sleep(self._poll_interval)  # Nothing to do, wait
                else:
                    time.sleep(0.05)  # More work available, continue quickly
            except Exception:
                time.sleep(self._poll_interval)  # Wait before retrying

    def enrich_batch(self, limit: int = 500) -> int:
        """Enrich a batch of unenriched parts.

        NO FILE I/O - all data from DB query!

        Args:
            limit: Maximum number of parts to enrich in this batch

        Returns:
            Number of parts enriched
        """
        conn = self._db.connect()
        analyzer = self._get_analyzer()

        # Query unenriched parts - data already in DB from indexer
        # The 'arguments' column contains the JSON with command/filePath/url
        # Join with sessions to get project_root for scope analysis
        try:
            parts = conn.execute(
                """
                SELECT p.id, p.tool_name, p.arguments, s.directory as project_root
                FROM parts p
                LEFT JOIN sessions s ON p.session_id = s.id
                WHERE p.security_enriched_at IS NULL
                  AND p.tool_name IN ('bash', 'read', 'write', 'edit', 'webfetch')
                ORDER BY p.created_at DESC
                LIMIT ?
            """,
                [limit],
            ).fetchall()
        except Exception:
            return 0

        if not parts:
            return 0

        # Compute scores using Python analyzer (no file reads!)
        updates = []
        now = datetime.now()

        for part_id, tool_name, arguments_json, project_root in parts:
            try:
                # Parse arguments JSON
                if arguments_json:
                    args = json.loads(arguments_json)
                else:
                    args = {}
            except (json.JSONDecodeError, TypeError):
                # Invalid JSON - mark as enriched with no risk
                updates.append(
                    (0, "low", "Invalid arguments JSON", "[]", now, None, None, part_id)
                )
                continue

            # Analyze based on tool type (includes scope analysis)
            result, scope_verdict, scope_resolved = self._analyze_part(
                analyzer, tool_name, args, project_root
            )

            # Collect update data
            mitre_json = json.dumps(getattr(result, "mitre_techniques", []))
            updates.append(
                (
                    result.score,
                    result.level,
                    result.reason,
                    mitre_json,
                    now,
                    scope_verdict,
                    scope_resolved,
                    part_id,
                )
            )

        # Batch UPDATE - no INSERT, just enriching existing rows
        if updates:
            conn.executemany(
                """
                UPDATE parts SET 
                    risk_score = ?, 
                    risk_level = ?, 
                    risk_reason = ?,
                    mitre_techniques = ?, 
                    security_enriched_at = ?,
                    scope_verdict = ?,
                    scope_resolved_path = ?
                WHERE id = ?
            """,
                updates,
            )

            risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for update in updates:
                risk_level = update[1]
                if risk_level in risk_counts:
                    risk_counts[risk_level] += 1

            critical = risk_counts["critical"]
            high = risk_counts["high"]
            if critical > 0 or high > 0:
                info(
                    f"[Security] Enriched {len(updates)} parts: "
                    f"{critical} critical, {high} high"
                )

        return len(updates)

    def _analyze_part(
        self,
        analyzer: AnalyzerProtocol,
        tool_name: str,
        args: dict,
        project_root: str | None = None,
    ) -> tuple[Any, str | None, str | None]:
        """Analyze a part and return risk result with scope analysis.

        Args:
            analyzer: The risk analyzer
            tool_name: Name of the tool (bash, read, write, edit, webfetch)
            args: Parsed arguments from the parts.arguments column
            project_root: Project root directory for scope analysis

        Returns:
            Tuple of (RiskResult, scope_verdict, scope_resolved_path)
        """
        # Default result for parts we can't analyze
        default_result = type(
            "RiskResult",
            (),
            {
                "score": 0,
                "level": "low",
                "reason": "No data to analyze",
                "mitre_techniques": [],
            },
        )()

        scope_verdict: str | None = None
        scope_resolved: str | None = None

        if tool_name == "bash":
            command = args.get("command", "")
            if command:
                return analyzer.analyze_command(command), scope_verdict, scope_resolved
            return default_result, scope_verdict, scope_resolved

        elif tool_name == "read":
            file_path = args.get("filePath", "")
            if file_path:
                result = analyzer.analyze_file_path(file_path, write_mode=False)
                # Add scope analysis
                scope_verdict, scope_resolved, result = self._apply_scope_analysis(
                    result, file_path, "read", project_root
                )
                return result, scope_verdict, scope_resolved
            return default_result, scope_verdict, scope_resolved

        elif tool_name in ("write", "edit"):
            file_path = args.get("filePath", "")
            if file_path:
                result = analyzer.analyze_file_path(file_path, write_mode=True)
                # Add scope analysis
                scope_verdict, scope_resolved, result = self._apply_scope_analysis(
                    result, file_path, "write", project_root
                )
                return result, scope_verdict, scope_resolved
            return default_result, scope_verdict, scope_resolved

        elif tool_name == "webfetch":
            url = args.get("url", "")
            if url:
                return analyzer.analyze_url(url), scope_verdict, scope_resolved
            return default_result, scope_verdict, scope_resolved

        return default_result, scope_verdict, scope_resolved

    def _apply_scope_analysis(
        self,
        result: Any,
        file_path: str,
        operation: str,
        project_root: str | None,
    ) -> tuple[str | None, str | None, Any]:
        """Apply scope analysis and modify result if needed.

        Args:
            result: The base risk analysis result
            file_path: File path being analyzed
            operation: 'read' or 'write'
            project_root: Project root directory

        Returns:
            Tuple of (scope_verdict, scope_resolved_path, modified_result)
        """
        if not project_root:
            return None, None, result

        detector = self._get_scope_detector(project_root)
        if not detector:
            return None, None, result

        scope_result = detector.detect(file_path, operation)
        scope_verdict = scope_result.verdict.value
        scope_resolved = scope_result.resolved_path

        # Combine scores if out of scope
        if scope_result.score_modifier > 0:
            new_score = min(100, result.score + scope_result.score_modifier)
            new_reason = f"{result.reason}; {scope_result.reason}"
            # Create new result with combined score
            result = type(
                "RiskResult",
                (),
                {
                    "score": new_score,
                    "level": result.level,
                    "reason": new_reason,
                    "mitre_techniques": getattr(result, "mitre_techniques", []),
                },
            )()

        return scope_verdict, scope_resolved, result

    def get_progress(self) -> dict:
        """Get enrichment progress stats.

        Returns:
            Dict with 'enriched', 'pending', and 'total' counts
        """
        conn = self._db.connect()
        result = conn.execute(
            """
            SELECT 
                COUNT(*) FILTER (WHERE security_enriched_at IS NOT NULL) as enriched,
                COUNT(*) FILTER (WHERE security_enriched_at IS NULL 
                    AND tool_name IN ('bash', 'read', 'write', 'edit', 'webfetch')) as pending,
                COUNT(*) as total
            FROM parts
        """
        ).fetchone()
        return {"enriched": result[0], "pending": result[1], "total": result[2]}
