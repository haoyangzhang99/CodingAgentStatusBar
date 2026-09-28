# Test Quality Improvement Orchestration Plan

> **Projet** : opencode-status-bar  
> **Date** : 2025-01-07  
> **Objectif** : Ratio test/code < 0.8 | Mutation Score > 60% | Assertions/test > 4

---

## Table des Matieres

1. [Metriques Actuelles](#1-metriques-actuelles)
2. [Methodologie de Refactoring](#2-methodologie-de-refactoring)
3. [Checklist par Fichier](#3-checklist-par-fichier)
4. [Workflow d'Execution](#4-workflow-dexecution)
5. [Patterns de Test de Qualite](#5-patterns-de-test-de-qualite)
6. [Commandes de Validation](#6-commandes-de-validation)
7. [Fichiers Prioritaires](#7-fichiers-prioritaires)

---

## 1. Metriques Actuelles

| Metrique | Actuel | Cible | Ecart |
|----------|--------|-------|-------|
| Lignes de test | 35,623 | < 25,000 | -10,623 |
| Lignes de code | 31,398 | - | - |
| Ratio test/code | 1.13 | < 0.8 | -0.33 |
| Fonctions de test | 992 | < 700 | -292 |
| Mutation score | ~40% | > 60% | +20% |

### Fichiers Prioritaires (Faible Ratio Assertions/Test)

| Fichier | Ratio | Lignes | Actions |
|---------|-------|--------|---------|
| test_hybrid_indexer_resume.py | 1.4 | 223 | Consolider, assertions multiples |
| test_unified_indexer.py | 1.4 | 1251 | Majeur - 60+ tests a optimiser |
| test_dashboard_sync.py | 1.5 | 207 | Parametriser, consolider |
| test_mitre_tags.py | 1.5 | 269 | Deja parametrise, ajouter assertions |
| test_tooltips.py | 1.5 | 280 | Deja parametrise, ajouter assertions |
| test_correlator.py | 1.6 | 462 | Consolider les classes |

---

## 2. Methodologie de Refactoring

### 2.1 Identification des Tests Redondants

```python
# Pattern a detecter : Tests avec setup identique
class TestA:
    def test_feature_case1(self):
        obj = create_object()  # Setup identique
        result = obj.method()
        assert result == "case1"
    
    def test_feature_case2(self):
        obj = create_object()  # Setup identique
        result = obj.method()
        assert result == "case2"

# REFACTORER EN :
class TestA:
    @pytest.mark.parametrize("input,expected", [
        ("case1", "result1"),
        ("case2", "result2"),
    ])
    def test_feature(self, input, expected):
        obj = create_object()
        result = obj.method(input)
        assert result == expected
```

### 2.2 Criteres de Redondance

| Critere | Description | Action |
|---------|-------------|--------|
| **Setup identique** | > 3 tests avec meme fixture setup | Parametriser |
| **Une seule assertion** | Tests avec 1 assert | Combiner ou enrichir |
| **Meme methode testee** | Multiples tests sur meme fonction | Consolider |
| **Edge cases isoles** | Tests de cas limites separes | Regrouper |
| **Mock identique** | Memes patches/mocks repetes | Extraire en fixture |

### 2.3 Patterns de Consolidation

#### Pattern A : Parametrisation Simple
```python
# AVANT (3 tests = 18 lignes)
def test_analyze_rm_rf(self):
    result = analyze_command("rm -rf /")
    assert "T1485" in result.mitre_techniques

def test_analyze_dd(self):
    result = analyze_command("dd if=/dev/zero of=/dev/sda")
    assert "T1485" in result.mitre_techniques

def test_analyze_sudo(self):
    result = analyze_command("sudo rm -rf /tmp")
    assert "T1548" in result.mitre_techniques

# APRES (1 test parametrise = 12 lignes, +assertions)
@pytest.mark.parametrize("command,expected_tags", [
    ("rm -rf /", ["T1485"]),
    ("dd if=/dev/zero of=/dev/sda", ["T1485"]),
    ("sudo rm -rf /tmp", ["T1548"]),
])
def test_command_mitre_tagging(self, command, expected_tags):
    result = analyze_command(command)
    assert result is not None
    assert isinstance(result.mitre_techniques, list)
    for tag in expected_tags:
        assert tag in result.mitre_techniques
    assert result.risk_level >= RiskLevel.LOW
```

#### Pattern B : Builder avec Assertions Enrichies
```python
# AVANT
def test_session_stored_in_db(self, indexer, temp_storage):
    session_data = create_session_json("ses_002", "DB Session")
    indexer._file_processor._process_session(session_data)
    conn = indexer._db.connect()
    row = conn.execute("SELECT title FROM sessions WHERE id = 'ses_002'").fetchone()
    assert row[0] == "DB Session"

# APRES
def test_session_processing_complete(self, connected_indexer, session_builder):
    """Process session and verify full data integrity."""
    session = session_builder.with_id("ses_002").with_title("DB Session").build()
    
    result = connected_indexer._file_processor._process_session(session)
    
    # Assertions enrichies (4+)
    assert result == "ses_002", "Should return session ID"
    assert connected_indexer._stats["sessions_indexed"] == 1
    
    row = connected_indexer._db.get_session("ses_002")
    assert row is not None, "Session should be persisted"
    assert row.title == "DB Session"
    assert row.id == "ses_002"
```

#### Pattern C : Test Matrix avec Fixture Factory
```python
@pytest.fixture
def event_factory(base_time):
    """Factory pour creer des evenements avec defaults."""
    def create(event_type, target, offset=0, risk=50, session="test"):
        return SecurityEvent(
            event_type=event_type,
            target=target,
            timestamp=base_time + offset,
            risk_score=risk,
            session_id=session,
        )
    return create

class TestCorrelationMatrix:
    """Test complet des correlations avec matrice."""
    
    CORRELATION_MATRIX = [
        # (event1, event2, expected_correlation, expected_mitre, expected_modifier)
        ((EventType.READ, "/app/.env"), (EventType.WEBFETCH, "https://evil.com"), 
         "exfiltration_read_webfetch", "T1048", 30),
        ((EventType.WEBFETCH, "https://x.com/s.sh"), (EventType.BASH, "bash s.sh"), 
         "remote_code_execution", "T1059", 35),
        # ... plus de cas
    ]
    
    @pytest.mark.parametrize("e1,e2,corr_type,mitre,modifier", CORRELATION_MATRIX)
    def test_correlation_detection(self, correlator, event_factory, e1, e2, 
                                    corr_type, mitre, modifier):
        """Verify correlation detection with full validation."""
        event1 = event_factory(e1[0], e1[1], offset=0)
        event2 = event_factory(e2[0], e2[1], offset=30)
        
        correlator.add_event(event1)
        correlations = correlator.add_event(event2)
        
        # 4+ assertions
        assert len(correlations) >= 1, f"Should detect {corr_type}"
        match = next((c for c in correlations if c.correlation_type == corr_type), None)
        assert match is not None, f"Missing correlation type: {corr_type}"
        assert match.mitre_technique == mitre
        assert match.score_modifier == modifier
        assert match.confidence >= 0.5
```

---

## 3. Checklist par Fichier

### 3.1 Template d'Evaluation

Pour chaque fichier de test, remplir cette checklist :

```markdown
## Fichier : test_xxx.py

### Metriques
- [ ] Nombre de tests : ___
- [ ] Lignes totales : ___
- [ ] Ratio assertions/test : ___
- [ ] Tests avec 1 seule assertion : ___

### Analyse de Redondance
- [ ] Tests avec setup identique identifies
- [ ] Groupes de tests consolidables listes
- [ ] Tests supprimables (couverts ailleurs) identifies

### Plan d'Action
- [ ] Parametriser : [liste des tests]
- [ ] Consolider : [groupes a fusionner]
- [ ] Supprimer : [tests redondants]
- [ ] Enrichir : [tests avec assertions insuffisantes]

### Validation
- [ ] Coverage maintenue >= precedent
- [ ] Mutation score >= precedent
- [ ] Tous les tests passent
```

### 3.2 Decisions : Garder / Refactorer / Supprimer

| Critere | Garder | Refactorer | Supprimer |
|---------|--------|------------|-----------|
| Unique edge case critique | X | | |
| Test avec 4+ assertions | X | | |
| Bien parametrise | X | | |
| 1 assertion, cas commun | | X | |
| Setup duplique > 3 fois | | X | |
| Couvert par autre test | | | X |
| Test flaky non fixable | | | X |
| Mock excessif (> 5 patches) | | X | |

### 3.3 Template d'Amelioration des Assertions

```python
# AVANT : 1 assertion
def test_process_returns_id(self):
    result = processor.process(data)
    assert result == "expected_id"

# APRES : 4+ assertions avec contexte
def test_process_validates_and_returns_id(self):
    """Process should validate input, transform data, and return ID."""
    data = create_valid_data()
    
    result = processor.process(data)
    
    # Assertion 1 : Type de retour
    assert isinstance(result, str), "Should return string ID"
    # Assertion 2 : Format de l'ID
    assert result.startswith("id_"), "ID should have correct prefix"
    # Assertion 3 : Effet de bord verifie
    assert processor.processed_count == 1, "Should increment counter"
    # Assertion 4 : Etat interne coherent
    assert data in processor.cache, "Should cache processed data"
```

---

## 4. Workflow d'Execution

### 4.1 Ordre de Traitement

```
Phase 1 : Quick Wins (Jours 1-2)
------------------------------
1. test_unified_indexer.py      [1251 lignes, -500 cible]
2. test_hybrid_indexer_resume.py [223 lignes, -50 cible]

Phase 2 : UI/Dashboard (Jours 3-4)
----------------------------------
3. test_dashboard_sync.py       [207 lignes, -50 cible]
4. test_tooltips.py             [280 lignes, -80 cible]

Phase 3 : Security (Jours 5-6)
------------------------------
5. test_correlator.py           [462 lignes, -100 cible]
6. test_mitre_tags.py           [269 lignes, -50 cible]

Phase 4 : Autres fichiers (Jours 7+)
------------------------------------
7. test_monitor.py              [1452 lignes, -400 cible]
8. test_parts_enrichment.py     [1246 lignes, -300 cible]
9. Autres fichiers > 500 lignes
```

### 4.2 Workflow par Fichier

```
Pour chaque fichier :

1. BASELINE
   - [ ] pytest tests/test_xxx.py --cov=src --cov-report=term
   - [ ] Noter : coverage %, nb tests, temps execution
   - [ ] mutmut run --paths-to-mutate=src/module.py (si applicable)
   - [ ] Noter : mutation score

2. ANALYSE
   - [ ] Lire le fichier et identifier patterns
   - [ ] Remplir checklist d'evaluation
   - [ ] Decider actions par groupe de tests

3. REFACTORING
   - [ ] Appliquer patterns de consolidation
   - [ ] Ajouter assertions manquantes
   - [ ] Verifier que chaque test a >= 4 assertions

4. VALIDATION INCREMENTALE
   - [ ] pytest tests/test_xxx.py -v (tous passent?)
   - [ ] pytest tests/test_xxx.py --cov (coverage maintenue?)
   - [ ] Si mutation testing applicable : score ameliore?

5. COMMIT ATOMIQUE
   - [ ] git add tests/test_xxx.py
   - [ ] git commit -m "refactor(tests): consolidate test_xxx with improved assertions"
```

### 4.3 Points de Validation

| Checkpoint | Frequence | Criteres de Succes |
|------------|-----------|-------------------|
| Test unitaire | Apres chaque fonction | pytest test.py::TestClass |
| Coverage fichier | Apres refactoring fichier | >= coverage precedente |
| Mutation | Apres phase complete | Score >= 55% (Phase 1), 60% (final) |
| Integration | Apres chaque phase | make test-all passe |
| Ratio global | Fin de phase | Ratio en baisse progressive |

### 4.4 Criteres de Succes par Fichier

| Fichier | Cible Lignes | Cible Tests | Cible Assertions/Test |
|---------|--------------|-------------|----------------------|
| test_unified_indexer.py | < 800 | < 50 | >= 4 |
| test_hybrid_indexer_resume.py | < 180 | < 8 | >= 4 |
| test_dashboard_sync.py | < 150 | < 12 | >= 4 |
| test_tooltips.py | < 200 | < 15 | >= 4 |
| test_correlator.py | < 350 | < 25 | >= 4 |
| test_mitre_tags.py | < 220 | < 18 | >= 4 |

---

## 5. Patterns de Test de Qualite

### 5.1 Structure Arrange-Act-Assert (AAA)

```python
def test_feature_with_aaa_structure(self, fixtures):
    """Docstring describing what is being tested."""
    # ============= ARRANGE =============
    # Setup: Create objects, prepare data, configure mocks
    input_data = create_input(value=42)
    expected_output = ExpectedResult(status="success", value=42)
    mock_dependency.configure(return_value="mocked")
    
    # ============= ACT =============
    # Execute: Single action being tested
    result = system_under_test.process(input_data)
    
    # ============= ASSERT =============
    # Verify: Multiple assertions covering different aspects
    assert result is not None, "Result should not be None"
    assert result.status == expected_output.status, "Status should match"
    assert result.value == expected_output.value, "Value should match"
    assert mock_dependency.called, "Dependency should be called"
    assert mock_dependency.call_count == 1, "Dependency called exactly once"
```

### 5.2 Assertions Robustes

#### Assertions de Type
```python
# Verifier le type avant la valeur
assert isinstance(result, ExpectedClass)
assert hasattr(result, 'required_attribute')
```

#### Assertions de Contenu
```python
# Collections
assert len(items) == 3
assert "key" in dictionary
assert all(item.valid for item in items)

# Strings
assert result.startswith("prefix_")
assert "expected" in result.lower()
```

#### Assertions d'Effet de Bord
```python
# Database
assert db.query_count("SELECT * FROM table") == 1

# State changes
assert object.state_after != object.state_before

# Mock calls
assert mock.called_with(expected_arg)
assert mock.call_count == 2
```

#### Assertions avec Messages Explicites
```python
# Toujours ajouter un message pour les assertions non evidentes
assert result.is_valid, f"Result should be valid, got: {result.errors}"
assert len(items) >= 3, f"Expected at least 3 items, got {len(items)}"
```

### 5.3 Anti-Patterns a Eviter

| Anti-Pattern | Probleme | Solution |
|--------------|----------|----------|
| **Single Assert** | Faible couverture mutation | Ajouter 3+ assertions |
| **Assert True/False generique** | Pas informatif | Assertion specifique |
| **Test sans assert** | Test inutile | Ajouter assertions ou supprimer |
| **Mock everything** | Test fragile | Mocker minimum necessaire |
| **Giant test** | Difficile a maintenir | Decomposer en tests focuses |
| **Magic numbers** | Incomprehensible | Utiliser constantes nommees |
| **Setup duplique** | Maintenance penible | Extraire en fixtures |
| **Test de l'implementation** | Fragile aux refactoring | Tester le comportement |

#### Exemples d'Anti-Patterns

```python
# MAUVAIS : Single Assert
def test_returns_true(self):
    assert function() == True

# MAUVAIS : Test de l'implementation
def test_calls_internal_method(self):
    with patch.object(obj, '_internal_method') as mock:
        obj.public_method()
        mock.assert_called()

# MAUVAIS : Magic numbers
def test_calculation(self):
    assert calculate(5, 3) == 8
    assert calculate(10, 7) == 17

# BON : Multiple assertions avec contexte
def test_addition_behavior(self):
    """Test addition with various inputs."""
    OPERAND_A, OPERAND_B = 5, 3
    EXPECTED_SUM = 8
    
    result = calculate(OPERAND_A, OPERAND_B)
    
    assert isinstance(result, int)
    assert result == EXPECTED_SUM
    assert result == OPERAND_A + OPERAND_B
    assert result > max(OPERAND_A, OPERAND_B)
```

### 5.4 Fixture Best Practices

```python
# Utiliser des fixtures composables
@pytest.fixture
def base_config():
    return {"debug": False, "timeout": 30}

@pytest.fixture
def test_config(base_config):
    return {**base_config, "debug": True}

# Utiliser des factories pour les variations
@pytest.fixture
def user_factory():
    def create(name="test", role="user", active=True):
        return User(name=name, role=role, active=active)
    return create

# Utiliser autouse avec parcimonie
@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test."""
    MySingleton._instance = None
    yield
    MySingleton._instance = None
```

---

## 6. Commandes de Validation

### 6.1 Verification de la Coverage

```bash
# Coverage d'un fichier specifique
pytest tests/test_xxx.py --cov=src/module --cov-report=term-missing

# Coverage complete
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Coverage avec seuil minimum
pytest tests/ --cov=src --cov-fail-under=70
```

### 6.2 Mutation Testing avec mutmut

```bash
# Executer mutation testing sur un module
mutmut run --paths-to-mutate=src/opencode_status_bar/security/correlator.py

# Voir les resultats
mutmut results

# Voir les mutants survivants (a tuer avec de meilleurs tests)
mutmut show <id>

# Rapport HTML
mutmut html
open html/index.html
```

### 6.3 Verification Rapide

```bash
# Tests rapides (sans integration/slow)
pytest tests/ -m "not integration and not slow" -x

# Tests d'un module specifique
pytest tests/test_correlator.py -v

# Tests avec details des assertions echouees
pytest tests/ --tb=short
```

### 6.4 Metriques de Test

```bash
# Compter lignes de test
find tests -name "*.py" | xargs wc -l | tail -1

# Compter fonctions de test
grep -r "def test_" tests/ | wc -l

# Ratio test/code
echo "scale=2; $(find tests -name '*.py' | xargs wc -l | tail -1 | awk '{print $1}') / $(find src -name '*.py' | xargs wc -l | tail -1 | awk '{print $1}')" | bc
```

### 6.5 Validation Pre-Commit

```bash
# Script de validation complet
#!/bin/bash
set -e

echo "=== Running linter ==="
ruff check src/ tests/

echo "=== Running tests ==="
pytest tests/ -x -q

echo "=== Checking coverage ==="
pytest tests/ --cov=src --cov-fail-under=70 -q

echo "=== All checks passed ==="
```

---

## 7. Fichiers Prioritaires

### 7.1 test_unified_indexer.py (1251 lignes)

**Problemes identifies :**
- 22 classes de test (fragmentation excessive)
- Tests simples avec 1-2 assertions
- Setup repete dans chaque classe
- Factories dupliquees (lignes 83-250)

**Plan d'action :**
```
1. Consolider les 7 factories en un seul module tests/factories/indexer.py
2. Fusionner les classes de test par domaine :
   - TestInit + TestLifecycle -> TestUnifiedIndexerCore
   - TestProcessSession + TestProcessMessage + TestProcessPart -> TestFileProcessing
   - TestBatch* -> TestBatchProcessing
3. Parametriser les tests repetitifs (voir TestProcessFile)
4. Enrichir assertions dans chaque test
```

**Cible :** < 800 lignes, < 50 tests, 4+ assertions/test

### 7.2 test_hybrid_indexer_resume.py (223 lignes)

**Problemes identifies :**
- Tests avec 1-2 assertions
- Setup mock repete
- Classes separees inutilement

**Plan d'action :**
```
1. Fusionner TestHybridIndexerResume et TestSyncStateRealtimeProperty
2. Extraire mock setup commun en fixtures
3. Parametriser test_is_realtime_false_for_bulk_phases
4. Ajouter assertions sur les etats intermediaires
```

**Cible :** < 180 lignes, < 8 tests, 4+ assertions/test

### 7.3 test_dashboard_sync.py (207 lignes)

**Problemes identifies :**
- Utilisation excessive de nested patches (4 niveaux)
- Tests parametrises mais assertions simples
- Duplication du setup de mock

**Plan d'action :**
```
1. Creer fixture `dashboard_mocked` avec tous les patches
2. Consolider TestSyncChecker et TestDashboardReadOnly
3. Enrichir assertions dans test_sync_checker_callback_and_timer
4. Ajouter tests de regression pour edge cases
```

**Cible :** < 150 lignes, < 12 tests, 4+ assertions/test

### 7.4 test_tooltips.py (280 lignes)

**Problemes identifies :**
- Duplication du mock_menu_item fixture dans 2 classes
- TestRealWorldScenarios pourrait etre integre

**Plan d'action :**
```
1. Extraire mock_menu_item au niveau module
2. Fusionner TestTruncateWithTooltip et TestRealWorldScenarios
3. Combiner test_truncation_at_boundary avec test_long_text_truncation
4. Ajouter assertions sur les proprietes du MenuItem retourne
```

**Cible :** < 200 lignes, < 15 tests, 4+ assertions/test

### 7.5 test_correlator.py (462 lignes)

**Problemes identifies :**
- 6 classes de test pour un seul module
- Certains tests testent des details d'implementation

**Plan d'action :**
```
1. Fusionner en 2-3 classes max :
   - TestCorrelationDetection (positif + negatif)
   - TestSessionManagement
   - TestCorrelationMetrics (summary + confidence)
2. Utiliser event_factory fixture (deja presente)
3. Parametriser avec CORRELATION_MATRIX
4. Enrichir assertions avec confidence ranges
```

**Cible :** < 350 lignes, < 25 tests, 4+ assertions/test

### 7.6 test_mitre_tags.py (269 lignes)

**Problemes identifies :**
- Deja bien structure avec parametrize
- Manque d'assertions sur les resultats complets

**Plan d'action :**
```
1. Ajouter assertions sur result.risk_level, result.reason
2. Combiner test_command_has_expected_mitre_tags variations
3. Ajouter validation de structure pour chaque resultat
```

**Cible :** < 220 lignes, < 18 tests, 4+ assertions/test

---

## Annexes

### A. Checklist de Review de Test

```markdown
### Pre-Merge Checklist

- [ ] Chaque test a >= 4 assertions
- [ ] Aucun test avec `pass` ou `assert True`
- [ ] Tous les mocks sont necessaires
- [ ] Fixtures utilisees au lieu de setup duplique
- [ ] Tests parametrises quand applicable
- [ ] Noms de tests descriptifs (test_<action>_<scenario>_<expected>)
- [ ] Docstrings sur les tests complexes
- [ ] Coverage >= coverage precedente
- [ ] Pas de tests flaky (re-executer 3x)
```

### B. Script d'Analyse de Test

```python
#!/usr/bin/env python3
"""Analyse les fichiers de test pour identifier les opportunites d'amelioration."""

import ast
import sys
from pathlib import Path
from collections import defaultdict

def analyze_test_file(filepath: Path) -> dict:
    """Analyse un fichier de test."""
    with open(filepath) as f:
        tree = ast.parse(f.read())
    
    stats = {
        "functions": 0,
        "classes": 0,
        "assertions": 0,
        "single_assert_tests": [],
        "no_assert_tests": [],
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            stats["functions"] += 1
            asserts = sum(1 for n in ast.walk(node) if isinstance(n, ast.Assert))
            if asserts == 0:
                stats["no_assert_tests"].append(node.name)
            elif asserts == 1:
                stats["single_assert_tests"].append(node.name)
            stats["assertions"] += asserts
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            stats["classes"] += 1
    
    stats["ratio"] = stats["assertions"] / stats["functions"] if stats["functions"] else 0
    return stats

if __name__ == "__main__":
    for path in Path("tests").glob("test_*.py"):
        stats = analyze_test_file(path)
        if stats["ratio"] < 3:
            print(f"{path.name}: ratio={stats['ratio']:.1f}, "
                  f"single_assert={len(stats['single_assert_tests'])}")
```

### C. Mapping Fichiers Source -> Tests

| Source Module | Test File | Coverage Target |
|---------------|-----------|-----------------|
| security/correlator.py | test_correlator.py | 85% |
| security/analyzer.py | test_mitre_tags.py, test_risk_analyzer.py | 90% |
| analytics/indexer/unified/* | test_unified_indexer.py | 80% |
| analytics/indexer/hybrid.py | test_hybrid_indexer*.py | 80% |
| dashboard/window.py | test_dashboard_*.py | 75% |
| app.py | test_app.py, test_tooltips.py | 70% |

---

## Suivi de Progression

| Phase | Fichier | Baseline | Apres | Delta | Status |
|-------|---------|----------|-------|-------|--------|
| 1 | test_unified_indexer.py | 1251 L / 65 T | - | - | TODO |
| 1 | test_hybrid_indexer_resume.py | 223 L / 8 T | - | - | TODO |
| 2 | test_dashboard_sync.py | 207 L / 9 T | - | - | TODO |
| 2 | test_tooltips.py | 280 L / 18 T | - | - | TODO |
| 3 | test_correlator.py | 462 L / 25 T | - | - | TODO |
| 3 | test_mitre_tags.py | 269 L / 15 T | - | - | TODO |

**Legende :** L = Lignes, T = Tests
