# Plan 46: Architecture Document - Dashboard Enriched Data

## Overview

This document defines the technical architecture for integrating enriched data fields into the dashboard. It specifies data flow, component interfaces, widget designs, performance strategies, and implementation sequence.

**Key Principle**: Minimal API changes. The enriched fields already exist in the database (from Plan 45). We expose them through existing API responses and display them in the dashboard.

---

## 1. Data Flow Enhancement

### 1.1 Current Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────────┐   │
│  │  sessions   │  │  messages   │  │            parts                    │   │
│  │  - title    │  │  - agent    │  │  - title                            │   │
│  │  - directory│  │  - error    │  │  - result_summary                   │   │
│  │             │  │  - summary_ │  │  - cost                             │   │
│  │             │  │    title    │  │  - tokens_in/out                    │   │
│  │             │  │  - root_path│  │  - file_url (file parts)            │   │
│  └─────────────┘  └─────────────┘  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API Layer (routes/tracing/)                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────────┐  │
│  │ builders.py    │  │ fetchers.py    │  │ timeline_builder.py            │  │
│  │ - Session tree │  │ - SQL queries  │  │ - Timeline events              │  │
│  │ - Tool nodes   │  │ - Field select │  │                                │  │
│  └────────────────┘  └────────────────┘  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Dashboard (sections/tracing/)                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────────┐  │
│  │ tree_builder   │  │ timeline.py    │  │ detail_panel/                  │  │
│  │ - Session items│  │ - Event widgets│  │ - Session summary              │  │
│  │ - Tool items   │  │                │  │ - Tool details                 │  │
│  └────────────────┘  └────────────────┘  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 API Endpoints & Required Fields

| Endpoint | Current Fields | Fields to Add | Impact |
|----------|----------------|---------------|--------|
| `/api/tracing/tree` | tool_name, display_info, status | `title`, `result_summary` | Modify `build_tools_by_session()` |
| `/api/tracing/tree` | session.directory, session.title | `summary_title` from first message | New join in fetcher |
| `/api/session/{id}/timeline` | type, timestamp, duration | `agent`, `error`, `title`, `file_url` | Modify `build_timeline_events()` |
| `/api/session/{id}/tools` | All fields | Already includes `result_summary` | None |

### 1.3 SQL Changes Required

**1. Add `summary_title` to session tree (fetchers.py)**

```sql
-- Current query returns sessions without summary_title
-- Add LEFT JOIN to get first message's summary_title
SELECT s.*, 
       (SELECT m.summary_title 
        FROM messages m 
        WHERE m.session_id = s.id 
        ORDER BY m.created_at ASC 
        LIMIT 1) as summary_title
FROM sessions s
WHERE ...
```

**2. Add enriched fields to tool nodes (builders.py:build_tools_by_session)**

```sql
SELECT 
    id, session_id, tool_name, tool_status,
    arguments, created_at, duration_ms, result_summary,
    title,      -- ADD: Human-readable title
    cost,       -- ADD: Tool cost
    tokens_in,  -- ADD: Token usage
    tokens_out  -- ADD: Token usage
FROM parts
WHERE session_id IN (...)
  AND part_type = 'tool'
```

**3. Add fields to timeline events**

```sql
SELECT 
    p.id, p.part_type, p.created_at, p.duration_ms,
    p.tool_name, p.tool_status, p.arguments,
    p.title,          -- ADD
    p.result_summary, -- ADD
    m.agent,          -- ADD: From parent message
    m.error           -- ADD: Error object (JSON)
FROM parts p
LEFT JOIN messages m ON p.message_id = m.id
```

### 1.4 Enhanced Data Flow

```
Database ──► API (add fields) ──► DataLoader ──► Views (display enriched data)
                  │                    │              │
                  │                    │              └─ TimelineEventWidget
                  │                    │                   uses: title, agent, error
                  │                    │
                  │                    └─ TracingSection.update_data()
                  │                         passes: session_hierarchy
                  │
                  └─ Returns enriched JSON:
                      {
                        "tool_name": "bash",
                        "title": "Check git status",       // NEW
                        "result_summary": "3 files...",    // NEW
                        "agent": "executor",               // NEW
                        "error": {"name": "...", ...}      // NEW
                      }
```

---

## 2. Component Interfaces

### 2.1 TypedDict Definitions (Python Type Hints)

```python
# File: src/opencode_status_bar/dashboard/sections/tracing/types.py

from typing import TypedDict, Optional, Literal


class ErrorInfo(TypedDict, total=False):
    """Error information for failed operations."""
    name: str           # Error class name (e.g., "FileNotFoundError")
    data: str           # Error message/details
    path: Optional[str] # Related file path if applicable


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
    title: Optional[str]         # Human-readable operation title
    result_summary: Optional[str] # Summary of result
    cost: Optional[float]        # Operation cost in dollars
    tokens_in: Optional[int]     # Input tokens
    tokens_out: Optional[int]    # Output tokens


class EnrichedMessageData(TypedDict, total=False):
    """Enriched message data from API."""
    # Existing fields
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str
    
    # Enriched fields
    agent: Optional[str]          # Agent type (main, executor, tea, etc.)
    summary_title: Optional[str]  # Auto-generated conversation summary
    root_path: Optional[str]      # Project root path
    error: Optional[ErrorInfo]    # Error info if operation failed


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
    title: Optional[str]         # Human-readable title
    result_summary: Optional[str] # Result summary for tooltip
    
    # For message events
    agent: Optional[str]          # Agent badge
    error: Optional[ErrorInfo]    # Error indicator
    
    # For file events
    file_url: Optional[str]       # Base64 data URL


class FileAttachmentInfo(TypedDict):
    """Parsed file attachment information."""
    filename: str
    mime_type: str
    size_bytes: int
    width: Optional[int]   # For images
    height: Optional[int]  # For images
    data_url: str          # Full base64 data URL


AgentType = Literal["main", "executor", "tea", "subagent", "coder", "analyst", "unknown"]
```

