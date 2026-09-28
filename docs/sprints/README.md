# Sprints - OpenCode Status Bar

Sprint records and current work tracking.

## Current Sprint

**[Data Quality - Parts Enrichment](./2026-01-parts-enrichment.md)** (17 points, 5 stories)

Enriching the loader to process 5 types of parts currently ignored (reasoning, step-finish, step-start, patch, compaction, file). This improves debugging visibility, cost precision, and traceability.

| Story | Points | Status |
|-------|--------|--------|
| US-01: Schema DB - New tables and columns | 3 | To Do |
| US-02: Loader - Enriched parts | 5 | To Do |
| US-03: Service - Query methods | 3 | To Do |
| US-04: API - New endpoints | 3 | To Do |
| US-05: Tests - Complete coverage | 3 | To Do |

## Completed Sprints

| Sprint | Date | Points | Stories |
|--------|------|--------|---------|
| [Code Quality](../archive/plans/code-quality-plan.md) | Jan 2026 | 34 | 17 |
| [Complexity Refactoring](../archive/plans/refactoring-plan.md) | Jan 2026 | 8 | 3 |
| [UI Modernization](./2026-01-ui-modernization.md) | Jan 2026 | 8 | 5 |

## Cancelled Sprints

| Sprint | Date | Points | Reason |
|--------|------|--------|--------|
| [Unified Indexer v2 - Sprint 1](./2026-01-unified-indexer-v2-sprint1.md) | 2026-01-10 | 16 | **CANCELLED**: Unified indexer approach superseded by data quality improvements. Worktree caused UI freezes. |

**Note**: The unified indexer v2 was cancelled in favor of incremental data quality improvements via parts enrichment (see [Parts Enrichment Sprint](./2026-01-parts-enrichment.md)). This approach delivers immediate value without the complexity and UI performance issues of a full indexer rewrite.

## Sprint Workflow

1. Pick plan(s) from [backlog/](../backlog/)
2. Create sprint file: `YYYY-MM-name.md`
3. Break into user stories with acceptance criteria
4. Execute and track progress
5. Move completed plans to [archive/](../archive/)

## User Story Convention

```markdown
### US-XX: Short title

**As a** [role],
**I want** [action],
**So that** [benefit].

**Acceptance Criteria**:
- [ ] Criterion 1
- [ ] Criterion 2

**Files**: `path/to/file.py`
```
