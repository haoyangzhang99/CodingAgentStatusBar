#!/usr/bin/env python3
"""
Bulk Security Enrichment for Backfill.

Enriches historical parts during backfill to avoid slow startup.
This runs synchronously during backfill (app must be stopped) and processes
all unenriched parts in large batches for maximum performance.
"""

import sys
import time
from pathlib import Path

# Add src to path for opencode_status_bar imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add scripts to path for config imports
sys.path.insert(0, str(Path(__file__).parent))

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.security.enrichment.worker import SecurityEnrichmentWorker
from opencode_status_bar.utils.logger import info
from config import DEFAULT_DB_PATH

BATCH_SLEEP_SECONDS = 0.1
PROGRESS_LOG_INTERVAL = 5


def bulk_enrich(db: AnalyticsDB, batch_size: int = 1000) -> dict:
    """Enrich all unenriched parts in bulk (for backfill)."""
    info("[BulkEnrichment] Starting bulk security enrichment...")

    worker = SecurityEnrichmentWorker(db=db, batch_size=batch_size)

    total_enriched = 0
    start_time = time.time()
    batch_count = 0

    while True:
        batch_start = time.time()
        enriched = worker.enrich_batch(limit=batch_size)

        if enriched == 0:
            break

        batch_count += 1
        total_enriched += enriched
        batch_elapsed = time.time() - batch_start
        enriched / batch_elapsed if batch_elapsed > 0 else 0

        if batch_count % PROGRESS_LOG_INTERVAL == 0:
            elapsed = time.time() - start_time
            overall_rate = total_enriched / elapsed if elapsed > 0 else 0
            info(
                f"[BulkEnrichment] {total_enriched:,} parts enriched "
                f"({overall_rate:.0f} parts/sec, batch {batch_count})"
            )

        time.sleep(BATCH_SLEEP_SECONDS)

    elapsed = time.time() - start_time
    rate = total_enriched / elapsed if elapsed > 0 else 0

    if total_enriched > 0:
        info(
            f"[BulkEnrichment] Complete: {total_enriched:,} parts in "
            f"{elapsed:.1f}s ({rate:.0f} parts/sec)"
        )
    else:
        info("[BulkEnrichment] No unenriched parts found (already done)")

    return {
        "enriched": total_enriched,
        "duration_seconds": elapsed,
        "rate": rate,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("OpenCode Status Bar - Bulk Security Enrichment")
    print("=" * 60)

    db_path = DEFAULT_DB_PATH

    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        print("Run 'make backfill' first to load data.")
        sys.exit(1)

    print(f"Database: {db_path}")
    print()

    db = AnalyticsDB(db_path)
    db.connect()

    try:
        stats = bulk_enrich(db, batch_size=1000)

        print()
        print("=" * 60)
        print("Enrichment Summary")
        print("=" * 60)
        print(f"Parts enriched: {stats['enriched']:,}")
        print(f"Duration: {stats['duration_seconds']:.1f}s")
        print(f"Rate: {stats['rate']:.0f} parts/sec")
        print("=" * 60)
    finally:
        db.close()

    sys.exit(0)