### 2.2 Widget Interfaces

```python
# File: src/opencode_status_bar/dashboard/sections/tracing/widgets.py

from typing import Protocol, Optional
from PyQt6.QtWidgets import QWidget


class EnrichedDataConsumer(Protocol):
    """Protocol for widgets that consume enriched data."""
    
    def set_agent(self, agent_type: Optional[str]) -> None:
        """Set agent type for badge display."""
        ...
    
    def set_error(self, error_info: Optional[dict]) -> None:
        """Set error info for indicator display."""
        ...
    
    def set_tooltip_content(self, content: Optional[str]) -> None:
        """Set rich tooltip content."""
        ...


class ThumbnailProvider(Protocol):
    """Protocol for thumbnail providers (e.g., image cache)."""
    
    def get_thumbnail(
        self, 
        data_url: str, 
        size: tuple[int, int] = (48, 48)
    ) -> Optional["QPixmap"]:
        """Get cached thumbnail or None if not ready."""
        ...
    
    def request_thumbnail(
        self, 
        data_url: str, 
        callback: callable,
        size: tuple[int, int] = (48, 48)
    ) -> None:
        """Request async thumbnail generation."""
        ...
```

### 2.3 Helper Functions Interface

```python
# File: src/opencode_status_bar/dashboard/sections/tracing/enriched_helpers.py

from typing import Optional


def get_tool_display_label(tool_data: dict) -> str:
    """Get primary label for tool display.
    
    Priority: title > formatted tool_name
    
    Args:
        tool_data: Tool dict with 'title' and 'tool_name' fields
        
    Returns:
        Human-readable label string
    """
    ...


def format_result_tooltip(tool_data: dict) -> Optional[str]:
    """Format rich tooltip content for tool result.
    
    Includes: result_summary, cost, tokens
    
    Args:
        tool_data: Tool dict with enriched fields
        
    Returns:
        Formatted tooltip string or None
    """
    ...


def get_agent_color(agent_type: str) -> tuple[str, str]:
    """Get text and background colors for agent type.
    
    Args:
        agent_type: Agent type string (main, executor, tea, etc.)
        
    Returns:
        Tuple of (text_color, bg_color) hex strings
    """
    ...


def format_cost(cost: Optional[float]) -> str:
    """Format cost value for display.
    
    Rules:
    - < $0.01: Show 3 decimals ($0.001)
    - >= $0.01: Show 2 decimals ($0.01)
    """
    ...


def parse_file_attachment(file_url: str) -> Optional[dict]:
    """Parse base64 data URL to extract file info.
    
    Args:
        file_url: Data URL (data:image/png;base64,...)
        
    Returns:
        FileAttachmentInfo dict or None if invalid
    """
    ...
```

---

## 3. Widget Architecture

### 3.1 AgentBadge Widget

**Purpose**: Display agent type as a colored pill badge.

```python
# File: src/opencode_status_bar/dashboard/sections/tracing/widgets.py

from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt

from opencode_status_bar.dashboard.styles import COLORS, FONTS, RADIUS


# Agent color definitions (add to colors.py)
AGENT_COLORS = {
    "main": ("#3b82f6", "rgba(59, 130, 246, 0.15)"),      # Blue
    "executor": ("#22c55e", "rgba(34, 197, 94, 0.15)"),   # Green
    "tea": ("#f59e0b", "rgba(245, 158, 11, 0.15)"),       # Amber
    "subagent": ("#a855f7", "rgba(168, 85, 247, 0.15)"),  # Violet
    "coder": ("#22c55e", "rgba(34, 197, 94, 0.15)"),      # Green
    "analyst": ("#3b82f6", "rgba(59, 130, 246, 0.15)"),   # Blue
    "default": ("#6b7280", "rgba(107, 114, 128, 0.15)"),  # Gray
}


class AgentBadge(QLabel):
    """Pill badge showing agent type with color coding.
    
    Visual:
        ┌──────────┐
        │ executor │  ← Green pill with text
        └──────────┘
    
    Usage:
        badge = AgentBadge("executor")
        layout.addWidget(badge)
    """
    
    # Short labels for display
    AGENT_LABELS = {
        "main": "main",
        "executor": "exec",
        "tea": "tea",
        "subagent": "sub",
        "coder": "coder",
        "analyst": "analyst",
    }
    
    def __init__(self, agent_type: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._agent_type = ""
        self.set_agent(agent_type)
    
    def set_agent(self, agent_type: str) -> None:
        """Update displayed agent type."""
        if not agent_type:
            self.hide()
            return
        
        self._agent_type = agent_type.lower()
        
        # Get display label (shortened)
        label = self.AGENT_LABELS.get(self._agent_type, self._agent_type[:4])
        
        # Get colors
        text_color, bg_color = AGENT_COLORS.get(
            self._agent_type, 
            AGENT_COLORS["default"]
        )
        
        self.setText(label)
        self.setStyleSheet(f"""
            QLabel {{
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_medium"]};
                padding: 2px 6px;
                border-radius: {RADIUS["full"]}px;
                background-color: {bg_color};
                color: {text_color};
            }}
        """)
        self.setToolTip(f"Agent: {agent_type}")
        self.show()
    
    def agent_type(self) -> str:
        """Return current agent type."""
        return self._agent_type
```

