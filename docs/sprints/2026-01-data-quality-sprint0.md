# Sprint 0: Data Quality - P0 Critical Fixes

**Sprint ID**: 2026-01-DQ-S0  
**Epic**: [DQ-001 - Data Quality & Architecture Improvement](../epics/epic-data-quality.md)  
**Duration**: 3-5 days  
**Start Date**: 2026-01-13  
**End Date**: 2026-01-17  
**Status**: Planned

---

## Sprint Goal

**Fix all P0 blockers** that prevent accurate analytics and Plan 45 functionality: load Plan 45 tables, fix token calculation, eliminate race conditions, add critical indexes, and fix error_data type.

This sprint removes **5 critical blockers** and establishes the foundation for all subsequent data quality work.

---

## Velocity

| Métrique | Valeur |
|----------|--------|
| Points planifiés | 14 |
| Stories | 5 |
| Focus | P0 Critical Fixes |
| Team Size | 2-3 FTE |
| Daily Capacity | ~3 points/day |

---

## Stories

### US-1: Fix Root Trace Token Calculation

**Story ID**: DQ-001  
**Points**: 3  
**Priority**: P0 - Critical  
**Assignee**: TBD

**As a** system analyst,  
**I want** to extract root_token_count from JSON and calculate correct token usage,  
**So that** cost reports accurately reflect API token consumption.

**Current State**: All root_tokens hardcoded to 0 → Cost calculations 100% wrong

**Acceptance Criteria**:
- [ ] Token count extracted from root traces JSON (`usage.input_tokens + usage.output_tokens`)
- [ ] Stored in `session_stats.root_tokens` correctly
- [ ] Cost calculations updated to use real values (not hardcoded 0)
- [ ] Backward compatible with existing data (default to 0 if missing)
- [ ] Unit tests (100% coverage for token extraction)
- [ ] Performance validated (<50ms per calculation)

**Technical Notes**:
```python
# Current (BROKEN):
root_tokens = 0  # Hardcoded!

# Target:
root_tokens = sum(
    trace.get('usage', {}).get('input_tokens', 0) + 
    trace.get('usage', {}).get('output_tokens', 0)
    for trace in root_traces
)
```

**Files**:
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Add token extraction logic
- `src/opencode_status_bar/analytics/db.py` - Update session_stats insert
- `tests/test_token_calculation.py` - NEW

**Tasks**:
- [ ] Add `extract_root_tokens()` function in parsers.py
- [ ] Update `SessionStats` parsing to call extraction
- [ ] Add unit tests for token extraction edge cases
- [ ] Backfill existing sessions (migration script)
- [ ] Validate cost reports show real values

---

### US-2: Implement Plan 45 Data Loading

**Story ID**: DQ-002  
**Points**: 5  
**Priority**: P0 - Critical  
**Assignee**: TBD

**As a** analytics user,  
**I want** exchanges and exchange_traces to be loaded from JSON storage,  
**So that** Plan 45 tracing architecture provides complete data for timeline views.

**Current State**: 
- `exchanges` table: 0 records
- `exchange_traces` table: 0 records
- Plan 45 UI completely broken

**Acceptance Criteria**:
- [ ] `exchanges` table populated from JSON (1 row per exchange)
- [ ] `exchange_traces` table populated from JSON (1 row per trace)
- [ ] Both bulk loading and real-time loading work
- [ ] No duplicates or data loss during loading
- [ ] Integration tests pass (bulk + real-time scenarios)
- [ ] Performance validated (>1000 records/sec)

**Technical Notes**:
```python
# Expected data flow:
JSON File → Parser → exchanges + exchange_traces tables

# Validation query:
SELECT 
    COUNT(DISTINCT e.exchange_id) as exchanges_count,
    COUNT(t.trace_id) as traces_count
FROM exchanges e
LEFT JOIN exchange_traces t ON e.exchange_id = t.exchange_id
```

