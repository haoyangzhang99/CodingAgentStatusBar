# Sprint 2: Data Quality - Data Enrichment & Optimization

**Sprint ID**: 2026-01-DQ-S2  
**Epic**: [DQ-001 - Data Quality & Architecture Improvement](../epics/epic-data-quality.md)  
**Duration**: 11-14 days (2 weeks)  
**Start Date**: 2026-01-27  
**End Date**: 2026-02-09  
**Status**: Planned  
**Depends On**: Sprint 1 (Data extraction complete)

---

## Sprint Goal

**Enrich data with computed metrics, normalization, and aggregations** to enable advanced analytics: track resource metrics (tokens, costs), implement data denormalization for query performance, and create computed aggregations.

This sprint transforms **raw data into analytics-ready metrics** for dashboards and insights.

---

## Velocity

| Métrique | Valeur |
|----------|--------|
| Points planifiés | 8 |
| Stories | 2 |
| Focus | Data Enrichment & Schema Optimization |
| Team Size | 2-3 FTE |
| Daily Capacity | ~0.6 points/day |

---

## Stories

### US-10: Add Resource Metrics

**Story ID**: DQ-010  
**Points**: 3  
**Priority**: P2 - Medium  
**Assignee**: TBD

**As a** cost analyst,  
**I want** input/output tokens, cost estimates, and resource usage tracked per session/message/tool,  
**So that** I can optimize API costs, forecast spending, and identify resource-intensive operations.

**Current State**: Token data scattered, no cost calculations → Cannot track API spend

**Acceptance Criteria**:
- [ ] Token counts extracted per tool/model/agent
- [ ] Cost calculated per session/message/part (using pricing table)
- [ ] Resource metrics aggregated at session level
- [ ] Cost trends visible in dashboards (daily/weekly/monthly)
- [ ] Alerts on cost anomalies possible (>2x baseline)
- [ ] Accuracy validated against API bills (±5%)

**Technical Notes**:

**Pricing Table**:
```sql
CREATE TABLE model_pricing (
    model_name VARCHAR PRIMARY KEY,
    vendor VARCHAR NOT NULL,
    input_token_cost_per_1k DOUBLE NOT NULL,
    output_token_cost_per_1k DOUBLE NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Example data
INSERT INTO model_pricing VALUES
('claude-3-opus', 'anthropic', 0.015, 0.075),
('claude-3-sonnet', 'anthropic', 0.003, 0.015),
('gpt-4-turbo', 'openai', 0.01, 0.03),
('gpt-4o', 'openai', 0.005, 0.015);
```

**Cost Calculation**:
```python
def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate cost in USD for given token usage."""
    pricing = get_model_pricing(model)
    input_cost = (input_tokens / 1000) * pricing.input_token_cost_per_1k
    output_cost = (output_tokens / 1000) * pricing.output_token_cost_per_1k
    return input_cost + output_cost

# Add computed columns
ALTER TABLE session_stats ADD COLUMN total_cost_usd DOUBLE;
ALTER TABLE messages ADD COLUMN message_cost_usd DOUBLE;
ALTER TABLE parts ADD COLUMN part_cost_usd DOUBLE;
```

**Resource Metrics Schema**:
```sql
-- Session-level aggregations
CREATE TABLE session_resource_metrics (
    session_id VARCHAR PRIMARY KEY,
    total_input_tokens BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    total_cost_usd DOUBLE NOT NULL DEFAULT 0.0,
    tool_call_count INT NOT NULL DEFAULT 0,
    message_count INT NOT NULL DEFAULT 0,
    avg_response_time_ms DOUBLE,
    total_execution_time_ms DOUBLE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_session_metrics_cost ON session_resource_metrics(total_cost_usd);
CREATE INDEX idx_session_metrics_tokens ON session_resource_metrics(total_input_tokens, total_output_tokens);
```

