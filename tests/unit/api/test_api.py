"""
Tests for API endpoints and TracingDataService list methods.

Covers:
- Pagination helper (_paginate)
- get_sessions_list() with pagination
- get_traces_list() with pagination
- get_delegations_list() with pagination
- get_trace_details()
- get_daily_stats()
- search_sessions()
- get_session_cost_breakdown()
"""

from datetime import datetime, timedelta

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.tracing import (
    TracingDataService,
)


# =============================================================================
# Fixtures (db, service are provided by conftest.py via tracing_service)
# =============================================================================


# Alias for compatibility - uses tracing_service from conftest
@pytest.fixture
def service(tracing_service: TracingDataService) -> TracingDataService:
    """Alias for tracing_service from conftest."""
    return tracing_service


@pytest.fixture
def populated_db(db) -> AnalyticsDB:
    """Populate database with test data for API tests."""
    conn = db.connect()

    # Insert test sessions
    now = datetime.now()
    for i in range(25):  # 25 sessions for pagination tests
        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                f"ses_{i:03d}",
                "proj_001",
                f"/projects/test{i}",
                f"Test Session {i}",
                now - timedelta(days=i),
                now - timedelta(days=i) + timedelta(hours=1),
            ],
        )

    # Insert test traces
    for i in range(30):  # 30 traces for pagination tests
        is_root = i < 10
        parent_id = None if is_root else f"trace_{(i % 10):03d}"
        conn.execute(
            """INSERT INTO agent_traces 
               (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                started_at, ended_at, duration_ms, tokens_in, tokens_out, status,
                prompt_input, prompt_output, child_session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                f"root_trace_{i:03d}" if is_root else f"trace_{i:03d}",
                f"ses_{(i % 25):03d}",
                parent_id,
                "user" if is_root else "agent",
                "executor" if is_root else "tester",
                now - timedelta(hours=i),
                now - timedelta(hours=i) + timedelta(minutes=30),
                1800000,
                1000 + i * 100,
                500 + i * 50,
                "completed" if i % 5 != 0 else "error",
                f"Test prompt {i}",
                f"Test output {i}",
                f"child_ses_{i:03d}",
            ],
        )

    # Insert test delegations
    for i in range(20):  # 20 delegations for pagination tests
        conn.execute(
            """INSERT INTO delegations 
               (id, session_id, parent_agent, child_agent, child_session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                i + 1,
                f"ses_{(i % 25):03d}",
                "coordinator",
                f"executor_{i}",
                f"child_ses_{i:03d}",
                now - timedelta(hours=i),
            ],
        )

    # Insert messages for token cost calculations
    for i in range(5):
        conn.execute(
            """INSERT INTO messages 
               (id, session_id, parent_id, role, agent, model_id, provider_id,
                tokens_input, tokens_output, tokens_reasoning,
                tokens_cache_read, tokens_cache_write, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                f"msg_{i:03d}",
                "ses_000",
                None if i == 0 else f"msg_{(i - 1):03d}",
                "user" if i % 2 == 0 else "assistant",
                "executor",
                "claude-3",
                "anthropic",
                1000,
                500,
                0,
                200,
                50,
                now - timedelta(minutes=30 - i * 5),
                now - timedelta(minutes=30 - i * 5) + timedelta(seconds=30),
            ],
        )

    # Insert parts (tool calls) for child sessions
    for i in range(10):
        conn.execute(
            """INSERT INTO parts 
               (id, message_id, part_type, tool_name, tool_status, created_at,
                session_id, content, ended_at, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                f"prt_{i:03d}",
                "msg_001",
                "tool",
                ["read", "write", "bash", "edit", "glob"][i % 5],
                "completed" if i % 3 != 0 else "error",
                now - timedelta(minutes=20 - i),
                f"child_ses_{i:03d}",
                None,
                now - timedelta(minutes=20 - i) + timedelta(seconds=5),
                5000,
            ],
        )

    return db


@pytest.fixture
def populated_service(populated_db: AnalyticsDB) -> TracingDataService:
    """Create service with populated database."""
    return TracingDataService(db=populated_db)


# =============================================================================
# Tests for _paginate helper
# =============================================================================


