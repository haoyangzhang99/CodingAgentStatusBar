"""
Dashboard utility functions for formatting display values.
"""


def format_tokens(count: int) -> str:
    """Format token count for display (e.g., 1500000 -> '1.5M').

    Args:
        count: Raw token count

    Returns:
        Formatted string with K/M suffix
    """
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.0f}K"
    return str(count)


def format_duration_ms(elapsed_ms: int) -> str:
    """Format duration in milliseconds for display.

    Args:
        elapsed_ms: Duration in milliseconds

    Returns:
        Human-readable duration string (e.g., '2m 30s', '5s', '250ms')
    """
    if elapsed_ms >= 60000:
        return f"{elapsed_ms // 60000}m {(elapsed_ms % 60000) // 1000}s"
    elif elapsed_ms >= 1000:
        return f"{elapsed_ms // 1000}s"
    return f"{elapsed_ms}ms"
