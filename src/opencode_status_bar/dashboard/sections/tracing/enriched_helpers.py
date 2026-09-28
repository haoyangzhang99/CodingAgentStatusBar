"""
Helper functions for enriched tracing data.

Provides utilities for formatting and displaying enriched tool data,
agent information, cost, and tokens.
"""

import json
from typing import Optional

from opencode_status_bar.dashboard.styles import AGENT_COLORS


def get_tool_display_label(tool_data: dict) -> str:
    """Get primary label for tool display.

    Priority: title > task args (subagent: description) > formatted tool_name > 'Unknown'

    Args:
        tool_data: Tool dict with 'title', 'tool_name', 'arguments' fields

    Returns:
        Human-readable label string
    """
    title = tool_data.get("title")
    if title:
        return title

    tool_name = tool_data.get("tool_name")

    if tool_name == "task":
        arguments = tool_data.get("arguments")
        if arguments:
            args = None
            if isinstance(arguments, dict):
                args = arguments
            elif isinstance(arguments, str):
                try:
                    args = json.loads(arguments)
                except json.JSONDecodeError:
                    pass
            if args:
                subagent = args.get("subagent_type", "")
                description = args.get("description", "")
                if subagent and description:
                    return f"{subagent}: {description}"
                elif description:
                    return description
                elif subagent:
                    return subagent

    if tool_name:
        return tool_name.replace("_", " ").title()

    return "Unknown"


def format_result_tooltip(tool_data: dict) -> str:
    """Format rich tooltip content for tool result.

    Includes: result_summary, cost, tokens

    Format:
        Result: File read successfully (245 lines)
        ---
        Cost: $0.0012  |  Tokens: 1.2K in / 500 out

    Args:
        tool_data: Tool dict with enriched fields

    Returns:
        Formatted tooltip string or empty string if no enriched data
    """
    parts = []

    # Result summary
    result_summary = tool_data.get("result_summary")
    if result_summary:
        # Truncate if too long
        if len(result_summary) > 150:
            summary = result_summary[:147] + "..."
        else:
            summary = result_summary
        parts.append(f"Result: {summary}")

    # Cost and tokens line
    metrics = []

    cost = tool_data.get("cost")
    if cost is not None:
        metrics.append(f"Cost: {format_cost(cost)}")

    tokens_in = tool_data.get("tokens_in")
    tokens_out = tool_data.get("tokens_out")
    if tokens_in or tokens_out:
        tokens_str = f"{format_tokens_short(tokens_in)} in"
        if tokens_out:
            tokens_str += f" / {format_tokens_short(tokens_out)} out"
        metrics.append(f"Tokens: {tokens_str}")

    if metrics:
        if parts:
            parts.append("-" * 30)
        parts.append("  |  ".join(metrics))

    return "\n".join(parts) if parts else ""


def get_agent_color(agent_type: str) -> tuple[str, str]:
    """Get text and background colors for agent type.

    Args:
        agent_type: Agent type string (main, executor, tea, etc.)

    Returns:
        Tuple of (text_color, bg_color) hex strings
    """
    normalized = agent_type.lower() if agent_type else "default"
    return AGENT_COLORS.get(normalized, AGENT_COLORS["default"])


def format_cost(cost: Optional[float]) -> str:
    """Format cost value for display.

    Rules:
    - None: Returns "-"
    - < $0.01: Show 4 decimals ($0.0010)
    - < $1.00: Show 3 decimals ($0.050)
    - >= $1.00: Show 2 decimals ($1.50)

    Args:
        cost: Cost in dollars or None

    Returns:
        Formatted cost string
    """
    if cost is None:
        return "-"
    if cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1.0:
        return f"${cost:.3f}"
    else:
        return f"${cost:.2f}"


def format_tokens_short(tokens: Optional[int]) -> str:
    """Format token count with K/M suffixes.

    Args:
        tokens: Token count or None

    Returns:
        Formatted string (e.g., "1.2K", "500", "-")
    """
    if tokens is None:
        return "-"
    if tokens == 0:
        return "0"
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1_000_000:
        return f"{tokens / 1000:.1f}K"
    else:
        return f"{tokens / 1_000_000:.1f}M"


def build_tool_tooltip(tool_data: dict) -> str:
    """Build rich tooltip for tool with result_summary, cost, tokens.

    Alias for format_result_tooltip for consistency with architecture doc.

    Args:
        tool_data: Tool dict with enriched fields

    Returns:
        Formatted tooltip string
    """
    return format_result_tooltip(tool_data)
