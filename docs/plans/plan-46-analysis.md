# Plan 46: Dashboard Code Analysis

## Executive Summary

Analysis of current dashboard components to identify exact integration points for enriched data from Plan 45. Key findings:

1. **No separate session_list.py** - Sessions are displayed as tree items in `section.py` and `tree_builder.py`
2. **Timeline view exists** - `views/timeline.py` displays events with type, timestamp, and content preview
3. **Data flows through API client** - All data fetched via `AnalyticsAPIClient` → API routes → TracingDataService
4. **Enriched fields available but not displayed** - API already returns `result_summary`, `display_info`, etc.

---

## 1. Current State

### 1.1 Session Tree (replaces Session Cards)
**Files:**
- `src/opencode_status_bar/dashboard/sections/tracing/section.py`
- `src/opencode_status_bar/dashboard/sections/tracing/tree_builder.py`

**Current Display:**
- Root sessions show: `🌳 {project_name}` (line 61, tree_builder.py)
- User turns show: `💬 user → {agent}: "{preview}"` (lines 76-88)
- Delegations show: `{icon} {parent_agent} → {agent}` (lines 143-167)
- Tools show: `{icon} {tool_name}: {display_info}` (lines 168-223)

**Data Available But Not Used:**
- `session.get("title")` - Session title from DB
- **Missing:** `summary_title` - Not yet in API response

### 1.2 Timeline View
**File:** `src/opencode_status_bar/dashboard/sections/tracing/views/timeline.py`

**Current Display (TimelineEventWidget):**
| Element | Source | Line |
|---------|--------|------|
| Type label | `_format_type_label()` | 171-187 |
| Timestamp | `event.get("timestamp")` | 122-129 |
| Duration | `event.get("duration_ms")` | 132-139 |
| Content preview | `_get_content_preview()` | 199-236 |
| Tokens (step_finish only) | `tokens_in/tokens_out` | 160-169 |

**Tool Call Preview (lines 212-220):**
```python
elif event_type == "tool_call":
    tool_name = event_data.get("tool_name", "")
    status = event_data.get("status", "")
    status_icon = "✓" if status == "completed" else "✗" if status == "error" else ""
    return f"{tool_name} {status_icon}"
```

**Missing Enrichments:**
- `title` field (human-readable tool title)
- `result_summary` (tooltip on hover)
- `cost` and `tokens` per tool
- `agent` badge on messages
- Error indicator icon

### 1.3 Detail Panel
**File:** `src/opencode_status_bar/dashboard/sections/tracing/detail_panel/panel.py`

**Current Display:**
| Method | Shows | Lines |
|--------|-------|-------|
| `show_session_summary()` | Header with project name | 267-324 |
| `show_tool()` | Tool name, display_info, status, duration | 508-564 |
| `show_exchange()` | User content, assistant content, tokens | 412-444 |

**Header Display (lines 302-306):**
```python
directory = meta.get("directory", "")
project_name = os.path.basename(directory) if directory else "Session"
self._header.setText(f"🌳 {project_name}")
```

**Missing Enrichments:**
- `root_path` display (only directory basename shown)
- `summary_title` as subtitle

### 1.4 Data Loader
**File:** `src/opencode_status_bar/dashboard/sections/tracing/detail_panel/handlers/data_loader.py`

**Tab Loading Methods:**
| Tab Index | Method | API Endpoint |
|-----------|--------|--------------|
| 0 | `_load_transcript_tab()` | `/api/session/{id}/prompts` |
| 1 | `_load_tokens_tab()` | `/api/session/{id}/tokens` |
| 2 | `_load_tools_tab()` | `/api/session/{id}/tools` |
| 3 | `_load_files_tab()` | `/api/session/{id}/files` |
| 4 | `_load_agents_tab()` | `/api/session/{id}/agents` |
| 5 | `_load_timeline_tab()` | `/api/session/{id}/timeline` |
| 6 | `_load_delegations_tab()` | Via service.get_delegation_tree() |

---

## 2. Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                           API Server                                 │
│  routes/tracing/builders.py → builds tree with all available data   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       api/client.py                                  │
│  get_tracing_tree() → /api/tracing/tree                             │
│  get_session_timeline() → /api/session/{id}/timeline                │
│  get_session_tools() → /api/session/{id}/tools                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Dashboard Components                              │
│  TracingSection.update_data() → receives session_hierarchy          │
│  tree_builder.build_session_tree() → populates QTreeWidget          │
│  TraceDetailPanel.show_session_summary() → shows details            │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Entry Points:
1. **Session Tree**: `TracingSection.update_data(session_hierarchy)` (section.py:363)
2. **Detail Panel**: `TraceDetailPanel.show_session_summary(session_id, tree_data)` (panel.py:267)
3. **Timeline Events**: `TimelineView.set_timeline(timeline)` (timeline.py:345)

---

## 3. Integration Points

