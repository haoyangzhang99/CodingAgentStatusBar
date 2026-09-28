"""
Delegation span strategy - Handle delegation (task tool) spans.
"""

import json

from .types import PanelContent, TreeNodeData, DelegationData


class DelegationSpanStrategy:
    """Strategy for delegation spans (task tool calls with child_session_id)."""

    @staticmethod
    def handles() -> list[str]:
        return ["delegation_span"]

    def get_content(self, node: TreeNodeData) -> PanelContent:
        child_session_id = node.raw.get("child_session_id")
        subagent_type = (
            node.raw.get("subagent_type")
            or node.agent_type
            or self._extract_subagent_type(node)
        )
        tool_name = node.tool_name or "task"

        status = node.status
        duration_ms = node.duration_ms
        display_info = node.display_info or node.title

        breadcrumb: list[str] = ["🤖 Delegation"]
        if subagent_type:
            breadcrumb.append(f"→ {subagent_type}")

        delegation_data: DelegationData = {
            "child_session_id": child_session_id,
            "subagent_type": subagent_type,
            "status": status,
            "duration_ms": duration_ms,
            "display_info": display_info,
            "tool_name": tool_name,
        }

        return PanelContent(
            breadcrumb=breadcrumb,
            content_type="delegation_transcript",
            overview_data=None,
            transcript=None,
            available_tabs=[],
            initial_tab=0,
            delegation_data=delegation_data,
        )

    def _extract_subagent_type(self, node: TreeNodeData) -> str | None:
        arguments = node.raw.get("arguments", "")
        if arguments and isinstance(arguments, str):
            try:
                args = json.loads(arguments)
                return args.get("subagent_type")
            except (json.JSONDecodeError, TypeError):
                pass

        input_data = node.raw.get("input", {})
        if isinstance(input_data, dict):
            subagent = input_data.get("subagent_type")
            if subagent:
                return subagent

        display_info = node.display_info
        if display_info and "→" in display_info:
            return display_info.split("→")[-1].strip()

        return None


def is_delegation_span(node: TreeNodeData) -> bool:
    """Check if a node represents a delegation span (agent with child_session_id)."""
    node_type = node.node_type

    if node_type == "agent":
        child_session_id = node.raw.get("child_session_id")
        return bool(child_session_id)

    if node_type in ("part", "tool"):
        tool_name = node.tool_name
        if tool_name == "task":
            child_session_id = node.raw.get("child_session_id")
            return bool(child_session_id)

    return False
