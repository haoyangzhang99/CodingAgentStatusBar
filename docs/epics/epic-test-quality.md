# Epic: Test Quality Improvement

**Epic ID**: TQI-001  
**Status**: In Progress  
**Priority**: P1 - High  
**Owner**: QA/Dev Team  
**Created**: 2026-01-07  
**Target Completion**: Sprint 4

## POC Results (Story 1 - COMPLETED)

**Date**: 2026-01-07  
**Module testé**: `utils/` (250 lignes)

### Résultats

| Métrique | Valeur |
|----------|--------|
| Mutants générés | 62 |
| Mutants tués | 27 (44%) |
| Mutants survivants | 35 (56%) |
| Vitesse | 18.5 mutations/sec |

### Mutants survivants identifiés

Principalement dans `logger.py` - la fonction `setup_logger` n'est pas testée :
- Valeur par défaut du paramètre `name`
- Configuration du handler
- Format du logger

### Configuration validée

```bash
# macOS nécessite --max-children=1 (problème fork/PyQt6)
make mutation
```

### Prochaines étapes

1. Écrire tests pour `setup_logger` → tuer 35 mutants
2. Étendre mutation testing à d'autres modules

---

## Overview

Le projet opencode-status-bar a accumulé une dette technique significative dans sa suite de tests. Avec 992 fonctions de test pour 35,623 lignes de code test contre 31,398 lignes de code source (ratio 1.13), les tests sont plus volumineux que le code qu'ils testent. Paradoxalement, la couverture du module `core/` n'est que de 25%.

Cet epic vise à améliorer la qualité et l'efficacité des tests plutôt que leur quantité, en introduisant le mutation testing comme métrique de qualité réelle.

## Business Value

| Métrique | Actuel | Cible |
|----------|--------|-------|
| Ratio test/code | 1.13 | < 0.8 |
| Assertions/test moyen | 3.1 | > 4.0 |
| Couverture core/ | 25% | > 70% |
| Mutation score | N/A | > 60% |
| Temps CI tests | ~8min | < 5min |

### Bénéfices attendus

1. **Confiance accrue** : Mutation testing prouve que les tests détectent vraiment les bugs
2. **Maintenance réduite** : Moins de tests = moins de maintenance
3. **CI plus rapide** : Temps de feedback réduit pour les développeurs
4. **Couverture réelle** : Focus sur le code critique (core/) plutôt que verbosité

---

## User Stories

### Story 1: POC Mutation Testing avec mutmut

**ID**: TQI-001-S1  
**Priority**: P0 - Critical (Prerequisite)  
**Estimate**: 3 points  
**Sprint**: 1

#### Description

En tant que développeur, je veux valider l'intégration de mutmut sur un module ciblé afin de mesurer l'efficacité réelle de nos tests et établir une baseline.

#### Scope

- Module cible : `src/opencode_status_bar/analytics/` (module critique)
- Configuration initiale mutmut
- Rapport de baseline

#### Acceptance Criteria

```gherkin
GIVEN le projet opencode-status-bar avec pytest configuré
WHEN je lance mutmut sur le module analytics/
THEN mutmut génère un rapport avec le mutation score

GIVEN mutmut configuré dans pyproject.toml
WHEN je lance `make mutation-test`
THEN les mutations sont exécutées sur le scope défini
AND le temps d'exécution est < 15 minutes pour le POC

GIVEN un rapport mutmut généré
WHEN j'analyse les mutants survivants
THEN je peux identifier les tests faibles à améliorer
AND le rapport est exportable en HTML/JSON
```

#### Tasks

- [ ] Installer mutmut (`uv add --dev mutmut`)
- [ ] Configurer `[tool.mutmut]` dans pyproject.toml
- [ ] Créer target Makefile `mutation-test`
- [ ] Exécuter POC sur `analytics/indexer/` (scope réduit)
- [ ] Documenter baseline mutation score
- [ ] Identifier top 5 mutants survivants à corriger

#### Definition of Done

