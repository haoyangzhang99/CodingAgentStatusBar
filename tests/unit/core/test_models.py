"""
Tests for opencode_status_bar.core.models

Coverage target: 100% for all model classes
Uses parametrized tests for enum values and edge cases.
"""

import pytest
from opencode_status_bar.core.models import (
    SessionStatus,
    TodoStatus,
    Tool,
    AgentTodos,
    Agent,
    Instance,
    Todos,
    State,
    UsagePeriod,
    Usage,
)


# =============================================================================
# Enum Tests (Parametrized)
# =============================================================================


@pytest.mark.parametrize(
    "enum_class,member,expected_value",
    [
        (SessionStatus, "IDLE", "idle"),
        (SessionStatus, "BUSY", "busy"),
        (TodoStatus, "PENDING", "pending"),
        (TodoStatus, "IN_PROGRESS", "in_progress"),
        (TodoStatus, "COMPLETED", "completed"),
    ],
)
def test_enum_values(enum_class, member, expected_value):
    """All enum values are correct."""
    assert getattr(enum_class, member).value == expected_value


# =============================================================================
# Tool Tests
# =============================================================================


class TestTool:
    """Tests for Tool dataclass"""

    @pytest.mark.parametrize(
        "name,arg,elapsed_ms,expected_dict",
        [
            # Default arg and elapsed_ms
            (
                "bash",
                "",
                0,
                {
                    "name": "bash",
                    "arg": "",
                    "elapsed_ms": 0,
                    "may_need_permission": False,
                },
            ),
            # Custom arg
            (
                "read",
                "/path/to/file.py",
                0,
                {
                    "name": "read",
                    "arg": "/path/to/file.py",
                    "elapsed_ms": 0,
                    "may_need_permission": False,
                },
            ),
            # Custom elapsed_ms (below threshold)
            (
                "bash",
                "ls",
                5000,
                {
                    "name": "bash",
                    "arg": "ls",
                    "elapsed_ms": 5000,
                    "may_need_permission": False,
                },
            ),
            # Above threshold - may_need_permission True
            (
                "read",
                "/file.py",
                10000,
                {
                    "name": "read",
                    "arg": "/file.py",
                    "elapsed_ms": 10000,
                    "may_need_permission": True,
                },
            ),
            # Write tool
            (
                "write",
                "content.txt",
                0,
                {
                    "name": "write",
                    "arg": "content.txt",
                    "elapsed_ms": 0,
                    "may_need_permission": False,
                },
            ),
        ],
    )
    def test_tool_creation_and_to_dict(self, name, arg, elapsed_ms, expected_dict):
        """Tool creation with various params and to_dict serialization."""
        if arg == "":
            tool = Tool(name=name)
            if elapsed_ms > 0:
                tool = Tool(name=name, elapsed_ms=elapsed_ms)
        else:
            tool = Tool(name=name, arg=arg, elapsed_ms=elapsed_ms)

        assert tool.name == expected_dict["name"]
        assert tool.arg == expected_dict["arg"]
        assert tool.elapsed_ms == expected_dict["elapsed_ms"]
        assert tool.to_dict() == expected_dict

    def test_excluded_tools_contains_task(self):
        """EXCLUDED_TOOLS contains 'task' for sub-agents."""
        assert "task" in Tool.EXCLUDED_TOOLS

    @pytest.mark.parametrize(
        "tool_name,elapsed_ms,expected",
        [
            # Below threshold (5s = 5000ms) - should be False
            ("bash", 0, False),
            ("bash", 4999, False),
            ("read", 5000, False),  # Exactly at threshold, not above
            # Above threshold - should be True
            ("bash", 5001, True),
            ("read", 10000, True),
            ("write", 6000, True),
            # Excluded tools - always False regardless of elapsed_ms
            ("task", 0, False),
            ("task", 5001, False),
            ("task", 100000, False),
            ("Task", 10000, False),  # Case-insensitive check
        ],
    )
    def test_may_need_permission(self, tool_name, elapsed_ms, expected):
        """may_need_permission property based on elapsed_ms and exclusions."""
        tool = Tool(name=tool_name, elapsed_ms=elapsed_ms)
        assert tool.may_need_permission == expected


