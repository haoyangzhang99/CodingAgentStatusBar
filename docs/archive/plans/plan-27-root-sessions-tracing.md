# Plan 27 : Traçage des Sessions ROOT

**Statut** : ✅ Terminé  
**Version** : v0.8.1  
**Branche** : `feature/root-sessions-tracing` (mergée)

## Contexte

Le système de tracing actuel ne capture que les **délégations** (invocations `tool="task"`). Les conversations directes avec un agent (sessions ROOT) ne sont pas visibles dans le dashboard.

**Exemple** :
- Session "OpenMonitor Planning..." → ROOT, non tracée
- Session "Quality: Features vs Plans" → CHILD (délégation), tracée

## Objectif

Capturer et afficher **toutes les sessions**, pas seulement les délégations :
1. Sessions ROOT (conversations directes)
2. Sessions CHILD (délégations via task)
3. Liens parent/enfant pour la hiérarchie

## Structure des données OpenCode

```
session/
  └── {session_id}/session.json
      - id, title, parentID (null pour ROOT), directory, time

message/
  └── {message_id}/message.json  
      - id, sessionID, role (user/assistant), agent, content (via parts)

part/
  └── {message_id}/{part_id}.json
      - tool="task" pour délégations (déjà capturé)
      - tool="text" pour contenu des messages
```

## Implémentation

### Phase 1 : Extraire les sessions ROOT

**Fichier** : `src/opencode_status_bar/analytics/loader.py`

```python
def extract_root_sessions(storage_path: Path, max_days: int = 30) -> list[AgentTrace]:
    """Extract root sessions (direct conversations, not delegations)."""
    session_dir = storage_path / "session"
    message_dir = storage_path / "message"
    
    traces = []
    for session in find_sessions_without_parent(session_dir, max_days):
        # Get first user message as prompt
        first_message = get_first_user_message(message_dir, session.id)
        
        trace = AgentTrace(
            trace_id=f"root_{session.id}",
            session_id=session.id,
            parent_trace_id=None,  # ROOT
            parent_agent=None,
            subagent_type=session.agent or "user",  # From first message
            prompt_input=first_message.content,
            prompt_output=None,  # Conversation ongoing
            started_at=session.created_at,
            # ... tokens from session messages
        )
        traces.append(trace)
    
    return traces
```

### Phase 2 : Unifier ROOT et CHILD dans load_traces

```python
def load_traces(db, storage_path, max_days=30):
    # Existing: delegations from task tool
    delegation_traces = extract_traces(storage_path, max_days)
    
    # New: root sessions
    root_traces = extract_root_sessions(storage_path, max_days)
    
    # Merge and deduplicate
    all_traces = root_traces + delegation_traces
    
    # Link children to parents via session_id/parent_session_id
    resolve_hierarchy(all_traces)
    
    # Insert all
    for trace in all_traces:
        db.insert_trace(trace)
```

### Phase 3 : Améliorer l'UI

**Fichier** : `src/opencode_status_bar/dashboard/sections/tracing.py`

- Distinguer visuellement ROOT vs CHILD
- Icône différente : 🌳 pour ROOT, 🔗 pour délégation
- Afficher le prompt utilisateur pour les ROOT

## Schéma visuel attendu

```
🌳 OpenMonitor Planning (executeur) - 2h ago
   └─ 🔗 refactoring (@refactoring) - "Analyze testability..."
   └─ 🔗 tester (@tester) - "Write tests for..."
   └─ 🔗 quality (@quality) - "Review code..."

🌳 BluePlayer (executeur) - 3h ago
   └─ 🔗 quality (@quality) - "E2E Tests Analysis"
   └─ 🔗 quality (@quality) - "Features vs Plans"
```

## Impact sur la sync

- `load_traces` devra aussi charger les root sessions
- Besoin de récupérer le contenu du premier message (prompt utilisateur)
- Le contenu des messages est dans les `part/` avec `type="text"`

## Tests

- [x] Sessions ROOT extraites correctement (14 tests)
- [x] Prompt utilisateur récupéré depuis first message
- [x] Hiérarchie ROOT → CHILD affichée correctement
- [x] Tokens calculés pour ROOT sessions aussi

## Résultat

**Fichiers modifiés** :
- `loader.py` : +158 lignes (extract_root_sessions, get_first_user_message)
- `trace_queries.py` : +30 lignes (COALESCE pour prompts ROOT+CHILD)
- `tracing.py` : +58 lignes (icônes 🌳/🔗, UI améliorée)
- `test_loader.py` : +457 lignes (14 nouveaux tests)

## Estimation

- Phase 1 : 1h
- Phase 2 : 30min  
- Phase 3 : 30min
- Tests : 30min

## Priorité

**Moyenne** - Amélioration UX importante mais non bloquante