### 3.1 Story 1: Session Card Enrichment (summary_title)
**No session cards exist** - Sessions are tree items. Enrichment should be added to tree labels.

| File | Method | Line | Current | Enhancement |
|------|--------|------|---------|-------------|
| tree_builder.py | `add_session_item()` | 59-62 | `🌳 {project}` | Add `summary_title` as second line |
| tree_builder.py | `add_session_item()` | 296-297 | `setToolTip(0, directory)` | Add full `summary_title` to tooltip |

**Implementation Location:**
```python
# tree_builder.py, around line 61
if is_root:
    project = get_project_name(directory)
    item.setText(0, f"🌳 {project}")
    # ADD: summary_title as subtitle if available
    summary_title = session.get("summary_title", "")
    if summary_title:
        # Option 1: Append to text
        item.setText(0, f"🌳 {project}\n   {summary_title[:50]}...")
        # Option 2: Store for second column or tooltip
        item.setToolTip(0, summary_title)
```

### 3.2 Story 2: Tool Operation Labels (title, result_summary)
**Integration Points:**

| File | Method | Line | Current | Enhancement |
|------|--------|------|---------|-------------|
| timeline.py | `_get_content_preview()` | 212-220 | `f"{tool_name} {status_icon}"` | Use `title` field, add `result_summary` tooltip |
| timeline.py | `_format_type_label()` | 171-187 | Fixed labels | Dynamic label from `title` |
| tree_items.py | `add_part_item()` | 133-143 | `f"{icon} {tool_name}: {info_preview}"` | Use `title` as primary label |
| tree_builder.py | node_type "tool" | 168-223 | `f"{icon} {tool_name}: {display_info}"` | Use `title` field |

**Primary Implementation (timeline.py:212-220):**
```python
elif event_type == "tool_call":
    # Current: tool_name only
    tool_name = event_data.get("tool_name", "")
    
    # Enhancement: Use title field if available
    title = event_data.get("title", "")  # From enriched API
    label = title if title else tool_name
    
    status = event_data.get("status", "")
    status_icon = "✓" if status == "completed" else "✗" if status == "error" else ""
    return f"{label} {status_icon}"
```

**Tooltip Enhancement (timeline.py, TimelineEventWidget):**
```python
# Add to __init__ or _setup_ui around line 87
result_summary = self._event.get("result_summary", "")
if result_summary:
    self.setToolTip(result_summary)
```

### 3.3 Story 3: Agent Type Indicators
**Integration Points:**

| File | Method | Line | Current | Enhancement |
|------|--------|------|---------|-------------|
| timeline.py | `_get_content_preview()` | 204-206 | No agent shown | Add agent badge |
| timeline.py | `_setup_ui()` | 106-117 | Type label only | Add agent chip after type |
| tree_builder.py | user_turn | 63-88 | `user → {agent}` format | Already shows agent, add color coding |

**Implementation (timeline.py, around line 117):**
```python
# After type_label in header row, add agent badge
agent = self._event.get("agent", "")
if agent and event_type in ("user_prompt", "assistant_response", "reasoning"):
    agent_label = QLabel(agent)
    agent_label.setStyleSheet(f"""
        background-color: {self._get_agent_color(agent)};
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: {FONTS["size_xs"]}px;
    """)
    header_row.addWidget(agent_label)
```

### 3.4 Story 4: Error Indicators
**Integration Points:**

| File | Method | Line | Current | Enhancement |
|------|--------|------|---------|-------------|
| timeline.py | `_setup_ui()` | 76-86 | Border color only | Add error icon in header |
| timeline.py | `_get_content_preview()` | 217-218 | Status icon at end | Move to header row |
| tree_items.py | `add_part_item()` | 156-161 | Foreground color only | Add ⚠️ icon |

**Implementation (timeline.py, around line 130):**
```python
# In header_row after timestamp, add error indicator
error_info = self._event.get("error", {})
if error_info:
    error_label = QLabel("⚠️")
    error_label.setToolTip(f"{error_info.get('name', 'Error')}: {error_info.get('data', '')}")
    error_label.setStyleSheet(f"color: {COLORS['error']};")
    header_row.addWidget(error_label)
```

### 3.5 Story 5: Image Attachments Preview (file_url)
**Integration Points:**

| File | Method | Line | Current | Enhancement |
|------|--------|------|---------|-------------|
| timeline.py | `_get_content_preview()` | 236 | Returns "" for unknown | Handle file_attachment type |
| timeline.py | `_setup_ui()` | 144-155 | Text preview only | Add image thumbnail |

**New Event Type Handler (timeline.py):**
```python
# Add to EVENT_TYPE_CONFIG (line 39)
"file_attachment": ("📎", "#ec4899", "type_glob_bg"),

# Add to _get_content_preview (after line 234)
elif event_type == "file_attachment":
    filename = event_data.get("filename", "")
    return f"📎 {filename}"

# Add thumbnail widget in _setup_ui for file types
file_url = self._event.get("file_url", "")
if file_url and file_url.startswith("data:image"):
    thumbnail = self._create_image_thumbnail(file_url)
    layout.addWidget(thumbnail)
```

