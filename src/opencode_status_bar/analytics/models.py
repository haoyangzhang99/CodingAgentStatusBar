"""
Analytics data models.

All dataclasses for analytics metrics and statistics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TokenStats:
    """Token usage statistics."""

    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0

    @property
    def total(self) -> int:
        """Total tokens (input + output + reasoning)."""
        return self.input + self.output + self.reasoning

    @property
    def total_with_cache(self) -> int:
        """Total including cache operations."""
        return self.total + self.cache_read + self.cache_write

    @property
    def total_input_with_cache(self) -> int:
        """Total input including cache read."""
        return self.input + self.cache_read

    @property
    def cache_hit_ratio(self) -> float:
        """Cache hit ratio (cache_read / total_input_with_cache)."""
        total = self.total_input_with_cache
        if total == 0:
            return 0.0
        return (self.cache_read / total) * 100

    @property
    def input_saved_by_cache(self) -> int:
        """Tokens saved by cache (cache_read tokens that didn't need to be sent)."""
        return self.cache_read


@dataclass
class AgentStats:
    """Statistics for a specific agent."""

    agent: str
    message_count: int
    tokens: TokenStats


@dataclass
class ToolStats:
    """Statistics for a specific tool."""

    tool_name: str
    invocations: int
    failures: int

    @property
    def failure_rate(self) -> float:
        """Failure rate as percentage."""
        if self.invocations == 0:
            return 0.0
        return (self.failures / self.invocations) * 100


@dataclass
class SkillStats:
    """Statistics for skill usage."""

    skill_name: str
    load_count: int


@dataclass
class SessionStats:
    """Statistics for a session."""

    session_id: str
    title: str
    tokens: TokenStats
    message_count: int
    duration_minutes: int


@dataclass
class HourlyStats:
    """Usage by hour of day."""

    hour: int
    message_count: int
    tokens: int


@dataclass
class AgentChain:
    """Agent call chain statistics."""

    chain: str  # e.g., "executor -> tester -> quality"
    occurrences: int
    depth: int


@dataclass
class SessionTokenStats:
    """Token statistics across sessions."""

    avg_tokens: int
    max_tokens: int
    min_tokens: int
    median_tokens: int
    total_sessions: int


@dataclass
class DelegationPattern:
    """Detailed delegation pattern between two agents."""

    parent: str
    child: str
    count: int
    percentage: float  # of total delegations
    tokens_total: int  # Total tokens used in this pattern
    tokens_avg: int  # Average tokens per occurrence


@dataclass
class AgentRole:
    """Agent classification based on delegation behavior."""

    agent: str
    role: str  # "orchestrator", "hub", "worker"
    delegations_sent: int
    delegations_received: int
    fan_out: float  # sent / received ratio
    tokens_total: int
    tokens_per_task: int  # tokens / tasks received


@dataclass
class DelegationMetrics:
    """Overall delegation metrics."""

    total_delegations: int
    sessions_with_delegations: int
    unique_patterns: int
    recursive_delegations: int
    recursive_percentage: float
    max_depth: int
    avg_per_session: float


@dataclass
class HourlyDelegations:
    """Delegations by hour of day."""

    hour: int
    count: int


@dataclass
class DailyStats:
    """Daily activity statistics."""

    date: datetime
    sessions: int
    messages: int
    tokens: int
    delegations: int


@dataclass
class SkillByAgent:
    """Skill usage per agent."""

    agent: str
    skill_name: str
    count: int


@dataclass
class DelegationSession:
    """A session with multiple delegations."""

    agent: str
    session_id: str
    delegation_count: int
    sequence: str  # e.g., "tester -> quality -> roadmap"


@dataclass
class AgentDelegationStats:
    """Delegation statistics per agent."""

    agent: str
    sessions_with_delegations: int
    total_delegations: int
    avg_per_session: float
    max_per_session: int


@dataclass
class DirectoryStats:
    """Statistics per working directory."""

    directory: str
    sessions: int
    tokens: int


@dataclass
class Todo:
    """A todo item from a session."""

    id: str
    session_id: str
    content: str
    status: str  # pending, in_progress, completed, cancelled
    priority: str  # high, medium, low
    position: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Project:
    """An OpenCode project."""

    id: str
    worktree: str
    vcs: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class TodoStats:
    """Todo statistics for a period."""

    total: int
    completed: int
    in_progress: int
    pending: int
    cancelled: int
    completion_rate: float  # percentage


@dataclass
class ProjectStats:
    """Statistics for a project."""

    project_id: str
    worktree: str
    sessions: int
    tokens: int
    todos_total: int
    todos_completed: int


@dataclass
class AgentTrace:
    """Trace of an agent invocation via task tool.

    Captures the full execution context of a delegated task,
    including prompts, timing, and nested tool usage.
    """

    trace_id: str  # UUID generated
    session_id: str
    parent_trace_id: Optional[str] = None
    parent_agent: Optional[str] = None
    subagent_type: str = ""
    prompt_input: str = ""  # Full prompt (not truncated)
    prompt_output: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    status: str = "running"  # running, completed, error
    tools_used: list[str] = field(default_factory=list)
    child_session_id: Optional[str] = None  # Session created for the subtask


@dataclass
class ModelStats:
    """Statistics per model."""

    model_id: str
    provider_id: str
    messages: int
    tokens: int
    percentage: float  # of total tokens


@dataclass
class PeriodStats:
    """Complete statistics for a time period."""

    start_date: datetime
    end_date: datetime
    session_count: int
    message_count: int
    tokens: TokenStats
    agents: list[AgentStats] = field(default_factory=list)
    tools: list[ToolStats] = field(default_factory=list)
    skills: list[SkillStats] = field(default_factory=list)
    top_sessions: list[SessionStats] = field(default_factory=list)
    hourly_usage: list[HourlyStats] = field(default_factory=list)
    agent_chains: list[AgentChain] = field(default_factory=list)
    avg_session_duration_min: float = 0.0
    anomalies: list[str] = field(default_factory=list)
    # Advanced delegation stats
    delegation_metrics: Optional[DelegationMetrics] = None
    delegation_patterns: list[DelegationPattern] = field(default_factory=list)
    agent_roles: list[AgentRole] = field(default_factory=list)
    hourly_delegations: list[HourlyDelegations] = field(default_factory=list)
    # Time series
    daily_stats: list[DailyStats] = field(default_factory=list)
    # Session token stats
    session_token_stats: Optional[SessionTokenStats] = None
    # New dimension metrics
    directories: list[DirectoryStats] = field(default_factory=list)
    models: list[ModelStats] = field(default_factory=list)
    # Skills and delegation analysis
    skills_by_agent: list[SkillByAgent] = field(default_factory=list)
    delegation_sessions: list[DelegationSession] = field(default_factory=list)
    agent_delegation_stats: list[AgentDelegationStats] = field(default_factory=list)
