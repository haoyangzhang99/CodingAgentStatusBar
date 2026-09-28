"""High-performance materialized table management.

Manages materialized analytics tables with incremental refresh capabilities.
Replaces batch TraceBuilder.build_*() methods with real-time incremental updates.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import time

from .db import AnalyticsDB
from ..utils.logger import info


class MaterializedTableManager:
    """Manages materialized analytics tables with incremental refresh."""

    def __init__(self, db: AnalyticsDB):
        self._db = db
        self._last_refresh: dict[str, datetime] = {}
        self._sql_dir = Path(__file__).parent / "sql"

    def initialize_indexes(self) -> None:
        """Create all performance indexes on first run."""
        conn = self._db.connect()

        conn.execute("SET memory_limit='8GB'")
        conn.execute("SET preserve_insertion_order=false")

        indexes_sql = (self._sql_dir / "indexes.sql").read_text()
        conn.execute(indexes_sql)
        info("[Materialization] Initialized performance indexes")

    def refresh_exchanges(
        self, session_id: Optional[str] = None, incremental: bool = True
    ) -> dict:
        """Refresh exchanges table (full or incremental).

        Args:
            session_id: Optional session to refresh (incremental)
            incremental: If True, only refresh changed sessions

        Returns:
            Dict with stats (rows_added, rows_updated, duration_ms)
        """
        conn = self._db.connect()
        start = time.time()

        if session_id:
            info(f"[Materialization] Incremental refresh exchanges for {session_id}")

            conn.execute("DELETE FROM exchanges WHERE session_id = ?", [session_id])
            inserted = self._build_exchanges_for_session(conn, session_id)

            duration_ms = int((time.time() - start) * 1000)

            return {
                "type": "incremental",
                "session_id": session_id,
                "rows_added": inserted,
                "duration_ms": duration_ms,
            }

        elif incremental:
            last_refresh = self._last_refresh.get(
                "exchanges", datetime.now() - timedelta(hours=1)
            )

            info(
                f"[Materialization] Incremental refresh exchanges since {last_refresh}"
            )

            changed_sessions = conn.execute(
                """
                SELECT DISTINCT session_id 
                FROM messages 
                WHERE created_at > ?
            """,
                [last_refresh],
            ).fetchall()

            total_inserted = 0
            for (sid,) in changed_sessions:
                conn.execute("DELETE FROM exchanges WHERE session_id = ?", [sid])
                total_inserted += self._build_exchanges_for_session(conn, sid)

            self._last_refresh["exchanges"] = datetime.now()
            duration_ms = int((time.time() - start) * 1000)

            return {
                "type": "incremental_batch",
                "sessions_refreshed": len(changed_sessions),
                "rows_added": total_inserted,
                "duration_ms": duration_ms,
            }

        else:
            info("[Materialization] Full refresh exchanges")

            conn.execute("DELETE FROM exchanges")
            total_inserted = self._build_exchanges_for_session(conn, None)

            conn.execute("ANALYZE exchanges")

            self._last_refresh["exchanges"] = datetime.now()
            duration_ms = int((time.time() - start) * 1000)

            return {
                "type": "full",
                "rows_added": total_inserted,
                "duration_ms": duration_ms,
            }

    def _build_exchanges_for_session(self, conn, session_id: Optional[str]) -> int:
        """Build exchanges data using CTE query."""

        session_filter = "WHERE ep.session_id = ?" if session_id else ""
        params = [session_id] if session_id else []

        query = f"""
            INSERT INTO exchanges (
                id, session_id, exchange_number,
                user_message_id, assistant_message_id,
                prompt_input, prompt_output,
                started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count,
                agent, model_id
            )
            WITH first_assistant_per_user AS (
                SELECT
                    a.id,
                    a.parent_id,
                    a.created_at,
                    a.agent,
                    a.model_id,
                    ROW_NUMBER() OVER (PARTITION BY a.parent_id ORDER BY a.created_at ASC) as rn
                FROM messages a
                WHERE a.role = 'assistant' AND a.parent_id IS NOT NULL
            ),
            exchange_pairs AS (
                SELECT
                    u.id as user_msg_id,
                    u.session_id,
                    ROW_NUMBER() OVER (PARTITION BY u.session_id ORDER BY fa.created_at) as exchange_num,
                    u.created_at as user_time,
                    fa.id as assistant_msg_id,
                    fa.created_at as assistant_time,
                    fa.agent,
                    fa.model_id
                FROM messages u
                JOIN first_assistant_per_user fa ON fa.parent_id = u.id AND fa.rn = 1
                WHERE u.role = 'user'
            ),
            user_prompts AS (
                SELECT DISTINCT ON (p.message_id) p.message_id, p.content as prompt_input
                FROM parts p
                WHERE p.part_type = 'text'
                  AND p.message_id IN (SELECT user_msg_id FROM exchange_pairs)
                ORDER BY p.message_id, p.created_at
            ),
            assistant_responses AS (
                SELECT DISTINCT ON (m.parent_id) m.parent_id as user_msg_id, p.content as prompt_output
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                WHERE p.part_type = 'text'
                  AND m.role = 'assistant'
                  AND m.parent_id IS NOT NULL
                ORDER BY m.parent_id, p.created_at DESC
            ),
            step_totals AS (
                SELECT
                    m.parent_id as user_msg_id,
                    SUM(se.tokens_input) as tokens_in,
                    SUM(se.tokens_output) as tokens_out,
                    SUM(se.tokens_reasoning) as tokens_reasoning,
                    SUM(se.cost) as cost
                FROM step_events se
                JOIN messages m ON se.message_id = m.id
                WHERE se.event_type = 'finish' AND m.parent_id IS NOT NULL
                GROUP BY m.parent_id
            ),
            tool_counts AS (
                SELECT m.parent_id as user_msg_id, COUNT(*) as tool_count
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                WHERE p.part_type = 'tool' AND m.role = 'assistant' AND m.parent_id IS NOT NULL
                GROUP BY m.parent_id
            ),
            reasoning_counts AS (
                SELECT m.parent_id as user_msg_id, COUNT(*) as reasoning_count
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                WHERE p.part_type = 'reasoning' AND m.role = 'assistant' AND m.parent_id IS NOT NULL
                GROUP BY m.parent_id
            )
            SELECT
                'exc_' || ep.session_id || '_' || CAST(ep.exchange_num AS VARCHAR) as id,
                ep.session_id,
                ep.exchange_num as exchange_number,
                ep.user_msg_id,
                ep.assistant_msg_id,
                up.prompt_input,
                ar.prompt_output,
                ep.user_time as started_at,
                ep.assistant_time as ended_at,
                CASE
                    WHEN ep.assistant_time IS NOT NULL AND ep.user_time IS NOT NULL
                    THEN CAST(EXTRACT(EPOCH FROM (ep.assistant_time - ep.user_time)) * 1000 AS INTEGER)
                    ELSE NULL
                END as duration_ms,
                COALESCE(st.tokens_in, 0) as tokens_in,
                COALESCE(st.tokens_out, 0) as tokens_out,
                COALESCE(st.tokens_reasoning, 0) as tokens_reasoning,
                COALESCE(st.cost, 0) as cost,
                COALESCE(tc.tool_count, 0) as tool_count,
                COALESCE(rc.reasoning_count, 0) as reasoning_count,
                ep.agent,
                ep.model_id
            FROM exchange_pairs ep
            LEFT JOIN user_prompts up ON up.message_id = ep.user_msg_id
            LEFT JOIN assistant_responses ar ON ar.user_msg_id = ep.user_msg_id
            LEFT JOIN step_totals st ON st.user_msg_id = ep.user_msg_id
            LEFT JOIN tool_counts tc ON tc.user_msg_id = ep.user_msg_id
            LEFT JOIN reasoning_counts rc ON rc.user_msg_id = ep.user_msg_id
            {session_filter}
            ORDER BY ep.session_id, ep.exchange_num
        """

        conn.execute(query, params)

        if session_id:
            count = conn.execute(
                "SELECT COUNT(*) FROM exchanges WHERE session_id = ?", [session_id]
            ).fetchone()[0]
        else:
            count = conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()[0]

        return count

    def refresh_session_traces(
        self, session_id: Optional[str] = None, incremental: bool = True
    ) -> dict:
        """Refresh session_traces table."""
        conn = self._db.connect()
        start = time.time()

        if session_id:
            conn.execute(
                "DELETE FROM session_traces WHERE session_id = ?", [session_id]
            )
            inserted = self._build_session_traces_for_session(conn, session_id)
            duration_ms = int((time.time() - start) * 1000)

            return {
                "type": "incremental",
                "session_id": session_id,
                "rows_added": inserted,
                "duration_ms": duration_ms,
            }
        else:
            conn.execute("DELETE FROM session_traces")
            inserted = self._build_session_traces_for_session(conn, None)
            conn.execute("ANALYZE session_traces")

            duration_ms = int((time.time() - start) * 1000)

            return {"type": "full", "rows_added": inserted, "duration_ms": duration_ms}

    def _build_session_traces_for_session(self, conn, session_id: Optional[str]) -> int:
        """Build session_traces data using recursive CTE."""

        session_filter = "WHERE s.id = ?" if session_id else ""
        params = [session_id] if session_id else []

        query = f"""
            INSERT INTO session_traces (
                id, session_id, title, directory,
                parent_session_id, parent_trace_id, depth,
                total_exchanges, total_tool_calls,
                total_file_reads, total_file_writes,
                total_tokens, total_cost, total_delegations,
                started_at, ended_at, duration_ms, status
            )
            WITH RECURSIVE delegation_tree AS (
                SELECT
                    s.id as session_id,
                    CAST(NULL AS VARCHAR) as parent_session_id,
                    0 as depth
                FROM sessions s
                WHERE NOT EXISTS (SELECT 1 FROM delegations d WHERE d.child_session_id = s.id)
                
                UNION ALL
                
                SELECT
                    d.child_session_id as session_id,
                    d.session_id as parent_session_id,
                    dt.depth + 1 as depth
                FROM delegations d
                JOIN delegation_tree dt ON dt.session_id = d.session_id
                WHERE d.child_session_id IS NOT NULL
            ),
            exchange_stats AS (
                SELECT
                    session_id,
                    COUNT(*) as total_exchanges,
                    SUM(tool_count) as total_tool_calls,
                    SUM(tokens_in + tokens_out + tokens_reasoning) as total_tokens,
                    SUM(cost) as total_cost,
                    MIN(started_at) as first_exchange,
                    MAX(ended_at) as last_exchange
                FROM exchanges
                GROUP BY session_id
            ),
            file_stats AS (
                SELECT
                    session_id,
                    SUM(CASE WHEN operation = 'read' THEN 1 ELSE 0 END) as total_reads,
                    SUM(CASE WHEN operation IN ('write', 'edit') THEN 1 ELSE 0 END) as total_writes
                FROM file_operations
                GROUP BY session_id
            ),
            delegation_stats AS (
                SELECT session_id, COUNT(*) as total_delegations
                FROM delegations
                GROUP BY session_id
            ),
            parent_traces AS (
                SELECT
                    d.child_session_id as session_id,
                    COALESCE(atr.trace_id, 'del_' || p.id) as parent_trace_id
                FROM delegations d
                LEFT JOIN agent_traces atr ON atr.child_session_id = d.child_session_id
                LEFT JOIN parts p ON p.id = d.id
            )
            SELECT
                'st_' || s.id as id,
                s.id as session_id,
                s.title,
                s.directory,
                dt.parent_session_id,
                pt.parent_trace_id,
                COALESCE(dt.depth, 0) as depth,
                COALESCE(es.total_exchanges, 0) as total_exchanges,
                COALESCE(es.total_tool_calls, 0) as total_tool_calls,
                COALESCE(fs.total_reads, 0) as total_file_reads,
                COALESCE(fs.total_writes, 0) as total_file_writes,
                COALESCE(es.total_tokens, 0) as total_tokens,
                COALESCE(es.total_cost, 0) as total_cost,
                COALESCE(ds.total_delegations, 0) as total_delegations,
                COALESCE(es.first_exchange, s.created_at) as started_at,
                COALESCE(es.last_exchange, s.updated_at) as ended_at,
                s.duration_ms,
                CASE
                    WHEN s.ended_at IS NOT NULL THEN 'completed'
                    ELSE 'running'
                END as status
            FROM sessions s
            LEFT JOIN delegation_tree dt ON dt.session_id = s.id
            LEFT JOIN exchange_stats es ON es.session_id = s.id
            LEFT JOIN file_stats fs ON fs.session_id = s.id
            LEFT JOIN delegation_stats ds ON ds.session_id = s.id
            LEFT JOIN parent_traces pt ON pt.session_id = s.id
            {session_filter}
        """

        conn.execute(query, params)

        if session_id:
            count = conn.execute(
                "SELECT COUNT(*) FROM session_traces WHERE session_id = ?", [session_id]
            ).fetchone()[0]
        else:
            count = conn.execute("SELECT COUNT(*) FROM session_traces").fetchone()[0]

        return count

    def refresh_exchange_traces(self, session_id: Optional[str] = None) -> dict:
        """Refresh exchange_traces table."""
        conn = self._db.connect()
        start = time.time()

        if session_id:
            conn.execute(
                "DELETE FROM exchange_traces WHERE session_id = ?", [session_id]
            )
        else:
            conn.execute("DELETE FROM exchange_traces")

        session_filter = "WHERE all_events.session_id = ?" if session_id else ""
        params = [session_id] if session_id else []

        query = f"""
            INSERT INTO exchange_traces (
                id, session_id, exchange_id, event_type, event_order,
                event_data, timestamp, duration_ms, tokens_in, tokens_out
            )
            WITH all_events AS (
                SELECT
                    p.id,
                    p.session_id,
                    e.id as exchange_id,
                    'user_prompt' as event_type,
                    p.created_at as timestamp,
                    NULL::INTEGER as duration_ms,
                    0 as tokens_in,
                    0 as tokens_out,
                    json_object('content', p.content, 'message_id', p.message_id) as event_data
                FROM parts p
                JOIN exchanges e ON e.user_message_id = p.message_id
                WHERE p.part_type = 'text'

                UNION ALL

                SELECT
                    p.id, p.session_id, e.id as exchange_id,
                    'reasoning' as event_type,
                    p.created_at as timestamp, p.duration_ms,
                    0 as tokens_in, 0 as tokens_out,
                    json_object('text', COALESCE(p.reasoning_text, p.content)) as event_data
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                JOIN exchanges e ON m.parent_id = e.user_message_id
                WHERE p.part_type = 'reasoning'

                UNION ALL

                SELECT
                    p.id, p.session_id, e.id as exchange_id,
                    'tool_call' as event_type,
                    p.created_at as timestamp, p.duration_ms,
                    0 as tokens_in, 0 as tokens_out,
                    json_object(
                        'tool_name', p.tool_name,
                        'status', p.tool_status,
                        'arguments', p.arguments,
                        'result_summary', p.result_summary,
                        'child_session_id', p.child_session_id
                    ) as event_data
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                JOIN exchanges e ON m.parent_id = e.user_message_id
                WHERE p.part_type = 'tool'

                UNION ALL

                SELECT
                    se.id, se.session_id, e.id as exchange_id,
                    'step_finish' as event_type,
                    se.created_at as timestamp, NULL::INTEGER as duration_ms,
                    se.tokens_input as tokens_in, se.tokens_output as tokens_out,
                    json_object('reason', se.reason, 'cost', se.cost) as event_data
                FROM step_events se
                JOIN messages m ON se.message_id = m.id
                JOIN exchanges e ON m.parent_id = e.user_message_id
                WHERE se.event_type = 'finish'

                UNION ALL

                SELECT
                    p.id || '_result', p.session_id, e.id as exchange_id,
                    'delegation_result' as event_type,
                    p.created_at as timestamp, p.duration_ms,
                    0 as tokens_in, 0 as tokens_out,
                    json_object(
                        'tool_name', p.tool_name,
                        'child_session_id', p.child_session_id,
                        'result_summary', p.result_summary
                    ) as event_data
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                JOIN exchanges e ON m.parent_id = e.user_message_id
                WHERE p.part_type = 'tool'
                  AND p.child_session_id IS NOT NULL
                  AND p.result_summary IS NOT NULL

                UNION ALL

                SELECT
                    p.id, p.session_id, e.id as exchange_id,
                    'assistant_response' as event_type,
                    p.created_at as timestamp, NULL::INTEGER as duration_ms,
                    0 as tokens_in, 0 as tokens_out,
                    json_object('content', p.content, 'message_id', p.message_id) as event_data
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                JOIN exchanges e ON m.parent_id = e.user_message_id
                WHERE p.part_type = 'text'
                  AND m.role = 'assistant'
                  AND p.id = (
                      SELECT p2.id FROM parts p2
                      JOIN messages m2 ON p2.message_id = m2.id
                      WHERE m2.parent_id = e.user_message_id
                        AND p2.part_type = 'text'
                        AND m2.role = 'assistant'
                      ORDER BY p2.created_at DESC
                      LIMIT 1
                  )
            )
            SELECT
                all_events.id || '_' || all_events.exchange_id || '_evt' as id,
                all_events.session_id,
                all_events.exchange_id,
                all_events.event_type,
                ROW_NUMBER() OVER (
                    PARTITION BY all_events.exchange_id 
                    ORDER BY all_events.timestamp,
                        CASE all_events.event_type
                            WHEN 'user_prompt' THEN 1
                            WHEN 'reasoning' THEN 2
                            WHEN 'tool_call' THEN 3
                            WHEN 'step_finish' THEN 4
                            WHEN 'delegation_result' THEN 5
                            WHEN 'assistant_response' THEN 6
                            ELSE 7
                        END
                ) as event_order,
                all_events.event_data,
                all_events.timestamp,
                all_events.duration_ms,
                all_events.tokens_in,
                all_events.tokens_out
            FROM all_events
            {session_filter}
            ORDER BY all_events.exchange_id, all_events.timestamp
        """

        conn.execute(query, params)

        if session_id:
            count = conn.execute(
                "SELECT COUNT(*) FROM exchange_traces WHERE session_id = ?",
                [session_id],
            ).fetchone()[0]
        else:
            count = conn.execute("SELECT COUNT(*) FROM exchange_traces").fetchone()[0]

        duration_ms = int((time.time() - start) * 1000)

        return {
            "type": "incremental" if session_id else "full",
            "rows_added": count,
            "duration_ms": duration_ms,
        }

    def refresh_all(self, incremental: bool = True) -> dict:
        """Refresh all materialized tables."""
        info("[Materialization] Starting full refresh")

        results = {}

        results["exchanges"] = self.refresh_exchanges(incremental=incremental)
        results["exchange_traces"] = self.refresh_exchange_traces()
        results["session_traces"] = self.refresh_session_traces(incremental=incremental)

        info(f"[Materialization] Refresh complete: {results}")

        return results
