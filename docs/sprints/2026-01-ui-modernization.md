# Sprint - UI Modernization (Janvier 2026)

Modernisation progressive de l'interface du dashboard OpenCode Status Bar.

## Objectifs

- **Lisibilité** : Meilleur contraste, typographie forte
- **Densité** : Meilleure utilisation de l'espace
- **Cohérence** : Composants réutilisables

## Résumé des changements

| Sprint | Objectif | Status |
|--------|----------|--------|
| Sprint 1 | Quick Wins - Couleurs, typo, borders | Terminé |
| Sprint 2 | Badges colorés, layout single-row | Terminé |

---

## Sprint 1 : Quick Wins

### US-01: Améliorer la palette de couleurs

**En tant qu'** utilisateur du dashboard,
**Je veux** un meilleur contraste entre le texte et le fond,
**Afin de** lire plus facilement les informations.

**Critères d'acceptation**:
- [x] `bg_elevated`: #252525 -> #222222
- [x] `text_secondary`: #a0a0a0 -> #b3b3b3
- [x] Borders alpha: 0.06/0.10/0.15 -> 0.08/0.12/0.18
- [x] Contraste WCAG AA (4.5:1)

**Fichiers**: `styles/colors.py`

---

### US-02: Améliorer la hiérarchie typographique

**En tant qu'** utilisateur du dashboard,
**Je veux** une hiérarchie typographique plus marquée,
**Afin de** distinguer rapidement les informations importantes.

**Critères d'acceptation**:
- [x] Tailles augmentées: size_2xl: 24->28, size_3xl: 32->36
- [x] Nouveau weight: weight_extrabold: 800
- [x] Border radius réduits pour look plus moderne

**Fichiers**: `styles/dimensions.py`

---

### US-03: Borders visibles sur cards et tables

**En tant qu'** utilisateur du dashboard,
**Je veux** des borders clairement visibles,
**Afin de** mieux délimiter les sections.

**Critères d'acceptation**:
- [x] MetricCard: border 1px solid + hover state
- [x] Shadow plus subtile
- [x] Value: size_3xl + weight_extrabold

**Fichiers**: `widgets/cards.py`

---

### US-04: Tables plus denses

**En tant qu'** utilisateur du dashboard,
**Je veux** des tables plus denses,
**Afin de** voir plus de lignes sans scroll.

**Critères d'acceptation**:
- [x] row_height: 48 -> 40px
- [x] header_height: 44 -> 36px
- [x] Headers uppercase + letter-spacing

**Fichiers**: `widgets/tables.py`, `styles/dimensions.py`

---

## Sprint 2 : Badges & Layout

### US-05: SectionCard sobre

**En tant que** développeur UI,
**Je veux** un composant SectionCard sobre,
**Afin de** encapsuler les sections sans surcharge visuelle.

**Critères d'acceptation**:
- [x] Background #151515, border gris subtil
- [x] PAS d'accent lines colorées (trop chargé)
- [x] Title + subtitle optionnel

**Fichiers**: `widgets/cards.py`

---

### US-06: Badges colorés dans les tables

**En tant qu'** utilisateur du dashboard,
**Je veux** des badges colorés pour les statuts et risques,
**Afin de** identifier visuellement les informations importantes.

**Critères d'acceptation**:
- [x] CellBadge avec background translucide
- [x] create_risk_badge() - CRITICAL/HIGH/MEDIUM/LOW
- [x] create_type_badge() - COMMAND/READ/WRITE/etc.
- [x] create_score_badge() - Score coloré selon valeur
- [x] Pas de superposition texte/badge

**Fichiers**: `widgets/cell_badge.py`, `sections/security.py`, `sections/monitoring.py`

---

### US-07: Métriques sur une ligne

**En tant qu'** utilisateur du dashboard,
**Je veux** toutes les métriques sur une seule ligne,
**Afin de** gagner de l'espace vertical.

**Critères d'acceptation**:
- [x] Security: 5 cartes sur 1 ligne
- [x] Monitoring: 6 cartes sur 1 ligne
- [x] Largeur adaptative au contenu (plus de crop)

**Fichiers**: `sections/security.py`, `sections/monitoring.py`, `widgets/cards.py`

---

## Fichiers modifiés (récap)

```
src/opencode_status_bar/dashboard/
├── styles/
│   ├── colors.py          # Palette améliorée
│   └── dimensions.py      # Typography, spacing
├── widgets/
│   ├── cards.py           # MetricCard, SectionCard
│   ├── cell_badge.py      # NEW: CellBadge
│   ├── tables.py          # DataTable compact
│   └── __init__.py        # Exports
└── sections/
    ├── monitoring.py      # Layout single-row + badges
    └── security.py        # Layout single-row + badges
```

## Leçons apprises

1. **Couleur = information** : Utiliser la couleur seulement pour les statuts (pas décoratif)
2. **Sobre > Chargé** : L'utilisateur a rejeté les accent lines, préféré design minimal
3. **Tester visuellement tôt** : Les screenshots révèlent des problèmes non visibles dans le code
4. **Largeur adaptative** : Éviter les min/max-width fixes qui coupent le contenu
