"""
Tree formatters - Pure functions for formatting tree node display data.

Extracted from TreeNode to separate display logic from tree structure.
"""

from typing import Any, Optional

from PyQt6.QtGui import QColor

from opencode_status_bar.dashboard.styles import COLORS

from .enriched_helpers import get_tool_display_label, build_tool_tooltip
from .helpers import format_duration, format_tokens_short
from .tree_utils import (
    format_time,
    get_project_name,
    get_delegation_icon,
    TREE_TOOL_ICONS,
)


def get_display_text(data: dict, column: int) -> str:
    node_type = data.get("node_type", "session")
    if column == 0:
        return _get_name_text(data, node_type)
    elif column == 1:
        return _get_time_text(data)
    elif column == 2:
        return _get_duration_text(data)
    elif column == 3:
        return _get_tokens_in_text(data)
    elif column == 4:
        return _get_tokens_out_text(data)
    elif column == 5:
        return _get_status_text(data, node_type)
    return ""


def _get_name_text(data: dict, node_type: str) -> str:
    if node_type == "session":
        directory = data.get("directory")
        title = data.get("title", "")
        project = get_project_name(directory)
        if title:
            return f"🌳 {project}: {title}"
        return f"🌳 {project}"

    elif node_type in ("user_turn", "conversation", "exchange"):
        if "user" in data:
            user_msg = data.get("user", {})
            assistant_msg = data.get("assistant", {})
            prompt_input = user_msg.get("content", "")
            agent = assistant_msg.get("agent", "assistant")
        else:
            prompt_input = data.get("prompt_input", "")
            agent = data.get("agent") or data.get("subagent_type", "assistant")

        if agent == "compaction":
            icon = "📦"
        else:
            icon = "💬"

        if prompt_input:
            preview = prompt_input[:60].replace("\n", " ")
            if len(prompt_input) > 60:
                preview += "..."
            return f'{icon} user → {agent}: "{preview}"'
        return f"{icon} user → {agent}"

    elif node_type in ("agent", "delegation"):
        agent_type = data.get("subagent_type") or data.get("agent_type", "agent")
        parent_agent = data.get("parent_agent", "")
        depth = data.get("depth", 0)
        icon = get_delegation_icon(depth, parent_agent)

        if parent_agent:
            return f"{icon} {parent_agent} → {agent_type}"
        return f"{icon} {agent_type}"

    elif node_type in ("part", "tool"):
        tool_name = data.get("tool_name", "")
        part_type = data.get("type", "")
        display_info = data.get("display_info", "")
        content = data.get("content", "")

        if tool_name:
            icon = TREE_TOOL_ICONS.get(tool_name, "⚙️")
            display_label = get_tool_display_label(data)
            if display_info:
                info_preview = (
                    display_info[:50] + "..."
                    if len(display_info) > 50
                    else display_info
                )
                info_preview = info_preview.replace("\n", " ")
                return f"  {icon} {display_label}: {info_preview}"
            return f"  {icon} {display_label}"
        elif part_type == "text":
            icon = "💭"
            text_preview = content[:60] + "..." if len(content) > 60 else content
            text_preview = text_preview.replace("\n", " ")
            return f"  {icon} {text_preview}" if text_preview else f"  {icon} (text)"
        return f"  ○ {part_type}"

    return ""


def _get_time_text(data: dict) -> str:
    created_at = data.get("created_at") or data.get("started_at") or ""
    if created_at:
        return format_time(created_at)
    return ""


def _get_duration_text(data: dict) -> str:
    duration_ms = data.get("duration_ms", 0)
    if duration_ms:
        return format_duration(duration_ms)
    return "-"


def _get_tokens_in_text(data: dict) -> str:
    tokens_in = data.get("tokens_in", 0)
    if tokens_in:
        return format_tokens_short(tokens_in)
    return "-"


def _get_tokens_out_text(data: dict) -> str:
    tokens_out = data.get("tokens_out", 0)
    if tokens_out:
        return format_tokens_short(tokens_out)
    return "-"


def _get_status_text(data: dict, node_type: str) -> str:
    if node_type in ("part", "tool"):
        status = data.get("status") or data.get("tool_status", "completed")
        if status == "completed":
            return "✓"
        elif status == "error":
            return "✗"
        elif status == "running":
            return "◐"
    return ""


def get_foreground_color(data: dict, column: int) -> QColor:
    node_type = data.get("node_type", "session")

    if column == 0:
        if node_type == "session":
            return QColor(COLORS["tree_root"])
        elif node_type in ("user_turn", "conversation", "exchange"):
            agent = data.get("agent", "")
            if agent == "compaction":
                return QColor(COLORS.get("text_secondary", "#9CA3AF"))
            return QColor(COLORS.get("text_primary", "#E5E7EB"))
        elif node_type == "agent":
            return QColor(COLORS.get("accent_primary", "#3B82F6"))
        elif node_type in ("part", "tool"):
            status = data.get("status") or data.get("tool_status", "completed")
            tool_name = data.get("tool_name", "")
            if status == "error":
                return QColor(COLORS["error"])
            elif tool_name:
                return QColor(COLORS["text_secondary"])
            return QColor(COLORS["text_muted"])
    elif column == 1:
        return QColor(COLORS["text_secondary"])
    elif column == 5:
        if node_type in ("part", "tool"):
            status = data.get("status") or data.get("tool_status", "completed")
            if status == "completed":
                return QColor(COLORS["success"])
            elif status == "error":
                return QColor(COLORS["error"])
            elif status == "running":
                return QColor(COLORS["warning"])

    return QColor(COLORS["text_muted"])


def get_tooltip(data: dict, column: int) -> Optional[str]:
    node_type = data.get("node_type", "session")

    if column == 0:
        if node_type in ("user_turn", "conversation", "exchange"):
            prompt_input = data.get("prompt_input", "")
            if not prompt_input and "user" in data:
                prompt_input = data["user"].get("content", "")
            if prompt_input:
                tooltip = f"User:\n{prompt_input[:500]}"
                if len(prompt_input) > 500:
                    tooltip += "..."
                return tooltip
        elif node_type in ("part", "tool"):
            tool_name = data.get("tool_name", "")
            if tool_name:
                return build_tool_tooltip(data)
    return None