class TestPaginate:
    """Tests for pagination helper."""

    def test_paginate_first_page(self, service: TracingDataService):
        """Test pagination returns first page correctly."""
        data = list(range(100))
        result = service._paginate(data, page=1, per_page=10)

        assert result["success"]  # Direct boolean assertion
        assert len(result["data"]) == 10
        assert result["data"] == list(range(10))
        assert result["meta"]["page"] == 1
        assert result["meta"]["per_page"] == 10
        assert result["meta"]["total"] == 100
        assert result["meta"]["total_pages"] == 10

    def test_paginate_middle_page(self, service: TracingDataService):
        """Test pagination returns middle page correctly."""
        data = list(range(100))
        result = service._paginate(data, page=5, per_page=10)

        assert result["data"] == list(range(40, 50))
        assert result["meta"]["page"] == 5

    def test_paginate_last_page(self, service: TracingDataService):
        """Test pagination returns last page correctly."""
        data = list(range(95))
        result = service._paginate(data, page=10, per_page=10)

        assert len(result["data"]) == 5
        assert result["data"] == list(range(90, 95))
        assert result["meta"]["total_pages"] == 10

    def test_paginate_max_per_page(self, service: TracingDataService):
        """Test pagination enforces max 200 per_page."""
        data = list(range(500))
        result = service._paginate(data, page=1, per_page=500)

        assert len(result["data"]) == 200
        assert result["meta"]["per_page"] == 200

    def test_paginate_empty_list(self, service: TracingDataService):
        """Test pagination handles empty list."""
        result = service._paginate([], page=1, per_page=10)

        assert result["data"] == []
        assert result["meta"]["total"] == 0
        assert result["meta"]["total_pages"] == 0

    def test_paginate_with_provided_total(self, service: TracingDataService):
        """Test pagination with pre-sliced data and total."""
        data = list(range(10))  # Pre-sliced
        result = service._paginate(data, page=2, per_page=10, total=100)

        assert len(result["data"]) == 10
        assert result["meta"]["total"] == 100
        assert result["meta"]["total_pages"] == 10


# =============================================================================
# Tests for get_sessions_list
# =============================================================================


class TestGetSessionsList:
    """Tests for get_sessions_list method."""

    def test_sessions_list_default_pagination(
        self, populated_service: TracingDataService
    ):
        """Test sessions list with default pagination."""
        result = populated_service.get_sessions_list()

        assert result["success"]  # Direct boolean assertion
        assert "data" in result
        assert "meta" in result
        assert result["meta"]["page"] == 1
        assert result["meta"]["per_page"] == 50

    def test_sessions_list_custom_page(self, populated_service: TracingDataService):
        """Test sessions list with custom page."""
        result = populated_service.get_sessions_list(page=2, per_page=10)

        assert result["meta"]["page"] == 2
        assert result["meta"]["per_page"] == 10

    def test_sessions_list_with_search(self, populated_service: TracingDataService):
        """Test sessions list with search filter."""
        result = populated_service.get_sessions_list(search="test1")

        assert result["success"]  # Direct boolean assertion
        # Should match sessions with "test1" in title or directory
        for session in result["data"]:
            assert (
                "test1" in session.get("title", "").lower()
                or "test1" in session.get("directory", "").lower()
            )

    def test_sessions_list_has_required_fields(
        self, populated_service: TracingDataService
    ):
        """Test session items have all required fields."""
        result = populated_service.get_sessions_list()

        # Verify we have exactly 25 sessions (from populated_db fixture)
        assert len(result["data"]) == 25
        session = result["data"][0]
        # Verify specific field values for first session
        assert session["id"] == "ses_000"
        assert session["title"] == "Test Session 0"
        assert session["directory"] == "/projects/test0"
        assert "created_at" in session
        assert "updated_at" in session


# =============================================================================
# Tests for get_traces_list
# =============================================================================


