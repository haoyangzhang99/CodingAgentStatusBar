# Plan 46 - Unified Indexer v2 (DuckDB-Only Pipeline)

## Executive Summary

Refonte du système d'indexation pour éliminer le goulot d'étranglement Python realtime (250 files/sec) en unifiant bulk et realtime dans un seul pipeline DuckDB micro-batch (~5,000 files/sec).

| Métrique | Actuel (HybridIndexer) | Cible (v2) | Gain |
|----------|------------------------|------------|------|
| Realtime throughput | 250 files/sec | 5,000 files/sec | **20x** |
| Latence événement→DB | 500ms - 2s | < 500ms | **2-4x** |
| Fichiers manqués | Possible (watchdog) | 0 (réconciliation) | **∞** |
| Pipelines à maintenir | 2 (DuckDB + Python) | 1 (DuckDB) | **50%** |

## Contexte et Problématique

### Architecture actuelle : HybridIndexer

```
┌─────────────────────────────────────────────────────────────────┐
│                        HybridIndexer                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐     ┌──────────────────────┐          │
│  │     BulkLoader       │     │     FileWatcher      │          │
│  │   (DuckDB Native)    │     │     (Watchdog)       │          │
│  │                      │     │                      │          │
│  │  • read_json_auto()  │     │  • Python callbacks  │          │
│  │  • ~20,000 files/s   │     │  • ~250 files/s      │ ← GOULOT │
│  │  • Historical only   │     │  • Real-time only    │          │
│  └──────────┬───────────┘     └──────────┬───────────┘          │
│             │                            │                       │
│             └────────────┬───────────────┘                       │
│                          ▼                                       │
│                   ┌──────────────┐                               │
│                   │  Analytics   │                               │
│                   │   DuckDB     │                               │
│                   └──────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

### Problèmes identifiés

1. **Performance asymétrique** : 80x de différence entre bulk (20k/s) et realtime (250/s)
2. **Double maintenance** : Deux flux de données à maintenir et tester
3. **Fiabilité watchdog** : Peut manquer des événements sous forte charge
4. **Complexité** : Queue, phases, transitions bulk→realtime

## Architecture Cible : Unified DuckDB Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    Unified Indexer v2                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FILE DETECTION LAYER                                            │
│  ┌──────────────────────┐     ┌──────────────────────┐          │
│  │   Watchdog Primary   │     │  Periodic Reconciler │          │
│  │   (~100ms latency)   │     │   (every 30 seconds) │          │
│  └──────────┬───────────┘     └──────────┬───────────┘          │
│             │                            │                       │
│             └────────────┬───────────────┘                       │
│                          ▼                                       │
│  BATCHING LAYER                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                  BatchCollector                               ││
│  │  • 200ms collection window                                    ││
│  │  • Max 100 files per batch                                    ││
│  │  • Triggers: window elapsed OR max files reached              ││
│  │  • Thread-safe queue with deduplication                       ││
│  └────────────────────────┬─────────────────────────────────────┘│
│                           ▼                                      │
│  DUCKDB PROCESSING LAYER                                         │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │              DuckDB Micro-Batch INSERT                        ││
│  │  • read_json_auto([file1, file2, ...])                        ││
│  │  • ~5,000 files/sec sustained                                 ││
│  │  • Single INSERT per batch                                    ││
│  └────────────────────────┬─────────────────────────────────────┘│
│                           ▼                                      │
│  TRACKING LAYER                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │              indexed_files Table                              ││
│  │  • file_path (PK), mtime, size, indexed_at, status            ││
│  │  • Enables reconciliation queries                             ││
│  │  • Fast "needs indexing" checks                               ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Flux de données détaillé

```
         ┌─────────────┐
         │  Watchdog   │  ──────┐
         └─────────────┘        │
                                ▼
         ┌─────────────┐   ┌─────────────────┐
         │ Reconciler  │──▶│ BatchCollector  │
         └─────────────┘   │                 │
                           │  files: []      │
                           │  timer: 200ms   │
                           │  max: 100       │
                           └────────┬────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │ Trigger conditions:    │                        │
           │ • len(files) >= 100    │                        │
           │ • timer elapsed        │                        │
           │ • force_flush() called │                        │
           └────────────────────────┼────────────────────────┘
                                    ▼
                           ┌─────────────────┐
                           │  DuckDB Batch   │
                           │    INSERT       │
                           │                 │
                           │ read_json_auto( │
                           │   [f1,f2,f3...])│
                           └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ indexed_files   │
                           │ UPDATE          │
                           └─────────────────┘
