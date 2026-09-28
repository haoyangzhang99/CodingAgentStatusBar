import pytest

from opencode_status_bar.analytics.db import AnalyticsDB


class TestDatabaseSchema:
    def test_creates_all_tables(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {t[0] for t in tables}

        expected = {
            "sessions",
            "messages",
            "parts",
            "skills",
            "delegations",
            "todos",
            "projects",
        }
        assert expected.issubset(table_names)

    def test_sessions_has_new_columns(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'sessions'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        new_cols = {"parent_id", "version", "additions", "deletions", "files_changed"}
        assert new_cols.issubset(col_names)

    def test_messages_has_new_columns(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'messages'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        new_cols = {"mode", "cost", "finish_reason", "working_dir"}
        assert new_cols.issubset(col_names)

    def test_parts_has_new_columns(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'parts'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        new_cols = {"session_id", "call_id", "ended_at", "duration_ms"}
        assert new_cols.issubset(col_names)

    def test_todos_table_structure(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'todos'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        expected = {
            "id",
            "session_id",
            "content",
            "status",
            "priority",
            "position",
            "created_at",
            "updated_at",
        }
        assert expected == col_names

    def test_projects_table_structure(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'projects'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        expected = {"id", "worktree", "vcs", "created_at", "updated_at"}
        assert expected == col_names
