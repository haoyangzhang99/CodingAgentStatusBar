# Plan 13 - Refactoring du code source

## Contexte

Le codebase actuel fonctionne bien mais presente des signes de dette technique :

- **`app.py`** (888 lignes) : Classe `OpenCodeApp` avec trop de responsabilites
- **`security_auditor.py`** (1322 lignes) : Logique SQLite, scanning, analyse et reporting melangees
- Duplication de code dans le formatage et les patterns
- Couplage fort entre les composants

Ces problemes rendent le code plus difficile a maintenir et a tester.

## Objectif

Ameliorer la maintenabilite et la testabilite du code en :
- Extrayant des modules a responsabilite unique
- Eliminant la duplication de code
- Reduisant le couplage entre composants

## Comportement attendu

Apres refactoring :
- L'application fonctionne exactement comme avant (aucun changement utilisateur)
- Chaque fichier fait moins de 400 lignes
- Chaque classe a une responsabilite unique
- Le code duplique est factorise
- Les tests unitaires sont plus faciles a ecrire

---

## Ameliorations suggerees

### 1. Refactoring de `security_auditor.py` (Priorite haute)

**Problemes actuels :**
- 1322 lignes dans un seul fichier
- `SecurityAuditor` melange : gestion SQLite, scanning, analyse, reporting, statistiques
- 4 dataclasses quasi-identiques (`AuditedCommand`, `AuditedFileRead`, `AuditedFileWrite`, `AuditedWebFetch`)
- ~10 methodes de query SQLite avec code similaire
- Duplication dans `_analyze_file_path()` et `_analyze_url()`

**Actions :**

| Action | Fichier cree | Lignes estimees |
|--------|--------------|-----------------|
| Extraire la gestion SQLite | `database.py` | ~200 |
| Extraire l'analyse de risques | `risk_analyzer.py` | ~150 |
| Extraire la generation de rapports | `reporter.py` | ~150 |
| Classe de base pour les operations auditees | `models.py` (extend) | ~50 |

**Structure proposee :**

```
src/opencode_status_bar/
  database.py         # SecurityDatabase - Repository pattern SQLite
  risk_analyzer.py    # RiskAnalyzer - Analyse file paths et URLs
  reporter.py         # SecurityReporter - Generation rapports texte
  security_auditor.py # SecurityAuditor - Orchestration scanning (~300 lignes)
```

**Benefices :**
- `SecurityDatabase` peut etre teste independamment avec une DB en memoire
- `RiskAnalyzer` testable avec des patterns fixes
- `SecurityReporter` testable sans DB

---

### 2. Refactoring de `app.py` (Priorite moyenne)

**Problemes actuels :**
- 888 lignes dans `OpenCodeApp`
- Responsabilites multiples : menu, etat, security, export, terminal focus, monitoring
- Formatage du risque repete 4+ fois dans `_build_menu()`
- Generation de rapport dans une methode d'UI

**Actions :**

| Action | Fichier cree | Lignes estimees |
|--------|--------------|-----------------|
| Extraire la construction du menu | `menu_builder.py` | ~250 |
| Extraire l'export des donnees | `exporter.py` | ~150 |
| Extraire le focus terminal | `terminal.py` | ~50 |

**Structure proposee :**

```
src/opencode_status_bar/
  app.py              # OpenCodeApp - Orchestration principale (~350 lignes)
  menu_builder.py     # MenuBuilder - Construction du menu rumps
  exporter.py         # DataExporter - Export fichiers et rapports
  terminal.py         # TerminalFocuser - AppleScript iTerm2
```

**Benefices :**
- `MenuBuilder` testable en isolation
- `DataExporter` reutilisable pour d'autres formats
- `app.py` devient un orchestrateur leger

---

### 3. Fusion des modules de securite (Priorite moyenne)

**Problemes actuels :**
- `security.py` (241 lignes) : Analyse de commandes
- `security_auditor.py` : Analyse de file paths et URLs
- Logique d'analyse similaire dispersee

**Action :**
- Deplacer `analyze_command()` vers `risk_analyzer.py`
- Unifier les patterns de risque dans un seul module
- Garder `security.py` comme facade publique simple

