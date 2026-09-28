"""
Tests for opencode_monitor.core.monitor module.

Consolidated test suite covering:
- find_opencode_ports() - subprocess mocking for netstat
- get_tty_for_port() - subprocess mocking for lsof/ps
- extract_tools_from_messages() - message parsing
- count_todos() - todo counting logic
- fetch_instance() - async instance fetching
- fetch_all_instances() - async state building
"""

import pytest
import time
import json
from unittest.mock import patch, MagicMock, AsyncMock

from opencode_monitor.core.monitor import (
    find_opencode_ports,
    get_tty_for_port,
    extract_tools_from_messages,
    count_todos,
    fetch_instance,
    fetch_all_instances,
    AskUserResult,
    _find_latest_notify_ask_user,
    _has_activity_after_notify,
    check_pending_ask_user_from_disk,
)
from opencode_monitor.core.models import (
    Instance,
    Agent,
    SessionStatus,
    AgentTodos,
)


@pytest.fixture(autouse=True)
def no_live_bridge_snapshots():
    """Legacy port tests must not see the developer's real desktop bridge files."""
    with patch("opencode_monitor.core.monitor.fetcher.read_bridge_instances", return_value=[]):
        yield


# ===========================================================================
# Tests for find_opencode_ports()
# ===========================================================================


class TestFindOpencodePorts:
    """Consolidated tests for find_opencode_ports() function"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario,netstat_output,mock_check_result,expected_ports",
        [
            # Scenario: empty when netstat has no LISTEN lines
            (
                "no_listen_lines",
                "Active connections\nProto  Local Address\n",
                lambda p: True,
                [],
            ),
            # Scenario: parse and filter valid ports
            (
                "valid_ports_filtered",
                """Active Internet connections
Proto Recv-Q Send-Q  Local Address          Foreign Address        (state)
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
tcp4       0      0  127.0.0.1.3000         *.*                    LISTEN
tcp4       0      0  192.168.1.1.80         *.*                    LISTEN
tcp4       0      0  127.0.0.1.500          *.*                    LISTEN
""",
                lambda p: p == 8080,
                [8080],
            ),
            # Scenario: invalid port numbers ignored
            (
                "invalid_ports_ignored",
                """Active Internet connections
tcp4       0      0  127.0.0.1.abc          *.*                    LISTEN
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
""",
                lambda p: True,
                [8080],
            ),
            # Scenario: ports outside valid range filtered
            (
                "range_filtered",
                """Active Internet connections
tcp4       0      0  127.0.0.1.80           *.*                    LISTEN
tcp4       0      0  127.0.0.1.1024         *.*                    LISTEN
tcp4       0      0  127.0.0.1.65536        *.*                    LISTEN
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
""",
                lambda p: True,
                [8080],
            ),
            # Scenario: multiple opencode instances
            (
                "multiple_instances",
                """Active Internet connections
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
tcp4       0      0  127.0.0.1.8081         *.*                    LISTEN
tcp4       0      0  127.0.0.1.9000         *.*                    LISTEN
""",
                lambda p: p in [8080, 9000],
                [8080, 9000],
            ),
        ],
    )
    async def test_netstat_parsing_scenarios(
        self, scenario, netstat_output, mock_check_result, expected_ports
    ):
        """Test netstat output parsing with various scenarios"""
        mock_result = MagicMock()
        mock_result.stdout = netstat_output

        async def mock_check(port):
            return mock_check_result(port)

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.ports.check_opencode_port",
                side_effect=mock_check,
            ):
                mock_run.return_value = mock_result
                result = await find_opencode_ports()

                assert sorted(result) == sorted(expected_ports), (
                    f"Failed for scenario: {scenario}"
                )
                # Verify result is a list (not just truthy check)
                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_netstat_fails(self):
        """When subprocess raises exception, return empty list"""
        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Command failed")
            result = await find_opencode_ports()

            assert result == []
            assert isinstance(result, list)


# ===========================================================================
# Tests for get_tty_for_port()
# ===========================================================================


class TestGetTtyForPort:
    """Consolidated tests for get_tty_for_port() function"""

    @pytest.mark.parametrize(
        "scenario,lsof_output,ps_output,ps_raises,expected",
        [
            # No opencode process found
            (
                "no_opencode_process",
                "COMMAND     PID   USER\nnode      1234   user",
                None,
                False,
                "",
            ),
            # Valid TTY returned
            (
                "valid_tty",
                """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (LISTEN)
