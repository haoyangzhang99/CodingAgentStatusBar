# Plan de Refactoring - Complexite Cyclomatique

> Sprint de refactoring pour ramener les fonctions critiques a une complexite C ou moins (score <= 20)

## Contexte

Analyse Radon du projet OpenCode Status Bar identifiant 3 fonctions de complexite E (score > 30).
Ces fonctions sont difficiles a maintenir, tester et deboguer.

**Objectif** : Reduire la complexite de E (>30) a C (<=20) via extraction de methodes et separation des responsabilites.

---

## Story 1 : Refactorer `_add_critical_items`

### Metadata

| Champ | Valeur |
|-------|--------|
| **Fichier** | `src/opencode_status_bar/ui/menu.py` |
| **Fonction** | `_add_critical_items` |
| **Lignes** | 470-578 (~108 lignes) |
| **Score actuel** | E (35) |
| **Score cible** | C (<=20) |
| **Story Points** | 2 |

### Description du probleme

La fonction `_add_critical_items` affiche 4 categories d'items de securite (commands, reads, writes, webfetches) avec un code quasi-identique repete 4 fois :

```python
# Pattern repete 4 fois :
items = auditor.get_xxx(5)
if items:
    menu.add(rumps.MenuItem("emoji -- Category --"))
    for item in items:
        emoji = "..." if item.risk_level == "critical" else "..."
        short = truncate(item.xxx)
        menu_item = rumps.MenuItem(...)
        # Tooltip building
        menu.add(menu_item)
```

**Causes de complexite** :
- 4 blocs de code dupliques (DRY violation)
- Logique de formatage MITRE/EDR inline
- Conditions imbriquees pour les tooltips

### Strategie de refactoring

**Pattern : Extract Method + Polymorphisme leger**

1. **Extraire `_add_category_items()`** - methode generique pour une categorie
2. **Creer un dataclass `CategoryConfig`** - encapsule emoji, titre, getter, formateur
3. **Simplifier la boucle principale** - iterer sur les configs

### Implementation proposee

```python
@dataclass
class CategoryConfig:
    emoji: str
    title: str
    getter: Callable
    path_attr: str  # "command", "file_path", "url"

def _add_category_items(
    self, 
    menu: rumps.MenuItem, 
    config: CategoryConfig, 
    items: list
) -> None:
    """Add items for a single security category."""
    if not items:
        return
    
    menu.add(rumps.MenuItem(f"{config.emoji} -- {config.title} --"))
    for item in items:
        menu.add(self._format_security_item(item, config))

def _format_security_item(self, item, config: CategoryConfig) -> rumps.MenuItem:
    """Format a single security item with tooltip."""
    # Logique de formatage centralisee
    ...

def _add_critical_items(self, menu: rumps.MenuItem, auditor) -> None:
    """Add critical/high risk items to security menu."""
    categories = [
        CategoryConfig("laptop", "Commands", auditor.get_critical_commands, "command"),
        CategoryConfig("book", "File Reads", auditor.get_sensitive_reads, "file_path"),
        CategoryConfig("pencil", "File Writes", auditor.get_sensitive_writes, "file_path"),
        CategoryConfig("globe", "Web Fetches", auditor.get_risky_webfetches, "url"),
    ]
    
    has_items = False
    for config in categories:
        items = config.getter(5)
        if items:
            has_items = True
            self._add_category_items(menu, config, items)
    
    if not has_items:
        menu.add(rumps.MenuItem("checkmark No critical items"))
```

### Criteres d'acceptation

- [ ] **AC1** : Score Radon de `_add_critical_items` <= 10
- [ ] **AC2** : Score Radon de chaque methode extraite <= 10
- [ ] **AC3** : Tests unitaires pour `_format_security_item()` avec couverture MITRE/EDR
- [ ] **AC4** : Tests de regression : le menu de securite affiche les memes items
- [ ] **AC5** : Zero duplication de code entre les 4 categories

### Tests

```bash
# Verification complexite
radon cc src/opencode_status_bar/ui/menu.py -a -s | grep "_add_critical_items\|_format_security\|_add_category"

# Tests unitaires
pytest tests/test_menu.py -v -k "security"
```

---

## Story 2 : Refactorer `extract_root_sessions`

### Metadata

| Champ | Valeur |
|-------|--------|
| **Fichier** | `src/opencode_status_bar/analytics/loaders/traces.py` |
| **Fonction** | `extract_root_sessions` |
| **Lignes** | 131-315 (~185 lignes) |
| **Score actuel** | E (32) |
| **Score cible** | C (<=20) |
| **Story Points** | 3 |

