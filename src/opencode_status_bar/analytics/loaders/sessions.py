"""Session data loader."""

from datetime import datetime, timedelta
from pathlib import Path

from ..db import AnalyticsDB
from ...utils.logger import error


def get_opencode_storage_path() -> Path:
    """Get the path to OpenCode storage directory."""
    return Path.home() / ".local" / "share" / "opencode" / "storage"


def load_sessions_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load session data using DuckDB's JSON reader."""
    conn = db.connect()
    session_dir = storage_path / "session"

    if not session_dir.exists():
        return 0

    json_pattern = str(session_dir) + "/**/*.json"
    cutoff_ts = int((datetime.now() - timedelta(days=max_days)).timestamp() * 1000)

    try:
        # Use temp table for deduplication, then insert only new records
        conn.execute("DROP TABLE IF EXISTS _tmp_sessions")
        # json_pattern is derived from trusted storage_path, cutoff_ts is computed int
        conn.execute(f"""
            CREATE TEMP TABLE _tmp_sessions AS
            SELECT id, project_id, directory, title, created_at, updated_at
            FROM (
                SELECT
                    id,
                    projectID as project_id,
                    directory,
                    title,
                    epoch_ms(time.created) as created_at,
                    epoch_ms(time.updated) as updated_at,
                    ROW_NUMBER() OVER (PARTITION BY id ORDER BY time.updated DESC) as rn
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
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            SELECT id, project_id, directory, title, created_at, updated_at FROM _tmp_sessions
            ON CONFLICT (id) DO NOTHING
        """)
        conn.execute("DROP TABLE IF EXISTS _tmp_sessions")

        # Update enriched columns if available in JSON (newer OpenCode versions)
        try:
            # json_pattern is derived from trusted storage_path
            conn.execute(f"""
                UPDATE sessions SET
                    parent_id = src.parentID,
                    version = src.version,
                    additions = COALESCE(src.summary.additions, 0),
                    deletions = COALESCE(src.summary.deletions, 0),
                    files_changed = COALESCE(src.summary.files, 0)
                FROM (
                    SELECT id, parentID, version, summary
                    FROM read_json_auto('{json_pattern}',
                                        maximum_object_size=50000000,
                                        union_by_name=true,
                                        ignore_errors=true)
                    WHERE parentID IS NOT NULL OR version IS NOT NULL OR summary IS NOT NULL
                ) src
                WHERE sessions.id = src.id
            """)  # nosec B608
        except Exception:
            pass  # nosec B110 - enriched columns may not exist in schema

        row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        count = row[0] if row else 0
        return count
    except Exception as e:  # Intentional catch-all: DuckDB can raise various errors
        error(f"Session load failed: {e}")
        return 0
