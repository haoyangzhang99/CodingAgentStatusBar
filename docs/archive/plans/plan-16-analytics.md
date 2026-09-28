# Plan 16 - Analytics et statistiques d'utilisation

## Contexte

OpenCode stocke des donnees riches sur chaque session dans `~/.local/share/opencode/storage/` :
- **Sessions** : Metadonnees (projet, titre, timestamps)
- **Messages** : Role, agent utilise, modele, tokens, cout
- **Parts** : Contenu des messages, appels d'outils, resultats

Volume estime : ~83 000 fichiers JSON, 627 Mo de donnees.

Ces donnees permettent d'analyser l'utilisation des agents, skills et workflows. Actuellement, il n'existe aucun moyen de visualiser ces metriques dans l'application.

## Objectif

Ajouter un sous-menu "Analytics" dans opencode-status-bar qui permet de visualiser les statistiques d'utilisation avec differentes periodes d'analyse.

## Comportement attendu

### Menu Analytics

Dans le menu principal, un nouveau sous-menu "Analytics" apparait :

```
📊 Analytics ▸
    📅 Dernier jour
    📅 7 derniers jours
    📅 30 derniers jours
    ─────────────
    🔄 Rafraichir les donnees
```

### Rapport affiche

Quand l'utilisateur clique sur une periode, une fenetre ou un panel affiche :

```
=== OpenCode Analytics ===
Periode: 2025-12-29 (dernier jour)

┌─ RESUME ─────────────────────────────┐
│ Sessions: 12                         │
│ Messages: 234                        │
│ Tokens: 450K (in: 380K, out: 70K)    │
│ Cout estime: $8.50                   │
└──────────────────────────────────────┘

┌─ AGENTS ─────────────────────────────┐
│ Agent       │ Msgs  │ Tokens │ Cout  │
│─────────────┼───────┼────────┼───────│
│ build       │ 156   │ 280K   │ $5.20 │
│ executeur   │ 45    │ 120K   │ $2.30 │
│ explore     │ 23    │ 35K    │ $0.70 │
│ roadmap     │ 10    │ 15K    │ $0.30 │
└──────────────────────────────────────┘

┌─ TOOLS (top 10) ─────────────────────┐
│ Tool     │ Invocations │ Echecs     │
│──────────┼─────────────┼────────────│
│ edit     │ 89          │ 2          │
│ read     │ 234         │ 0          │
│ bash     │ 67          │ 5          │
│ glob     │ 45          │ 0          │
└──────────────────────────────────────┘

┌─ SKILLS ─────────────────────────────┐
│ agentic-flow (12), clean-code (5)   │
│ notify (3), qml (2)                  │
└──────────────────────────────────────┘

┌─ ALERTES ────────────────────────────┐
│ ⚠️ 3 sessions avec >10 task calls    │
│ ℹ️ Skill 'qt-cpp' jamais utilise     │
└──────────────────────────────────────┘
```

### Analyses disponibles

| Metrique | Description |
|----------|-------------|
| Sessions | Nombre de sessions sur la periode |
| Messages | Total messages (user + assistant) |
| Tokens | Input, output, cache read/write |
| Cout | Estime base sur les tokens |
| Agents | Usage par agent (build, executeur, etc.) |
| Tools | Top outils utilises + taux d'echec |
| Skills | Skills charges via le tool "skill" |
| Chaines | Detection agents imbriques (task → subagent) |
| Alertes | Anomalies detectees |

### Detection d'anomalies

| Alerte | Seuil |
|--------|-------|
| Sur-utilisation task | > 10 invocations/session |
| Profondeur excessive | Chaines agents > 3 niveaux |
| Skills inutilises | Definis mais 0 invocations |
| Echecs repetitifs | Taux echec tool > 20% |

## Specifications techniques

### Base de donnees : DuckDB

Utiliser DuckDB pour les performances (vs scan JSON) :
- Import initial : scan JSON → tables DuckDB
- Requetes suivantes : ~50ms vs ~30s

```sql
-- Schema suggere
CREATE TABLE sessions (id, project_id, created_at, title);
CREATE TABLE messages (id, session_id, agent, tokens_in, tokens_out, cost, created_at);
CREATE TABLE parts (id, message_id, tool, status, created_at);
```

### Integration dans l'app

```python
# Nouveau module
src/opencode_status_bar/
└── analytics/
    ├── __init__.py
    ├── db.py          # Gestion DuckDB
    ├── loader.py      # Import JSON → DuckDB
    ├── queries.py     # Requetes analytiques
    └── report.py      # Generation du rapport
```

### Menu rumps

```python
@rumps.clicked("Analytics", "Dernier jour")
def analytics_1d(self, _):
    report = self.analytics.generate(days=1)
    self.show_report(report)
```

## Checklist de validation

- [x] Sous-menu "Analytics" present dans le menu principal
- [x] Option "Dernier jour" affiche les stats correctes
- [x] Option "7 derniers jours" affiche les stats correctes
- [x] Option "30 derniers jours" affiche les stats correctes
- [x] Les agents custom (executeur, roadmap, etc.) sont identifies
- [x] Les skills sont detectes via le tool "skill"
- [x] Les alertes s'affichent si anomalies detectees
- [x] "Rafraichir les donnees" reimporte les JSON
- [x] Performance acceptable (< 2s pour generer un rapport)

## Specifications implementees

- **Base DuckDB** : `~/.config/opencode-status-bar/analytics.duckdb`
- **Chargement optimise** : ~9s cold start (skip parts pour performance)
- **Refresh automatique** : Au demarrage si donnees > 24h
- **Rapport HTML** : Genere avec Plotly pour les graphiques
- **Metriques** :
  - Sessions, messages, tokens (input/output/cache)
  - Delegation patterns et chaines d'agents
  - Skills par agent
  - Modeles utilises
  - Activite par heure (heatmap)
