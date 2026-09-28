# Sprint 1: Data Quality - Data Extraction & Quality

**Sprint ID**: 2026-01-DQ-S1  
**Epic**: [DQ-001 - Data Quality & Architecture Improvement](../epics/epic-data-quality.md)  
**Duration**: 7 days (1 week)  
**Start Date**: 2026-01-20  
**End Date**: 2026-01-26  
**Status**: Planned  
**Depends On**: Sprint 0 (P0 fixes complete)

---

## Sprint Goal

**Extract missing fields from JSON** to recover ~430K lost data points: capture root_path, classify error types, extract tool execution times, and store git metadata.

This sprint focuses on **data enrichment** by extracting critical fields currently lost during loading.

---

## Velocity

| Métrique | Valeur |
|----------|--------|
| Points planifiés | 7 |
| Stories | 4 |
| Focus | Data Extraction |
| Team Size | 2 FTE |
| Daily Capacity | ~1 point/day |

---

## Stories

### US-6: Extract root_path from Messages

**Story ID**: DQ-006  
**Points**: 2  
**Priority**: P1 - High  
**Assignee**: TBD

**As a** project analyst,  
**I want** root_path (OpenCode project root) stored for each message,  
**So that** I can correlate messages with specific projects and filter by project.

**Current State**: root_path exists in JSON but not extracted → Cannot filter by project

**Acceptance Criteria**:
- [ ] root_path extracted from message JSON (`message.root_path`)
- [ ] Added to messages table as new column
- [ ] Index created for filtering (`CREATE INDEX idx_messages_root_path`)
- [ ] 100% backward populated (all existing messages)
- [ ] Tests for all edge cases (null, empty, missing)
- [ ] Query performance validated (<50ms for project filtering)

**Technical Notes**:
```python
# JSON structure:
{
    "message": {
        "root_path": "/Users/name/Projects/my-project",
        "content": "..."
    }
}

# Schema change:
ALTER TABLE messages ADD COLUMN root_path VARCHAR;
CREATE INDEX idx_messages_root_path ON messages(root_path);
```

**Files**:
- `src/opencode_status_bar/analytics/db.py` - Add root_path column
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Extract root_path
- `src/opencode_status_bar/analytics/migrations/add_root_path.sql` - NEW
- `tests/test_root_path_extraction.py` - NEW

**Tasks**:
- [ ] Add root_path column to messages schema
- [ ] Update message parser to extract root_path
- [ ] Create migration script for backfill
- [ ] Add index on root_path
- [ ] Unit tests for extraction logic
- [ ] Integration test with real messages
- [ ] Validate queries by project work

---

### US-7: Extract & Classify Error Types

**Story ID**: DQ-007  
**Points**: 3  
**Priority**: P1 - High  
**Assignee**: TBD

**As a** SRE,  
**I want** error types classified (timeout, auth, network, rate_limit, etc.),  
**So that** I can build error analytics dashboards and identify patterns.

**Current State**: error_data is blob → Cannot categorize or aggregate errors

**Acceptance Criteria**:
- [ ] Error classification logic implemented (15+ categories)
- [ ] error_data.type extracted and normalized
- [ ] error_category column added to parts table
- [ ] All historical errors classified and backfilled
- [ ] Classification accuracy >95% (validated manually)
- [ ] Tests for all error types (timeout, auth, network, etc.)

**Error Categories**:
```python
ERROR_CATEGORIES = {
    'timeout': ['timeout', 'timed out', 'deadline exceeded'],
    'auth': ['authentication', 'unauthorized', '401', '403'],
    'network': ['connection', 'network', 'dns', 'socket'],
    'rate_limit': ['rate limit', 'too many requests', '429'],
    'api_error': ['api error', 'invalid request', '400'],
    'server_error': ['500', '502', '503', 'internal server error'],
    'parse_error': ['json', 'parse', 'decode', 'invalid format'],
    'file_error': ['file not found', 'permission denied', 'no such file'],
    'validation': ['validation', 'invalid', 'constraint'],
    'resource': ['memory', 'disk space', 'quota exceeded'],
    # ... 5+ more categories
}
```