**Files**:
- `src/opencode_status_bar/analytics/indexer/bulk_loader.py` - Add Plan 45 loading
- `src/opencode_status_bar/analytics/indexer/hybrid.py` - Add real-time loading
- `src/opencode_status_bar/analytics/indexer/handlers.py` - Add exchange handlers
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Add exchange parsing
- `tests/test_plan45_loading.py` - NEW

**Tasks**:
- [ ] Design exchange/trace parsing logic
- [ ] Implement bulk loader for Plan 45 tables
- [ ] Implement real-time handler for Plan 45
- [ ] Add integration tests (bulk + real-time)
- [ ] Validate no duplicates or data loss
- [ ] Benchmark loading performance

---

### US-3: Add Race Condition Handling

**Story ID**: DQ-003  
**Points**: 3  
**Priority**: P0 - Critical  
**Assignee**: TBD

**As a** system administrator,  
**I want** bulk loading and real-time watching to be properly synchronized,  
**So that** no files are missed or duplicated during the transition phase.

**Current State**: Phase boundary unprotected → Files can be missed or duplicated

**Acceptance Criteria**:
- [ ] Bulk loading phase has exclusive lock (no real-time during bulk)
- [ ] Real-time watching waits for bulk completion signal
- [ ] Transition marked clearly in logs with timestamps
- [ ] Integration tests verify no file loss (100 files loaded correctly)
- [ ] Recovery procedure documented (how to restart safely)
- [ ] Monitoring dashboard shows phase status (bulk/real-time)

**Technical Notes**:
```python
# Solution: Use file-based lock + sync state table
class SyncState:
    def acquire_bulk_lock(self) -> bool
    def release_bulk_lock(self) -> None
    def wait_for_bulk_completion(self) -> None
    def is_bulk_phase(self) -> bool
```

**Files**:
- `src/opencode_status_bar/analytics/indexer/bulk_loader.py` - Add lock acquisition
- `src/opencode_status_bar/analytics/indexer/sync_state.py` - NEW (lock manager)
- `src/opencode_status_bar/analytics/indexer/watcher.py` - Add lock check
- `tests/test_race_condition.py` - NEW

**Tasks**:
- [ ] Create `SyncState` class with lock management
- [ ] Update bulk_loader to acquire/release lock
- [ ] Update watcher to check lock before processing
- [ ] Add integration test: bulk + real-time overlap
- [ ] Add monitoring for phase transitions
- [ ] Document recovery procedure

---

### US-4: Add Missing Critical Indexes

**Story ID**: DQ-004  
**Points**: 2  
**Priority**: P0 - Critical  
**Assignee**: TBD

**As a** data analyst,  
**I want** queries on agents, models, types, tools to be fast (<10ms),  
**So that** dashboards render responsively even with large datasets.

**Current State**: 8+ missing indexes → Queries take 100-500ms instead of <10ms

**Acceptance Criteria**:
- [ ] 8+ composite indexes created on critical tables
- [ ] Query performance improved 50x (100-500ms → <10ms)
- [ ] Explain plans reviewed (all use indexes)
- [ ] Indexes validated with real production data
- [ ] Migrations idempotent (can run multiple times safely)
- [ ] Performance benchmarks documented (before/after)

**Indexes to Add**:
```sql
-- Critical indexes for query performance
CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name);
CREATE INDEX IF NOT EXISTS idx_models_vendor ON models(vendor);
CREATE INDEX IF NOT EXISTS idx_parts_type ON parts(part_type);
CREATE INDEX IF NOT EXISTS idx_parts_session ON parts(session_id);
CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(tool_name);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_session ON exchanges(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_exchange ON exchange_traces(exchange_id);
```

**Files**:
- `src/opencode_status_bar/analytics/db.py` - Add index creation
- `src/opencode_status_bar/analytics/migrations/add_indexes.sql` - NEW
- `tests/test_indexes.py` - NEW