**Analytics Queries**:
```sql
-- Daily cost trends
SELECT 
    DATE(created_at) as date,
    SUM(total_cost_usd) as daily_cost,
    SUM(total_input_tokens + total_output_tokens) as daily_tokens
FROM session_resource_metrics
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Cost by model
SELECT 
    m.model_name,
    COUNT(*) as sessions,
    SUM(srm.total_cost_usd) as total_cost,
    AVG(srm.total_cost_usd) as avg_cost_per_session
FROM session_resource_metrics srm
JOIN sessions s ON srm.session_id = s.session_id
JOIN models m ON s.model_id = m.model_id
GROUP BY m.model_name
ORDER BY total_cost DESC;

-- Cost anomaly detection
WITH daily_costs AS (
    SELECT DATE(created_at) as date, SUM(total_cost_usd) as cost
    FROM session_resource_metrics
    GROUP BY DATE(created_at)
),
baseline AS (
    SELECT AVG(cost) as avg_cost, STDDEV(cost) as stddev_cost
    FROM daily_costs
)
SELECT dc.date, dc.cost, b.avg_cost
FROM daily_costs dc, baseline b
WHERE dc.cost > b.avg_cost + (2 * b.stddev_cost);  -- Anomaly: >2 std dev
```

**Files**:
- `src/opencode_status_bar/analytics/db.py` - Add resource metrics schema
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Extract token counts
- `src/opencode_status_bar/analytics/indexer/cost_calculator.py` - NEW
- `src/opencode_status_bar/analytics/indexer/aggregator.py` - NEW
- `src/opencode_status_bar/analytics/migrations/add_resource_metrics.sql` - NEW
- `tests/test_cost_calculation.py` - NEW
- `tests/test_resource_aggregation.py` - NEW

**Tasks**:
- [ ] Create model_pricing table with current prices
- [ ] Implement cost_calculator.py module
- [ ] Create session_resource_metrics table
- [ ] Implement aggregator.py for session metrics
- [ ] Update parsers to calculate costs during loading
- [ ] Backfill existing sessions with costs
- [ ] Add cost analytics queries
- [ ] Unit tests for cost calculations (±5% accuracy)
- [ ] Integration tests for aggregations
- [ ] Create cost dashboard mockup
- [ ] Validate against real API bills

---

### US-11: Implement Data Denormalization

**Story ID**: DQ-011  
**Points**: 5  
**Priority**: P2 - Medium  
**Assignee**: TBD

**As a** DBA,  
**I want** parts table denormalized from 29 cols to 7-10 logical tables,  
**So that** schema is cleaner, updates more efficient, and queries more focused.

**Current State**: parts table has 29 mixed-purpose columns → Schema bloated, slow updates

**Target State**: Normalized schema with focused tables → Clean architecture, efficient queries

**Acceptance Criteria**:
- [ ] New normalized schema designed (7-10 tables)
- [ ] Migration script created and tested
- [ ] Data integrity verified (100% data preserved)
- [ ] Query performance maintained or improved
- [ ] Rollback procedure documented and tested
- [ ] Tests cover all data transitions

**Current Schema Problem**:
```sql
-- Current parts table (29 columns - too many!)
CREATE TABLE parts (
    part_id VARCHAR PRIMARY KEY,
    session_id VARCHAR,
    part_type VARCHAR,
    content TEXT,
    
    -- Tool-specific (only used if part_type = 'tool_call')
    tool_name VARCHAR,
    tool_args JSON,
    tool_result TEXT,
    execution_time_ms DOUBLE,
    
    -- File-specific (only used if part_type = 'file_operation')
    file_path VARCHAR,
    file_operation VARCHAR,
    git_branch VARCHAR,
    git_commit VARCHAR,
    git_diff TEXT,
    
    -- Error-specific (only used if part_type = 'error')
    error_data JSON,
    error_category VARCHAR,
    
    -- Thinking-specific (only used if part_type = 'thinking')
    thinking_tokens INT,
    
    -- ... 10+ more mixed columns
);
```

