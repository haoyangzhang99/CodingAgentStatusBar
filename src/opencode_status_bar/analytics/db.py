"""
DuckDB database management for analytics.

Uses a singleton pattern to ensure only one connection to the database,
avoiding DuckDB lock conflicts.
"""

import threading
from pathlib import Path
from typing import Optional

import duckdb

from datetime import datetime

from ..utils.logger import info, error


def get_db_path() -> Path:
    """Get the path to the analytics database."""
    config_dir = Path.home() / ".config" / "opencode-status-bar"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "analytics.duckdb"


# Global singleton connection - DEPRECATED
# WARNING: This singleton keeps a connection open indefinitely, which
# blocks dashboard readers. Use AnalyticsDB() directly with context manager.
_db_instance: Optional["AnalyticsDB"] = None
_db_lock = threading.Lock()


def get_analytics_db() -> "AnalyticsDB":
    """Get the singleton AnalyticsDB instance.

    DEPRECATED: This function keeps a connection open indefinitely,
    which blocks concurrent readers (like the dashboard).

    Prefer using AnalyticsDB directly with context manager:

        with AnalyticsDB(read_only=True) as db:
            stats = db.get_stats()

    Or manage connection lifecycle explicitly:

        db = AnalyticsDB()
        try:
            # ... use db ...
        finally:
            db.close()
    """
    global _db_instance
    with _db_lock:
        if _db_instance is None:
            _db_instance = AnalyticsDB()
        return _db_instance


