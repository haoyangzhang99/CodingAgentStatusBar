# Plan 10 - Notifications systeme macOS

## Contexte

L'application OpenCode Status Bar dispose actuellement de notifications sonores (plan-02) pour alerter l'utilisateur d'evenements importants. Cependant, quand l'utilisateur n'est pas devant son ecran ou que le volume est coupe, ces alertes peuvent passer inapercues.

Les notifications systeme macOS (Centre de notifications) offrent plusieurs avantages complementaires :
- Visibilite meme quand l'application n'est pas au premier plan
- Persistance dans le Centre de notifications pour consultation ulterieure
- Possibilite d'interaction (clic pour agir)
- Integration native avec le systeme de notifications macOS

**Note** : Ce plan est complementaire au plan-02 (sons). Les deux systemes peuvent fonctionner ensemble ou independamment selon les preferences utilisateur.

**Note Plan-07** : Le plan-07 (detection permissions) a ete abandonne car les API OpenCode ne permettent pas une detection fiable. Ce plan integre une version simplifiee de la notification de permission : detection ponctuelle via scan des tools avec `status: "pending"`, notification immediate sans suivi d'etat "stuck".

## Objectif

Ajouter des notifications systeme macOS natives pour les evenements importants, permettant a l'utilisateur d'etre informe visuellement meme sans surveiller la barre de menu, et de pouvoir interagir avec ces notifications.

## Comportement attendu

### 1. Types de notifications

**Evenements declencheurs** :

| Evenement | Priorite | Description |
|-----------|----------|-------------|
| Agent termine | Normale | Un agent a complete sa tache |
| Permission demandee | Haute | Un agent attend une reponse utilisateur (detection simplifiee) |
| Usage API eleve | Normale | Seuil d'utilisation atteint (70%, 90%) |
| Erreur agent | Haute | Un agent a rencontre une erreur |

**Note** : L'evenement "Agent stuck" du plan-07 n'est pas inclus car la detection fiable de l'etat "waiting for permission" n'est pas possible via les API OpenCode. La notification de permission est declenchee au moment de la detection (scan des tools), sans suivi de duree.

### 2. Contenu des notifications

**Ce que l'utilisateur voit pour chaque type** :

**Completion d'agent** :
- Titre : "Agent termine"
- Sous-titre : Nom/identifiant de la session
- Corps : Resume court de la tache (si disponible) ou message generique

**Permission demandee** :
- Titre : "Permission requise"
- Sous-titre : Nom/identifiant de la session
- Corps : Nom de l'outil en attente (ex: "bash", "edit", "write")
- Note : Detection simplifiee, notification unique au moment de la detection

**Usage API eleve** :
- Titre : "Usage API Anthropic"
- Sous-titre : Pourcentage atteint (ex: "70% utilise")
- Corps : Montant ou details du quota si disponible

**Erreur** :
- Titre : "Erreur agent"
- Sous-titre : Nom/identifiant de la session
- Corps : Message d'erreur court ou type d'erreur

### 3. Comportement des notifications

**Apparition** :
- La notification apparait dans le coin superieur droit (comportement macOS standard)
- Elle reste visible quelques secondes avant de disparaitre
- Elle est ajoutee au Centre de notifications

**Interaction - Clic sur la notification** :

**Ce que l'utilisateur fait** :
- Clique sur la notification

**Ce qui se passe** :
- L'application menu bar est mise au premier plan
- Si possible, le terminal de la session concernee est focus
- La notification est marquee comme lue

**Cas particulier - Permission/Stuck** :
- Le clic devrait idealement ouvrir le terminal sur la session qui attend
- L'utilisateur peut alors repondre a la permission demandee

### 4. Prevention du spam

**Regles anti-spam** :

- **Delai minimum entre notifications identiques** : Une meme notification (meme type, meme session) ne peut pas etre renvoyee avant un delai minimum
- **Regroupement** : Si plusieurs agents terminent simultanement, une seule notification "X agents termines" plutot que X notifications
- **Seuils d'usage API** : Notification a 70% et 90% uniquement, pas de notification repetee tant que le seuil n'a pas ete refranchie (cycle de facturation)
- **Agent stuck** : Une seule notification au passage du seuil "stuck", pas de rappels repetitifs

**Ce que l'utilisateur observe** :
- Les notifications sont informatives mais pas intrusives
- Pas de bombardement de notifications
- Chaque notification apporte une information nouvelle et utile