**Technical Notes**:
```python
def classify_error(error_data: dict) -> str:
    """Classify error into category based on type and message."""
    error_type = error_data.get('type', '')
    error_msg = error_data.get('message', '')
    
    for category, patterns in ERROR_CATEGORIES.items():
        if any(p in error_type.lower() or p in error_msg.lower() 
               for p in patterns):
            return category
    return 'unknown'
```

**Files**:
- `src/opencode_status_bar/analytics/indexer/error_classifier.py` - NEW
- `src/opencode_status_bar/analytics/db.py` - Add error_category column
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Use classifier
- `tests/test_error_classification.py` - NEW

**Tasks**:
- [ ] Design error classification taxonomy (15+ categories)
- [ ] Implement error_classifier.py module
- [ ] Add error_category column to parts table
- [ ] Update parsers to classify errors during loading
- [ ] Backfill existing errors with classification
- [ ] Unit tests for each error category
- [ ] Validate classification accuracy (sample 100 errors)
- [ ] Create error analytics queries

---

### US-8: Capture Tool Execution Times

**Story ID**: DQ-008  
**Points**: 2  
**Priority**: P1 - High  
**Assignee**: TBD

**As a** performance engineer,  
**I want** tool execution times captured for each tool call,  
**So that** I can identify slow tools and optimize performance bottlenecks.

**Current State**: Execution time in JSON but not extracted → No performance analytics

**Acceptance Criteria**:
- [ ] execution_time extracted from parts JSON (`part.timing.duration_ms`)
- [ ] Stored in parts table as execution_time_ms column
- [ ] Aggregations per tool/model/agent work
- [ ] Percentile queries (p50, p95, p99) validated
- [ ] Performance dashboard queries (<100ms)
- [ ] Tests cover all scenarios (null, missing, edge cases)

**Technical Notes**:
```python
# JSON structure:
{
    "part": {
        "tool_call": {
            "name": "mcp_read",
            "timing": {
                "start": 1234567890.123,
                "end": 1234567891.456,
                "duration_ms": 1333
            }
        }
    }
}

# Schema change:
ALTER TABLE parts ADD COLUMN execution_time_ms DOUBLE;
CREATE INDEX idx_parts_execution_time ON parts(execution_time_ms);

# Analytics queries:
SELECT 
    tool_name,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY execution_time_ms) as p50,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY execution_time_ms) as p95,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY execution_time_ms) as p99
FROM parts 
WHERE execution_time_ms IS NOT NULL
GROUP BY tool_name;
```

**Files**:
- `src/opencode_status_bar/analytics/db.py` - Add execution_time_ms column
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Extract timing
- `tests/test_tool_execution_times.py` - NEW

**Tasks**:
- [ ] Add execution_time_ms column to parts table
- [ ] Update parser to extract timing data
- [ ] Backfill existing tool calls with timing
- [ ] Add index on execution_time_ms
- [ ] Create performance analytics queries (p50, p95, p99)
- [ ] Unit tests for timing extraction
- [ ] Validate queries on real data

---

### US-9: Extract Git Metadata

**Story ID**: DQ-009  
**Points**: 2  
**Priority**: P1 - High  
**Assignee**: TBD

**As a** developer,  
**I want** git branch, commit_hash, and diff stored for file modifications,  
**So that** I can correlate code changes with agent behavior and trace decisions.

**Current State**: Git metadata in JSON but not captured → Cannot correlate with commits

**Acceptance Criteria**:
- [ ] git_branch extracted and stored in parts table
- [ ] git_commit extracted and stored in parts table
- [ ] diff content optionally stored (truncated if >1KB)
- [ ] Queries on branch/commit work fast (<50ms)
- [ ] Historical data enriched (backfill existing file modifications)
- [ ] Tests verify all edge cases (detached HEAD, no git, etc.)

