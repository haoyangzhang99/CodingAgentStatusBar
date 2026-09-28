# Plan 35 - Todos & Projects Loading

## Contexte

L'analyse du stockage OpenCode a revele deux sources de donnees completement ignorees :

| Source | Fichiers | Contenu | Charge |
|--------|----------|---------|--------|
| `storage/todo/` | 88 fichiers | Todos par session | **Non** |
| `storage/project/` | 5 fichiers | Metadonnees projets | **Non** |

Les tables `todos` et `projects` existent dans le schema DB (`db.py`) mais :
- Aucune fonction `load_todos()` dans `loader.py`
- Aucune fonction `load_projects()` dans `loader.py`
- Les tables restent vides

### Exemple todo reel (ses_xxx.json)
```json
[
  {"id": "1", "content": "Determine which MCP client...", "status": "completed", "priority": "high"},
  {"id": "2", "content": "Add Chrome DevTools MCP...", "status": "in_progress", "priority": "high"}
]
```

### Exemple project reel (hash.json)
```json
{
  "id": "61ab6c1cb2dcb238f74ea62a1d899faca11bd485",
  "worktree": "/Users/sofiane/Projects/opencode-status-bar",
  "vcs": "git",
  "time": {"created": 1766909809452, "updated": 1767455301774}
}
```

## Objectif

Implementer le chargement des fichiers `todo/` et `project/` et exposer ces donnees via l'API.

## Comportement attendu

### Chargement des todos

1. Parcourir `storage/todo/*.json`
2. Le nom du fichier = `ses_xxx.json` donne le `session_id`
3. Chaque fichier contient un tableau de todos
4. Inserer chaque todo avec :
   - `id` : ID unique (prefixe par session_id pour unicite globale)
   - `session_id` : Extrait du nom de fichier
   - `content` : Texte du todo
   - `status` : pending, in_progress, completed, cancelled
   - `priority` : high, medium, low
   - `position` : Index dans le tableau (ordre)

### Chargement des projects

1. Parcourir `storage/project/*.json`
2. Inserer chaque projet avec :
   - `id` : Hash du projet
   - `worktree` : Chemin absolu du projet
   - `vcs` : Type VCS (git)
   - `created_at` / `updated_at` : Timestamps

3. Enrichir les sessions :
   - Extraire `project_name` depuis le `worktree` (basename du path)
   - UPDATE sessions SET project_name = ... WHERE project_id = ...

### Acces via API

- `GET /api/session/<id>/todos` : Liste des todos d'une session
- `GET /api/projects` : Liste des projets avec stats
- `GET /api/project/<id>/stats` : Stats detaillees d'un projet
- `GET /api/project/<id>/sessions` : Sessions d'un projet

### Dashboard

- Afficher les todos dans le detail session (section collapsible)
- Badge avec nombre de todos (completed/total)
- Vue "Projects" dans la navigation (optionnel, phase 2)

## Specifications

### Fonction load_todos()

```python
def load_todos(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load todos from OpenCode storage.
    
    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage
        max_days: Only load todos for sessions from last N days
        
    Returns:
        Number of todos loaded
    """
    conn = db.connect()
    todo_dir = storage_path / "todo"
    
    if not todo_dir.exists():
        return 0
    
    count = 0
    for todo_file in todo_dir.glob("*.json"):
        session_id = todo_file.stem  # ses_xxx
        
        try:
            with open(todo_file) as f:
                todos = json.load(f)
            
            for idx, todo in enumerate(todos):
                unique_id = f"{session_id}_{todo.get('id', idx)}"
                conn.execute("""
                    INSERT OR REPLACE INTO todos 
                    (id, session_id, content, status, priority, position, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, [
                    unique_id,
                    session_id,
                    todo.get("content", ""),
                    todo.get("status", "pending"),
                    todo.get("priority", "medium"),
                    idx
                ])
                count += 1
        except Exception as e:
            debug(f"Failed to load todos from {todo_file}: {e}")
    
    return count
```

### Fonction load_projects()

```python
def load_projects(db: AnalyticsDB, storage_path: Path) -> int:
    """Load projects from OpenCode storage.
    
    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage
        
    Returns:
        Number of projects loaded
    """
    conn = db.connect()
    project_dir = storage_path / "project"
    
    if not project_dir.exists():
        return 0
    
    count = 0
    for project_file in project_dir.glob("*.json"):
        try:
            with open(project_file) as f:
                data = json.load(f)
            
            project_id = data.get("id")
            worktree = data.get("worktree", "")
            vcs = data.get("vcs", "")
            time_data = data.get("time", {})
            
            conn.execute("""
                INSERT OR REPLACE INTO projects 
                (id, worktree, vcs, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, [
                project_id,
                worktree,
                vcs,
                ms_to_datetime(time_data.get("created")),
                ms_to_datetime(time_data.get("updated"))
            ])
            count += 1
            
            # Enrich sessions with project_name
            project_name = Path(worktree).name if worktree else None
            if project_name:
                conn.execute("""
                    UPDATE sessions SET project_name = ? WHERE project_id = ?
                """, [project_name, project_id])
                
        except Exception as e:
            debug(f"Failed to load project from {project_file}: {e}")
    
    return count
```

### Integration dans load_opencode_data()

```python
def load_opencode_data(...):
    # ... existing code ...
    
    # Add after delegations
    todos = load_todos(db, storage_path, max_days)
    projects = load_projects(db, storage_path)
    
    return {
        # ... existing ...
        "todos": todos,
        "projects": projects,
    }
```

## Checklist de validation

- [ ] Fonction `load_todos()` implementee
- [ ] Fonction `load_projects()` implementee
- [ ] Integration dans `load_opencode_data()`
- [ ] Sessions enrichies avec `project_name`
- [ ] Endpoint `/api/session/<id>/todos` fonctionnel
- [ ] Endpoint `/api/projects` fonctionnel
- [ ] Tests unitaires `test_todos_loading.py`
- [ ] Tests unitaires `test_projects_loading.py`
- [ ] Tous les 88 fichiers todo charges correctement
- [ ] Tous les 5 fichiers project charges correctement

## Estimation

- **Effort** : Faible (1 jour)
- **Risque** : Tres faible (ajout simple, pas de breaking changes)
- **Dependances** : Aucune
