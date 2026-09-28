"""Integration tests for tracing API builders with error data."""

from datetime import datetime

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB


class TestBuildToolsBySession:
    def test_returns_error_field_with_all_tool_fields(
        self, analytics_db_real: AnalyticsDB
    ):
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ["sess-001", "proj-001", "/dir", "Test Session", now, now],
        )
        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, duration_ms, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "bash",
                "error",
                '{"command": "ls"}',
                now,
                1500,
                "Tool execution aborted",
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        assert "sess-001" in result
        tool = result["sess-001"][0]
        assert tool["id"] == "prt-001"
        assert tool["node_type"] == "tool"
        assert tool["tool_name"] == "bash"
        assert tool["status"] == "error"
        assert tool["error"] == "Tool execution aborted"
        assert tool["duration_ms"] == 1500
        assert tool["created_at"] is not None

    def test_success_tool_has_none_error(self, analytics_db_real: AnalyticsDB):
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ["sess-001", "proj-001", "/dir", "Test", now, now],
        )
        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "bash",
                "success",
                "{}",
                now,
                None,
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        assert result["sess-001"][0]["status"] == "success"
        assert result["sess-001"][0]["error"] is None

    def test_include_tools_false_returns_empty(self, analytics_db_real: AnalyticsDB):
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ["sess-001", "proj-001", "/dir", "Test", now, now],
        )
        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "bash",
                "error",
                "{}",
                now,
                "Error",
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=False)

        assert result == {}

    def test_empty_session_ids_returns_empty(self, analytics_db_real: AnalyticsDB):
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()

        result = build_tools_by_session(conn, set(), include_tools=True)

        assert result == {}

    def test_filters_out_task_tool(self, analytics_db_real: AnalyticsDB):
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ["sess-001", "proj-001", "/dir", "Test", now, now],
        )
        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "task",
                "error",
                "{}",
                now,
                "Error",
            ],
        )
        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt-002",
                "sess-001",
                "msg-001",
                "tool",
                "bash",
                "error",
                "{}",
                now,
                "Error",
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        tool_names = [t["tool_name"] for t in result["sess-001"]]
        assert "task" not in tool_names
        assert "bash" in tool_names

    def test_multiple_sessions_grouped_correctly(self, analytics_db_real: AnalyticsDB):
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        for sess_id in ["sess-001", "sess-002"]:
            conn.execute(
                """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                [sess_id, "proj-001", "/dir", "Test", now, now],
            )
            conn.execute(
                """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                                  arguments, created_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    f"prt-{sess_id}",
                    sess_id,
                    "msg-001",
                    "tool",
                    "bash",
                    "error",
                    "{}",
                    now,
                    f"Error {sess_id}",
                ],
            )

        result = build_tools_by_session(
            conn, {"sess-001", "sess-002"}, include_tools=True
        )

        assert len(result) == 2
        assert result["sess-001"][0]["error"] == "Error sess-001"
        assert result["sess-002"][0]["error"] == "Error sess-002"


class TestBuildToolsByMessage:
    def test_returns_error_field_grouped_by_message(
        self, analytics_db_real: AnalyticsDB
    ):
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_message

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ["sess-001", "proj-001", "/dir", "Test", now, now],
        )
        conn.execute(
            """INSERT INTO messages (id, session_id, role, created_at)
            VALUES (?, ?, ?, ?)""",
            ["msg-001", "sess-001", "assistant", now],
        )
        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "edit",
                "error",
                '{"filePath": "/test.py"}',
                now,
                "Error: oldString not found",
            ],
        )

        result = build_tools_by_message(conn, {"sess-001"}, include_tools=True)

        assert "msg-001" in result
        tool = result["msg-001"][0]
        assert tool["tool_name"] == "edit"
        assert tool["tool_status"] == "error"
        assert tool["error"] == "Error: oldString not found"
        assert tool["node_type"] == "tool"
        assert tool["session_id"] == "sess-001"


class TestErrorMessagePreservation:
    @pytest.mark.parametrize(
        "error_message",
        [
            "Tool execution aborted",
            "Error: Request failed with status code: 403",
            "Error: unknown certificate verification error",
            "Error: The user rejected permission to use this specific tool call.",
            "File not found: /path/to/missing/file.py",
            'Error: Long message with JSON [{"permission":"*","pattern":"*","action":"allow"},{"permission":"todowrite","pattern":"*","action":"deny"}]',
            "",
            None,
        ],
    )
    def test_preserves_error_message_exactly(
        self, analytics_db_real: AnalyticsDB, error_message
    ):
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ["sess-001", "proj-001", "/dir", "Test", now, now],
        )
        conn.execute(
            """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "bash",
                "error",
                "{}",
                now,
                error_message,
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        assert result["sess-001"][0]["error"] == error_message
        if error_message:
            assert len(result["sess-001"][0]["error"]) == len(error_message)
