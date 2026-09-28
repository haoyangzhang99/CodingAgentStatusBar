# Sprint 3: Data Quality - Validation & Go-Live

**Sprint ID**: 2026-01-DQ-S3  
**Epic**: [DQ-001 - Data Quality & Architecture Improvement](../epics/epic-data-quality.md)  
**Duration**: 8-9 days  
**Start Date**: 2026-02-10  
**End Date**: 2026-02-18  
**Status**: Planned  
**Depends On**: Sprint 2 (Enrichment complete)

---

## Sprint Goal

**Validate 100% data integrity, optimize performance to production-ready state, and deploy to production** with comprehensive monitoring and alerting.

This sprint ensures **production-ready quality** and **go-live readiness** for all data quality improvements.

---

## Velocity

| Métrique | Valeur |
|----------|--------|
| Points planifiés | 5 |
| Stories | 2 |
| Focus | Validation & Go-Live |
| Team Size | 3 FTE (dev, QA, DevOps) |
| Daily Capacity | ~0.6 points/day |

---

## Stories

### US-12: Complete Data Validation

**Story ID**: DQ-012  
**Points**: 3  
**Priority**: P2 - Medium  
**Assignee**: TBD (QA Lead)

**As a** QA lead,  
**I want** all data completeness checks automated with daily health reports,  
**So that** we can guarantee 100% data integrity on production and detect issues proactively.

**Current State**: Manual validation, no health checks → Cannot guarantee data quality

**Target State**: Automated validation suite with daily reports and alerts

**Acceptance Criteria**:
- [ ] Validation queries for each data type (15+ checks)
- [ ] Automated daily health checks (scheduled job)
- [ ] Reports on data gaps/anomalies (sent to team)
- [ ] Alerting on threshold violations (Slack/email)
- [ ] Documentation of validation rules (wiki page)
- [ ] Historical tracking of improvements (dashboard)

**Validation Checks**:

