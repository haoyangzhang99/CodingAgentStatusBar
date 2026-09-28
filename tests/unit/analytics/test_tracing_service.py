"""
Tests for TracingDataService.

Covers:
- get_session_summary()
- get_session_tokens()
- get_session_tools()
- get_session_files()
- get_session_timeline()
- get_session_agents()
- get_global_stats()
- get_comparison()
- update_session_stats()
- update_daily_stats()
- extract_tool_display_info()
"""

import json
from datetime import datetime

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.tracing import (
    TracingDataService,
    TracingConfig,
)
from opencode_status_bar.analytics.tracing.helpers import extract_tool_display_info


class TestExtractToolDisplayInfo:
    @pytest.mark.parametrize(
        "tool,args,expected",
        [
            (None, None, ""),
            ("bash", None, ""),
            ("read", "not-json", ""),
            ("read", json.dumps({}), ""),
        ],
        ids=["none_tool", "none_args", "invalid_json", "empty_path"],
    )
    def test_edge_cases(self, tool, args, expected):
        assert extract_tool_display_info(tool, args) == expected

    @pytest.mark.parametrize(
        "tool,file_path,expected",
        [
            ("read", "/path/to/file.py", "file.py"),
            ("write", "/deep/nested/output.txt", "output.txt"),
            ("edit", "/src/main.rs", "main.rs"),
        ],
        ids=["read", "write", "edit"],
    )
    def test_file_tools_extract_basename(self, tool, file_path, expected):
        args = json.dumps({"filePath": file_path})
        assert extract_tool_display_info(tool, args) == expected

    @pytest.mark.parametrize(
        "args_dict,expected",
        [
            ({"pattern": "**/*.py"}, "**/*.py"),
            ({"path": "/src/components"}, "/src/components"),
            ({"pattern": "a" * 50}, "a" * 40),
        ],
        ids=["pattern", "path_fallback", "truncate_long"],
    )
    def test_glob_tool(self, args_dict, expected):
        args = json.dumps(args_dict)
        assert extract_tool_display_info("glob", args) == expected

    @pytest.mark.parametrize(
        "command,expected_suffix",
        [
            ("git status", "git status"),
            ("line1\nline2", "line1..."),
        ],
        ids=["simple", "multiline"],
    )
    def test_bash_tool(self, command, expected_suffix):
        args = json.dumps({"command": command})
        result = extract_tool_display_info("bash", args)
        assert result == expected_suffix

    def test_bash_truncates_long_command(self):
        args = json.dumps({"command": "echo " + "x" * 100})
        result = extract_tool_display_info("bash", args)
        assert len(result) <= 63 and result.endswith("...")

    @pytest.mark.parametrize(
        "pattern,expected",
        [
            ("def main", "/def main/"),
            ("x" * 50, "/" + "x" * 39),
        ],
        ids=["simple", "truncate"],
    )
    def test_grep_tool(self, pattern, expected):
        args = json.dumps({"pattern": pattern})
        result = extract_tool_display_info("grep", args)
        assert result == expected
        assert len(result) <= 40

    @pytest.mark.parametrize(
        "tool,url,expected",
        [
            ("webfetch", "https://docs.python.org/3/lib", "docs.python.org"),
            ("web_fetch", "https://example.com/page", "example.com"),
            ("webfetch", "invalid-url", ""),
        ],
        ids=["webfetch", "web_fetch", "invalid_url_returns_empty"],
    )
    def test_webfetch_tools(self, tool, url, expected):
        args = json.dumps({"url": url})
        assert extract_tool_display_info(tool, args) == expected

    @pytest.mark.parametrize(
        "tool,args_dict,expected",
        [
            ("context7_query-docs", {"libraryId": "react/hooks"}, "react/hooks"),
            ("task", {"subagent_type": "oracle"}, "oracle"),
            ("task", {"description": "Analyze code"}, "Analyze code"),
            (
                "task",
                {"subagent_type": "librarian", "description": "Find docs"},
                "librarian: Find docs",
            ),
            ("unknown_tool", {"someKey": "someValue"}, "someValue"),
        ],
        ids=[
            "context7",
            "task_subagent_only",
            "task_description_only",
            "task_combined",
            "generic_fallback",
        ],
    )
    def test_other_tools(self, tool, args_dict, expected):
        args = json.dumps(args_dict)
        assert extract_tool_display_info(tool, args) == expected


