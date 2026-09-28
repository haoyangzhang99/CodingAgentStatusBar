"""
Helper functions for trace building.

Pure utility functions extracted from TraceBuilder for better testability.
"""

import json
from typing import Optional


def determine_status(tool_status: Optional[str]) -> str:
    """Determine trace status from tool status.

    Args:
        tool_status: Raw tool status string

    Returns:
        Normalized status (running/completed/error)
    """
    if not tool_status:
        return "running"

    status_lower = tool_status.lower()
    if status_lower in ("completed", "success"):
        return "completed"
    elif status_lower in ("error", "failed"):
        return "error"
    else:
        return "running"


def extract_prompt(arguments: Optional[str]) -> str:
    """Extract prompt from task tool arguments.

    Combines description and prompt fields for complete context.
    Format: "{description}\n\n{prompt}" if both exist.

    Args:
        arguments: JSON string of tool arguments

    Returns:
        Combined prompt text or empty string
    """
    if not arguments:
        return ""

    try:
        data = json.loads(arguments)
        prompt = data.get("prompt", "") or ""
        description = data.get("description", "") or ""

        # Combine description and prompt for full context
        if description and prompt:
            return f"{description}\n\n{prompt}"
        elif description:
            return description
        return prompt
    except (json.JSONDecodeError, TypeError):
        return ""