**1. Data Completeness Checks**:
```sql
-- Check 1: Plan 45 tables populated
SELECT 
    'Plan 45 Tables' as check_name,
    COUNT(*) as exchanges_count,
    (SELECT COUNT(*) FROM exchange_traces) as traces_count,
    CASE 
        WHEN COUNT(*) = 0 THEN 'FAIL: exchanges table empty'
        WHEN (SELECT COUNT(*) FROM exchange_traces) = 0 THEN 'FAIL: traces table empty'
        ELSE 'PASS'
    END as status
FROM exchanges;

-- Check 2: Root tokens not 0
SELECT 
    'Root Tokens' as check_name,
    COUNT(*) as total_sessions,
    COUNT(*) FILTER (WHERE root_tokens = 0) as zero_tokens,
    ROUND(100.0 * COUNT(*) FILTER (WHERE root_tokens > 0) / COUNT(*), 2) as pct_valid,
    CASE 
        WHEN COUNT(*) FILTER (WHERE root_tokens > 0) / COUNT(*) < 0.95 THEN 'FAIL: <95% sessions have tokens'
        ELSE 'PASS'
    END as status
FROM session_stats;

-- Check 3: Messages have root_path
SELECT 
    'Messages root_path' as check_name,
    COUNT(*) as total_messages,
    COUNT(*) FILTER (WHERE root_path IS NOT NULL) as with_root_path,
    ROUND(100.0 * COUNT(*) FILTER (WHERE root_path IS NOT NULL) / COUNT(*), 2) as pct_complete,
    CASE 
        WHEN COUNT(*) FILTER (WHERE root_path IS NOT NULL) / COUNT(*) < 0.80 THEN 'FAIL: <80% messages have root_path'
        ELSE 'PASS'
    END as status
FROM messages;

-- Check 4: Errors classified
SELECT 
    'Error Classification' as check_name,
    COUNT(*) as total_errors,
    COUNT(*) FILTER (WHERE error_category IS NOT NULL) as classified,
    ROUND(100.0 * COUNT(*) FILTER (WHERE error_category IS NOT NULL) / COUNT(*), 2) as pct_classified,
    CASE 
        WHEN COUNT(*) FILTER (WHERE error_category IS NOT NULL) / COUNT(*) < 0.95 THEN 'FAIL: <95% errors classified'
        ELSE 'PASS'
    END as status
FROM errors;

-- Check 5: Tool calls have execution time
SELECT 
    'Tool Execution Times' as check_name,
    COUNT(*) as total_tool_calls,
    COUNT(*) FILTER (WHERE execution_time_ms IS NOT NULL) as with_timing,
    ROUND(100.0 * COUNT(*) FILTER (WHERE execution_time_ms IS NOT NULL) / COUNT(*), 2) as pct_complete,
    CASE 
        WHEN COUNT(*) FILTER (WHERE execution_time_ms IS NOT NULL) / COUNT(*) < 0.90 THEN 'FAIL: <90% tools have timing'
        ELSE 'PASS'
    END as status
FROM tool_calls;

-- Check 6: File operations have git metadata
SELECT 
    'Git Metadata' as check_name,
    COUNT(*) as total_file_ops,
    COUNT(*) FILTER (WHERE git_branch IS NOT NULL) as with_git,
    ROUND(100.0 * COUNT(*) FILTER (WHERE git_branch IS NOT NULL) / COUNT(*), 2) as pct_complete,
    CASE 
        WHEN COUNT(*) FILTER (WHERE git_branch IS NOT NULL) / COUNT(*) < 0.70 THEN 'FAIL: <70% file ops have git'
        ELSE 'PASS'
    END as status
FROM file_operations;

-- Check 7: Sessions have cost data
SELECT 
    'Session Costs' as check_name,
    COUNT(*) as total_sessions,
    COUNT(*) FILTER (WHERE total_cost_usd IS NOT NULL) as with_cost,
    ROUND(100.0 * COUNT(*) FILTER (WHERE total_cost_usd IS NOT NULL) / COUNT(*), 2) as pct_complete,
    CASE 
        WHEN COUNT(*) FILTER (WHERE total_cost_usd IS NOT NULL) / COUNT(*) < 0.95 THEN 'FAIL: <95% sessions have cost'
        ELSE 'PASS'
    END as status
FROM session_resource_metrics;
```

**2. Data Integrity Checks**:
```sql
-- Check 8: No orphaned records
SELECT 
    'Orphaned Parts' as check_name,
    COUNT(*) as orphaned_count,
    CASE 
        WHEN COUNT(*) > 0 THEN 'FAIL: Orphaned parts exist'
        ELSE 'PASS'
    END as status
FROM parts p
LEFT JOIN sessions s ON p.session_id = s.session_id
WHERE s.session_id IS NULL;

-- Check 9: No duplicate exchanges
SELECT 
    'Duplicate Exchanges' as check_name,
    COUNT(*) - COUNT(DISTINCT exchange_id) as duplicate_count,
    CASE 
        WHEN COUNT(*) != COUNT(DISTINCT exchange_id) THEN 'FAIL: Duplicates found'
        ELSE 'PASS'
    END as status
FROM exchanges;

-- Check 10: Foreign key consistency
SELECT 
    'Foreign Key Consistency' as check_name,
    (SELECT COUNT(*) FROM tool_calls tc LEFT JOIN parts p ON tc.part_id = p.part_id WHERE p.part_id IS NULL) as orphaned_tools,
    (SELECT COUNT(*) FROM file_operations fo LEFT JOIN parts p ON fo.part_id = p.part_id WHERE p.part_id IS NULL) as orphaned_files,
    CASE 
        WHEN orphaned_tools + orphaned_files > 0 THEN 'FAIL: Foreign key violations'
        ELSE 'PASS'
    END as status;
```

