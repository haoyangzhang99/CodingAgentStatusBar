# Plan 24 - Data Model Enrichment

## Contexte

Après analyse complète des fichiers JSON d'OpenCode (`~/.local/share/opencode/storage/`), nous avons identifié que notre base DuckDB ne collecte qu'environ **60% des données disponibles**.

### Données manquantes critiques

| Catégorie | Données manquantes | Impact |
|-----------|-------------------|--------|
| **TODOS** | Table entière non collectée | Pas d'analytics sur productivité |
| **PROJECTS** | Table entière non collectée | Pas de groupement par projet |
| **Sessions** | parentID, summary (additions/deletions/files) | Pas de hiérarchie, pas de stats code |
| **Messages** | mode, cost, finish_reason, working_dir | Pas de budget tracking |
| **Parts** | session_id, ended_at, duration_ms | Pas de performance tools |

## Objectif

Enrichir le data model pour collecter **100% des données utiles** d'OpenCode.

## Stratégie d'implémentation

### Phase 1 : Migration schéma DB (non destructive)

Modifier `db.py` pour ajouter les nouvelles colonnes/tables **sans perdre les données existantes**.

```sql
-- Nouvelles tables
CREATE TABLE IF NOT EXISTS todos (...)
CREATE TABLE IF NOT EXISTS projects (...)

-- Nouvelles colonnes (ALTER TABLE avec défaut NULL)
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS parent_id VARCHAR;
-- etc.
```

### Phase 2 : Enrichir le Collector

Modifier `collector.py` pour extraire les nouveaux champs des JSON.

### Phase 3 : Ajouter collecte Todos et Projects

Nouveaux handlers dans le collector pour `todo/` et `project/`.

### Phase 4 : Enrichir les Queries

Modifier `queries.py` pour exposer les nouvelles données.

### Phase 5 : Tests de régression

S'assurer que les anciennes fonctionnalités continuent de fonctionner.

## Spécifications techniques

### Nouveaux schémas

#### Table `todos`
```sql
CREATE TABLE IF NOT EXISTS todos (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR,
    content VARCHAR,
    status VARCHAR,           -- pending, in_progress, completed, cancelled
    priority VARCHAR,         -- high, medium, low
    position INTEGER,         -- ordre dans la liste
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_todos_session ON todos(session_id);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
```

#### Table `projects`
```sql
CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR PRIMARY KEY,
    worktree VARCHAR,
    vcs VARCHAR,              -- git, etc.
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_worktree ON projects(worktree);
```

### Colonnes à ajouter

#### Sessions
```sql
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS parent_id VARCHAR;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS version VARCHAR;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS additions INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS deletions INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS files_changed INTEGER DEFAULT 0;
```

#### Messages
```sql
ALTER TABLE messages ADD COLUMN IF NOT EXISTS mode VARCHAR;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS cost DECIMAL(10,6) DEFAULT 0;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS finish_reason VARCHAR;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS working_dir VARCHAR;
```

#### Parts
```sql
ALTER TABLE parts ADD COLUMN IF NOT EXISTS session_id VARCHAR;
ALTER TABLE parts ADD COLUMN IF NOT EXISTS ended_at TIMESTAMP;
ALTER TABLE parts ADD COLUMN IF NOT EXISTS duration_ms INTEGER;
ALTER TABLE parts ADD COLUMN IF NOT EXISTS call_id VARCHAR;
```

### Mapping JSON → DB

#### Session
```python
{
    "id": data.get("id"),
    "project_id": data.get("projectID"),
    "directory": data.get("directory"),
    "parent_id": data.get("parentID"),          # NEW
    "title": data.get("title"),
    "version": data.get("version"),              # NEW
    "additions": data.get("summary", {}).get("additions", 0),  # NEW
    "deletions": data.get("summary", {}).get("deletions", 0),  # NEW
    "files_changed": data.get("summary", {}).get("files", 0),  # NEW
    "created_at": timestamp(data["time"]["created"]),
    "updated_at": timestamp(data["time"]["updated"]),
}
```

#### Message
```python
{
    "id": data.get("id"),
    "session_id": data.get("sessionID"),
    "parent_id": data.get("parentID"),
    "role": data.get("role"),
    "agent": data.get("agent"),
    "model_id": data.get("modelID"),
    "provider_id": data.get("providerID"),
    "mode": data.get("mode"),                    # NEW
    "cost": data.get("cost", 0),                 # NEW
    "finish_reason": data.get("finish"),         # NEW
    "working_dir": data.get("path", {}).get("cwd"),  # NEW
    "tokens_input": data.get("tokens", {}).get("input", 0),
    "tokens_output": data.get("tokens", {}).get("output", 0),
    "tokens_reasoning": data.get("tokens", {}).get("reasoning", 0),
    "tokens_cache_read": data.get("tokens", {}).get("cache", {}).get("read", 0),
    "tokens_cache_write": data.get("tokens", {}).get("cache", {}).get("write", 0),
    "created_at": timestamp(data["time"]["created"]),
    "completed_at": timestamp(data["time"].get("completed")),
}
```

