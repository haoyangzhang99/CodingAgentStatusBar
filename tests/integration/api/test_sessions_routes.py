from datetime import datetime

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB


class TestGetSessions:
    def test_get_sessions_empty(self, api_client_real):
        response = api_client_real.get("/api/sessions")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"]
        assert data["data"] == []

    def test_get_sessions_with_data(
        self, api_client_real, analytics_db_real: AnalyticsDB
    ):
        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-001", "proj-001", "/dir1", "Title 1", now, now],
        )
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-002", "proj-001", "/dir2", "Title 2", now, now],
        )

        response = api_client_real.get("/api/sessions")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"]
        assert len(data["data"]) == 2
        assert data["data"][0]["id"] == "sess-001"
        assert data["data"][1]["id"] == "sess-002"

    def test_get_sessions_respects_limit(
        self, api_client_real, analytics_db_real: AnalyticsDB
    ):
        conn = analytics_db_real.connect()
        now = datetime.now()

        for i in range(10):
            conn.execute(
                """
                INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [f"sess-{i:03d}", "proj-001", f"/dir{i}", f"Title {i}", now, now],
            )

        response = api_client_real.get("/api/sessions?limit=5")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"]
        assert len(data["data"]) == 5

    def test_get_sessions_filters_by_days(
        self, api_client_real, analytics_db_real: AnalyticsDB
    ):
        conn = analytics_db_real.connect()
        now = datetime.now()
        old = datetime(2020, 1, 1)

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-recent", "proj-001", "/dir1", "Recent", now, now],
        )
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-old", "proj-001", "/dir2", "Old", old, old],
        )

        response = api_client_real.get("/api/sessions?days=7")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"]
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "sess-recent"


class TestGetSessionsErrorHandling:
    def test_get_sessions_invalid_days(self, api_client_real):
        response = api_client_real.get("/api/sessions?days=0")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"]