**3. Performance Checks**:
```sql
-- Check 11: Query performance
SELECT 
    'Query Performance' as check_name,
    query_name,
    execution_time_ms,
    CASE 
        WHEN execution_time_ms > 250 THEN 'FAIL: Query >250ms'
        ELSE 'PASS'
    END as status
FROM (
    SELECT 'agents_by_name' as query_name, 
           EXTRACT(MILLISECONDS FROM (NOW() - start_time)) as execution_time_ms
    FROM (SELECT NOW() as start_time, name FROM agents WHERE name = 'test') t
) queries;

-- Check 12: Index usage
EXPLAIN SELECT * FROM agents WHERE name = 'test';  -- Should use idx_agents_name
EXPLAIN SELECT * FROM tool_calls WHERE tool_name = 'mcp_read';  -- Should use idx_tool_calls_name
```

**4. Business Logic Checks**:
```sql
-- Check 13: Cost calculations reasonable
SELECT 
    'Cost Anomalies' as check_name,
    COUNT(*) FILTER (WHERE total_cost_usd > 100) as expensive_sessions,
    COUNT(*) FILTER (WHERE total_cost_usd < 0) as negative_costs,
    CASE 
        WHEN COUNT(*) FILTER (WHERE total_cost_usd < 0) > 0 THEN 'FAIL: Negative costs found'
        WHEN COUNT(*) FILTER (WHERE total_cost_usd > 100) > (SELECT COUNT(*) * 0.01 FROM session_resource_metrics) THEN 'WARN: >1% sessions >$100'
        ELSE 'PASS'
    END as status
FROM session_resource_metrics;

-- Check 14: Token counts reasonable
SELECT 
    'Token Count Anomalies' as check_name,
    COUNT(*) FILTER (WHERE total_input_tokens > 1000000) as very_large,
    COUNT(*) FILTER (WHERE total_input_tokens < 0) as negative,
    CASE 
        WHEN COUNT(*) FILTER (WHERE total_input_tokens < 0) > 0 THEN 'FAIL: Negative tokens'
        ELSE 'PASS'
    END as status
FROM session_resource_metrics;

-- Check 15: Error rates reasonable
SELECT 
    'Error Rate' as check_name,
    COUNT(*) as total_parts,
    (SELECT COUNT(*) FROM errors) as error_count,
    ROUND(100.0 * (SELECT COUNT(*) FROM errors) / COUNT(*), 2) as error_pct,
    CASE 
        WHEN (SELECT COUNT(*) FROM errors) / COUNT(*) > 0.10 THEN 'WARN: >10% error rate'
        ELSE 'PASS'
    END as status
FROM parts;
```

**Daily Health Check Script**:
```python
#!/usr/bin/env python3
"""Daily data health check script."""

import duckdb
from datetime import datetime
from pathlib import Path

def run_health_checks():
    """Run all health checks and generate report."""
    db = duckdb.connect('analytics.duckdb')
    
    checks = [
        'plan45_tables', 'root_tokens', 'messages_root_path',
        'error_classification', 'tool_timing', 'git_metadata',
        'session_costs', 'orphaned_records', 'duplicate_exchanges',
        'foreign_keys', 'query_performance', 'cost_anomalies',
        'token_anomalies', 'error_rate'
    ]
    
    results = []
    for check in checks:
        result = db.execute(f"SELECT * FROM health_check_{check}()").fetchone()
        results.append({
            'check': check,
            'status': result[0],
            'details': result[1]
        })
    
    # Generate report
    report = generate_report(results)
    
    # Send alerts for failures
    failures = [r for r in results if r['status'] == 'FAIL']
    if failures:
        send_alert(failures)
    
    # Save historical record
    save_health_check_history(results)
    
    return report

def send_alert(failures):
    """Send alert to Slack/email for failures."""
    # Implementation: Slack webhook or email
    pass

def save_health_check_history(results):
    """Save results to health_check_history table."""
    # Implementation: INSERT INTO health_check_history
    pass
```