### 3.2 ErrorIndicator Widget

**Purpose**: Display error icon with tooltip showing error details.

```python
class ErrorIndicator(QLabel):
    """Error indicator icon with tooltip.
    
    Visual:
        ⚠  ← Warning icon in error color
        └─ Tooltip: "FileNotFoundError: File not found"
    
    Usage:
        indicator = ErrorIndicator()
        indicator.set_error({"name": "FileNotFoundError", "data": "..."})
    """
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setText("")
        self.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["error"]};
                font-size: {FONTS["size_sm"]}px;
            }}
        """)
        self.hide()
    
    def set_error(self, error_info: dict | None) -> None:
        """Update error display.
        
        Args:
            error_info: Dict with 'name' and optional 'data' keys, or None to hide
        """
        if not error_info:
            self.hide()
            return
        
        error_name = error_info.get("name", "Error")
        error_data = error_info.get("data", "")
        
        self.setText("⚠")
        
        # Build tooltip
        tooltip = f"Error: {error_name}"
        if error_data:
            # Truncate long error messages
            data_preview = error_data[:200] + "..." if len(error_data) > 200 else error_data
            tooltip += f"\n{data_preview}"
        
        self.setToolTip(tooltip)
        self.show()
    
    def has_error(self) -> bool:
        """Return True if error is displayed."""
        return self.isVisible()
```

### 3.3 ImageThumbnail Widget

**Purpose**: Display image preview with click-to-expand.

```python
from PyQt6.QtWidgets import QLabel, QWidget, QDialog, QVBoxLayout, QScrollArea
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, pyqtSignal, QByteArray
import base64


class ImageThumbnail(QLabel):
    """Clickable image thumbnail with lazy loading.
    
    Visual:
        ┌────────┐
        │  IMG   │ ← 48x48 thumbnail
        │        │   Click to expand
        └────────┘
    
    Usage:
        thumb = ImageThumbnail()
        thumb.set_image_url("data:image/png;base64,...")
        thumb.clicked.connect(self._show_full_image)
    """
    
    clicked = pyqtSignal(str)  # Emits data_url when clicked
    
    DEFAULT_SIZE = (48, 48)
    DETAIL_SIZE = (128, 128)
    
    def __init__(
        self, 
        size: tuple[int, int] = DEFAULT_SIZE,
        parent: QWidget | None = None
    ):
        super().__init__(parent)
        self._data_url: str = ""
        self._size = size
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup widget appearance."""
        self.setFixedSize(*self._size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS["bg_hover"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["sm"]}px;
            }}
            QLabel:hover {{
                border-color: {COLORS["border_strong"]};
            }}
        """)
        self.setText("...")  # Placeholder
    
    def set_image_url(self, data_url: str) -> None:
        """Set image from base64 data URL.
        
        Args:
            data_url: Data URL (data:image/png;base64,...)
        """
        if not data_url or not data_url.startswith("data:image"):
            self.hide()
            return
        
        self._data_url = data_url
        
        # Parse data URL
        try:
            # Format: data:image/png;base64,<data>
            header, b64_data = data_url.split(",", 1)
            image_data = base64.b64decode(b64_data)
            
            # Create QImage from data
            image = QImage()
            image.loadFromData(QByteArray(image_data))
            
            if image.isNull():
                self.setText("?")
                return
            
            # Scale to thumbnail size
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(
                *self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.setPixmap(scaled)
            
            # Set tooltip with image info
            self.setToolTip(
                f"Image: {image.width()}x{image.height()}\n"
                f"Click to view full size"
            )
            self.show()
            
        except Exception:
            self.setText("!")
            self.setToolTip("Failed to load image")
    
    def mousePressEvent(self, event) -> None:
        """Handle click to expand image."""
        if event.button() == Qt.MouseButton.LeftButton and self._data_url:
            self.clicked.emit(self._data_url)
        super().mousePressEvent(event)
    
    def data_url(self) -> str:
        """Return current data URL."""
        return self._data_url


class ImagePreviewDialog(QDialog):
    """Full-size image preview dialog.
    
    Usage:
        dialog = ImagePreviewDialog(data_url, parent)
        dialog.exec()
    """
    
    MAX_SIZE = (800, 600)
    
    def __init__(self, data_url: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Image Preview")
        self.setModal(True)
        self._setup_ui(data_url)
    
    def _setup_ui(self, data_url: str) -> None:
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area for large images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background-color: {COLORS['bg_base']};")
        
        # Image label
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        try:
            _, b64_data = data_url.split(",", 1)
            image_data = base64.b64decode(b64_data)
            
            image = QImage()
            image.loadFromData(QByteArray(image_data))
            
            pixmap = QPixmap.fromImage(image)
            
            # Scale if too large
            if pixmap.width() > self.MAX_SIZE[0] or pixmap.height() > self.MAX_SIZE[1]:
                pixmap = pixmap.scaled(
                    *self.MAX_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            image_label.setPixmap(pixmap)
            self.resize(pixmap.width() + 20, pixmap.height() + 20)
            
        except Exception:
            image_label.setText("Failed to load image")
        
        scroll.setWidget(image_label)
        layout.addWidget(scroll)
    
    def keyPressEvent(self, event) -> None:
        """Close on ESC."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)
```

