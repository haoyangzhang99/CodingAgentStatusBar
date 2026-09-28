"""
Helper functions for OpenCode monitoring.

Small utility functions for message and todo processing.
"""

import time
from typing import Optional

from ..models import Tool


def extract_tools_from_messages(messages: Optional[list]) -> list[Tool]:
    """Extract running tools from message data.

    Also calculates elapsed_ms for permission detection heuristic.
    """
    tools: list[Tool] = []

    if not messages or not isinstance(messages, list) or len(messages) == 0:
        return tools

    now_ms = int(time.time() * 1000)
    parts = messages[0].get("parts", [])

    for part in parts:
        if part.get("type") == "tool":
            state = part.get("state", {})
            if state.get("status") == "running":
                tool_name = part.get("tool", "unknown")
                inp = state.get("input", {}) or {}

                # Extract argument based on tool type
                arg = (
                    state.get("title")
                    or inp.get("command")
                    or inp.get("filePath")
                    or inp.get("description")
                    or inp.get("pattern")
                    or (inp.get("prompt", "")[:50] if inp.get("prompt") else "")
                    or ""
                )

                # Calculate elapsed time for permission detection
                start_time = state.get("time", {}).get("start")
                elapsed_ms = 0
                if start_time is not None:
                    elapsed_ms = max(0, now_ms - start_time)

                tools.append(Tool(name=tool_name, arg=arg, elapsed_ms=elapsed_ms))

    return tools


def count_todos(todos: Optional[list]) -> tuple[int, int, str, str]:
    """Count pending and in_progress todos, return labels"""
    pending = 0
    in_progress = 0
    current_label = ""
    next_label = ""

    if not todos or not isinstance(todos, list):
        return pending, in_progress, current_label, next_label

    for todo in todos:
        status = todo.get("status", "")
        content = todo.get("content", "")
        if status == "pending":
            pending += 1
            if not next_label:  # First pending
                next_label = content
        elif status == "in_progress":
            in_progress += 1
            if not current_label:  # First in_progress
                current_label = content

    return pending, in_progress, current_label, next_label