**Files**:
- `src/opencode_status_bar/analytics/validation/` - NEW (validation module)
  - `__init__.py`
  - `checks.py` - All validation check functions
  - `health_check.py` - Daily health check script
  - `report_generator.py` - Generate HTML/Markdown reports
  - `alerting.py` - Slack/email alerting
- `src/opencode_status_bar/analytics/db.py` - Add health_check_history table
- `scripts/run_daily_health_check.sh` - Cron job script
- `tests/test_validation.py` - NEW

**Tasks**:
- [ ] Implement 15+ validation check functions
- [ ] Create health_check_history table
- [ ] Implement daily health check script
- [ ] Implement report generator (HTML + Markdown)
- [ ] Implement alerting (Slack webhook)
- [ ] Set up cron job for daily checks
- [ ] Create validation dashboard (Grafana/Metabase)
- [ ] Document validation rules in wiki
- [ ] Unit tests for each check
- [ ] Integration test for full health check
- [ ] Manual validation run (verify results)

---

### US-13: Performance Optimization & Go-Live

**Story ID**: DQ-013  
**Points**: 2  
**Priority**: P3 - Low  
**Assignee**: TBD (DevOps)

**As a** DevOps engineer,  
**I want** all performance optimizations deployed to production with monitoring,  
**So that** users experience fast, reliable analytics and we can detect issues proactively.

**Current State**: Changes in staging, no monitoring → Not production-ready

**Target State**: Production deployment with full monitoring and rollback capability

**Acceptance Criteria**:
- [ ] Query benchmarks show <250ms latency (50% improvement)
- [ ] All P0 indexes deployed to production
- [ ] Monitoring dashboards show improvement metrics
- [ ] Zero regressions from baseline (validated)
- [ ] Rollback procedure tested and documented
- [ ] Team signed off on go-live readiness

**Performance Benchmarks**:
```sql
-- Benchmark 1: Agents by name (should be <10ms)
EXPLAIN ANALYZE SELECT * FROM agents WHERE name = 'test';

-- Benchmark 2: Tools by session (should be <50ms)
EXPLAIN ANALYZE 
SELECT tc.tool_name, COUNT(*) as calls
FROM tool_calls tc
JOIN parts p ON tc.part_id = p.part_id
WHERE p.session_id = 'test-session'
GROUP BY tc.tool_name;

-- Benchmark 3: Error breakdown (should be <100ms)
EXPLAIN ANALYZE
SELECT error_category, COUNT(*) as count
FROM errors
GROUP BY error_category;

-- Benchmark 4: Cost trends (should be <200ms)
EXPLAIN ANALYZE
SELECT DATE(created_at) as date, SUM(total_cost_usd) as cost
FROM session_resource_metrics
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;

-- Benchmark 5: Session details (should be <150ms)
EXPLAIN ANALYZE
SELECT s.session_id, m.model_name, COUNT(p.part_id) as parts,
       srm.total_cost_usd, srm.total_input_tokens + srm.total_output_tokens as tokens
FROM sessions s
JOIN models m ON s.model_id = m.model_id
LEFT JOIN parts p ON s.session_id = p.session_id
LEFT JOIN session_resource_metrics srm ON s.session_id = srm.session_id
GROUP BY s.session_id, m.model_name, srm.total_cost_usd, srm.total_input_tokens, srm.total_output_tokens
LIMIT 100;
```

**Monitoring Dashboards**:

**1. Performance Monitoring**:
- Query latency (p50, p95, p99)
- Database size growth
- Index hit rate
- Cache hit rate

**2. Data Quality Monitoring**:
- Data completeness (% fields populated)
- Error classification rate
- Data freshness (last update time)
- Health check pass rate

**3. Business Metrics Monitoring**:
- Daily cost trends
- Token usage trends
- Error rate trends
- Session count trends

**4. System Health**:
- Indexer running status
- Bulk loader status
- Race condition incidents
- Data loss incidents (should be 0)