# =============================================================================
# AgentTodos Tests
# =============================================================================


class TestAgentTodos:
    """Tests for AgentTodos dataclass"""

    @pytest.mark.parametrize(
        "pending,in_progress,current_label,next_label,expected_total",
        [
            # Defaults
            (0, 0, "", "", 0),
            # With values
            (3, 1, "Implementing feature", "Write tests", 4),
            (5, 2, "Current task", "Next task", 7),
            (10, 0, "Only pending", "", 10),
            (0, 5, "", "Only in progress", 5),
        ],
    )
    def test_creation_total_and_to_dict(
        self, pending, in_progress, current_label, next_label, expected_total
    ):
        """AgentTodos creation, total property, and to_dict."""
        if (
            pending == 0
            and in_progress == 0
            and current_label == ""
            and next_label == ""
        ):
            todos = AgentTodos()
        else:
            todos = AgentTodos(
                pending=pending,
                in_progress=in_progress,
                current_label=current_label,
                next_label=next_label,
            )

        assert todos.pending == pending
        assert todos.in_progress == in_progress
        assert todos.current_label == current_label
        assert todos.next_label == next_label
        assert todos.total == expected_total
        assert todos.to_dict() == {
            "pending": pending,
            "in_progress": in_progress,
            "current_label": current_label,
            "next_label": next_label,
        }


# =============================================================================
# Agent Tests
# =============================================================================


class TestAgent:
    """Tests for Agent dataclass"""

    @pytest.mark.parametrize(
        "parent_id,expected_is_subagent",
        [
            (None, False),
            ("parent-123", True),
        ],
    )
    def test_agent_creation_and_is_subagent(self, parent_id, expected_is_subagent):
        """Agent creation with various parent_id and is_subagent property."""
        agent = Agent(
            id="agent-123",
            title="Test Session",
            dir="project",
            full_dir="/home/user/project",
            status=SessionStatus.IDLE,
            parent_id=parent_id,
        )

        assert agent.id == "agent-123"
        assert agent.title == "Test Session"
        assert agent.dir == "project"
        assert agent.full_dir == "/home/user/project"
        assert agent.status == SessionStatus.IDLE
        assert agent.tools == []
        assert agent.todos.pending == 0
        assert agent.todos.in_progress == 0
        assert agent.parent_id == parent_id
        assert agent.is_subagent == expected_is_subagent

    def test_to_dict_complete(self):
        """to_dict returns correct structure with tools, todos, and optional parent_id."""
        tool = Tool(name="bash", arg="ls -la")
        todos = AgentTodos(pending=2, in_progress=1, current_label="Task")
        agent = Agent(
            id="agent-123",
            title="Test",
            dir="proj",
            full_dir="/full/path/proj",
            status=SessionStatus.BUSY,
            tools=[tool],
            todos=todos,
        )
        result = agent.to_dict()

        # Core fields
        assert result["id"] == "agent-123"
        assert result["title"] == "Test"
        assert result["dir"] == "proj"
        assert result["full_dir"] == "/full/path/proj"
        assert result["status"] == "busy"
        assert result["tools"] == [
            {
                "name": "bash",
                "arg": "ls -la",
                "elapsed_ms": 0,
                "may_need_permission": False,
            }
        ]
        assert result["todos"] == {
            "pending": 2,
            "in_progress": 1,
            "current_label": "Task",
            "next_label": "",
        }
        # ask_user fields (defaults)
        assert not result["has_pending_ask_user"]  # Direct boolean assertion
        assert result["ask_user_title"] == ""
        assert result["ask_user_question"] == ""
        assert result["ask_user_options"] == []
        assert result["ask_user_repo"] == ""
        assert result["ask_user_agent"] == ""
        assert result["ask_user_branch"] == ""
        assert result["ask_user_urgency"] == "normal"
        # No parent_id when not set
        assert "parent_id" not in result

    def test_to_dict_with_parent_and_multiple_tools(self):
        """to_dict includes parent_id when set and serializes multiple tools."""
        tools = [
            Tool(name="read", arg="file1.py"),
            Tool(name="write", arg="file2.py"),
            Tool(name="bash", arg="pytest"),
        ]
        agent = Agent(
            id="sub-123",
            title="Sub Agent",
            dir="proj",
            full_dir="/path",
            status=SessionStatus.BUSY,
            tools=tools,
            parent_id="parent-456",
        )
        result = agent.to_dict()

        assert result["parent_id"] == "parent-456"
        assert len(result["tools"]) == 3
        assert result["tools"][0] == {
            "name": "read",
            "arg": "file1.py",
            "elapsed_ms": 0,
            "may_need_permission": False,
        }
        assert result["tools"][1] == {
            "name": "write",
            "arg": "file2.py",
            "elapsed_ms": 0,
            "may_need_permission": False,
        }
        assert result["tools"][2] == {
            "name": "bash",
            "arg": "pytest",
            "elapsed_ms": 0,
            "may_need_permission": False,
        }