**Target Normalized Schema**:
```sql
-- Core parts table (minimal, shared fields)
CREATE TABLE parts (
    part_id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    part_type VARCHAR NOT NULL,
    sequence_number INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    content TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Tool-specific data
CREATE TABLE tool_calls (
    tool_call_id VARCHAR PRIMARY KEY,
    part_id VARCHAR NOT NULL,
    tool_name VARCHAR NOT NULL,
    tool_args JSON,
    tool_result TEXT,
    execution_time_ms DOUBLE,
    status VARCHAR,  -- success, error, timeout
    FOREIGN KEY (part_id) REFERENCES parts(part_id)
);

-- File operations
CREATE TABLE file_operations (
    file_op_id VARCHAR PRIMARY KEY,
    part_id VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    operation VARCHAR NOT NULL,  -- read, write, edit, delete
    git_branch VARCHAR,
    git_commit VARCHAR,
    git_diff TEXT,
    file_size BIGINT,
    FOREIGN KEY (part_id) REFERENCES parts(part_id)
);

-- Errors
CREATE TABLE errors (
    error_id VARCHAR PRIMARY KEY,
    part_id VARCHAR NOT NULL,
    error_data JSON NOT NULL,
    error_category VARCHAR,
    error_severity VARCHAR,  -- low, medium, high, critical
    is_retryable BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (part_id) REFERENCES parts(part_id)
);

-- Thinking blocks
CREATE TABLE thinking_blocks (
    thinking_id VARCHAR PRIMARY KEY,
    part_id VARCHAR NOT NULL,
    thinking_tokens INT,
    thinking_time_ms DOUBLE,
    FOREIGN KEY (part_id) REFERENCES parts(part_id)
);

-- Messages (text/assistant/user)
CREATE TABLE text_messages (
    message_id VARCHAR PRIMARY KEY,
    part_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    token_count INT,
    FOREIGN KEY (part_id) REFERENCES parts(part_id)
);

-- Indexes for all tables
CREATE INDEX idx_parts_session ON parts(session_id);
CREATE INDEX idx_parts_type ON parts(part_type);
CREATE INDEX idx_tool_calls_name ON tool_calls(tool_name);
CREATE INDEX idx_file_ops_path ON file_operations(file_path);
CREATE INDEX idx_errors_category ON errors(error_category);
```

**Migration Strategy**:
```python
# Phase 1: Create new tables (no data yet)
# Phase 2: Migrate data from parts to new tables
# Phase 3: Validate data integrity (counts match)
# Phase 4: Update queries to use new tables
# Phase 5: Deprecate old parts table (rename to parts_legacy)
# Phase 6: Monitor for 1 week, then drop parts_legacy
```

**Data Integrity Validation**:
```sql
-- Verify counts match
SELECT 
    COUNT(*) as old_count,
    (SELECT COUNT(*) FROM parts) as new_core_count,
    (SELECT COUNT(*) FROM tool_calls) as tool_count,
    (SELECT COUNT(*) FROM file_operations) as file_count,
    (SELECT COUNT(*) FROM errors) as error_count
FROM parts_legacy;

-- Verify no data loss
SELECT 
    pl.part_id,
    CASE 
        WHEN p.part_id IS NULL THEN 'MISSING IN NEW SCHEMA'
        ELSE 'OK'
    END as status
FROM parts_legacy pl
LEFT JOIN parts p ON pl.part_id = p.part_id
WHERE p.part_id IS NULL;
```

**Query Migration Examples**:
```sql
-- OLD: Get tool calls with execution time
SELECT part_id, tool_name, execution_time_ms
FROM parts
WHERE part_type = 'tool_call';

-- NEW: Same query with normalized schema
SELECT p.part_id, tc.tool_name, tc.execution_time_ms
FROM parts p
JOIN tool_calls tc ON p.part_id = tc.part_id;

-- OLD: Get errors by category
SELECT error_category, COUNT(*) as count
FROM parts
WHERE part_type = 'error'
GROUP BY error_category;

-- NEW: Same query
SELECT error_category, COUNT(*) as count
FROM errors
GROUP BY error_category;
```

**Files**:
- `src/opencode_status_bar/analytics/db.py` - New normalized schema
- `src/opencode_status_bar/analytics/migrations/denormalize_parts.sql` - NEW
- `src/opencode_status_bar/analytics/migrations/rollback_denormalization.sql` - NEW
- `src/opencode_status_bar/analytics/indexer/parsers.py` - Update to insert into new tables
- `src/opencode_status_bar/analytics/queries/` - Update all query files
- `tests/test_denormalization.py` - NEW
- `tests/test_migration_integrity.py` - NEW

