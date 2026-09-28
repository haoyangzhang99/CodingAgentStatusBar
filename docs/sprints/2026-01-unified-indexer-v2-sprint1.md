# Sprint: Unified Indexer v2 - Fondations

**Sprint ID**: 2026-01-IDX  
**Epic**: IDX-001 (Unified Indexer v2)  
**Duration**: 2 weeks  
**Start Date**: 2026-01-08  
**Status**: Planned

---

## Sprint Goal

Construire les fondations du nouvel indexer : table de tracking, BatchCollector, et Reconciler avec tests complets.

## Velocity

| Métrique | Valeur |
|----------|--------|
| Points planifiés | 16 |
| Stories | 4 |
| Focus | Fondations |

---

## Stories

### US-1: Table indexed_files et Migration

**Story ID**: IDX-001-S1  
**Points**: 3  
**Priority**: P0 - Critical  
**Assignee**: TBD

**As a** système d'indexation,  
**I want** une table `indexed_files` pour tracker les fichiers indexés,  
**So that** je peux permettre la réconciliation et éviter les doublons.

**Acceptance Criteria**:
- [ ] Table `indexed_files` créée au premier démarrage
- [ ] Migration idempotente (exécutable plusieurs fois sans erreur)
- [ ] Index optimisés pour queries de réconciliation
- [ ] Tests unitaires couvrent CRUD + edge cases

**Technical Notes**:

```sql
CREATE TABLE IF NOT EXISTS indexed_files (
    file_path VARCHAR PRIMARY KEY,
    file_type VARCHAR NOT NULL,
    mtime DOUBLE NOT NULL,
    size BIGINT NOT NULL,
    indexed_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR DEFAULT 'indexed',
    error_message VARCHAR,
    record_id VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_indexed_files_mtime ON indexed_files(mtime);
CREATE INDEX IF NOT EXISTS idx_indexed_files_status ON indexed_files(status);
```

**Files**:
- `src/opencode_status_bar/analytics/db.py` - Add schema
- `src/opencode_status_bar/analytics/indexer/repository.py` - NEW
- `tests/test_indexed_files.py` - NEW

**Tasks**:
- [ ] Ajouter schema dans `db.py`
- [ ] Créer `IndexedFilesRepository` class
- [ ] Implémenter méthodes : `upsert()`, `get_by_path()`, `get_missing()`
- [ ] Écrire tests unitaires
- [ ] Vérifier migration sur DB existante

---

### US-2: Implémenter BatchCollector

**Story ID**: IDX-001-S2  
**Points**: 5  
**Priority**: P0 - Critical  
**Assignee**: TBD

**As a** système d'indexation,  
**I want** un BatchCollector qui accumule les fichiers en micro-batches,  
**So that** je peux optimiser les performances d'insertion DuckDB.

**Acceptance Criteria**:
- [ ] BatchCollector thread-safe
- [ ] Trigger sur max_files (100) OU window_ms (200ms)
- [ ] Deduplication automatique via Set
- [ ] Callback `on_batch_ready` appelé avec liste de fichiers
- [ ] `force_flush()` pour flush immédiat
- [ ] `get_stats()` retourne compteurs

**Technical Notes**:

```python
@dataclass
class BatchConfig:
    window_ms: int = 200
    max_files: int = 100
    flush_on_stop: bool = True

class BatchCollector:
    def add(self, file_path: Path) -> None: ...
    def add_many(self, files: List[Path]) -> None: ...
    def force_flush(self) -> int: ...
    def stop(self) -> None: ...
    def get_stats(self) -> dict: ...
```

**Files**:
- `src/opencode_status_bar/analytics/indexer/batch_collector.py` - NEW
- `tests/test_batch_collector.py` - NEW

**Tasks**:
- [ ] Créer `BatchConfig` dataclass
- [ ] Implémenter `BatchCollector.__init__()` avec timer setup
- [ ] Implémenter `add()` avec lock et trigger check
- [ ] Implémenter `add_many()` pour bulk addition
- [ ] Implémenter `_flush_locked()` avec callback thread
- [ ] Implémenter timer management (`_start_timer`, `_cancel_timer`)
- [ ] Tests: single file addition
- [ ] Tests: batch trigger on max_files
- [ ] Tests: batch trigger on timer
- [ ] Tests: deduplication
- [ ] Tests: thread-safety (concurrent adds)
- [ ] Tests: stop() behavior

---

### US-3: Implémenter Reconciler

**Story ID**: IDX-001-S3  
**Points**: 5  
**Priority**: P0 - Critical  
**Assignee**: TBD

**As a** système d'indexation,  
**I want** un Reconciler qui scanne périodiquement le filesystem,  
**So that** je peux garantir zéro fichier manqué.

**Acceptance Criteria**:
- [ ] Scan périodique configurable (default 30s)
- [ ] Détection fichiers nouveaux (pas dans indexed_files)
- [ ] Détection fichiers modifiés (mtime > indexed mtime)
- [ ] `scan_now()` pour scan immédiat (initial)
- [ ] Callback `on_missing_files` appelé avec liste
- [ ] Performance: < 1s pour 100k fichiers

**Technical Notes**:

```python
class Reconciler:
    def __init__(
        self,
        storage_path: Path,
        db: AnalyticsDB,
        interval_seconds: int = 30,
        on_missing_files: Callable[[List[Path]], None] = None
    ): ...
    
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def scan_now(self) -> List[Path]: ...
    def get_stats(self) -> dict: ...
```