# =============================================================================
# Instance Tests
# =============================================================================


class TestInstance:
    """Tests for Instance dataclass"""

    @pytest.mark.parametrize(
        "port,tty,busy_count,idle_count",
        [
            # Defaults
            (3000, "", 0, 0),
            # With tty
            (3001, "/dev/ttys001", 0, 0),
            # With agents
            (3000, "", 2, 1),
            (3000, "", 0, 3),
            (3000, "", 3, 0),
        ],
    )
    def test_instance_creation_and_counts(self, port, tty, busy_count, idle_count):
        """Instance creation with various configs and count properties."""
        agents = [
            Agent(
                id=f"busy-{i}",
                title="Busy",
                dir="d",
                full_dir="/d",
                status=SessionStatus.BUSY,
            )
            for i in range(busy_count)
        ] + [
            Agent(
                id=f"idle-{i}",
                title="Idle",
                dir="d",
                full_dir="/d",
                status=SessionStatus.IDLE,
            )
            for i in range(idle_count)
        ]

        if tty:
            instance = Instance(port=port, tty=tty, agents=agents)
        else:
            instance = (
                Instance(port=port, agents=agents) if agents else Instance(port=port)
            )

        assert instance.port == port
        assert instance.tty == tty
        assert instance.agent_count == busy_count + idle_count
        assert instance.busy_count == busy_count
        assert instance.idle_count == idle_count

    def test_to_dict_complete(self):
        """to_dict returns complete structure with all counts."""
        agent = Agent(
            id="agent-1",
            title="Test Agent",
            dir="project",
            full_dir="/home/project",
            status=SessionStatus.BUSY,
        )
        instance = Instance(port=3000, tty="/dev/ttys001", agents=[agent])
        result = instance.to_dict()

        # Instance fields
        assert result["port"] == 3000
        assert result["tty"] == "/dev/ttys001"
        assert result["agent_count"] == 1
        assert result["busy_count"] == 1
        assert result["idle_count"] == 0
        assert len(result["agents"]) == 1

        # Agent fields in instance
        agent_dict = result["agents"][0]
        assert agent_dict["id"] == "agent-1"
        assert agent_dict["title"] == "Test Agent"
        assert agent_dict["dir"] == "project"
        assert agent_dict["full_dir"] == "/home/project"
        assert agent_dict["status"] == "busy"
        assert agent_dict["tools"] == []
        assert agent_dict["todos"] == {
            "pending": 0,
            "in_progress": 0,
            "current_label": "",
            "next_label": "",
        }
        assert not agent_dict["has_pending_ask_user"]  # Direct boolean assertion

    def test_to_dict_empty_and_mixed_agents(self):
        """to_dict with no agents and with mixed busy/idle agents."""
        # Empty
        empty_instance = Instance(port=3000)
        empty_result = empty_instance.to_dict()
        assert empty_result["agents"] == []
        assert empty_result["agent_count"] == 0
        assert empty_result["busy_count"] == 0
        assert empty_result["idle_count"] == 0

        # Mixed
        agents = [
            Agent(
                id="busy-1",
                title="Busy",
                dir="d",
                full_dir="/d",
                status=SessionStatus.BUSY,
            ),
            Agent(
                id="idle-1",
                title="Idle1",
                dir="d",
                full_dir="/d",
                status=SessionStatus.IDLE,
            ),
            Agent(
                id="idle-2",
                title="Idle2",
                dir="d",
                full_dir="/d",
                status=SessionStatus.IDLE,
            ),
        ]
        mixed_instance = Instance(port=3000, agents=agents)
        mixed_result = mixed_instance.to_dict()
        assert mixed_result["busy_count"] == 1
        assert mixed_result["idle_count"] == 2


