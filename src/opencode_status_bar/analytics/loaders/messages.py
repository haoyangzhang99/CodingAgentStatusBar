"""Message data loader."""

from datetime import datetime, timedelta
from pathlib import Path

from ..db import AnalyticsDB
from ...utils.logger import error


def load_messages_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load message data using DuckDB's JSON reader."""
    conn = db.connect()
    message_dir = storage_path / "message"

    if not message_dir.exists():
        return 0

    json_pattern = str(message_dir) + "/**/*.json"
    cutoff_ts = int((datetime.now() - timedelta(days=max_days)).timestamp() * 1000)

    try:
        # Use temp table for deduplication, then insert only new records
        conn.execute("DROP TABLE IF EXISTS _tmp_messages")
        # json_pattern is derived from trusted storage_path, cutoff_ts is computed int
        conn.execute(f"""
            CREATE TEMP TABLE _tmp_messages AS
            SELECT id, session_id, parent_id, role, agent, model_id, provider_id,
                   tokens_input, tokens_output, tokens_reasoning,
                   tokens_cache_read, tokens_cache_write, created_at, completed_at
            FROM (
                SELECT
                    id,
                    sessionID as session_id,
                    parentID as parent_id,
                    role,
                    agent,
                    modelID as model_id,
                    providerID as provider_id,
                    COALESCE(tokens.input, 0) as tokens_input,
                    COALESCE(tokens.output, 0) as tokens_output,
                    COALESCE(tokens.reasoning, 0) as tokens_reasoning,
                    COALESCE(tokens.cache.read, 0) as tokens_cache_read,
                    COALESCE(tokens.cache.write, 0) as tokens_cache_write,
                    epoch_ms(time.created) as created_at,
                    epoch_ms(time.completed) as completed_at,
                    ROW_NUMBER() OVER (PARTITION BY id ORDER BY time.created DESC) as rn
                FROM read_json_auto('{json_pattern}',
                                    maximum_object_size=50000000,
                                    ignore_errors=true)
                WHERE id IS NOT NULL
                  AND time.created >= {cutoff_ts}
            ) deduped
            WHERE rn = 1
        """)  # nosec B608

        # Insert only new records, skip existing (incremental load)
        conn.execute("""
            INSERT INTO messages (id, session_id, parent_id, role, agent, model_id, provider_id,
                                  tokens_input, tokens_output, tokens_reasoning,
                                  tokens_cache_read, tokens_cache_write, created_at, completed_at)
            SELECT id, session_id, parent_id, role, agent, model_id, provider_id,
                   tokens_input, tokens_output, tokens_reasoning,
                   tokens_cache_read, tokens_cache_write, created_at, completed_at
            FROM _tmp_messages
            ON CONFLICT (id) DO NOTHING
        """)
        conn.execute("DROP TABLE IF EXISTS _tmp_messages")

        # Update enriched columns if available (newer OpenCode versions)
        try:
            # json_pattern is derived from trusted storage_path
            conn.execute(f"""
                UPDATE messages SET
                    mode = src.mode,
                    cost = COALESCE(src.cost, 0),
                    finish_reason = src.finish,
                    working_dir = src.path.cwd
                FROM (
                    SELECT id, mode, cost, finish, path
                    FROM read_json_auto('{json_pattern}',
                                        maximum_object_size=50000000,
                                        union_by_name=true,
                                        ignore_errors=true)
                    WHERE mode IS NOT NULL OR cost IS NOT NULL OR finish IS NOT NULL OR path IS NOT NULL
                ) src
                WHERE messages.id = src.id
            """)  # nosec B608
        except Exception:
            pass  # nosec B110 - enriched columns may not exist in schema

        row = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        count = row[0] if row else 0
        return count
    except Exception as e:  # Intentional catch-all: DuckDB can raise various errors
        error(f"Message load failed: {e}")
        return 0
