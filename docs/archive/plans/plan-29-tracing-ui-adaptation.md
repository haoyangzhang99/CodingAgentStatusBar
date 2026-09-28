# Plan 29 - Tracing UI Adaptation

## Contexte

Suite à l'implémentation du Plan 28 (Tracing Data Strategy), le dashboard dispose désormais d'un modèle de données riche et de requêtes performantes pour obtenir des KPIs détaillés par session.

Ce plan adapte l'interface utilisateur pour exploiter ces nouvelles données et offrir une expérience de visualisation complète.

## Objectif

Adapter la section Tracing du dashboard PyQt pour :
1. Consommer les données du nouveau TracingDataService
2. Afficher tous les KPIs disponibles de manière claire
3. Organiser l'information en panneaux cohérents
4. Maintenir la performance avec le nouveau volume de données

## Comportement attendu

### 1. Refonte du panneau de détails

Quand l'utilisateur sélectionne une session ou trace, le panneau de droite affiche :

**Header avec métriques clés** :
```
┌─────────────────────────────────────────────┐
│ 🌳 opencode-status-bar                         │
│ ─────────────────────────────────────────── │
│ ⏱ 2m 34s   🎫 15.2K tokens   🔧 42 tools    │
│ 📁 12 files   🤖 3 agents   ✅ Completed    │
└─────────────────────────────────────────────┘
```

**Onglets de détails** :
- 💬 **Prompts** : User prompt initial + output final
- 📊 **Tokens** : Répartition in/out/cache, par agent
- 🔧 **Tools** : Liste avec count, durée, status
- 📁 **Files** : Reads/writes avec indicateur de risque
- 🤖 **Agents** : Hiérarchie de délégation avec temps
- ⏱ **Timeline** : Événements chronologiques

### 2. Section Prompts (onglet par défaut)

```
┌─ 💬 User Prompt ────────────────────────────┐
│ [Collapsible text area with first message]  │
│                                             │
│ "Crée un système de tracing pour..."        │
└─────────────────────────────────────────────┘

┌─ 📤 Final Output ───────────────────────────┐
│ [Collapsible text area with last response]  │
│                                             │
│ "J'ai implémenté le système avec..."        │
└─────────────────────────────────────────────┘
```

### 3. Section Tokens

```
┌─ Résumé ────────────────────────────────────┐
│  Input: 8,234    Output: 6,998    Cache: 2,156  │
│  Cache Hit: 14%   Coût estimé: $0.12        │
└─────────────────────────────────────────────┘

┌─ Par Agent ─────────────────────────────────┐
│  [Horizontal bar chart]                     │
│  executeur  ████████████  45%  6.8K         │
│  tester     ██████       28%  4.2K          │
│  quality    ████         18%  2.7K          │
│  other      ██            9%  1.5K          │
└─────────────────────────────────────────────┘
```

### 4. Section Tools

```
┌─ Top Tools ─────────────────────────────────┐
│  Tool          Count   Avg Time   Status    │
│  ─────────────────────────────────────────  │
│  Read          18      45ms       ✅ 100%   │
│  Edit          12      120ms      ✅ 92%    │
│  Bash          8       2.3s       ⚠️ 75%    │
│  Write         4       80ms       ✅ 100%   │
└─────────────────────────────────────────────┘

┌─ Échecs récents ────────────────────────────┐
│  ⚠️ Bash: "Permission denied" (14:32)       │
│  ⚠️ Bash: "Command not found" (14:28)       │
└─────────────────────────────────────────────┘
```

### 5. Section Files

```
┌─ Résumé ────────────────────────────────────┐
│  📖 Reads: 8    ✏️ Writes: 4    ⚠️ Risky: 1  │
└─────────────────────────────────────────────┘

┌─ Fichiers modifiés ─────────────────────────┐
│  ✏️ src/tracing.py           [low]         │
│  ✏️ src/models.py            [low]         │
│  ✏️ tests/test_tracing.py    [low]         │
│  ⚠️ .env                      [high]        │
└─────────────────────────────────────────────┘

┌─ Par extension ─────────────────────────────┐
│  .py  ████████████  75%                     │
│  .md  ████         20%                      │
│  .env █             5%                      │
└─────────────────────────────────────────────┘
```

### 6. Section Agents