# =============================================================================
# Todos Tests
# =============================================================================


class TestTodos:
    """Tests for Todos dataclass"""

    @pytest.mark.parametrize(
        "pending,in_progress",
        [
            (0, 0),  # Defaults
            (10, 3),  # With values
            (5, 2),
        ],
    )
    def test_todos_creation_and_to_dict(self, pending, in_progress):
        """Todos creation and to_dict."""
        if pending == 0 and in_progress == 0:
            todos = Todos()
        else:
            todos = Todos(pending=pending, in_progress=in_progress)

        assert todos.pending == pending
        assert todos.in_progress == in_progress
        assert todos.to_dict() == {"pending": pending, "in_progress": in_progress}


# =============================================================================
# State Tests
# =============================================================================


class TestState:
    """Tests for State dataclass"""

    @pytest.mark.parametrize(
        "connected",
        [False, True],
    )
    def test_state_defaults_and_connected(self, connected):
        """State default values and connected flag."""
        state = State(connected=connected) if connected else State()

        assert state.instances == []
        assert state.todos.pending == 0
        assert state.todos.in_progress == 0
        # Timestamp should be a reasonable value (not 0, within last year)
        assert state.updated > 1700000000  # After Nov 2023
        assert state.connected == connected

    @pytest.mark.parametrize(
        "instance_configs,expected_agent,expected_busy,expected_idle",
        [
            # Empty state
            ([], 0, 0, 0),
            # Single instance with agents
            ([{"busy": 1, "idle": 1}], 2, 1, 1),
            # Multiple instances
            ([{"busy": 2, "idle": 0}, {"busy": 1, "idle": 1}], 4, 3, 1),
            # All idle
            ([{"busy": 0, "idle": 2}, {"busy": 0, "idle": 1}], 3, 0, 3),
            # All busy
            ([{"busy": 2, "idle": 0}, {"busy": 1, "idle": 0}], 3, 3, 0),
        ],
    )
    def test_state_counts_across_instances(
        self, instance_configs, expected_agent, expected_busy, expected_idle
    ):
        """State counts sum agents across all instances."""
        instances = []
        for i, config in enumerate(instance_configs):
            agents = [
                Agent(
                    id=f"busy-{i}-{j}",
                    title="B",
                    dir="d",
                    full_dir="/d",
                    status=SessionStatus.BUSY,
                )
                for j in range(config["busy"])
            ] + [
                Agent(
                    id=f"idle-{i}-{j}",
                    title="I",
                    dir="d",
                    full_dir="/d",
                    status=SessionStatus.IDLE,
                )
                for j in range(config["idle"])
            ]
            instances.append(Instance(port=3000 + i, agents=agents))

        state = State(instances=instances)

        assert state.instance_count == len(instance_configs)
        assert state.agent_count == expected_agent
        assert state.busy_count == expected_busy
        assert state.idle_count == expected_idle

    def test_to_dict_complete(self):
        """to_dict returns complete structure."""
        agent = Agent(
            id="agent-1",
            title="Test",
            dir="proj",
            full_dir="/path/proj",
            status=SessionStatus.BUSY,
        )
        instance = Instance(port=3000, tty="/dev/tty", agents=[agent])
        todos = Todos(pending=5, in_progress=2)
        state = State(
            instances=[instance],
            todos=todos,
            updated=1234567890,
            connected=True,
        )
        result = state.to_dict()

        assert result["instance_count"] == 1
        assert result["agent_count"] == 1
        assert result["busy_count"] == 1
        assert result["idle_count"] == 0
        assert result["todos"] == {"pending": 5, "in_progress": 2}
        assert result["updated"] == 1234567890
        assert result["connected"]  # Direct boolean assertion
        assert len(result["instances"]) == 1
        assert result["instances"][0]["port"] == 3000


