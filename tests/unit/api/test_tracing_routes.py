"""
Tests for API Tracing Routes - builders.py, utils.py, fetchers.py.

This module provides comprehensive unit tests for the tracing routes
helper modules to achieve >60% coverage.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Utils Tests
# =============================================================================


class TestGetSortKey:
    """Tests for get_sort_key utility function."""

    def test_sort_key_with_started_at(self):
        """Return started_at timestamp when present."""
        from opencode_status_bar.api.routes.tracing.utils import get_sort_key

        item = {"started_at": "2026-01-01T10:00:00"}
        assert get_sort_key(item) == "2026-01-01T10:00:00"

    def test_sort_key_with_created_at(self):
        """Fall back to created_at when started_at missing."""
        from opencode_status_bar.api.routes.tracing.utils import get_sort_key

        item = {"created_at": "2026-01-01T09:00:00"}
        assert get_sort_key(item) == "2026-01-01T09:00:00"

    def test_sort_key_prefers_started_at(self):
        """Prefer started_at over created_at."""
        from opencode_status_bar.api.routes.tracing.utils import get_sort_key

        item = {
            "started_at": "2026-01-01T10:00:00",
            "created_at": "2026-01-01T09:00:00",
        }
        assert get_sort_key(item) == "2026-01-01T10:00:00"

    def test_sort_key_returns_min_timestamp_when_empty(self):
        """Return MIN_TIMESTAMP when no timestamps present."""
        from opencode_status_bar.api.routes.tracing.utils import (
            MIN_TIMESTAMP,
            get_sort_key,
        )

        item = {}
        assert get_sort_key(item) == MIN_TIMESTAMP

    def test_sort_key_with_none_values(self):
        """Handle None values correctly."""
        from opencode_status_bar.api.routes.tracing.utils import (
            MIN_TIMESTAMP,
            get_sort_key,
        )

        item = {"started_at": None, "created_at": None}
        assert get_sort_key(item) == MIN_TIMESTAMP


class TestExtractDisplayInfo:
    """Tests for extract_display_info utility function."""

    def test_extract_webfetch_url(self):
        """Extract URL from webfetch tool arguments."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        args = json.dumps({"url": "https://example.com/api"})
        result = extract_display_info("webfetch", args)
        assert result == "https://example.com/api"

    def test_extract_context7_library_id(self):
        """Extract libraryId from context7 query-docs tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        args = json.dumps({"libraryId": "/org/project"})
        result = extract_display_info("context7_query-docs", args)
        assert result == "/org/project"

    def test_extract_read_file_path(self):
        """Extract filePath from read tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        args = json.dumps({"filePath": "/home/user/file.py"})
        result = extract_display_info("read", args)
        assert result == "/home/user/file.py"

    def test_extract_glob_path(self):
        """Extract path from glob tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        args = json.dumps({"path": "/home/user"})
        result = extract_display_info("glob", args)
        assert result == "/home/user"

    def test_extract_bash_command(self):
        """Extract command from bash tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        args = json.dumps({"command": "ls -la"})
        result = extract_display_info("bash", args)
        assert result == "ls -la"

    def test_extract_grep_pattern(self):
        """Extract pattern from grep tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        args = json.dumps({"pattern": "function.*test"})
        result = extract_display_info("grep", args)
        assert result == "/function.*test/"

    def test_extract_task_description(self):
        """Extract description from task tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        args = json.dumps({"description": "Run tests"})
        result = extract_display_info("task", args)
        assert result == "Run tests"

    def test_extract_display_info_no_args(self):
        """Return None when arguments is None."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        result = extract_display_info("bash", None)
        assert result is None

    def test_extract_display_info_invalid_json(self):
        """Return None when arguments is invalid JSON."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        result = extract_display_info("bash", "not json")
        assert result is None

    def test_extract_display_info_unknown_tool(self):
        """Return None for unknown tool type."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        args = json.dumps({"some": "args"})
        result = extract_display_info("unknown_tool", args)
        assert result is None

    def test_extract_display_info_truncates_long_values(self):
        """Truncate long values to 80 characters."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        long_url = "https://example.com/" + "a" * 100
        args = json.dumps({"url": long_url})
        result = extract_display_info("webfetch", args)
        # Verify result is a truncated string
        assert isinstance(result, str), "result must be string"
        assert len(result) == 80

    def test_extract_bash_truncates_to_60(self):
        """Bash commands truncate to 60 characters."""
        from opencode_status_bar.api.routes.tracing.utils import extract_display_info

        long_cmd = "echo " + "a" * 100
        args = json.dumps({"command": long_cmd})
        result = extract_display_info("bash", args)
        # Verify result is a truncated string
        assert isinstance(result, str), "result must be string"
        assert len(result) == 60