### Description du probleme

La fonction `extract_root_sessions` fait 3 choses distinctes melangees :

1. **Phase 1** : Collecte des sessions root (parcours fichiers)
2. **Phase 2** : Tri par date
3. **Phase 3** : Traitement avec throttling + creation de traces

**Causes de complexite** :
- 3 phases distinctes dans une seule fonction (SRP violation)
- Logique multi-segment vs single-segment imbriquee
- Try/except disperses
- Boucles imbriquees avec conditions multiples

### Strategie de refactoring

**Pattern : Extract Method + Pipeline**

1. **Extraire `_collect_root_sessions()`** - Phase 1 pure
2. **Extraire `_create_trace_from_session()`** - Creation d'une trace
3. **Extraire `_create_segment_traces()`** - Gestion multi-segments
4. **Simplifier la fonction principale** - Pipeline clair

### Implementation proposee

```python
@dataclass
class SessionData:
    """Raw session data before trace creation."""
    session_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    duration_ms: Optional[int]
    data: dict
    file_path: Path

def _collect_root_sessions(
    session_dir: Path, 
    cutoff: datetime
) -> list[SessionData]:
    """Phase 1: Collect all root sessions from disk."""
    # Logique de parcours fichiers
    ...

def _create_single_trace(
    session: SessionData,
    segments: list[AgentSegment],
    first_message: Optional[str],
) -> AgentTrace:
    """Create trace for single-agent session."""
    ...

def _create_segment_traces(
    session: SessionData,
    segments: list[AgentSegment],
    first_message: Optional[str],
) -> list[AgentTrace]:
    """Create traces for multi-agent session."""
    ...

def extract_root_sessions(
    storage_path: Path,
    max_days: int = 30,
    throttle_ms: int = 10,
    segment_analysis_days: int = 1,
) -> list[AgentTrace]:
    """Extract root sessions (pipeline pattern)."""
    session_dir = storage_path / "session"
    message_dir = storage_path / "message"
    
    if not session_dir.exists():
        return []
    
    cutoff = datetime.now() - timedelta(days=max_days)
    segment_cutoff = datetime.now() - timedelta(days=segment_analysis_days)
    
    # Phase 1: Collect
    sessions = _collect_root_sessions(session_dir, cutoff)
    
    # Phase 2: Sort (newest first)
    sessions.sort(key=lambda x: x.created_at, reverse=True)
    
    # Phase 3: Process
    traces = []
    for session in sessions:
        traces.extend(
            _process_session(session, message_dir, segment_cutoff, throttle_ms)
        )
    
    return traces
```

### Criteres d'acceptation

- [ ] **AC1** : Score Radon de `extract_root_sessions` <= 8
- [ ] **AC2** : Score Radon de chaque methode extraite <= 12
- [ ] **AC3** : Tests unitaires pour `_collect_root_sessions()` avec mocks filesystem
- [ ] **AC4** : Tests pour sessions single-agent vs multi-agent
- [ ] **AC5** : Performance : pas de regression > 5% sur dataset reel

### Tests

```bash
# Verification complexite
radon cc src/opencode_status_bar/analytics/loaders/traces.py -a -s | grep "extract_root\|_collect\|_create"

# Tests unitaires
pytest tests/test_traces.py -v -k "root_session"

# Test performance (optionnel)
time python -c "from opencode_status_bar.analytics.loaders.traces import extract_root_sessions; ..."
```

---

## Story 3 : Refactorer `load_traces`

### Metadata

| Champ | Valeur |
|-------|--------|
| **Fichier** | `src/opencode_status_bar/analytics/loaders/traces.py` |
| **Fonction** | `load_traces` |
| **Lignes** | 428-582 (~155 lignes) |
| **Score actuel** | E (31) |
| **Score cible** | C (<=20) |
| **Story Points** | 3 |

### Description du probleme

La fonction `load_traces` melange 5 responsabilites :

1. **Schema** : Creation de table si absente
2. **Extraction** : Appel des extracteurs
3. **Resolution parents** : Mapping child_session_id -> parent_trace
4. **Enrichissement** : Batch lookup parent_agent et tokens
5. **Insertion** : Ecriture en base

**Causes de complexite** :
- 5 phases distinctes (SRP violation severe)
- Try/except imbriques pour chaque phase
- Logique de resolution parent complexe
- SQL inline repete

