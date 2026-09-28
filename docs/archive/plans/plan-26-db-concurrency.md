# Plan 26 : Correction Concurrence DB Analytics

**Statut** : ✅ Terminé  
**Version** : v0.8.2  
**Branche** : `feature/db-concurrency` (mergée)

## Contexte

Le menubar et le dashboard utilisent tous deux la même base DuckDB (`analytics.duckdb`). DuckDB ne supporte pas les écritures concurrentes - un seul processus peut écrire à la fois.

**Problème actuel** :
- Le menubar détient le verrou d'écriture
- Le dashboard essaie de sync (écriture) au démarrage → échec silencieux
- Les nouvelles données ne sont jamais chargées dans le dashboard

## Objectif

Séparer les responsabilités :
- **Menubar** : Seul processus qui écrit dans la DB (sync périodique)
- **Dashboard** : Lecture seule (`read_only=True`)

## Comportement Attendu

1. Le menubar fait le sync des données OpenCode périodiquement (toutes les 5 min ou configurable)
2. Le dashboard ouvre la DB en mode `read_only` pour les requêtes
3. Le dashboard ne fait plus de sync lui-même
4. Option : Bouton "Refresh Data" dans le dashboard qui demande au menubar de sync via IPC

## Implémentation

### Phase 1 : Dashboard en lecture seule

**Fichier** : `src/opencode_status_bar/analytics/db.py`
- Ajouter paramètre `read_only: bool = False` au constructeur `AnalyticsDB`
- Passer ce paramètre à `duckdb.connect()`

**Fichier** : `src/opencode_status_bar/dashboard/window.py`
- Supprimer `_sync_opencode_data()` et le signal `sync_completed`
- Dans `_fetch_*_data()`, utiliser `AnalyticsDB(read_only=True)`

### Phase 2 : Sync périodique dans le menubar

**Fichier** : `src/opencode_status_bar/app/core.py` ou `handlers.py`
- Ajouter timer pour sync périodique (configurable, défaut 5 min)
- Le sync existant dans `needs_refresh()` reste mais avec intervalle plus court

### Phase 3 (Optionnel) : IPC pour refresh à la demande

- Mécanisme simple : fichier signal ou socket Unix
- Dashboard écrit un fichier `/tmp/opencode-status-bar-refresh`
- Menubar surveille ce fichier et lance un sync quand détecté
- Alternative : Bouton dans le dashboard qui tue/relance le sync

## Tests

- [x] Dashboard peut lire la DB pendant que menubar écrit
- [x] Pas d'erreur "database locked" 
- [x] Les données se mettent à jour après sync du menubar
- [x] SyncChecker polling adaptatif (2s actif → 5s repos)
- [x] 21 tests passent (test_db_concurrency.py + test_dashboard_sync.py)

## Résultat

**Architecture finale** :
```
MENUBAR (seul writer) → sync_meta.last_sync → DASHBOARD (poll 2s, read_only)
```

**Fichiers modifiés** :
- `db.py` : +table sync_meta, +2 méthodes
- `window.py` : -SyncConfig, +SyncChecker
- `handlers.py` : +AnalyticsSyncManager
- `core.py` : +intégration sync au démarrage

## Estimation

- Phase 1 : 30 min
- Phase 2 : 15 min
- Phase 3 : 45 min (optionnel)

## Priorité

**Haute** - Bloque l'utilisation normale du dashboard