**Deployment Checklist**:
```markdown
## Pre-Deployment
- [ ] All tests pass in staging
- [ ] Performance benchmarks meet targets
- [ ] Health checks pass 100%
- [ ] Backup database created
- [ ] Rollback procedure documented
- [ ] Team briefed on deployment plan
- [ ] Stakeholders notified (maintenance window)

## Deployment Steps
1. [ ] Stop indexer (graceful shutdown)
2. [ ] Backup production database
3. [ ] Run migrations (Plan 45, indexes, schema changes)
4. [ ] Validate migration (data integrity checks)
5. [ ] Restart indexer with new code
6. [ ] Monitor logs for errors (first 30 min)
7. [ ] Run performance benchmarks
8. [ ] Run health checks
9. [ ] Validate dashboards show data
10. [ ] Enable monitoring alerts

## Post-Deployment
- [ ] Monitor for 24h (alerts on anomalies)
- [ ] Verify cost calculations match API bills
- [ ] Verify no data loss (compare counts)
- [ ] Collect team feedback
- [ ] Document lessons learned
- [ ] Celebrate success! 🎉

## Rollback (if needed)
1. [ ] Stop indexer
2. [ ] Restore database from backup
3. [ ] Revert code to previous version
4. [ ] Restart indexer
5. [ ] Notify stakeholders
6. [ ] Post-mortem analysis
```

**Monitoring Setup**:
```python
# Example: Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Query performance
query_duration = Histogram('query_duration_seconds', 'Query execution time', ['query_name'])

# Data quality
data_completeness = Gauge('data_completeness_percent', 'Data completeness percentage', ['field'])

# Business metrics
daily_cost = Gauge('daily_cost_usd', 'Daily API cost in USD')
session_count = Counter('session_count_total', 'Total number of sessions')
error_count = Counter('error_count_total', 'Total number of errors', ['category'])

# System health
indexer_status = Gauge('indexer_status', 'Indexer running status (1=running, 0=stopped)')
```

**Files**:
- `src/opencode_status_bar/analytics/monitoring/` - NEW (monitoring module)
  - `__init__.py`
  - `metrics.py` - Prometheus metrics
  - `dashboards/` - Grafana dashboard configs
  - `alerts.yml` - Alert rules
- `docs/deployment/go-live-checklist.md` - NEW
- `docs/deployment/rollback-procedure.md` - NEW
- `scripts/deploy_production.sh` - NEW
- `scripts/rollback_production.sh` - NEW
- `tests/test_performance.py` - NEW

**Tasks**:
- [ ] Run performance benchmarks in staging
- [ ] Set up Prometheus metrics collection
- [ ] Create Grafana dashboards (4 dashboards)
- [ ] Configure alerts (Slack integration)
- [ ] Write deployment script
- [ ] Write rollback script
- [ ] Test rollback procedure in staging
- [ ] Create go-live checklist document
- [ ] Schedule deployment window (low-traffic time)
- [ ] Execute deployment
- [ ] Monitor for 24h post-deployment
- [ ] Collect feedback and document lessons learned

---

## Sprint Backlog

| ID | Story | Points | Status | Assignee | Week |
|----|-------|--------|--------|----------|------|
| DQ-012 | Complete Data Validation | 3 | To Do | QA Lead | Week 1 |
| DQ-013 | Performance & Go-Live | 2 | To Do | DevOps | Week 1-2 |
| **Total** | | **5** | | | |

---

## Daily Schedule

### Week 1: Validation & Preparation

**Day 1 (Mon)**: Validation Framework
- Morning: DQ-012 implement validation checks (1-7)
- Afternoon: DQ-012 implement validation checks (8-15)

**Day 2 (Tue)**: Health Check Automation
- Morning: DQ-012 health check script + report generator
- Afternoon: DQ-012 alerting setup (Slack webhook)

**Day 3 (Wed)**: Validation Testing
- Morning: DQ-012 unit tests for all checks
- Afternoon: DQ-012 manual validation run + dashboard