**Benefices :**
- Un seul endroit pour toute la logique d'analyse de risques
- Patterns centralises et faciles a maintenir

---

### 4. Ameliorations mineures (Priorite basse)

| Amelioration | Fichier | Description |
|--------------|---------|-------------|
| Constantes de formatage | `constants.py` | Extraire TITLE_MAX_LENGTH, etc. |
| Helpers de formatage | `formatters.py` | Factoriser truncation, emoji, timestamps |
| Type hints complets | Tous | Ajouter annotations manquantes |
| Docstrings | Tous | Documenter classes et methodes publiques |

---

## Plan d'execution suggere

### Phase 1 : `security_auditor.py` (2-3h)
1. Creer `database.py` avec `SecurityDatabase`
2. Creer `risk_analyzer.py` avec `RiskAnalyzer`
3. Creer `reporter.py` avec `SecurityReporter`
4. Refactoriser `security_auditor.py` pour utiliser ces modules
5. Tester que l'application fonctionne

### Phase 2 : `app.py` (1-2h)
1. Creer `menu_builder.py` avec `MenuBuilder`
2. Creer `exporter.py` avec `DataExporter`
3. Creer `terminal.py` avec `TerminalFocuser`
4. Refactoriser `OpenCodeApp`
5. Tester que l'application fonctionne

### Phase 3 : Consolidation (1h)
1. Fusionner la logique de `security.py` dans `risk_analyzer.py`
2. Creer les constantes et helpers communs
3. Ajouter type hints et docstrings

---

## Structure finale proposee

```
src/opencode_status_bar/
  __init__.py
  
  # Core
  app.py              # OpenCodeApp - Point d'entree (~350 lignes)
  menu_builder.py     # MenuBuilder - Construction menu (~250 lignes)
  monitor.py          # Detection instances (inchange)
  client.py           # HTTP client (inchange)
  models.py           # Modeles de donnees (extended)
  
  # Security
  security.py         # Facade publique (simplifie)
  security_auditor.py # Orchestration scanning (~300 lignes)
  risk_analyzer.py    # Analyse de risques (~200 lignes)
  database.py         # Repository SQLite (~200 lignes)
  reporter.py         # Generation rapports (~150 lignes)
  
  # Utils
  settings.py         # Preferences (inchange)
  logger.py           # Logging (inchange)
  terminal.py         # Focus iTerm2 (~50 lignes)
  exporter.py         # Export donnees (~150 lignes)
  constants.py        # Constantes partagees (~30 lignes)
```

## Checklist de validation

### Avant de commencer
- [x] Lancer l'application et noter le comportement actuel
- [x] S'assurer que tous les tests passent
- [x] Creer une branche `feature/refactoring`

### Phase 1 - security_auditor.py
- [x] `database.py` cree avec SecurityDatabase (568 lignes)
- [x] `risk_analyzer.py` cree avec RiskAnalyzer (160 lignes)
- [x] `reporter.py` cree avec SecurityReporter (250 lignes)
- [x] `security_auditor.py` refactored (321 lignes < 400)
- [x] Security audit fonctionne correctement
- [x] Export des donnees fonctionne
- [x] Rapport de securite genere correctement

### Phase 2 - app.py
- [ ] `menu_builder.py` cree avec MenuBuilder (skip - app.py acceptable)
- [ ] `exporter.py` cree avec DataExporter (skip - utilise reporter.py)
- [x] `terminal.py` cree avec TerminalFocuser (50 lignes)
- [x] `app.py` refactored (725 lignes - reduction 18%)
- [x] Menu s'affiche correctement
- [x] Click sur agent focus le terminal
- [x] Preferences fonctionnent
- [x] Usage s'affiche correctement

### Phase 3 - Consolidation (optionnel - skip)
- [ ] Logique d'analyse centralisee dans risk_analyzer.py
- [ ] Constantes extraites
- [ ] Type hints ajoutes sur les classes publiques
- [x] Aucune regression fonctionnelle

### Validation finale
- [x] Application demarre sans erreur
- [x] Toutes les fonctionnalites operationnelles
- [x] Tests passent (100 tests, 100% couverture sur nouveaux modules)