- [ ] mutmut installé et configuré
- [ ] `make mutation-test` fonctionne
- [ ] Baseline mutation score documenté
- [ ] Rapport des mutants survivants analysé

---

### Story 2: Audit et Cleanup des Tests Redondants

**ID**: TQI-001-S2  
**Priority**: P1 - High  
**Estimate**: 5 points  
**Sprint**: 2  
**Depends On**: TQI-001-S1

#### Description

En tant que mainteneur, je veux identifier et supprimer les tests redondants afin de réduire le ratio test/code de 1.13 à < 0.8 et accélérer la CI.

#### Scope

Fichiers prioritaires (faible ratio assertions/test) :
1. `test_hybrid_indexer_resume.py` (1.4)
2. `test_unified_indexer.py` (1.4)
3. `test_dashboard_sync.py` (1.5)
4. `test_mitre_tags.py` (1.5)
5. `test_tooltips.py` (1.5)

#### Acceptance Criteria

```gherkin
GIVEN les fichiers de test avec ratio assertions/test < 2.0
WHEN j'analyse chaque fichier
THEN j'identifie les catégories :
  - Tests dupliqués (même comportement testé plusieurs fois)
  - Tests triviaux (assertions évidentes sans valeur)
  - Tests over-mocked (mocks excessifs masquant le comportement réel)

GIVEN une liste de tests candidats à suppression
WHEN je vérifie avec mutation testing
THEN les tests supprimés n'augmentent PAS les mutants survivants
AND le ratio test/code diminue

GIVEN les tests nettoyés
WHEN je lance la suite complète
THEN tous les tests passent
AND la couverture ne diminue pas de plus de 2%
```

#### Tasks

- [ ] Script d'analyse : identifier tests avec 1 seule assertion triviale
- [ ] Script d'analyse : détecter tests quasi-dupliqués
- [ ] Audit `test_hybrid_indexer_resume.py`
- [ ] Audit `test_unified_indexer.py`
- [ ] Audit `test_dashboard_sync.py`
- [ ] Audit `test_mitre_tags.py`
- [ ] Audit `test_tooltips.py`
- [ ] Consolider tests redondants
- [ ] Vérifier mutation score stable après cleanup
- [ ] Mesurer réduction lignes de code test

#### Definition of Done

- [ ] Chaque fichier audité avec rapport
- [ ] Tests redondants consolidés ou supprimés
- [ ] Mutation score stable ou amélioré
- [ ] Ratio test/code réduit (mesurable)

---

### Story 3: Amélioration des Assertions

**ID**: TQI-001-S3  
**Priority**: P1 - High  
**Estimate**: 5 points  
**Sprint**: 2  
**Depends On**: TQI-001-S1

#### Description

En tant que développeur, je veux renforcer les assertions des tests faibles afin d'augmenter le ratio assertions/test et tuer plus de mutants.

#### Scope

Fichiers identifiés + tests avec mutants survivants du POC.

#### Acceptance Criteria

```gherkin
GIVEN un test avec 1-2 assertions seulement
WHEN j'analyse le comportement testé
THEN j'ajoute des assertions pour :
  - Vérifier les effets de bord (état modifié)
  - Vérifier les valeurs de retour complètes
  - Vérifier les appels de dépendances

GIVEN un mutant survivant identifié
WHEN j'ajoute une assertion ciblée
THEN le mutant est tué
AND le test reste lisible et maintenable

GIVEN les fichiers améliorés
WHEN je calcule le nouveau ratio
THEN assertions/test moyen > 4.0 pour ces fichiers
```

#### Patterns d'amélioration

```python
# AVANT (faible)
def test_process_data(self):
    result = processor.process(data)
    assert result is not None  # 1 assertion triviale

# APRÈS (robuste)
def test_process_data(self):
    result = processor.process(data)
    assert result is not None
    assert result.status == "processed"
    assert result.items_count == len(data)
    assert processor.last_run is not None  # effet de bord
    mock_logger.info.assert_called_once()  # interaction
```

#### Definition of Done

- [ ] Ratio assertions/test > 4.0 sur fichiers ciblés
- [ ] Mutants survivants réduits de 30%+
- [ ] Patterns documentés dans CONTRIBUTING.md

