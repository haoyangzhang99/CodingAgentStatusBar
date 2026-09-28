# Plan 17 - Dashboard PyQt

## Context

Actuellement, l'application OpenCode Status Bar affiche les données de monitoring, sécurité et analytics uniquement dans la barre des menus. Les données sont compactes et difficilement lisibles. L'utilisateur doit naviguer rapidement dans le menu pour voir les informations, ce qui n'est pas adapté pour une consultation détaillée ou comparative des données.

## Objective

Créer une interface graphique PyQt (dashboard) qui affiche de manière claire, organisée et visuellement lisible l'ensemble des données existantes du projet :
- Données de monitoring (sessions, todo, outils détectés, etc.)
- Données de sécurité (risques, commandes analysées, permissions, etc.)
- Données statistiques/analytics (KPIs, distributions, tendances, etc.)

## Expected Behavior

1. **Entry point depuis la menubar**
   - Ajouter une entrée "Dashboard" dans le menu rumps
   - Au clic, une fenêtre PyQt séparée s'ouvre en avant-plan
   - La fenêtre peut être fermée sans affecter l'application menubar

2. **Interface organisée en 3 sections**
   - Chaque section (Monitoring, Security, Analytics) est clairement séparée
   - L'utilisateur peut voir un aperçu rapide de chaque section
   - Interface responsive, données agrandies et lisibles

3. **Récupération des données**
   - Les données sont récupérées de la même manière que le client Python actuel (depuis le backend/modèles existants)
   - Pas de nouvelle source de données
   - Réutilisation des classes et méthodes existantes (`client.py`, `models.py`, `monitor.py`, etc.)

4. **Affichage des données**
   - **Monitoring** : Sessions actives, nombre de todos, outils détectés, temps de scans, etc.
   - **Security** : Risques détectés, analyses de commandes, permissions, etc.
   - **Analytics** : KPIs globaux, distributions, statistiques par repository, etc.
   - Format d'affichage : tableaux, listes, ou des éléments visuels clairs

5. **Interaction utilisateur**
   - Interface intuitive et responsive
   - Les données se mettent à jour quand l'utilisateur les demande ou automatiquement
   - Possibilité de naviguer entre les sections

## Skills Required

- **ui-design-principles** : Utiliser les principes de design UI pour structurer l'interface et les sections

## Specifications

(À compléter par l'Executor)

## Validation Checklist

- [ ] Fenêtre PyQt créée et intégrée au projet
- [ ] Entry point "Dashboard" ajouté au menu rumps
- [ ] Section Monitoring implémentée et affiche les données correctement
- [ ] Section Security implémentée et affiche les données de sécurité
- [ ] Section Analytics implémentée et affiche les statistiques
- [ ] Récupération des données utilise les méthodes existantes
- [ ] Interface responsive et lisible
- [ ] Fenêtre peut être ouverte/fermée sans impact sur l'app menubar
- [ ] Tests unitaires pour la nouvelle interface PyQt
- [ ] Documentation mise à jour si nécessaire
- [ ] Global documentation evaluated