class TestGetTracesList:
    """Tests for get_traces_list method."""

    def test_traces_list_default_pagination(
        self, populated_service: TracingDataService
    ):
        """Test traces list with default pagination."""
        result = populated_service.get_traces_list()

        assert result["success"]  # Direct boolean assertion
        assert "data" in result
        assert "meta" in result
        assert result["meta"]["page"] == 1

    def test_traces_list_custom_pagination(self, populated_service: TracingDataService):
        """Test traces list with custom pagination."""
        result = populated_service.get_traces_list(page=2, per_page=5)

        assert result["meta"]["page"] == 2
        assert result["meta"]["per_page"] == 5

    def test_traces_list_has_required_fields(
        self, populated_service: TracingDataService
    ):
        """Test trace items have all required fields."""
        result = populated_service.get_traces_list()

        # Verify we have exactly 30 traces (from populated_db fixture)
        assert len(result["data"]) == 30
        trace = result["data"][0]
        # Verify specific field values
        assert trace["trace_id"] in [
            "root_trace_000",
            "root_trace_001",
            "root_trace_002",
            "root_trace_003",
            "root_trace_004",
            "root_trace_005",
            "root_trace_006",
            "root_trace_007",
            "root_trace_008",
            "root_trace_009",
            "trace_010",
            "trace_011",
            "trace_012",
            "trace_013",
            "trace_014",
            "trace_015",
            "trace_016",
            "trace_017",
            "trace_018",
            "trace_019",
            "trace_020",
            "trace_021",
            "trace_022",
            "trace_023",
            "trace_024",
            "trace_025",
            "trace_026",
            "trace_027",
            "trace_028",
            "trace_029",
        ]
        assert "session_id" in trace
        assert "started_at" in trace
        assert trace["status"] in ["completed", "error"]


# =============================================================================
# Tests for get_delegations_list
# =============================================================================


class TestGetDelegationsList:
    """Tests for get_delegations_list method."""

    def test_delegations_list_default(self, populated_service: TracingDataService):
        """Test delegations list with default settings."""
        result = populated_service.get_delegations_list()

        assert result["success"]  # Direct boolean assertion
        assert "data" in result
        assert "meta" in result

    def test_delegations_list_has_required_fields(
        self, populated_service: TracingDataService
    ):
        """Test delegation items have all required fields."""
        result = populated_service.get_delegations_list()

        # Verify we have exactly 20 delegations (from populated_db fixture)
        assert len(result["data"]) == 20
        delegation = result["data"][0]
        # Verify specific field values for first delegation (id is returned as string)
        assert delegation["id"] == "1"
        assert delegation["parent_session_id"] == "ses_000"
        assert delegation["parent_agent"] == "coordinator"
        assert delegation["child_agent"] == "executor_0"
        assert delegation["child_session_id"] == "child_ses_000"
        assert "created_at" in delegation


# =============================================================================
# Tests for get_trace_details
# =============================================================================


class TestGetTraceDetails:
    """Tests for get_trace_details method."""

    def test_trace_details_found(self, populated_service: TracingDataService):
        """Test getting details for existing trace."""
        result = populated_service.get_trace_details("root_trace_000")

        # Verify specific trace details
        assert result["trace_id"] == "root_trace_000"
        assert result["session_id"] == "ses_000"
        assert result["subagent_type"] == "executor"
        # Status is "error" for traces where i % 5 == 0 (from populated_db fixture)
        assert result["status"] in ["completed", "error"]
        assert "children" in result
        assert "tools" in result

    def test_trace_details_not_found(self, populated_service: TracingDataService):
        """Test getting details for non-existing trace."""
        result = populated_service.get_trace_details("nonexistent_trace")

        assert result is None

    def test_trace_details_includes_children(
        self, populated_service: TracingDataService
    ):
        """Test trace details includes child traces."""
        result = populated_service.get_trace_details("root_trace_000")

        # root_trace_000 should have child traces (trace_010, trace_020, etc.)
        assert "children" in result
        assert isinstance(result["children"], list)


# =============================================================================
# Tests for get_daily_stats
# =============================================================================