---

### Story 4: Augmentation Couverture Module Core

**ID**: TQI-001-S4  
**Priority**: P2 - Medium  
**Estimate**: 8 points  
**Sprint**: 3  
**Depends On**: TQI-001-S2, TQI-001-S3

#### Description

En tant que mainteneur, je veux augmenter la couverture du module core/ de 25% à 70% afin de sécuriser le code critique de l'application.

#### Scope

```
src/opencode_status_bar/core/
├── client.py      # ~0% coverage
├── monitor/       # ~0% coverage
├── models.py      # 100% coverage ✓
└── usage.py       # ~0% coverage
```

#### Acceptance Criteria

```gherkin
GIVEN le rapport de couverture actuel pour core/
WHEN j'identifie les fichiers < 50% couverture
THEN je priorise par criticité business

GIVEN un fichier core/ non couvert
WHEN j'écris de nouveaux tests
THEN chaque test a minimum 4 assertions
AND mutation score > 60% pour le nouveau code

GIVEN les nouveaux tests écrits
WHEN je lance coverage + mutation
THEN couverture core/ > 70%
AND mutation score core/ > 60%
```

#### Definition of Done

- [ ] Couverture core/ ≥ 70%
- [ ] Mutation score core/ ≥ 60%
- [ ] Pas d'augmentation du ratio test/code global

---

### Story 5: Intégration CI Mutation Testing

**ID**: TQI-001-S5  
**Priority**: P2 - Medium  
**Estimate**: 3 points  
**Sprint**: 4  
**Depends On**: TQI-001-S4

#### Description

En tant que mainteneur, je veux intégrer le mutation testing dans la CI afin de prévenir la régression de qualité des tests.

#### Acceptance Criteria

```gherkin
GIVEN une PR avec modifications de tests
WHEN la CI s'exécute
THEN mutation testing s'exécute sur les modules modifiés

GIVEN un mutation score < seuil (60%)
WHEN la CI évalue le résultat
THEN le check échoue

GIVEN mutation testing en CI
WHEN le temps d'exécution dépasse 10 minutes
THEN seuls les modules modifiés sont testés (incremental)
```

#### Definition of Done

- [ ] Workflow CI fonctionnel
- [ ] Temps CI < 10 minutes (incrémental)
- [ ] Seuils configurés et documentés

---

## Technical Notes

### Configuration mutmut recommandée

```toml
# pyproject.toml
[tool.mutmut]
paths_to_mutate = "src/opencode_status_bar/"
tests_dir = "tests/"
runner = "python -m pytest -x --tb=no -q"
```

### Makefile targets

```makefile
.PHONY: mutation-test mutation-report

mutation-test:
	mutmut run --paths-to-mutate=src/opencode_status_bar/analytics/

mutation-report:
	mutmut html
	open .mutmut-results/html/index.html
```

---

## Sprint Allocation

| Sprint | Stories | Points | Focus |
|--------|---------|--------|-------|
| 1 | S1 | 3 | POC & Baseline |
| 2 | S2, S3 | 10 | Cleanup & Amélioration |
| 3 | S4 | 8 | Couverture core/ |
| 4 | S5 | 3 | Intégration CI |
| **Total** | **5** | **24** | |

---

## Files Analysis

### Tests à faible ratio assertions/test

| Fichier | Ratio | Action |
|---------|-------|--------|
| test_hybrid_indexer_resume.py | 1.4 | Audit + Improve |
| test_unified_indexer.py | 1.4 | Audit + Improve |
| test_dashboard_sync.py | 1.5 | Audit + Improve |
| test_mitre_tags.py | 1.5 | Audit + Improve |
| test_tooltips.py | 1.5 | Audit + Improve |

### Module core/ - Coverage Gaps

| Fichier | Couverture | Priorité |
|---------|------------|----------|
| models.py | 100% | ✓ Done |
| client.py | 0% | High |
| monitor/* | 0% | High |
| usage.py | 0% | Medium |
