"""
Data models for OpenCode Status Bar
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import time


class SessionStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"


class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class Tool:
    """A tool being executed by an agent"""

    name: str
    arg: str = ""
    elapsed_ms: int = 0  # Time since tool started running (milliseconds)
    permission_pending: Optional[bool] = None

    # Tools that naturally take long and should not trigger permission detection
    EXCLUDED_TOOLS: frozenset[str] = frozenset({"task"})  # Sub-agents (immutable)

    @property
    def may_need_permission(self) -> bool:
        """Heuristic: tool running > threshold may be waiting for permission.

        Note: This is informational only, not 100% reliable.
        """
        if self.permission_pending is not None:
            return self.permission_pending

        from ..utils.settings import get_settings

        threshold_ms = get_settings().permission_threshold_seconds * 1000
        return (
            self.elapsed_ms > threshold_ms
            and self.name.lower() not in self.EXCLUDED_TOOLS
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "arg": self.arg,
            "elapsed_ms": self.elapsed_ms,
            "may_need_permission": self.may_need_permission,
        }


@dataclass
class AgentTodos:
    """Todo counters and labels for a single agent"""

    pending: int = 0
    in_progress: int = 0
    current_label: str = ""  # Label of in_progress todo
    next_label: str = ""  # Label of first pending todo

    def to_dict(self) -> dict:
        return {
            "pending": self.pending,
            "in_progress": self.in_progress,
            "current_label": self.current_label,
            "next_label": self.next_label,
        }

    @property
    def total(self) -> int:
        return self.pending + self.in_progress


@dataclass
class Agent:
    """A session/agent within an OpenCode instance"""

    id: str
    title: str
    dir: str  # Short directory name
    full_dir: str  # Full path
    status: SessionStatus
    tools: list[Tool] = field(default_factory=list)
    todos: AgentTodos = field(default_factory=AgentTodos)
    parent_id: Optional[str] = None  # ID of parent session (for sub-agents)
    has_pending_ask_user: bool = False  # MCP Notify ask_user awaiting response
    ask_user_title: str = ""  # Title of the pending ask_user question
    ask_user_question: str = ""  # Full question text
    ask_user_options: list[str] = field(default_factory=list)  # Response options
    ask_user_repo: str = ""  # Repository name
    ask_user_agent: str = ""  # Agent name from notification
    ask_user_branch: str = ""  # Branch name
    ask_user_urgency: str = "normal"  # Urgency level (normal/high)

    @property
    def is_subagent(self) -> bool:
        """Check if this is a sub-agent (has a parent)"""
        return self.parent_id is not None

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "title": self.title,
            "dir": self.dir,
            "full_dir": self.full_dir,
            "status": self.status.value,
            "tools": [t.to_dict() for t in self.tools],
            "todos": self.todos.to_dict(),
            "has_pending_ask_user": self.has_pending_ask_user,
            "ask_user_title": self.ask_user_title,
            "ask_user_question": self.ask_user_question,
            "ask_user_options": self.ask_user_options,
            "ask_user_repo": self.ask_user_repo,
            "ask_user_agent": self.ask_user_agent,
            "ask_user_branch": self.ask_user_branch,
            "ask_user_urgency": self.ask_user_urgency,
        }
        if self.parent_id:
            result["parent_id"] = self.parent_id
        return result


@dataclass
class Instance:
    """An OpenCode instance running on a specific port"""

    port: int
    tty: str = ""
    agents: list[Agent] = field(default_factory=list)

    @property
    def agent_count(self) -> int:
        return len(self.agents)

    @property
    def busy_count(self) -> int:
        return sum(1 for a in self.agents if a.status == SessionStatus.BUSY)

    @property
    def idle_count(self) -> int:
        return sum(1 for a in self.agents if a.status == SessionStatus.IDLE)

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "tty": self.tty,
            "agents": [a.to_dict() for a in self.agents],
            "agent_count": self.agent_count,
            "busy_count": self.busy_count,
            "idle_count": self.idle_count,
        }


@dataclass
class Todos:
    """Todo counters"""

    pending: int = 0
    in_progress: int = 0

    def to_dict(self) -> dict:
        return {"pending": self.pending, "in_progress": self.in_progress}


@dataclass
class State:
    """Complete state for menu bar consumption"""

    instances: list[Instance] = field(default_factory=list)
    todos: Todos = field(default_factory=Todos)
    updated: int = field(default_factory=lambda: int(time.time()))
    connected: bool = False

    @property
    def instance_count(self) -> int:
        return len(self.instances)

    @property
    def agent_count(self) -> int:
        return sum(i.agent_count for i in self.instances)

    @property
    def busy_count(self) -> int:
        return sum(i.busy_count for i in self.instances)

    @property
    def idle_count(self) -> int:
        return sum(i.idle_count for i in self.instances)

    @property
    def has_pending_ask_user(self) -> bool:
        """Check if any agent has a pending ask_user"""
        return any(
            agent.has_pending_ask_user
            for instance in self.instances
            for agent in instance.agents
        )

    def to_dict(self) -> dict:
        return {
            "instances": [i.to_dict() for i in self.instances],
            "instance_count": self.instance_count,
            "agent_count": self.agent_count,
            "busy_count": self.busy_count,
            "idle_count": self.idle_count,
            "has_pending_ask_user": self.has_pending_ask_user,
            "todos": self.todos.to_dict(),
            "updated": self.updated,
            "connected": self.connected,
        }


@dataclass
class UsagePeriod:
    """Usage data for a time period"""

    utilization: int = 0  # Percentage 0-100
    resets_at: Optional[str] = None  # ISO datetime

    def to_dict(self) -> dict:
        return {"utilization": self.utilization, "resets_at": self.resets_at}


@dataclass
class Usage:
    """Anthropic API usage data"""

    five_hour: UsagePeriod = field(default_factory=UsagePeriod)
    seven_day: UsagePeriod = field(default_factory=UsagePeriod)
    error: Optional[str] = None
    updated: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict:
        result = {
            "five_hour": self.five_hour.to_dict(),
            "seven_day": self.seven_day.to_dict(),
            "updated": self.updated,
        }
        if self.error:
            result["error"] = self.error
        return result
