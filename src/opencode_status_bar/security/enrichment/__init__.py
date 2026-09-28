"""
Security Enrichment Module - Async enrichment for parts table.

This module provides the SecurityEnrichmentWorker which:
1. NEVER reads files from disk - only queries the parts table
2. Enriches parts with risk_score, risk_level, risk_reason
3. Runs asynchronously in background
4. Can resume after restart (tracks enriched via security_enriched_at column)

Usage:
    from opencode_status_bar.security.enrichment import SecurityEnrichmentWorker

    worker = SecurityEnrichmentWorker(db=analytics_db)
    worker.start()  # Starts background enrichment

    # Later...
    worker.stop()   # Stops background enrichment
"""

from .worker import SecurityEnrichmentWorker

__all__ = ["SecurityEnrichmentWorker"]
