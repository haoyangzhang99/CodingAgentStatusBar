"""
Tests for Plan 45 Timeline API endpoints.

Covers:
- GET /api/session/{id}/timeline/full
- GET /api/session/{id}/exchanges
- GET /api/session/{id}/delegations
- Service layer methods: get_session_timeline_full, get_session_exchanges, get_delegation_tree
"""

from datetime import datetime, timedelta

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.tracing import TracingDataService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service(tracing_service: TracingDataService) -> TracingDataService:
    """Alias for tracing_service from conftest."""
    return tracing_service


@pytest.fixture
def timeline_db(db: AnalyticsDB) -> AnalyticsDB:
    """Populate database with test data for timeline tests."""
    conn = db.connect()
    now = datetime.now()

    # Insert test session
    conn.execute(
        """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "ses_timeline_001",
            "proj_001",
            "/projects/test",
            "Timeline Test Session",
            now - timedelta(hours=2),
            now,
        ],
    )

    # Insert parent session for delegation tests
    conn.execute(
        """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "ses_parent_001",
            "proj_001",
            "/projects/parent",
            "Parent Session",
            now - timedelta(hours=3),
            now - timedelta(hours=1),
        ],
    )

    # Insert child session for delegation tests
    conn.execute(
        """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "ses_child_001",
            "proj_001",
            "/projects/child",
            "Child Session",
            now - timedelta(hours=2),
            now - timedelta(hours=1, minutes=30),
        ],
    )

    # Insert messages for timeline test
    # User message
    conn.execute(
        """INSERT INTO messages 
           (id, session_id, role, agent, model_id, provider_id,
            tokens_input, tokens_output, tokens_reasoning,
            created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "msg_user_001",
            "ses_timeline_001",
            "user",
            None,
            None,
            None,
            0,
            0,
            0,
            now - timedelta(hours=2),
            now - timedelta(hours=2),
        ],
    )

    # Assistant message
    conn.execute(
        """INSERT INTO messages 
           (id, session_id, role, agent, model_id, provider_id,
            tokens_input, tokens_output, tokens_reasoning,
            created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "msg_asst_001",
            "ses_timeline_001",
            "assistant",
            "dev",
            "claude-3",
            "anthropic",
            1000,
            500,
            100,
            now - timedelta(hours=1, minutes=55),
            now - timedelta(hours=1, minutes=50),
        ],
    )

    # Insert parts for timeline test
    # User text part
    conn.execute(
        """INSERT INTO parts 
           (id, session_id, message_id, part_type, content, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "prt_text_001",
            "ses_timeline_001",
            "msg_user_001",
            "text",
            "This is the user prompt content",
            now - timedelta(hours=2),
        ],
    )

    # Reasoning part
    conn.execute(
        """INSERT INTO parts 
           (id, session_id, message_id, part_type, reasoning_text, anthropic_signature,
            created_at, ended_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "prt_reason_001",
            "ses_timeline_001",
            "msg_asst_001",
            "reasoning",
            "Let me analyze this request...",
            "signature_abc123",
            now - timedelta(hours=1, minutes=55),
            now - timedelta(hours=1, minutes=54),
        ],
    )

    # Tool call part
    conn.execute(
        """INSERT INTO parts 
           (id, session_id, message_id, part_type, tool_name, tool_status,
            arguments, result_summary, duration_ms, created_at, ended_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "prt_tool_001",
            "ses_timeline_001",
            "msg_asst_001",
            "tool",
            "read",
            "completed",
            '{"filePath": "/src/main.py"}',
            "File content here...",
            150,
            now - timedelta(hours=1, minutes=53),
            now - timedelta(hours=1, minutes=52),
        ],
    )

    # Assistant response text part
    conn.execute(
        """INSERT INTO parts 
           (id, session_id, message_id, part_type, content, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "prt_text_002",
            "ses_timeline_001",
            "msg_asst_001",
            "text",
            "This is the assistant response content",
            now - timedelta(hours=1, minutes=50),
        ],
    )

    # Insert exchanges table data
    conn.execute(
        """INSERT INTO exchanges 
           (id, session_id, exchange_number, user_message_id, assistant_message_id,
            prompt_input, prompt_output, started_at, ended_at, duration_ms,
            tokens_in, tokens_out, tokens_reasoning, cost,
            tool_count, reasoning_count, agent, model_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "exc_001",
            "ses_timeline_001",
            1,
            "msg_user_001",
            "msg_asst_001",
            "This is the user prompt content",
            "This is the assistant response content",
            now - timedelta(hours=2),
            now - timedelta(hours=1, minutes=50),
            600000,  # 10 minutes
            1000,
            500,
            100,
            0.015,
            1,
            1,
            "dev",
            "claude-3",
        ],
    )

    # Insert exchange traces
    conn.execute(
        """INSERT INTO exchange_traces 
           (id, session_id, exchange_id, event_type, event_order, event_data,
            timestamp, duration_ms, tokens_in, tokens_out)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "evt_001",
            "ses_timeline_001",
            "exc_001",
            "reasoning",
            1,
            '{"text": "Let me analyze...", "has_signature": true, "signature": "sig123"}',
            now - timedelta(hours=1, minutes=55),
            60000,
            0,
            0,
        ],
    )

    conn.execute(
        """INSERT INTO exchange_traces 
           (id, session_id, exchange_id, event_type, event_order, event_data,
            timestamp, duration_ms, tokens_in, tokens_out)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "evt_002",
            "ses_timeline_001",
            "exc_001",
            "tool_call",
            2,
            '{"tool_name": "read", "status": "completed", "arguments": {"filePath": "/src/main.py"}}',
            now - timedelta(hours=1, minutes=53),
            150,
            0,
            0,
        ],
    )

    # Insert delegation for parent session
    conn.execute(
        """INSERT INTO delegations 
           (id, session_id, parent_agent, child_agent, child_session_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "del_001",
            "ses_parent_001",
            "coordinator",
            "dev",
            "ses_child_001",
            now - timedelta(hours=2),
        ],
    )

    # Insert messages for parent session
    conn.execute(
        """INSERT INTO messages 
           (id, session_id, role, agent, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        [
            "msg_parent_001",
            "ses_parent_001",
            "assistant",
            "coordinator",
            now - timedelta(hours=3),
        ],
    )

    # Insert messages for child session
    conn.execute(
        """INSERT INTO messages 
           (id, session_id, role, agent, created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "msg_child_001",
            "ses_child_001",
            "assistant",
            "dev",
            now - timedelta(hours=2),
            now - timedelta(hours=1, minutes=30),
        ],
    )

    return db


@pytest.fixture
def timeline_service(timeline_db: AnalyticsDB) -> TracingDataService:
    """Create service with timeline test database."""
    return TracingDataService(db=timeline_db)


# =============================================================================
# Tests for get_session_timeline_full
# =============================================================================


class TestGetSessionTimelineFull:
    """Tests for get_session_timeline_full method."""

    def test_timeline_returns_success(self, timeline_service: TracingDataService):
        """Test timeline endpoint returns success for existing session."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert result["success"]
        assert "data" in result
        # Verify data structure exists and has expected keys
        assert "meta" in result["data"]
        assert "session" in result["data"]
        assert "timeline" in result["data"]
        assert "summary" in result["data"]

    def test_timeline_returns_meta(self, timeline_service: TracingDataService):
        """Test timeline includes meta information."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert "meta" in result["data"]
        meta = result["data"]["meta"]
        assert meta["session_id"] == "ses_timeline_001"
        assert "generated_at" in meta
        assert "title" in meta
        assert "directory" in meta

    def test_timeline_returns_session_info(self, timeline_service: TracingDataService):
        """Test timeline includes session information."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert "session" in result["data"]
        session = result["data"]["session"]
        assert session["id"] == "ses_timeline_001"
        assert "title" in session
        assert "directory" in session
        assert "started_at" in session
        assert "ended_at" in session

    def test_timeline_returns_events(self, timeline_service: TracingDataService):
        """Test timeline includes chronological events."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert "timeline" in result["data"]
        timeline = result["data"]["timeline"]
        assert isinstance(timeline, list)
        # Verify we have at least one event (we inserted test data)
        assert len(timeline) >= 1

        for event in timeline:
            assert "timestamp" in event, f"Event {event.get('type')} missing timestamp"
            # Verify timestamp is a valid ISO string, not just "not None"
            assert isinstance(event["timestamp"], str), (
                f"Event {event.get('type')} timestamp must be string"
            )
            assert event["timestamp"], f"Event {event.get('type')} has empty timestamp"
            assert "exchange_number" in event
            assert event["exchange_number"] >= 1, "Exchange number must be >= 1"

        timestamps = [e["timestamp"] for e in timeline if e.get("timestamp")]
        if len(timestamps) > 1:
            for i in range(len(timestamps) - 1):
                assert timestamps[i] <= timestamps[i + 1], (
                    "Timeline events not chronologically sorted"
                )

    def test_timeline_events_have_type(self, timeline_service: TracingDataService):
        """Test each timeline event has a type."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        timeline = result["data"]["timeline"]
        for event in timeline:
            assert "type" in event
            assert event["type"] in [
                "user_prompt",
                "delegation_result",
                "reasoning",
                "tool_call",
                "step_finish",
                "patch",
                "assistant_response",
            ]

    def test_timeline_events_have_exchange_number(
        self, timeline_service: TracingDataService
    ):
        """Test each timeline event has exchange_number."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        timeline = result["data"]["timeline"]
        for event in timeline:
            assert "exchange_number" in event
            assert isinstance(event["exchange_number"], int)

    def test_timeline_returns_summary(self, timeline_service: TracingDataService):
        """Test timeline includes summary statistics."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert "summary" in result["data"]
        summary = result["data"]["summary"]
        assert "total_exchanges" in summary
        assert "total_tokens" in summary
        assert "total_cost_usd" in summary
        assert "total_tool_calls" in summary
        assert "total_reasoning_entries" in summary

    def test_timeline_not_found(self, timeline_service: TracingDataService):
        """Test timeline returns error for non-existing session."""
        result = timeline_service.get_session_timeline_full("nonexistent_session")

        assert not result["success"]
        assert "error" in result

    def test_timeline_user_prompt_content(self, timeline_service: TracingDataService):
        """Test user prompt events have full content."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        user_prompts = [
            e for e in result["data"]["timeline"] if e["type"] == "user_prompt"
        ]
        # We inserted test data with user prompts
        assert len(user_prompts) >= 1

        for prompt in user_prompts:
            assert "content" in prompt
            # Verify actual content value, not just existence
            assert isinstance(prompt["content"], str), (
                "User prompt content must be string"
            )
            assert prompt["content"], "User prompt content must not be empty"
            # For our test data, verify it matches expected content
            if prompt.get("message_id") == "msg_user_001":
                assert prompt["content"] == "This is the user prompt content"

            assert "message_id" in prompt
            # Verify message_id format (msg_*)
            assert isinstance(prompt["message_id"], str), "message_id must be string"
            assert prompt["message_id"].startswith("msg_"), (
                "message_id must start with 'msg_'"
            )

            assert "timestamp" in prompt
            # Verify timestamp is valid ISO format string
            assert isinstance(prompt["timestamp"], str), "timestamp must be string"
            assert prompt["timestamp"], "timestamp must not be empty"

    def test_timeline_reasoning_text_complete(
        self, timeline_service: TracingDataService
    ):
        """Test reasoning events have non-empty text."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        reasoning_events = [
            e for e in result["data"]["timeline"] if e["type"] == "reasoning"
        ]

        if len(reasoning_events) > 0:
            for reasoning in reasoning_events:
                assert "entries" in reasoning, "Reasoning event missing entries field"
                # Verify entries is a list with content
                assert isinstance(reasoning["entries"], list), (
                    "Reasoning entries must be a list"
                )
                assert len(reasoning["entries"]) >= 1, (
                    "Reasoning entries must have at least one entry"
                )

                for entry in reasoning["entries"]:
                    assert "text" in entry, "Reasoning entry missing text field"
                    # Verify text is a non-empty string
                    assert isinstance(entry["text"], str), (
                        "Reasoning text must be string"
                    )
                    assert entry["text"], "Reasoning text must not be empty"

    def test_timeline_tool_call_has_details(self, timeline_service: TracingDataService):
        """Test tool call events have necessary details."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        tool_calls = [e for e in result["data"]["timeline"] if e["type"] == "tool_call"]
        if len(tool_calls) > 0:
            for tool in tool_calls:
                assert "tool_name" in tool, "Tool call missing tool_name"
                # Verify tool_name is a valid non-empty string
                assert isinstance(tool["tool_name"], str), "Tool name must be string"
                assert tool["tool_name"], "Tool name must not be empty"
                # For our test data, verify it's "read"
                if tool.get("tool_name") == "read":
                    assert tool["tool_name"] == "read"

                assert "status" in tool, "Tool call missing status"
                # Verify status is one of the valid values
                assert tool["status"] in ["completed", "failed", "pending"], (
                    f"Invalid tool status: {tool['status']}"
                )

                if "arguments" in tool and tool["arguments"]:
                    assert isinstance(tool["arguments"], dict), (
                        "Tool arguments must be dict"
                    )

                if "duration_ms" in tool and tool["duration_ms"] is not None:
                    # Duration should be a positive number for completed tools
                    assert isinstance(tool["duration_ms"], (int, float)), (
                        "duration_ms must be numeric"
                    )
                    assert tool["duration_ms"] >= 0, "Duration must be non-negative"


# =============================================================================
# Tests for get_session_exchanges
# =============================================================================


class TestGetSessionExchanges:
    """Tests for get_session_exchanges method."""

    def test_exchanges_returns_meta(self, timeline_service: TracingDataService):
        """Test exchanges endpoint returns meta information."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        assert "meta" in result
        assert result["meta"]["session_id"] == "ses_timeline_001"
        assert "count" in result["meta"]
        assert "generated_at" in result["meta"]

    def test_exchanges_returns_list(self, timeline_service: TracingDataService):
        """Test exchanges endpoint returns list of exchanges."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        assert "exchanges" in result
        assert isinstance(result["exchanges"], list)
        # We inserted test data with 1 exchange
        assert len(result["exchanges"]) == 1

    def test_exchange_has_number(self, timeline_service: TracingDataService):
        """Test each exchange has a number."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "number" in exchange
            assert isinstance(exchange["number"], int)
            assert exchange["number"] >= 1

    def test_exchange_has_user_prompt(self, timeline_service: TracingDataService):
        """Test each exchange has user prompt content."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "user_prompt" in exchange
            assert isinstance(exchange["user_prompt"], str)

    def test_exchange_has_assistant_response(
        self, timeline_service: TracingDataService
    ):
        """Test each exchange has assistant response content."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "assistant_response" in exchange
            assert isinstance(exchange["assistant_response"], str)

    def test_exchange_has_tokens(self, timeline_service: TracingDataService):
        """Test each exchange has token counts."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "tokens" in exchange
            tokens = exchange["tokens"]
            assert "input" in tokens
            assert "output" in tokens
            assert "reasoning" in tokens

    def test_exchange_has_timing(self, timeline_service: TracingDataService):
        """Test each exchange has timing information."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "started_at" in exchange
            assert "ended_at" in exchange
            assert "duration_ms" in exchange

    def test_exchange_has_tool_count(self, timeline_service: TracingDataService):
        """Test each exchange has tool_count."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "tool_count" in exchange
            assert isinstance(exchange["tool_count"], int)

    def test_exchange_has_reasoning_count(self, timeline_service: TracingDataService):
        """Test each exchange has reasoning_count."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "reasoning_count" in exchange
            assert isinstance(exchange["reasoning_count"], int)

    def test_exchanges_empty_session(self, timeline_service: TracingDataService):
        """Test exchanges returns empty for session without messages."""
        result = timeline_service.get_session_exchanges("nonexistent_session")

        assert "exchanges" in result
        assert result["exchanges"] == []


# =============================================================================
# Tests for get_delegation_tree
# =============================================================================


class TestGetDelegationTree:
    """Tests for get_delegation_tree method."""

    def test_delegation_tree_returns_meta(self, timeline_service: TracingDataService):
        """Test delegation tree returns meta information."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        assert "meta" in result
        assert result["meta"]["session_id"] == "ses_parent_001"
        assert "generated_at" in result["meta"]

    def test_delegation_tree_returns_summary(
        self, timeline_service: TracingDataService
    ):
        """Test delegation tree returns summary statistics."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        assert "summary" in result
        summary = result["summary"]
        assert "total_delegations" in summary
        assert "max_depth" in summary
        assert "agents_involved" in summary

    def test_delegation_tree_returns_tree(self, timeline_service: TracingDataService):
        """Test delegation tree returns tree structure."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        assert "tree" in result
        tree = result["tree"]
        # Verify tree structure is complete
        assert isinstance(tree, dict), "tree must be a dictionary"
        assert "session_id" in tree
        assert tree["session_id"] == "ses_parent_001"
        assert "agent" in tree
        assert isinstance(tree["agent"], str), "agent must be string"
        assert "children" in tree
        assert isinstance(tree["children"], list), "children must be list"

    def test_delegation_tree_has_children(self, timeline_service: TracingDataService):
        """Test delegation tree includes children."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        tree = result["tree"]
        assert isinstance(tree["children"], list)
        # We inserted 1 child delegation in test data
        assert len(tree["children"]) == 1

    def test_delegation_child_has_session_id(
        self, timeline_service: TracingDataService
    ):
        """Test child nodes have session_id."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        if len(result["tree"]["children"]) > 0:
            child = result["tree"]["children"][0]
            assert "session_id" in child
            assert child["session_id"] == "ses_child_001"

    def test_delegation_child_has_agent(self, timeline_service: TracingDataService):
        """Test child nodes have agent."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        if len(result["tree"]["children"]) > 0:
            child = result["tree"]["children"][0]
            assert "agent" in child

    def test_delegation_child_has_status(self, timeline_service: TracingDataService):
        """Test child nodes have status."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        if len(result["tree"]["children"]) > 0:
            child = result["tree"]["children"][0]
            assert "status" in child

    def test_delegation_tree_agents_involved(
        self, timeline_service: TracingDataService
    ):
        """Test agents_involved list in summary."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        agents = result["summary"]["agents_involved"]
        assert isinstance(agents, list)
        # We have coordinator and dev agents in test data
        assert len(agents) >= 1
        # Verify agents are strings
        for agent in agents:
            assert isinstance(agent, str), "agent must be string"
            assert agent, "agent name must not be empty"

    def test_delegation_tree_session_not_found(
        self, timeline_service: TracingDataService
    ):
        """Test delegation tree handles missing session."""
        result = timeline_service.get_delegation_tree("nonexistent_session")

        assert "tree" in result
        assert result["tree"] is None
        assert "error" in result["meta"]

    def test_delegation_tree_no_delegations(self, timeline_service: TracingDataService):
        """Test delegation tree for session without delegations."""
        result = timeline_service.get_delegation_tree("ses_timeline_001")

        assert "tree" in result
        if result["tree"]:
            assert result["tree"]["children"] == []


# =============================================================================
# Tests for fallback methods (when exchanges table is empty)
# =============================================================================


class TestFallbackMethods:
    """Tests for fallback timeline building from parts."""

    def test_build_timeline_from_parts(self, timeline_service: TracingDataService):
        """Test _build_timeline_from_parts returns events."""
        timeline = timeline_service._build_timeline_from_parts("ses_timeline_001")

        assert isinstance(timeline, list)
        # Should have user_prompt, reasoning, tool_call, assistant_response
        types = [e["type"] for e in timeline]
        assert "user_prompt" in types or len(timeline) == 0

    def test_calculate_timeline_stats(self, timeline_service: TracingDataService):
        """Test _calculate_timeline_stats returns stats dict."""
        stats = timeline_service._calculate_timeline_stats("ses_timeline_001")

        assert "total_tokens" in stats
        assert "total_cost" in stats
        assert "total_tool_calls" in stats
        assert "total_reasoning" in stats

    def test_build_exchanges_from_messages(self, timeline_service: TracingDataService):
        """Test _build_exchanges_from_messages returns exchange list."""
        exchanges = timeline_service._build_exchanges_from_messages("ses_timeline_001")

        assert isinstance(exchanges, list)
        if len(exchanges) > 0:
            ex = exchanges[0]
            assert "number" in ex
            assert "user_prompt" in ex
            assert "assistant_response" in ex


# =============================================================================
# Tests for response format compliance
# =============================================================================


class TestResponseFormat:
    """Tests for API response format compliance."""

    def test_timeline_response_format(self, timeline_service: TracingDataService):
        """Test timeline response matches Plan 45 spec."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        # Check top-level structure
        assert "success" in result
        assert "data" in result

        data = result["data"]
        assert "meta" in data
        assert "session" in data
        assert "timeline" in data
        assert "summary" in data

    def test_exchanges_response_format(self, timeline_service: TracingDataService):
        """Test exchanges response format."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        assert "meta" in result
        assert "exchanges" in result

    def test_delegations_response_format(self, timeline_service: TracingDataService):
        """Test delegations response format."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        assert "meta" in result
        assert "summary" in result
        assert "tree" in result


# =============================================================================
# Tests for continuation detection and child session inline
# =============================================================================


class TestContinuationAndChildSessionInline:
    """Tests for continuation detection and child session inline features."""

    @pytest.fixture
    def continuation_db(self, db: AnalyticsDB) -> AnalyticsDB:
        """Setup test data for continuation and child session inline tests."""
        conn = db.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "ses_continuation_001",
                "proj_001",
                "/projects/test",
                "Continuation Test Session",
                now - timedelta(hours=2),
                now,
            ],
        )

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "ses_librarian_001",
                "proj_001",
                "/projects/test",
                "Librarian Child Session",
                now - timedelta(hours=1, minutes=45),
                now - timedelta(hours=1, minutes=30),
            ],
        )

        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_user_cont_001",
                "ses_continuation_001",
                "user",
                None,
                now - timedelta(hours=2),
            ],
        )

        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_asst_cont_001",
                "ses_continuation_001",
                "assistant",
                "build",
                now - timedelta(hours=1, minutes=50),
            ],
        )

        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_asst_cont_002",
                "ses_continuation_001",
                "assistant",
                "build",
                now - timedelta(hours=1, minutes=30),
            ],
        )

        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_lib_user_001",
                "ses_librarian_001",
                "user",
                None,
                now - timedelta(hours=1, minutes=45),
            ],
        )

        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_lib_asst_001",
                "ses_librarian_001",
                "assistant",
                "librarian",
                now - timedelta(hours=1, minutes=40),
            ],
        )

        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_cont_001",
                "ses_continuation_001",
                1,
                "msg_user_cont_001",
                "msg_asst_cont_001",
                "Find the latest changelogs",
                "I will delegate to librarian...",
                now - timedelta(hours=2),
                now - timedelta(hours=1, minutes=50),
                600000,
                500,
                200,
                50,
                0.01,
                1,
                1,
                "build",
                "claude-3",
            ],
        )

        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_cont_002",
                "ses_continuation_001",
                2,
                "msg_user_cont_001",
                "msg_asst_cont_002",
                "Find the latest changelogs",
                "Based on the librarian's findings...",
                now - timedelta(hours=1, minutes=35),
                now - timedelta(hours=1, minutes=30),
                300000,
                300,
                400,
                100,
                0.02,
                0,
                1,
                "build",
                "claude-3",
            ],
        )

        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_lib_001",
                "ses_librarian_001",
                1,
                "msg_lib_user_001",
                "msg_lib_asst_001",
                "Search for OpenCode changelogs",
                "I found three changelog entries...",
                now - timedelta(hours=1, minutes=45),
                now - timedelta(hours=1, minutes=40),
                300000,
                200,
                300,
                50,
                0.008,
                1,
                1,
                "librarian",
                "claude-3",
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_cont_001",
                "ses_continuation_001",
                "exc_cont_001",
                "tool_call",
                1,
                '{"tool_name": "mcp_task", "status": "completed", '
                '"arguments": {"subagent_type": "librarian", "description": "Search changelogs"}, '
                '"result_summary": "Found 3 changelog entries for OpenCode versions.", '
                '"child_session_id": "ses_librarian_001"}',
                now - timedelta(hours=1, minutes=55),
                900000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_lib_001",
                "ses_librarian_001",
                "exc_lib_001",
                "reasoning",
                1,
                '{"text": "Searching for changelogs...", "has_signature": false}',
                now - timedelta(hours=1, minutes=44),
                30000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_lib_002",
                "ses_librarian_001",
                "exc_lib_001",
                "tool_call",
                2,
                '{"tool_name": "web_search", "status": "completed", '
                '"arguments": {"query": "OpenCode changelog"}, '
                '"result_summary": "Found changelog page"}',
                now - timedelta(hours=1, minutes=42),
                60000,
                0,
                0,
            ],
        )

        return db

    @pytest.fixture
    def continuation_service(self, continuation_db: AnalyticsDB) -> TracingDataService:
        """Create TracingDataService with continuation test data."""
        return TracingDataService(continuation_db)

    def test_continuation_uses_delegation_result(
        self, continuation_service: TracingDataService
    ):
        """Test that repeated user_msg_id produces delegation_result instead of user_prompt."""
        result = continuation_service.get_session_timeline_full(
            "ses_continuation_001", include_children=False
        )

        assert result["success"]
        timeline = result["data"]["timeline"]

        user_prompts = [e for e in timeline if e["type"] == "user_prompt"]
        delegation_results = [e for e in timeline if e["type"] == "delegation_result"]

        assert len(user_prompts) == 1, (
            "Should have exactly one user_prompt for exchange 1"
        )
        assert len(delegation_results) == 1, (
            "Should have exactly one delegation_result for exchange 2"
        )

        assert user_prompts[0]["exchange_number"] == 1
        assert delegation_results[0]["exchange_number"] == 2
        assert delegation_results[0]["content"] == (
            "Found 3 changelog entries for OpenCode versions."
        )

    def test_child_session_inline_with_include_children(
        self, continuation_service: TracingDataService
    ):
        """Test that child session events are inlined when include_children=True."""
        result = continuation_service.get_session_timeline_full(
            "ses_continuation_001", include_children=True, depth=1
        )

        assert result["success"]
        timeline = result["data"]["timeline"]

        child_events = [
            e for e in timeline if e.get("from_child_session") == "ses_librarian_001"
        ]

        assert len(child_events) >= 1, "Should have inlined child session events"

        child_reasoning = [e for e in child_events if e["type"] == "reasoning"]
        child_tool_calls = [e for e in child_events if e["type"] == "tool_call"]

        assert len(child_reasoning) >= 1, "Should include child reasoning events"
        assert len(child_tool_calls) >= 1, "Should include child tool call events"

        for evt in child_events:
            assert "original_exchange_number" in evt
            assert evt["original_exchange_number"] == 1

    def test_child_session_not_inlined_without_flag(
        self, continuation_service: TracingDataService
    ):
        """Test that child session events are NOT inlined when include_children=False."""
        result = continuation_service.get_session_timeline_full(
            "ses_continuation_001", include_children=False
        )

        assert result["success"]
        timeline = result["data"]["timeline"]

        child_events = [
            e for e in timeline if e.get("from_child_session") == "ses_librarian_001"
        ]

        assert len(child_events) == 0, "Should NOT have inlined child session events"

    def test_timeline_preserves_chronological_order_with_inline(
        self, continuation_service: TracingDataService
    ):
        """Test timeline remains chronologically ordered with inline child events."""
        result = continuation_service.get_session_timeline_full(
            "ses_continuation_001", include_children=True, depth=1
        )

        assert result["success"]
        timeline = result["data"]["timeline"]

        tool_call_idx = None
        first_child_idx = None
        for i, evt in enumerate(timeline):
            if evt["type"] == "tool_call" and evt.get("child_session_id"):
                tool_call_idx = i
            if evt.get("from_child_session") and first_child_idx is None:
                first_child_idx = i

        if tool_call_idx is not None and first_child_idx is not None:
            assert first_child_idx == tool_call_idx + 1, (
                "Child events should appear immediately after tool_call"
            )


# =============================================================================
# Tests for Delegation Timeline Bug Fixes (Plan 45)
# =============================================================================


class TestDelegationTimelineBugFixes:
    """Tests for delegation timeline fixes from Plan 45."""

    @pytest.fixture
    def delegation_db(self, db: AnalyticsDB) -> AnalyticsDB:
        """Setup realistic delegation test data matching actual test session."""
        conn = db.connect()
        now = datetime.now()

        # Parent session (build agent)
        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "ses_parent_fix",
                "proj_001",
                "/projects/test",
                "Parent Session with Delegation",
                now - timedelta(hours=2),
                now,
            ],
        )

        # Child session (librarian agent)
        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "ses_child_fix",
                "proj_001",
                "/projects/test",
                "Librarian Child Session",
                now - timedelta(hours=1, minutes=45),
                now - timedelta(hours=1, minutes=30),
            ],
        )

        # Parent messages
        # Exchange 1 - User message
        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_parent_user_1",
                "ses_parent_fix",
                "user",
                None,
                now - timedelta(hours=2),
            ],
        )

        # Exchange 1 - Assistant message with delegation
        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_parent_asst_1",
                "ses_parent_fix",
                "assistant",
                "build",
                now - timedelta(hours=1, minutes=50),
            ],
        )

        # Exchange 3 - Assistant continuation message (same user_msg_id)
        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_parent_asst_2",
                "ses_parent_fix",
                "assistant",
                "build",
                now - timedelta(hours=1, minutes=25),
            ],
        )

        # Child messages
        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_child_user_1",
                "ses_child_fix",
                "user",
                None,
                now - timedelta(hours=1, minutes=45),
            ],
        )

        conn.execute(
            """INSERT INTO messages 
               (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_child_asst_1",
                "ses_child_fix",
                "assistant",
                "librarian",
                now - timedelta(hours=1, minutes=35),
            ],
        )

        # Parent exchanges
        # Exchange 1 - Initial delegation
        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_parent_1",
                "ses_parent_fix",
                1,
                "msg_parent_user_1",
                "msg_parent_asst_1",
                "Find OpenCode changelogs",
                "Je vais appeler l'agent librarian...",
                now - timedelta(hours=2),
                now - timedelta(hours=1, minutes=50),
                600000,
                500,
                200,
                50,
                0.01,
                1,
                1,
                "build",
                "claude-3",
            ],
        )

        # Exchange 2 - Continuation with delegation_result (becomes Exchange 3 after offset)
        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_parent_2",
                "ses_parent_fix",
                2,
                "msg_parent_user_1",  # Same user_msg_id triggers continuation
                "msg_parent_asst_2",
                "Find OpenCode changelogs",
                "Parfait! L'agent librarian a trouvé...",
                now - timedelta(hours=1, minutes=30),
                now - timedelta(hours=1, minutes=25),
                300000,
                300,
                400,
                100,
                0.02,
                0,
                1,
                "build",
                "claude-3",
            ],
        )

        # Child exchange
        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_child_1",
                "ses_child_fix",
                1,
                "msg_child_user_1",
                "msg_child_asst_1",
                "Search for OpenCode changelogs",
                "J'ai trouvé les changelogs...",
                now - timedelta(hours=1, minutes=45),
                now - timedelta(hours=1, minutes=35),
                600000,
                400,
                500,
                80,
                0.015,
                3,
                2,
                "librarian",
                "claude-3",
            ],
        )

        # Parent exchange traces - Exchange 1
        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_parent_1_reason",
                "ses_parent_fix",
                "exc_parent_1",
                "reasoning",
                1,
                '{"text": "L\'utilisateur demande...", "has_signature": false}',
                now - timedelta(hours=1, minutes=58),
                30000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_parent_1_tool",
                "ses_parent_fix",
                "exc_parent_1",
                "tool_call",
                2,
                '{"tool_name": "mcp_task", "status": "completed", '
                '"arguments": {"subagent_type": "librarian", "description": "Search changelogs"}, '
                '"result_summary": "Found 3 changelog entries", '
                '"child_session_id": "ses_child_fix"}',
                now - timedelta(hours=1, minutes=52),
                120000,
                0,
                0,
            ],
        )

        # Parent exchange traces - Exchange 2 (continuation, becomes Exchange 3)
        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_parent_2_reason",
                "ses_parent_fix",
                "exc_parent_2",
                "reasoning",
                1,
                '{"text": "L\'agent librarian a terminé...", "has_signature": false}',
                now - timedelta(hours=1, minutes=28),
                20000,
                0,
                0,
            ],
        )

        # Child exchange traces
        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_child_1_reason",
                "ses_child_fix",
                "exc_child_1",
                "reasoning",
                1,
                '{"text": "Je vais chercher les changelogs...", "has_signature": false}',
                now - timedelta(hours=1, minutes=44),
                15000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_child_1_tool1",
                "ses_child_fix",
                "exc_child_1",
                "tool_call",
                2,
                '{"tool_name": "bash", "status": "completed", '
                '"arguments": {"command": "gh api repos/sst/opencode/releases"}}',
                now - timedelta(hours=1, minutes=42),
                5000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_child_1_tool2",
                "ses_child_fix",
                "exc_child_1",
                "tool_call",
                3,
                '{"tool_name": "read", "status": "completed", '
                '"arguments": {"filePath": "/tmp/changelog.md"}}',
                now - timedelta(hours=1, minutes=40),
                3000,
                0,
                0,
            ],
        )

        # Delegation record
        conn.execute(
            """INSERT INTO delegations 
               (id, session_id, parent_agent, child_agent, child_session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "del_fix_001",
                "ses_parent_fix",
                "build",
                "librarian",
                "ses_child_fix",
                now - timedelta(hours=1, minutes=52),
            ],
        )

        return db

    @pytest.fixture
    def delegation_service(self, delegation_db: AnalyticsDB) -> TracingDataService:
        """Create TracingDataService with delegation test data."""
        return TracingDataService(delegation_db)

    def test_exchange_1_user_prompt_content(
        self, delegation_service: TracingDataService
    ):
        """Exchange 1 user_prompt must have exact content and message_id."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        assert result["success"]
        timeline = result["data"]["timeline"]

        exchange_1_events = [e for e in timeline if e["exchange_number"] == 1]
        user_prompts = [e for e in exchange_1_events if e["type"] == "user_prompt"]
        assert len(user_prompts) == 1

        user_prompt = user_prompts[0]
        assert user_prompt["exchange_number"] == 1
        assert user_prompt["content"] == "Find OpenCode changelogs"
        assert user_prompt["message_id"] == "msg_parent_user_1"
        assert user_prompt["timestamp"] is not None

    def test_exchange_1_reasoning_content(self, delegation_service: TracingDataService):
        """Exchange 1 reasoning must have exact text and signature info."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_1_events = [e for e in timeline if e["exchange_number"] == 1]

        reasoning_events = [e for e in exchange_1_events if e["type"] == "reasoning"]
        assert len(reasoning_events) == 1

        reasoning = reasoning_events[0]
        assert len(reasoning["entries"]) == 1
        assert reasoning["entries"][0]["text"] == "L'utilisateur demande..."
        assert reasoning["entries"][0]["has_signature"] is False
        assert reasoning["entries"][0]["signature"] is None

    def test_exchange_1_tool_call_delegation_details(
        self, delegation_service: TracingDataService
    ):
        """Exchange 1 tool_call must have exact delegation arguments and child_session_id."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_1_events = [e for e in timeline if e["exchange_number"] == 1]

        tool_calls = [e for e in exchange_1_events if e["type"] == "tool_call"]
        assert len(tool_calls) == 1

        tool_call = tool_calls[0]
        assert tool_call["tool_name"] == "mcp_task"
        assert tool_call["status"] == "completed"
        assert tool_call["child_session_id"] == "ses_child_fix"
        assert tool_call["result_summary"] == "Found 3 changelog entries"
        assert tool_call["duration_ms"] == 120000

        assert tool_call["arguments"]["subagent_type"] == "librarian"
        assert tool_call["arguments"]["description"] == "Search changelogs"

    def test_exchange_1_assistant_response_content(
        self, delegation_service: TracingDataService
    ):
        """Exchange 1 assistant_response must have exact content."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_1_events = [e for e in timeline if e["exchange_number"] == 1]

        responses = [e for e in exchange_1_events if e["type"] == "assistant_response"]
        assert len(responses) == 1

        response = responses[0]
        assert response["content"] == "Je vais appeler l'agent librarian..."
        assert response["tokens_out"] == 200

    def test_exchange_2_child_events_structure(
        self, delegation_service: TracingDataService
    ):
        """Exchange 2 must contain exactly the child session events with correct content."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_2_events = [e for e in timeline if e["exchange_number"] == 2]

        assert len(exchange_2_events) == 5

        for evt in exchange_2_events:
            assert evt["from_child_session"] == "ses_child_fix"
            assert evt["original_exchange_number"] == 1

        event_types = [e["type"] for e in exchange_2_events]
        assert event_types == [
            "user_prompt",
            "reasoning",
            "tool_call",
            "tool_call",
            "assistant_response",
        ]

    def test_exchange_2_child_user_prompt_content(
        self, delegation_service: TracingDataService
    ):
        """Exchange 2 child user_prompt must have exact content."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_2_events = [e for e in timeline if e["exchange_number"] == 2]

        user_prompt = exchange_2_events[0]
        assert user_prompt["type"] == "user_prompt"
        assert user_prompt["content"] == "Search for OpenCode changelogs"
        assert user_prompt["message_id"] == "msg_child_user_1"

    def test_exchange_2_child_reasoning_content(
        self, delegation_service: TracingDataService
    ):
        """Exchange 2 child reasoning must have exact text."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_2_events = [e for e in timeline if e["exchange_number"] == 2]

        reasoning = exchange_2_events[1]
        assert reasoning["type"] == "reasoning"
        assert reasoning["entries"][0]["text"] == "Je vais chercher les changelogs..."
        assert reasoning["entries"][0]["has_signature"] is False

    def test_exchange_2_child_tool_calls_content(
        self, delegation_service: TracingDataService
    ):
        """Exchange 2 child tool_calls must have exact tool names and arguments."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_2_events = [e for e in timeline if e["exchange_number"] == 2]

        bash_tool = exchange_2_events[2]
        assert bash_tool["type"] == "tool_call"
        assert bash_tool["tool_name"] == "bash"
        assert bash_tool["status"] == "completed"
        assert bash_tool["arguments"]["command"] == "gh api repos/sst/opencode/releases"
        assert bash_tool["duration_ms"] == 5000

        read_tool = exchange_2_events[3]
        assert read_tool["type"] == "tool_call"
        assert read_tool["tool_name"] == "read"
        assert read_tool["status"] == "completed"
        assert read_tool["arguments"]["filePath"] == "/tmp/changelog.md"
        assert read_tool["duration_ms"] == 3000

    def test_exchange_2_child_assistant_response_content(
        self, delegation_service: TracingDataService
    ):
        """Exchange 2 child assistant_response must have exact content."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_2_events = [e for e in timeline if e["exchange_number"] == 2]

        response = exchange_2_events[4]
        assert response["type"] == "assistant_response"
        assert response["content"] == "J'ai trouvé les changelogs..."
        assert response["tokens_out"] == 500

    def test_exchange_3_delegation_result_content(
        self, delegation_service: TracingDataService
    ):
        """Exchange 3 delegation_result must have exact content from result_summary."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_3_events = [e for e in timeline if e["exchange_number"] == 3]

        delegation_result = exchange_3_events[0]
        assert delegation_result["type"] == "delegation_result"
        assert delegation_result["content"] == "Found 3 changelog entries"
        assert delegation_result["message_id"] == "msg_parent_user_1"

    def test_exchange_3_reasoning_content(self, delegation_service: TracingDataService):
        """Exchange 3 reasoning must have exact continuation text."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_3_events = [e for e in timeline if e["exchange_number"] == 3]

        reasoning = exchange_3_events[1]
        assert reasoning["type"] == "reasoning"
        assert reasoning["entries"][0]["text"] == "L'agent librarian a terminé..."
        assert reasoning["entries"][0]["has_signature"] is False

    def test_exchange_3_assistant_response_content(
        self, delegation_service: TracingDataService
    ):
        """Exchange 3 assistant_response must have exact final content."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_3_events = [e for e in timeline if e["exchange_number"] == 3]

        response = exchange_3_events[2]
        assert response["type"] == "assistant_response"
        assert response["content"] == "Parfait! L'agent librarian a trouvé..."
        assert response["tokens_out"] == 400

    def test_exchange_3_event_order_is_delegation_result_then_reasoning_then_response(
        self, delegation_service: TracingDataService
    ):
        """Exchange 3 must have events in exact order: delegation_result, reasoning, assistant_response."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_3_events = [e for e in timeline if e["exchange_number"] == 3]

        assert len(exchange_3_events) == 3

        assert exchange_3_events[0]["type"] == "delegation_result"
        assert exchange_3_events[1]["type"] == "reasoning"
        assert exchange_3_events[2]["type"] == "assistant_response"

    def test_result_summary_is_plain_string_not_json_encoded(
        self, delegation_service: TracingDataService
    ):
        """result_summary must be plain string without JSON encoding artifacts."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=False
        )

        timeline = result["data"]["timeline"]
        tool_calls = [e for e in timeline if e["type"] == "tool_call"]
        delegation_tool = [t for t in tool_calls if t.get("child_session_id")][0]

        result_summary = delegation_tool["result_summary"]

        assert result_summary == "Found 3 changelog entries"
        assert not result_summary.startswith('"')
        assert not result_summary.startswith("'")
        assert not result_summary.endswith('"')
        assert "\\" not in result_summary

    def test_delegation_result_content_is_plain_string_not_json_encoded(
        self, delegation_service: TracingDataService
    ):
        """delegation_result content must be plain string without JSON encoding."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        delegation_results = [e for e in timeline if e["type"] == "delegation_result"]

        assert len(delegation_results) == 1
        content = delegation_results[0]["content"]

        assert content == "Found 3 changelog entries"
        assert not content.startswith('"')
        assert not content.startswith("'")
        assert "\\" not in content

    def test_timeline_has_exactly_three_exchanges(
        self, delegation_service: TracingDataService
    ):
        """Timeline must have exactly exchanges 1, 2, 3."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        exchange_numbers = sorted(set(e["exchange_number"] for e in timeline))

        assert exchange_numbers == [1, 2, 3]

    def test_timeline_total_event_count(self, delegation_service: TracingDataService):
        """Timeline must have exactly 12 events total."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        assert len(timeline) == 12

        exchange_1_count = len([e for e in timeline if e["exchange_number"] == 1])
        exchange_2_count = len([e for e in timeline if e["exchange_number"] == 2])
        exchange_3_count = len([e for e in timeline if e["exchange_number"] == 3])

        assert exchange_1_count == 4
        assert exchange_2_count == 5
        assert exchange_3_count == 3

    def test_child_events_not_present_when_include_children_false(
        self, delegation_service: TracingDataService
    ):
        """When include_children=False, no child events should appear."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=False
        )

        timeline = result["data"]["timeline"]
        child_events = [e for e in timeline if e.get("from_child_session")]

        assert len(child_events) == 0

        exchange_numbers = sorted(set(e["exchange_number"] for e in timeline))
        assert exchange_numbers == [1, 2]

    def test_timestamps_are_chronologically_ordered_within_exchange(
        self, delegation_service: TracingDataService
    ):
        """Events within each exchange must have timestamps in chronological order."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]

        for exchange_num in [1, 2, 3]:
            exchange_events = [
                e for e in timeline if e["exchange_number"] == exchange_num
            ]
            timestamps = [e["timestamp"] for e in exchange_events if e.get("timestamp")]

            for i in range(len(timestamps) - 1):
                assert timestamps[i] <= timestamps[i + 1], (
                    f"Exchange {exchange_num}: timestamps not chronological "
                    f"at position {i}: {timestamps[i]} > {timestamps[i + 1]}"
                )

    def test_delegation_result_from_db_with_include_children_false(
        self, delegation_service: TracingDataService
    ):
        """When include_children=False, delegation_result from DB should appear."""
        result = delegation_service.get_session_timeline_full(
            "ses_parent_fix", include_children=False
        )

        timeline = result["data"]["timeline"]
        delegation_results = [e for e in timeline if e["type"] == "delegation_result"]

        assert len(delegation_results) == 1
        assert delegation_results[0]["exchange_number"] == 2
        assert delegation_results[0]["content"] == "Found 3 changelog entries"


# =============================================================================
# Tests for Delegation Without Continuation (Edge Case)
# =============================================================================


class TestDelegationWithoutContinuation:
    """Tests for delegation where parent has no subsequent exchange."""

    @pytest.fixture
    def single_exchange_db(self, db: AnalyticsDB) -> AnalyticsDB:
        """Setup delegation where parent has only ONE exchange (no continuation)."""
        conn = db.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "ses_single_parent",
                "proj_001",
                "/projects/test",
                "Single Exchange Parent",
                now - timedelta(hours=1),
                now,
            ],
        )

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "ses_single_child",
                "proj_001",
                "/projects/test",
                "Child Session",
                now - timedelta(minutes=50),
                now - timedelta(minutes=40),
            ],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_single_user",
                "ses_single_parent",
                "user",
                None,
                now - timedelta(hours=1),
            ],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_single_asst",
                "ses_single_parent",
                "assistant",
                "build",
                now - timedelta(minutes=55),
            ],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_child_user",
                "ses_single_child",
                "user",
                None,
                now - timedelta(minutes=50),
            ],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_child_asst",
                "ses_single_child",
                "assistant",
                "librarian",
                now - timedelta(minutes=45),
            ],
        )

        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_single_1",
                "ses_single_parent",
                1,
                "msg_single_user",
                "msg_single_asst",
                "Do something with delegation",
                "I delegated to librarian.",
                now - timedelta(hours=1),
                now - timedelta(minutes=55),
                300000,
                100,
                200,
                50,
                0.01,
                1,
                1,
                "build",
                "claude-3",
            ],
        )

        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_child_1",
                "ses_single_child",
                1,
                "msg_child_user",
                "msg_child_asst",
                "Search for data",
                "Found the data.",
                now - timedelta(minutes=50),
                now - timedelta(minutes=45),
                300000,
                80,
                150,
                30,
                0.008,
                1,
                1,
                "librarian",
                "claude-3",
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_single_tool",
                "ses_single_parent",
                "exc_single_1",
                "tool_call",
                1,
                '{"tool_name": "mcp_task", "status": "completed", '
                '"arguments": {"subagent_type": "librarian"}, '
                '"result_summary": "Task completed successfully", '
                '"child_session_id": "ses_single_child"}',
                now - timedelta(minutes=55),
                60000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_child_tool",
                "ses_single_child",
                "exc_child_1",
                "tool_call",
                1,
                '{"tool_name": "bash", "status": "completed", '
                '"arguments": {"command": "ls"}}',
                now - timedelta(minutes=48),
                5000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO delegations 
               (id, session_id, parent_agent, child_agent, child_session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "del_single_001",
                "ses_single_parent",
                "build",
                "librarian",
                "ses_single_child",
                now - timedelta(minutes=55),
            ],
        )

        return db

    @pytest.fixture
    def single_exchange_service(
        self, single_exchange_db: AnalyticsDB
    ) -> TracingDataService:
        return TracingDataService(single_exchange_db)

    def test_delegation_without_continuation_has_no_delegation_result_event(
        self, single_exchange_service: TracingDataService
    ):
        """When there's no continuation exchange, delegation_result doesn't appear via is_continuation."""
        result = single_exchange_service.get_session_timeline_full(
            "ses_single_parent", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        delegation_results = [e for e in timeline if e["type"] == "delegation_result"]

        assert len(delegation_results) == 0

    def test_delegation_without_continuation_still_inlines_child(
        self, single_exchange_service: TracingDataService
    ):
        """Child session events should still be inlined even without continuation."""
        result = single_exchange_service.get_session_timeline_full(
            "ses_single_parent", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        child_events = [e for e in timeline if e.get("from_child_session")]

        assert len(child_events) > 0
        assert all(e["from_child_session"] == "ses_single_child" for e in child_events)

    def test_delegation_without_continuation_tool_call_has_result_summary(
        self, single_exchange_service: TracingDataService
    ):
        """The tool_call event should still have result_summary even without delegation_result event."""
        result = single_exchange_service.get_session_timeline_full(
            "ses_single_parent", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        tool_calls = [
            e
            for e in timeline
            if e["type"] == "tool_call" and e.get("child_session_id")
        ]

        assert len(tool_calls) == 1
        assert tool_calls[0]["result_summary"] == "Task completed successfully"


class TestDelegationResultAfterChildSession:
    """Tests for delegation_result appearing AFTER child session when include_children=True.

    This tests the fix for the bug where delegation_result appeared BEFORE child events
    because delegation_result DB event had lower event_order than tool_call.
    """

    @pytest.fixture
    def db_with_delegation_result_event(self, db: AnalyticsDB) -> AnalyticsDB:
        """Setup with explicit delegation_result event in exchange_traces."""
        conn = db.connect()
        now = datetime.now()

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "ses_dr_parent",
                "proj_001",
                "/projects/test",
                "Parent with DR event",
                now - timedelta(hours=1),
                now,
            ],
        )

        conn.execute(
            """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "ses_dr_child",
                "proj_001",
                "/projects/test",
                "Child Session",
                now - timedelta(minutes=50),
                now - timedelta(minutes=40),
            ],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ["msg_dr_user", "ses_dr_parent", "user", None, now - timedelta(hours=1)],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_dr_asst",
                "ses_dr_parent",
                "assistant",
                "build",
                now - timedelta(minutes=55),
            ],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_dr_child_user",
                "ses_dr_child",
                "user",
                None,
                now - timedelta(minutes=50),
            ],
        )

        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                "msg_dr_child_asst",
                "ses_dr_child",
                "assistant",
                "librarian",
                now - timedelta(minutes=45),
            ],
        )

        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_dr_1",
                "ses_dr_parent",
                1,
                "msg_dr_user",
                "msg_dr_asst",
                "Delegate to librarian",
                "Delegated successfully.",
                now - timedelta(hours=1),
                now - timedelta(minutes=55),
                300000,
                100,
                200,
                50,
                0.01,
                1,
                0,
                "build",
                "claude-3",
            ],
        )

        conn.execute(
            """INSERT INTO exchanges 
               (id, session_id, exchange_number, user_message_id, assistant_message_id,
                prompt_input, prompt_output, started_at, ended_at, duration_ms,
                tokens_in, tokens_out, tokens_reasoning, cost,
                tool_count, reasoning_count, agent, model_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "exc_dr_child_1",
                "ses_dr_child",
                1,
                "msg_dr_child_user",
                "msg_dr_child_asst",
                "Search for data",
                "Found the data.",
                now - timedelta(minutes=50),
                now - timedelta(minutes=45),
                300000,
                80,
                150,
                30,
                0.008,
                1,
                0,
                "librarian",
                "claude-3",
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_dr_tool",
                "ses_dr_parent",
                "exc_dr_1",
                "tool_call",
                1,
                '{"tool_name": "mcp_task", "status": "completed", '
                '"arguments": {"subagent_type": "librarian"}, '
                '"result_summary": "Librarian found 5 results", '
                '"child_session_id": "ses_dr_child"}',
                now - timedelta(minutes=55),
                60000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_dr_result",
                "ses_dr_parent",
                "exc_dr_1",
                "delegation_result",
                2,
                '{"tool_name": "mcp_task", '
                '"result_summary": "Librarian found 5 results", '
                '"child_session_id": "ses_dr_child"}',
                now - timedelta(minutes=55),
                0,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_dr_child_prompt",
                "ses_dr_child",
                "exc_dr_child_1",
                "user_prompt",
                1,
                '{"content": "Search for data", "message_id": "msg_dr_child_user"}',
                now - timedelta(minutes=50),
                0,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO exchange_traces 
               (id, session_id, exchange_id, event_type, event_order, event_data,
                timestamp, duration_ms, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "evt_dr_child_tool",
                "ses_dr_child",
                "exc_dr_child_1",
                "tool_call",
                2,
                '{"tool_name": "grep", "status": "completed", '
                '"arguments": {"pattern": "test"}}',
                now - timedelta(minutes=48),
                5000,
                0,
                0,
            ],
        )

        conn.execute(
            """INSERT INTO delegations 
               (id, session_id, parent_agent, child_agent, child_session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                "del_dr_001",
                "ses_dr_parent",
                "build",
                "librarian",
                "ses_dr_child",
                now - timedelta(minutes=50),
            ],
        )

        return db

    @pytest.fixture
    def dr_service(
        self, db_with_delegation_result_event: AnalyticsDB
    ) -> TracingDataService:
        return TracingDataService(db_with_delegation_result_event)

    def test_timeline_exact_event_order(self, dr_service: TracingDataService):
        """Timeline must have events in exact order: parent events, child events, delegation_result, parent response."""
        result = dr_service.get_session_timeline_full(
            "ses_dr_parent", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        event_sequence = [(e["type"], e.get("from_child_session")) for e in timeline]

        assert event_sequence[0] == ("user_prompt", None), "First: parent user_prompt"
        assert event_sequence[1] == ("tool_call", None), (
            "Second: parent tool_call (delegation)"
        )
        assert event_sequence[2] == ("user_prompt", "ses_dr_child"), (
            "Third: child user_prompt"
        )
        assert event_sequence[3] == ("tool_call", "ses_dr_child"), (
            "Fourth: child tool_call"
        )
        assert event_sequence[4] == ("assistant_response", "ses_dr_child"), (
            "Fifth: child assistant_response"
        )
        assert event_sequence[5] == ("delegation_result", None), (
            "Sixth: delegation_result AFTER all child events"
        )
        assert event_sequence[6] == ("assistant_response", None), (
            "Seventh: parent assistant_response"
        )

    def test_delegation_result_position_by_index(self, dr_service: TracingDataService):
        """delegation_result index must be greater than all child event indices."""
        result = dr_service.get_session_timeline_full(
            "ses_dr_parent", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]

        parent_tool_call_idx = next(
            i
            for i, e in enumerate(timeline)
            if e["type"] == "tool_call" and not e.get("from_child_session")
        )
        child_indices = [
            i for i, e in enumerate(timeline) if e.get("from_child_session")
        ]
        dr_idx = next(
            i for i, e in enumerate(timeline) if e["type"] == "delegation_result"
        )

        assert len(child_indices) == 3, (
            "3 child events: user_prompt, tool_call, assistant_response"
        )
        assert dr_idx == parent_tool_call_idx + 4, (
            "delegation_result at position tool_call + 4"
        )
        assert dr_idx > max(child_indices), "delegation_result after ALL child events"

    def test_delegation_result_has_correct_content(
        self, dr_service: TracingDataService
    ):
        """delegation_result should have correct content from DB event."""
        result = dr_service.get_session_timeline_full(
            "ses_dr_parent", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        delegation_results = [e for e in timeline if e["type"] == "delegation_result"]

        assert len(delegation_results) == 1
        dr = delegation_results[0]
        assert dr["content"] == "Librarian found 5 results"
        assert dr["result_summary"] == "Librarian found 5 results"
        assert dr["child_session_id"] == "ses_dr_child"

    def test_delegation_result_has_offset_exchange_number(
        self, dr_service: TracingDataService
    ):
        """delegation_result should have exchange_number offset after child session."""
        result = dr_service.get_session_timeline_full(
            "ses_dr_parent", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]

        tool_call = next(e for e in timeline if e["type"] == "tool_call")
        child_events = [e for e in timeline if e.get("from_child_session")]
        delegation_result = next(
            e for e in timeline if e["type"] == "delegation_result"
        )

        assert tool_call["exchange_number"] == 1
        assert all(e["exchange_number"] == 2 for e in child_events)
        assert delegation_result["exchange_number"] == 3

    def test_child_events_have_correct_metadata(self, dr_service: TracingDataService):
        """Child events must have from_child_session set to exact child session ID."""
        result = dr_service.get_session_timeline_full(
            "ses_dr_parent", include_children=True, depth=1
        )

        timeline = result["data"]["timeline"]
        child_events = [e for e in timeline if e.get("from_child_session")]

        assert len(child_events) == 3, (
            "3 child events: user_prompt, tool_call, assistant_response"
        )

        for child_evt in child_events:
            assert child_evt["from_child_session"] == "ses_dr_child"
            assert child_evt["exchange_number"] == 2
            assert child_evt["original_exchange_number"] == 1

        child_prompt = next(e for e in child_events if e["type"] == "user_prompt")
        assert child_prompt["content"] == "Search for data"

        child_tool = next(e for e in child_events if e["type"] == "tool_call")
        assert child_tool["tool_name"] == "grep"
        assert child_tool["status"] == "completed"

        child_response = next(
            e for e in child_events if e["type"] == "assistant_response"
        )
        assert child_response["content"] == "Found the data."
