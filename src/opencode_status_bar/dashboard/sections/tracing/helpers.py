"""
Tracing helpers - Utility functions and constants.
"""

import re
from typing import Optional

# Pre-compiled regex patterns
AGENT_PATTERN = re.compile(r"\(@(\w+)")  # Extract agent type from title
AGENT_SUFFIX_PATTERN = re.compile(r"\s*\(@\w+.*\)$")  # Remove agent suffix from title


def format_duration(ms: Optional[int]) -> str:
    """Format duration in milliseconds to human readable."""
    if ms is None:
        return "..."
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        return f"{minutes}m {seconds}s"


def format_tokens_short(tokens: Optional[int]) -> str:
    """Format tokens to short form like 1.2K."""
    if tokens is None:
        return "-"
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1000000:
        return f"{tokens / 1000:.1f}K"
    else:
        return f"{tokens / 1000000:.1f}M"
