# Plan 46: Dashboard Enriched Data Integration

## Overview

Integrate the enriched data fields from Plan 45 into existing dashboard components without changing the UI structure. Focus on enhancing existing elements with more meaningful information.

## Available Enriched Data

| Field | Source | Description |
|-------|--------|-------------|
| `summary_title` | Messages | Auto-generated hook/title for the conversation |
| `title` | Tool parts | Human-readable tool operation title |
| `result_summary` | Tool parts | Summary of tool execution result |
| `error.name/data` | Messages | Error information when operation failed |
| `agent` | Messages | Agent type (main, executor, tea, etc.) |
| `root_path` | Messages | Project root path |
| `cost` | Tool parts | Cost of the tool operation |
| `tokens` | Tool parts | Token usage (input/output) |
| `file_url` | File parts | Base64 data URL for images/attachments |

## Integration Points

### 1. Session List/Cards
- **Current**: Shows title, directory, timestamps
- **Enhancement**: Add `summary_title` as subtitle when available
- **File**: `src/opencode_status_bar/dashboard/sections/tracing/session_list.py`

### 2. Timeline Tool Items  
- **Current**: Shows `tool_name` and status
- **Enhancement**: 
  - Use `title` as primary label (fallback to tool_name)
  - Add `result_summary` as tooltip on hover
  - Show `cost`/`tokens` in detail view
- **File**: `src/opencode_status_bar/dashboard/sections/tracing/views/timeline.py`

### 3. Message Items
- **Current**: Shows role and content
- **Enhancement**:
  - Add agent badge (main/executor/subagent)
  - Add error indicator icon for failed messages
- **File**: `src/opencode_status_bar/dashboard/sections/tracing/views/timeline.py`

### 4. Session Detail Header
- **Current**: Shows session title
- **Enhancement**: Add `root_path` as project indicator
- **File**: `src/opencode_status_bar/dashboard/sections/tracing/detail_panel/panel.py`

### 5. File Attachments (NEW)
- **Current**: Not displayed
- **Enhancement**: Show thumbnail for image attachments
- **File**: `src/opencode_status_bar/dashboard/sections/tracing/views/timeline.py`

## Agent Workflow

```
Phase 1: Analysis & Design
├── @analyst    → Analyze current dashboard code, identify integration points
└── @ux-designer → Design enrichment patterns, define visual indicators

Phase 2: Architecture
└── @architect  → Define data flow, component interfaces, caching strategy

Phase 3: Implementation  
└── @dev        → Implement enrichments following TDD approach

Phase 4: Quality
├── @tea        → Write comprehensive tests, verify coverage
└── @dev        → Code review and refinements

Phase 5: Validation
└── @ux-designer → Visual review, accessibility check
```

## Stories

### Story 1: Session Card Enrichment
**As a** user viewing the session list  
**I want** to see a meaningful subtitle for each session  
**So that** I can quickly understand what the session is about

**Acceptance Criteria:**
- [ ] Display `summary_title` below the main title when available
- [ ] Truncate with ellipsis if too long
- [ ] Show tooltip with full text on hover
- [ ] Graceful fallback when not available

### Story 2: Tool Operation Labels
**As a** user viewing the timeline  
**I want** to see human-readable tool descriptions  
**So that** I understand what each operation did without reading code

**Acceptance Criteria:**
- [ ] Use `title` field as primary label when available
- [ ] Fallback to formatted `tool_name` when title not present
- [ ] Show `result_summary` in tooltip on hover
- [ ] Display `cost` and `tokens` in expanded detail view

### Story 3: Agent Type Indicators
**As a** user analyzing a conversation  
**I want** to see which agent handled each message  
**So that** I can understand the delegation structure

**Acceptance Criteria:**
- [ ] Display agent badge/chip next to message role
- [ ] Use distinct colors for different agent types
- [ ] Show agent type in tooltip

### Story 4: Error Indicators
**As a** user debugging a session  
**I want** to see error indicators on failed operations  
**So that** I can quickly identify problems

**Acceptance Criteria:**
- [ ] Show error icon for messages with `error` field
- [ ] Display error name and details in tooltip
- [ ] Use warning color for visibility

### Story 5: Image Attachments Preview
**As a** user reviewing a session with screenshots  
**I want** to see thumbnail previews of attached images  
**So that** I can quickly review visual context

**Acceptance Criteria:**
- [ ] Display thumbnail for file parts with `file_url`
- [ ] Support common image formats (PNG, JPEG, GIF)
- [ ] Click to expand full image
- [ ] Show filename and size info

## Technical Considerations

### Performance
- Use lazy loading for image thumbnails
- Cache decoded base64 data
- Limit thumbnail size to 64x64 or 128x128

### Accessibility
- All new visual indicators must have text alternatives
- Tooltips accessible via keyboard
- Color-blind friendly indicator colors

### Testing
- Unit tests for data transformation
- Integration tests for API data flow
- Visual regression tests for UI changes

## Files to Modify

```
src/opencode_status_bar/dashboard/sections/tracing/
├── session_list.py          # Story 1: Session card enrichment
├── detail_panel/
│   └── panel.py             # Story 4: Session header with root_path
└── views/
    └── timeline.py          # Stories 2,3,4,5: Timeline enrichments
```

## Success Metrics

- [ ] All 5 stories implemented and tested
- [ ] No visual regression in existing elements
- [ ] Test coverage > 80% for new code
- [ ] Accessibility audit passed
- [ ] Performance: No additional API calls, data already in responses
