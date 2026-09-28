# Code Quality & Security Sprint Plan

**Project**: OpenCode Status Bar v2.11.0  
**Created**: 2026-01-06  
**Total Story Points**: 34  
**Estimated Duration**: 2 sprints (4-5 days)

---

## Sprint Overview

### Goals
1. Eliminate all critical CVE vulnerabilities (P0)
2. Remove SQL injection attack vectors (P1)
3. Achieve mypy type compliance (P2)
4. Clean up code hygiene warnings (P3)

### Priority Order
| Priority | Category | Points | Risk Level |
|----------|----------|--------|------------|
| P0 | CVE Fix | 1 | Critical |
| P1 | SQL Injection | 8 | High |
| P2 | Type Safety | 18 | Medium |
| P3 | Code Hygiene | 7 | Low |

### Sprint Allocation

**Sprint 1** (P0 + P1 + P2 partial): 17 points
- CVE fix (1 pt)
- SQL injection remediation (8 pts)
- Type safety - high-error files (8 pts)

**Sprint 2** (P2 + P3): 17 points
- Type safety - remaining files (10 pts)
- Code hygiene cleanup (7 pts)

---

## Epic 1: Security Fixes (P0 + P1)

> **Goal**: Eliminate critical vulnerabilities and SQL injection risks  
> **Total Points**: 9  
> **Priority**: Critical

### Definition of Done
- [ ] `uv run pip-audit` returns 0 vulnerabilities
- [ ] `uv run bandit -r src -ll` returns 0 high-severity issues (B608)
- [ ] All SQL queries use parameterized statements
- [ ] All tests pass: `uv run pytest -n 8`

---

### Story 1.1: Update aiohttp to Fix CVEs

**Description**: Update aiohttp from 3.13.2 to 3.13.3 to resolve 8 CVE vulnerabilities.

**Story Points**: 1

**Files to Modify**:
- `pyproject.toml`
- `uv.lock`

**Acceptance Criteria**:
- [ ] aiohttp version pinned to `>=3.13.3`
- [ ] Lock file regenerated with `uv lock`
- [ ] `uv run pip-audit` shows 0 vulnerabilities
- [ ] Existing tests pass without modification

**Implementation**:
```bash
# Update pyproject.toml
# Then regenerate lock
uv lock
uv sync

# Verify
uv run pip-audit
uv run pytest -n 8
```

---

### Story 1.2: Fix SQL Injection in analytics/db.py

**Description**: Replace f-string SQL construction with parameterized queries in the main database module.

**Story Points**: 2

**Files to Modify**:
- `src/opencode_status_bar/analytics/db.py`

**Acceptance Criteria**:
- [ ] All `f"SELECT..."` patterns replaced with parameterized queries
- [ ] DuckDB parameter binding syntax used (`?` placeholders)
- [ ] No B608 warnings from bandit on this file
- [ ] All database tests pass

**Verification**:
```bash
uv run bandit src/opencode_status_bar/analytics/db.py -f txt
uv run pytest tests/analytics/test_db.py -v
```

---

### Story 1.3: Fix SQL Injection in bulk_loader.py

**Description**: Secure SQL queries in the bulk loader module used for batch data imports.

**Story Points**: 2

**Files to Modify**:
- `src/opencode_status_bar/analytics/indexer/bulk_loader.py`

**Acceptance Criteria**:
- [ ] Dynamic table names handled safely (whitelist validation)
- [ ] Query parameters passed via parameter binding
- [ ] No B608 warnings from bandit
- [ ] Bulk import tests pass

**Verification**:
```bash
uv run bandit src/opencode_status_bar/analytics/indexer/bulk_loader.py -f txt
uv run pytest tests/analytics/indexer/ -v -k bulk
```

---

### Story 1.4: Fix SQL Injection in Loaders Module

**Description**: Secure all SQL queries in the loaders submodule (traces, sessions, messages, etc.).

**Story Points**: 2