# =============================================================================
# UsagePeriod Tests
# =============================================================================


class TestUsagePeriod:
    """Tests for UsagePeriod dataclass"""

    @pytest.mark.parametrize(
        "utilization,resets_at",
        [
            (0, None),  # Defaults
            (75, "2024-01-15T10:00:00Z"),  # With values
            (50, "2024-01-15T12:00:00Z"),
            (25, None),  # Utilization without reset
        ],
    )
    def test_usage_period_creation_and_to_dict(self, utilization, resets_at):
        """UsagePeriod creation and to_dict."""
        if utilization == 0 and resets_at is None:
            period = UsagePeriod()
        else:
            period = UsagePeriod(utilization=utilization, resets_at=resets_at)

        assert period.utilization == utilization
        assert period.resets_at == resets_at
        assert period.to_dict() == {"utilization": utilization, "resets_at": resets_at}


# =============================================================================
# Usage Tests
# =============================================================================


class TestUsage:
    """Tests for Usage dataclass"""

    def test_usage_defaults(self):
        """Usage default values with equality assertions."""
        usage = Usage()

        assert usage.five_hour.utilization == 0
        assert usage.five_hour.resets_at is None
        assert usage.seven_day.utilization == 0
        assert usage.seven_day.resets_at is None
        assert usage.error is None
        # Timestamp should be a reasonable value (not 0, within last year)
        assert usage.updated > 1700000000  # After Nov 2023

    @pytest.mark.parametrize(
        "five_hour_util,five_hour_reset,seven_day_util,seven_day_reset,error",
        [
            (30, "2024-01-15T15:00:00Z", 60, "2024-01-20T00:00:00Z", None),
            (40, "2024-01-15T15:00:00Z", 80, "2024-01-20T00:00:00Z", None),
            (0, None, 0, None, "API rate limited"),
            (0, None, 0, None, "Connection failed"),
        ],
    )
    def test_usage_with_periods_and_errors(
        self, five_hour_util, five_hour_reset, seven_day_util, seven_day_reset, error
    ):
        """Usage with custom periods and/or error."""
        five_hour = UsagePeriod(utilization=five_hour_util, resets_at=five_hour_reset)
        seven_day = UsagePeriod(utilization=seven_day_util, resets_at=seven_day_reset)

        if error:
            usage = Usage(error=error)
        else:
            usage = Usage(five_hour=five_hour, seven_day=seven_day)

        if not error:
            assert usage.five_hour.utilization == five_hour_util
            assert usage.five_hour.resets_at == five_hour_reset
            assert usage.seven_day.utilization == seven_day_util
            assert usage.seven_day.resets_at == seven_day_reset
        assert usage.error == error

    def test_to_dict_without_error(self):
        """to_dict without error."""
        five_hour = UsagePeriod(utilization=40, resets_at="2024-01-15T15:00:00Z")
        seven_day = UsagePeriod(utilization=80, resets_at="2024-01-20T00:00:00Z")
        usage = Usage(five_hour=five_hour, seven_day=seven_day, updated=1234567890)
        result = usage.to_dict()

        assert result == {
            "five_hour": {"utilization": 40, "resets_at": "2024-01-15T15:00:00Z"},
            "seven_day": {"utilization": 80, "resets_at": "2024-01-20T00:00:00Z"},
            "updated": 1234567890,
        }
        assert "error" not in result

    def test_to_dict_with_error(self):
        """to_dict includes error when set."""
        usage = Usage(error="Connection failed", updated=1234567890)
        result = usage.to_dict()

        assert result["error"] == "Connection failed"
        assert result["updated"] == 1234567890