### 3.4 EnrichedTooltip Helper

**Purpose**: Build rich tooltip content for tools.

```python
def build_tool_tooltip(tool_data: dict) -> str:
    """Build rich tooltip for tool with result_summary, cost, tokens.
    
    Format:
        Result: File read successfully (245 lines)
        ─────────────────────────
        Cost: $0.0012  |  Tokens: 1.2K in / 500 out
    
    Args:
        tool_data: Tool dict with enriched fields
        
    Returns:
        Formatted tooltip string
    """
    parts = []
    
    # Result summary
    result_summary = tool_data.get("result_summary")
    if result_summary:
        # Truncate if too long
        summary = result_summary[:150] + "..." if len(result_summary) > 150 else result_summary
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
            parts.append("─" * 30)
        parts.append("  |  ".join(metrics))
    
    return "\n".join(parts) if parts else ""


def format_cost(cost: float | None) -> str:
    """Format cost with appropriate precision."""
    if cost is None:
        return "-"
    if cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1.0:
        return f"${cost:.3f}"
    else:
        return f"${cost:.2f}"
```

### 3.5 Widget Integration Points

**Timeline Event Widget Enhancement** (`views/timeline.py`):

```python
class TimelineEventWidget(QFrame):
    """Enhanced timeline event with agent badge and error indicator."""
    
    def _setup_ui(self) -> None:
        # ... existing setup ...
        
        # Header row additions (after type_label):
        
        # Agent badge (for message events)
        agent = self._event.get("agent")
        if agent and self._event.get("type") in ("user_prompt", "assistant_response", "reasoning"):
            self._agent_badge = AgentBadge(agent)
            header_row.addWidget(self._agent_badge)
        
        # Error indicator (for any event with error)
        error_info = self._event.get("error")
        if error_info:
            self._error_indicator = ErrorIndicator()
            self._error_indicator.set_error(error_info)
            header_row.addWidget(self._error_indicator)
        
        # ... rest of header ...
        
        # Image thumbnail (for file_attachment events)
        file_url = self._event.get("file_url")
        if file_url and file_url.startswith("data:image"):
            self._thumbnail = ImageThumbnail()
            self._thumbnail.set_image_url(file_url)
            self._thumbnail.clicked.connect(self._show_image_preview)
            layout.addWidget(self._thumbnail)
    
    def _get_content_preview(self) -> str:
        """Enhanced content preview using title field."""
        event_type = self._event.get("type", "")
        
        if event_type == "tool_call":
            # Use title if available, fallback to tool_name
            title = self._event.get("title")
            tool_name = self._event.get("tool_name", "")
            
            label = title if title else self._format_tool_name(tool_name)
            
            status = self._event.get("status", "")
            status_icon = "✓" if status == "completed" else "✗" if status == "error" else ""
            
            return f"{label} {status_icon}"
        
        # ... rest of method ...
    
    def _format_tool_name(self, tool_name: str) -> str:
        """Format tool_name to Title Case."""
        return tool_name.replace("_", " ").title()
    
    def _setup_tooltip(self) -> None:
        """Setup enhanced tooltip with result_summary."""
        tooltip = build_tool_tooltip(self._event)
        if tooltip:
            self.setToolTip(tooltip)
```

**Tree Item Enhancement** (`tree_items.py`):

```python
def add_part_item(parent: QTreeWidgetItem, part: dict, index: int) -> QTreeWidgetItem:
    """Add a part (tool/file) item to tree with enriched data."""
    item = QTreeWidgetItem(parent)
    
    tool_name = part.get("tool_name", "")
    title = part.get("title")  # NEW: enriched title
    status = part.get("status", "")
    
    # Primary label: use title if available
    icon = TOOL_ICONS.get(tool_name, "⚙️")
    display_label = title if title else format_tool_name(tool_name)
    display_info = part.get("display_info", "")
    
    if display_info:
        item.setText(0, f"{icon} {display_label}: {display_info[:40]}")
    else:
        item.setText(0, f"{icon} {display_label}")
    
    # Tooltip with result_summary
    result_summary = part.get("result_summary")
    if result_summary:
        item.setToolTip(0, result_summary)
    
    # Status column with error indicator
    if status == "error":
        item.setText(5, "✗")
        item.setForeground(5, QColor(COLORS["error"]))
        
        # Error tooltip
        error_info = part.get("error", {})
        if error_info:
            error_tooltip = f"{error_info.get('name', 'Error')}: {error_info.get('data', '')}"
            item.setToolTip(5, error_tooltip)
    elif status == "completed":
        item.setText(5, "✓")
        item.setForeground(5, QColor(COLORS["success"]))
    
    # ... rest of method ...
```