class TestExtractToolDisplayInfo:
    """Tests for extract_tool_display_info utility function."""

    def test_tool_display_bash_command(self):
        """Extract bash command with truncation at 100 chars."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"command": "ls -la /home/user"})
        result = extract_tool_display_info("bash", args)
        assert result == "ls -la /home/user"

    def test_tool_display_bash_long_command(self):
        """Long bash commands get truncated with ellipsis."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        long_cmd = "x" * 150
        args = json.dumps({"command": long_cmd})
        result = extract_tool_display_info("bash", args)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")

    def test_tool_display_read_file_path(self):
        """Extract filePath from read tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"filePath": "/path/to/file.py"})
        result = extract_tool_display_info("read", args)
        assert result == "/path/to/file.py"

    def test_tool_display_read_fallback_path(self):
        """Fall back to path when filePath missing."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"path": "/fallback/path.py"})
        result = extract_tool_display_info("read", args)
        assert result == "/fallback/path.py"

    def test_tool_display_glob_pattern(self):
        """Extract pattern from glob tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"pattern": "**/*.py"})
        result = extract_tool_display_info("glob", args)
        assert result == "**/*.py"

    def test_tool_display_grep_pattern(self):
        """Extract pattern from grep tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"pattern": "TODO"})
        result = extract_tool_display_info("grep", args)
        assert result == "TODO"

    def test_tool_display_task_subagent_only(self):
        """Extract subagent_type from task tool when only subagent present."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"subagent_type": "roadmap"})
        result = extract_tool_display_info("task", args)
        assert result == "roadmap"

    def test_tool_display_task_description_only(self):
        """Extract description from task tool when only description present."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"description": "Analyze the code"})
        result = extract_tool_display_info("task", args)
        assert result == "Analyze the code"

    def test_tool_display_task_combined(self):
        """Combine subagent_type and description when both present."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"subagent_type": "librarian", "description": "Find docs"})
        result = extract_tool_display_info("task", args)
        assert result == "librarian: Find docs"

    def test_tool_display_empty_args(self):
        """Return empty string when args is None."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        result = extract_tool_display_info("bash", None)
        assert result == ""

    def test_tool_display_invalid_json(self):
        """Return empty string for invalid JSON."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        result = extract_tool_display_info("bash", "invalid")
        assert result == ""

    def test_tool_display_write_file_path(self):
        """Extract filePath from write tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"filePath": "/write/path.txt"})
        result = extract_tool_display_info("write", args)
        assert result == "/write/path.txt"

    def test_tool_display_edit_file_path(self):
        """Extract filePath from edit tool."""
        from opencode_status_bar.api.routes.tracing.utils import extract_tool_display_info

        args = json.dumps({"filePath": "/edit/path.txt"})
        result = extract_tool_display_info("edit", args)
        assert result == "/edit/path.txt"