**Tasks**:
- [ ] Design normalized schema (7-10 tables)
- [ ] Create new table definitions in db.py
- [ ] Write migration script (parts → new tables)
- [ ] Write rollback script (new tables → parts)
- [ ] Update parsers to use new schema
- [ ] Update all existing queries to use new tables
- [ ] Run migration on test database
- [ ] Validate data integrity (100% preserved)
- [ ] Performance benchmark queries (before/after)
- [ ] Unit tests for migration logic
- [ ] Integration tests for new schema
- [ ] Document schema changes in README
- [ ] Create rollback procedure

---

## Sprint Backlog

| ID | Story | Points | Status | Assignee | Week |
|----|-------|--------|--------|----------|------|
| DQ-010 | Resource Metrics | 3 | To Do | TBD | Week 1 |
| DQ-011 | Data Denormalization | 5 | To Do | TBD | Week 1-2 |
| **Total** | | **8** | | | |

---

## Daily Schedule

### Week 1: Resource Metrics + Denormalization Design

**Day 1 (Mon)**: DQ-010 Pricing + Cost Calculator
- Morning: Create model_pricing table + data
- Afternoon: Implement cost_calculator.py module

**Day 2 (Tue)**: DQ-010 Session Metrics
- Morning: Create session_resource_metrics table
- Afternoon: Implement aggregator.py

**Day 3 (Wed)**: DQ-010 Backfill + Validation
- Morning: Backfill existing sessions with costs
- Afternoon: Validate against API bills + tests

**Day 4 (Thu)**: DQ-011 Schema Design
- Morning: Design normalized schema (7-10 tables)
- Afternoon: Create table definitions + indexes

**Day 5 (Fri)**: DQ-011 Migration Script
- Morning: Write migration script (data transfer)
- Afternoon: Write rollback script + validation queries

### Week 2: Denormalization Implementation + Validation

**Day 6 (Mon)**: DQ-011 Parser Updates
- Morning: Update parsers to use new tables
- Afternoon: Update bulk_loader and hybrid.py

**Day 7 (Tue)**: DQ-011 Query Migration
- Morning: Update all query files to new schema
- Afternoon: Update dashboard queries

**Day 8 (Wed)**: DQ-011 Testing
- Morning: Run migration on test database
- Afternoon: Validate data integrity (100%)

**Day 9 (Thu)**: DQ-011 Performance Validation
- Morning: Benchmark queries (before/after)
- Afternoon: Integration tests

**Day 10 (Fri)**: DQ-011 Rollback Testing
- Morning: Test rollback procedure
- Afternoon: Document schema changes

**Day 11 (Sat)**: Sprint Validation
- Morning: Final integration tests
- Afternoon: Sprint review prep

---

## Definition of Done (Sprint)

### Code Quality
- [ ] All tests pass (`make test`)
- [ ] Coverage >= 80% on new code
- [ ] No lint errors (`make lint`)
- [ ] Code reviewed and approved

### Data Quality
- [ ] 100% of sessions have cost calculations
- [ ] Cost accuracy ±5% vs API bills
- [ ] Migration preserves 100% of data
- [ ] No orphaned records after migration

### Documentation
- [ ] Schema changes documented
- [ ] Migration procedure documented
- [ ] Rollback procedure documented
- [ ] Cost calculation formula documented
- [ ] Query migration guide created

### Validation
- [ ] Cost analytics queries work correctly
- [ ] Query performance maintained or improved
- [ ] Data integrity validated (counts match)
- [ ] Rollback tested successfully

---

## Technical Dependencies

```
Sprint 1 (Extraction) ──► DQ-010 (Metrics) ───┐
                                              │
                          DQ-011 (Schema) ────┼──► Sprint 3
                                              │
                          (Can run parallel)  │
```

**Critical Path**: Sprint 1 → DQ-011 (blocks Sprint 3 queries)

**Parallelizable**: DQ-010 can start immediately after Sprint 1

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Migration causes data loss | Low | Critical | Backup before migration, extensive validation, rollback ready |
| Query performance degrades | Medium | High | Benchmark before/after, optimize indexes, rollback if needed |
| Cost calculations inaccurate | Medium | High | Validate against API bills, manual spot checks, ±5% tolerance |
| Pricing table outdated | High | Low | Document update procedure, monitor API pricing changes |
| Migration takes too long | Medium | Medium | Incremental migration, progress tracking, parallel processing |
| Rollback fails | Low | Critical | Test rollback on copy first, document procedure, practice runs |

