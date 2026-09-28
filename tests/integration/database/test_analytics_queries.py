from datetime import datetime

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.models import Todo, Project
from opencode_status_bar.analytics.queries import AnalyticsQueries
from tests.fixtures.builders import SessionDataFactory, MessageDataFactory


class TestAnalyticsQueries:
    def test_get_todos_empty(self, analytics_db_real: AnalyticsDB):
        queries = AnalyticsQueries(analytics_db_real)
        result = queries.get_todos()
        assert result == []

    def test_get_todos_with_data(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()

        conn.execute(
            """
            INSERT INTO todos (id, session_id, content, status, priority, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "todo_1",
                "ses_test",
                "Task 1",
                "completed",
                "high",
                0,
                datetime.now(),
                datetime.now(),
            ],
        )
        conn.execute(
            """
            INSERT INTO todos (id, session_id, content, status, priority, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "todo_2",
                "ses_test",
                "Task 2",
                "pending",
                "medium",
                1,
                datetime.now(),
                datetime.now(),
            ],
        )

        queries = AnalyticsQueries(analytics_db_real)
        result = queries.get_todos()

        assert len(result) == 2
        assert isinstance(result[0], Todo)
        assert result[0].content == "Task 1"

    def test_get_todos_filter_by_status(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()

        conn.execute(
            """
            INSERT INTO todos (id, session_id, content, status, priority, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "todo_1",
                "ses_test",
                "Task 1",
                "completed",
                "high",
                0,
                datetime.now(),
                datetime.now(),
            ],
        )
        conn.execute(
            """
            INSERT INTO todos (id, session_id, content, status, priority, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "todo_2",
                "ses_test",
                "Task 2",
                "pending",
                "medium",
                1,
                datetime.now(),
                datetime.now(),
            ],
        )

        queries = AnalyticsQueries(analytics_db_real)
        result = queries.get_todos(status="completed")

        assert len(result) == 1
        assert result[0].status == "completed"

    def test_get_projects_empty(self, analytics_db_real: AnalyticsDB):
        queries = AnalyticsQueries(analytics_db_real)
        result = queries.get_projects()
        assert result == []

    def test_get_projects_with_data(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()

        conn.execute(
            """
            INSERT INTO projects (id, worktree, vcs, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ["proj_001", "/test/path", "git", datetime.now(), datetime.now()],
        )

        queries = AnalyticsQueries(analytics_db_real)
        result = queries.get_projects()

        assert len(result) == 1
        assert isinstance(result[0], Project)
        assert result[0].worktree == "/test/path"
        assert result[0].vcs == "git"

    def test_get_code_stats(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()
        now = datetime.now()

        for i in range(3):
            conn.execute(
                """
                INSERT INTO sessions (
                    id, project_id, directory, title, created_at, updated_at,
                    additions, deletions, files_changed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [f"ses_{i}", "proj_001", "/test", f"Session {i}", now, now, 100, 50, 5],
            )

        queries = AnalyticsQueries(analytics_db_real)
        result = queries.get_code_stats(days=30)

        assert result["additions"] == 300
        assert result["deletions"] == 150
        assert result["files_changed"] == 15
        assert result["sessions_with_changes"] == 3

    def test_get_cost_stats(self, analytics_db_real: AnalyticsDB):
        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["ses_test", "proj_001", "/test", "Test Session", now, now],
        )

        for i in range(3):
            conn.execute(
                """
                INSERT INTO messages (
                    id, session_id, role, agent, model_id, provider_id,
                    tokens_input, tokens_output, cost, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"msg_{i}",
                    "ses_test",
                    "assistant",
                    "main",
                    "claude-sonnet",
                    "anthropic",
                    100,
                    50,
                    0.01,
                    now,
                ],
            )

        queries = AnalyticsQueries(analytics_db_real)
        result = queries.get_cost_stats(days=30)

        assert result["total_cost"] == pytest.approx(0.03, rel=0.01)
        assert result["messages_with_cost"] == 3