""",
                "ttys001",
                False,
                "ttys001",
            ),
            # TTY is unknown (??)
            (
                "unknown_tty",
                """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (LISTEN)
""",
                "??",
                False,
                "",
            ),
            # Empty TTY response
            (
                "empty_tty",
                """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (LISTEN)
""",
                "",
                False,
                "",
            ),
            # Line without LISTEN
            (
                "no_listen",
                """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (ESTABLISHED)
""",
                None,
                False,
                "",
            ),
            # Insufficient line parts
            (
                "insufficient_parts",
                "LISTEN\n",
                None,
                False,
                "",
            ),
            # PS command fails
            (
                "ps_fails",
                """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (LISTEN)
""",
                None,
                True,
                "",
            ),
        ],
    )
    def test_tty_detection_scenarios(
        self, scenario, lsof_output, ps_output, ps_raises, expected
    ):
        """Test TTY detection with various lsof/ps scenarios"""
        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            if ps_raises:
                mock_run.side_effect = [mock_lsof, Exception("ps failed")]
            elif ps_output is not None:
                mock_ps = MagicMock()
                mock_ps.stdout = ps_output
                mock_run.side_effect = [mock_lsof, mock_ps]
            else:
                mock_run.return_value = mock_lsof

            result = get_tty_for_port(8080)

            assert result == expected, f"Failed for scenario: {scenario}"
            assert isinstance(result, str)

    def test_returns_empty_string_when_lsof_fails(self):
        """When lsof raises exception, return empty string"""
        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Command failed")
            result = get_tty_for_port(8080)

            assert result == ""
            assert isinstance(result, str)


# ===========================================================================
# Tests for extract_tools_from_messages()
# ===========================================================================


class TestExtractToolsFromMessages:
    """Consolidated tests for extract_tools_from_messages() function"""

    @pytest.mark.parametrize(
        "invalid_input",
        [None, "not a list", 123, {"key": "value"}],
    )
    def test_returns_empty_list_for_invalid_inputs(self, invalid_input):
        """Return empty list for None, non-list, or invalid inputs"""
        result = extract_tools_from_messages(invalid_input)
        assert result == []
        assert isinstance(result, list)

    def test_returns_empty_list_for_empty_or_no_tools(self):
        """Return empty list when messages is empty or has no tool parts"""
        # Empty list
        assert extract_tools_from_messages([]) == []

        # No parts field
        assert extract_tools_from_messages([{"content": "Hello"}]) == []

        # No tool-type parts
        messages = [{"parts": [{"type": "text", "content": "Hello"}]}]
        assert extract_tools_from_messages(messages) == []

        # Empty state (status not "running")
        messages = [{"parts": [{"type": "tool", "tool": "test", "state": {}}]}]
        assert extract_tools_from_messages(messages) == []

        # Completed tool (not running)
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {"status": "completed", "input": {"command": "ls"}},
                    }
                ]
            }
        ]
        assert extract_tools_from_messages(messages) == []

    @pytest.mark.parametrize(
        "arg_type,tool_name,input_data,expected_arg",
        [
            ("command", "bash", {"command": "npm test"}, "npm test"),
            ("filePath", "read", {"filePath": "/path/to/file.py"}, "/path/to/file.py"),
            ("description", "bash", {"description": "Running tests"}, "Running tests"),
            ("pattern", "glob", {"pattern": "**/*.py"}, "**/*.py"),
        ],
    )
    def test_extracts_tool_with_various_argument_types(
        self, arg_type, tool_name, input_data, expected_arg
    ):
        """Extract running tools with command, filePath, description, pattern args"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": tool_name,
                        "state": {"status": "running", "input": input_data},
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)

        assert len(result) == 1
        assert result[0].name == tool_name
        assert result[0].arg == expected_arg

    def test_extracts_tool_with_title_fallback(self):
        """Extract running tool with title in state when no input args"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "webfetch",
                        "state": {
                            "status": "running",
                            "title": "Fetching documentation",
                            "input": {},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)

        assert len(result) == 1
        assert result[0].name == "webfetch"
        assert result[0].arg == "Fetching documentation"

    def test_prompt_truncated_to_50_chars(self):
        """Extract running tool with prompt (truncated to 50 chars)"""
        long_prompt = "A" * 100
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "ask",
                        "state": {
                            "status": "running",
                            "input": {"prompt": long_prompt},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)

        assert len(result) == 1
        assert result[0].arg == "A" * 50
        assert len(result[0].arg) == 50

    def test_extracts_multiple_running_tools(self):
        """Extract multiple running tools, ignoring completed ones"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {"status": "running", "input": {"command": "ls"}},
                    },
                    {
                        "type": "tool",
                        "tool": "read",
                        "state": {
                            "status": "running",
                            "input": {"filePath": "/file.py"},
                        },
                    },
                    {
                        "type": "tool",
                        "tool": "write",
                        "state": {"status": "completed", "input": {}},
                    },
                ]
            }
        ]
        result = extract_tools_from_messages(messages)

        assert len(result) == 2
        assert result[0].name == "bash"
        assert result[0].arg == "ls"
        assert result[1].name == "read"
        assert result[1].arg == "/file.py"

    def test_handles_none_input_gracefully(self):
        """Handle case where input is None"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "unknown",
                        "state": {"status": "running", "input": None},
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)

        assert len(result) == 1
        assert result[0].name == "unknown"
        assert result[0].arg == ""

    def test_elapsed_ms_calculation(self):
        """Test elapsed_ms calculation from state.time.start"""
        # Use a start time 3 seconds in the past
        start_time_ms = int((time.time() - 3) * 1000)
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "running",
                            "input": {"command": "sleep 10"},
                            "time": {"start": start_time_ms},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)

        assert len(result) == 1
        # elapsed_ms should be approximately 3000ms (allow 500ms tolerance)
        assert 2500 <= result[0].elapsed_ms <= 4000

    @pytest.mark.parametrize(
        "time_field,expected_elapsed",
        [
            (None, 0),  # No time field
            ({"start": None}, 0),  # start is None
        ],
    )
    def test_elapsed_ms_edge_cases(self, time_field, expected_elapsed):
        """Test elapsed_ms is 0 for missing/None time fields"""
        state = {"status": "running", "input": {"command": "ls"}}
        if time_field is not None:
            state["time"] = time_field

        messages = [{"parts": [{"type": "tool", "tool": "bash", "state": state}]}]
        result = extract_tools_from_messages(messages)

        assert len(result) == 1
        assert result[0].elapsed_ms == expected_elapsed

    def test_elapsed_ms_clamped_to_non_negative(self):
        """elapsed_ms is clamped to 0 if start time is in the future"""
        future_start_ms = int((time.time() + 10) * 1000)
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "running",
                            "input": {"command": "ls"},
                            "time": {"start": future_start_ms},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)

        assert len(result) == 1
        assert result[0].elapsed_ms == 0


# ===========================================================================
# Tests for count_todos()
# ===========================================================================


class TestCountTodos:
    """Consolidated tests for count_todos() function"""

    @pytest.mark.parametrize("invalid_input", [None, "not a list", 123])
    def test_returns_zeros_for_invalid_inputs(self, invalid_input):
        """Return zeros for None, non-list inputs"""
        pending, in_progress, current, next_label = count_todos(invalid_input)

        assert pending == 0
        assert in_progress == 0
        assert current == ""
        assert next_label == ""

    def test_returns_zeros_for_empty_list(self):
        """Return zeros when todos is empty"""
        pending, in_progress, current, next_label = count_todos([])

        assert pending == 0
        assert in_progress == 0
        assert current == ""
        assert next_label == ""

    def test_counts_and_extracts_labels_correctly(self):
        """Full test of counting pending/in_progress and extracting labels"""
        todos = [
            {"status": "completed", "content": "Done task"},
            {"status": "in_progress", "content": "Working on this"},
            {"status": "in_progress", "content": "Also working"},
            {"status": "pending", "content": "Next task"},
            {"status": "pending", "content": "After that"},
            {"status": "pending"},  # Missing content
            {"content": "No status field"},  # Missing status
        ]
        pending, in_progress, current, next_label = count_todos(todos)

        assert pending == 3  # 2 with content + 1 without content
        assert in_progress == 2
        assert current == "Working on this"  # First in_progress
        assert next_label == "Next task"  # First pending with content


# ===========================================================================
# Tests for fetch_instance()
# ===========================================================================


class TestFetchInstance:
    """Consolidated tests for fetch_instance() async function"""

    @pytest.mark.asyncio
    async def test_returns_instance_with_no_agents_when_no_busy_sessions(
        self, mock_aioresponse
    ):
        """Return instance with empty agents when no busy sessions or status is None"""
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/status",
            payload={},
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session",
            payload=[],
        )

        with patch(
            "opencode_monitor.core.monitor.fetcher.get_tty_for_port",
            return_value="ttys001",
        ):
            (
                instance,
                pending,
                in_progress,
                idle_candidates,
                busy_ids,
            ) = await fetch_instance(8080)

            assert instance.port == 8080
            assert instance.tty == "ttys001"
            assert instance.agents == []
            assert pending == 0
            assert in_progress == 0
            assert idle_candidates == []
            assert busy_ids == set()

    @pytest.mark.asyncio
    async def test_fetches_and_processes_busy_sessions_fully(self, mock_aioresponse):
        """Complete test of busy session fetching with tools, todos, and parent detection"""
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/status",
            payload={
                "ses_main": {"type": "busy"},
                "ses_sub": {"type": "busy"},
            },
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session",
            payload=[
                {"id": "ses_main"},
                {"id": "ses_sub"},
            ],
        )

        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_main",
            payload={"title": "Main Session", "directory": "/home/user/project"},
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_main/message?limit=1",
            payload=[
                {
                    "parts": [
                        {
                            "type": "tool",
                            "tool": "bash",
                            "state": {
                                "status": "running",
                                "input": {"command": "npm test"},
                            },
                        }
                    ]
                }
            ],
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_main/todo",
            payload=[
                {"status": "pending", "content": "Task 1"},
                {"status": "in_progress", "content": "Working"},
            ],
        )

        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_sub",
            payload={
                "title": "Sub-agent",
                "directory": "/home/user/project",
                "parentID": "ses_main",
            },
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_sub/message?limit=1",
            payload=[],
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_sub/todo",
            payload=[{"status": "pending", "content": "Sub task"}],
        )

        with patch(
            "opencode_monitor.core.monitor.fetcher.get_tty_for_port",
            return_value="ttys001",
        ):
            (
                instance,
                pending,
                in_progress,
                idle_candidates,
                busy_ids,
            ) = await fetch_instance(8080)

            assert instance.port == 8080
            assert instance.tty == "ttys001"
            assert len(instance.agents) == 2

            main_agent = next(a for a in instance.agents if a.id == "ses_main")
            assert main_agent.title == "Main Session"
            assert main_agent.dir == "project"
            assert main_agent.status == SessionStatus.BUSY
            assert len(main_agent.tools) == 1
            assert main_agent.tools[0].name == "bash"
            assert main_agent.tools[0].arg == "npm test"
            assert main_agent.parent_id is None
            assert not main_agent.is_subagent

            sub_agent = next(a for a in instance.agents if a.id == "ses_sub")
            assert sub_agent.title == "Sub-agent"
            assert sub_agent.parent_id == "ses_main"
            assert sub_agent.is_subagent

            assert pending == 2
            assert in_progress == 1
            assert "ses_main" in busy_ids
            assert "ses_sub" in busy_ids

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "info_data,expected_title,expected_dir",
        [
            (None, "Sans titre", "global"),
            ({}, "Sans titre", "global"),
            (
                {"title": None, "directory": None},
                None,
                "global",
            ),
            ({"title": "Test", "directory": ""}, "Test", "global"),
            ({"directory": "/project"}, "Sans titre", "project"),
        ],
    )
    async def test_handles_missing_or_empty_session_info(
        self, mock_aioresponse, info_data, expected_title, expected_dir
    ):
        """Handle sessions with missing or empty title/directory"""
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/status",
            payload={"ses_123": {"type": "busy"}},
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session",
            payload=[{"id": "ses_123"}],
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_123",
            payload=info_data,
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_123/message?limit=1",
            payload=[],
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/ses_123/todo",
            payload=[],
        )

        with patch(
            "opencode_monitor.core.monitor.fetcher.get_tty_for_port",
            return_value="",
        ):
            instance, _, _, _, _ = await fetch_instance(8080)

            assert len(instance.agents) == 1
            assert instance.agents[0].title == expected_title
            assert instance.agents[0].dir == expected_dir

    @pytest.mark.asyncio
    async def test_returns_idle_candidates_excluding_subagents(self, mock_aioresponse):
        """Return idle candidates for post-processing, excluding sub-agents"""
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session/status",
            payload={},
        )
        mock_aioresponse.get(
            "http://127.0.0.1:8080/session",
            payload=[
                {"id": "parent_session", "title": "Parent", "directory": "/project"},
                {
                    "id": "subagent",
                    "title": "Sub-agent",
                    "directory": "/project",
                    "parentID": "parent_session",
                },
            ],
        )

        with patch(
            "opencode_monitor.core.monitor.fetcher.get_tty_for_port",
            return_value="",
        ):
            (
                instance,
                pending,
                in_progress,
                idle_candidates,
                busy_ids,
            ) = await fetch_instance(8080)

            assert len(idle_candidates) == 1
            assert idle_candidates[0]["id"] == "parent_session"
            assert busy_ids == set()


# ===========================================================================
# Tests for fetch_all_instances()
# ===========================================================================


class TestFetchAllInstances:
    """Consolidated tests for fetch_all_instances() async function"""

    @pytest.mark.asyncio
    async def test_returns_disconnected_state_when_no_ports(self):
        """Return disconnected state when no OpenCode ports found"""
        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports", return_value=[]
        ):
            state = await fetch_all_instances()

            assert not state.connected
            assert state.instances == []

    @pytest.mark.asyncio
    async def test_aggregates_instances_and_todos(self):
        """Test full instance fetching with todo aggregation across instances"""
        instance1 = Instance(
            port=8080,
            tty="ttys001",
            agents=[
                Agent(
                    id="ses_1",
                    title="Test",
                    dir="project",
                    full_dir="/home/user/project",
                    status=SessionStatus.BUSY,
                    tools=[],
                    todos=AgentTodos(pending=2, in_progress=1),
                )
            ],
        )
        instance2 = Instance(port=9000, tty="", agents=[])

        async def mock_find():
            return [8080, 9000]

        async def mock_fetch(port):
            if port == 8080:
                return (instance1, 2, 1, [], {"ses_1"})
            else:
                return (instance2, 3, 2, [], set())

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                assert state.connected
                assert len(state.instances) == 2
                assert state.instances[0].port == 8080
                assert state.todos.pending == 5  # 2 + 3
                assert state.todos.in_progress == 3  # 1 + 2

    @pytest.mark.asyncio
    async def test_handles_none_instances_gracefully(self):
        """Handle None instances and return disconnected when all are None"""
        valid_instance = Instance(port=8080, tty="", agents=[])

        async def mock_find():
            return [8080, 9000, 9001]

        async def mock_fetch(port):
            if port == 8080:
                return (valid_instance, 1, 0, [], set())
            else:
                return (None, 0, 0, [], set())

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                assert state.connected
                assert len(state.instances) == 1
                assert state.instances[0].port == 8080

    @pytest.mark.asyncio
    async def test_idle_session_filtering_with_cache(self):
        """Test idle session filtering based on known_active_sessions cache"""
        instance = Instance(port=8080, tty="", agents=[])

        async def mock_find():
            return [8080]

        async def mock_fetch(port):
            idle_candidates = [
                {"id": "known_session", "title": "Known", "directory": "/project"},
                {"id": "zombie_session", "title": "Zombie", "directory": "/project"},
            ]
            return (instance, 0, 0, idle_candidates, set())

        def mock_check_pending(session_id, storage_path=None):
            return AskUserResult(has_pending=True, title=f"Question for {session_id}")

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                with patch(
                    "opencode_monitor.core.monitor.fetcher.check_pending_ask_user_from_disk",
                    side_effect=mock_check_pending,
                ):
                    # With cache: only known_session should be included
                    state = await fetch_all_instances(
                        known_active_sessions={"known_session"}
                    )

                    assert len(state.instances[0].agents) == 1
                    assert state.instances[0].agents[0].id == "known_session"
                    assert state.instances[0].agents[0].has_pending_ask_user
                    assert state.instances[0].agents[0].status == SessionStatus.IDLE

    @pytest.mark.asyncio
    async def test_includes_all_idle_sessions_when_no_cache(self):
        """Include all idle sessions with pending ask_user when no cache provided"""
        instance = Instance(port=8080, tty="", agents=[])

        async def mock_find():
            return [8080]

        async def mock_fetch(port):
            return (
                instance,
                0,
                0,
                [{"id": "any_session", "title": "Any", "directory": "/project"}],
                set(),
            )

        def mock_check_pending(session_id, storage_path=None):
            return AskUserResult(has_pending=True, title="Question")

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                with patch(
                    "opencode_monitor.core.monitor.fetcher.check_pending_ask_user_from_disk",
                    side_effect=mock_check_pending,
                ):
                    # Without cache: include all sessions
                    state = await fetch_all_instances(known_active_sessions=None)

                    assert len(state.instances[0].agents) == 1
                    assert state.instances[0].agents[0].id == "any_session"

    @pytest.mark.asyncio
    async def test_deduplicates_agents_across_instances(self):
        """Ensure agents are not duplicated when appearing in both busy and idle"""
        busy_agent = Agent(
            id="ses_dup",
            title="Busy Agent",
            dir="project",
            full_dir="/project",
            status=SessionStatus.BUSY,
            tools=[],
        )
        instance = Instance(port=8080, tty="", agents=[busy_agent])

        async def mock_find():
            return [8080]

        async def mock_fetch(port):
            # Session also appears in idle_candidates
            return (
                instance,
                0,
                0,
                [{"id": "ses_dup", "title": "Dup", "directory": "/project"}],
                {"ses_dup"},
            )

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                # Should only have one agent, not duplicated
                all_agent_ids = [
                    agent.id for inst in state.instances for agent in inst.agents
                ]
                assert all_agent_ids.count("ses_dup") == 1


# ===========================================================================
# Tests for AskUserResult dataclass
# ===========================================================================


class TestAskUserResult:
    """Tests for AskUserResult dataclass"""

    def test_default_and_custom_values(self):
        """Test default values and custom title"""
        # Default
        result_default = AskUserResult(has_pending=False)
        assert not result_default.has_pending
        assert result_default.title == ""

        # Custom
        result_custom = AskUserResult(has_pending=True, title="User input needed")
        assert result_custom.has_pending
        assert result_custom.title == "User input needed"


# ===========================================================================
# Tests for _find_latest_notify_ask_user()
# ===========================================================================


class TestFindLatestNotifyAskUser:
    """Consolidated tests for _find_latest_notify_ask_user()"""

    def test_returns_empty_when_no_files_or_old_files(self, tmp_path):
        """Return empty results for no files or files older than cutoff"""
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Test with empty directory
        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time=0
        )

        assert timestamp == 0
        assert notify_input == {}
        assert messages == []

    def test_parses_messages_and_finds_notify(self, tmp_path):
        """Parse message files and find notify_ask_user in part files"""
        import os

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create message files
        for i, (created, role) in enumerate(
            [(1000, "assistant"), (2000, "assistant")], 1
        ):
            msg_file = message_dir / f"msg_00{i}.json"
            msg_file.write_text(
                json.dumps(
                    {
                        "id": f"msg_00{i}",
                        "time": {"created": created},
                        "role": role,
                    }
                )
            )

            # Create part with notify_ask_user for each message
            msg_part_dir = part_dir / f"msg_00{i}"
            msg_part_dir.mkdir(parents=True)

            part_data = {
                "type": "tool",
                "tool": "notify_ask_user",
                "state": {
                    "status": "completed",
                    "time": {"start": created + 100},
                    "input": {"title": f"Question {i}"},
                },
            }
            part_file = msg_part_dir / f"prt_00{i}.json"
            part_file.write_text(json.dumps(part_data))

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        # Should find the most recent notify
        assert timestamp == 2100  # 2000 + 100
        assert notify_input.get("title") == "Question 2"
        assert len(messages) == 2

    @pytest.mark.parametrize(
        "scenario,part_data,expected_timestamp",
        [
            # Non-completed status ignored
            (
                "running_status",
                {
                    "type": "tool",
                    "tool": "notify_ask_user",
                    "state": {"status": "running", "time": {"start": 1500}},
                },
                0,
            ),
            # Different tool ignored
            (
                "different_tool",
                {
                    "type": "tool",
                    "tool": "bash",
                    "state": {"status": "completed", "time": {"start": 1500}},
                },
                0,
            ),
        ],
    )
    def test_ignores_non_matching_parts(
        self, tmp_path, scenario, part_data, expected_timestamp
    ):
        """Ignore parts that are not completed notify_ask_user"""
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            '{"id": "msg_001", "time": {"created": 1000}, "role": "assistant"}'
        )

        # Create part with test data
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        assert timestamp == expected_timestamp, f"Failed for scenario: {scenario}"

    def test_handles_malformed_json_gracefully(self, tmp_path):
        """Handle malformed JSON files gracefully"""
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create malformed message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text("not valid json {{{")

        # Create valid message file
        msg_file2 = message_dir / "msg_002.json"
        msg_file2.write_text(
            '{"id": "msg_002", "time": {"created": 2000}, "role": "user"}'
        )

        # Create malformed part and valid part
        msg_part_dir = part_dir / "msg_002"
        msg_part_dir.mkdir(parents=True)
        (msg_part_dir / "prt_001.json").write_text("invalid json")
        (msg_part_dir / "prt_002.json").write_text(
            json.dumps(
                {
                    "type": "tool",
                    "tool": "notify_ask_user",
                    "state": {
                        "status": "completed",
                        "time": {"start": 2500},
                        "input": {"title": "Valid"},
                    },
                }
            )
        )

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        # Should handle malformed files and still find valid data
        assert len(messages) == 1
        assert timestamp == 2500
        assert notify_input.get("title") == "Valid"


# ===========================================================================
# Tests for _has_activity_after_notify()
# ===========================================================================


class TestHasActivityAfterNotify:
    """Consolidated tests for _has_activity_after_notify()"""

    @pytest.mark.parametrize(
        "scenario,messages,part_tool,expected",
        [
            # No messages after notify
            ("no_messages_after", [(1000, "msg_001", "assistant")], None, False),
            # User message after notify
            ("user_after", [(2500, "msg_002", "user")], None, True),
            # Other tool after notify (activity detected)
            ("other_tool_after", [(2500, "msg_002", "assistant")], "bash", True),
            # notify_ask_user after (not real activity)
            (
                "notify_after",
                [(2500, "msg_002", "assistant")],
                "notify_ask_user",
                False,
            ),
        ],
    )
    def test_activity_detection_scenarios(
        self, tmp_path, scenario, messages, part_tool, expected
    ):
        """Test activity detection with various scenarios"""
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create part file if needed
        if part_tool and any(m[1] == "msg_002" for m in messages):
            msg_part_dir = part_dir / "msg_002"
            msg_part_dir.mkdir(parents=True)
            part_data = {
                "type": "tool",
                "tool": part_tool,
                "state": {"status": "completed"},
            }
            (msg_part_dir / "prt_001.json").write_text(json.dumps(part_data))

        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=messages,
            part_dir=part_dir,
        )

        assert result is expected, f"Failed for scenario: {scenario}"

    def test_handles_missing_or_malformed_parts(self, tmp_path):
        """Handle missing part directory and malformed JSON"""
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # No part directory for message
        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=[(2500, "msg_missing", "assistant")],
            part_dir=part_dir,
        )
        assert not result

        # Create malformed part file
        msg_part_dir = part_dir / "msg_malformed"
        msg_part_dir.mkdir(parents=True)
        (msg_part_dir / "prt_001.json").write_text("not valid json")

        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=[(2500, "msg_malformed", "assistant")],
            part_dir=part_dir,
        )
        assert not result


# ===========================================================================
# Tests for check_pending_ask_user_from_disk()
# ===========================================================================


class TestCheckPendingAskUserFromDisk:
    """Consolidated tests for check_pending_ask_user_from_disk()"""

    def test_returns_false_for_missing_directory_or_no_notify(self, tmp_path):
        """Return has_pending=False when directory missing or no recent notify"""
        # Missing directory
        result = check_pending_ask_user_from_disk(
            session_id="nonexistent",
            storage_path=tmp_path,
        )
        assert not result.has_pending
        assert result.title == ""

        # Empty directory
        message_dir = tmp_path / "message" / "empty_session"
        message_dir.mkdir(parents=True)
        (tmp_path / "part").mkdir(parents=True)

        result = check_pending_ask_user_from_disk(
            session_id="empty_session",
            storage_path=tmp_path,
        )
        assert not result.has_pending

    def test_returns_true_when_pending_notify_found(self, tmp_path):
        """Return has_pending=True when pending notify_ask_user found"""
        current_time = int(time.time() * 1000)

        # Create message and part structure
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        (message_dir / "msg_001.json").write_text(
            json.dumps(
                {
                    "id": "msg_001",
                    "time": {"created": current_time},
                    "role": "assistant",
                }
            )
        )

        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)
        (msg_part_dir / "prt_001.json").write_text(
            json.dumps(
                {
                    "type": "tool",
                    "tool": "notify_ask_user",
                    "state": {
                        "status": "completed",
                        "time": {"start": current_time},
                        "input": {"title": "Waiting for user"},
                    },
                }
            )
        )

        result = check_pending_ask_user_from_disk(
            session_id="session_1",
            storage_path=tmp_path,
        )

        assert result.has_pending
        assert result.title == "Waiting for user"

    def test_returns_false_when_user_responded(self, tmp_path):
        """Return has_pending=False when user responded after notify"""
        current_time = int(time.time() * 1000)

        # Create message directory with assistant and user messages
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)

        # Assistant message with notify
        (message_dir / "msg_001.json").write_text(
            json.dumps(
                {
                    "id": "msg_001",
                    "time": {"created": current_time - 5000},
                    "role": "assistant",
                }
            )
        )

        # User response after notify
        (message_dir / "msg_002.json").write_text(
            json.dumps(
                {
                    "id": "msg_002",
                    "time": {"created": current_time - 2000},  # After notify
                    "role": "user",
                }
            )
        )

        # Create part with notify
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)
        (msg_part_dir / "prt_001.json").write_text(
            json.dumps(
                {
                    "type": "tool",
                    "tool": "notify_ask_user",
                    "state": {
                        "status": "completed",
                        "time": {"start": current_time - 4000},  # 4 seconds ago
                        "input": {"title": "Question"},
                    },
                }
            )
        )

        result = check_pending_ask_user_from_disk(
            session_id="session_1",
            storage_path=tmp_path,
        )

        assert not result.has_pending

    def test_respects_timeout_setting(self, tmp_path):
        """Notifications older than timeout are ignored"""
        import os

        # Create notification from 45 minutes ago
        forty_five_min_ago = time.time() - (45 * 60)
        forty_five_min_ago_ms = int(forty_five_min_ago * 1000)

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            json.dumps(
                {
                    "id": "msg_001",
                    "time": {"created": forty_five_min_ago_ms},
                    "role": "assistant",
                }
            )
        )
        os.utime(msg_file, (forty_five_min_ago, forty_five_min_ago))

        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(
            json.dumps(
                {
                    "type": "tool",
                    "tool": "notify_ask_user",
                    "state": {
                        "status": "completed",
                        "time": {"start": forty_five_min_ago_ms},
                        "input": {"title": "Old question"},
                    },
                }
            )
        )
        os.utime(part_file, (forty_five_min_ago, forty_five_min_ago))

        # With 30 minute timeout: should NOT find it
        mock_settings = MagicMock()
        mock_settings.ask_user_timeout = 30 * 60

        with patch(
            "opencode_monitor.core.monitor.ask_user.get_settings",
            return_value=mock_settings,
        ):
            result = check_pending_ask_user_from_disk(
                session_id="session_1",
                storage_path=tmp_path,
            )
            assert not result.has_pending

        # With 1 hour timeout: should find it
        mock_settings.ask_user_timeout = 60 * 60

        with patch(
            "opencode_monitor.core.monitor.ask_user.get_settings",
            return_value=mock_settings,
        ):
            result = check_pending_ask_user_from_disk(
                session_id="session_1",
                storage_path=tmp_path,
            )
        assert result.has_pending

    def test_handles_exception_gracefully(self, tmp_path):
        """Handle exceptions during file scanning gracefully"""
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)

        with patch(
            "opencode_monitor.core.monitor._find_latest_notify_ask_user",
            side_effect=Exception("File error"),
        ):
            result = check_pending_ask_user_from_disk(
                session_id="session_1",
                storage_path=tmp_path,
            )

            assert not result.has_pending