# =============================================================================
# Fixtures (db, service are provided by conftest.py)
# =============================================================================


# Alias for compatibility - uses tracing_service from conftest
@pytest.fixture
def service(tracing_service: TracingDataService) -> TracingDataService:
    """Alias for tracing_service from conftest."""
    return tracing_service


@pytest.fixture
def populated_db(temp_db: AnalyticsDB) -> AnalyticsDB:
    """Populate database with test data."""
    conn = temp_db.connect()

    # Insert test session
    conn.execute(
        """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "ses_001",
            "proj_001",
            "/projects/test",
            "Test Session",
            datetime(2026, 1, 1, 10, 0, 0),
            datetime(2026, 1, 1, 10, 30, 0),
        ],
    )

    # Insert test messages
    messages = [
        (
            "msg_001",
            "ses_001",
            None,
            "user",
            "user",
            "claude-3",
            "anthropic",
            100,
            50,
            0,
            20,
            0,
            datetime(2026, 1, 1, 10, 0, 0),
            datetime(2026, 1, 1, 10, 0, 5),
        ),
        (
            "msg_002",
            "ses_001",
            "msg_001",
            "assistant",
            "executor",
            "claude-3",
            "anthropic",
            200,
            150,
            10,
            50,
            30,
            datetime(2026, 1, 1, 10, 0, 5),
            datetime(2026, 1, 1, 10, 5, 0),
        ),
        (
            "msg_003",
            "ses_001",
            "msg_002",
            "user",
            "user",
            "claude-3",
            "anthropic",
            80,
            40,
            0,
            10,
            0,
            datetime(2026, 1, 1, 10, 5, 0),
            datetime(2026, 1, 1, 10, 5, 5),
        ),
    ]

    for msg in messages:
        conn.execute(
            """INSERT INTO messages 
               (id, session_id, parent_id, role, agent, model_id, provider_id,
                tokens_input, tokens_output, tokens_reasoning,
                tokens_cache_read, tokens_cache_write, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            list(msg),
        )

    # Insert test parts (tool calls)
    parts = [
        (
            "prt_001",
            "msg_002",
            "tool",
            "read",
            "completed",
            datetime(2026, 1, 1, 10, 1, 0),
            "ses_001",
            None,
            datetime(2026, 1, 1, 10, 1, 2),
            2000,
        ),
        (
            "prt_002",
            "msg_002",
            "tool",
            "write",
            "completed",
            datetime(2026, 1, 1, 10, 2, 0),
            "ses_001",
            None,
            datetime(2026, 1, 1, 10, 2, 5),
            5000,
        ),
        (
            "prt_003",
            "msg_002",
            "tool",
            "bash",
            "error",
            datetime(2026, 1, 1, 10, 3, 0),
            "ses_001",
            None,
            datetime(2026, 1, 1, 10, 3, 1),
            1000,
        ),
    ]

    for prt in parts:
        conn.execute(
            """INSERT INTO parts 
               (id, message_id, part_type, tool_name, tool_status, created_at,
                session_id, call_id, ended_at, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            list(prt),
        )

    # Insert test traces
    conn.execute(
        """INSERT INTO agent_traces 
           (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
            prompt_input, prompt_output, started_at, ended_at, duration_ms,
            tokens_in, tokens_out, status, tools_used, child_session_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "trace_001",
            "ses_001",
            None,
            "user",
            "executor",
            "Implement feature X",
            "Feature implemented",
            datetime(2026, 1, 1, 10, 0, 0),
            datetime(2026, 1, 1, 10, 30, 0),
            1800000,
            500,
            300,
            "completed",
            ["read", "write", "bash"],
            None,
        ],
    )

    # Insert test file operations
    file_ops = [
        (
            "fop_001",
            "ses_001",
            None,
            "read",
            "/projects/test/src/app.py",
            datetime(2026, 1, 1, 10, 1, 0),
            "normal",
            None,
        ),
        (
            "fop_002",
            "ses_001",
            None,
            "write",
            "/projects/test/src/output.py",
            datetime(2026, 1, 1, 10, 2, 0),
            "normal",
            None,
        ),
    ]
    for fop in file_ops:
        conn.execute(
            """INSERT INTO file_operations
               (id, session_id, trace_id, operation, file_path, timestamp, risk_level, risk_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            list(fop),
        )

    return temp_db


# =============================================================================
# Test get_session_summary
# =============================================================================


class TestGetSessionSummary:
    """Tests for get_session_summary method."""

    def test_returns_empty_for_nonexistent_session(self, service: TracingDataService):
        """Should return empty response for non-existent session."""
        result = service.get_session_summary("nonexistent")

        assert result["meta"]["error"] == "Session not found"
        assert result["summary"] == {}

    def test_returns_complete_summary(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should return complete session summary with all KPIs."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_summary("ses_001")

        # Check meta
        assert result["meta"]["session_id"] == "ses_001"
        assert result["meta"]["title"] == "Test Session"
        assert "generated_at" in result["meta"]

        # Check summary
        summary = result["summary"]
        assert summary["total_tokens"] > 0
        assert summary["total_tool_calls"] == 3
        assert summary["unique_agents"] > 0
        assert "estimated_cost_usd" in summary
        assert "duration_ms" in summary

        # Check details sections exist
        assert "tokens" in result["details"]
        assert "tools" in result["details"]
        assert "files" in result["details"]
        assert "agents" in result["details"]

        # Check charts sections exist
        assert "tokens_by_type" in result["charts"]
        assert "tools_by_name" in result["charts"]

    def test_calculates_token_metrics(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should correctly calculate token metrics."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_summary("ses_001")

        tokens = result["details"]["tokens"]
        # 100 + 200 + 80 = 380 input
        assert tokens["input"] == 380
        # 50 + 150 + 40 = 240 output
        assert tokens["output"] == 240
        # 20 + 50 + 10 = 80 cache_read
        assert tokens["cache_read"] == 80
        # Total = input + output = 620
        assert tokens["total"] == 620

    def test_calculates_tool_metrics(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should correctly calculate tool metrics."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_summary("ses_001")

        tools = result["details"]["tools"]
        assert tools["total_calls"] == 3
        assert tools["unique_tools"] == 3
        assert tools["success_count"] == 2
        assert tools["error_count"] == 1
        # 2/3 success rate
        assert tools["success_rate"] == pytest.approx(66.7, abs=0.1)


# =============================================================================
# Test get_session_tokens
# =============================================================================


class TestGetSessionTokens:
    """Tests for get_session_tokens method."""

    def test_returns_token_details(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should return detailed token breakdown."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_tokens("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert result["summary"]["total"] == 620
        assert result["summary"]["input"] == 380
        assert result["summary"]["output"] == 240
        assert "cache_hit_ratio" in result["summary"]


# =============================================================================
# Test get_session_tools
# =============================================================================


class TestGetSessionTools:
    """Tests for get_session_tools method."""

    def test_returns_tool_details(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should return detailed tool breakdown."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_tools("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert result["summary"]["total_calls"] == 3
        assert result["summary"]["unique_tools"] == 3
        assert "success_rate" in result["summary"]
        assert "avg_duration_ms" in result["summary"]


# =============================================================================
# Test get_session_files
# =============================================================================


class TestGetSessionFiles:
    def test_returns_file_details(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        service = TracingDataService(db=populated_db)
        result = service.get_session_files("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert result["summary"]["total_reads"] == 1
        assert result["summary"]["total_writes"] == 1

    def test_fallback_extracts_from_parts_when_file_operations_empty(
        self, temp_db: AnalyticsDB
    ):
        conn = temp_db.connect()

        conn.execute(
            """INSERT INTO sessions (id, title, created_at)
               VALUES ('ses_fallback', 'Fallback Test', '2026-01-01 10:00:00')"""
        )
        conn.execute(
            """INSERT INTO messages (id, session_id, role, created_at)
               VALUES ('msg_fb', 'ses_fallback', 'assistant', '2026-01-01 10:00:00')"""
        )

        parts_data = [
            ("prt_fb_read", "read", json.dumps({"filePath": "/src/app.py"})),
            ("prt_fb_write", "write", json.dumps({"filePath": "/out/result.txt"})),
            ("prt_fb_edit", "edit", json.dumps({"filePath": "/src/utils.py"})),
        ]
        for part_id, tool, args in parts_data:
            conn.execute(
                """INSERT INTO parts (id, session_id, message_id, part_type, tool_name, 
                   tool_status, arguments, created_at)
                   VALUES (?, 'ses_fallback', 'msg_fb', 'tool', ?, 'completed', ?, 
                   '2026-01-01 10:01:00')""",
                [part_id, tool, args],
            )

        service = TracingDataService(db=temp_db)
        result = service.get_session_files("ses_fallback")

        assert result["summary"]["total_reads"] == 1
        assert result["summary"]["total_writes"] == 1
        assert result["summary"]["total_edits"] == 1
        assert result["details"]["unique_files"] == 3
        assert "/src/app.py" in result["details"]["files_list"]["read"]
        assert "/out/result.txt" in result["details"]["files_list"]["write"]
        assert "/src/utils.py" in result["details"]["files_list"]["edit"]


# =============================================================================
# Test get_session_timeline
# =============================================================================


class TestGetSessionTimeline:
    """Tests for get_session_timeline method."""

    def test_returns_chronological_events(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should return events sorted chronologically."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_timeline("ses_001")

        assert result
        for event in result:
            assert "type" in event
            assert "id" in event
            assert "timestamp" in event

    def test_returns_empty_for_nonexistent_session(self, service: TracingDataService):
        """Should return empty list for non-existent session."""
        result = service.get_session_timeline("nonexistent")
        assert result == []


# =============================================================================
# Test get_session_agents
# =============================================================================


class TestGetSessionAgents:
    """Tests for get_session_agents method."""

    def test_returns_agent_list(self, temp_db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should return list of agents involved in session."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_agents("ses_001")

        assert result
        for agent in result:
            assert "agent" in agent
            assert "message_count" in agent


# =============================================================================
# Test get_session_prompts
# =============================================================================


class TestGetSessionPrompts:
    """Tests for get_session_prompts method."""

    def test_returns_prompt_data(self, temp_db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should return user prompt and output."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_prompts("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert "prompt_input" in result
        assert "prompt_output" in result

    def test_returns_fallback_for_nonexistent_session(
        self, service: TracingDataService
    ):
        """Should return fallback messages for non-existent session."""
        result = service.get_session_prompts("nonexistent")

        assert result["meta"]["session_id"] == "nonexistent"
        # Returns fallback message instead of None for better UX
        assert isinstance(result["prompt_input"], str)
        assert result["prompt_input"]


# =============================================================================
# Test get_global_stats
# =============================================================================


class TestGetGlobalStats:
    """Tests for get_global_stats method."""

    def test_returns_global_statistics(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should return aggregated global statistics."""
        service = TracingDataService(db=populated_db)
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 2)

        result = service.get_global_stats(start, end)

        assert "meta" in result
        assert "summary" in result
        assert result["summary"]["total_sessions"] == 1
        assert result["summary"]["total_messages"] == 3
        assert result["summary"]["total_tokens"] > 0

    def test_uses_default_date_range(self, service: TracingDataService):
        """Should use last 30 days as default range."""
        result = service.get_global_stats()

        assert "period" in result["meta"]
        # Period should span 30 days
        period = result["meta"]["period"]
        assert period["start"]
        assert period["end"]

    def test_returns_agents_tools_skills_lists(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should return agents, tools, and skills lists with correct format."""
        # Add skill data - parts with tool_name='skill' and arguments JSON
        conn = populated_db.connect()
        conn.execute(
            """INSERT INTO parts 
               (id, message_id, part_type, tool_name, tool_status, created_at,
                session_id, call_id, ended_at, duration_ms, arguments)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt_skill_001",
                "msg_002",
                "tool",
                "skill",
                "completed",
                datetime(2026, 1, 1, 10, 4, 0),
                "ses_001",
                None,
                datetime(2026, 1, 1, 10, 4, 1),
                1000,
                '{"name": "functional-testing"}',
            ],
        )
        conn.execute(
            """INSERT INTO parts 
               (id, message_id, part_type, tool_name, tool_status, created_at,
                session_id, call_id, ended_at, duration_ms, arguments)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "prt_skill_002",
                "msg_002",
                "tool",
                "skill",
                "completed",
                datetime(2026, 1, 1, 10, 5, 0),
                "ses_001",
                None,
                datetime(2026, 1, 1, 10, 5, 1),
                1000,
                '{"name": "agentic-flow"}',
            ],
        )

        service = TracingDataService(db=populated_db)
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 2)

        result = service.get_global_stats(start, end)

        # Check agents list structure (from agent_traces)
        assert "agents" in result
        assert isinstance(result["agents"], list)
        if result["agents"]:
            agent = result["agents"][0]
            assert "agent" in agent  # Key is 'agent', not 'agent_name'
            assert "messages" in agent
            assert "tokens" in agent
            assert agent["agent"] == "executor"  # From populated_db agent_trace

        # Check tools list structure (from parts)
        assert "tools" in result
        assert isinstance(result["tools"], list)
        assert len(result["tools"]) >= 3  # read, write, bash, skill
        tool = result["tools"][0]
        assert "tool" in tool  # Key is 'tool', not 'tool_name'
        assert "invocations" in tool
        assert "failures" in tool
        assert "failure_rate" in tool  # New field

        # Check that bash has correct failure count (1 error in populated_db)
        bash_tool = next((t for t in result["tools"] if t["tool"] == "bash"), None)
        if bash_tool:
            assert bash_tool["failures"] == 1
            assert bash_tool["failure_rate"] == "100.0%"  # 1 failure out of 1

        # Check skills list structure (from parts where tool_name='skill')
        assert "skills" in result
        assert isinstance(result["skills"], list)
        assert len(result["skills"]) >= 2  # functional-testing, agentic-flow
        skill = result["skills"][0]
        assert "skill" in skill  # Key is 'skill', not 'skill_name'
        assert "load_count" in skill

        # Verify skill names are extracted from JSON arguments
        skill_names = [s["skill"] for s in result["skills"]]
        assert "functional-testing" in skill_names or "agentic-flow" in skill_names


# =============================================================================
# Test get_comparison
# =============================================================================


class TestGetComparison:
    """Tests for get_comparison method."""

    def test_compares_multiple_sessions(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should compare metrics across sessions."""
        service = TracingDataService(db=populated_db)

        # Add another session for comparison
        conn = populated_db.connect()
        conn.execute(
            """INSERT INTO sessions (id, title, created_at)
               VALUES (?, ?, ?)""",
            ["ses_002", "Another Session", datetime(2026, 1, 2, 10, 0, 0)],
        )

        result = service.get_comparison(["ses_001", "ses_002"])

        assert result["meta"]["sessions_compared"] == 2
        assert len(result["comparisons"]) == 2


# =============================================================================
# Test update_session_stats
# =============================================================================


class TestUpdateSessionStats:
    """Tests for update_session_stats method."""

    def test_updates_session_stats_table(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should update session_stats aggregation table."""
        service = TracingDataService(db=populated_db)
        service.update_session_stats("ses_001")

        conn = populated_db.connect()
        result = conn.execute(
            "SELECT total_messages, total_tokens_in FROM session_stats WHERE session_id = ?",
            ["ses_001"],
        ).fetchone()

        assert result[0] == 3  # 3 messages
        assert result[1] == 380  # total input tokens


# =============================================================================
# Test update_daily_stats
# =============================================================================


class TestUpdateDailyStats:
    """Tests for update_daily_stats method."""

    def test_updates_daily_stats_table(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should update daily_stats aggregation table."""
        service = TracingDataService(db=populated_db)
        test_date = datetime(2026, 1, 1)
        service.update_daily_stats(test_date)

        conn = populated_db.connect()
        result = conn.execute(
            "SELECT total_sessions FROM daily_stats WHERE date = ?",
            ["2026-01-01"],
        ).fetchone()

        assert result[0] >= 1


# =============================================================================
# Test TracingConfig
# =============================================================================


class TestTracingConfig:
    """Tests for TracingConfig dataclass."""

    def test_default_values(self):
        """Should have sensible default values."""
        config = TracingConfig()

        assert config.cost_per_1k_input == 0.003
        assert config.cost_per_1k_output == 0.015
        assert config.cost_per_1k_cache == 0.0003

    def test_custom_values(self):
        """Should accept custom pricing."""
        config = TracingConfig(
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
            cost_per_1k_cache=0.001,
        )

        assert config.cost_per_1k_input == 0.01
        assert config.cost_per_1k_output == 0.03
        assert config.cost_per_1k_cache == 0.001

    def test_service_uses_custom_config(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Service should use custom config for calculations."""
        custom_config = TracingConfig(
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.05,
        )
        service = TracingDataService(db=populated_db, config=custom_config)

        result = service.get_session_summary("ses_001")

        # Cost should be higher with custom pricing
        assert result["summary"]["estimated_cost_usd"] > 0


# =============================================================================
# Test Response Format
# =============================================================================


class TestPerformance:
    """Tests for performance requirements."""

    def test_get_session_summary_under_100ms(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """get_session_summary should complete in under 100ms."""
        import time

        service = TracingDataService(db=populated_db)

        # Warm up
        service.get_session_summary("ses_001")

        # Measure
        start = time.perf_counter()
        for _ in range(10):
            service.get_session_summary("ses_001")
        elapsed = (time.perf_counter() - start) * 1000 / 10  # Average ms

        assert elapsed < 100, (
            f"get_session_summary took {elapsed:.1f}ms (target: <100ms)"
        )

    def test_get_global_stats_under_100ms(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """get_global_stats should complete in under 100ms."""
        import time
        from datetime import datetime

        service = TracingDataService(db=populated_db)
        start_date = datetime(2026, 1, 1)
        end_date = datetime(2026, 1, 2)

        # Warm up
        service.get_global_stats(start_date, end_date)

        # Measure
        start = time.perf_counter()
        for _ in range(10):
            service.get_global_stats(start_date, end_date)
        elapsed = (time.perf_counter() - start) * 1000 / 10  # Average ms

        assert elapsed < 100, f"get_global_stats took {elapsed:.1f}ms (target: <100ms)"


class TestResponseFormat:
    """Tests for standardized response format."""

    def test_all_responses_have_meta(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """All responses should have meta section."""
        service = TracingDataService(db=populated_db)

        responses = [
            service.get_session_summary("ses_001"),
            service.get_session_tokens("ses_001"),
            service.get_session_tools("ses_001"),
            service.get_session_files("ses_001"),
            service.get_global_stats(),
        ]

        for response in responses:
            assert "meta" in response
            assert "generated_at" in response["meta"]

    def test_summary_and_details_structure(
        self, temp_db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Responses should have summary and details sections."""
        service = TracingDataService(db=populated_db)

        result = service.get_session_summary("ses_001")

        # Summary should have quick access metrics
        assert isinstance(result["summary"], dict)
        assert "duration_ms" in result["summary"]
        assert "total_tokens" in result["summary"]

        # Details should have full breakdown
        assert isinstance(result["details"], dict)
        assert "tokens" in result["details"]
        assert "tools" in result["details"]