```

## Composants Techniques

### 1. BatchCollector

```python
class BatchCollector:
    """
    Accumule les fichiers détectés et déclenche des micro-batches.
    
    Thread-safe avec deduplication automatique.
    """
    
    def __init__(
        self,
        window_ms: int = 200,
        max_files: int = 100,
        on_batch_ready: Callable[[List[Path]], None]
    ):
        self._pending: Set[Path] = set()  # Dedup automatique
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._window_ms = window_ms
        self._max_files = max_files
        self._on_batch_ready = on_batch_ready
    
    def add(self, file_path: Path) -> None:
        """Ajoute un fichier au batch en cours."""
        with self._lock:
            self._pending.add(file_path)
            
            if len(self._pending) >= self._max_files:
                self._flush_locked()
            elif self._timer is None:
                self._start_timer()
    
    def _flush_locked(self) -> None:
        """Flush le batch (appelé avec lock acquis)."""
        if not self._pending:
            return
        
        batch = list(self._pending)
        self._pending.clear()
        self._cancel_timer()
        
        # Callback hors du lock
        threading.Thread(
            target=self._on_batch_ready,
            args=(batch,),
            daemon=True
        ).start()
```

### 2. Reconciler

```python
class Reconciler:
    """
    Réconciliation périodique pour rattraper les fichiers manqués.
    
    Scanne le filesystem et compare avec indexed_files.
    """
    
    def __init__(
        self,
        storage_path: Path,
        db: AnalyticsDB,
        interval_seconds: int = 30,
        on_missing_files: Callable[[List[Path]], None]
    ):
        self._storage_path = storage_path
        self._db = db
        self._interval = interval_seconds
        self._on_missing = on_missing_files
        self._running = False
    
    def find_missing_files(self) -> List[Path]:
        """
        Trouve les fichiers sur le filesystem non présents dans indexed_files.
        
        Utilise DuckDB pour la comparaison efficace.
        """
        conn = self._db.connect()
        
        # Requête efficace: fichiers sur disque mais pas dans indexed_files
        # ou avec mtime plus récent
        query = """
        WITH filesystem AS (
            SELECT 
                filename AS path,
                file_modified_time AS mtime
            FROM glob('{storage}/**/*.json')
        ),
        indexed AS (
            SELECT file_path, mtime 
            FROM indexed_files 
            WHERE status = 'indexed'
        )
        SELECT f.path
        FROM filesystem f
        LEFT JOIN indexed i ON f.path = i.file_path
        WHERE i.file_path IS NULL
           OR f.mtime > i.mtime
        """
        
        result = conn.execute(
            query.format(storage=self._storage_path)
        ).fetchall()
        
        return [Path(row[0]) for row in result]
```

### 3. Table indexed_files

```sql
CREATE TABLE IF NOT EXISTS indexed_files (
    file_path VARCHAR PRIMARY KEY,
    file_type VARCHAR NOT NULL,        -- 'session', 'message', 'part'
    mtime DOUBLE NOT NULL,             -- Modification time (epoch)
    size BIGINT NOT NULL,              -- File size in bytes
    indexed_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR DEFAULT 'indexed',  -- 'indexed', 'error', 'pending'
    error_message VARCHAR,             -- Si status='error'
    record_id VARCHAR                  -- ID de l'enregistrement créé
);

-- Index pour la réconciliation rapide
CREATE INDEX IF NOT EXISTS idx_indexed_files_mtime 
ON indexed_files(mtime);