**Technical Notes**:
```python
# JSON structure:
{
    "part": {
        "file_operation": {
            "path": "/path/to/file.py",
            "git_context": {
                "branch": "feature/new-feature",
                "commit": "a1b2c3d",
                "diff": "+added line\n-removed line"
            }
        }
    }
}

# Schema changes:
ALTER TABLE parts ADD COLUMN git_branch VARCHAR;
ALTER TABLE parts ADD COLUMN git_commit VARCHAR(40);
ALTER TABLE parts ADD COLUMN git_diff TEXT;

CREATE INDEX idx_parts_git_branch ON parts(git_branch);
CREATE INDEX idx_parts_git_commit ON parts(git_commit);
```

**Files**:
- `src/opencode_status_bar/analytics/db.py` - Add git columns
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Extract git metadata
- `tests/test_git_metadata.py` - NEW

**Tasks**:
- [ ] Add git columns to parts table (branch, commit, diff)
- [ ] Update parser to extract git context
- [ ] Handle edge cases (no git, detached HEAD)
- [ ] Truncate diffs >1KB to save space
- [ ] Backfill existing file operations
- [ ] Add indexes on git_branch and git_commit
- [ ] Unit tests for git extraction
- [ ] Integration test with real git repos

---

## Sprint Backlog

| ID | Story | Points | Status | Assignee | Day |
|----|-------|--------|--------|----------|-----|
| DQ-006 | Extract root_path | 2 | To Do | TBD | Day 1-2 |
| DQ-007 | Classify Error Types | 3 | To Do | TBD | Day 3-4 |
| DQ-008 | Tool Execution Times | 2 | To Do | TBD | Day 5-6 |
| DQ-009 | Git Metadata | 2 | To Do | TBD | Day 6-7 |
| **Total** | | **7** | | | |

---

## Daily Schedule

### Day 1 (Mon): root_path Extraction
- Morning: DQ-006 schema + parser implementation
- Afternoon: DQ-006 backfill + tests

### Day 2 (Tue): root_path Validation
- Morning: DQ-006 integration tests + validation
- Afternoon: Start DQ-007 design (error taxonomy)

### Day 3 (Wed): Error Classification (Part 1)
- Morning: DQ-007 error_classifier implementation
- Afternoon: DQ-007 parser integration

### Day 4 (Thu): Error Classification (Part 2)
- Morning: DQ-007 backfill + validation
- Afternoon: DQ-007 tests + accuracy check

### Day 5 (Fri): Tool Execution Times
- Morning: DQ-008 schema + parser
- Afternoon: DQ-008 backfill + analytics queries

### Day 6 (Sat): Git Metadata
- Morning: DQ-009 schema + parser
- Afternoon: DQ-009 backfill + edge cases

### Day 7 (Sun): Final Validation
- Morning: Sprint validation + integration tests
- Afternoon: Sprint review prep + metrics

---

## Definition of Done (Sprint)

### Code Quality
- [ ] All tests pass (`make test`)
- [ ] Coverage >= 80% on new code
- [ ] No lint errors (`make lint`)
- [ ] Code reviewed and approved

### Data Quality
- [ ] 100% of messages have root_path
- [ ] 95%+ errors classified correctly
- [ ] 100% of tool calls have execution_time
- [ ] 100% of file ops have git metadata (where applicable)

### Documentation
- [ ] All functions have docstrings
- [ ] Migration procedures documented
- [ ] Backfill procedures documented
- [ ] Analytics query examples provided

### Validation
- [ ] Backfill completed successfully (0 data loss)
- [ ] Queries on new fields work (<50ms)
- [ ] Error analytics dashboard mockup validated
- [ ] Performance analytics queries validated

---

## Technical Dependencies

```
Sprint 0 (P0 fixes) ──► DQ-006 (root_path) ───┐
                                              │
                        DQ-007 (errors) ──────┼──► Sprint 2
                                              │
                        DQ-008 (timing) ──────┤
                                              │
                        DQ-009 (git) ─────────┘
```

**Critical Path**: Sprint 0 → All stories (parallel) → Sprint 2

**Parallelizable**: DQ-006, DQ-007, DQ-008, DQ-009 can be done in parallel after Sprint 0

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Backfill takes too long | Medium | Medium | Incremental backfill, batch processing, progress tracking |
| Error classification accuracy low | Medium | Medium | Manual validation on 100 samples, iterative refinement |
| Git metadata missing for old data | High | Low | Handle null gracefully, document data gaps |
| Timing data format inconsistent | Low | Medium | Handle multiple formats, fallback to null |
| root_path extraction edge cases | Medium | Low | Extensive edge case testing, default to null |