### 5. Configuration des notifications

**Lien avec plan-08 (Settings)** :

**Ce que l'utilisateur voit dans les preferences** :
- Une section "Notifications systeme" dans le panel de configuration
- Des cases a cocher pour activer/desactiver chaque type de notification :
  - [ ] Agent termine
  - [ ] Permission demandee
  - [ ] Agent stuck
  - [ ] Usage API eleve
  - [ ] Erreurs

**Options additionnelles possibles** :
- Seuils personnalisables pour l'usage API (ex: 50%, 80% au lieu de 70%, 90%)
- Delai avant notification "stuck" (ex: 30s, 60s, 120s)
- Mode "Ne pas deranger" temporaire

**Ce que l'utilisateur observe** :
- Controle total sur les notifications recues
- Les preferences sont persistees entre les sessions
- Les changements s'appliquent immediatement

### 6. Integration avec les sons existants

**Comportement combine** :

- Les notifications systeme et les sons sont independants
- L'utilisateur peut activer l'un, l'autre, ou les deux
- Exemple : Son + Notification pour les permissions, seulement notification pour les completions

**Ce que l'utilisateur configure** :
- Dans les preferences, les deux systemes ont leurs propres toggles
- Section "Sons" (plan-08 existant)
- Section "Notifications systeme" (ce plan)

### 7. Etat initial et valeurs par defaut

**Premier lancement** :
- Notifications activees par defaut pour : Permission, Stuck, Erreurs
- Notifications desactivees par defaut pour : Completion (trop frequent), Usage API
- L'utilisateur peut ajuster selon ses preferences

**Justification** :
- Les permissions et erreurs sont critiques et meritent d'etre notifiees
- Les completions peuvent etre tres frequentes et devenir genant
- L'usage API est une information secondaire

### 8. Icone et branding

**Apparence de la notification** :
- L'icone de l'application apparait dans la notification
- Le nom "OpenCode Status Bar" identifie la source
- Coherence visuelle avec l'application

### 9. Permissions systeme

**Ce qui se passe au premier usage** :
- macOS peut demander l'autorisation d'envoyer des notifications
- L'utilisateur doit accepter pour que les notifications fonctionnent
- Si refuse, les notifications ne s'affichent pas mais l'application continue de fonctionner

**Ce que l'utilisateur voit** :
- Dialogue systeme macOS standard demandant la permission
- L'application fonctionne normalement meme si refuse (juste sans notifications)

## Dependances

- **Plan-08 (Settings)** : Fournit l'infrastructure de configuration pour activer/desactiver les notifications (termine v2.6.0)
- **Plan-12 (Debug preferences)** : Correction du systeme de preferences si necessaire avant implementation

**Note** : Le plan-07 (Permissions) a ete abandonne. La detection de permission est integree directement dans ce plan de maniere simplifiee (scan des tools avec `status: "pending"`, notification immediate sans suivi d'etat).

## Checklist de validation

### Types de notifications
- [ ] Notification pour agent termine
- [ ] Notification pour permission demandee (detection simplifiee)
- [ ] Notification pour usage API eleve (70%, 90%)
- [ ] Notification pour erreurs

### Contenu et apparence
- [ ] Titre clair identifiant le type de notification
- [ ] Sous-titre avec identifiant de session quand applicable
- [ ] Corps informatif sans etre trop long
- [ ] Icone de l'application visible

### Interaction
- [ ] Clic sur notification met l'application au premier plan
- [ ] Clic sur notification permission focus le bon terminal (si possible)
- [ ] Notifications presentes dans le Centre de notifications

### Anti-spam
- [ ] Pas de notifications repetees pour le meme evenement
- [ ] Regroupement des notifications multiples simultanees
- [ ] Seuils d'usage API respectes (pas de re-notification avant nouveau cycle)

### Configuration
- [ ] Section dans les preferences pour activer/desactiver
- [ ] Toggle pour chaque type de notification
- [ ] Preferences persistees entre sessions
- [ ] Valeurs par defaut raisonnables

### Integration sons
- [ ] Fonctionne independamment des sons
- [ ] Peut etre combine avec les sons
- [ ] Pas de conflit entre les deux systemes

### Permissions systeme
- [ ] Gestion de la demande de permission macOS
- [ ] Application fonctionnelle meme si notifications refusees
- [ ] Comportement gracieux en cas de refus