---

## 4. API Data Available

### 4.1 Currently Available in API Responses

**From `/api/tracing/tree` (builders.py):**
```python
# Tool node (line 62-72)
{
    "tool_name": row[2],
    "status": row[3],
    "display_info": display_info,  # Extracted from arguments
    "duration_ms": row[6],
    # Missing: title, result_summary, cost, tokens
}
```

**From parts table (fetchers.py:45-52):**
```sql
SELECT id, session_id, tool_name, tool_status,
       arguments, created_at, duration_ms, result_summary
FROM parts
```
Note: `result_summary` is already fetched but only used in `build_tools_by_message()`, not in tree.

### 4.2 Enriched Fields from Plan 45 (to verify)

| Field | Table | Available in API? | Used in Dashboard? |
|-------|-------|-------------------|-------------------|
| `summary_title` | messages | **Not checked** | No |
| `title` | parts (tool) | **Not checked** | No |
| `result_summary` | parts | Yes (fetchers.py:45) | Partially (tools by message only) |
| `error.name/data` | messages | **Not checked** | No |
| `agent` | messages | Yes (fetchers.py:154) | Partially |
| `root_path` | messages | **Not checked** | No |
| `cost` | parts | **Not checked** | No |
| `tokens` | parts | **Not checked** | No |
| `file_url` | parts (file) | **Not checked** | No |

### 4.3 Recommended API Enhancements

1. **Add to tracing tree response:**
   - `summary_title` from first message in session
   - `result_summary` for tool nodes (already fetched, not exposed)

2. **Add to timeline response:**
   - `title` field for tool events
   - `agent` field for all events
   - `error` object for failed events
   - `file_url` for file attachment events

---

## 5. Risks and Considerations

### 5.1 Potential Breaking Changes
| Risk | Severity | Mitigation |
|------|----------|------------|
| Adding widgets to tree items may affect layout | Low | Test tree rendering performance |
| Image thumbnails increase memory | Medium | Lazy load, cache decoded data, limit size |
| Tooltip content may overflow | Low | Truncate with "..." |
| Agent color conflicts | Low | Use existing color palette |

### 5.2 Performance Considerations
- **Timeline max_events limit**: Currently 100 events (timeline.py:381) - sufficient
- **Image thumbnails**: Need lazy loading for file_url base64 data
- **Tree widget**: `setUpdatesEnabled(False)` already used (section.py:345)

### 5.3 Accessibility
- All icons need text alternatives (tooltips)
- Color-only indicators need shape differentiation (already using status icons)
- Agent badges need sufficient contrast

### 5.4 Missing Components
- No session card widget - sessions are tree items
- No separate session list - integrated in tree view
- Image preview component does not exist - needs creation

---

## 6. Implementation Priority

### Phase 1: Low-hanging fruit (data already available)
1. **Tool result_summary tooltips** - Data fetched, just not displayed
2. **Agent in tree labels** - Already shown in user_turn format
3. **Error indicators** - Status already tracked

### Phase 2: API enhancement needed
4. **summary_title** - Needs API to return from messages.summary_title
5. **Tool title field** - Needs API to return from parts.title
6. **cost/tokens per tool** - Needs API enhancement

### Phase 3: New component needed
7. **Image attachment thumbnails** - Needs thumbnail widget and base64 handling

---

## 7. Files to Modify Summary

```
src/opencode_status_bar/dashboard/sections/tracing/
├── tree_builder.py          # Stories 1, 2: Session labels, tool titles
├── tree_items.py            # Story 2: Part item labels
├── views/timeline.py        # Stories 2, 3, 4, 5: All timeline enrichments
├── detail_panel/panel.py    # Story 4: Root path display
└── helpers.py               # New: Agent color helper

src/opencode_status_bar/api/routes/tracing/
├── builders.py              # API: Add enriched fields to responses
└── fetchers.py              # Already fetches result_summary
```

---

## Appendix: Key Line References

| Component | File | Key Lines |
|-----------|------|-----------|
| Session tree label | tree_builder.py | 59-62, 296-297 |
| User turn label | tree_builder.py | 63-88 |
| Tool tree item | tree_builder.py | 168-223 |
| Timeline event widget | views/timeline.py | 46-251 |
| Event type config | views/timeline.py | 27-43 |
| Content preview | views/timeline.py | 199-236 |
| Detail panel header | detail_panel/panel.py | 152-165 |
| Session summary | detail_panel/panel.py | 267-324 |
| Tool display | detail_panel/panel.py | 508-564 |
| Data loader tabs | detail_panel/handlers/data_loader.py | 48-89 |