---

## Success Criteria

### Sprint-Level Metrics
- [ ] All 4 stories completed (7 points)
- [ ] Zero critical bugs introduced
- [ ] Test coverage >= 80%
- [ ] All backfills completed successfully

### Business Impact
- [ ] +430K data points recovered
- [ ] Error analytics enabled (15+ categories)
- [ ] Performance analytics enabled (tool timing)
- [ ] Git correlation enabled (branch/commit tracking)
- [ ] Project filtering enabled (root_path)

### Data Completeness
- [ ] Messages: 70% → 85% completeness
- [ ] Parts: 70% → 90% completeness
- [ ] Errors: 0% → 95% classified
- [ ] Tool calls: 0% → 100% timed

---

## References

- **Epic**: [epic-data-quality.md](../epics/epic-data-quality.md)
- **Sprint 0**: [2026-01-data-quality-sprint0.md](2026-01-data-quality-sprint0.md)
- **Audit Report**: [data-audit-comprehensive-2026-01-10.md](../../audit-reports/data-audit-comprehensive-2026-01-10.md)
- **Architecture**: `src/opencode_status_bar/analytics/`

---

## Sprint Review Checklist

**Demos**:
- [ ] Show project filtering by root_path
- [ ] Show error analytics dashboard with 15+ categories
- [ ] Show tool performance analytics (p50, p95, p99)
- [ ] Show git correlation (changes by branch/commit)
- [ ] Show data completeness improvement (70% → 90%)

**Metrics**:
- [ ] Velocity: 7 points completed
- [ ] Backfill success rate: 100%
- [ ] Error classification accuracy: >95%
- [ ] Query performance: <50ms on all new fields

**Feedback**:
- [ ] Stakeholder sign-off on data completeness
- [ ] Analyst feedback on error categories
- [ ] Performance team feedback on timing data
- [ ] Developer feedback on git correlation

---

## Retrospective Topics

- Backfill strategy effectiveness?
- Error classification accuracy challenges?
- Data extraction patterns learned?
- Readiness for Sprint 2 (enrichment)?
- Action items for next sprint?

---

## Notes for Developers

### Setup

```bash
# Checkout branch
cd worktrees/feature/data-quality

# Run backfill scripts
python scripts/backfill_root_path.py
python scripts/backfill_errors.py
python scripts/backfill_timing.py
python scripts/backfill_git.py

# Validate backfill
make test-backfill
```

### Key Files

```
src/opencode_status_bar/analytics/
├── db.py                           # Schema changes (all stories)
├── indexer/
│   ├── parsers.py                 # Extraction logic (all stories)
│   ├── error_classifier.py        # NEW - Error categorization (US-7)
│   └── backfill/                  # NEW - Backfill scripts
│       ├── root_path.py
│       ├── errors.py
│       ├── timing.py
│       └── git.py
```

### Analytics Queries

```sql
-- Project activity
SELECT root_path, COUNT(*) as messages
FROM messages
GROUP BY root_path
ORDER BY messages DESC;

-- Error breakdown
SELECT error_category, COUNT(*) as errors
FROM parts
WHERE error_category IS NOT NULL
GROUP BY error_category;

-- Tool performance
SELECT tool_name, 
    percentile_cont(0.5) WITHIN GROUP (ORDER BY execution_time_ms) as p50_ms
FROM parts
GROUP BY tool_name;

-- Git activity
SELECT git_branch, COUNT(*) as changes
FROM parts
WHERE git_branch IS NOT NULL
GROUP BY git_branch;
```

### Testing Strategy

1. **Unit Tests**: Each extraction function in isolation
2. **Integration Tests**: End-to-end with real JSON files
3. **Backfill Tests**: Validate 100% data migration
4. **Query Tests**: Validate analytics queries work

### Coding Standards

- Type hints required on all functions
- Docstrings: Google-style
- Tests: Arrange-Act-Assert pattern
- Naming: `test_<function>_<scenario>_<expected>`