#### Part
```python
{
    "id": data.get("id"),
    "session_id": data.get("sessionID"),         # NEW
    "message_id": data.get("messageID"),
    "part_type": data.get("type"),
    "tool_name": data.get("tool"),
    "tool_status": data.get("state", {}).get("status"),
    "call_id": data.get("callID"),               # NEW
    "created_at": timestamp(data["time"]["start"]),
    "ended_at": timestamp(data["time"].get("end")),  # NEW
    "duration_ms": calculate_duration(data["time"]),  # NEW (computed)
}
```

#### Todo
```python
{
    "id": f"{session_id}_{todo['id']}",  # Composite key
    "session_id": session_id,
    "content": todo.get("content"),
    "status": todo.get("status"),
    "priority": todo.get("priority"),
    "position": index,
    "created_at": file_mtime,  # Approximation from file
    "updated_at": file_mtime,
}
```

#### Project
```python
{
    "id": data.get("id"),
    "worktree": data.get("worktree"),
    "vcs": data.get("vcs"),
    "created_at": timestamp(data["time"]["created"]),
    "updated_at": timestamp(data["time"]["updated"]),
}
```

## Fichiers à modifier

| Fichier | Modifications |
|---------|---------------|
| `src/opencode_status_bar/analytics/db.py` | Schéma enrichi, migrations |
| `src/opencode_status_bar/analytics/collector.py` | Nouveaux extracteurs |
| `src/opencode_status_bar/analytics/loader.py` | Loaders enrichis |
| `src/opencode_status_bar/analytics/models.py` | Nouveaux dataclasses |
| `src/opencode_status_bar/analytics/queries.py` | Nouvelles requêtes |
| `tests/test_analytics_*.py` | Tests de régression |

## Checklist de validation

### Phase 1 - Schéma
- [ ] Table `todos` créée
- [ ] Table `projects` créée
- [ ] Colonnes sessions ajoutées (parent_id, version, additions, deletions, files_changed)
- [ ] Colonnes messages ajoutées (mode, cost, finish_reason, working_dir)
- [ ] Colonnes parts ajoutées (session_id, ended_at, duration_ms, call_id)
- [ ] Migration non destructive (données existantes préservées)

### Phase 2 - Collector
- [ ] `_insert_session()` enrichi
- [ ] `_insert_message()` enrichi
- [ ] `_insert_part()` enrichi
- [ ] `_insert_todo()` créé
- [ ] `_insert_project()` créé
- [ ] Watcher étendu aux répertoires todo/ et project/

### Phase 3 - Queries
- [ ] Nouvelles requêtes pour todos
- [ ] Nouvelles requêtes pour projects
- [ ] Requêtes existantes compatibles

### Phase 4 - Tests
- [ ] Tests migration schéma
- [ ] Tests insertion enrichie
- [ ] Tests requêtes todos/projects
- [ ] Régression sur requêtes existantes
- [ ] Dashboard fonctionne toujours

## Notes

- La migration doit être **non destructive** : les anciennes données restent valides
- Les nouvelles colonnes ont des valeurs par défaut (NULL ou 0)
- Le collector doit gérer les deux formats (ancien et nouveau) pendant la transition
- Priorité aux données les plus utiles pour les analytics (todos, cost, duration)

---

## Notes Exécuteur

### Implementation Status: COMPLETED

#### Commits
1. `ad19f46` - feat(analytics): enrich data model with todos, projects, and new fields
2. `c4844af` - test(analytics): add comprehensive tests for enriched data model

#### Fichiers modifiés
| Fichier | Lignes | Description |
|---------|--------|-------------|
| `db.py` | +132 | Schéma enrichi, tables todos/projects, méthode migrate_schema() |
| `collector.py` | +241 | Handlers todo/project, extracteurs enrichis, watcher étendu |
| `models.py` | +49 | Dataclasses Todo, Project, TodoStats, ProjectStats |
| `queries.py` | +298 | 8 nouvelles méthodes de requêtes |
| `test_analytics.py` | +493 | 21 tests pour le nouveau data model |

#### Nouvelles fonctionnalités
- **Tables**: `todos`, `projects` avec indexes
- **Colonnes sessions**: `parent_id`, `version`, `additions`, `deletions`, `files_changed`
- **Colonnes messages**: `mode`, `cost`, `finish_reason`, `working_dir`
- **Colonnes parts**: `session_id`, `call_id`, `ended_at`, `duration_ms`
- **Queries**: `get_todos()`, `get_todo_stats()`, `get_projects()`, `get_project_stats()`, `get_code_stats()`, `get_cost_stats()`, `get_tool_performance()`, `get_session_hierarchy()`

#### Tests
- 21 nouveaux tests dans `test_analytics.py`
- 44 tests total passent (analytics + database)
- Pas de régression sur les tests existants

#### Décisions techniques
1. **Todo ID composite**: `{session_id}_{todo_id}` pour unicité
2. **Todo timestamps**: file mtime utilisé (pas disponible dans JSON)
3. **Duration calculée**: `end - start` en millisecondes
4. **Flat directory handler**: Nouveau `_reconcile_flat_directory()` pour todo/ et project/

#### Bug corrigé
- Double `except Exception` dans `db.py:get_last_refresh()` (ligne 278-280)