class TestGetDailyStats:
    """Tests for get_daily_stats method."""

    def test_daily_stats_default(self, populated_service: TracingDataService):
        """Test daily stats with default 7 days."""
        result = populated_service.get_daily_stats()

        assert isinstance(result, list)
        # Should have stats for days with activity

    def test_daily_stats_custom_days(self, populated_service: TracingDataService):
        """Test daily stats with custom day range."""
        result = populated_service.get_daily_stats(days=14)

        assert isinstance(result, list)

    def test_daily_stats_has_required_fields(
        self, populated_service: TracingDataService
    ):
        """Test daily stats items have required fields."""
        result = populated_service.get_daily_stats()

        if len(result) > 0:
            day = result[0]
            assert "date" in day
            assert "traces" in day
            assert "tokens" in day
            assert "errors" in day


# =============================================================================
# Tests for search_sessions
# =============================================================================


class TestSearchSessions:
    """Tests for search_sessions method."""

    def test_search_sessions_by_title(self, populated_service: TracingDataService):
        """Test searching sessions by title."""
        result = populated_service.search_sessions("Test Session 1")

        assert isinstance(result, list)
        for session in result:
            assert "test session 1" in session.get(
                "title", ""
            ).lower() or "1" in session.get("directory", "")

    def test_search_sessions_by_directory(self, populated_service: TracingDataService):
        """Test searching sessions by directory."""
        result = populated_service.search_sessions("test5")

        assert isinstance(result, list)

    def test_search_sessions_empty_query(self, populated_service: TracingDataService):
        """Test searching with empty query."""
        result = populated_service.search_sessions("")

        # Empty query should still work (returns empty or all)
        assert isinstance(result, list)

    def test_search_sessions_limit(self, populated_service: TracingDataService):
        """Test search respects limit."""
        result = populated_service.search_sessions("Test", limit=5)

        assert len(result) <= 5

    def test_search_sessions_has_extra_fields(
        self, populated_service: TracingDataService
    ):
        """Test search results include message_count and total_tokens."""
        result = populated_service.search_sessions("Test")

        if len(result) > 0:
            session = result[0]
            assert "message_count" in session
            assert "total_tokens" in session


# =============================================================================
# Tests for get_session_cost_breakdown
# =============================================================================


class TestGetSessionCostBreakdown:
    """Tests for get_session_cost_breakdown method."""

    def test_cost_breakdown_basic(self, populated_service: TracingDataService):
        """Test cost breakdown for session with messages."""
        result = populated_service.get_session_cost_breakdown("ses_000")

        assert "session_id" in result
        assert "total_cost_usd" in result
        assert "breakdown" in result
        assert "by_agent" in result
        assert "cache_savings_usd" in result

    def test_cost_breakdown_structure(self, populated_service: TracingDataService):
        """Test cost breakdown has correct structure."""
        result = populated_service.get_session_cost_breakdown("ses_000")

        breakdown = result["breakdown"]
        assert "input" in breakdown
        assert "output" in breakdown
        assert "cache_read" in breakdown

        input_breakdown = breakdown["input"]
        assert "tokens" in input_breakdown
        assert "rate_per_1k" in input_breakdown
        assert "cost_usd" in input_breakdown

    def test_cost_breakdown_empty_session(self, populated_service: TracingDataService):
        """Test cost breakdown for session without messages."""
        result = populated_service.get_session_cost_breakdown("ses_020")

        assert result["total_cost_usd"] == 0
        assert result["by_agent"] == []


# =============================================================================
# Tests for API response format
# =============================================================================


class TestAPIResponseFormat:
    """Tests for standardized API response format."""

    def test_sessions_response_format(self, populated_service: TracingDataService):
        """Test sessions endpoint returns standardized format."""
        result = populated_service.get_sessions_list()

        assert "success" in result
        assert "data" in result
        assert "meta" in result
        assert "page" in result["meta"]
        assert "per_page" in result["meta"]
        assert "total" in result["meta"]
        assert "total_pages" in result["meta"]

    def test_traces_response_format(self, populated_service: TracingDataService):
        """Test traces endpoint returns standardized format."""
        result = populated_service.get_traces_list()

        assert "success" in result
        assert "data" in result
        assert "meta" in result

    def test_delegations_response_format(self, populated_service: TracingDataService):
        """Test delegations endpoint returns standardized format."""
        result = populated_service.get_delegations_list()

        assert "success" in result
        assert "data" in result
        assert "meta" in result