### Strategie de refactoring

**Pattern : Extract Method + Service Layer**

1. **Extraire `_ensure_traces_table()`** - DDL isole
2. **Extraire `_resolve_parent_traces()`** - Logique de parentage
3. **Extraire `_enrich_traces_from_db()`** - Batch lookups
4. **Extraire `_insert_traces_batch()`** - Insertion avec gestion erreurs
5. **Simplifier `load_traces()`** - Orchestration pure

### Implementation proposee

```python
def _ensure_traces_table(conn) -> None:
    """Ensure agent_traces table exists (DDL)."""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_traces (...)
        """)
    except Exception:
        pass  # Table already exists

def _resolve_parent_traces(traces: list[AgentTrace]) -> None:
    """Resolve parent_trace_id for each trace (in-place mutation)."""
    parent_by_child_session = {
        t.child_session_id: t 
        for t in traces 
        if t.child_session_id
    }
    
    for trace in traces:
        if "_seg" in trace.trace_id:
            continue  # Segments already resolved
        
        parent = parent_by_child_session.get(trace.session_id)
        if parent and parent.trace_id != trace.trace_id:
            trace.parent_trace_id = parent.trace_id
            trace.parent_agent = parent.subagent_type

def _enrich_parent_agents(conn, traces: list[AgentTrace]) -> None:
    """Batch resolve parent_agent from messages table."""
    ...

def _enrich_tokens(conn, traces: list[AgentTrace]) -> None:
    """Batch resolve tokens from child session messages."""
    ...

def _insert_traces(conn, traces: list[AgentTrace]) -> int:
    """Insert traces into database, return success count."""
    ...

def load_traces(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load agent traces into the database (orchestrator)."""
    conn = db.connect()
    
    # 1. Ensure schema
    _ensure_traces_table(conn)
    
    # 2. Extract traces
    traces = extract_traces(storage_path, max_days)
    traces.extend(extract_root_sessions(storage_path, max_days))
    
    if not traces:
        info("No traces found")
        return 0
    
    # 3. Resolve hierarchy
    _resolve_parent_traces(traces)
    
    # 4. Enrich from DB
    _enrich_parent_agents(conn, traces)
    _enrich_tokens(conn, traces)
    
    # 5. Insert
    _insert_traces(conn, traces)
    
    count = conn.execute("SELECT COUNT(*) FROM agent_traces").fetchone()[0]
    info(f"Loaded {count} traces")
    return count
```

### Criteres d'acceptation

- [ ] **AC1** : Score Radon de `load_traces` <= 6
- [ ] **AC2** : Score Radon de chaque methode extraite <= 12
- [ ] **AC3** : Tests unitaires pour `_resolve_parent_traces()` avec hierarchies complexes
- [ ] **AC4** : Tests pour `_enrich_tokens()` avec sessions manquantes
- [ ] **AC5** : Gestion d'erreur : une trace en erreur ne bloque pas les autres

### Tests

```bash
# Verification complexite
radon cc src/opencode_status_bar/analytics/loaders/traces.py -a -s | grep "load_traces\|_ensure\|_resolve\|_enrich\|_insert"

# Tests unitaires
pytest tests/test_traces.py -v -k "load"

# Test integration
pytest tests/test_traces.py -v -k "integration"
```

---

## Resume du Sprint

| Story | Fonction | Score E | Score Cible | Points |
|-------|----------|---------|-------------|--------|
| 1 | `_add_critical_items` | 35 | <=20 | 2 |
| 2 | `extract_root_sessions` | 32 | <=20 | 3 |
| 3 | `load_traces` | 31 | <=20 | 3 |
| **Total** | | | | **8** |

## Definition of Done

- [ ] Toutes les fonctions refactorees ont un score Radon C ou moins
- [ ] Couverture de tests >= 80% sur le code refactore
- [ ] Zero regression sur les tests existants
- [ ] Code review approuvee
- [ ] Documentation des nouvelles methodes (docstrings)

## Commandes de verification

```bash
# Verification globale complexite
radon cc src/opencode_status_bar/ui/menu.py src/opencode_status_bar/analytics/loaders/traces.py -a -s

# Tests complets
pytest tests/test_menu.py tests/test_traces.py -v --cov=src/opencode_status_bar

# Linting
ruff check src/opencode_status_bar/ui/menu.py src/opencode_status_bar/analytics/loaders/traces.py
```
