# Instructions projet opencode-status-bar

## Outils d'analyse Python

Ce projet dispose d'outils CLI intégrés pour l'analyse de code Python.
Utilise ces outils au lieu de lsmcp-python qui a des problèmes de timeout.

### Navigation dans le code

```bash
# Aller à la définition d'un symbole
uv run python -m tools.pycode goto <file>:<line>:<col>

# Trouver toutes les références
uv run python -m tools.pycode refs <file>:<line>:<col>

# Obtenir la documentation (hover)
uv run python -m tools.pycode hover <file>:<line>:<col>

# Lister tous les symboles d'un fichier
uv run python -m tools.pycode symbols <file>
```

### Qualité du code

```bash
# Linting avec ruff
uv run python -m tools.pycode lint <path>

# Vérifier le formatage
uv run python -m tools.pycode check <path>

# Analyser la complexité cyclomatique
uv run python -m tools.pycode complexity <path>

# Analyser l'indice de maintenabilité
uv run python -m tools.pycode maintainability <path>

# Détecter le code mort
uv run python -m tools.pycode dead-code <path>

# Rapport combiné
uv run python -m tools.pycode report <path>
```

### Options

- `--json` : Sortie JSON parsable par les agents
- `--verbose` ou `-v` : Afficher plus de détails

### Exemples

```bash
# Navigation JSON
uv run python -m tools.pycode --json goto src/opencode_status_bar/app.py:50:4

# Symboles d'un fichier
uv run python -m tools.pycode symbols src/opencode_status_bar/utils/logger.py

# Rapport de qualité sur un répertoire
uv run python -m tools.pycode report src/opencode_status_bar/analytics/

# Lint avec corrections automatiques
uv run python -m tools.pycode lint --fix src/
```

## Structure du projet

```
src/opencode_status_bar/
├── analytics/      # Analytics et requêtes DuckDB
├── api/            # API REST Flask
├── app/            # Application rumps (menu bar)
├── core/           # Monitoring des instances OpenCode
├── dashboard/      # Dashboard PyQt6
├── security/       # Analyse de sécurité
├── ui/             # Composants UI
└── utils/          # Utilitaires (logger, settings, etc.)

tools/
└── pycode/         # Outils CLI d'analyse Python

tests/
├── integration/    # Tests d'intégration dashboard
└── *.py            # Tests unitaires
```

## Commandes utiles

```bash
# Tests
make test                    # Tous les tests
make coverage                # Tests avec couverture

# Développement
make run                     # Lancer l'app menu bar
uv run python -m opencode_status_bar.dashboard  # Lancer le dashboard
```