**Files to Modify**:
- `src/opencode_status_bar/analytics/loaders/traces.py`
- `src/opencode_status_bar/analytics/loaders/sessions.py`
- `src/opencode_status_bar/analytics/loaders/messages.py`
- `src/opencode_status_bar/analytics/loaders/parts.py`
- `src/opencode_status_bar/analytics/loaders/files.py`
- `src/opencode_status_bar/analytics/loaders/delegations.py`
- `src/opencode_status_bar/analytics/loaders/skills.py`

**Acceptance Criteria**:
- [ ] All dynamic SQL converted to parameterized queries
- [ ] Table name injections prevented via whitelist
- [ ] No B608 warnings in loaders directory
- [ ] Loader integration tests pass

**Verification**:
```bash
uv run bandit src/opencode_status_bar/analytics/loaders/ -r -f txt
uv run pytest tests/analytics/loaders/ -v
```

---

### Story 1.5: Fix SQL Injection in Security Repository

**Description**: Secure the security database repository queries.

**Story Points**: 1

**Files to Modify**:
- `src/opencode_status_bar/security/db/repository.py`

**Acceptance Criteria**:
- [ ] All queries use parameter binding
- [ ] No B608 warnings from bandit
- [ ] Security module tests pass

**Verification**:
```bash
uv run bandit src/opencode_status_bar/security/ -r -f txt
uv run pytest tests/security/ -v
```

---

## Epic 2: Type Safety (P2)

> **Goal**: Achieve mypy compliance across the codebase  
> **Total Points**: 18  
> **Priority**: Medium

### Definition of Done
- [ ] `uv run mypy src/opencode_status_bar --strict` returns 0 errors
- [ ] All type annotations are explicit (no `Any` unless justified)
- [ ] All tests pass: `uv run pytest -n 8`

---

### Story 2.1: Fix Tuple Indexing in tracing/helpers.py

**Description**: Add proper null checks and type guards for database row access patterns.

**Story Points**: 3

**Files to Modify**:
- `src/opencode_status_bar/analytics/tracing/helpers.py`

**Error Pattern**: `[index]` - accessing `row[0]` where `row` could be None

**Acceptance Criteria**:
- [ ] All row accesses guarded with null checks
- [ ] Return types explicitly annotated
- [ ] Helper functions have full type signatures
- [ ] 0 mypy errors in this file

**Verification**:
```bash
uv run mypy src/opencode_status_bar/analytics/tracing/helpers.py --strict
```

---

### Story 2.2: Fix Type Errors in Loaders - Part 1

**Description**: Add type annotations and fix type errors in high-traffic loaders.

**Story Points**: 3

**Files to Modify**:
- `src/opencode_status_bar/analytics/loaders/traces.py`
- `src/opencode_status_bar/analytics/loaders/sessions.py`
- `src/opencode_status_bar/analytics/loaders/messages.py`

**Acceptance Criteria**:
- [ ] All functions have complete type annotations
- [ ] Optional returns properly typed
- [ ] Database row types defined or imported
- [ ] 0 mypy errors in these files

**Verification**:
```bash
uv run mypy src/opencode_status_bar/analytics/loaders/traces.py \
            src/opencode_status_bar/analytics/loaders/sessions.py \
            src/opencode_status_bar/analytics/loaders/messages.py --strict
```

---

### Story 2.3: Fix Type Errors in Loaders - Part 2

**Description**: Complete type safety for remaining loader modules.

**Story Points**: 3

**Files to Modify**:
- `src/opencode_status_bar/analytics/loaders/parts.py`
- `src/opencode_status_bar/analytics/loaders/files.py`
- `src/opencode_status_bar/analytics/loaders/delegations.py`
- `src/opencode_status_bar/analytics/loaders/skills.py`
- `src/opencode_status_bar/analytics/loaders/enrichment.py`
- `src/opencode_status_bar/analytics/loaders/utils.py`

**Acceptance Criteria**:
- [ ] Consistent type patterns across all loaders
- [ ] Shared types extracted to `loaders/__init__.py` or types module
- [ ] 0 mypy errors in loaders directory

**Verification**:
```bash
uv run mypy src/opencode_status_bar/analytics/loaders/ --strict
```