class TestCollectSessionIds:
    """Tests for collect_session_ids utility function."""

    def test_collect_from_root_rows(self):
        """Collect session IDs from root trace rows."""
        from opencode_status_bar.api.routes.tracing.utils import collect_session_ids

        # Row format: (trace_id, session_id, ..., child_session_id at index 13)
        root_rows = [
            (
                "root_1",
                "sess_1",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
            (
                "root_2",
                "sess_2",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "child_sess_1",
            ),
        ]
        child_rows = []

        all_ids, root_ids = collect_session_ids(root_rows, child_rows)

        assert "sess_1" in all_ids
        assert "sess_2" in all_ids
        assert "child_sess_1" in all_ids
        assert root_ids == {"sess_1", "sess_2"}

    def test_collect_from_child_rows(self):
        """Collect child session IDs from child trace rows."""
        from opencode_status_bar.api.routes.tracing.utils import collect_session_ids

        root_rows = [
            (
                "root_1",
                "sess_1",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
        ]
        child_rows = [
            (
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "child_sess_2",
            ),
        ]

        all_ids, root_ids = collect_session_ids(root_rows, child_rows)

        assert "child_sess_2" in all_ids
        assert "sess_1" in all_ids
        assert root_ids == {"sess_1"}

    def test_collect_empty_rows(self):
        """Handle empty row lists."""
        from opencode_status_bar.api.routes.tracing.utils import collect_session_ids

        all_ids, root_ids = collect_session_ids([], [])
        assert all_ids == set()
        assert root_ids == set()


class TestMatchDelegationTokens:
    """Tests for match_delegation_tokens utility function."""

    def test_match_existing_tokens(self):
        """Return existing tokens if already present."""
        from opencode_status_bar.api.routes.tracing.utils import match_delegation_tokens

        delegation_tokens = {"tokens_in": 100, "tokens_out": 200}
        result, matched_session = match_delegation_tokens(
            datetime.now(), "agent", delegation_tokens, []
        )

        assert result == delegation_tokens
        assert matched_session is None

    def test_match_no_delegation_start(self):
        """Return original tokens when no delegation start."""
        from opencode_status_bar.api.routes.tracing.utils import match_delegation_tokens

        delegation_tokens = {"tokens_in": None, "tokens_out": None}
        result, matched_session = match_delegation_tokens(
            None, "agent", delegation_tokens, []
        )

        assert result == delegation_tokens
        assert matched_session is None

    def test_match_by_agent_type_and_time(self):
        """Match subagent session by agent type and time proximity."""
        from opencode_status_bar.api.routes.tracing.utils import match_delegation_tokens

        now = datetime.now()
        delegation_tokens = {"tokens_in": None, "tokens_out": None}
        subagent_by_time = [
            {
                "agent_type": "roadmap",
                "created_at": now + timedelta(seconds=2),
                "session_id": "matched_session",
                "tokens": {"tokens_in": 50, "tokens_out": 100, "cache_read": 200},
            }
        ]

        result, matched_session = match_delegation_tokens(
            now, "roadmap", delegation_tokens, subagent_by_time
        )

        assert result["tokens_in"] == 50
        assert result["tokens_out"] == 100
        assert result["cache_read"] == 200
        assert matched_session == "matched_session"

    def test_no_match_different_agent(self):
        """Don't match if agent type differs."""
        from opencode_status_bar.api.routes.tracing.utils import match_delegation_tokens

        now = datetime.now()
        delegation_tokens = {"tokens_in": None, "tokens_out": None}
        subagent_by_time = [
            {
                "agent_type": "different_agent",
                "created_at": now + timedelta(seconds=2),
                "session_id": "sess_1",
                "tokens": {"tokens_in": 50, "tokens_out": 100},
            }
        ]

        result, matched_session = match_delegation_tokens(
            now, "roadmap", delegation_tokens, subagent_by_time
        )

        assert result == delegation_tokens
        assert matched_session is None

    def test_no_match_time_too_far(self):
        """Don't match if time difference > 5 seconds."""
        from opencode_status_bar.api.routes.tracing.utils import match_delegation_tokens

        now = datetime.now()
        delegation_tokens = {"tokens_in": None, "tokens_out": None}
        subagent_by_time = [
            {
                "agent_type": "roadmap",
                "created_at": now + timedelta(seconds=10),  # Too far
                "session_id": "sess_1",
                "tokens": {"tokens_in": 50, "tokens_out": 100},
            }
        ]

        result, matched_session = match_delegation_tokens(
            now, "roadmap", delegation_tokens, subagent_by_time
        )

        assert result == delegation_tokens
        assert matched_session is None


class TestCreateAgentAtTimeGetter:
    """Tests for create_agent_at_time_getter utility function."""

    def test_get_initial_agent(self):
        """Return initial agent when no timeline."""
        from opencode_status_bar.api.routes.tracing.utils import (
            create_agent_at_time_getter,
        )

        initial_agent = {"sess_1": "plan"}
        segment_timeline = {}
        get_agent = create_agent_at_time_getter(initial_agent, segment_timeline)

        result = get_agent("sess_1", datetime.now())
        assert result == "plan"

    def test_get_default_agent(self):
        """Return 'assistant' when session not in initial_agent."""
        from opencode_status_bar.api.routes.tracing.utils import (
            create_agent_at_time_getter,
        )

        get_agent = create_agent_at_time_getter({}, {})
        result = get_agent("unknown_sess", datetime.now())
        assert result == "assistant"

    def test_get_agent_from_timeline(self):
        """Return agent from timeline at given timestamp."""
        from opencode_status_bar.api.routes.tracing.utils import (
            create_agent_at_time_getter,
        )

        now = datetime.now()
        initial_agent = {"sess_1": "plan"}
        segment_timeline = {
            "sess_1": [
                (now - timedelta(minutes=5), "plan"),
                (now - timedelta(minutes=2), "code"),
                (now + timedelta(minutes=1), "review"),
            ]
        }
        get_agent = create_agent_at_time_getter(initial_agent, segment_timeline)

        # At current time, should return "code" (most recent before now)
        result = get_agent("sess_1", now)
        assert result == "code"


class TestCalculateExchangeEndTime:
    """Tests for calculate_exchange_end_time utility function."""

    def test_end_time_from_child(self):
        """Get end time from child's ended_at."""
        from opencode_status_bar.api.routes.tracing.utils import (
            calculate_exchange_end_time,
        )

        ex = {
            "started_at": "2026-01-01T10:00:00",
            "children": [{"ended_at": "2026-01-01T10:05:00"}],
        }
        result = calculate_exchange_end_time(ex, [], 0, None)
        assert result == "2026-01-01T10:05:00"

    def test_end_time_from_child_duration(self):
        """Calculate end time from child's start + duration."""
        from opencode_status_bar.api.routes.tracing.utils import (
            calculate_exchange_end_time,
        )

        ex = {
            "started_at": "2026-01-01T10:00:00",
            "children": [
                {"started_at": "2026-01-01T10:01:00", "duration_ms": 60000}  # 1 minute
            ],
        }
        result = calculate_exchange_end_time(ex, [], 0, None)
        assert result == "2026-01-01T10:02:00"

    def test_end_time_from_next_exchange(self):
        """Get end time from next exchange's start."""
        from opencode_status_bar.api.routes.tracing.utils import (
            calculate_exchange_end_time,
        )

        ex = {"started_at": "2026-01-01T10:00:00", "children": []}
        sorted_exchanges = [
            ex,
            {"started_at": "2026-01-01T10:10:00"},
        ]
        result = calculate_exchange_end_time(ex, sorted_exchanges, 0, None)
        assert result == "2026-01-01T10:10:00"

    def test_end_time_from_session_end(self):
        """Get end time from session end timestamp."""
        from opencode_status_bar.api.routes.tracing.utils import (
            calculate_exchange_end_time,
        )

        ex = {"started_at": "2026-01-01T10:00:00", "children": []}
        session_end = datetime.fromisoformat("2026-01-01T10:30:00")
        result = calculate_exchange_end_time(ex, [ex], 0, session_end)
        assert result == "2026-01-01T10:30:00"

    def test_end_time_no_children_key(self):
        """Handle exchange without children key."""
        from opencode_status_bar.api.routes.tracing.utils import (
            calculate_exchange_end_time,
        )

        ex = {"started_at": "2026-01-01T10:00:00"}
        session_end = datetime.fromisoformat("2026-01-01T10:30:00")
        result = calculate_exchange_end_time(ex, [ex], 0, session_end)
        assert result == "2026-01-01T10:30:00"


class TestCalculateExchangeDurations:
    """Tests for calculate_exchange_durations utility function."""

    def test_calculate_duration(self):
        """Calculate duration from ended_at - started_at."""
        from opencode_status_bar.api.routes.tracing.utils import (
            calculate_exchange_durations,
        )

        exchanges = [
            {"started_at": "2026-01-01T10:00:00", "children": []},
            {"started_at": "2026-01-01T10:05:00", "children": []},
        ]
        session_end = datetime.fromisoformat("2026-01-01T10:10:00")

        calculate_exchange_durations(exchanges, session_end)

        # First exchange ends when second starts
        assert exchanges[0]["ended_at"] == "2026-01-01T10:05:00"
        assert exchanges[0]["duration_ms"] == 300000  # 5 minutes

        # Second exchange ends at session end
        assert exchanges[1]["ended_at"] == "2026-01-01T10:10:00"
        assert exchanges[1]["duration_ms"] == 300000  # 5 minutes

    def test_skip_exchange_without_start(self):
        """Skip exchanges without started_at."""
        from opencode_status_bar.api.routes.tracing.utils import (
            calculate_exchange_durations,
        )

        exchanges = [{"children": []}]  # No started_at
        calculate_exchange_durations(exchanges, None)

        # Should not crash, and no duration added
        assert "duration_ms" not in exchanges[0]


# =============================================================================
# Builders Tests
# =============================================================================


class TestBuildToolsBySession:
    """Tests for build_tools_by_session builder function."""

    def test_build_empty_when_not_included(self):
        """Return empty dict when include_tools is False."""
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = MagicMock()
        result = build_tools_by_session(conn, {"sess_1"}, include_tools=False)
        assert result == {}
        conn.execute.assert_not_called()

    def test_build_empty_when_no_sessions(self):
        """Return empty dict when no session IDs provided."""
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = MagicMock()
        result = build_tools_by_session(conn, set(), include_tools=True)
        assert result == {}
        conn.execute.assert_not_called()

    def test_build_tools_grouped_by_session(self):
        """Build tools dictionary grouped by session_id."""
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_session

        conn = MagicMock()
        # Row format: id, session_id, tool_name, tool_status, arguments, created_at, duration_ms, result_summary, error_message
        tool_rows = [
            (
                "tool_1",
                "sess_1",
                "bash",
                "completed",
                '{"command": "ls"}',
                datetime.now(),
                100,
                "success",
                None,  # error_message
            ),
            (
                "tool_2",
                "sess_1",
                "read",
                "completed",
                '{"filePath": "/file.py"}',
                datetime.now(),
                50,
                None,
                None,  # error_message
            ),
            (
                "tool_3",
                "sess_2",
                "write",
                "completed",
                '{"filePath": "/out.txt"}',
                datetime.now(),
                75,
                None,
                "File write error",  # error_message
            ),
        ]
        conn.execute.return_value.fetchall.return_value = tool_rows

        result = build_tools_by_session(conn, {"sess_1", "sess_2"}, include_tools=True)

        assert len(result["sess_1"]) == 2
        assert len(result["sess_2"]) == 1
        assert result["sess_1"][0]["tool_name"] == "bash"
        assert result["sess_1"][0]["node_type"] == "tool"
        assert result["sess_1"][0]["error"] is None
        assert result["sess_2"][0]["error"] == "File write error"


class TestBuildToolsByMessage:
    """Tests for build_tools_by_message builder function."""

    def test_build_empty_when_not_included(self):
        """Return empty dict when include_tools is False."""
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_message

        conn = MagicMock()
        result = build_tools_by_message(conn, {"sess_1"}, include_tools=False)
        assert result == {}

    def test_build_empty_when_no_sessions(self):
        """Return empty dict when no session IDs provided."""
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_message

        conn = MagicMock()
        result = build_tools_by_message(conn, set(), include_tools=True)
        assert result == {}

    def test_build_tools_grouped_by_message(self):
        """Build tools dictionary grouped by message_id."""
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_message

        conn = MagicMock()
        # Row format: id, session_id, message_id, tool_name, tool_status, arguments, created_at, duration_ms, result_summary, error_message
        tool_rows = [
            (
                "tool_1",
                "sess_1",
                "msg_1",
                "bash",
                "completed",
                '{"command": "ls"}',
                datetime.now(),
                100,
                "success",
                None,  # error_message
            ),
            (
                "tool_2",
                "sess_1",
                "msg_1",
                "read",
                "completed",
                '{"filePath": "/file.py"}',
                datetime.now(),
                50,
                None,
                "Connection timeout",  # error_message
            ),
        ]
        conn.execute.return_value.fetchall.return_value = tool_rows

        result = build_tools_by_message(conn, {"sess_1"}, include_tools=True)

        assert "msg_1" in result
        assert len(result["msg_1"]) == 2
        assert result["msg_1"][0]["tool_name"] == "bash"
        assert result["msg_1"][0]["trace_id"] == "tool_tool_1"
        assert result["msg_1"][0]["error"] is None
        assert result["msg_1"][1]["error"] == "Connection timeout"

    def test_skip_tools_without_message_id(self):
        """Skip tools that have no message_id."""
        from opencode_status_bar.api.routes.tracing.builders import build_tools_by_message

        conn = MagicMock()
        tool_rows = [
            (
                "tool_1",
                "sess_1",
                None,
                "bash",
                "completed",
                '{"command": "ls"}',
                datetime.now(),
                100,
                None,
                None,
            ),
        ]
        conn.execute.return_value.fetchall.return_value = tool_rows

        result = build_tools_by_message(conn, {"sess_1"}, include_tools=True)
        assert result == {}


class TestBuildChildrenByParent:
    """Tests for build_children_by_parent builder function."""

    def test_build_empty_children(self):
        """Return empty dict when no child rows."""
        from opencode_status_bar.api.routes.tracing.builders import (
            build_children_by_parent,
        )

        result = build_children_by_parent([], {}, [], include_tools=True)
        assert result == {}

    def test_build_children_grouped_by_parent(self):
        """Build children dictionary grouped by parent trace ID."""
        from opencode_status_bar.api.routes.tracing.builders import (
            build_children_by_parent,
        )

        # Row format: trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
        #             started_at, ended_at, duration_ms, tokens_in, tokens_out, status,
        #             prompt_input, prompt_output, child_session_id
        now = datetime.now()
        child_rows = [
            (
                "child_1",
                "sess_1",
                "parent_1",
                "plan",
                "code",
                now,
                now + timedelta(minutes=1),
                60000,
                100,
                200,
                "completed",
                "input",
                "output",
                "child_sess_1",
            ),
            (
                "child_2",
                "sess_1",
                "parent_1",
                "plan",
                "review",
                now + timedelta(minutes=2),
                now + timedelta(minutes=3),
                60000,
                50,
                100,
                "completed",
                "input2",
                "output2",
                None,
            ),
        ]
        tools_by_session = {"child_sess_1": [{"id": "tool_1", "node_type": "tool"}]}

        result = build_children_by_parent(
            child_rows, tools_by_session, [], include_tools=True
        )

        assert "parent_1" in result
        assert len(result["parent_1"]) == 2
        assert result["parent_1"][0]["trace_id"] == "child_1"
        assert result["parent_1"][0]["node_type"] == "agent"
        # First child has tools from child_sess_1
        assert len(result["parent_1"][0]["children"]) == 1


class TestBuildRecursiveChildren:
    """Tests for build_recursive_children builder function."""

    def test_build_empty_children(self):
        """Return empty list when parent not in dict."""
        from opencode_status_bar.api.routes.tracing.builders import (
            build_recursive_children,
        )

        result = build_recursive_children({}, "unknown_parent")
        assert result == []

    def test_build_recursive_tree(self):
        """Build recursive tree of children."""
        from opencode_status_bar.api.routes.tracing.builders import (
            build_recursive_children,
        )

        children_by_parent = {
            "root": [
                {
                    "trace_id": "child_1",
                    "started_at": "2026-01-01T10:00:00",
                    "children": [],
                }
            ],
            "child_1": [
                {
                    "trace_id": "grandchild_1",
                    "started_at": "2026-01-01T10:01:00",
                    "children": [],
                }
            ],
        }

        result = build_recursive_children(children_by_parent, "root")

        assert len(result) == 1
        assert result[0]["trace_id"] == "child_1"
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["trace_id"] == "grandchild_1"

    def test_depth_limit(self):
        """Stop recursion at depth > 10."""
        from opencode_status_bar.api.routes.tracing.builders import (
            build_recursive_children,
        )

        # Create deep tree
        children_by_parent = {}
        for i in range(15):
            children_by_parent[f"node_{i}"] = [
                {
                    "trace_id": f"node_{i + 1}",
                    "started_at": f"2026-01-01T10:{i:02d}:00",
                    "children": [],
                }
            ]

        result = build_recursive_children(children_by_parent, "node_0")

        # Check depth is limited
        def count_depth(node, current=0):
            if not node.get("children"):
                return current
            return max(count_depth(c, current + 1) for c in node["children"])

        max_depth = count_depth({"children": result})
        assert max_depth <= 11  # depth 0-10 = 11 levels


class TestBuildSegmentTimeline:
    """Tests for build_segment_timeline builder function."""

    def test_build_empty_timeline(self):
        """Return empty dict for empty segments."""
        from opencode_status_bar.api.routes.tracing.builders import build_segment_timeline

        result = build_segment_timeline({})
        assert result == {}

    def test_build_sorted_timeline(self):
        """Build sorted timeline per session."""
        from opencode_status_bar.api.routes.tracing.builders import build_segment_timeline

        now = datetime.now()
        segments_by_session = {
            "sess_1": [
                (None, None, None, "plan", now - timedelta(minutes=5)),
                (None, None, None, "code", now - timedelta(minutes=2)),
                (None, None, None, "review", now),
            ]
        }

        result = build_segment_timeline(segments_by_session)

        assert "sess_1" in result
        timeline = result["sess_1"]
        assert len(timeline) == 3
        # Should be sorted by timestamp
        assert timeline[0][1] == "plan"
        assert timeline[1][1] == "code"
        assert timeline[2][1] == "review"

    def test_skip_segments_without_timestamp_or_agent(self):
        """Skip segments missing timestamp or agent."""
        from opencode_status_bar.api.routes.tracing.builders import build_segment_timeline

        now = datetime.now()
        segments_by_session = {
            "sess_1": [
                (None, None, None, None, now),  # No agent
                (None, None, None, "plan", None),  # No timestamp
                (None, None, None, "code", now),  # Valid
            ]
        }

        result = build_segment_timeline(segments_by_session)

        assert len(result["sess_1"]) == 1
        assert result["sess_1"][0][1] == "code"


class TestBuildUserExchange:
    """Tests for build_user_exchange builder function."""

    def test_build_user_exchange(self):
        """Build user exchange node with all fields."""
        from opencode_status_bar.api.routes.tracing.builders import build_user_exchange

        now = datetime.now()
        get_agent_at_time = MagicMock(return_value="plan")

        result = build_user_exchange(
            msg_id="msg_1",
            session_id="sess_1",
            created_at=now,
            content="Hello, world!",
            msg_agent=None,
            get_agent_at_time=get_agent_at_time,
        )

        assert result["trace_id"] == "exchange_msg_1"
        assert result["session_id"] == "sess_1"
        assert result["node_type"] == "user_turn"
        assert result["parent_agent"] == "user"
        assert result["subagent_type"] == "plan"
        assert result["prompt_input"] == "Hello, world!"
        assert result["children"] == []

    def test_use_msg_agent_when_provided(self):
        """Use msg_agent directly when provided."""
        from opencode_status_bar.api.routes.tracing.builders import build_user_exchange

        get_agent_at_time = MagicMock()

        result = build_user_exchange(
            msg_id="msg_1",
            session_id="sess_1",
            created_at=datetime.now(),
            content="Test",
            msg_agent="code",
            get_agent_at_time=get_agent_at_time,
        )

        assert result["subagent_type"] == "code"
        get_agent_at_time.assert_not_called()

    def test_truncate_long_content(self):
        """Truncate content to 500 characters."""
        from opencode_status_bar.api.routes.tracing.builders import build_user_exchange

        long_content = "x" * 1000

        result = build_user_exchange(
            msg_id="msg_1",
            session_id="sess_1",
            created_at=datetime.now(),
            content=long_content,
            msg_agent="plan",
            get_agent_at_time=MagicMock(),
        )

        assert len(result["prompt_input"]) == 500


class TestBuildExchangesFromMessages:
    """Tests for build_exchanges_from_messages builder function."""

    def test_build_empty_exchanges(self):
        """Return empty dict for empty messages."""
        from opencode_status_bar.api.routes.tracing.builders import (
            build_exchanges_from_messages,
        )

        result = build_exchanges_from_messages([], {}, MagicMock())
        assert result == {}

    def test_build_exchanges_user_assistant_pair(self):
        """Build exchange from user + assistant message pair."""
        from opencode_status_bar.api.routes.tracing.builders import (
            build_exchanges_from_messages,
        )

        now = datetime.now()
        # Row format: id, session_id, created_at, role, agent, content, tokens_in, tokens_out, tokens_cache
        msg_rows = [
            ("msg_1", "sess_1", now, "user", "plan", "Hello", None, None, None, None),
            (
                "msg_2",
                "sess_1",
                now + timedelta(seconds=1),
                "assistant",
                "plan",
                "Hi",
                10,
                20,
                5,
                0,
            ),
        ]

        result = build_exchanges_from_messages(
            msg_rows, {}, MagicMock(return_value="plan")
        )

        assert "sess_1" in result
        assert len(result["sess_1"]) == 1
        exchange = result["sess_1"][0]
        assert exchange["prompt_input"] == "Hello"
        assert exchange["tokens_in"] == 10
        assert exchange["tokens_out"] == 20
        assert exchange["cache_read"] == 5

    def test_attach_tools_to_exchange(self):
        """Attach tools from assistant message to exchange."""
        from opencode_status_bar.api.routes.tracing.builders import (
            build_exchanges_from_messages,
        )

        now = datetime.now()
        msg_rows = [
            ("msg_1", "sess_1", now, "user", None, "Hello", None, None, None, None),
            (
                "msg_2",
                "sess_1",
                now + timedelta(seconds=1),
                "assistant",
                None,
                "Hi",
                10,
                20,
                5,
                0,
            ),
        ]
        tools_by_message = {
            "msg_2": [{"id": "tool_1", "node_type": "tool", "tool_name": "bash"}]
        }

        result = build_exchanges_from_messages(
            msg_rows, tools_by_message, MagicMock(return_value="plan")
        )

        assert len(result["sess_1"][0]["children"]) == 1
        assert result["sess_1"][0]["children"][0]["tool_name"] == "bash"


class TestAttachDelegationsToExchanges:
    """Tests for attach_delegations_to_exchanges builder function."""

    def test_attach_empty_delegations(self):
        """Return empty list when no delegations."""
        from opencode_status_bar.api.routes.tracing.builders import (
            attach_delegations_to_exchanges,
        )

        result = attach_delegations_to_exchanges([{"started_at": "2026-01-01"}], [])
        assert result == []

    def test_attach_delegation_to_parent_exchange(self):
        """Attach delegation to the correct parent exchange."""
        from opencode_status_bar.api.routes.tracing.builders import (
            attach_delegations_to_exchanges,
        )

        exchanges = [
            {"started_at": "2026-01-01T10:00:00", "children": []},
            {"started_at": "2026-01-01T10:10:00", "children": []},
        ]
        delegations = [{"started_at": "2026-01-01T10:05:00", "trace_id": "deleg_1"}]

        result = attach_delegations_to_exchanges(exchanges, delegations)

        # Delegation should be attached to first exchange
        assert len(exchanges[0]["children"]) == 1
        assert exchanges[0]["children"][0]["trace_id"] == "deleg_1"
        assert result == []  # All delegations attached

    def test_delegation_before_all_exchanges(self):
        """Add delegation as sibling when before all exchanges."""
        from opencode_status_bar.api.routes.tracing.builders import (
            attach_delegations_to_exchanges,
        )

        exchanges = [
            {"started_at": "2026-01-01T10:00:00", "children": []},
        ]
        delegations = [{"started_at": "2026-01-01T09:00:00", "trace_id": "early_deleg"}]

        attach_delegations_to_exchanges(exchanges, delegations)

        # Delegation should be added to exchanges list
        assert len(exchanges) == 2
        assert exchanges[1]["trace_id"] == "early_deleg"


class TestBuildSessionNode:
    """Tests for build_session_node builder function."""

    def test_build_session_node(self):
        """Build complete session node."""
        from opencode_status_bar.api.routes.tracing.builders import build_session_node

        now = datetime.now()
        # Row format: trace_id, session_id, parent_agent, subagent_type, started_at, ended_at,
        #             duration_ms, tokens_in, tokens_out, status, prompt_input, title, directory, child_session_id
        row = (
            "root_1",
            "sess_1",
            "user",
            "plan",
            now,
            now + timedelta(hours=1),
            3600000,
            100,
            200,
            "completed",
            "Initial prompt",
            "Test Session",
            "/project",
            None,
        )
        agent_children = [
            {"trace_id": "child_1", "children": []},
            {"trace_id": "child_2", "children": [{"trace_id": "grandchild"}]},
        ]
        session_tokens = {
            "tokens_in": 150,
            "tokens_out": 250,
            "cache_read": 500,
            "cache_write": 100,
        }

        result = build_session_node(row, agent_children, session_tokens)

        assert result["session_id"] == "sess_1"
        assert result["trace_id"] == "root_1"
        assert result["node_type"] == "session"
        assert result["agent_type"] == "plan"
        assert result["title"] == "Test Session"
        assert result["directory"] == "/project"
        assert result["tokens_in"] == 150  # From session_tokens
        assert result["tokens_out"] == 250
        assert result["cache_read"] == 500
        assert result["trace_count"] == 3  # 2 children + 1 grandchild

        # Verify complete tokens object
        assert "tokens" in result
        tokens = result["tokens"]
        assert "input" in tokens
        assert "output" in tokens
        assert "cache_read" in tokens
        assert "cache_write" in tokens
        assert "total" in tokens
        assert (
            tokens["total"]
            == tokens["input"]
            + tokens["output"]
            + tokens["cache_read"]
            + tokens["cache_write"]
        )

    def test_build_session_node_fallback_tokens(self):
        """Use row tokens when session_tokens empty."""
        from opencode_status_bar.api.routes.tracing.builders import build_session_node

        now = datetime.now()
        row = (
            "root_1",
            "sess_1",
            "user",
            "plan",
            now,
            now + timedelta(hours=1),
            3600000,
            100,
            200,
            "completed",
            "Prompt",
            "Title",
            "/dir",
            None,
        )

        result = build_session_node(row, [], {})

        assert result["tokens_in"] == 100  # From row
        assert result["tokens_out"] == 200


# =============================================================================
# Fetchers Tests
# =============================================================================


class TestFetchRootTraces:
    """Tests for fetch_root_traces fetcher function."""

    def test_fetch_root_traces(self):
        """Fetch root traces from database."""
        from opencode_status_bar.api.routes.tracing.fetchers import fetch_root_traces

        conn = MagicMock()
        expected_rows = [("root_1", "sess_1", "user", "plan")]
        conn.execute.return_value.fetchall.return_value = expected_rows

        result = fetch_root_traces(conn, datetime.now())

        assert result == expected_rows
        conn.execute.assert_called_once()
        # Check SQL query contains expected clauses
        call_args = conn.execute.call_args[0][0]
        assert "WHERE t.parent_trace_id IS NULL" in call_args
        assert "t.trace_id LIKE 'root_%'" in call_args


class TestFetchSegmentTraces:
    """Tests for fetch_segment_traces fetcher function."""

    def test_fetch_segment_traces_grouped(self):
        """Fetch segment traces grouped by session_id."""
        from opencode_status_bar.api.routes.tracing.fetchers import fetch_segment_traces

        conn = MagicMock()
        segment_rows = [
            ("seg_1", "sess_1", "user", "plan", datetime.now()),
            ("seg_2", "sess_1", "plan", "code", datetime.now()),
            ("seg_3", "sess_2", "user", "plan", datetime.now()),
        ]
        conn.execute.return_value.fetchall.return_value = segment_rows

        result = fetch_segment_traces(conn, datetime.now())

        assert "sess_1" in result
        assert "sess_2" in result
        assert len(result["sess_1"]) == 2
        assert len(result["sess_2"]) == 1


class TestFetchChildTraces:
    """Tests for fetch_child_traces fetcher function."""

    def test_fetch_child_traces(self):
        """Fetch child traces from database."""
        from opencode_status_bar.api.routes.tracing.fetchers import fetch_child_traces

        conn = MagicMock()
        expected_rows = [("child_1", "sess_1", "parent_1", "plan", "code")]
        conn.execute.return_value.fetchall.return_value = expected_rows

        result = fetch_child_traces(conn, datetime.now())

        assert result == expected_rows
        call_args = conn.execute.call_args[0][0]
        assert "WHERE t.parent_trace_id IS NOT NULL" in call_args


class TestFetchMessagesForExchanges:
    """Tests for fetch_messages_for_exchanges fetcher function."""

    def test_fetch_empty_for_no_sessions(self):
        """Return empty list when no session IDs."""
        from opencode_status_bar.api.routes.tracing.fetchers import (
            fetch_messages_for_exchanges,
        )

        conn = MagicMock()
        result = fetch_messages_for_exchanges(conn, set())
        assert result == []
        conn.execute.assert_not_called()

    def test_fetch_messages(self):
        """Fetch messages for exchanges."""
        from opencode_status_bar.api.routes.tracing.fetchers import (
            fetch_messages_for_exchanges,
        )

        conn = MagicMock()
        expected_rows = [("msg_1", "sess_1", datetime.now(), "user", "plan", "Hello")]
        conn.execute.return_value.fetchall.return_value = expected_rows

        result = fetch_messages_for_exchanges(conn, {"sess_1"})

        assert result == expected_rows


class TestFetchSubagentTokens:
    """Tests for fetch_subagent_tokens fetcher function."""

    def test_fetch_subagent_tokens(self):
        """Fetch subagent sessions and tokens."""
        from opencode_status_bar.api.routes.tracing.fetchers import fetch_subagent_tokens

        conn = MagicMock()
        now = datetime.now()
        # First query returns subagent sessions
        subagent_rows = [
            ("sess_sub_1", "@roadmap subagent", now),
            ("sess_sub_2", "@code subagent", now + timedelta(minutes=1)),
        ]
        # Second query returns token aggregation
        token_rows = [
            ("sess_sub_1", 100, 200, 50),
            ("sess_sub_2", 150, 250, 75),
        ]
        conn.execute.return_value.fetchall.side_effect = [subagent_rows, token_rows]

        tokens, by_time = fetch_subagent_tokens(conn, now - timedelta(days=1))

        assert "sess_sub_1" in tokens
        assert tokens["sess_sub_1"]["tokens_in"] == 100
        assert len(by_time) == 2
        assert by_time[0]["agent_type"] == "roadmap"
        assert by_time[1]["agent_type"] == "code"


class TestFetchTokensBySession:
    """Tests for fetch_tokens_by_session fetcher function."""

    def test_fetch_empty_for_no_sessions(self):
        """Return empty dict when no session IDs."""
        from opencode_status_bar.api.routes.tracing.fetchers import fetch_tokens_by_session

        conn = MagicMock()
        result = fetch_tokens_by_session(conn, set())
        assert result == {}

    def test_fetch_tokens_by_session(self):
        """Fetch aggregated tokens per session."""
        from opencode_status_bar.api.routes.tracing.fetchers import fetch_tokens_by_session

        conn = MagicMock()
        token_rows = [
            ("sess_1", 100, 200, 50, 25),
            ("sess_2", 150, 250, 75, 30),
        ]
        conn.execute.return_value.fetchall.return_value = token_rows

        result = fetch_tokens_by_session(conn, {"sess_1", "sess_2"})

        assert result["sess_1"]["tokens_in"] == 100
        assert result["sess_1"]["tokens_out"] == 200
        assert result["sess_1"]["cache_read"] == 50
        assert result["sess_1"]["cache_write"] == 25
        assert result["sess_2"]["tokens_in"] == 150
        assert result["sess_2"]["cache_write"] == 30


class TestGetInitialAgents:
    """Tests for get_initial_agents fetcher function."""

    def test_get_empty_for_no_sessions(self):
        """Return empty dict when no session IDs."""
        from opencode_status_bar.api.routes.tracing.fetchers import get_initial_agents

        conn = MagicMock()
        result = get_initial_agents(conn, set())
        assert result == {}

    def test_get_initial_agents(self):
        """Get initial agent type for each session."""
        from opencode_status_bar.api.routes.tracing.fetchers import get_initial_agents

        conn = MagicMock()
        agent_rows = [
            ("sess_1", "plan", datetime.now()),
            ("sess_2", "code", datetime.now()),
        ]
        conn.execute.return_value.fetchall.return_value = agent_rows

        result = get_initial_agents(conn, {"sess_1", "sess_2"})

        assert result["sess_1"] == "plan"
        assert result["sess_2"] == "code"
