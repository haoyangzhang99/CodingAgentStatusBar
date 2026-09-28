# Plan 45b - Timeline UI Integration

**Status**: Ready for Implementation  
**Priority**: High  
**Effort**: Medium (1-2 days)  
**Depends on**: Plan 45 (Complete Tracing Architecture) ✅

---

## Problem Statement

Plan 45 created the data layer and UI components (`TimelineView`, `DelegationTreeView`) but they are **not connected** to the existing Dashboard UI. Users cannot see the new timeline features.

### Current State
```
TracingSection
├── QTreeWidget (session/exchange hierarchy)
└── TraceDetailPanel
    └── Tabs: Transcript, Tokens, Tools, Files, Agents, Timeline
                                                         ↑
                                          TimelineTab (basic QListWidget)
```

### Target State
```
TracingSection
├── QTreeWidget (session/exchange hierarchy) 
└── TraceDetailPanel
    └── Tabs: Transcript, Tokens, Tools, Files, Agents, Timeline
                                                         ↑
                                    NEW: Uses TimelineView component
                                         with full event rendering
```

---

## Implementation Tasks

### Task 1: Update TimelineTab to use TimelineView

**File**: `src/opencode_status_bar/dashboard/sections/tracing/tabs/timeline.py`

Replace the basic QListWidget with the new `TimelineView` component:

```python
from opencode_status_bar.dashboard.sections.tracing.views import TimelineView

class TimelineTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._add_summary_label()
        
        # NEW: Use TimelineView instead of QListWidget
        self._timeline_view = TimelineView()
        self._timeline_view.event_clicked.connect(self._on_event_clicked)
        self._layout.addWidget(self._timeline_view)
    
    def load_data(self, events: list[dict]) -> None:
        """Load timeline data."""
        self._loaded = True
        self._timeline_view.set_timeline(events)
        
        # Update summary
        if self._summary:
            total = len(events)
            tools = len([e for e in events if e.get("type") == "tool_call"])
            self._summary.setText(f"Events: {total}  •  Tools: {tools}")
    
    def _on_event_clicked(self, event: dict) -> None:
        """Handle event click - emit signal for detail panel."""
        # TODO: Connect to detail panel
        pass
```

### Task 2: Update DataLoader to fetch full timeline

**File**: `src/opencode_status_bar/dashboard/sections/tracing/detail_panel/handlers/data_loader.py`

Add method to load timeline from new API:

```python
def _load_timeline_data(self, session_id: str) -> list[dict]:
    """Load full timeline from /api/session/{id}/timeline/full."""
    if not self._service:
        return []
    
    # Use the new service method
    result = self._service.get_session_timeline_full(session_id)
    if result and result.get("success"):
        return result.get("data", {}).get("timeline", [])
    return []
```

### Task 3: Connect TimelineView events to detail panel

When user clicks an event in TimelineView, show details in the panel.

**Signal flow**:
```
TimelineView.event_clicked(event_dict)
    → TimelineTab._on_event_clicked
    → TraceDetailPanel.show_event_detail(event)
```

### Task 4: Add "Delegations" tab with DelegationTreeView

**File**: `src/opencode_status_bar/dashboard/sections/tracing/tabs/delegations.py` (NEW)

```python
from opencode_status_bar.dashboard.sections.tracing.views import DelegationTreePanel

class DelegationsTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tree_panel = DelegationTreePanel()
        self._tree_panel.tree_view.session_selected.connect(self._on_session_selected)
        self._layout.addWidget(self._tree_panel)
    
    def load_data(self, tree: dict) -> None:
        self._loaded = True
        self._tree_panel.tree_view.set_tree(tree)
    
    def _on_session_selected(self, session_id: str) -> None:
        """Navigate to selected session."""
        pass  # Emit signal to parent
```

### Task 5: Register new tab in TraceDetailPanel

**File**: `src/opencode_status_bar/dashboard/sections/tracing/detail_panel/panel.py`

```python
from ..tabs import DelegationsTab  # Add import

def _setup_tabs(self, layout):
    # ... existing tabs ...
    self._tabs.addTab(self._timeline_tab, "Timeline")
    
    # NEW: Add Delegations tab
    self._delegations_tab = DelegationsTab()
    self._tabs.addTab(self._delegations_tab, "Delegations")
```

### Task 6: Update tab data loading

**File**: `src/opencode_status_bar/dashboard/sections/tracing/detail_panel/handlers/data_loader.py`

Update `_load_tab_data` to handle new tabs:

```python
def _load_tab_data(self, tab_index: int) -> None:
    tab_name = self._tabs.tabText(tab_index).lower()
    
    if tab_name == "timeline":
        events = self._load_timeline_data(self._current_session_id)
        self._timeline_tab.load_data(events)
    
    elif tab_name == "delegations":
        tree = self._load_delegations_data(self._current_session_id)
        self._delegations_tab.load_data(tree)
```

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `tabs/timeline.py` | MODIFY | Use TimelineView component |
| `tabs/delegations.py` | CREATE | New tab with DelegationTreeView |
| `tabs/__init__.py` | MODIFY | Export DelegationsTab |
| `detail_panel/panel.py` | MODIFY | Add Delegations tab |
| `detail_panel/handlers/data_loader.py` | MODIFY | Load full timeline & delegations |

---

## Testing Checklist

- [ ] Timeline tab shows rich event widgets (not just text list)
- [ ] Event types have correct icons and colors
- [ ] Clicking an event shows details
- [ ] Delegations tab shows tree hierarchy
- [ ] Clicking a delegation navigates to that session
- [ ] Data loads correctly from new API endpoints
- [ ] No regressions in existing functionality

---

## Agent Assignment

| Task | Agent | Priority |
|------|-------|----------|
| Task 1: Update TimelineTab | `dev` | High |
| Task 2: Update DataLoader | `dev` | High |
| Task 3: Connect signals | `dev` | Medium |
| Task 4: Create DelegationsTab | `dev` | Medium |
| Task 5: Register new tab | `dev` | Low |
| Task 6: Update tab loading | `dev` | Medium |

**Estimated time**: 1-2 hours per task