CREATE INDEX IF NOT EXISTS idx_indexed_files_status 
ON indexed_files(status);
```

### 4. DuckDB Micro-Batch INSERT

```python
def process_batch(self, files: List[Path]) -> int:
    """
    Traite un batch de fichiers via DuckDB read_json_auto.
    
    Args:
        files: Liste de chemins de fichiers JSON
        
    Returns:
        Nombre de fichiers traités avec succès
    """
    if not files:
        return 0
    
    conn = self._db.connect()
    
    # Grouper par type de fichier
    by_type: Dict[str, List[Path]] = defaultdict(list)
    for f in files:
        file_type = self._detect_file_type(f)
        by_type[file_type].append(f)
    
    total_processed = 0
    
    for file_type, type_files in by_type.items():
        # Construire la liste de fichiers pour DuckDB
        file_list = ", ".join(f"'{f}'" for f in type_files)
        
        # INSERT via read_json_auto avec liste de fichiers
        query = self._get_insert_query(file_type, file_list)
        
        try:
            conn.execute(query)
            total_processed += len(type_files)
            
            # Mettre à jour indexed_files
            self._update_tracking(conn, type_files, file_type, 'indexed')
            
        except Exception as e:
            self._update_tracking(conn, type_files, file_type, 'error', str(e))
    
    return total_processed
```

## Migration Strategy

### Phase 1 : Feature Flag (Sprint 1)

```python
# config.py
UNIFIED_INDEXER_V2_ENABLED = os.getenv("UNIFIED_INDEXER_V2", "false") == "true"
UNIFIED_INDEXER_V2_ROLLOUT = float(os.getenv("UNIFIED_INDEXER_V2_ROLLOUT", "0"))

def should_use_v2() -> bool:
    """Détermine si on utilise l'indexer v2."""
    if UNIFIED_INDEXER_V2_ENABLED:
        return True
    
    if UNIFIED_INDEXER_V2_ROLLOUT > 0:
        # Rollout progressif basé sur hash du hostname
        import hashlib
        host_hash = int(hashlib.md5(socket.gethostname().encode()).hexdigest(), 16)
        return (host_hash % 100) < (UNIFIED_INDEXER_V2_ROLLOUT * 100)
    
    return False
```

### Phase 2 : Rollout Progressif (Sprint 3)

1. **10%** : Machines de dev internes
2. **25%** : Utilisateurs beta opt-in
3. **50%** : Validation 48h
4. **100%** : General availability

### Phase 3 : Cleanup (Sprint 3)

- Supprimer `HybridIndexer` et code associé
- Supprimer flag de migration
- Archiver documentation v1

## Risques et Mitigations

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| Performance micro-batch < prévue | High | Medium | Benchmark avant merge, ajuster window/max |
| Watchdog manque plus d'events que prévu | Medium | Low | Reconciler couvre, ajuster intervalle |
| DuckDB lock contention | High | Low | Connection pool, retries exponentiels |
| Migration corrompt données | Critical | Very Low | Feature flag, rollback instantané |
| Réconciliation trop lente sur 1M fichiers | Medium | Medium | Index optimisés, pagination |

## Métriques de Succès

### Performance

- [ ] Realtime throughput ≥ 5,000 files/sec (POC avant implementation)
- [ ] Latence p95 < 500ms (event → DB)
- [ ] Reconciliation 1M files < 10 secondes

### Fiabilité

- [ ] 0 fichiers manqués sur 1 semaine de test
- [ ] Recovery automatique après crash
- [ ] Pas de corruption de données

### Maintenabilité

- [ ] Réduction de 40% du code d'indexation
- [ ] Tests unitaires ≥ 90% coverage
- [ ] Documentation architecture complète

## Timeline

| Sprint | Focus | Livrables |
|--------|-------|-----------|
| **Sprint 1** | Fondations | indexed_files, BatchCollector, Reconciler, tests unitaires |
| **Sprint 2** | Intégration | UnifiedIndexerV2, intégration flux, benchmarks |
| **Sprint 3** | Migration | Rollout 10%→100%, cleanup, documentation |

## Annexes

### A. Benchmark DuckDB Micro-Batch (POC)

```python
# benchmark_microbatch.py
"""
Résultats attendus sur MacBook Pro M1:
- 100 files batch: ~5,200 files/sec
- 50 files batch: ~4,800 files/sec
- 10 files batch: ~3,500 files/sec
- 1 file (current): ~250 files/sec
"""
```

### B. Requêtes SQL optimisées

Voir `src/opencode_status_bar/analytics/indexer/queries_v2.py`

### C. Schéma de données complet

Voir migration `migrations/004_indexed_files.sql`

---

**Auteur**: Architecture Team  
**Date**: 2026-01-08  
**Version**: 1.0  
**Status**: Draft - En attente validation POC