class AnalyticsDB:
    """Manages the DuckDB database for analytics.

    Supports context manager for automatic connection cleanup:

        with AnalyticsDB(read_only=True) as db:
            stats = db.get_stats()
        # Connection automatically closed

    IMPORTANT for concurrency:
    - DuckDB does not allow concurrent readers when a writer holds a lock
    - The menubar is the sole writer; dashboard opens read_only connections
    - Always close connections promptly to avoid blocking readers
    """

    def __init__(self, db_path: Optional[Path] = None, read_only: bool = False):
        """Initialize the analytics database.

        Args:
            db_path: Optional path to database. Uses default if not provided.
            read_only: If True, open in read-only mode (allows concurrent reads).
        """
        self._db_path = db_path or get_db_path()
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._lock = threading.Lock()
        self._read_only = read_only

    def __enter__(self) -> "AnalyticsDB":
        """Context manager entry - connects to database."""
        self.connect()
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        """Context manager exit - closes connection."""
        self.close()

    def connect(self, read_only: Optional[bool] = None) -> duckdb.DuckDBPyConnection:
        """Get or create a database connection (thread-safe).

        Args:
            read_only: If True, open in read-only mode. Defaults to instance setting.
        """
        if read_only is None:
            read_only = self._read_only
        with self._lock:
            if self._conn is None:
                self._conn = duckdb.connect(str(self._db_path), read_only=read_only)
                # Performance settings: optimized for bulk loading
                self._conn.execute("PRAGMA disable_progress_bar")

                # Auto-scale threads: use half of CPU cores (minimum 2)
                import os

                cpu_count = os.cpu_count()
                threads = max(2, cpu_count // 2) if cpu_count else 2
                self._conn.execute(f"SET threads = {threads}")

                # Memory limit: 4GB for streaming (forces efficient algorithms)
                self._conn.execute("SET memory_limit = '4GB'")

                # Enable object cache for repeated struct parsing
                self._conn.execute("SET enable_object_cache = true")

                # Temp directory for spill-to-disk operations
                self._conn.execute("SET temp_directory = '/tmp/duckdb'")

                if not read_only:
                    self._create_schema()
            return self._conn

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _create_schema(self) -> None:
        """Create the database schema if it doesn't exist.

        Order of operations:
        1. Create base tables (without new columns for existing DBs)
        2. Run migrations to add any missing columns
        3. Create indexes (including those on migrated columns)
        """
        conn = self._conn
        if not conn:
            return

        # Sessions table (base columns only - new columns added via migration)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR,
                directory VARCHAR,
                title VARCHAR,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Messages table with token metrics (base columns only)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                parent_id VARCHAR,
                role VARCHAR,
                agent VARCHAR,
                model_id VARCHAR,
                provider_id VARCHAR,
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                tokens_reasoning INTEGER DEFAULT 0,
                tokens_cache_read INTEGER DEFAULT 0,
                tokens_cache_write INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Parts table for message content and tool calls
        conn.execute("""
            CREATE TABLE IF NOT EXISTS parts (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                message_id VARCHAR,
                part_type VARCHAR,
                content VARCHAR,
                tool_name VARCHAR,
                tool_status VARCHAR,
                created_at TIMESTAMP
            )
        """)

        # Skills tracking table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id VARCHAR PRIMARY KEY,
                message_id VARCHAR,
                session_id VARCHAR,
                skill_name VARCHAR,
                loaded_at TIMESTAMP
            )
        """)

        # Agent delegations table (task tool invocations)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delegations (
                id VARCHAR PRIMARY KEY,
                message_id VARCHAR,
                session_id VARCHAR,
                parent_agent VARCHAR,
                child_agent VARCHAR,
                child_session_id VARCHAR,
                created_at TIMESTAMP
            )
        """)

        # Todos table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                content VARCHAR,
                status VARCHAR,
                priority VARCHAR,
                position INTEGER,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Projects table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id VARCHAR PRIMARY KEY,
                worktree VARCHAR,
                vcs VARCHAR,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Agent traces table for task tool invocations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_traces (
                trace_id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                parent_trace_id VARCHAR,
                parent_agent VARCHAR,
                subagent_type VARCHAR NOT NULL,
                prompt_input TEXT NOT NULL,
                prompt_output TEXT,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                duration_ms INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER,
                status VARCHAR DEFAULT 'running',
                tools_used TEXT[],
                child_session_id VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Run migrations to add any missing columns BEFORE creating indexes
        self._migrate_columns(conn)

        # Create indexes for performance (base tables)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_created
            ON messages(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_message
            ON parts(message_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_created
            ON sessions(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegations_session
            ON delegations(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegations_parent
            ON delegations(parent_agent)
        """)

        # Indexes for todos/projects tables
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_todos_session
            ON todos(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_todos_status
            ON todos(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_worktree
            ON projects(worktree)
        """)

        # Indexes on migrated columns (safe now that columns exist)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_session
            ON parts(session_id)
        """)

        # Indexes for security enrichment (Plan 42)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_risk
            ON parts(risk_level, risk_score DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_tool_unenriched
            ON parts(tool_name, security_enriched_at)
        """)

        # Index for scope-aware security (Plan 44)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_scope
            ON parts(scope_verdict)
        """)

        # Indexes for agent_traces table
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_session
            ON agent_traces(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_parent
            ON agent_traces(parent_trace_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_subagent
            ON agent_traces(subagent_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_date
            ON agent_traces(started_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_child_session
            ON agent_traces(child_session_id)
        """)

        # Sync metadata table (for dashboard polling)
        # This allows the dashboard to detect when menubar has synced new data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_meta (
                id INTEGER PRIMARY KEY DEFAULT 1,
                last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sync_count INTEGER DEFAULT 0
            )
        """)
        # Insert initial row if empty
        conn.execute("""
            INSERT INTO sync_meta (id, last_sync, sync_count)
            SELECT 1, CURRENT_TIMESTAMP, 0
            WHERE NOT EXISTS (SELECT 1 FROM sync_meta WHERE id = 1)
        """)

        # File operations table (for tracing file reads/writes/edits)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_operations (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                trace_id VARCHAR,
                operation VARCHAR,
                file_path VARCHAR,
                timestamp TIMESTAMP,
                risk_level VARCHAR,
                risk_reason VARCHAR,
                additions INTEGER DEFAULT 0,
                deletions INTEGER DEFAULT 0
            )
        """)

        # Session stats aggregation table (pre-calculated KPIs)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_stats (
                session_id VARCHAR PRIMARY KEY,
                total_messages INTEGER DEFAULT 0,
                total_tokens_in INTEGER DEFAULT 0,
                total_tokens_out INTEGER DEFAULT 0,
                total_tokens_cache INTEGER DEFAULT 0,
                total_tool_calls INTEGER DEFAULT 0,
                tool_success_rate DECIMAL(5,2) DEFAULT 0,
                total_file_reads INTEGER DEFAULT 0,
                total_file_writes INTEGER DEFAULT 0,
                unique_agents INTEGER DEFAULT 0,
                max_delegation_depth INTEGER DEFAULT 0,
                estimated_cost_usd DECIMAL(10,6) DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Daily stats aggregation table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date DATE PRIMARY KEY,
                total_sessions INTEGER DEFAULT 0,
                total_traces INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_tool_calls INTEGER DEFAULT 0,
                avg_session_duration_ms INTEGER DEFAULT 0,
                error_rate DECIMAL(5,2) DEFAULT 0
            )
        """)

        # Indexes for new tables
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_session
            ON file_operations(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_trace
            ON file_operations(trace_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_operation
            ON file_operations(operation)
        """)

        # Step events table (step-start, step-finish from parts)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS step_events (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                message_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                reason VARCHAR,
                snapshot_hash VARCHAR,
                cost DECIMAL(10,6) DEFAULT 0,
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                tokens_reasoning INTEGER DEFAULT 0,
                tokens_cache_read INTEGER DEFAULT 0,
                tokens_cache_write INTEGER DEFAULT 0,
                created_at TIMESTAMP
            )
        """)

        # Patches table (git commits from patch parts)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patches (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                message_id VARCHAR NOT NULL,
                git_hash VARCHAR NOT NULL,
                files VARCHAR[],
                created_at TIMESTAMP
            )
        """)

        # Indexes for step_events and patches
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_step_events_session
            ON step_events(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_step_events_message
            ON step_events(message_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_patches_session
            ON patches(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_patches_hash
            ON patches(git_hash)
        """)

        # =================================================================
        # Plan 45: Complete Tracing Architecture Tables
        # =================================================================

        # Exchanges table: User->Assistant conversation turns
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exchanges (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                exchange_number INTEGER NOT NULL,
                user_message_id VARCHAR,
                assistant_message_id VARCHAR,
                prompt_input TEXT,
                prompt_output TEXT,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                duration_ms INTEGER,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                tokens_reasoning INTEGER DEFAULT 0,
                cost DECIMAL(10,6) DEFAULT 0,
                tool_count INTEGER DEFAULT 0,
                reasoning_count INTEGER DEFAULT 0,
                agent VARCHAR,
                model_id VARCHAR
            )
        """)

        # Session traces table: High-level session timeline view
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_traces (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                title VARCHAR,
                directory VARCHAR,
                parent_session_id VARCHAR,
                parent_trace_id VARCHAR,
                depth INTEGER DEFAULT 0,
                total_exchanges INTEGER DEFAULT 0,
                total_tool_calls INTEGER DEFAULT 0,
                total_file_reads INTEGER DEFAULT 0,
                total_file_writes INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_cost DECIMAL(10,6) DEFAULT 0,
                total_delegations INTEGER DEFAULT 0,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                duration_ms INTEGER,
                status VARCHAR DEFAULT 'completed'
            )
        """)

        # Exchange traces table: Detailed per-exchange timeline events
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exchange_traces (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                exchange_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                event_order INTEGER NOT NULL,
                event_data JSON,
                timestamp TIMESTAMP,
                duration_ms INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER
            )
        """)

        # Indexes for exchanges table
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_exchanges_session
            ON exchanges(session_id, exchange_number)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_exchanges_timing
            ON exchanges(started_at)
        """)

        # Indexes for session_traces table
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_traces_parent
            ON session_traces(parent_session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_traces_date
            ON session_traces(started_at)
        """)

        # Indexes for exchange_traces table
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_exchange_traces_session
            ON exchange_traces(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_exchange_traces_exchange
            ON exchange_traces(exchange_id, event_order)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_exchange_traces_type
            ON exchange_traces(event_type)
        """)

        # =================================================================
        # DQ-004: Data Quality Sprint 0 - Composite Indexes
        # =================================================================
        # Purpose: Optimize common query patterns for 50x performance improvement
        # Added: 2026-01-10

        # Index: Sessions by project and time
        # Pattern: WHERE project_name = ? ORDER BY created_at DESC
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_project_time
            ON sessions(project_name, created_at DESC)
        """)

        # Index: Parts by message and tool
        # Pattern: WHERE message_id = ? AND tool_name = ?
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_message_tool
            ON parts(message_id, tool_name)
        """)

        # Index: File operations by session and operation (composite)
        # Pattern: WHERE session_id = ? AND operation = ?
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_session_operation
            ON file_operations(session_id, operation)
        """)

        # Index: Messages by root_path (Sprint 1 prep)
        # Pattern: WHERE root_path = ? OR root_path LIKE ?
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_root_path
            ON messages(root_path)
        """)

        # Index: Parts by error_message (error analysis)
        # Pattern: WHERE error_message IS NOT NULL
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_error_message
            ON parts(error_message)
        """)

        # NOTE: Old security_* tables removed in Plan 42
        # Security data is now stored in the unified `parts` table
        # with risk_score, risk_level, risk_reason, mitre_techniques columns

        info("Analytics database schema created")

    # Tables managed by this module - used for whitelist validation
    _MANAGED_TABLES = frozenset(
        {
            "sessions",
            "messages",
            "parts",
            "skills",
            "delegations",
            "todos",
            "projects",
            "agent_traces",
            "file_operations",
            "session_stats",
            "daily_stats",
            "sync_meta",
            "step_events",
            "patches",
            # Plan 45: Complete Tracing Architecture
            "exchanges",
            "session_traces",
            "exchange_traces",
        }
    )

    def _migrate_columns(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Add missing columns to existing tables (idempotent).

        This method checks if each column exists before adding it,
        making it safe to call multiple times.

        Args:
            conn: Active database connection
        """

        # Helper to check if column exists
        def column_exists(table: str, column: str) -> bool:
            # Validate table name against whitelist before using in SQL
            if table not in self._MANAGED_TABLES:
                return False

            try:
                # Use parameterized query to prevent SQL injection
                # Table validated against whitelist above, column from internal code
                result = conn.execute(
                    """
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = ? AND column_name = ?
                    """,
                    [table, column],
                ).fetchone()
                return result is not None
            except duckdb.CatalogException:
                # Expected: information_schema may not exist or table doesn't exist yet
                return False
            except Exception:
                # Unexpected error querying schema - treat as non-existent
                return False

        # Helper to add column if not exists
        def add_column(
            table: str, column: str, col_type: str, default: str = ""
        ) -> None:
            # Validate table name against whitelist (also checked in column_exists)
            if table not in self._MANAGED_TABLES:
                return

            if not column_exists(table, column):
                default_clause = f" DEFAULT {default}" if default else ""
                try:
                    # Table validated against whitelist, column/type from internal constants
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
                    )
                except duckdb.CatalogException:
                    # Expected: table doesn't exist yet, will be created later
                    pass
                except (duckdb.ParserException, duckdb.SyntaxException) as e:
                    # CRITICAL: SQL syntax error in migration - this is a BUG
                    error(f"CRITICAL: Invalid SQL for {table}.{column}: {e}")
                    raise
                except (duckdb.BinderException, duckdb.InvalidTypeException) as e:
                    # CRITICAL: Type or binding error in migration - this is a BUG
                    error(f"CRITICAL: SQL binding/type error for {table}.{column}: {e}")
                    raise
                except Exception as e:
                    # CRITICAL: Unexpected error - fail loudly to debug
                    error(f"CRITICAL: Unexpected error adding {table}.{column}: {e}")
                    raise

        # Sessions - new columns
        add_column("sessions", "parent_id", "VARCHAR")
        add_column("sessions", "version", "VARCHAR")
        add_column("sessions", "additions", "INTEGER", "0")
        add_column("sessions", "deletions", "INTEGER", "0")
        add_column("sessions", "files_changed", "INTEGER", "0")

        # Messages - new columns
        add_column("messages", "mode", "VARCHAR")
        add_column("messages", "cost", "DECIMAL(10,6)", "0")
        add_column("messages", "finish_reason", "VARCHAR")
        add_column("messages", "working_dir", "VARCHAR")
        # Plan 45+: summary_title is the "hook" - auto-generated title for each prompt
        add_column("messages", "summary_title", "VARCHAR")

        # Parts - new columns
        add_column("parts", "session_id", "VARCHAR")
        add_column("parts", "content", "TEXT")  # Text content for prompts/responses
        add_column("parts", "call_id", "VARCHAR")
        add_column("parts", "ended_at", "TIMESTAMP")
        add_column("parts", "duration_ms", "INTEGER")
        add_column("parts", "arguments", "TEXT")
        add_column("parts", "result_summary", "TEXT")
        add_column("parts", "error_message", "TEXT")
        add_column("parts", "error_data", "JSON")  # Structured error data (DQ-005)
        add_column("parts", "child_session_id", "VARCHAR")  # For task delegations

        # Parts - enriched columns for reasoning, compaction, file parts
        add_column("parts", "reasoning_text", "TEXT")  # Reasoning content
        add_column("parts", "anthropic_signature", "TEXT")  # Crypto signature
        add_column("parts", "compaction_auto", "BOOLEAN")  # Auto vs manual compaction
        add_column("parts", "file_mime", "VARCHAR")  # MIME type for file parts
        add_column("parts", "file_name", "VARCHAR")  # Filename for file parts
        add_column("parts", "file_url", "TEXT")  # Base64 data URL for file parts

        # Parts - additional data completeness columns (Plan 45+)
        add_column("parts", "cost", "DECIMAL(10,6)")  # Cost per part
        add_column("parts", "tokens_input", "INTEGER")  # Input tokens per part
        add_column("parts", "tokens_output", "INTEGER")  # Output tokens per part
        add_column("parts", "tokens_reasoning", "INTEGER")  # Reasoning tokens per part
        add_column("parts", "tokens_cache_read", "INTEGER")  # Cache read tokens
        add_column("parts", "tokens_cache_write", "INTEGER")  # Cache write tokens
        add_column("parts", "tool_title", "VARCHAR")  # Tool title from state.title

        # Messages - additional data completeness columns (Plan 45+)
        add_column("messages", "error_name", "VARCHAR")  # Error name if failed
        add_column("messages", "error_data", "TEXT")  # Error details (JSON)
        add_column("messages", "root_path", "VARCHAR")  # Project root path

        # Sessions - additional columns for stats
        add_column("sessions", "ended_at", "TIMESTAMP")
        add_column("sessions", "duration_ms", "INTEGER")
        add_column("sessions", "is_root", "BOOLEAN", "TRUE")
        add_column("sessions", "project_name", "VARCHAR")

        # Parts - security enrichment columns (Plan 42)
        # These columns are populated by SecurityEnrichmentWorker, NOT the indexer
        add_column("parts", "risk_score", "INTEGER")
        add_column("parts", "risk_level", "VARCHAR")
        add_column("parts", "risk_reason", "VARCHAR")
        add_column("parts", "mitre_techniques", "VARCHAR")  # JSON array as string
        add_column("parts", "security_enriched_at", "TIMESTAMP")

        # Parts - scope-aware security columns (Plan 44)
        add_column("parts", "scope_verdict", "VARCHAR")
        add_column("parts", "scope_resolved_path", "VARCHAR")

        # File operations - per-file diff stats
        add_column("file_operations", "additions", "INTEGER", "0")
        add_column("file_operations", "deletions", "INTEGER", "0")

        # NOTE: security_scanned table migration removed in Plan 42
        # Security tracking now uses parts.security_enriched_at column

    def clear_data(self) -> None:
        """Clear all data from the database."""
        conn = self.connect()
        conn.execute("DELETE FROM agent_traces")
        conn.execute("DELETE FROM delegations")
        conn.execute("DELETE FROM skills")
        conn.execute("DELETE FROM parts")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM todos")
        conn.execute("DELETE FROM projects")
        conn.execute("DELETE FROM file_operations")
        conn.execute("DELETE FROM session_stats")
        conn.execute("DELETE FROM daily_stats")
        conn.execute("DELETE FROM step_events")
        conn.execute("DELETE FROM patches")
        # Plan 45: Complete Tracing Architecture
        conn.execute("DELETE FROM exchanges")
        conn.execute("DELETE FROM session_traces")
        conn.execute("DELETE FROM exchange_traces")
        info("Analytics database cleared")

    def get_stats(self) -> dict:
        """Get basic stats about the database."""
        conn = self.connect()
        result = {}

        # Use whitelist for validation - ensures only managed tables are queried
        for table in self._MANAGED_TABLES:
            try:
                # Table name validated against whitelist, safe for SQL
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                result[table] = count[0] if count else 0
            except duckdb.CatalogException:
                # Expected: table doesn't exist yet
                result[table] = 0
            except Exception:
                # Unexpected error - return 0 for robustness
                result[table] = 0

        return result

    def get_last_refresh(self) -> float:
        """Get timestamp of last data refresh (0 if never refreshed)."""
        conn = self.connect()
        try:
            # Use the max updated_at from sessions as proxy for last refresh
            result = conn.execute("SELECT MAX(updated_at) FROM sessions").fetchone()
            if result and result[0]:
                # DuckDB returns datetime objects
                from datetime import datetime

                if isinstance(result[0], datetime):
                    return result[0].timestamp()
                return float(result[0]) / 1000  # Convert ms to seconds if int
            return 0
        except duckdb.CatalogException:
            # Expected: sessions table doesn't exist yet
            return 0
        except Exception:
            # Unexpected error - return 0 for robustness
            return 0

    def migrate_schema(self) -> None:
        """Migrate existing database to add new columns.

        This is safe to call multiple times - it checks if columns exist
        before adding them. Delegates to _migrate_columns() which contains
        the actual migration logic.
        """
        conn = self.connect()
        self._migrate_columns(conn)
        info("Database schema migration completed")

    def needs_refresh(self, max_age_hours: int = 24) -> bool:
        """Check if data needs refresh based on age."""
        import time

        last_refresh = self.get_last_refresh()
        if last_refresh == 0:
            return True
        age_hours = (time.time() - last_refresh) / 3600
        return age_hours > max_age_hours

    def update_sync_timestamp(self) -> None:
        """Mark that a sync just completed (called by menubar only).

        This updates the sync_meta table to signal to dashboard readers
        that new data is available.
        """
        conn = self.connect()
        conn.execute("""
            UPDATE sync_meta
            SET last_sync = CURRENT_TIMESTAMP, sync_count = sync_count + 1
            WHERE id = 1
        """)

    def get_sync_timestamp(self) -> Optional[datetime]:
        """Get last sync timestamp (for dashboard polling).

        Returns:
            The timestamp of the last sync, or None if no sync has occurred.
        """
        conn = self.connect()
        result = conn.execute("SELECT last_sync FROM sync_meta WHERE id = 1").fetchone()
        return result[0] if result else None
