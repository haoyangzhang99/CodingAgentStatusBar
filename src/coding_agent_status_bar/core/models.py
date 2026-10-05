"""Data models for Coding Agent Status Bar, filled in from the OpenCode plugin's snapshots and
the Codex and Claude Code hooks' status files."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SessionStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"


@dataclass
class Tool:
    """A pending tool call. The plugin reports only approval requests."""

    name: str
    permission_pending: bool = False

    @property
    def may_need_permission(self) -> bool:
        return self.permission_pending


@dataclass
class Agent:
    """An OpenCode session (or sub-agent session)."""

    id: str
    title: str
    dir: str  # Short directory name
    full_dir: str  # Full path
    status: SessionStatus
    tools: list[Tool] = field(default_factory=list)
    parent_id: Optional[str] = None  # Parent session ID, for sub-agents
    has_pending_ask_user: bool = False  # OpenCode is waiting for an answer
    ask_user_title: str = ""

    @property
    def is_subagent(self) -> bool:
        return self.parent_id is not None


@dataclass
class Instance:
    """One running OpenCode process. `port` is the negated process ID."""

    port: int
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


@dataclass
class State:
    """Complete state for the menu bar."""

    instances: list[Instance] = field(default_factory=list)
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
        return any(a.has_pending_ask_user for i in self.instances for a in i.agents)


@dataclass
class HookState:
    """Codex or Claude Code status from their hooks. Sessions are recent ones, titled by
    project folder."""

    running: bool = False
    sessions: list[Agent] = field(default_factory=list)