---

## 4. Performance Strategy

### 4.1 Image Thumbnail Caching

```python
# File: src/opencode_status_bar/dashboard/sections/tracing/image_cache.py

from typing import Optional
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QByteArray, QThread, pyqtSignal, QObject
import base64
from functools import lru_cache


class ThumbnailCache(QObject):
    """LRU cache for decoded image thumbnails.
    
    Design:
    - Cache key: hash of data_url + size
    - Max cache size: 50 images (~5MB at 48x48)
    - Async decoding in worker thread
    """
    
    thumbnail_ready = pyqtSignal(str, object)  # (cache_key, QPixmap)
    
    MAX_CACHE_SIZE = 50
    
    def __init__(self):
        super().__init__()
        self._cache: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._worker: Optional[ThumbnailWorker] = None
    
    def get_thumbnail(
        self, 
        data_url: str, 
        size: tuple[int, int] = (48, 48)
    ) -> Optional[QPixmap]:
        """Get cached thumbnail synchronously.
        
        Returns:
            QPixmap if cached, None otherwise
        """
        cache_key = self._make_key(data_url, size)
        return self._cache.get(cache_key)
    
    def request_thumbnail(
        self, 
        data_url: str,
        size: tuple[int, int] = (48, 48)
    ) -> None:
        """Request async thumbnail generation.
        
        Connect to thumbnail_ready signal for result.
        """
        cache_key = self._make_key(data_url, size)
        
        # Already cached or pending
        if cache_key in self._cache or cache_key in self._pending:
            if cache_key in self._cache:
                self.thumbnail_ready.emit(cache_key, self._cache[cache_key])
            return
        
        # Start worker if needed
        if self._worker is None or not self._worker.isRunning():
            self._worker = ThumbnailWorker()
            self._worker.decoded.connect(self._on_decoded)
            self._worker.start()
        
        self._pending.add(cache_key)
        self._worker.add_task(cache_key, data_url, size)
    
    def _on_decoded(self, cache_key: str, pixmap: QPixmap) -> None:
        """Handle decoded thumbnail from worker."""
        self._pending.discard(cache_key)
        
        if not pixmap.isNull():
            # Evict oldest if cache full
            if len(self._cache) >= self.MAX_CACHE_SIZE:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            
            self._cache[cache_key] = pixmap
        
        self.thumbnail_ready.emit(cache_key, pixmap)
    
    def _make_key(self, data_url: str, size: tuple[int, int]) -> str:
        """Create cache key from data_url and size."""
        # Use hash of URL prefix (first 100 chars) + size
        url_hash = hash(data_url[:100])
        return f"{url_hash}_{size[0]}x{size[1]}"
    
    def clear(self) -> None:
        """Clear all cached thumbnails."""
        self._cache.clear()


class ThumbnailWorker(QThread):
    """Background worker for decoding images."""
    
    decoded = pyqtSignal(str, object)  # (cache_key, QPixmap)
    
    def __init__(self):
        super().__init__()
        self._tasks: list[tuple[str, str, tuple[int, int]]] = []
        self._running = True
    
    def add_task(self, cache_key: str, data_url: str, size: tuple[int, int]) -> None:
        """Add decoding task to queue."""
        self._tasks.append((cache_key, data_url, size))
    
    def run(self) -> None:
        """Process tasks in background."""
        while self._running and self._tasks:
            cache_key, data_url, size = self._tasks.pop(0)
            
            try:
                pixmap = self._decode_thumbnail(data_url, size)
                self.decoded.emit(cache_key, pixmap)
            except Exception:
                self.decoded.emit(cache_key, QPixmap())
    
    def _decode_thumbnail(self, data_url: str, size: tuple[int, int]) -> QPixmap:
        """Decode base64 image to scaled pixmap."""
        _, b64_data = data_url.split(",", 1)
        image_data = base64.b64decode(b64_data)
        
        image = QImage()
        image.loadFromData(QByteArray(image_data))
        
        if image.isNull():
            return QPixmap()
        
        pixmap = QPixmap.fromImage(image)
        return pixmap.scaled(
            *size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
    
    def stop(self) -> None:
        """Stop worker thread."""
        self._running = False


# Global cache instance
_thumbnail_cache: Optional[ThumbnailCache] = None

def get_thumbnail_cache() -> ThumbnailCache:
    """Get or create global thumbnail cache."""
    global _thumbnail_cache
    if _thumbnail_cache is None:
        _thumbnail_cache = ThumbnailCache()
    return _thumbnail_cache
```

### 4.2 Lazy Loading Strategy