---

### Story 2.4: Fix Return Type Errors in api/client.py

**Description**: Correct return type annotations in the API client module.

**Story Points**: 2

**Files to Modify**:
- `src/opencode_status_bar/api/client.py`

**Error Pattern**: `[return-value]` - functions returning wrong types

**Acceptance Criteria**:
- [ ] All async methods properly typed with `Awaitable`
- [ ] Error handling returns typed properly
- [ ] Response parsing has correct types
- [ ] 0 mypy errors in this file

**Verification**:
```bash
uv run mypy src/opencode_status_bar/api/client.py --strict
```

---

### Story 2.5: Fix Assignment Errors in dashboard/security.py

**Description**: Fix type assignment errors in the security dashboard section.

**Story Points**: 2

**Files to Modify**:
- `src/opencode_status_bar/dashboard/sections/security.py`

**Error Pattern**: `[assignment]` - incompatible types in assignments

**Acceptance Criteria**:
- [ ] Widget types properly annotated
- [ ] Signal connections typed correctly
- [ ] Layout assignments use correct types
- [ ] 0 mypy errors in this file

**Verification**:
```bash
uv run mypy src/opencode_status_bar/dashboard/sections/security.py --strict
```

---

### Story 2.6: Fix Type Errors in Indexer Module

**Description**: Add type safety to the indexer module components.

**Story Points**: 3

**Files to Modify**:
- `src/opencode_status_bar/analytics/indexer/bulk_loader.py`
- `src/opencode_status_bar/analytics/indexer/handlers.py`
- `src/opencode_status_bar/analytics/indexer/queries.py`
- `src/opencode_status_bar/analytics/indexer/parsers.py`

**Acceptance Criteria**:
- [ ] Batch processing functions fully typed
- [ ] Handler callbacks have explicit signatures
- [ ] Query builders return typed results
- [ ] 0 mypy errors in indexer directory

**Verification**:
```bash
uv run mypy src/opencode_status_bar/analytics/indexer/ --strict
```

---

### Story 2.7: Fix Remaining Type Errors

**Description**: Address remaining mypy errors across the codebase.

**Story Points**: 2

**Files to Modify**:
- `src/opencode_status_bar/analytics/queries/*.py`
- `src/opencode_status_bar/api/routes/*.py`
- Any remaining files with errors

**Acceptance Criteria**:
- [ ] All query modules fully typed
- [ ] API route handlers typed
- [ ] Full codebase passes mypy strict
- [ ] 0 total mypy errors

**Verification**:
```bash
uv run mypy src/opencode_status_bar --strict
```

---

## Epic 3: Code Hygiene (P3)

> **Goal**: Clean up low-severity bandit warnings and improve code quality  
> **Total Points**: 7  
> **Priority**: Low

### Definition of Done
- [ ] `uv run bandit -r src` returns 0 issues (or only documented exceptions)
- [ ] All exception handlers have proper logging
- [ ] Subprocess calls are secure
- [ ] All tests pass: `uv run pytest -n 8`

---

### Story 3.1: Fix Silent Exception Handlers (B110)

**Description**: Replace `try/except/pass` patterns with proper error logging.

**Story Points**: 2

**Files to Modify**:
- Multiple files with B110 warnings (14 instances)

**Pattern to Fix**:
```python
# Before
try:
    risky_operation()
except Exception:
    pass

# After
try:
    risky_operation()
except Exception:
    logger.debug("Operation failed", exc_info=True)
```

**Acceptance Criteria**:
- [ ] All `except: pass` replaced with logging
- [ ] Appropriate log levels used (debug/warning/error)
- [ ] No B110 warnings from bandit
- [ ] Log messages are informative

**Verification**:
```bash
uv run bandit -r src -f txt | grep B110
```

---

### Story 3.2: Secure Subprocess Calls (B603/B607)

**Description**: Audit and secure subprocess invocations.

**Story Points**: 2

**Files to Modify**:
- Files with subprocess calls (15 instances)