**Day 4 (Thu)**: Performance Benchmarking
- Morning: DQ-013 run all performance benchmarks
- Afternoon: DQ-013 analyze results + optimization tweaks

**Day 5 (Fri)**: Monitoring Setup
- Morning: DQ-013 Prometheus metrics + Grafana dashboards
- Afternoon: DQ-013 alert configuration

### Week 2: Go-Live

**Day 6 (Mon)**: Deployment Preparation
- Morning: DQ-013 deployment scripts + testing
- Afternoon: DQ-013 rollback testing in staging

**Day 7 (Tue)**: Final Validation
- Morning: Run full validation suite in staging
- Afternoon: Team briefing + stakeholder notification

**Day 8 (Wed)**: **GO-LIVE DAY** 🚀
- Morning: Execute deployment (low-traffic window)
- Afternoon: Monitor logs + validate deployment

**Day 9 (Thu)**: Post-Deployment Monitoring
- All day: Monitor metrics, respond to issues, collect feedback

---

## Definition of Done (Sprint)

### Code Quality
- [ ] All tests pass (`make test`)
- [ ] Coverage >= 80% on new code
- [ ] No lint errors (`make lint`)
- [ ] Code reviewed and approved

### Validation
- [ ] 15+ health checks implemented
- [ ] All health checks pass 100%
- [ ] Daily health check cron job scheduled
- [ ] Validation dashboard live

### Performance
- [ ] Query benchmarks <250ms (50% improvement)
- [ ] All indexes deployed
- [ ] Zero performance regressions

### Monitoring
- [ ] 4 Grafana dashboards live
- [ ] Prometheus metrics collecting
- [ ] Alerts configured (Slack)
- [ ] 24h monitoring post-deployment

### Deployment
- [ ] Production deployment successful
- [ ] Zero critical bugs in production
- [ ] Rollback procedure tested
- [ ] Team sign-off on go-live

---

## Technical Dependencies

```
Sprint 2 (Enrichment) ──► DQ-012 (Validation) ───┐
                                                  │
                          DQ-013 (Go-Live) ──────┼──► Production Ready ✅
                                                  │
                          (Sequential flow)       │
```

**Critical Path**: Sprint 2 → DQ-012 (validate) → DQ-013 (deploy) → Production

**Sequential**: Must validate before deploying

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Deployment causes downtime | Low | High | Deploy during low-traffic window, gradual rollout, rollback ready |
| Performance regression in prod | Low | High | Extensive benchmarking, staging validation, rollback if needed |
| Health checks too noisy | Medium | Low | Fine-tune thresholds, gradual alert rollout |
| Monitoring not capturing issues | Medium | Medium | Test alerts in staging, manual spot checks first 24h |
| Team not ready for go-live | Low | Medium | Team briefing, documentation, on-call rotation |
| Rollback fails | Low | Critical | Test rollback procedure multiple times in staging |

---

## Success Criteria

### Sprint-Level Metrics
- [ ] All 2 stories completed (5 points)
- [ ] Zero critical bugs in production
- [ ] Test coverage >= 80%
- [ ] Deployment successful

### Business Impact
- [ ] 100% data completeness validated
- [ ] Query performance 50% faster (<250ms)
- [ ] Production analytics fully functional
- [ ] Cost tracking accurate (±5% vs API bills)
- [ ] Plan 45 UI showing data

### Epic Completion
- [ ] All 13 user stories completed (34 points total)
- [ ] 430K data points recovered
- [ ] 5 P0 blockers fixed
- [ ] Production-ready in 6 weeks

---

## References

- **Epic**: [epic-data-quality.md](../epics/epic-data-quality.md)
- **Sprint 0**: [2026-01-data-quality-sprint0.md](2026-01-data-quality-sprint0.md)
- **Sprint 1**: [2026-01-data-quality-sprint1.md](2026-01-data-quality-sprint1.md)
- **Sprint 2**: [2026-01-data-quality-sprint2.md](2026-01-data-quality-sprint2.md)
- **Audit Report**: [data-audit-comprehensive-2026-01-10.md](../../audit-reports/data-audit-comprehensive-2026-01-10.md)

