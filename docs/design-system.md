# Design System

Design system du dashboard OpenCode Status Bar.

## Fichiers de référence

Les tokens de design sont définis dans le code source :

- `src/opencode_status_bar/dashboard/styles/colors.py` - Palette de couleurs
- `src/opencode_status_bar/dashboard/styles/dimensions.py` - Spacing, typography, UI constants

## Principes

### Couleurs

- **Dark theme** avec palette neutre raffinée
- **Layered depth** via les backgrounds (`bg_base` < `bg_surface` < `bg_elevated`)
- **Semantic colors** pour les niveaux de risque et types d'opération
- **Contraste WCAG AA** (4.5:1 minimum)

### Typography

- **System fonts** : `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto`
- **Hiérarchie forte** : 4 niveaux de taille (xs, sm, base, lg, xl, 2xl, 3xl)
- **Weights** : normal (400), medium (500), semibold (600), bold (700), extrabold (800)

### Spacing

- **Base 8px** : xs(4), sm(8), md(16), lg(24), xl(32), 2xl(48)
- **Border radius doux** : sm(4), md(6), lg(8), xl(12)

## Composants principaux

### MetricCard
Carte de métrique avec valeur, label et accent coloré.
- Largeur adaptative au contenu
- Hover state avec border renforcé
- Shadow subtile

### SectionCard
Container sobre pour sections de contenu.
- Background `#151515`
- Border gris subtil
- Titre + subtitle optionnel

### CellBadge
Badge pill coloré pour les tables.
- `create_risk_badge(level)` - CRITICAL/HIGH/MEDIUM/LOW
- `create_type_badge(type)` - COMMAND/READ/WRITE/etc.
- `create_score_badge(score)` - Score numérique coloré

### DataTable
Table de données avec styling moderne.
- Alternating rows
- Row height compact (40px)
- Sorting avec indicateurs
