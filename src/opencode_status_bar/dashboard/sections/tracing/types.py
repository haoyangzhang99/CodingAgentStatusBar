"""
TypedDict definitions for enriched tracing data.

These types define the structure of enriched data from the API,
making it easier to work with tool results, message data, and timeline events.
"""

from typing import TypedDict, Optional, Literal


class ErrorInfo(TypedDict, total=False):
    """Error information for failed operations."""

    name: str  # Error class name (e.g., "FileNotFoundError")
    data: str  # Error message/details
    path: Optional[str]  # Related file path if applicable


class EnrichedToolData(TypedDict, total=False):
    """Enriched tool/part data from API."""

    # Existing fields
    id: str
    tool_name: str
    status: Literal["completed", "error", "running"]
    display_info: str
    created_at: str
    duration_ms: Optional[int]

    # Enriched fields (Plan 45)
    title: Optional[str]  # Human-readable operation title
    result_summary: Optional[str]  # Summary of result
    cost: Optional[float]  # Operation cost in dollars
    tokens_in: Optional[int]  # Input tokens
    tokens_out: Optional[int]  # Output tokens


class EnrichedMessageData(TypedDict, total=False):
    """Enriched message data from API."""

    # Existing fields
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str

    # Enriched fields
    agent: Optional[str]  # Agent type (main, executor, tea, etc.)
    summary_title: Optional[str]  # Auto-generated conversation summary
    root_path: Optional[str]  # Project root path
    error: Optional[ErrorInfo]  # Error info if operation failed


class EnrichedSessionData(TypedDict, total=False):
    """Enriched session data from API."""

    session_id: str
    title: str
    directory: str
    started_at: str
    ended_at: Optional[str]

    # Enriched fields
    summary_title: Optional[str]  # From first user message


class EnrichedTimelineEvent(TypedDict, total=False):
    """Timeline event with enriched data."""

    type: str
    timestamp: str
    duration_ms: Optional[int]

    # For tool events
    tool_name: Optional[str]
    status: Optional[str]
    title: Optional[str]  # Human-readable title
    result_summary: Optional[str]  # Result summary for tooltip

    # For message events
    agent: Optional[str]  # Agent badge
    error: Optional[ErrorInfo]  # Error indicator

    # For file events
    file_url: Optional[str]  # Base64 data URL


class FileAttachmentInfo(TypedDict):
    """Parsed file attachment information."""

    filename: str
    mime_type: str
    size_bytes: int
    width: Optional[int]  # For images
    height: Optional[int]  # For images
    data_url: str  # Full base64 data URL


# Type alias for agent types
AgentType = Literal[
    "main", "executor", "tea", "subagent", "coder", "analyst", "unknown"
]