**Tasks**:
- [ ] Add index creation in db.py init
- [ ] Create migration SQL file
- [ ] Test migration on existing DB
- [ ] Run EXPLAIN QUERY PLAN on key queries
- [ ] Benchmark queries before/after
- [ ] Document performance improvements

---

### US-5: Change error_data Type to JSON

**Story ID**: DQ-005  
**Points**: 1  
**Priority**: P0 - Critical  
**Assignee**: TBD

**As a** error analyst,  
**I want** error_data stored as JSON instead of VARCHAR,  
**So that** I can filter and aggregate on specific error fields.

**Current State**: error_data is VARCHAR → Cannot query error fields directly

**Acceptance Criteria**:
- [ ] Schema migration: error_data VARCHAR → JSON type
- [ ] Existing data converted correctly (parse JSON strings)
- [ ] Parsing updated to handle JSON insertion
- [ ] Unit tests for error_data handling (valid/invalid JSON)
- [ ] Backward compatibility verified (old data still readable)
- [ ] Rollback procedure documented

**Technical Notes**:
```sql
-- Migration steps:
ALTER TABLE parts ADD COLUMN error_data_json JSON;
UPDATE parts SET error_data_json = CAST(error_data AS JSON) WHERE error_data IS NOT NULL;
ALTER TABLE parts DROP COLUMN error_data;
ALTER TABLE parts RENAME COLUMN error_data_json TO error_data;
```

**Files**:
- `src/opencode_status_bar/analytics/db.py` - Update schema
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Update error parsing
- `tests/test_error_data.py` - NEW

**Tasks**:
- [ ] Create migration script (VARCHAR → JSON)
- [ ] Update parsers to insert JSON directly
- [ ] Test migration on real data
- [ ] Add unit tests for JSON parsing
- [ ] Validate queries on error_data fields work
- [ ] Document rollback procedure

---

## Sprint Backlog

| ID | Story | Points | Status | Assignee | Day |
|----|-------|--------|--------|----------|-----|
| DQ-001 | Fix Root Token Calculation | 3 | To Do | TBD | Day 1 |
| DQ-002 | Implement Plan 45 Loading | 5 | To Do | TBD | Day 2-3 |
| DQ-003 | Race Condition Handling | 3 | To Do | TBD | Day 3-4 |
| DQ-004 | Add Missing Indexes | 2 | To Do | TBD | Day 4 |
| DQ-005 | error_data Type to JSON | 1 | To Do | TBD | Day 5 |
| **Total** | | **14** | | | |

---

## Daily Schedule

### Day 1 (Mon): Token Calculation
- Morning: DQ-001 implementation (parsers + db)
- Afternoon: DQ-001 tests + validation

### Day 2 (Tue): Plan 45 Loading (Part 1)
- Morning: DQ-002 design + bulk loader
- Afternoon: DQ-002 real-time handler

### Day 3 (Wed): Plan 45 Loading (Part 2) + Race Conditions
- Morning: DQ-002 integration tests + validation
- Afternoon: DQ-003 implementation (sync state + locks)

### Day 4 (Thu): Race Conditions + Indexes
- Morning: DQ-003 tests + monitoring
- Afternoon: DQ-004 implementation (index creation + benchmarks)

### Day 5 (Fri): error_data Migration
- Morning: DQ-005 migration script + testing
- Afternoon: Sprint review prep + final validation

---

## Definition of Done (Sprint)

### Code Quality
- [ ] All tests pass (`make test`)
- [ ] Coverage >= 80% on new code
- [ ] No lint errors (`make lint`)
- [ ] Code reviewed and approved

### Documentation
- [ ] All functions have docstrings
- [ ] Migration procedures documented
- [ ] Rollback procedures documented
- [ ] Performance benchmarks recorded

### Validation
- [ ] Plan 45 tables populated with real data
- [ ] Token calculations show real values (not 0)
- [ ] No race conditions in 10 test runs
- [ ] Query performance <10ms on indexed queries
- [ ] error_data JSON queries work

---