```python
# In TimelineView or TreeWidget

class LazyImageLoader:
    """Lazy load images as they become visible.
    
    Strategy:
    1. Initially show placeholder for all image items
    2. When item scrolls into view, request thumbnail
    3. Update item when thumbnail ready
    """
    
    def __init__(self, scroll_area: QScrollArea):
        self._scroll_area = scroll_area
        self._cache = get_thumbnail_cache()
        self._cache.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._pending_widgets: dict[str, ImageThumbnail] = {}
        
        # Connect to scroll events
        scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)
    
    def register_thumbnail(self, widget: ImageThumbnail, data_url: str) -> None:
        """Register thumbnail for lazy loading."""
        cache_key = self._cache._make_key(data_url, widget._size)
        
        # Check if already cached
        cached = self._cache.get_thumbnail(data_url, widget._size)
        if cached:
            widget.setPixmap(cached)
            return
        
        # Store for later loading
        self._pending_widgets[cache_key] = widget
    
    def _on_scroll(self) -> None:
        """Load visible thumbnails on scroll."""
        visible_rect = self._scroll_area.viewport().rect()
        
        for cache_key, widget in list(self._pending_widgets.items()):
            # Check if widget is visible
            widget_rect = widget.visibleRegion().boundingRect()
            if not widget_rect.isEmpty():
                # Request thumbnail
                self._cache.request_thumbnail(widget._data_url, widget._size)
    
    def _on_thumbnail_ready(self, cache_key: str, pixmap: QPixmap) -> None:
        """Update widget when thumbnail ready."""
        widget = self._pending_widgets.pop(cache_key, None)
        if widget and not pixmap.isNull():
            widget.setPixmap(pixmap)
```

### 4.3 Memory Management

```python
# Memory considerations

class MemoryManager:
    """Track and limit memory usage for image cache.
    
    Limits:
    - Max thumbnails: 50 (48x48) = ~5MB
    - Max detail images: 10 (128x128) = ~6MB
    - Total target: < 15MB for image cache
    """
    
    MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024   # 5MB
    MAX_DETAIL_BYTES = 6 * 1024 * 1024      # 6MB
    
    @staticmethod
    def estimate_pixmap_size(pixmap: QPixmap) -> int:
        """Estimate memory usage of pixmap in bytes."""
        # 4 bytes per pixel (RGBA)
        return pixmap.width() * pixmap.height() * 4
    
    @staticmethod
    def should_cache(current_size: int, new_pixmap: QPixmap, max_size: int) -> bool:
        """Check if new pixmap should be cached."""
        new_size = MemoryManager.estimate_pixmap_size(new_pixmap)
        return (current_size + new_size) <= max_size
```

### 4.4 Performance Summary

| Concern | Strategy | Implementation |
|---------|----------|----------------|
| Image decoding | Async worker thread | `ThumbnailWorker` |
| Memory usage | LRU cache with size limit | `ThumbnailCache` (50 items) |
| Initial load | Placeholder, lazy load | `LazyImageLoader` |
| Scroll performance | Only load visible items | Viewport intersection check |
| Tooltip delay | Native Qt tooltip (no custom) | `setToolTip()` |
| API response size | No change (file_url only on detail) | Server-side filtering |

---

## 5. Implementation Order

### Phase 1: Foundation (Day 1)
**Goal**: Add enriched fields to API, create base widgets.

| # | Task | Files | Depends On | Complexity |
|---|------|-------|------------|------------|
| 1.1 | Add agent colors to colors.py | `styles/colors.py` | - | Low |
| 1.2 | Create `types.py` with TypedDict definitions | `tracing/types.py` | - | Low |
| 1.3 | Create `enriched_helpers.py` | `tracing/enriched_helpers.py` | 1.2 | Low |
| 1.4 | Add `title`, `result_summary` to tool API | `api/routes/tracing/builders.py` | - | Low |

### Phase 2: Core Widgets (Day 2)
**Goal**: Implement AgentBadge, ErrorIndicator, integrate into timeline.

| # | Task | Files | Depends On | Complexity |
|---|------|-------|------------|------------|
| 2.1 | Implement `AgentBadge` widget | `tracing/widgets.py` | 1.1, 1.3 | Low |
| 2.2 | Implement `ErrorIndicator` widget | `tracing/widgets.py` | 1.1 | Low |
| 2.3 | Integrate badges into TimelineEventWidget | `tracing/views/timeline.py` | 2.1, 2.2 | Medium |
| 2.4 | Add `title` field to tool content preview | `tracing/views/timeline.py` | 1.4 | Low |

### Phase 3: Tree Enrichments (Day 3)
**Goal**: Add enriched data to tree items.

| # | Task | Files | Depends On | Complexity |
|---|------|-------|------------|------------|
| 3.1 | Add `title` to tree tool items | `tracing/tree_items.py`, `tree_builder.py` | 1.4 | Low |
| 3.2 | Add `result_summary` tooltips | `tracing/tree_items.py` | 1.4 | Low |
| 3.3 | Add error indicator column | `tracing/tree_items.py` | 2.2 | Low |
| 3.4 | Add `summary_title` to session items | `tracing/tree_builder.py`, API | 1.4 | Medium |

### Phase 4: Image Support (Day 4-5)
**Goal**: Implement image thumbnails with caching.