**Acceptance Criteria**:
- [ ] All subprocess calls use explicit executable paths or are validated
- [ ] `shell=False` used where possible
- [ ] Input sanitization for any user-provided arguments
- [ ] Documented exceptions for legitimate use cases
- [ ] B603/B607 warnings addressed or justified

**Verification**:
```bash
uv run bandit -r src -f txt | grep -E "B603|B607"
```

---

### Story 3.3: Clean Up Subprocess Imports (B404)

**Description**: Review subprocess imports and ensure they're necessary.

**Story Points**: 1

**Files to Modify**:
- Files importing subprocess (5 instances)

**Acceptance Criteria**:
- [ ] Unnecessary subprocess imports removed
- [ ] Remaining imports justified and documented
- [ ] Consider alternatives where appropriate

**Verification**:
```bash
uv run bandit -r src -f txt | grep B404
```

---

### Story 3.4: URL Scheme Validation (B310)

**Description**: Add URL scheme validation for user-provided URLs.

**Story Points**: 1

**Files to Modify**:
- Files with URL handling (3 instances)

**Acceptance Criteria**:
- [ ] URL schemes validated (http/https only)
- [ ] No arbitrary URL opening from untrusted input
- [ ] B310 warnings resolved

**Verification**:
```bash
uv run bandit -r src -f txt | grep B310
```

---

### Story 3.5: Replace Weak Hash and Fix Temp Files (B324/B108)

**Description**: Replace MD5 with secure alternatives and fix temp file handling.

**Story Points**: 1

**Files to Modify**:
- File using MD5 (1 instance)
- File with temp file usage (1 instance)

**Acceptance Criteria**:
- [ ] MD5 replaced with SHA-256 (if security-relevant) or documented if not
- [ ] Temp files use secure creation methods (`tempfile.mkstemp`)
- [ ] B324 and B108 warnings resolved

**Verification**:
```bash
uv run bandit -r src -f txt | grep -E "B324|B108"
```

---

## Verification Commands Reference

### Full Security Audit
```bash
# CVE check
uv run pip-audit

# All bandit checks
uv run bandit -r src -f txt

# High severity only
uv run bandit -r src -ll -f txt
```

### Type Checking
```bash
# Full strict check
uv run mypy src/opencode_status_bar --strict

# Single file
uv run mypy path/to/file.py --strict

# Show error codes
uv run mypy src/opencode_status_bar --strict --show-error-codes
```

### Test Suite
```bash
# Full parallel run
uv run pytest -n 8

# With coverage
uv run pytest -n 8 --cov=src/opencode_status_bar --cov-report=term-missing

# Specific module
uv run pytest tests/analytics/ -v
```

### Quick Health Check
```bash
# All-in-one verification
uv run pip-audit && \
uv run bandit -r src -ll && \
uv run mypy src/opencode_status_bar --strict && \
uv run pytest -n 8
```

---

## Appendix: File Impact Matrix

| File | SQL (P1) | Type (P2) | Hygiene (P3) |
|------|----------|-----------|--------------|
| analytics/db.py | X | | |
| analytics/indexer/bulk_loader.py | X | X | |
| analytics/loaders/*.py | X | X | |
| analytics/tracing/helpers.py | | X | |
| api/client.py | | X | |
| dashboard/sections/security.py | | X | |
| security/db/repository.py | X | | |
| Various (subprocess) | | | X |

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Story Points** | 34 |
| **Epic 1 Stories** | 5 |
| **Epic 2 Stories** | 7 |
| **Epic 3 Stories** | 5 |
| **Total Stories** | 17 |
| **Estimated Sprints** | 2 |

### Recommended Sprint Order

1. **Start with Story 1.1** (CVE fix) - Quick win, critical priority
2. **Complete Epic 1** (SQL injection) - Security-first approach
3. **Epic 2 Stories 2.1-2.3** - Type safety for data layer
4. **Epic 2 Stories 2.4-2.7** - Type safety for API/UI layer
5. **Epic 3** - Code hygiene cleanup

### Risk Mitigation

- Run tests after each story completion
- Commit frequently with clear messages
- If a story reveals more issues, create follow-up stories rather than scope creep
