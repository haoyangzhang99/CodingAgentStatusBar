"""
Panel strategy types - Data structures for panel content.
"""

from typing import TypedDict, Literal
from dataclasses import dataclass


class TranscriptData(TypedDict, total=False):
    user_content: str
    assistant_content: str


class DelegationData(TypedDict, total=False):
    """Data for delegation span panel."""

    child_session_id: str | None
    subagent_type: str | None
    status: str
    duration_ms: int
    display_info: str
    tool_name: str


class PanelContent(TypedDict, total=False):
    breadcrumb: list[str]
    content_type: Literal["overview", "tabs", "delegation_transcript"]
    overview_data: dict | None
    transcript: TranscriptData | None
    available_tabs: list[int]
    initial_tab: int
    delegation_data: DelegationData | None


@dataclass
class TreeNodeData:
    raw: dict

    @property
    def node_type(self) -> str:
        return self.raw.get("node_type", "session")

    @property
    def session_id(self) -> str | None:
        return self.raw.get("session_id")

    @property
    def children(self) -> list[dict]:
        return self.raw.get("children", [])

    @property
    def is_root(self) -> bool:
        # Priority 1: Use explicit flag set by tree_builder
        if self.raw.get("_is_tree_root"):
            return True

        # Priority 2: Fallback to heuristic based on agent_type/parent_agent
        agent_type = self.raw.get("agent_type")
        parent_agent = self.raw.get("parent_agent")
        # Root = pas de parent ET (pas d'agent_type OU agent_type="user")
        return parent_agent is None and (agent_type is None or agent_type == "user")

    @property
    def agent_type(self) -> str | None:
        return self.raw.get("agent_type")

    @property
    def parent_agent(self) -> str | None:
        return self.raw.get("parent_agent")

    @property
    def title(self) -> str:
        return self.raw.get("title", "")

    @property
    def status(self) -> str:
        return self.raw.get("status", "completed")

    @property
    def duration_ms(self) -> int:
        return self.raw.get("duration_ms") or self.raw.get("total_duration_ms", 0)

    @property
    def tokens_in(self) -> int:
        return self.raw.get("tokens_in", 0)

    @property
    def tokens_out(self) -> int:
        return self.raw.get("tokens_out", 0)

    @property
    def directory(self) -> str:
        return self.raw.get("directory", "")

    @property
    def prompt_input(self) -> str | None:
        return self.raw.get("prompt_input")

    @property
    def prompt_output(self) -> str | None:
        return self.raw.get("prompt_output")

    @property
    def tool_name(self) -> str:
        return self.raw.get("tool_name", "")

    @property
    def display_info(self) -> str:
        return self.raw.get("display_info", "")

    @property
    def content(self) -> str:
        return self.raw.get("content", "")

    @property
    def created_at(self) -> str | None:
        return self.raw.get("created_at")

    def get(self, key: str, default=None):
        return self.raw.get(key, default)