## Technical Dependencies

```
DQ-001 (Tokens) ────┐
                    │
DQ-002 (Plan 45) ───┼──► DQ-003 (Race) ──► Sprint 1
                    │
DQ-004 (Indexes) ───┤
                    │
DQ-005 (error_data)─┘
```

**Critical Path**: DQ-002 (Plan 45) → DQ-003 (Race Conditions) → Sprint 1

**Parallelizable**: DQ-001, DQ-004, DQ-005 can be done in parallel

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Data loss during Plan 45 loading | Medium | Critical | Backup DB before, test on copy first, incremental loading |
| Performance regression after indexes | Low | High | Benchmark before/after, EXPLAIN plans, rollback ready |
| Race condition still exists after fix | Low | Critical | Stress testing (100 files), integration tests, monitoring |
| error_data migration breaks queries | Low | Medium | Test migration on copy, rollback procedure, backward compat |
| Token calculation wrong for edge cases | Medium | High | Extensive unit tests, validate against API logs |

---

## Success Criteria

### Sprint-Level Metrics
- [ ] All 5 P0 stories completed (14 points)
- [ ] Zero critical bugs introduced
- [ ] Test coverage >= 80%
- [ ] All migrations tested on production data

### Business Impact
- [ ] Plan 45 UI shows data (not empty)
- [ ] Cost reports show real token values (not 0)
- [ ] Queries 50x faster (<10ms vs 100-500ms)
- [ ] No data loss during bulk/real-time transition
- [ ] Error analytics queries work on JSON fields

---

## References

- **Epic**: [epic-data-quality.md](../epics/epic-data-quality.md)
- **Audit Report**: [data-audit-comprehensive-2026-01-10.md](../../audit-reports/data-audit-comprehensive-2026-01-10.md)
- **Architecture**: `src/opencode_status_bar/analytics/`
- **Database Schema**: `src/opencode_status_bar/analytics/db.py`

---

## Sprint Review Checklist

**Demos**:
- [ ] Show Plan 45 UI with real data loaded
- [ ] Show cost report with real token counts
- [ ] Show query performance before/after indexes
- [ ] Show race condition test passing (bulk + real-time)
- [ ] Show error_data JSON queries working

**Metrics**:
- [ ] Velocity: 14 points completed
- [ ] Test coverage report (>80%)
- [ ] Performance benchmarks (50x improvement)
- [ ] Zero critical bugs

**Feedback**:
- [ ] Stakeholder sign-off on Plan 45 data
- [ ] Team confidence in race condition fix
- [ ] Performance improvement validated by analysts

---

## Retrospective Topics

- What went well with P0 fixes?
- Any blockers encountered?
- Performance optimization learnings?
- Readiness for Sprint 1 (data extraction)?
- Action items for next sprint?

---

## Notes for Developers

### Setup

```bash
# Checkout branch
cd worktrees/feature/data-quality

# Run tests
make test

# Check DB
duckdb analytics.duckdb "SHOW TABLES;"
```

### Key Files

```
src/opencode_status_bar/analytics/
├── db.py                           # Schema changes (US-4, US-5)
├── indexer/
│   ├── parsers.py                 # Token extraction (US-1), Plan 45 (US-2)
│   ├── bulk_loader.py             # Plan 45 loading (US-2), locks (US-3)
│   ├── hybrid.py                  # Real-time loading (US-2)
│   ├── sync_state.py              # NEW - Lock manager (US-3)
│   └── handlers.py                # Plan 45 handlers (US-2)
```

### Testing Strategy

1. **Unit Tests**: Each parser/function in isolation
2. **Integration Tests**: Bulk + real-time together
3. **Performance Tests**: Query benchmarks before/after
4. **Stress Tests**: 100 files bulk + real-time overlap

### Coding Standards

- Type hints required on all functions
- Docstrings: Google-style
- Tests: Arrange-Act-Assert pattern
- Naming: `test_<function>_<scenario>_<expected>`