---

## Sprint Review Checklist

**Demos**:
- [ ] Show validation dashboard (15+ checks passing)
- [ ] Show performance benchmarks (before/after)
- [ ] Show monitoring dashboards (4 dashboards)
- [ ] Show production analytics working
- [ ] Show cost tracking accuracy
- [ ] Show health check report

**Metrics**:
- [ ] Velocity: 5 points completed
- [ ] Epic velocity: 34 points total (all 4 sprints)
- [ ] Health checks: 100% passing
- [ ] Performance: 50% improvement (<250ms)
- [ ] Production uptime: 99.9%

**Feedback**:
- [ ] Stakeholder sign-off on production deployment
- [ ] Finance team sign-off on cost accuracy
- [ ] Analyst feedback on query performance
- [ ] Team feedback on monitoring/alerting

---

## Retrospective Topics

- Deployment process effectiveness?
- Monitoring and alerting adequacy?
- Health check coverage complete?
- Performance optimization learnings?
- Epic-level retrospective (6 weeks)?
- Celebration and team recognition! 🎉

---

## Epic-Level Retrospective

### What We Accomplished
- ✅ Fixed 5 P0 blockers
- ✅ Recovered 430K lost data points
- ✅ Improved query performance 50x
- ✅ Enabled cost tracking and forecasting
- ✅ Implemented comprehensive monitoring
- ✅ Production-ready in 6 weeks

### Key Learnings
- [Document key technical learnings]
- [Document process improvements]
- [Document team collaboration wins]

### Action Items for Future
- [Document improvements for next epic]
- [Document technical debt to address]
- [Document team growth areas]

---

## Notes for Developers

### Pre-Deployment Checklist

```bash
# 1. Run all tests
make test

# 2. Run performance benchmarks
python scripts/benchmark_queries.py

# 3. Run health checks
python scripts/run_health_check.py

# 4. Backup database
cp analytics.duckdb analytics.duckdb.pre-golive-backup

# 5. Validate staging
python scripts/validate_staging.py
```

### Deployment Commands

```bash
# 1. Stop indexer
systemctl stop opencode-indexer

# 2. Backup production DB
scripts/backup_production_db.sh

# 3. Deploy
scripts/deploy_production.sh

# 4. Validate
scripts/validate_production.sh

# 5. Monitor
tail -f /var/log/opencode-indexer/indexer.log
```

### Rollback Commands

```bash
# If issues detected
scripts/rollback_production.sh
```

### Key Monitoring URLs

- Grafana: http://grafana.internal/d/opencode-analytics
- Prometheus: http://prometheus.internal/graph
- Health Check: http://analytics.internal/health
- Alerts: #opencode-alerts (Slack)

### On-Call Rotation

**Week 1 Post-Deployment**:
- Primary: [Name]
- Secondary: [Name]
- Escalation: [Manager]

**Alert Response SLA**:
- Critical: 15 minutes
- High: 1 hour
- Medium: 4 hours

### Testing Strategy

1. **Unit Tests**: All validation checks
2. **Integration Tests**: End-to-end health check
3. **Performance Tests**: Query benchmarks
4. **Deployment Tests**: Deploy + rollback in staging
5. **Production Tests**: Smoke tests post-deployment

### Coding Standards

- Type hints required on all functions
- Docstrings: Google-style
- Tests: Arrange-Act-Assert pattern
- Naming: `test_<function>_<scenario>_<expected>`

---

## Celebration! 🎉

After 6 weeks of hard work:
- 5 P0 blockers → ✅ Fixed
- 430K data points → ✅ Recovered
- Query performance → ✅ 50x faster
- Cost tracking → ✅ Accurate
- Production → ✅ Live!

**Thank you to the team for making this epic a success!**
