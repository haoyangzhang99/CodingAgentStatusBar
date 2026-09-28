"""
Tree utility functions for tracing section.

Pure functions for formatting and extracting data from session nodes.
"""

import os
import re
from typing import Optional


# Regex patterns for agent extraction
AGENT_PATTERN = re.compile(r"\[([^\]]+)\]")
AGENT_SUFFIX_PATTERN = re.compile(r"\s*\[[^\]]+\]\s*$")


def format_time(dt) -> str:
    """Format datetime to MM-DD HH:MM for consistent Time column.

    Args:
        dt: Datetime string in ISO format or None

    Returns:
        Formatted time string like "01-04 08:21" or "-" if None
    """
    if not dt:
        return "-"
    if isinstance(dt, str):
        # Extract MM-DD HH:MM from ISO string (e.g., "2026-01-04T08:21:30")
        if "T" in dt:
            # "2026-01-04T08:21:30" -> "01-04 08:21"
            date_part = dt[5:10]  # MM-DD
            time_part = dt.split("T")[1][:5]  # HH:MM
            return f"{date_part} {time_part}"
        elif len(dt) > 10:
            # "2026-01-04 08:21:30" -> "01-04 08:21"
            return f"{dt[5:10]} {dt[11:16]}"
        return dt
    return dt.strftime("%m-%d %H:%M")


def get_project_name(directory: Optional[str]) -> str:
    """Extract project name from directory path.

    Args:
        directory: Full directory path

    Returns:
        Base name of directory or "Unknown" if None
    """
    if not directory:
        return "Unknown"
    return os.path.basename(directory.rstrip("/"))


def extract_agent_from_title(title: Optional[str]) -> Optional[str]:
    """Extract agent name from title with [agent] suffix.

    Args:
        title: Title string potentially containing [agent] suffix

    Returns:
        Agent name if found, None otherwise
    """
    if not title:
        return None
    match = AGENT_PATTERN.search(title)
    if match:
        return match.group(1)
    return None


def get_delegation_icon(depth: int, parent_agent: Optional[str]) -> str:
    """Get icon for delegation based on depth and parent.

    Args:
        depth: Nesting depth in the tree
        parent_agent: Name of parent agent

    Returns:
        💬 for user-initiated (depth 1, parent is user)
        🔗 for agent delegations (depth 1, parent is agent)
        └─ for nested delegations (depth > 1)
    """
    if depth == 1:
        return "💬" if parent_agent == "user" else "🔗"
    return "└─"


# Tool icons mapping
TOOL_ICONS = {
    "bash": "🔧",
    "read": "📖",
    "write": "📝",
    "edit": "✏️",
    "glob": "🔍",
    "grep": "🔎",
    "task": "📨",
    "webfetch": "🌐",
    "web_fetch": "🌐",
    "todowrite": "📋",
    "todoread": "📋",
    "skill": "📚",
    "notify_ask_user": "❓",
    "notify_notify_commit": "📦",
    "notify_notify_merge": "🔀",
}

# Extended tool icons for tree building (includes 'task' as robot)
TREE_TOOL_ICONS = {
    "read": "📖",
    "edit": "✏️",
    "write": "📝",
    "bash": "🔧",
    "glob": "🔍",
    "grep": "🔎",
    "task": "🤖",
    "webfetch": "🌐",
    "web_fetch": "🌐",
    "todowrite": "📋",
    "todoread": "📋",
}


def get_tool_icon(tool_name: str, for_tree: bool = False) -> str:
    """Get icon for a tool.

    Args:
        tool_name: Name of the tool
        for_tree: Use tree icons (task = 🤖) instead of default

    Returns:
        Icon string for the tool
    """
    icons = TREE_TOOL_ICONS if for_tree else TOOL_ICONS
    return icons.get(tool_name, "⚙️")
