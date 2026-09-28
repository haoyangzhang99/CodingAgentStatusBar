# Plan 28 - Tracing Data Strategy

## Contexte

La section Tracing du dashboard manque d'une stratégie data cohérente. Actuellement :
- Les données sont collectées de manière opportuniste (ce qui est disponible dans l'API OpenCode)
- Le modèle de données est orienté stockage plutôt qu'analytics
- Les requêtes sont basiques et ne fournissent pas de KPIs riches
- Le format de données n'est pas optimisé pour la consommation par le dashboard

Avant d'améliorer l'UI (plans 29, 30, 31, 32), il faut avoir un socle data solide qui permette d'afficher des métriques pertinentes et performantes.

## Objectif

Définir et implémenter une stratégie data complète pour le tracing :
1. Identifier toutes les données collectables
2. Concevoir un modèle de données optimisé pour les analytics
3. Implémenter des requêtes performantes pour chaque KPI
4. Fournir un format de sortie standardisé pour le dashboard

## Comportement attendu

### 1. Inventaire des données collectables

**Depuis l'API OpenCode (SSE events)** :
- Sessions : id, title, directory, parent_id, created_at
- Messages : role, content, tokens, timestamp
- Tool calls : name, arguments, result, duration, status
- Skill loads : skill_name, timestamp

**Depuis les fichiers session** :
- Conversations complètes (messages.json ou équivalent)
- Métadonnées de session
- État des todos

**Depuis notre collecte existante** :
- Traces d'agents (table agent_traces)
- Délégations (table delegations)
- Commandes exécutées (module security)

**Données dérivées/calculées** :
- Durées (session, trace, tool)
- Coûts estimés (tokens × tarif)
- Taux de succès/échec
- Profondeur de délégation

### 2. Modèle de données cible

**Tables principales** :

```
sessions
├── id (PK)
├── title
├── directory
├── parent_id (FK → sessions)
├── created_at
├── ended_at
├── duration_ms (calculé)
├── is_root (boolean)
└── project_name (extrait de directory)

traces
├── trace_id (PK)
├── session_id (FK → sessions)
├── parent_trace_id (FK → traces)
├── agent_type
├── parent_agent
├── started_at
├── ended_at
├── duration_ms
├── status (running, completed, error)
└── child_session_id (FK → sessions)

messages
├── id (PK)
├── session_id (FK → sessions)
├── trace_id (FK → traces, nullable)
├── role (user, assistant, system)
├── content (text)
├── timestamp
├── tokens_in
├── tokens_out
└── tokens_cache

tool_calls
├── id (PK)
├── session_id (FK → sessions)
├── trace_id (FK → traces, nullable)
├── message_id (FK → messages, nullable)
├── tool_name
├── arguments (JSON)
├── result_summary (text tronqué)
├── started_at
├── ended_at
├── duration_ms
├── status (pending, completed, error)
└── error_message

file_operations
├── id (PK)
├── session_id (FK → sessions)
├── trace_id (FK → traces, nullable)
├── operation (read, write, edit)
├── file_path
├── timestamp
├── risk_level
└── risk_reason

skill_loads
├── id (PK)
├── session_id (FK → sessions)
├── skill_name
├── timestamp
└── duration_ms
```

**Tables d'agrégation (pré-calculées)** :

```
session_stats
├── session_id (PK, FK → sessions)
├── total_messages
├── total_tokens_in
├── total_tokens_out
├── total_tokens_cache
├── total_tool_calls
├── tool_success_rate
├── total_file_reads
├── total_file_writes
├── unique_agents
├── max_delegation_depth
├── estimated_cost_usd
└── updated_at

daily_stats
├── date (PK)
├── total_sessions
├── total_traces
├── total_tokens
├── total_tool_calls
├── avg_session_duration_ms
└── error_rate
```

### 3. KPIs par session

Pour chaque session, le dashboard doit pouvoir afficher :

**Métriques de tokens** :
- Tokens in total
- Tokens out total
- Tokens cache (économisés)
- Cache hit ratio (%)
- Répartition par agent (pie chart data)

**Métriques de prompts** :
- Nombre de messages user
- Nombre de messages assistant
- Longueur moyenne des prompts
- Premier prompt (user question)
- Dernier output (résultat final)

**Métriques de tools** :
- Tools uniques utilisés
- Total invocations
- Top 5 tools par usage
- Taux d'échec par tool
- Durée moyenne par tool

**Métriques de fichiers** :
- Fichiers lus (count + liste)
- Fichiers écrits (count + liste)
- Fichiers à risque (high/critical)
- Extensions touchées (répartition)

**Métriques de délégation** :
- Agents impliqués (liste)
- Profondeur max de délégation
- Traces par agent (répartition)
- Temps par agent (répartition)

**Métriques temporelles** :
- Durée totale session
- Temps actif vs idle
- Timeline des événements
- Latence première réponse

**Métriques de coût** :
- Coût estimé (configurable $/1K tokens)
- Coût par agent
- Coût par tool

### 4. API de requêtes

Chaque requête retourne un dict standardisé prêt pour Qt signals :

```python
class TracingDataService:
    """Service centralisé pour les données de tracing."""
    
    def get_session_summary(self, session_id: str) -> dict:
        """Résumé complet d'une session avec tous les KPIs."""
        
    def get_session_tokens(self, session_id: str) -> dict:
        """Détail des tokens pour une session."""
        
    def get_session_tools(self, session_id: str) -> dict:
        """Détail des tools pour une session."""
        
    def get_session_files(self, session_id: str) -> dict:
        """Détail des fichiers pour une session."""
        
    def get_session_timeline(self, session_id: str) -> list[dict]:
        """Timeline des événements pour une session."""
        
    def get_session_agents(self, session_id: str) -> list[dict]:
        """Agents impliqués dans une session."""
        
    def get_global_stats(self, start: datetime, end: datetime) -> dict:
        """Statistiques globales sur une période."""
        
    def get_comparison(self, session_ids: list[str]) -> dict:
        """Comparaison entre plusieurs sessions."""
```

### 5. Format de sortie standardisé

Chaque réponse suit ce format :

```python
{
    "meta": {
        "session_id": "...",
        "generated_at": "2026-01-03T12:00:00",
        "period": {"start": "...", "end": "..."}
    },
    "summary": {
        # KPIs principaux (affichage header)
        "duration_ms": 45000,
        "total_tokens": 15234,
        "total_tools": 42,
        "status": "completed"
    },
    "details": {
        # Données détaillées par catégorie
        "tokens": {...},
        "tools": {...},
        "files": {...},
        "agents": {...}
    },
    "charts": {
        # Données pré-formatées pour graphiques
        "tokens_by_agent": [...],
        "tools_timeline": [...],
        "files_by_type": [...]
    }
}
```

### 6. Performance

- Utiliser des agrégations pré-calculées pour les KPIs fréquents
- Mettre à jour `session_stats` à chaque sync
- Indexer les colonnes utilisées dans les WHERE/JOIN
- Limiter les requêtes complexes aux vues détaillées (lazy loading)
- Cache en mémoire pour les sessions actives

## Sous-tâches

- 28.1 - Inventaire et audit des données existantes
- 28.2 - Migration schema DuckDB (nouvelles tables)
- 28.3 - Enrichissement de la collecte (loader.py)
- 28.4 - Implémentation TracingDataService
- 28.5 - Tables d'agrégation et triggers
- 28.6 - Tests de performance avec 1000+ sessions

## Priorité des sous-tâches

| Priorité | Sous-tâche | Dépendances | Effort |
|----------|------------|-------------|--------|
| 1 | 28.1 - Audit données | Aucune | Faible |
| 2 | 28.2 - Migration schema | 28.1 | Moyen |
| 3 | 28.3 - Enrichir collecte | 28.2 | Moyen |
| 4 | 28.4 - TracingDataService | 28.2 | Moyen |
| 5 | 28.5 - Agrégations | 28.3, 28.4 | Moyen |
| 6 | 28.6 - Tests perf | 28.5 | Faible |

## Checklist de validation

- [x] Inventaire complet des données collectables documenté
- [x] Schema DuckDB migré avec nouvelles tables
- [x] Collecte enrichie pour tool_calls, file_operations, messages
- [x] TracingDataService implémenté avec toutes les méthodes
- [x] get_session_summary retourne tous les KPIs listés
- [x] Tables d'agrégation session_stats et daily_stats fonctionnelles
- [x] Temps de réponse < 100ms pour get_session_summary
- [x] Tests unitaires pour chaque méthode du service
- [x] Documentation du format de sortie

## Implémentation (2026-01-03)

### Fichiers créés/modifiés

| Fichier | Action | Description |
|---------|--------|-------------|
| `src/opencode_status_bar/analytics/tracing_service.py` | Créé | TracingDataService complet (916 lignes) |
| `src/opencode_status_bar/analytics/db.py` | Modifié | +3 tables, +colonnes, +index |
| `src/opencode_status_bar/analytics/loader.py` | Modifié | +load_file_operations() |
| `src/opencode_status_bar/analytics/__init__.py` | Modifié | Export TracingDataService |
| `tests/test_tracing_service.py` | Créé | 22 tests (100% pass) |

### Nouvelles tables DuckDB

- `file_operations` : tracking read/write/edit avec risk_level
- `session_stats` : agrégation pré-calculée par session
- `daily_stats` : agrégation quotidienne

### Nouvelles colonnes

- `parts` : arguments, result_summary, error_message
- `sessions` : ended_at, duration_ms, is_root, project_name

### Tests

- 22 tests créés, 22 passent
- Tests de performance validant < 100ms