```
┌─ Hiérarchie ────────────────────────────────┐
│  🌳 ROOT (user)                             │
│   └─ 🔗 coordinateur (1m 20s, 5.2K tokens)  │
│       ├─ 🔗 executeur (45s, 3.1K tokens)    │
│       │   └─ 🔗 tester (30s, 2.8K tokens)   │
│       └─ 🔗 quality (20s, 1.2K tokens)      │
└─────────────────────────────────────────────┘

┌─ Répartition temps ─────────────────────────┐
│  [Stacked bar or pie chart]                 │
│  coordinateur: 35%                          │
│  executeur: 30%                             │
│  tester: 20%                                │
│  quality: 15%                               │
└─────────────────────────────────────────────┘
```

### 7. Section Timeline

```
┌─ Événements ────────────────────────────────┐
│  14:30:00  🚀 Session started               │
│  14:30:02  💬 User prompt received          │
│  14:30:05  🤖 Delegated to coordinateur     │
│  14:30:10  🔧 Tool: Read (src/main.py)      │
│  14:30:15  🤖 Delegated to executeur        │
│  14:30:45  🔧 Tool: Edit (src/main.py)      │
│  14:31:20  🤖 Delegated to tester           │
│  14:31:50  🔧 Tool: Bash (pytest)           │
│  14:32:15  ✅ All tasks completed           │
│  14:32:34  🏁 Session ended                 │
└─────────────────────────────────────────────┘
```

### 8. Intégration avec l'arbre

- Clic sur une session ROOT → affiche le résumé complet
- Clic sur une session CHILD → affiche les détails de ce sous-agent
- Clic sur une trace → affiche prompt in/out de cette trace spécifique
- Double-clic → ouvre le terminal (comportement existant préservé)

### 9. Lazy Loading

- Charger uniquement l'onglet visible
- Précharger les données au survol des onglets
- Indicateur de chargement pendant les requêtes
- Cache des données déjà chargées pour navigation rapide

### 10. Responsive Design

- Panneau de détails redimensionnable
- Onglets passent en mode compact si espace réduit
- Graphiques s'adaptent à la largeur disponible
- Textes longs avec ellipsis + tooltip

## Sous-tâches

- 29.1 - Refonte TraceDetailPanel avec onglets
- 29.2 - Implémentation section Prompts
- 29.3 - Implémentation section Tokens (avec mini-charts)
- 29.4 - Implémentation section Tools
- 29.5 - Implémentation section Files
- 29.6 - Implémentation section Agents
- 29.7 - Implémentation section Timeline
- 29.8 - Intégration TracingDataService
- 29.9 - Lazy loading et cache

## Priorité des sous-tâches

| Priorité | Sous-tâche | Dépendances | Effort |
|----------|------------|-------------|--------|
| 1 | 29.1 - Refonte panel | Plan 28 | Moyen |
| 2 | 29.8 - Intégration service | 29.1, Plan 28 | Faible |
| 3 | 29.2 - Prompts | 29.1 | Faible |
| 4 | 29.3 - Tokens | 29.1 | Moyen |
| 5 | 29.4 - Tools | 29.1 | Moyen |
| 6 | 29.5 - Files | 29.1 | Faible |
| 7 | 29.6 - Agents | 29.1 | Moyen |
| 8 | 29.7 - Timeline | 29.1 | Moyen |
| 9 | 29.9 - Lazy loading | 29.2-29.7 | Faible |

## Dépendances

- **Plan 28** (Tracing Data Strategy) doit être terminé avant ce plan
- TracingDataService doit être disponible et testé

## Checklist de validation

- [ ] Panneau de détails avec 6 onglets fonctionnels
- [ ] Header affiche les métriques clés pour toute sélection
- [ ] Section Prompts affiche user prompt et final output
- [ ] Section Tokens affiche répartition et chart par agent
- [ ] Section Tools affiche top tools avec stats
- [ ] Section Files affiche reads/writes avec risque
- [ ] Section Agents affiche hiérarchie avec temps
- [ ] Section Timeline affiche événements chronologiques
- [ ] Lazy loading : seul l'onglet actif charge ses données
- [ ] Performance : changement d'onglet < 100ms
- [ ] Responsive : panneau utilisable à 350px de large minimum
- [ ] Cohérence visuelle avec le design system existant
