#!/usr/bin/env python3
"""
Bulk backfill script for OpenCode Status Bar.

Loads all historical data into the analytics database.
Must be run when the app is NOT running (DB must not be locked).

Usage:
    make backfill
    # or
    uv run python scripts/backfill.py
"""

import sys
import time
from pathlib import Path

# Add src to path for opencode_status_bar imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add scripts to path for local bulk_loader import
sys.path.insert(0, str(Path(__file__).parent))

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.indexer.trace_builder import TraceBuilder
from opencode_status_bar.analytics.materialization import MaterializedTableManager
from bulk_loader import BulkLoader
from bulk_enrichment import bulk_enrich
from config import DEFAULT_DB_PATH, DEFAULT_STORAGE_PATH


OPENCODE_STORAGE = DEFAULT_STORAGE_PATH


def check_db_lock(db_path: Path) -> bool:
    """Return True if DB is available, False if locked."""
    import duckdb

    try:
        conn = duckdb.connect(str(db_path))
        conn.execute("SELECT 1")
        conn.close()
        return True
    except duckdb.IOException:
        return False


def run_backfill() -> int:
    print("=" * 60)
    print("OpenCode Status Bar - Bulk Backfill")
    print("=" * 60)

    db_path = DEFAULT_DB_PATH

    if not check_db_lock(db_path):
        print()
        print("ERROR: Database is locked!")
        print()
        print("The app is probably running. Stop it first:")
        print("  pkill -f opencode_status_bar")
        print()
        print("Then run backfill again:")
        print("  make backfill")
        print()
        return 1

    if not OPENCODE_STORAGE.exists():
        print(f"ERROR: Storage path not found: {OPENCODE_STORAGE}")
        return 1

    print(f"Storage: {OPENCODE_STORAGE}")
    print(f"Database: {db_path}")
    print()

    db = AnalyticsDB(db_path)
    db.connect()

    bulk_loader = BulkLoader(db, OPENCODE_STORAGE)
    trace_builder = TraceBuilder(db)
    materialization_manager = MaterializedTableManager(db)

    start_time = time.time()
    time.time()

    counts = bulk_loader.count_files()
    total = sum(counts.values())
    print(
        f"Files to load: {total:,} ({counts['session']:,} sessions, {counts['message']:,} messages, {counts['part']:,} parts)"
    )
    print("-" * 40)

    print("Loading sessions...", flush=True)
    results = {"session": bulk_loader.load_sessions()}
    print(
        f"  Sessions: {results['session'].files_loaded:,} in {results['session'].duration_seconds:.1f}s"
    )

    print("Loading messages...", flush=True)
    results["message"] = bulk_loader.load_messages()
    print(
        f"  Messages: {results['message'].files_loaded:,} in {results['message'].duration_seconds:.1f}s"
    )

    print("Loading parts (this may take a while)...", flush=True)
    results["part"] = bulk_loader.load_parts()
    print(
        f"  Parts: {results['part'].files_loaded:,} in {results['part'].duration_seconds:.1f}s"
    )

    print("Loading file operations...", flush=True)
    results["file_operation"] = bulk_loader.load_file_operations()
    print(
        f"  File operations: {results['file_operation'].files_loaded:,} in {results['file_operation'].duration_seconds:.1f}s"
    )

    print("Loading step events...", flush=True)
    results["step_event"] = bulk_loader.load_step_events()
    print(
        f"  Step events: {results['step_event'].files_loaded:,} in {results['step_event'].duration_seconds:.1f}s"
    )

    print("Loading patches...", flush=True)
    results["patch"] = bulk_loader.load_patches()
    print(
        f"  Patches: {results['patch'].files_loaded:,} in {results['patch'].duration_seconds:.1f}s"
    )

    print("Enriching file operations with diff stats...", flush=True)
    enriched_count = bulk_loader.enrich_file_operations_with_diffs()
    if enriched_count > 0:
        print(f"  Enriched {enriched_count:,} file operations with additions/deletions")

        conn = db.connect()
        conn.execute("""
            UPDATE sessions
            SET 
                additions = (SELECT COALESCE(SUM(additions), 0) FROM file_operations WHERE session_id = sessions.id),
                deletions = (SELECT COALESCE(SUM(deletions), 0) FROM file_operations WHERE session_id = sessions.id)
            WHERE additions = 0 AND deletions = 0
              AND id IN (SELECT DISTINCT session_id FROM file_operations WHERE additions > 0 OR deletions > 0)
        """)
        print("  Updated session totals from file operations")
    else:
        print("  No diff stats found")

    total_loaded = sum(r.files_loaded for r in results.values())
    total_time = sum(r.duration_seconds for r in results.values())

    print("-" * 40)
    print(f"Bulk load complete: {total_loaded:,} files in {total_time:.1f}s")
    print()

    print("Flushing database to disk...")
    print("-" * 40)
    conn = db.connect()
    conn.execute("CHECKPOINT")
    print("  ✓ Database flushed (memory freed)")
    db.close()
    print("  ✓ Connection closed")
    db.connect()
    print("  ✓ Connection reopened")
    print()

    print("Post-processing...")
    print("-" * 40)

    print("  Initializing performance indexes...", flush=True)
    materialization_manager.initialize_indexes()
    print("  ✓ Indexes created")

    updated_agents = trace_builder.update_root_trace_agents()
    if updated_agents > 0:
        print(f"  Updated {updated_agents} root trace agents")

    resolved = trace_builder.resolve_parent_traces()
    if resolved > 0:
        print(f"  Resolved {resolved} parent traces")

    backfilled = trace_builder.backfill_missing_tokens()
    if backfilled > 0:
        print(f"  Backfilled tokens for {backfilled} traces")

    print("  Building materialized tables...", flush=True)
    try:
        result_exchanges = materialization_manager.refresh_exchanges(incremental=False)
        print(
            f"    Exchanges: {result_exchanges['rows_added']:,} rows in {result_exchanges['duration_ms']}ms"
        )

        result_traces = materialization_manager.refresh_exchange_traces()
        print(
            f"    Exchange traces: {result_traces['rows_added']:,} rows in {result_traces['duration_ms']}ms"
        )

        result_sessions = materialization_manager.refresh_session_traces(
            incremental=False
        )
        print(
            f"    Session traces: {result_sessions['rows_added']:,} rows in {result_sessions['duration_ms']}ms"
        )
    except Exception as e:
        print(f"  Warning: Failed to build materialized tables: {e}")

    print("-" * 40)

    print()
    print("Security enrichment (bulk mode)...", flush=True)
    print("-" * 40)

    enrichment_stats = bulk_enrich(db, batch_size=1000)
    print(
        f"  Enriched: {enrichment_stats['enriched']:,} parts in "
        f"{enrichment_stats['duration_seconds']:.1f}s "
        f"({enrichment_stats['rate']:.0f} parts/sec)"
    )
    print("-" * 40)

    db.close()

    total_elapsed = time.time() - start_time
    print()
    print(f"Backfill complete in {total_elapsed:.1f}s")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(run_backfill())