| # | Task | Files | Depends On | Complexity |
|---|------|-------|------------|------------|
| 4.1 | Create `ImageThumbnail` widget | `tracing/widgets.py` | - | Medium |
| 4.2 | Create `ImagePreviewDialog` | `tracing/widgets.py` | 4.1 | Low |
| 4.3 | Implement `ThumbnailCache` | `tracing/image_cache.py` | - | Medium |
| 4.4 | Add `file_url` to timeline API | `api/routes/tracing/` | - | Low |
| 4.5 | Integrate thumbnails into timeline | `tracing/views/timeline.py` | 4.1, 4.3, 4.4 | Medium |
| 4.6 | Implement lazy loading | `tracing/image_cache.py` | 4.3, 4.5 | Medium |

### Phase 5: Testing & Polish (Day 6)
**Goal**: Comprehensive testing, accessibility, edge cases.

| # | Task | Files | Depends On | Complexity |
|---|------|-------|------------|------------|
| 5.1 | Unit tests for widgets | `tests/dashboard/tracing/` | All | Medium |
| 5.2 | Unit tests for helpers | `tests/dashboard/tracing/` | All | Low |
| 5.3 | Integration tests | `tests/dashboard/` | All | Medium |
| 5.4 | Accessibility audit | All widget files | All | Low |
| 5.5 | Visual regression check | Manual | All | Low |

### Implementation Gantt

```
Day 1: ████████░░░░░░░░░░░░░░░░  Foundation (Phase 1)
Day 2: ░░░░░░░░████████░░░░░░░░  Core Widgets (Phase 2)
Day 3: ░░░░░░░░░░░░░░░░████████  Tree Enrichments (Phase 3)
Day 4: ████████████░░░░░░░░░░░░  Image Support Part 1 (4.1-4.3)
Day 5: ░░░░░░░░░░░░████████████  Image Support Part 2 (4.4-4.6)
Day 6: ████████████████████████  Testing & Polish (Phase 5)
```

---

## 6. Test Strategy Outline

### 6.1 Unit Tests

```python
# tests/dashboard/sections/tracing/test_widgets.py

class TestAgentBadge:
    """Tests for AgentBadge widget."""
    
    def test_set_agent_shows_badge(self, qtbot):
        badge = AgentBadge()
        badge.set_agent("executor")
        assert badge.isVisible()
        assert badge.text() == "exec"
    
    def test_empty_agent_hides_badge(self, qtbot):
        badge = AgentBadge("executor")
        badge.set_agent("")
        assert not badge.isVisible()
    
    def test_unknown_agent_uses_default_color(self, qtbot):
        badge = AgentBadge("custom_agent")
        assert badge.isVisible()
        # Check default gray color applied


class TestErrorIndicator:
    """Tests for ErrorIndicator widget."""
    
    def test_set_error_shows_indicator(self, qtbot):
        indicator = ErrorIndicator()
        indicator.set_error({"name": "FileNotFoundError", "data": "File not found"})
        assert indicator.isVisible()
        assert indicator.text() == "⚠"
    
    def test_none_error_hides_indicator(self, qtbot):
        indicator = ErrorIndicator()
        indicator.set_error({"name": "Error"})
        indicator.set_error(None)
        assert not indicator.isVisible()


class TestImageThumbnail:
    """Tests for ImageThumbnail widget."""
    
    def test_valid_image_shows_pixmap(self, qtbot):
        # Create minimal valid PNG base64
        valid_png = "data:image/png;base64,iVBORw0KGgo..."
        thumb = ImageThumbnail()
        thumb.set_image_url(valid_png)
        assert thumb.pixmap() is not None
    
    def test_invalid_url_hides_widget(self, qtbot):
        thumb = ImageThumbnail()
        thumb.set_image_url("not-a-data-url")
        assert not thumb.isVisible()
    
    def test_click_emits_signal(self, qtbot):
        thumb = ImageThumbnail()
        thumb._data_url = "data:image/png;base64,..."
        with qtbot.waitSignal(thumb.clicked):
            qtbot.mouseClick(thumb, Qt.MouseButton.LeftButton)
```

### 6.2 Helper Function Tests

```python
# tests/dashboard/sections/tracing/test_enriched_helpers.py

class TestGetToolDisplayLabel:
    
    def test_title_takes_priority(self):
        data = {"title": "Check git status", "tool_name": "bash"}
        assert get_tool_display_label(data) == "Check git status"
    
    def test_fallback_to_tool_name(self):
        data = {"tool_name": "bash"}
        assert get_tool_display_label(data) == "Bash"
    
    def test_empty_returns_unknown(self):
        data = {}
        assert get_tool_display_label(data) == "Unknown"


class TestFormatCost:
    
    def test_small_cost_4_decimals(self):
        assert format_cost(0.0012) == "$0.0012"
    
    def test_medium_cost_3_decimals(self):
        assert format_cost(0.012) == "$0.012"
    
    def test_large_cost_2_decimals(self):
        assert format_cost(1.234) == "$1.23"
    
    def test_none_returns_dash(self):
        assert format_cost(None) == "-"


class TestBuildToolTooltip:
    
    def test_full_tooltip(self):
        data = {
            "result_summary": "File read successfully",
            "cost": 0.001,
            "tokens_in": 1500,
            "tokens_out": 0
        }
        tooltip = build_tool_tooltip(data)
        assert "File read successfully" in tooltip
        assert "$0.0010" in tooltip
        assert "1.5K in" in tooltip
    
    def test_empty_data_returns_empty(self):
        assert build_tool_tooltip({}) == ""
```

