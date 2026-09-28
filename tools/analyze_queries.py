#!/usr/bin/env python3
"""
DuckDB Query Analyzer

Analyzes slow queries and provides optimization recommendations.
Runs EXPLAIN ANALYZE on common queries to identify bottlenecks.

Usage:
    python tools/analyze_queries.py [--db PATH]
"""

import sys
import duckdb
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from opencode_status_bar.analytics.db import get_db_path
except ImportError:

    def get_db_path():
        from pathlib import Path

        return Path.home() / ".config" / "opencode-status-bar" / "analytics.duckdb"


def analyze_query(conn: duckdb.DuckDBPyConnection, name: str, query: str) -> None:
    print(f"\n{'=' * 80}")
    print(f"QUERY: {name}")
    print(f"{'=' * 80}")
    print(f"\n{query}\n")

    explain_query = f"EXPLAIN ANALYZE {query}"

    try:
        result = conn.execute(explain_query).fetchall()

        print("EXECUTION PLAN:")
        for row in result:
            if row:
                print(row[1] if len(row) > 1 else row[0])

        actual_query_result = conn.execute(query).fetchall()
        row_count = len(actual_query_result)
        print(f"\nRESULT: {row_count} rows")

    except Exception as e:
        print(f"ERROR: {e}")


def get_common_queries() -> List[Tuple[str, str]]:
    return [
        (
            "Root traces (30 days)",
            """
            SELECT 
                t.trace_id,
                t.session_id,
                t.started_at,
                s.title
            FROM agent_traces t
            LEFT JOIN sessions s ON t.session_id = s.id
            WHERE t.parent_trace_id IS NULL
              AND t.trace_id LIKE 'root_%'
              AND t.trace_id NOT LIKE '%_seg%'
              AND t.started_at >= CURRENT_TIMESTAMP - INTERVAL 30 DAY
            ORDER BY t.started_at DESC
            """,
        ),
        (
            "Session messages (no pagination)",
            """
            SELECT 
                m.id,
                m.session_id,
                m.created_at,
                m.role,
                (SELECT p.content FROM parts p 
                 WHERE p.message_id = m.id AND p.part_type = 'text' 
                 LIMIT 1) as content
            FROM messages m
            WHERE m.session_id IN (
                SELECT id FROM sessions 
                ORDER BY created_at DESC 
                LIMIT 10
            )
            ORDER BY m.session_id, m.created_at ASC
            """,
        ),
        (
            "Token aggregation by session",
            """
            SELECT 
                session_id,
                COALESCE(SUM(tokens_input), 0) as tokens_in,
                COALESCE(SUM(tokens_output), 0) as tokens_out,
                COALESCE(SUM(tokens_cache_read), 0) as cache_read
            FROM messages
            WHERE session_id IN (
                SELECT id FROM sessions 
                ORDER BY created_at DESC 
                LIMIT 100
            )
            GROUP BY session_id
            """,
        ),
        (
            "Tool calls by session",
            """
            SELECT 
                p.session_id,
                p.tool_name,
                COUNT(*) as call_count,
                AVG(p.duration_ms) as avg_duration_ms
            FROM parts p
            WHERE p.part_type = 'tool_use'
              AND p.session_id IN (
                  SELECT id FROM sessions 
                  ORDER BY created_at DESC 
                  LIMIT 50
              )
            GROUP BY p.session_id, p.tool_name
            ORDER BY call_count DESC
            """,
        ),
        (
            "Check index usage on parts.session_id",
            """
            SELECT COUNT(*) 
            FROM parts 
            WHERE session_id = (SELECT id FROM sessions LIMIT 1)
            """,
        ),
    ]


def check_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    print(f"\n{'=' * 80}")
    print("INDEX CHECK")
    print(f"{'=' * 80}\n")

    tables = ["sessions", "messages", "parts", "agent_traces"]

    for table in tables:
        try:
            result = conn.execute(f"PRAGMA show_tables").fetchall()
            if not any(table in str(row) for row in result):
                print(f"❌ Table {table} not found")
                continue

            print(f"\n{table}:")
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  Rows: {row_count:,}")

        except Exception as e:
            print(f"  Error: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze DuckDB queries")
    parser.add_argument(
        "--db", type=str, help="Database path (default: analytics.duckdb)"
    )

    args = parser.parse_args()

    db_path = args.db or str(get_db_path())

    print(f"Opening database: {db_path}")

    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        print("Run the menubar app first to create the database.")
        sys.exit(1)

    conn = duckdb.connect(db_path, read_only=True)

    check_indexes(conn)

    for name, query in get_common_queries():
        analyze_query(conn, name, query)

    conn.close()

    print(f"\n{'=' * 80}")
    print("ANALYSIS COMPLETE")
    print(f"{'=' * 80}")
    print("\nRecommendations will be shown above in EXPLAIN ANALYZE output.")


if __name__ == "__main__":
    main()
