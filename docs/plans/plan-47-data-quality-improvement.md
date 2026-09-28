# Plan 47: Data Quality Improvement - Complete Roadmap

**Plan ID**: PLAN-047  
**Epic**: DQ-001 - Data Quality & Architecture Improvement  
**Version**: 1.0  
**Date**: January 10, 2026  
**Owner**: Engineering Team  
**Status**: Ready for Execution

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Strategic Objectives](#3-strategic-objectives)
4. [Sprint Roadmap](#4-sprint-roadmap)
5. [Detailed Sprint Plans](#5-detailed-sprint-plans)
6. [Technical Approach](#6-technical-approach)
7. [Risk Assessment](#7-risk-assessment)
8. [Resource Requirements](#8-resource-requirements)
9. [Success Metrics](#9-success-metrics)
10. [Stakeholder Communication Plan](#10-stakeholder-communication-plan)
11. [Implementation Checklist](#11-implementation-checklist)
12. [Appendices](#12-appendices)

---

## 1. Executive Summary

### 1.1 Current Situation

OpenCode Status Bar's analytics platform processes **~232K JSON files** (877 sessions, 43,060 messages, 187,331 parts) representing **2GB of data**. Following a comprehensive audit on January 10, 2026, we've identified critical gaps in data quality and availability:

| Metric | Current State | Issue |
|--------|--------------|-------|
| **Data Coverage** | 70% of JSON fields | 30% data loss, 430K missing data points |
| **P0 Blockers** | 5 critical issues | Plan 45 broken, costs wrong, race conditions |
| **Query Performance** | 100-500ms | 8+ missing indexes, 50x slower than target |
| **Available Dashboards** | 25 dashboards | 15+ blocked by data gaps |
| **Cost Accuracy** | 100% wrong | Root tokens hardcoded to 0 |

**Business Impact**: 
- Plan 45 tracing UI completely non-functional (0 records in critical tables)
- Cost reports showing incorrect values (all root tokens = 0)
- Risk of data loss during bulk/real-time loading transition
- Analytics capability limited to 40% of potential
- Performance issues blocking user adoption

### 1.2 Strategic Objectives

This 6-week initiative will transform our analytics platform through **4 focused sprints**:

1. **Sprint 0 (Week 1)**: Fix all 5 P0 blockers - Enable basic functionality
2. **Sprint 1 (Week 2)**: Recover 430K lost data points - Enable rich analytics
3. **Sprint 2 (Weeks 3-4)**: Enrich data with computed metrics - Unlock new features
4. **Sprint 3 (Weeks 5-6)**: Validate integrity and go live - Production deployment

**Target State**:
- ✅ 100% data completeness (from 70%)
- ✅ All P0 blockers fixed (5 critical issues resolved)
- ✅ Query performance <250ms (50% improvement)
- ✅ 40+ dashboards enabled (from 25)
- ✅ Production-ready with full monitoring

### 1.3 Business Impact

| Impact Area | Before | After | Value |
|-------------|--------|-------|-------|
| **Data Completeness** | 70% fields | 100% fields | +430K data points recovered |
| **Cost Tracking** | ❌ Broken | ✅ Accurate ±5% | Critical for budget |
| **Query Performance** | 100-500ms | <250ms | 50-75% faster |
| **Available Features** | 25 dashboards | 40+ dashboards | +60% capability |
| **Plan 45 Tracing** | ❌ 0 records | ✅ Fully functional | Timeline views enabled |
| **Error Analytics** | ❌ No insights | ✅ 15+ categories | SLA monitoring enabled |
| **Resource Monitoring** | ❌ No data | ✅ CPU, memory, cache | Performance optimization |

**ROI**: ~$50K savings/year through accurate cost tracking + performance optimization reducing API calls by 15-20%

### 1.4 Timeline & Resources

| Phase | Duration | Points | Team Size | Key Deliverable |
|-------|----------|--------|-----------|----------------|
| **Sprint 0: P0 Fixes** | 5 days | 14 pts | 2-3 FTE | All blockers removed |
| **Sprint 1: Extraction** | 7 days | 7 pts | 2 FTE | 430K data points recovered |
| **Sprint 2: Enrichment** | 14 days | 8 pts | 2-3 FTE | Cost tracking + schema optimization |
| **Sprint 3: Go-Live** | 9 days | 5 pts | 3 FTE | Production deployment |
| **TOTAL** | **6 weeks** | **34 pts** | **2.5 avg FTE** | **100% data quality** |

**Budget**: 
- Engineering: ~140 dev-hours × $150/hr = $21,000
- Infrastructure: Minimal (existing DuckDB)
- **Total Investment**: ~$25,000

---

## 2. Problem Statement

### 2.1 Audit Findings Summary

Our comprehensive audit revealed the following critical issues blocking analytics capabilities:

#### 2.1.1 **P0 Critical Blockers** 🔴

| # | Issue | Current State | Impact | Severity |
|---|-------|--------------|--------|----------|
| **1** | **Plan 45 Tables Empty** | `exchanges`: 0 records<br>`exchange_traces`: 0 records | Plan 45 UI completely broken | CRITICAL |
| **2** | **Root Tokens Wrong** | All `root_tokens` = 0 | Cost calculations 100% inaccurate | CRITICAL |
| **3** | **Race Conditions** | Bulk/real-time overlap unprotected | Data loss or duplication risk | CRITICAL |
| **4** | **Missing Indexes** | 8+ critical indexes absent | Queries 50x slower (100-500ms) | HIGH |
| **5** | **error_data Type** | VARCHAR instead of JSON | Cannot filter on error fields | HIGH |

#### 2.1.2 **Quantified Data Loss** 📉

```
VOLUMETRIC ANALYSIS:
├─ Total JSON files: ~232K (2.0GB on disk)
├─ JSON fields defined: ~2,000+ unique fields
├─ Fields captured in DB: ~1,400 (70%)
└─ Fields LOST: ~430K field-level data points (30% loss)

DATA COMPLETENESS BY TYPE:
├─ TEXT parts: 75% coverage (length, format, embeddings missing)
├─ TOOL calls: 80% coverage (timing, retries, cache stats missing)
├─ REASONING: 65% coverage (budget, depth, tokens missing)
├─ STEP events: 85% coverage (CPU, memory metrics missing)
├─ PATCHES: 60% coverage (commit message, author, branch missing)
├─ COMPACTION: 40% coverage (compression stats missing)
└─ FILES: 55% coverage (size, OCR, source missing)

BUSINESS IMPACT:
├─ Project filtering: ❌ Impossible (root_path not stored)
├─ Error analytics: ❌ No categorization (error_type not classified)
├─ Performance tracking: ❌ No timing data (execution_time missing)
├─ Version control: ❌ No git correlation (branch, commit missing)
├─ Cost forecasting: ❌ No estimates (tool_cost not tracked)
└─ Resource monitoring: ❌ No metrics (CPU, memory not captured)
```

### 2.2 Root Cause Analysis

| Issue | Root Cause | Technical Debt | Priority |
|-------|-----------|----------------|----------|
| **Plan 45 Empty** | No loader implementation | Design incomplete from Plan 45 | P0 |
| **Token Count Wrong** | Hardcoded to 0 | Quick fix never corrected | P0 |
| **Race Conditions** | No phase synchronization | Oversight in hybrid architecture | P0 |
| **Missing Indexes** | Schema evolution oversight | Iterative schema changes | P0 |
| **error_data Type** | Early design decision | Schema migration needed | P0 |
| **Data Loss (30%)** | Incomplete parsing logic | Gradual feature additions | P1 |

### 2.3 Impact on Features

**Blocked Features** (Cannot implement until fixed):
1. ❌ Project-specific analytics (no root_path)
2. ❌ Error rate monitoring and SLA tracking (no error classification)
3. ❌ Performance optimization dashboard (no timing metrics)
4. ❌ Version control correlation (no git metadata)
5. ❌ Cost forecasting and budget alerts (no cost estimates)
6. ❌ Plan 45 timeline view (tables empty)
7. ❌ Resource utilization monitoring (no CPU/memory)
8. ❌ Semantic search (no embeddings)
9. ❌ Compression efficiency tracking (no stats)
10. ❌ File operation analytics (no file metadata)

**Partially Working** (Degraded experience):
- 🟡 Session analytics (missing project context)
- 🟡 Tool usage tracking (missing timing data)
- 🟡 Message browsing (missing root paths for filtering)
- 🟡 Security alerts (working but could be richer)

---

## 3. Strategic Objectives

### 3.1 Primary Goals

#### Goal 1: Fix All P0 Blockers (Sprint 0)
**Target**: 100% P0 issues resolved in 5 days

| Blocker | Fix | Success Criterion |
|---------|-----|------------------|
| Plan 45 tables empty | Implement exchange/trace loaders | >0 records in both tables |
| Root tokens = 0 | Extract from JSON | 95%+ sessions have real token counts |
| Race conditions | Add phase synchronization | 0 data loss in 100 test runs |
| Missing indexes | Create 8+ critical indexes | Queries <10ms on indexed fields |
| error_data VARCHAR | Migrate to JSON type | Can filter on error.type, error.code |

#### Goal 2: Recover Lost Data (Sprint 1)
**Target**: 430K data points extracted and stored

| Data Category | Fields to Extract | Target Completeness |
|---------------|------------------|---------------------|
| Project context | root_path | 100% messages |
| Error details | error_category, error_severity | 95%+ errors classified |
| Performance | execution_time_ms | 100% tool calls |
| Version control | git_branch, git_commit, git_diff | 70%+ file operations |

#### Goal 3: Enrich Analytics (Sprint 2)
**Target**: Enable 12+ new dashboard types

| Enrichment | New Capability | Business Value |
|-----------|---------------|----------------|
| Resource metrics | Cost tracking per session/tool/model | Budget optimization |
| Schema normalization | 7-10 focused tables vs. 1 bloated | Query performance +20% |
| Cost calculations | Pricing table + cost formulas | Spend forecasting |
| Aggregations | Pre-computed session/daily stats | Dashboard load time -50% |

#### Goal 4: Production Readiness (Sprint 3)
**Target**: 100% data integrity validated, zero regressions

| Validation | Criterion | Monitoring |
|-----------|----------|------------|
| Data completeness | 15+ automated health checks | Daily reports + alerts |
| Query performance | <250ms latency (50% improvement) | Prometheus metrics |
| Zero data loss | 100% migration integrity | Grafana dashboards |
| Deployment success | Tested rollback procedure | Production smoke tests |

### 3.2 Success Definition

**Sprint 0 Success** = All P0 fixed + 0 new critical bugs + test coverage >80%  
**Sprint 1 Success** = 430K data points recovered + 100% backfill + 0 data loss  
**Sprint 2 Success** = Cost tracking live + schema optimized + 100% data preserved  
**Sprint 3 Success** = Production deployed + monitoring active + stakeholder sign-off  

**Epic Success** = 
- ✅ 100% data completeness (from 70%)
- ✅ Query performance <250ms (from 100-500ms)
- ✅ 40+ dashboards available (from 25)
- ✅ Cost tracking accurate ±5% (from 100% wrong)
- ✅ Production uptime >99.9% for 7 days post-deployment

---

## 4. Sprint Roadmap

### 4.1 Visual Timeline

```
┌────────────────────────────────────────────────────────────────────────────┐
│ PLAN 47: DATA QUALITY IMPROVEMENT - 6 WEEK ROADMAP                        │
└────────────────────────────────────────────────────────────────────────────┘

WEEK 1: Sprint 0 - P0 CRITICAL FIXES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌───────────┬───────────┬───────────┬───────────┬───────────┐
│ Mon       │ Tue       │ Wed       │ Thu       │ Fri       │
├───────────┼───────────┼───────────┼───────────┼───────────┤
│ US-1      │ US-2      │ US-2      │ US-3      │ US-5      │
│ Tokens    │ Plan 45   │ Plan 45   │ Race      │ error_data│
│ (3 pts)   │ Load (5)  │ + US-4    │ Cond (3)  │ (1 pt)    │
│           │           │ Indexes   │           │           │
│           │           │ (2 pts)   │           │           │
└───────────┴───────────┴───────────┴───────────┴───────────┘
Milestone 1: ✅ All P0 blockers fixed, Plan 45 functional

WEEK 2: Sprint 1 - DATA EXTRACTION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌───────────┬───────────┬───────────┬───────────┬───────────┬──────┬──────┐
│ Mon       │ Tue       │ Wed       │ Thu       │ Fri       │ Sat  │ Sun  │
├───────────┼───────────┼───────────┼───────────┼───────────┼──────┼──────┤
│ US-6      │ US-6      │ US-7      │ US-7      │ US-8      │ US-9 │ Valid│
│ root_path │ Validate  │ Error     │ Error     │ Tool      │ Git  │ Sprint│
│ (2 pts)   │           │ Class (3) │ Backfill  │ Time (2)  │ Meta │      │
│           │           │           │           │           │ (2)  │      │
└───────────┴───────────┴───────────┴───────────┴───────────┴──────┴──────┘
Milestone 2: ✅ 430K data points recovered, analytics enabled

WEEKS 3-4: Sprint 2 - DATA ENRICHMENT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────────────────────────────┐
│ WEEK 3:                                                                  │
│ Mon-Wed: US-10 Resource Metrics (pricing table, cost calc, metrics) (3) │
│ Thu-Fri: US-11 Denormalization Design (schema, migration script)        │
│                                                                          │
│ WEEK 4:                                                                  │
│ Mon-Tue: US-11 Parser Updates (new tables, query migration)             │
│ Wed-Thu: US-11 Testing (migration test, integrity validation)           │
│ Fri-Sat: US-11 Performance & Rollback Testing (5 pts total)             │
└─────────────────────────────────────────────────────────────────────────┘
Milestone 3: ✅ Cost tracking live, schema optimized, 100% data preserved

WEEKS 5-6: Sprint 3 - VALIDATION & GO-LIVE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────────────────────────────┐
│ WEEK 5:                                                                  │
│ Mon-Wed: US-12 Validation Framework (15+ health checks, automation) (3) │
│ Thu-Fri: US-13 Performance Benchmarking (all queries validated)         │
│                                                                          │
│ WEEK 6:                                                                  │
│ Mon-Tue: US-13 Monitoring Setup (Prometheus, Grafana dashboards) (2)    │
│ Wed: **GO-LIVE DAY** 🚀 (Production deployment)                         │
│ Thu: Post-deployment monitoring and validation                          │
└─────────────────────────────────────────────────────────────────────────┘
Milestone 4: ✅ Production live, 100% data integrity, monitoring active

════════════════════════════════════════════════════════════════════════════
EPIC COMPLETE: 34 points, 13 stories, 100% data quality ✅
════════════════════════════════════════════════════════════════════════════
```

### 4.2 Dependency Graph

```
                         ┌──────────────────────┐
                         │   SPRINT 0 (P0)     │
                         │  5 critical fixes    │
                         └──────────┬───────────┘
                                    │ (Must complete)
                                    ▼
             ┌──────────────────────────────────────────┐
             │           SPRINT 1 (Extraction)          │
             │       Recover 430K data points           │
             └──────────────────┬───────────────────────┘
                                │ (Must complete)
                                ▼
             ┌──────────────────────────────────────────┐
             │        SPRINT 2 (Enrichment)             │
             │    Cost tracking + Schema optimization   │
             └──────────────────┬───────────────────────┘
                                │ (Must complete)
                                ▼
             ┌──────────────────────────────────────────┐
             │      SPRINT 3 (Validation & Go-Live)     │
             │    Production deployment + Monitoring    │
             └──────────────────────────────────────────┘

CRITICAL PATH:
US-2 (Plan 45) → US-3 (Race Fix) → US-11 (Schema) → US-13 (Go-Live)

PARALLEL TRACKS:
- US-1, US-4, US-5 can run in parallel in Sprint 0
- US-6, US-7, US-8, US-9 can run in parallel in Sprint 1
- US-10 can start while US-11 is in progress
- US-12 can prepare while US-13 deployment is being planned
```

### 4.3 Milestone Gates

Each sprint has a **milestone gate** with specific exit criteria:

| Milestone | Gate Criteria | Stakeholder Sign-Off |
|-----------|--------------|---------------------|
| **M1: Sprint 0 Complete** | ✅ All 5 P0 stories done<br>✅ Test coverage >80%<br>✅ Zero critical bugs<br>✅ Plan 45 tables populated | Tech Lead + QA |
| **M2: Sprint 1 Complete** | ✅ All 4 extraction stories done<br>✅ 430K data points recovered<br>✅ Backfill 100% successful<br>✅ New fields queryable | Product Manager + Analyst |
| **M3: Sprint 2 Complete** | ✅ Both enrichment stories done<br>✅ Cost tracking accurate ±5%<br>✅ Schema migration 100% data preserved<br>✅ Query performance validated | DBA + Finance |
| **M4: Sprint 3 Complete** | ✅ Health checks 100% passing<br>✅ Production deployed<br>✅ Monitoring active<br>✅ Zero regressions | VP Engineering + CTO |

**No sprint can start until the previous milestone gate is cleared.**

---

## 5. Detailed Sprint Plans

### 5.1 Sprint 0: P0 Critical Fixes (Jan 13-17, 5 days)

**Goal**: Fix all 5 P0 blockers that prevent basic analytics functionality

**Team**: 2-3 FTE (Backend Engineer, Data Engineer, QA)  
**Points**: 14 (high velocity expected due to criticality)

#### Stories & Schedule

##### **Day 1 (Monday): US-1 - Fix Root Token Calculation** (3 points)

**Problem**: All root_tokens hardcoded to 0 → Cost reports 100% wrong

**Tasks**:
- [ ] Morning: Add `extract_root_tokens()` function in parsers.py
  ```python
  def extract_root_tokens(root_traces: list) -> int:
      """Extract total token count from root trace usage."""
      return sum(
          trace.get('usage', {}).get('input_tokens', 0) + 
          trace.get('usage', {}).get('output_tokens', 0)
          for trace in root_traces
      )
  ```
- [ ] Afternoon: Update SessionStats parsing to use extraction
- [ ] Afternoon: Add unit tests for token extraction edge cases
- [ ] Evening: Backfill existing sessions with real token counts

**Acceptance**: 95%+ sessions have real token counts (not 0)

**Files Modified**:
- `src/opencode_status_bar/analytics/indexer/parsers.py`
- `src/opencode_status_bar/analytics/db.py`
- `tests/test_token_calculation.py` (NEW)

---

##### **Day 2 (Tuesday): US-2 - Implement Plan 45 Loading (Part 1)** (5 points)

**Problem**: exchanges and exchange_traces tables have 0 records

**Tasks**:
- [ ] Morning: Design exchange/trace parsing logic
  - Parse session JSON for user↔assistant exchanges
  - Extract exchange metadata (timing, tokens, cost)
  - Structure trace events (tool-call, reasoning, text)
- [ ] Afternoon: Implement bulk loader for Plan 45 tables
  ```python
  def load_exchanges(session_json: dict) -> list[Exchange]:
      """Parse session into exchanges (user↔assistant turns)."""
      exchanges = []
      # Logic to group messages into exchanges
      return exchanges
  ```
- [ ] Evening: Start integration tests (bulk loading scenarios)

**Acceptance**: Bulk loader can populate exchanges table from JSON

---

##### **Day 3 (Wednesday): US-2 Completion + US-4 - Indexes** (5+2 points)

**Morning - US-2 (Part 2)**:
- [ ] Implement real-time handler for Plan 45 (hybrid.py)
- [ ] Complete integration tests (bulk + real-time scenarios)
- [ ] Validate no duplicates or data loss

**Afternoon - US-4: Add Missing Indexes** (2 points):
- [ ] Create migration script with 8+ indexes:
  ```sql
  CREATE INDEX idx_agents_name ON agents(name);
  CREATE INDEX idx_models_vendor ON models(vendor);
  CREATE INDEX idx_parts_type ON parts(part_type);
  CREATE INDEX idx_parts_session ON parts(session_id);
  CREATE INDEX idx_tools_name ON tools(tool_name);
  CREATE INDEX idx_messages_session ON messages(session_id);
  CREATE INDEX idx_exchanges_session ON exchanges(session_id);
  CREATE INDEX idx_traces_exchange ON exchange_traces(exchange_id);
  ```
- [ ] Benchmark queries before/after (expect 50x improvement)
- [ ] Validate EXPLAIN QUERY PLAN shows index usage

**Acceptance**: 
- US-2: exchanges and exchange_traces both populated
- US-4: All 8 indexes created, queries <10ms

---

##### **Day 4 (Thursday): US-3 - Race Condition Handling** (3 points)

**Problem**: Files can be missed or duplicated during bulk→real-time transition

**Tasks**:
- [ ] Morning: Create `SyncState` class with lock management
  ```python
  class SyncState:
      def acquire_bulk_lock(self) -> bool
      def release_bulk_lock(self) -> None
      def wait_for_bulk_completion(self) -> None
      def is_bulk_phase(self) -> bool
  ```
- [ ] Afternoon: Update bulk_loader to acquire/release lock
- [ ] Afternoon: Update watcher to check lock before processing
- [ ] Evening: Integration test: bulk + real-time overlap (100 files)

**Acceptance**: 0 file loss or duplication in 10 test runs with overlap

**Files**:
- `src/opencode_status_bar/analytics/indexer/sync_state.py` (NEW)
- `src/opencode_status_bar/analytics/indexer/bulk_loader.py`
- `src/opencode_status_bar/analytics/indexer/watcher.py`
- `tests/test_race_condition.py` (NEW)

---

##### **Day 5 (Friday): US-5 - error_data Type Migration** (1 point)

**Problem**: error_data is VARCHAR → Cannot filter on error fields

**Tasks**:
- [ ] Morning: Create migration script (VARCHAR → JSON)
  ```sql
  ALTER TABLE parts ADD COLUMN error_data_json JSON;
  UPDATE parts SET error_data_json = CAST(error_data AS JSON) 
  WHERE error_data IS NOT NULL;
  ALTER TABLE parts DROP COLUMN error_data;
  ALTER TABLE parts RENAME COLUMN error_data_json TO error_data;
  ```
- [ ] Afternoon: Update parsers to insert JSON directly
- [ ] Afternoon: Add unit tests for JSON parsing
- [ ] Evening: Sprint review prep + final validation

**Acceptance**: Can run queries like `WHERE error_data.type = 'timeout'`

---

#### Sprint 0 Deliverables

✅ **Code Changes**:
- 5 user stories implemented (14 points)
- 8+ indexes created
- 2 new modules (sync_state.py, test files)
- Migration scripts for error_data

✅ **Data Quality**:
- Plan 45 tables populated (>0 records)
- Root tokens calculated correctly (95%+ sessions)
- No data loss (race conditions resolved)
- Query performance improved 50x

✅ **Testing**:
- 100+ unit tests added
- Integration tests pass (bulk + real-time)
- Performance benchmarks documented

✅ **Documentation**:
- Migration procedures documented
- Rollback procedures tested
- Performance improvements recorded

**Demo**: Show Plan 45 UI with real data, cost reports with real tokens, race condition test passing

---

### 5.2 Sprint 1: Data Extraction & Quality (Jan 20-26, 7 days)

**Goal**: Extract missing fields from JSON to recover ~430K lost data points

**Team**: 2 FTE (Backend Engineer, Data Analyst)  
**Points**: 7 (moderate complexity, mostly extraction logic)

#### Stories & Schedule

##### **Days 1-2: US-6 - Extract root_path** (2 points)

**Problem**: root_path exists in JSON but not stored → Cannot filter by project

**Tasks**:
- [ ] Day 1 Morning: Add root_path column to messages table
  ```sql
  ALTER TABLE messages ADD COLUMN root_path VARCHAR;
  CREATE INDEX idx_messages_root_path ON messages(root_path);
  ```
- [ ] Day 1 Afternoon: Update message parser to extract root_path
  ```python
  root_path = message_json.get('path', {}).get('root', None)
  ```
- [ ] Day 2 Morning: Create backfill script for existing messages
- [ ] Day 2 Afternoon: Unit tests + integration test

**Acceptance**: 100% of messages have root_path populated

---

##### **Days 3-4: US-7 - Error Classification** (3 points)

**Problem**: error_data is blob → Cannot categorize errors

**Tasks**:
- [ ] Day 3 Morning: Design error taxonomy (15+ categories)
  ```python
  ERROR_CATEGORIES = {
      'timeout': ['timeout', 'timed out', 'deadline exceeded'],
      'auth': ['authentication', 'unauthorized', '401', '403'],
      'network': ['connection', 'network', 'dns', 'socket'],
      'rate_limit': ['rate limit', 'too many requests', '429'],
      # ... 11+ more categories
  }
  ```
- [ ] Day 3 Afternoon: Implement error_classifier.py module
- [ ] Day 4 Morning: Add error_category column to parts table
- [ ] Day 4 Afternoon: Backfill existing errors + validate accuracy (>95%)

**Acceptance**: 95%+ errors classified correctly (manual validation on 100 samples)

---

##### **Days 5-6: US-8 - Tool Execution Times** (2 points)

**Problem**: Execution time in JSON but not extracted

**Tasks**:
- [ ] Day 5 Morning: Add execution_time_ms column to parts table
- [ ] Day 5 Afternoon: Update parser to extract timing data
  ```python
  duration_ms = part_json.get('timing', {}).get('duration_ms', None)
  ```
- [ ] Day 6 Morning: Backfill existing tool calls
- [ ] Day 6 Afternoon: Create performance analytics queries (p50, p95, p99)

**Acceptance**: 100% of tool calls have execution_time_ms

---

##### **Days 6-7: US-9 - Git Metadata** (2 points)

**Problem**: Git metadata in JSON but not captured

**Tasks**:
- [ ] Day 6 Morning: Add git columns to parts table
  ```sql
  ALTER TABLE parts ADD COLUMN git_branch VARCHAR;
  ALTER TABLE parts ADD COLUMN git_commit VARCHAR(40);
  ALTER TABLE parts ADD COLUMN git_diff TEXT;
  CREATE INDEX idx_parts_git_branch ON parts(git_branch);
  ```
- [ ] Day 6 Afternoon: Update parser to extract git context
- [ ] Day 7 Morning: Backfill existing file operations
- [ ] Day 7 Afternoon: Sprint validation + review prep

**Acceptance**: 70%+ file operations have git metadata (where applicable)

---

#### Sprint 1 Deliverables

✅ **Data Recovery**:
- 430K data points extracted and stored
- 100% messages have root_path
- 95%+ errors classified
- 100% tool calls have execution_time
- 70%+ file ops have git metadata

✅ **New Capabilities**:
- Project filtering enabled
- Error analytics dashboard possible
- Performance monitoring enabled
- Git correlation enabled

✅ **Data Completeness**:
- Messages: 70% → 85% completeness
- Parts: 70% → 90% completeness
- Errors: 0% → 95% classified

**Demo**: Show project filtering, error analytics, tool performance, git correlation

---

### 5.3 Sprint 2: Data Enrichment & Optimization (Jan 27 - Feb 9, 14 days)

**Goal**: Enrich data with computed metrics and optimize schema for performance

**Team**: 2-3 FTE (Backend Engineer, DBA, Analyst)  
**Points**: 8 (higher complexity, schema changes)

#### Stories & Schedule

##### **Week 1, Days 1-3: US-10 - Resource Metrics** (3 points)

**Problem**: No cost tracking or resource metrics

**Tasks**:
- [ ] Day 1: Create model_pricing table + seed data
  ```sql
  CREATE TABLE model_pricing (
      model_name VARCHAR PRIMARY KEY,
      input_token_cost_per_1k DOUBLE NOT NULL,
      output_token_cost_per_1k DOUBLE NOT NULL
  );
  INSERT INTO model_pricing VALUES
      ('claude-3-opus', 0.015, 0.075),
      ('claude-3-sonnet', 0.003, 0.015);
  ```
- [ ] Day 2: Implement cost_calculator.py module
  ```python
  def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
      pricing = get_model_pricing(model)
      return (input_tokens/1000 * pricing.input) + (output_tokens/1000 * pricing.output)
  ```
- [ ] Day 2: Create session_resource_metrics table
- [ ] Day 3: Implement aggregator.py for session-level metrics
- [ ] Day 3: Backfill existing sessions with costs
- [ ] Day 3: Validate against API bills (±5% accuracy)

**Acceptance**: 100% sessions have cost data, accuracy ±5% vs API bills

---

##### **Week 1 Days 4-5, Week 2 Full: US-11 - Data Denormalization** (5 points)

**Problem**: parts table has 29 mixed-purpose columns → Schema bloated

**Target**: Normalize to 7-10 focused tables

**Week 1, Days 4-5: Design + Migration Script**:
- [ ] Day 4 Morning: Design normalized schema
  ```
  parts (core: id, session_id, part_type, content, created_at)
      ├─ tool_calls (tool-specific fields)
      ├─ file_operations (file-specific fields)
      ├─ errors (error-specific fields)
      ├─ thinking_blocks (reasoning-specific)
      ├─ text_messages (text-specific)
      └─ step_events (step-specific)
  ```
- [ ] Day 4 Afternoon: Create table definitions with indexes
- [ ] Day 5: Write migration script (parts → new tables)
- [ ] Day 5: Write rollback script (new tables → parts)

**Week 2, Days 1-3: Implementation**:
- [ ] Day 1: Update parsers to insert into new tables
- [ ] Day 1-2: Update all query files to use new schema
- [ ] Day 3: Run migration on test database
- [ ] Day 3: Validate data integrity (100% preserved)

**Week 2, Days 4-5: Validation**:
- [ ] Day 4: Benchmark queries (before/after)
- [ ] Day 4: Integration tests for new schema
- [ ] Day 5: Test rollback procedure
- [ ] Day 5: Document schema changes

**Acceptance**:
- 100% data preserved in migration
- Query performance maintained or improved
- Rollback tested successfully

---

#### Sprint 2 Deliverables

✅ **Cost Tracking**:
- Pricing table with current rates
- Cost calculated per session/message/part
- Spend forecasting enabled
- Budget alerts possible

✅ **Schema Optimization**:
- 29-column parts table → 7-10 focused tables
- Query performance maintained/improved
- Cleaner data model

✅ **Data Completeness**:
- 100% sessions have cost data
- 100% parts migrated to new schema
- 0 orphaned records

**Demo**: Cost analytics dashboard, schema ER diagram, query performance comparison

---

### 5.4 Sprint 3: Validation & Go-Live (Feb 10-18, 9 days)

**Goal**: Validate 100% data integrity, optimize performance, deploy to production

**Team**: 3 FTE (Backend Engineer, DevOps, QA Lead)  
**Points**: 5 (high risk, careful validation required)

#### Stories & Schedule

##### **Days 1-3: US-12 - Complete Data Validation** (3 points)

**Tasks**:
- [ ] Day 1: Implement 15+ validation check functions
  - Check 1: Plan 45 tables populated
  - Check 2: Root tokens not 0 (>95% valid)
  - Check 3: Messages have root_path (>80%)
  - Check 4: Errors classified (>95%)
  - Check 5: Tool calls have timing (>90%)
  - Check 6: File ops have git metadata (>70%)
  - Check 7: Sessions have cost data (>95%)
  - Check 8-10: No orphaned records, duplicates, FK violations
  - Check 11-12: Query performance (<250ms), index usage
  - Check 13-15: Cost/token/error rate anomalies
- [ ] Day 2: Create health_check_history table
- [ ] Day 2: Implement daily health check script + report generator
- [ ] Day 3: Implement alerting (Slack webhook)
- [ ] Day 3: Set up cron job for daily checks
- [ ] Day 3: Manual validation run

**Acceptance**: All 15 health checks pass 100%

---

##### **Days 4-9: US-13 - Performance & Go-Live** (2 points)

**Days 4-5: Performance Benchmarking**:
- [ ] Run 5 key query benchmarks:
  - Agents by name: <10ms (was 100-500ms)
  - Tools by session: <50ms
  - Error breakdown: <100ms
  - Cost trends: <200ms
  - Session details: <150ms
- [ ] Analyze results + optimization tweaks

**Days 6-7: Monitoring Setup**:
- [ ] Set up Prometheus metrics collection
- [ ] Create 4 Grafana dashboards:
  - Performance monitoring (latency, DB size)
  - Data quality monitoring (completeness, freshness)
  - Business metrics (cost, tokens, errors)
  - System health (indexer status, data loss)
- [ ] Configure alerts (Slack integration)

**Day 7: Deployment Preparation**:
- [ ] Write deployment script
- [ ] Write rollback script
- [ ] Test rollback procedure in staging
- [ ] Team briefing + stakeholder notification

**Day 8: GO-LIVE DAY 🚀**:
- [ ] Morning: Execute deployment (low-traffic window)
  1. Stop indexer
  2. Backup production database
  3. Run migrations
  4. Validate migration
  5. Restart indexer with new code
  6. Monitor logs (first 30 min)
  7. Run performance benchmarks
  8. Run health checks
  9. Validate dashboards
  10. Enable monitoring alerts
- [ ] Afternoon: Monitor metrics, respond to issues

**Day 9: Post-Deployment**:
- [ ] Monitor for 24h (alerts on anomalies)
- [ ] Verify cost calculations match API bills
- [ ] Collect team feedback
- [ ] Document lessons learned
- [ ] **Celebrate success!** 🎉

---

#### Sprint 3 Deliverables

✅ **Validation**:
- 15+ health checks automated
- Daily health reports scheduled
- Alerting configured (Slack)

✅ **Performance**:
- Query benchmarks <250ms (50% improvement)
- All indexes deployed
- Zero regressions

✅ **Monitoring**:
- 4 Grafana dashboards live
- Prometheus metrics collecting
- 24h post-deployment monitoring

✅ **Deployment**:
- Production deployed successfully
- Rollback procedure tested
- Team sign-off on go-live

**Demo**: Health check dashboard, performance benchmarks, monitoring dashboards, production analytics working

---

## 6. Technical Approach

### 6.1 Architecture Overview

#### Current State
```
JSON Files (2GB)
    ↓
Bulk Loader (initial) + Watcher (real-time)
    ↓
DuckDB Analytics (analytics.duckdb)
    ↓
Query Interface (SQL)
```

**Issues**:
- Race condition between bulk/real-time
- Incomplete parsing (70% field coverage)
- Missing indexes (slow queries)
- Plan 45 tables not populated

#### Target State
```
JSON Files (2GB)
    ↓
SyncState Manager (phase coordination)
    ↓
┌─ Bulk Loader (with Plan 45, full parsing)
└─ Watcher (with Plan 45, full parsing)
    ↓
Enhanced Parsers (100% field extraction)
    ↓
DuckDB Analytics (normalized schema, all indexes)
    ├─ Core Tables: sessions, messages, parts
    ├─ Specialized Tables: tool_calls, file_operations, errors, etc.
    ├─ Metrics Tables: session_resource_metrics, daily_stats
    └─ Plan 45 Tables: exchanges, exchange_traces, session_traces
    ↓
Health Check System (15+ automated checks)
    ↓
Monitoring Layer (Prometheus + Grafana)
```

### 6.2 Database Schema Changes

#### New Tables (Sprint 2)

**1. session_resource_metrics** (Cost tracking)
```sql
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

**2. model_pricing** (Cost calculation)
```sql
CREATE TABLE model_pricing (
    model_name VARCHAR PRIMARY KEY,
    vendor VARCHAR NOT NULL,
    input_token_cost_per_1k DOUBLE NOT NULL,
    output_token_cost_per_1k DOUBLE NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Seed data
INSERT INTO model_pricing VALUES
('claude-3-opus', 'anthropic', 0.015, 0.075, NOW()),
('claude-3-sonnet', 'anthropic', 0.003, 0.015, NOW()),
('gpt-4-turbo', 'openai', 0.01, 0.03, NOW()),
('gpt-4o', 'openai', 0.005, 0.015, NOW());
```

**3. Normalized parts tables** (7-10 focused tables)
- `tool_calls` (tool-specific fields)
- `file_operations` (file-specific fields)
- `errors` (error-specific fields)
- `thinking_blocks` (reasoning-specific)
- `text_messages` (text-specific)

#### Column Additions

**messages table**:
```sql
ALTER TABLE messages ADD COLUMN root_path VARCHAR;
CREATE INDEX idx_messages_root_path ON messages(root_path);
```

**parts table** (before denormalization):
```sql
ALTER TABLE parts ADD COLUMN (
    root_path VARCHAR,
    execution_time_ms DOUBLE,
    error_category VARCHAR,
    git_branch VARCHAR,
    git_commit VARCHAR(40),
    git_diff TEXT
);

CREATE INDEX idx_parts_execution_time ON parts(execution_time_ms);
CREATE INDEX idx_parts_error_category ON parts(error_category);
CREATE INDEX idx_parts_git_branch ON parts(git_branch);
CREATE INDEX idx_parts_git_commit ON parts(git_commit);
```

**8+ Critical Indexes** (Sprint 0):
```sql
CREATE INDEX idx_agents_name ON agents(name);
CREATE INDEX idx_models_vendor ON models(vendor);
CREATE INDEX idx_parts_type ON parts(part_type);
CREATE INDEX idx_parts_session ON parts(session_id);
CREATE INDEX idx_tools_name ON tools(tool_name);
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_exchanges_session ON exchanges(session_id);
CREATE INDEX idx_traces_exchange ON exchange_traces(exchange_id);
```

### 6.3 Migration Strategy

#### Phase 1: Additive Changes (Sprint 0-1)
- Add new columns (backward compatible)
- Add new indexes (no data changes)
- Populate Plan 45 tables (new data)
- Backfill existing data

**Migration Pattern**:
```python
def migrate_add_column(table: str, column: str, type: str):
    """Add column with default value, backfill if needed."""
    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type}")
    if needs_backfill:
        backfill_column(table, column)
    validate_completeness(table, column)
```

#### Phase 2: Schema Normalization (Sprint 2)
- Create new normalized tables
- Migrate data from parts → new tables
- Validate data integrity (100%)
- Update queries to use new schema
- Keep old parts table as parts_legacy (1 week)
- Drop parts_legacy after validation

**Migration Pattern**:
```python
def migrate_denormalize():
    """Migrate parts table to normalized schema."""
    # Phase 1: Create new tables
    create_new_tables()
    
    # Phase 2: Migrate data
    migrate_data_with_progress()
    
    # Phase 3: Validate integrity
    validate_counts_match()
    validate_no_orphans()
    validate_no_data_loss()
    
    # Phase 4: Update queries
    update_query_files()
    
    # Phase 5: Rename old table
    db.execute("ALTER TABLE parts RENAME TO parts_legacy")
    
    # Phase 6: Monitor for 1 week
    if all_good_after_week:
        db.execute("DROP TABLE parts_legacy")
```

#### Rollback Procedures

**Sprint 0-1 Rollback**:
- Drop new columns
- Drop new indexes
- Truncate Plan 45 tables
- Restore from backup if needed

**Sprint 2 Rollback**:
- Rename parts_legacy back to parts
- Drop new normalized tables
- Restore query files to old version
- Validate data intact

**All Rollbacks**:
- Must complete in <30 minutes
- Tested in staging before production
- Documented step-by-step procedures
- Automated scripts prepared

### 6.4 Performance Optimization Strategy

#### Query Optimization
1. **Index all foreign keys** (Sprint 0)
2. **Index all common filters** (agent, model, type, tool)
3. **Composite indexes** for multi-column filters
4. **Explain plan validation** for all key queries

#### Data Access Patterns
1. **Denormalization** where appropriate (session_resource_metrics)
2. **Pre-aggregation** for dashboard queries (daily_stats)
3. **Materialized views** for complex joins (future work)

#### Benchmarking
- Baseline queries before changes
- Benchmark after each optimization
- Target: <250ms for 95% of queries
- Document performance improvements

---

## 7. Risk Assessment

### 7.1 Technical Risks

| Risk | Probability | Impact | Severity | Mitigation | Contingency |
|------|-------------|--------|----------|-----------|-------------|
| **Data loss during Plan 45 loading** | Medium | Critical | 🔴 HIGH | • Backup DB before loading<br>• Test on copy first<br>• Incremental loading | • Rollback to backup<br>• Restore from JSON |
| **Migration causes data corruption** | Low | Critical | 🔴 HIGH | • Extensive validation<br>• Test on staging<br>• Keep old table 1 week | • Rollback script ready<br>• Restore from backup |
| **Performance regression** | Medium | High | 🟠 MEDIUM | • Benchmark before/after<br>• EXPLAIN plans<br>• Staging validation | • Rollback indexes<br>• Revert to old schema |
| **Race condition still exists** | Low | Critical | 🔴 HIGH | • Stress testing (100 files)<br>• Integration tests<br>• Monitoring alerts | • Fix immediately<br>• Add more locks |
| **Backfill takes too long** | Medium | Medium | 🟡 LOW | • Incremental backfill<br>• Batch processing<br>• Progress tracking | • Extend timeline<br>• Parallelize work |
| **error_data migration breaks queries** | Low | Medium | 🟡 LOW | • Test on copy<br>• Backward compat<br>• Rollback procedure | • Revert to VARCHAR<br>• Fix queries |
| **Cost calculations inaccurate** | Medium | High | 🟠 MEDIUM | • Validate vs API bills<br>• Manual spot checks<br>• ±5% tolerance | • Refine pricing<br>• Add model cases |
| **Indexes cause write slowdown** | Low | Low | 🟢 TRIVIAL | • Monitor write latency<br>• Batch inserts | • Drop non-critical indexes |

### 7.2 Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Sprint 0 takes longer than 5 days** | Medium | Delays Sprint 1 | • Focus only on P0<br>• Cut scope if needed<br>• Extend by 2 days max |
| **Schema migration more complex** | Medium | Delays Sprint 2 | • Start design early<br>• Prototype in Sprint 1<br>• Add buffer days |
| **Production deployment delayed** | Low | Delays go-live | • Pre-schedule deployment<br>• Get stakeholder buy-in<br>• Have rollback ready |
| **Team unavailability** | Low | Velocity drops | • Cross-train team members<br>• Document thoroughly<br>• Adjust capacity |
| **Scope creep** | High | Timeline slip | • Firm P0/P1/P2 boundaries<br>• Sprint planning discipline<br>• Defer non-critical |

### 7.3 Data Quality Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Backfill misses edge cases** | Medium | Incomplete data | • Extensive unit tests<br>• Manual validation<br>• Re-run backfill if needed |
| **Error classification accuracy low** | Medium | Poor analytics | • Manual validation (100 samples)<br>• Iterative refinement<br>• Threshold >95% |
| **Git metadata missing for old data** | High | Gaps in history | • Handle null gracefully<br>• Document data gaps<br>• Accept incomplete history |
| **Cost estimates vs actuals diverge** | Medium | Trust issues | • Validate against API bills<br>• Calibrate pricing table<br>• ±5% tolerance |

### 7.4 Risk Mitigation Strategies

#### Strategy 1: Incremental Approach
- Each sprint builds on previous
- Can stop after Sprint 0 if needed (P0 fixed)
- Can defer Sprint 2-3 if timeline slips

#### Strategy 2: Validation at Every Step
- Unit tests for all new code
- Integration tests for data pipelines
- Manual validation of critical data
- Health checks automated

#### Strategy 3: Rollback Readiness
- Every migration has rollback script
- Rollback tested in staging
- Can rollback in <30 minutes
- Backup created before each phase

#### Strategy 4: Monitoring & Alerts
- Health checks run daily post-deployment
- Alerts on anomalies (Slack)
- Dashboards show key metrics
- Team on-call rotation (Week 1 post-deploy)

---

## 8. Resource Requirements

### 8.1 Team Composition

| Role | FTE | Responsibility | Sprints |
|------|-----|---------------|---------|
| **Backend Engineer** | 1.5 | • Implement parsers<br>• Build data loaders<br>• Write migrations<br>• Performance optimization | All (0-3) |
| **Data Engineer** | 0.5 | • Schema design<br>• Data validation<br>• Backfill scripts<br>• Quality assurance | Sprint 0-2 |
| **DevOps/SRE** | 0.5 | • Deployment automation<br>• Monitoring setup<br>• Rollback procedures<br>• Production support | Sprint 2-3 |
| **QA Engineer** | 0.5 | • Integration testing<br>• Performance testing<br>• Regression testing<br>• Deployment validation | Sprint 0,3 |
| **Data Analyst** | 0.25 | • Validate classifications<br>• Check data completeness<br>• Test dashboards | Sprint 1-2 |

**Total**: ~2.75 FTE average, peaks at 3.5 FTE in Sprint 3

### 8.2 Skills Required

**Must Have**:
- Python (parsers, data pipelines)
- DuckDB / SQL (schema, queries, migrations)
- Data modeling (normalization, optimization)
- Testing (unit, integration, performance)

**Nice to Have**:
- Prometheus / Grafana (monitoring)
- Data quality best practices
- Cost optimization techniques

### 8.3 Infrastructure

**Development**:
- Local DuckDB instances (each developer)
- Test data: Sample of 1K sessions (~50MB)

**Staging**:
- Full copy of production data (2GB)
- DuckDB analytics.duckdb.staging
- Used for migration testing, performance validation

**Production**:
- DuckDB analytics.duckdb (2GB)
- Prometheus + Grafana for monitoring
- Slack integration for alerts

**Cost**: Minimal - DuckDB is in-process, no cloud resources needed

### 8.4 Knowledge Transfer Plan

#### Week Before Sprint 0
- 2-hour architecture overview session
- 4-hour code walkthrough (indexer + db.py)
- Share architecture audit document
- Q&A session

#### During Sprints
- Pair programming for risky changes (migrations)
- Code reviews for all data changes
- Daily standups to surface blockers
- Weekly demos to stakeholders

#### Documentation
- Update README with new features
- Document schema changes (ER diagrams)
- Migration guide for future work
- Runbook for common issues

### 8.5 Budget Estimate

| Category | Cost | Details |
|----------|------|---------|
| **Engineering** | $21,000 | 140 dev-hours × $150/hr |
| **QA** | $3,000 | 20 QA-hours × $150/hr |
| **DevOps** | $1,500 | 10 DevOps-hours × $150/hr |
| **Infrastructure** | $0 | Using existing DuckDB |
| **Contingency** | $2,500 | 10% buffer for unknowns |
| **TOTAL** | **$28,000** | 6-week project |

**Expected Savings**: ~$50K/year through accurate cost tracking + performance optimization

**ROI**: ~180% in Year 1

---

## 9. Success Metrics

### 9.1 Before/After Comparison

| Metric | Before (Current) | After (Target) | Improvement |
|--------|-----------------|---------------|-------------|
| **Data Completeness** | 70% of JSON fields | 100% of JSON fields | +30% (+430K data points) |
| **Query Performance** | 100-500ms | <250ms | 50-75% faster |
| **Available Dashboards** | 25 dashboards | 40+ dashboards | +60% (+15 new dashboards) |
| **Cost Tracking** | ❌ Broken (root_tokens=0) | ✅ Accurate ±5% | Critical fix |
| **Plan 45 Functionality** | ❌ 0 records | ✅ Fully populated | Feature enabled |
| **Error Analytics** | ❌ No categorization | ✅ 15+ categories | SLA monitoring enabled |
| **Missing Indexes** | 8+ critical indexes | 0 missing indexes | All queries optimized |
| **Race Conditions** | Possible data loss | Zero data loss | 100% reliability |
| **Git Correlation** | ❌ No metadata | ✅ Branch, commit, diff | Version control insights |
| **Resource Monitoring** | ❌ No data | ✅ CPU, memory, cache | Performance optimization |

### 9.2 Key Performance Indicators (KPIs)

#### Sprint-Level KPIs

**Sprint 0 (P0 Fixes)**:
- ✅ All 5 P0 stories completed (14 points)
- ✅ Zero critical bugs introduced
- ✅ Test coverage >80% on new code
- ✅ Plan 45 tables have >0 records
- ✅ Root tokens: 95%+ sessions have real values (not 0)
- ✅ Race condition: 0 data loss in 10 test runs
- ✅ Query performance: 50x improvement (<10ms on indexed queries)

**Sprint 1 (Extraction)**:
- ✅ All 4 extraction stories completed (7 points)
- ✅ 430K data points recovered
- ✅ Backfill 100% successful (0 data loss)
- ✅ Messages: 100% have root_path
- ✅ Errors: 95%+ classified correctly
- ✅ Tool calls: 100% have execution_time
- ✅ File ops: 70%+ have git metadata

**Sprint 2 (Enrichment)**:
- ✅ All 2 enrichment stories completed (8 points)
- ✅ 100% sessions have cost data
- ✅ Cost accuracy: ±5% vs API bills
- ✅ Migration: 100% data preserved
- ✅ 0 orphaned records after migration
- ✅ Query performance maintained or improved

**Sprint 3 (Go-Live)**:
- ✅ All 2 validation stories completed (5 points)
- ✅ 15+ health checks 100% passing
- ✅ Production deployed successfully
- ✅ Zero critical bugs in production
- ✅ Monitoring active (4 Grafana dashboards)
- ✅ Query benchmarks <250ms (50% improvement)

#### Business Metrics

| Metric | Baseline | Milestone 1<br>(Sprint 0) | Milestone 2<br>(Sprint 1) | Milestone 3<br>(Sprint 2) | Milestone 4<br>(Sprint 3) |
|--------|----------|--------------------------|--------------------------|--------------------------|--------------------------|
| **Data Completeness** | 70% | 75% | 85% | 95% | 100% |
| **Query Latency (p95)** | 500ms | 250ms | 250ms | 220ms | <250ms |
| **Available Features** | 25 | 28 | 32 | 37 | 40+ |
| **Cost Accuracy** | 0% | 90% | 95% | 98% | ±5% |
| **Error Rate** | Unknown | Tracked | Analyzed | Monitored | Alerted |
| **Data Loss Incidents** | Possible | 0 | 0 | 0 | 0 |

### 9.3 Quality Gates

Each sprint has **exit criteria** that must be met before proceeding:

| Sprint | Exit Criteria | Validation Method |
|--------|--------------|------------------|
| **Sprint 0** | • All 5 P0 stories done<br>• Test coverage >80%<br>• Zero critical bugs<br>• Plan 45 tables >0 records | • Automated test suite<br>• Manual review<br>• Tech lead sign-off |
| **Sprint 1** | • All 4 extraction stories done<br>• 430K data points recovered<br>• Backfill 100% successful<br>• New fields queryable | • Backfill validation queries<br>• Manual spot checks (100 samples)<br>• Analyst sign-off |
| **Sprint 2** | • Both enrichment stories done<br>• Cost accuracy ±5%<br>• 100% data preserved in migration<br>• Query performance validated | • Cost vs API bill comparison<br>• Data integrity checks<br>• DBA sign-off |
| **Sprint 3** | • Health checks 100% passing<br>• Production deployed<br>• Monitoring active<br>• Zero regressions | • Health check report<br>• Performance benchmarks<br>• Stakeholder demo<br>• CTO sign-off |

### 9.4 Long-Term Success Indicators

**Month 1 Post-Deployment**:
- Production uptime >99.9%
- Zero data loss incidents
- Health checks 100% passing daily
- Query performance consistently <250ms

**Month 3 Post-Deployment**:
- 12+ new dashboards live and used
- Cost tracking enabling budget decisions
- Error analytics informing SLA improvements
- Performance monitoring catching regressions early

**Month 6 Post-Deployment**:
- ROI validated (~$50K savings)
- Team velocity improved (faster analytics development)
- Data quality culture established (daily health checks routine)
- Foundation for advanced features (semantic search, predictive analytics)

---

## 10. Stakeholder Communication Plan

### 10.1 Stakeholder Matrix

| Stakeholder | Role | Interest Level | Communication Frequency |
|-------------|------|---------------|------------------------|
| **VP Engineering** | Sponsor | High | Weekly status + milestone demos |
| **CTO** | Approver | Medium | Milestone gates only |
| **Product Manager** | User | High | Sprint planning + reviews |
| **Data Analysts** | User | High | Sprint 1-2 demos + feedback |
| **Finance Team** | User | Medium | Sprint 2 demo (cost tracking) |
| **Engineering Team** | Contributors | High | Daily standups + sprint ceremonies |
| **QA Team** | Contributors | High | Sprint 0,3 planning + reviews |
| **DevOps Team** | Contributors | Medium | Sprint 2-3 planning + deployment |

### 10.2 Communication Schedule

#### Weekly Updates (Fridays, 4pm)
**Format**: Email to stakeholders + Slack post in #data-quality

**Content**:
- Sprint progress (points completed vs planned)
- Key achievements this week
- Blockers and risks
- Next week's plan
- Metrics dashboard snapshot

**Template**:
```
📊 Week X Data Quality Update

Sprint: [Current Sprint] - [Status]
Progress: [X/Y points completed] ([Z]% done)

✅ This Week:
- [Achievement 1]
- [Achievement 2]

🚧 Blockers:
- [Blocker 1 + mitigation]

📈 Metrics:
- Data completeness: [X]% (target: [Y]%)
- Query performance: [X]ms (target: <250ms)

🎯 Next Week:
- [Goal 1]
- [Goal 2]

Dashboard: [link]
```

#### Sprint Reviews (End of each sprint)
**Attendees**: All stakeholders  
**Duration**: 1 hour  
**Agenda**:
1. Sprint recap (10 min)
   - Stories completed
   - Metrics achieved
   - Challenges overcome
2. Demo (30 min)
   - Show new functionality
   - Live data validation
   - Performance benchmarks
3. Q&A (15 min)
4. Next sprint preview (5 min)

**Sprint 0 Demo** (Jan 17):
- Show Plan 45 UI with real data
- Show cost reports with real token counts
- Show query performance improvement (before/after)
- Show race condition test passing

**Sprint 1 Demo** (Jan 26):
- Show project filtering by root_path
- Show error analytics dashboard (15+ categories)
- Show tool performance analytics (p50, p95, p99)
- Show git correlation (changes by branch)

**Sprint 2 Demo** (Feb 9):
- Show cost analytics dashboard (daily/weekly trends)
- Show cost by model breakdown
- Show new normalized schema (ER diagram)
- Show query performance comparison

**Sprint 3 Demo** (Feb 18):
- Show health check dashboard (15+ checks passing)
- Show monitoring dashboards (4 dashboards)
- Show production analytics working
- Celebrate epic completion! 🎉

### 10.3 Decision Points Requiring Stakeholder Input

| Decision Point | When | Stakeholders | Options |
|---------------|------|-------------|---------|
| **Scope Adjustment** | If Sprint 0 takes >7 days | VP Eng + PM | • Defer Sprint 2<br>• Cut Sprint 2 scope<br>• Extend timeline |
| **Schema Design Approval** | Sprint 2, Day 4 | DBA + Eng Lead | • Approve normalized design<br>• Request changes<br>• Defer denormalization |
| **Go-Live Date** | Sprint 3, Day 7 | CTO + VP Eng | • Proceed with deployment<br>• Delay 1 week<br>• Deploy in phases |
| **Rollback Decision** | If prod issues | VP Eng (on-call) | • Rollback immediately<br>• Fix forward<br>• Partial rollback |

### 10.4 Escalation Procedures

**Blocker Escalation**:
1. Developer raises in daily standup (< 1 hour)
2. Tech lead attempts resolution (< 4 hours)
3. If unresolved, escalate to VP Engineering (< 1 day)
4. If still blocked, escalate to CTO (< 2 days)

**Production Issue Escalation**:
- P0 (data loss): Immediate rollback + CTO notification
- P1 (performance): 1-hour response, fix within 4 hours
- P2 (non-critical): Next business day

### 10.5 Reporting Dashboard

**Real-Time Dashboard** (link shared with all stakeholders):

**Section 1: Sprint Progress**
- Burndown chart (points remaining vs days left)
- Velocity trend (points completed per day)
- Story status (To Do / In Progress / Done)

**Section 2: Key Metrics**
- Data completeness: 70% → [current]% → 100% target
- Query performance: 500ms → [current]ms → <250ms target
- Available features: 25 → [current] → 40+ target
- Cost accuracy: 0% → [current]% → ±5% target

**Section 3: Quality**
- Test coverage: [X]%
- Critical bugs: [count]
- Health checks passing: [X]/15

**Section 4: Risks**
- High risks: [count]
- Medium risks: [count]
- Mitigated this week: [count]

---

## 11. Implementation Checklist

### 11.1 Pre-Sprint 0 Preparation

**Week Before** (Jan 6-10):
- [ ] Kick-off meeting with team
- [ ] Architecture overview session (2 hours)
- [ ] Code walkthrough session (4 hours)
- [ ] Set up development environments
- [ ] Create test database with sample data
- [ ] Review and approve this plan document
- [ ] Assign roles and responsibilities
- [ ] Schedule all sprint ceremonies
- [ ] Set up Slack channel (#data-quality-epic)
- [ ] Share audit reports with team
- [ ] Stakeholder notification of timeline
- [ ] Reserve deployment window (Week 6, Wed)

### 11.2 Sprint 0 Execution Checklist (Jan 13-17)

**Monday**:
- [ ] Sprint planning meeting (1 hour)
- [ ] Start US-1: Token calculation
  - [ ] Implement extract_root_tokens() function
  - [ ] Update SessionStats parsing
  - [ ] Add unit tests
  - [ ] Backfill existing sessions
- [ ] Daily standup (15 min)

**Tuesday**:
- [ ] Daily standup
- [ ] US-1: Code review + merge
- [ ] Start US-2: Plan 45 loading (Part 1)
  - [ ] Design exchange/trace parsing
  - [ ] Implement bulk loader
  - [ ] Start integration tests
- [ ] Check: US-1 complete

**Wednesday**:
- [ ] Daily standup
- [ ] US-2: Complete Part 2
  - [ ] Implement real-time handler
  - [ ] Complete integration tests
  - [ ] Validate no duplicates/loss
- [ ] Start US-4: Add indexes
  - [ ] Create migration script (8+ indexes)
  - [ ] Benchmark queries before/after
  - [ ] Validate EXPLAIN plans
- [ ] Check: US-2 complete, US-4 in progress

**Thursday**:
- [ ] Daily standup
- [ ] US-4: Complete and merge
- [ ] Start US-3: Race condition handling
  - [ ] Create SyncState class
  - [ ] Update bulk_loader with locks
  - [ ] Update watcher with lock checks
  - [ ] Integration test: bulk + real-time overlap
- [ ] Check: US-4 complete

**Friday**:
- [ ] Daily standup
- [ ] US-3: Code review + merge
- [ ] Start US-5: error_data migration
  - [ ] Create migration script (VARCHAR → JSON)
  - [ ] Update parsers for JSON insertion
  - [ ] Add unit tests
  - [ ] Test migration on copy
- [ ] US-5: Complete and merge
- [ ] Sprint validation:
  - [ ] All tests pass
  - [ ] Coverage >80%
  - [ ] Plan 45 tables >0 records
  - [ ] Root tokens real values
  - [ ] Race condition test passing
- [ ] Sprint review prep
- [ ] Check: All 5 stories complete (14 points)

**Sprint 0 Review** (Friday afternoon):
- [ ] Demo all 5 fixes to stakeholders
- [ ] Show metrics improvement
- [ ] Get sign-off on Milestone 1
- [ ] Celebrate Sprint 0 success 🎉

### 11.3 Sprint 1 Execution Checklist (Jan 20-26)

**Monday**:
- [ ] Sprint planning meeting
- [ ] Start US-6: root_path extraction
  - [ ] Add root_path column
  - [ ] Update message parser
- [ ] Daily standup

**Tuesday**:
- [ ] Daily standup
- [ ] US-6: Complete
  - [ ] Backfill script
  - [ ] Unit + integration tests
- [ ] Check: US-6 complete (2 points)

**Wednesday**:
- [ ] Daily standup
- [ ] Start US-7: Error classification
  - [ ] Design error taxonomy (15+ categories)
  - [ ] Implement error_classifier.py
- [ ] Afternoon: Continue US-7

**Thursday**:
- [ ] Daily standup
- [ ] US-7: Complete
  - [ ] Add error_category column
  - [ ] Backfill existing errors
  - [ ] Validate accuracy (>95% on 100 samples)
- [ ] Check: US-7 complete (3 points)

**Friday**:
- [ ] Daily standup
- [ ] Start US-8: Tool execution times
  - [ ] Add execution_time_ms column
  - [ ] Update parser to extract timing
  - [ ] Backfill tool calls
  - [ ] Create analytics queries
- [ ] Check: US-8 in progress

**Saturday**:
- [ ] US-8: Complete and merge
- [ ] Start US-9: Git metadata
  - [ ] Add git columns
  - [ ] Update parser for git context
- [ ] Check: US-8 complete (2 points)

**Sunday**:
- [ ] US-9: Complete
  - [ ] Backfill file operations
  - [ ] Handle edge cases
  - [ ] Unit tests
- [ ] Sprint validation:
  - [ ] All 4 stories complete (7 points)
  - [ ] 430K data points recovered
  - [ ] Backfill 100% successful
  - [ ] All new fields queryable
- [ ] Sprint review prep
- [ ] Check: US-9 complete (2 points)

**Sprint 1 Review** (Sunday afternoon):
- [ ] Demo all 4 extractions
- [ ] Show data completeness improvement
- [ ] Get sign-off on Milestone 2
- [ ] Celebrate Sprint 1 success 🎉

### 11.4 Sprint 2 Execution Checklist (Jan 27 - Feb 9)

**Week 1, Monday**:
- [ ] Sprint planning meeting
- [ ] Start US-10: Resource metrics
  - [ ] Create model_pricing table
  - [ ] Seed pricing data
- [ ] Daily standup

**Week 1, Tuesday**:
- [ ] Daily standup
- [ ] US-10: Continue
  - [ ] Implement cost_calculator.py
  - [ ] Create session_resource_metrics table
  - [ ] Implement aggregator.py
- [ ] Check: US-10 progress

**Week 1, Wednesday**:
- [ ] Daily standup
- [ ] US-10: Complete
  - [ ] Backfill sessions with costs
  - [ ] Validate vs API bills (±5%)
  - [ ] Code review + merge
- [ ] Check: US-10 complete (3 points)

**Week 1, Thursday**:
- [ ] Daily standup
- [ ] Start US-11: Denormalization (Part 1)
  - [ ] Design normalized schema (7-10 tables)
  - [ ] Create table definitions
- [ ] Afternoon: Continue design

**Week 1, Friday**:
- [ ] Daily standup
- [ ] US-11: Continue (Part 2)
  - [ ] Write migration script
  - [ ] Write rollback script
  - [ ] Create validation queries
- [ ] Check: Design complete, scripts in progress

**Week 2, Monday**:
- [ ] Daily standup
- [ ] US-11: Continue (Part 3)
  - [ ] Update parsers for new tables
  - [ ] Update bulk_loader and hybrid.py
- [ ] Check: Parser updates in progress

**Week 2, Tuesday**:
- [ ] Daily standup
- [ ] US-11: Continue (Part 4)
  - [ ] Update all query files to new schema
  - [ ] Update dashboard queries
- [ ] Check: Query migration in progress

**Week 2, Wednesday**:
- [ ] Daily standup
- [ ] US-11: Testing (Part 5)
  - [ ] Run migration on test database
  - [ ] Validate data integrity (100%)
  - [ ] Check counts match
  - [ ] Check no orphans
- [ ] Check: Migration tested

**Week 2, Thursday**:
- [ ] Daily standup
- [ ] US-11: Performance validation (Part 6)
  - [ ] Benchmark queries (before/after)
  - [ ] Integration tests
  - [ ] Validate query performance maintained
- [ ] Check: Performance validated

**Week 2, Friday**:
- [ ] Daily standup
- [ ] US-11: Rollback testing + completion
  - [ ] Test rollback procedure
  - [ ] Document schema changes
  - [ ] Code review + merge
- [ ] Sprint validation:
  - [ ] Both stories complete (8 points)
  - [ ] 100% sessions have cost data
  - [ ] Cost accuracy ±5%
  - [ ] Migration 100% data preserved
  - [ ] 0 orphaned records
- [ ] Sprint review prep
- [ ] Check: US-11 complete (5 points)

**Sprint 2 Review** (Friday afternoon):
- [ ] Demo cost tracking + schema optimization
- [ ] Show data integrity validation
- [ ] Get sign-off on Milestone 3
- [ ] Celebrate Sprint 2 success 🎉

### 11.5 Sprint 3 Execution Checklist (Feb 10-18)

**Monday**:
- [ ] Sprint planning meeting
- [ ] Start US-12: Data validation
  - [ ] Implement validation checks 1-7
  - [ ] Create health_check_history table
- [ ] Daily standup

**Tuesday**:
- [ ] Daily standup
- [ ] US-12: Continue
  - [ ] Implement validation checks 8-15
  - [ ] Implement health_check.py script
  - [ ] Implement report_generator.py
- [ ] Check: Validation framework in progress

**Wednesday**:
- [ ] Daily standup
- [ ] US-12: Complete
  - [ ] Implement alerting.py (Slack)
  - [ ] Set up cron job
  - [ ] Unit tests for all checks
  - [ ] Manual validation run
  - [ ] Code review + merge
- [ ] Check: US-12 complete (3 points)

**Thursday**:
- [ ] Daily standup
- [ ] Start US-13: Performance benchmarking
  - [ ] Run 5 key query benchmarks
  - [ ] Analyze results
  - [ ] Optimization tweaks if needed
- [ ] Check: Benchmarks complete

**Friday**:
- [ ] Daily standup
- [ ] US-13: Monitoring setup
  - [ ] Set up Prometheus metrics
  - [ ] Create 4 Grafana dashboards
  - [ ] Configure alerts (Slack)
- [ ] Check: Monitoring setup in progress

**Monday (Week 2)**:
- [ ] Daily standup
- [ ] US-13: Deployment preparation
  - [ ] Write deployment script
  - [ ] Write rollback script
  - [ ] Test rollback in staging
- [ ] Check: Deployment scripts ready

**Tuesday**:
- [ ] Daily standup
- [ ] US-13: Final validation
  - [ ] Run full validation suite in staging
  - [ ] All 15 health checks pass
  - [ ] Performance benchmarks meet targets
- [ ] Afternoon: Team briefing + stakeholder notification
- [ ] Check: Ready for go-live

**Wednesday: GO-LIVE DAY 🚀**:
- [ ] Morning: Pre-deployment checklist
  - [ ] Backup production database
  - [ ] Team assembled (on-call)
  - [ ] Stakeholders notified
  - [ ] Rollback script tested
- [ ] 10:00 AM: Execute deployment
  - [ ] Stop indexer
  - [ ] Backup DB
  - [ ] Run migrations
  - [ ] Validate migration
  - [ ] Restart indexer
  - [ ] Monitor logs (30 min)
  - [ ] Run performance benchmarks
  - [ ] Run health checks
  - [ ] Validate dashboards
  - [ ] Enable monitoring alerts
- [ ] 12:00 PM: Deployment validation
  - [ ] All health checks passing
  - [ ] Query performance <250ms
  - [ ] Dashboards showing data
  - [ ] No errors in logs
- [ ] Afternoon: Monitor metrics
  - [ ] Watch for anomalies
  - [ ] Respond to issues quickly
  - [ ] Stakeholder update (success!)
- [ ] Check: Production deployed successfully

**Thursday**:
- [ ] Daily standup
- [ ] Post-deployment monitoring (24h)
  - [ ] Monitor all metrics
  - [ ] Verify cost calculations vs API bills
  - [ ] Verify no data loss (compare counts)
  - [ ] Collect team feedback
- [ ] Check: Production stable, 0 critical issues

**Friday**:
- [ ] Sprint validation:
  - [ ] All 2 stories complete (5 points)
  - [ ] 15+ health checks 100% passing
  - [ ] Production deployed
  - [ ] Monitoring active
  - [ ] Zero regressions
  - [ ] Query performance <250ms
- [ ] Sprint review + epic retrospective
- [ ] Document lessons learned
- [ ] Celebrate epic completion! 🎉🎉🎉
- [ ] Check: Epic complete (34 points)

### 11.6 Post-Deployment Checklist

**Week 1 Post-Deployment** (Feb 19-25):
- [ ] Daily: Monitor health check reports
- [ ] Daily: Review Grafana dashboards
- [ ] Daily: Check for alerts
- [ ] Mid-week: Validate cost calculations vs API bills
- [ ] End of week: Team retrospective
- [ ] Document any issues + resolutions
- [ ] Check: Production stable >99.9% uptime

**Week 2-4 Post-Deployment** (Feb 26 - Mar 17):
- [ ] Weekly: Review health check trends
- [ ] Weekly: Performance monitoring
- [ ] Bi-weekly: Stakeholder check-in
- [ ] Collect feedback on new dashboards
- [ ] Document feature requests for future work
- [ ] Check: All features being used

**Month 3 Post-Deployment** (May):
- [ ] Validate ROI (~$50K savings achieved)
- [ ] Measure dashboard adoption
- [ ] Review error analytics impact
- [ ] Plan advanced features (semantic search, etc.)
- [ ] Epic success report to leadership
- [ ] Check: Epic ROI validated

---

## 12. Appendices

### Appendix A: Audit Report Summary

**Source**: `audit-reports/data-audit-comprehensive-2026-01-10.md`

**Key Findings**:
- **Data Volume**: 232K JSON files (2GB), 877 sessions, 43,060 messages, 187,331 parts
- **Field Coverage**: 70% (1,400 fields captured, 600 fields lost = 430K data points)
- **P0 Blockers**: 5 critical issues
  - Plan 45 tables empty (0 records)
  - Root tokens hardcoded to 0 (100% cost reports wrong)
  - Race conditions in bulk/real-time loading
  - 8+ missing critical indexes
  - error_data VARCHAR instead of JSON
- **Data Loss Breakdown**:
  - TEXT parts: 75% coverage (length, format, embeddings missing)
  - TOOL calls: 80% coverage (timing, retries, cache missing)
  - REASONING: 65% coverage (budget, depth, tokens missing)
  - STEP events: 85% coverage (CPU, memory missing)
  - PATCHES: 60% coverage (commit msg, author, branch missing)
  - COMPACTION: 40% coverage (compression stats missing)
  - FILES: 55% coverage (size, OCR, source missing)

**Business Impact**:
- 40-50% of analytics capability blocked
- 15+ features cannot be implemented
- Cost tracking completely broken
- Performance issues blocking adoption

### Appendix B: Sprint File References

**Sprint 0 (P0 Fixes)**:
- File: `docs/sprints/2026-01-data-quality-sprint0.md`
- Stories: US-1 through US-5 (14 points)
- Duration: 3-5 days
- Focus: Critical blockers

**Sprint 1 (Extraction)**:
- File: `docs/sprints/2026-01-data-quality-sprint1.md`
- Stories: US-6 through US-9 (7 points)
- Duration: 7 days
- Focus: Data recovery

**Sprint 2 (Enrichment)**:
- File: `docs/sprints/2026-01-data-quality-sprint2.md`
- Stories: US-10, US-11 (8 points)
- Duration: 11-14 days
- Focus: Cost tracking + schema optimization

**Sprint 3 (Go-Live)**:
- File: `docs/sprints/2026-01-data-quality-sprint3.md`
- Stories: US-12, US-13 (5 points)
- Duration: 8-9 days
- Focus: Validation + production deployment

### Appendix C: Epic Reference

**File**: `docs/epics/epic-data-quality.md`

**Epic ID**: DQ-001  
**Priority**: P0 - Critical  
**Status**: Planned  
**Owner**: Engineering Team  
**Duration**: 6 weeks (4 sprints)  
**Points**: 34 total

**Strategic Objectives**:
1. Fix all P0 blockers (5 issues)
2. Recover 430K lost data points
3. Optimize query performance (50% improvement)
4. Deploy to production with monitoring

### Appendix D: Technical Glossary

| Term | Definition |
|------|-----------|
| **Plan 45** | OpenCode Status Bar's advanced tracing architecture featuring exchanges (user↔assistant turns) and hierarchical timeline views |
| **DuckDB** | In-process SQL database optimized for analytics, used for OpenCode Status Bar analytics storage |
| **Bulk Loader** | Initial data ingestion process that loads all historical JSON files into the database |
| **Real-time Watcher** | Continuous monitoring process that loads new JSON files as they're created |
| **Race Condition** | Potential data loss or duplication when bulk loading transitions to real-time watching without proper synchronization |
| **Root Tokens** | Token count from root-level API traces, used for accurate cost calculation |
| **Backfill** | Process of retroactively populating data for existing records when a new field is added |
| **Denormalization** | Database optimization technique of splitting a large table into multiple focused tables |
| **Health Check** | Automated validation query that verifies data integrity and completeness |
| **EXPLAIN Plan** | Database query analysis showing how queries are executed and which indexes are used |
| **p50/p95/p99** | Percentile metrics (median, 95th, 99th percentile) used for performance analysis |

### Appendix E: Related Documentation

**Code Documentation**:
- `src/opencode_status_bar/analytics/README.md` - Analytics architecture overview
- `src/opencode_status_bar/analytics/db.py` - Database schema documentation
- `src/opencode_status_bar/analytics/indexer/README.md` - Data pipeline architecture

**Audit Reports**:
- `audit-reports/data-audit-comprehensive-2026-01-10.md` - Complete data audit
- `audit-reports/architecture-audit-2026-01-10.md` - Architecture analysis

**Configuration**:
- `.env` - Environment configuration
- `pyproject.toml` - Project dependencies

**Testing**:
- `tests/README.md` - Testing strategy and patterns
- `Makefile` - Common commands (test, lint, etc.)

### Appendix F: Contact Information

**Project Team**:
- **Tech Lead**: TBD
- **Backend Engineer**: TBD
- **Data Engineer**: TBD
- **DevOps/SRE**: TBD
- **QA Engineer**: TBD

**Stakeholders**:
- **VP Engineering**: TBD
- **CTO**: TBD
- **Product Manager**: TBD

**Communication Channels**:
- Slack: #data-quality-epic
- Email: data-quality-team@company.com
- Dashboard: [Link to real-time dashboard]
- Docs: `docs/plans/plan-47-data-quality-improvement.md`

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-10 | Bob (SM) | Initial master plan created |

**Approval**:
- [ ] Tech Lead: _________________ Date: _________
- [ ] VP Engineering: _________________ Date: _________
- [ ] CTO: _________________ Date: _________

**Next Review Date**: After each sprint (Jan 17, Jan 26, Feb 9, Feb 18)

---

## 🎯 Quick Reference Card

**Epic At a Glance**:
- **Goal**: 100% data quality (from 70%)
- **Duration**: 6 weeks
- **Team**: 2.5 FTE avg
- **Budget**: ~$28K
- **ROI**: ~180% in Year 1

**Sprint Overview**:
1. **Sprint 0** (5 days): Fix 5 P0 blockers → Plan 45 working
2. **Sprint 1** (7 days): Recover 430K data points → Analytics enabled
3. **Sprint 2** (14 days): Cost tracking + schema optimization → Features unlocked
4. **Sprint 3** (9 days): Validation + go-live → Production ready

**Success Criteria**:
- ✅ All P0 fixed
- ✅ 430K data points recovered
- ✅ Query performance <250ms (50% faster)
- ✅ 40+ dashboards available (from 25)
- ✅ Cost accuracy ±5% (from 100% wrong)
- ✅ Production deployed with monitoring

**Key Contacts**:
- Project Slack: #data-quality-epic
- Dashboard: [Link]
- Tech Lead: TBD

---

**END OF PLAN 47: DATA QUALITY IMPROVEMENT**

*Last Updated: January 10, 2026*  
*Status: Ready for Execution* ✅