### 6.3 Integration Tests

```python
# tests/dashboard/sections/tracing/test_timeline_integration.py

class TestTimelineEnrichedData:
    """Integration tests for timeline with enriched data."""
    
    def test_agent_badge_displayed_for_message_event(self, qtbot):
        event = {
            "type": "assistant_response",
            "agent": "executor",
            "timestamp": "2026-01-09T10:00:00"
        }
        widget = TimelineEventWidget(event)
        # Find agent badge in widget
        badge = widget.findChild(AgentBadge)
        assert badge is not None
        assert badge.agent_type() == "executor"
    
    def test_error_indicator_displayed_for_failed_tool(self, qtbot):
        event = {
            "type": "tool_call",
            "status": "error",
            "error": {"name": "FileNotFoundError"},
            "timestamp": "2026-01-09T10:00:00"
        }
        widget = TimelineEventWidget(event)
        indicator = widget.findChild(ErrorIndicator)
        assert indicator is not None
        assert indicator.has_error()
    
    def test_tool_title_used_in_preview(self, qtbot):
        event = {
            "type": "tool_call",
            "tool_name": "bash",
            "title": "Check repository status",
            "timestamp": "2026-01-09T10:00:00"
        }
        widget = TimelineEventWidget(event)
        # Preview should use title, not tool_name
        assert "Check repository status" in widget._get_content_preview()
```

---

## 7. Files Summary

### New Files to Create

| File | Purpose |
|------|---------|
| `tracing/types.py` | TypedDict definitions for enriched data |
| `tracing/enriched_helpers.py` | Helper functions for enriched data |
| `tracing/image_cache.py` | Thumbnail caching with lazy loading |

### Files to Modify

| File | Changes |
|------|---------|
| `styles/colors.py` | Add agent type colors |
| `tracing/widgets.py` | Add AgentBadge, ErrorIndicator, ImageThumbnail |
| `tracing/views/timeline.py` | Integrate badges, error indicators, thumbnails |
| `tracing/tree_items.py` | Add title, result_summary tooltip, error column |
| `tracing/tree_builder.py` | Add summary_title to session items |
| `api/routes/tracing/builders.py` | Add enriched fields to tool nodes |
| `api/routes/tracing/fetchers.py` | Add summary_title to session query |

### Test Files

| File | Coverage |
|------|----------|
| `tests/dashboard/sections/tracing/test_widgets.py` | AgentBadge, ErrorIndicator, ImageThumbnail |
| `tests/dashboard/sections/tracing/test_enriched_helpers.py` | Helper functions |
| `tests/dashboard/sections/tracing/test_timeline_integration.py` | Timeline integration |
| `tests/dashboard/sections/tracing/test_image_cache.py` | Thumbnail cache |

---

## Appendix: ASCII Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           ENRICHED DATA FLOW                                    │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────────┐   │
│  │    Database     │──────►│   API Layer     │──────►│     Dashboard       │   │
│  │                 │       │                 │       │                     │   │
│  │  • messages     │       │  builders.py    │       │  ┌───────────────┐  │   │
│  │    - agent      │       │  - add fields   │       │  │ TimelineView  │  │   │
│  │    - error      │       │  - enriched     │       │  │               │  │   │
│  │    - summary_   │       │    JSON         │       │  │ ┌───────────┐ │  │   │
│  │      title      │       │                 │       │  │ │EventWidget│ │  │   │
│  │                 │       │  fetchers.py    │       │  │ │• AgentBadge│ │  │   │
│  │  • parts        │       │  - SQL queries  │       │  │ │• ErrorInd. │ │  │   │
│  │    - title      │       │                 │       │  │ │• Thumbnail │ │  │   │
│  │    - result_    │       │                 │       │  │ └───────────┘ │  │   │
│  │      summary    │       │                 │       │  └───────────────┘  │   │
│  │    - cost       │       │                 │       │                     │   │
│  │    - tokens     │       │                 │       │  ┌───────────────┐  │   │
│  │    - file_url   │       │                 │       │  │  TreeWidget   │  │   │
│  │                 │       │                 │       │  │  • title      │  │   │
│  └─────────────────┘       └─────────────────┘       │  │  • tooltip    │  │   │
│                                                       │  │  • error col  │  │   │
│                                                       │  └───────────────┘  │   │
│                                                       └─────────────────────┘   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                          WIDGET HIERARCHY                                  │  │
│  ├──────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                           │  │
│  │  widgets.py                                                               │  │
│  │  ├── AgentBadge(QLabel)         # Colored pill for agent type             │  │
│  │  ├── ErrorIndicator(QLabel)     # Warning icon with tooltip               │  │
│  │  ├── ImageThumbnail(QLabel)     # Clickable thumbnail                     │  │
│  │  └── ImagePreviewDialog(QDialog) # Full-size image modal                  │  │
│  │                                                                           │  │
│  │  image_cache.py                                                           │  │
│  │  ├── ThumbnailCache             # LRU cache for decoded images            │  │
│  │  └── ThumbnailWorker(QThread)   # Background decoder                      │  │
│  │                                                                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

*Document created: 2026-01-09*
*Author: @architect (Winston)*
*Status: Ready for Implementation*
