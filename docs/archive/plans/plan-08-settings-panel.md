# Plan 08 - Panel de configuration

## Contexte

L'application menu bar OpenCode Status Bar utilise actuellement des valeurs fixes pour plusieurs parametres :
- Frequence de rafraichissement de l'usage API Anthropic (60 secondes)
- Alertes sonores activees par defaut sans possibilite de les desactiver
- Autres parametres potentiels non configurables

L'utilisateur n'a aucun moyen de personnaliser ces comportements sans modifier le code.

## Objectif

Ajouter un panneau de configuration accessible depuis le menu, permettant a l'utilisateur de personnaliser :
1. La frequence de rafraichissement de l'usage API Anthropic
2. L'activation/desactivation des alertes sonores par type

## Comportement attendu

### 1. Acces aux settings

**Ce que l'utilisateur voit** :
- Un item "Preferences..." ou "Settings..." dans le menu principal
- L'item est place en bas du menu, avant "Quitter"

**Ce que l'utilisateur fait** :
- Clique sur "Preferences..."
- Une fenetre de configuration s'ouvre

**Ce qui se passe** :
- Une fenetre native macOS s'affiche
- Les parametres actuels sont pre-remplis
- L'utilisateur peut modifier et sauvegarder

### 2. Configuration de la frequence de rafraichissement

**Parametre : Frequence de l'usage API**

**Ce que l'utilisateur voit** :
- Un champ ou slider pour definir la frequence
- La valeur actuelle est affichee (ex: "60 secondes")
- Des valeurs suggerees peuvent etre proposees (30s, 60s, 120s, 300s)

**Plage de valeurs** :
- Minimum : 30 secondes (eviter de surcharger l'API Anthropic)
- Maximum : 600 secondes (10 minutes)
- Defaut : 60 secondes

**Ce que l'utilisateur observe** :
- Apres modification, la nouvelle frequence s'applique immediatement
- Pas besoin de redemarrer l'application

### 3. Configuration des alertes sonores

**Parametre : Alertes sonores**

**Ce que l'utilisateur voit** :
- Une section "Notifications sonores" ou "Sons"
- Des cases a cocher pour chaque type d'alerte :
  - Son de completion (quand un agent termine une tache)
  - Son de permission (quand une permission est demandee)
  - Autres types potentiels selon les fonctionnalites existantes

**Ce que l'utilisateur fait** :
- Coche ou decoche chaque type d'alerte
- Les changements s'appliquent immediatement

**Ce que l'utilisateur observe** :
- Quand une case est decochee, le son correspondant ne joue plus
- Quand elle est recochee, le son fonctionne a nouveau
- Optionnel : un bouton "Tester" pour ecouter chaque son

### 4. Persistance des settings

**Ce qui se passe en interne** :
- Les preferences sont sauvegardees dans un fichier de configuration
- Emplacement suggere : `~/.config/opencode-status-bar/settings.json` ou equivalent
- Les preferences sont chargees au demarrage de l'application

**Ce que l'utilisateur observe** :
- Les preferences sont conservees entre les sessions
- Au redemarrage, l'application utilise les dernieres valeurs sauvegardees

### 5. Interface du panel

**Design** :
- Fenetre native macOS simple et claire
- Organisation en sections logiques (General, Sons, etc.)
- Boutons "Annuler" et "Enregistrer" ou sauvegarde automatique

**Sections suggerees** :
```
+----------------------------------+
|          Preferences             |
+----------------------------------+
| General                          |
|   Frequence usage API: [60s  v]  |
|                                  |
| Notifications sonores            |
|   [ ] Son de completion          |
|   [x] Son de permission          |
|                                  |
|         [Annuler] [Enregistrer]  |
+----------------------------------+
```

**Comportement des boutons** :
- "Annuler" : ferme la fenetre sans sauvegarder
- "Enregistrer" : sauvegarde et ferme la fenetre
- Alternative : sauvegarde automatique a chaque modification

### 6. Valeurs par defaut

**Ce qui se passe au premier lancement** :
- Si aucun fichier de configuration n'existe, les valeurs par defaut sont utilisees
- Les valeurs par defaut sont identiques au comportement actuel :
  - Frequence usage API : 60 secondes
  - Tous les sons actives

**Ce que l'utilisateur observe** :
- L'application fonctionne immediatement sans configuration
- Les preferences par defaut sont raisonnables

### 7. Extensibilite future

**Structure flexible** :
- Le panel doit pouvoir accueillir de nouveaux parametres facilement
- Organisation en sections permettant d'ajouter des options
- Exemples de futurs parametres possibles :
  - Theme (clair/sombre/systeme)
  - Delai avant "stuck" pour les permissions
  - Frequence de scan des instances
  - Limite de longueur pour le troncage

## Checklist de validation

### Acces aux settings
- [ ] Item "Preferences..." present dans le menu
- [ ] Placement correct (avant "Quitter")
- [ ] Clic ouvre la fenetre de configuration

### Frequence usage API
- [ ] Champ/slider pour definir la frequence
- [ ] Valeur actuelle affichee
- [ ] Plage 30s - 600s respectee
- [ ] Changement applique immediatement

### Alertes sonores
- [ ] Section dediee aux sons
- [ ] Case pour son de completion
- [ ] Case pour son de permission
- [ ] Changements appliques immediatement

### Persistance
- [ ] Preferences sauvegardees dans un fichier
- [ ] Preferences chargees au demarrage
- [ ] Valeurs conservees entre sessions

### Interface
- [ ] Fenetre native macOS
- [ ] Organisation claire en sections
- [ ] Boutons Annuler/Enregistrer fonctionnels
- [ ] Design coherent avec macOS

### Valeurs par defaut
- [ ] Application fonctionne sans configuration
- [ ] Valeurs par defaut raisonnables
- [ ] Premier lancement sans erreur

### Extensibilite
- [ ] Structure permettant d'ajouter des parametres
- [ ] Sections extensibles