---

## Success Criteria

### Sprint-Level Metrics
- [ ] All 2 stories completed (8 points)
- [ ] Zero critical bugs introduced
- [ ] Test coverage >= 80%
- [ ] Migration successful (100% data preserved)

### Business Impact
- [ ] Cost tracking enabled (daily/weekly/monthly)
- [ ] Spend forecasting possible
- [ ] Cost anomaly detection enabled
- [ ] Schema 70% cleaner (29 cols → 7-10 tables)
- [ ] Query performance maintained or improved

### Data Completeness
- [ ] 100% sessions have cost data
- [ ] 100% parts migrated to new schema
- [ ] 0 orphaned records
- [ ] Cost accuracy ±5%

---

## References

- **Epic**: [epic-data-quality.md](../epics/epic-data-quality.md)
- **Sprint 0**: [2026-01-data-quality-sprint0.md](2026-01-data-quality-sprint0.md)
- **Sprint 1**: [2026-01-data-quality-sprint1.md](2026-01-data-quality-sprint1.md)
- **Audit Report**: [data-audit-comprehensive-2026-01-10.md](../../audit-reports/data-audit-comprehensive-2026-01-10.md)

---

## Sprint Review Checklist

**Demos**:
- [ ] Show cost analytics dashboard (daily/weekly trends)
- [ ] Show cost by model breakdown
- [ ] Show cost anomaly detection
- [ ] Show new normalized schema (ER diagram)
- [ ] Show query performance comparison (before/after)
- [ ] Show data integrity validation (100% preserved)

**Metrics**:
- [ ] Velocity: 8 points completed
- [ ] Migration success rate: 100%
- [ ] Cost accuracy: ±5%
- [ ] Query performance: maintained or improved

**Feedback**:
- [ ] Finance team sign-off on cost tracking
- [ ] DBA sign-off on schema design
- [ ] Analyst feedback on query performance
- [ ] Developer feedback on new schema

---

## Retrospective Topics

- Migration strategy effectiveness?
- Cost calculation accuracy challenges?
- Schema design trade-offs?
- Query performance optimization learnings?
- Readiness for Sprint 3 (validation)?
- Action items for next sprint?

---

## Notes for Developers

### Setup

```bash
# Checkout branch
cd worktrees/feature/data-quality

# Backup database before migration
cp analytics.duckdb analytics.duckdb.backup

# Run migration
python scripts/migrate_denormalize.py

# Validate migration
python scripts/validate_migration.py

# Rollback if needed
python scripts/rollback_migration.py
```

### Key Files

```
src/opencode_status_bar/analytics/
├── db.py                           # New schema (DQ-011)
├── indexer/
│   ├── parsers.py                 # Updated for new tables
│   ├── cost_calculator.py         # NEW - Cost calculations (DQ-010)
│   ├── aggregator.py              # NEW - Session metrics (DQ-010)
│   └── migrations/
│       ├── add_resource_metrics.sql
│       ├── denormalize_parts.sql
│       └── rollback_denormalization.sql
```

### Cost Analytics Queries

```sql
-- Daily spend
SELECT DATE(created_at) as date, SUM(total_cost_usd) as cost
FROM session_resource_metrics
GROUP BY DATE(created_at);

-- Top 10 expensive sessions
SELECT session_id, total_cost_usd, total_input_tokens + total_output_tokens as tokens
FROM session_resource_metrics
ORDER BY total_cost_usd DESC
LIMIT 10;

-- Cost by model
SELECT m.model_name, SUM(srm.total_cost_usd) as total_cost
FROM session_resource_metrics srm
JOIN sessions s ON srm.session_id = s.session_id
JOIN models m ON s.model_id = m.model_id
GROUP BY m.model_name;
```

### Testing Strategy

1. **Unit Tests**: Cost calculation logic, migration functions
2. **Integration Tests**: End-to-end with new schema
3. **Migration Tests**: Data integrity validation (100%)
4. **Performance Tests**: Query benchmarks (before/after)
5. **Rollback Tests**: Verify rollback works correctly

### Coding Standards

- Type hints required on all functions
- Docstrings: Google-style
- Tests: Arrange-Act-Assert pattern
- Naming: `test_<function>_<scenario>_<expected>`