**Query DuckDB optimisée**:
```sql
WITH filesystem AS (
    SELECT filename AS path, file_modified_time AS mtime
    FROM glob('{storage}/**/*.json')
),
indexed AS (
    SELECT file_path, mtime FROM indexed_files WHERE status = 'indexed'
)
SELECT f.path
FROM filesystem f
LEFT JOIN indexed i ON f.path = i.file_path
WHERE i.file_path IS NULL OR f.mtime > i.mtime
LIMIT 10000
```

**Files**:
- `src/opencode_status_bar/analytics/indexer/reconciler.py` - NEW
- `tests/test_reconciler.py` - NEW

**Tasks**:
- [ ] Créer classe `Reconciler`
- [ ] Implémenter `_find_missing_files()` avec query DuckDB
- [ ] Implémenter `_run_loop()` thread daemon
- [ ] Implémenter `scan_now()` synchrone
- [ ] Implémenter `get_stats()`
- [ ] Tests: détection fichiers nouveaux
- [ ] Tests: détection fichiers modifiés
- [ ] Tests: scan_now() immédiat
- [ ] Tests: periodic loop
- [ ] Tests: stop() clean shutdown
- [ ] Benchmark: 10k files

---

### US-4: Tests Complets Nouveaux Composants

**Story ID**: IDX-001-S4  
**Points**: 3  
**Priority**: P1 - High  
**Depends On**: US-1, US-2, US-3  
**Assignee**: TBD

**As a** développeur,  
**I want** une suite de tests complète pour les nouveaux composants,  
**So that** je peux garantir leur fiabilité.

**Acceptance Criteria**:
- [ ] Coverage >= 90% sur nouveaux fichiers
- [ ] Pas de tests flaky (10 runs consécutifs OK)
- [ ] Tests thread-safety validés
- [ ] Tests d'intégration composants combinés

**Files**:
- `tests/test_indexed_files.py`
- `tests/test_batch_collector.py`
- `tests/test_reconciler.py`
- `tests/test_indexer_v2_integration.py` - NEW
- `tests/conftest.py` - Add fixtures

**Tasks**:
- [ ] Review coverage des tests US-1, US-2, US-3
- [ ] Ajouter cas edge manquants
- [ ] Créer fixtures partagées dans `conftest.py`
- [ ] Test intégration: BatchCollector + Reconciler
- [ ] Test intégration: Repository + Reconciler
- [ ] Vérifier 10 runs consécutifs sans flaky
- [ ] Générer rapport coverage

---

## Sprint Backlog

| ID | Story | Points | Status | Assignee |
|----|-------|--------|--------|----------|
| US-1 | indexed_files Table | 3 | To Do | TBD |
| US-2 | BatchCollector | 5 | To Do | TBD |
| US-3 | Reconciler | 5 | To Do | TBD |
| US-4 | Tests Complets | 3 | To Do | TBD |
| **Total** | | **16** | | |

---

## Definition of Done (Sprint)

- [ ] Tous les tests passent (`make test`)
- [ ] Coverage >= 90% sur nouveaux fichiers
- [ ] Pas d'erreurs lint (`make lint`)
- [ ] Code reviewé et mergé
- [ ] Documentation inline à jour

---

## Technical Dependencies

```
US-1 (indexed_files) ─┐
                      ├──► US-4 (Tests)
US-2 (BatchCollector)─┤
                      │
US-3 (Reconciler) ────┘
```

**Note**: US-1, US-2, US-3 peuvent être développés en parallèle. US-4 les consolide.

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Query réconciliation lente | Medium | Medium | Tester avec fixtures 10k files |
| Race condition BatchCollector | Low | High | Tests thread-safety explicites |
| Migration casse DB existante | Low | High | Test sur copie de prod DB |

---

## Notes for Developers

### Setup Local Dev

```bash
# Créer branche feature
git checkout -b feature/unified-indexer-v2

# Installer deps
make install

# Run tests pendant dev
make test-watch  # ou pytest-watch
```

### File Structure After Sprint

```
src/opencode_status_bar/analytics/indexer/
├── __init__.py
├── hybrid.py               # Existing (will keep for now)
├── bulk_loader.py          # Existing
├── repository.py           # NEW (US-1)
├── batch_collector.py      # NEW (US-2)
├── reconciler.py           # NEW (US-3)
├── queries_v2.py           # NEW (queries for new components)
└── ...

tests/
├── test_indexed_files.py       # NEW (US-1)
├── test_batch_collector.py     # NEW (US-2)
├── test_reconciler.py          # NEW (US-3)
├── test_indexer_v2_integration.py  # NEW (US-4)
└── conftest.py                 # Updated with new fixtures
```

### Coding Standards

- Type hints obligatoires
- Docstrings Google-style
- Tests: Arrange-Act-Assert pattern
- Nommage: `test_<method>_<scenario>_<expected>`

---

## Daily Standup Questions

1. What did I complete yesterday?
2. What will I work on today?
3. Any blockers?

---

## Sprint Review Checklist

- [ ] Demo: indexed_files table création
- [ ] Demo: BatchCollector accumulation et flush
- [ ] Demo: Reconciler détection fichiers manquants
- [ ] Metrics: Coverage report
- [ ] Metrics: Benchmark Reconciler performance
- [ ] Feedback: équipe et stakeholders

---

## Retrospective Topics

- What went well?
- What could be improved?
- Action items for next sprint?
