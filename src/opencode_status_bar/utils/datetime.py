"""Datetime utilities for timestamp conversion."""

from datetime import datetime
from typing import Optional


def ms_to_datetime(timestamp_ms: Optional[int]) -> Optional[datetime]:
    """Convert milliseconds timestamp to datetime.

    Args:
        timestamp_ms: Unix timestamp in milliseconds, or None

    Returns:
        datetime object or None if input is None/0
    """
    if not timestamp_ms:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000)
