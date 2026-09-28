#!/usr/bin/env python3
"""Refresh materialized analytics tables manually or via cron."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.materialization import MaterializedTableManager


def main():
    parser = argparse.ArgumentParser(
        description="Refresh materialized analytics tables"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Incremental refresh (only changed sessions)",
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Refresh specific session only",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=["exchanges", "exchange_traces", "session_traces", "all"],
        default=["all"],
        help="Which tables to refresh",
    )

    args = parser.parse_args()

    db = AnalyticsDB()
    manager = MaterializedTableManager(db)

    results = {}

    if "all" in args.tables:
        tables = ["exchanges", "exchange_traces", "session_traces"]
    else:
        tables = args.tables

    print(f"Refreshing tables: {', '.join(tables)}")
    print(f"Mode: {'incremental' if args.incremental else 'full'}")
    if args.session:
        print(f"Session: {args.session}")

    if "exchanges" in tables:
        print("\n[1/3] Refreshing exchanges...")
        result = manager.refresh_exchanges(
            session_id=args.session, incremental=args.incremental
        )
        results["exchanges"] = result
        print(f"  ✓ {result['rows_added']} rows | {result['duration_ms']}ms")

    if "exchange_traces" in tables:
        print("\n[2/3] Refreshing exchange_traces...")
        result = manager.refresh_exchange_traces(session_id=args.session)
        results["exchange_traces"] = result
        print(f"  ✓ {result['rows_added']} rows | {result['duration_ms']}ms")

    if "session_traces" in tables:
        print("\n[3/3] Refreshing session_traces...")
        result = manager.refresh_session_traces(
            session_id=args.session, incremental=args.incremental
        )
        results["session_traces"] = result
        print(f"  ✓ {result['rows_added']} rows | {result['duration_ms']}ms")

    print("\n✨ Refresh complete!")
    print(f"\nTotal duration: {sum(r['duration_ms'] for r in results.values())}ms")


if __name__ == "__main__":
    main()
