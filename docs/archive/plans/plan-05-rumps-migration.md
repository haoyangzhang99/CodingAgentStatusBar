# Plan 05 - Migration vers rumps (menu bar native)

## Contexte

Le projet utilise actuellement une architecture hybride :
- **Backend Python** (`bin/opencode-status-bard`) : daemon async performant qui collecte les donnees des instances OpenCode et de l'API Anthropic
- **Frontend SwiftBar** (`plugins/opencode.2s.sh`) : plugin Bash qui lit les fichiers JSON et genere l'affichage

Cette architecture presente des limitations :
- **Separation artificielle** : le daemon ecrit des fichiers JSON que le plugin relit periodiquement
- **Limitations SwiftBar** : output texte uniquement, le caractere `|` pose probleme dans les menus, pas d'UI riche
- **Refresh sur timer** : SwiftBar poll toutes les 2 secondes meme sans changement
- **Maintenance double** : deux langages (Python + Bash), deux logiques d'affichage
- **Hacks textuels** : simulation de sous-menus via indentation, couleurs limitees

## Objectif

Unifier le monitoring dans une **application menu bar native macOS** utilisant **rumps** (Ridiculously Uncomplicated macOS Python Statusbar apps), une bibliotheque Python qui permet de creer des applications menu bar natives.

Avantages attendus :
- **Une seule application** : plus de daemon + plugin separes
- **Menus natifs macOS** : vrais sous-menus, separateurs, icones
- **Event-driven** : mise a jour instantanee sans polling cote UI
- **Notifications natives** : integration avec le centre de notifications macOS
- **Code unifie** : tout en Python, logique centralisee

## Comportement attendu

### 1. Application menu bar unifiee

**Ce que l'utilisateur voit** :
- Une icone dans la menu bar (peut afficher un compteur ou indicateur)
- Au clic, un menu deroulant natif macOS s'ouvre
- Les instances, agents, tools et todos sont affiches dans une hierarchie claire
- L'application demarre automatiquement (optionnel via launchd)

**Ce qui se passe** :
- L'application rumps integre directement le code du daemon existant
- Les donnees sont collectees en arriere-plan (asyncio)
- L'UI se met a jour instantanement quand le state change
- Plus de fichiers JSON intermediaires (sauf pour debugging)

### 2. Structure du menu

**Menu principal** :
```
[Icone + compteur]
├── Instance 1 (port 12345)                    ▶
│   ├── Agent: nom-projet (busy)               ▶
│   │   ├── Tools: Read, Edit
│   │   ├── Todos: 2 pending, 1 in_progress
│   │   └── Focus terminal
│   └── Agent: autre-projet (idle)             ▶
│       └── Focus terminal
├── Instance 2 (port 12346)                    ▶
│   └── ...
├── ────────────────────────────
├── Usage 5h: 45% (vert)
├── Usage 7d: 23% (vert)
├── ────────────────────────────
├── Refresh maintenant
├── Preferences...                             (future)
└── Quitter
```

**Ce que l'utilisateur observe** :
- Vrais sous-menus qui s'ouvrent au survol (pas de hack textuel)
- Indicateurs de couleur via texte colore ou icones
- Separateurs visuels entre les sections
- Navigation fluide et native

### 3. Affichage dans la menu bar

**Options d'affichage** :
- Icone simple (point vert/jaune/rouge selon l'etat)
- Icone + nombre d'agents busy
- Icone + compteur format "2/5" (busy/total)

**Indicateurs visuels** :
- Vert : tous les agents idle, pas de permission en attente
- Jaune : au moins un agent busy
- Orange : permission en attente depuis plus de 5s
- Rouge : erreur ou deconnexion

**Ce que l'utilisateur voit** :
- L'icone change de couleur en temps reel selon l'etat global
- Le compteur se met a jour instantanement quand un agent change de statut
- Pas de delai perceptible entre un evenement et l'affichage

### 4. Interaction avec les sessions

**Clic sur "Focus terminal"** :
- AppleScript active iTerm2 et focus sur le TTY de la session
- Comportement identique a l'existant

**Clic sur une instance ou un agent** :
- Ouvre le sous-menu correspondant
- Alternative : double-clic pour focus (a definir)

### 5. Notifications

**Ce que l'utilisateur recoit** :
- Notification native macOS quand une permission est demandee
- Notification quand tous les todos d'une session sont completes
- Son optionnel associe (reutilisation du module sounds existant)

**Avantages des notifications natives** :
- Apparaissent dans le centre de notifications
- Peuvent etre cliquees pour action
- Respectent les preferences Do Not Disturb de l'utilisateur

### 6. Integration avec le backend existant

**Reutilisation du code** :
- Module `opencode_status_bar.client` : requetes HTTP async vers les instances
- Module `opencode_status_bar.monitor` : detection des instances OpenCode
- Module `opencode_status_bar.state` : agregation du state global
- Module `opencode_status_bar.usage` : collecte usage API Anthropic
- Module `opencode_status_bar.sounds` : notifications sonores
- Module `opencode_status_bar.logger` : logging structure

**Architecture cible** :
```
bin/
  opencode-status-bar        # Application rumps (nouveau point d'entree)
  opencode_status_bar/
    __init__.py
    app.py                # NOUVEAU: classe rumps.App principale
    client.py             # existant
    logger.py             # existant
    models.py             # existant
    monitor.py            # existant
    sounds.py             # existant
    state.py              # existant
    usage.py              # existant
```

### 7. Demarrage et arret

**Ce que l'utilisateur fait** :
- Lance l'application avec `./bin/opencode-status-bar`
- Ou via launchd pour demarrage automatique
- Arrete via le menu "Quitter" ou signal SIGTERM

**Ce qui se passe** :
- L'application s'enregistre dans la menu bar
- Le monitoring demarre en arriere-plan
- Les ressources sont liberees proprement a l'arret

### 8. Mode debug et logging

**Comportement attendu** :
- `OPENCODE_DEBUG=1 ./bin/opencode-status-bar` active les logs detailles
- Les logs vont dans `/tmp/opencode-status-bar.log` (comme avant)
- Option de menu "Voir les logs" qui ouvre le fichier dans Console.app

### 9. Compatibilite et transition

**Phase de transition** :
- Le daemon `opencode-status-bard` reste disponible pour usage standalone
- Le plugin SwiftBar peut continuer a fonctionner si l'utilisateur prefere
- Les fichiers JSON peuvent etre ecrits en option (pour debugging ou outils tiers)

**Deprecation future** :
- Le plugin SwiftBar sera marque comme deprecated
- A terme, seule l'application rumps sera maintenue

## Checklist de validation

### Installation et demarrage
- [ ] L'application se lance avec `./bin/opencode-status-bar`
- [ ] Une icone apparait dans la menu bar macOS
- [ ] L'application ne crash pas au demarrage
- [ ] L'application s'arrete proprement via le menu "Quitter"
- [ ] L'application s'arrete proprement sur SIGTERM

### Affichage menu bar
- [ ] L'icone affiche un indicateur visuel (couleur ou compteur)
- [ ] L'indicateur change en temps reel selon l'etat des agents
- [ ] Vert si tous idle, jaune si busy, orange si permission pending

### Structure du menu
- [ ] Le menu s'ouvre au clic sur l'icone
- [ ] Les instances sont listees avec leur port
- [ ] Chaque instance a un sous-menu avec ses agents
- [ ] Chaque agent affiche son titre et statut (busy/idle)
- [ ] Les agents busy affichent les tools en cours
- [ ] Les todos sont affiches (pending et in_progress)
- [ ] L'usage API (5h et 7d) est affiche avec couleur

### Interactions
- [ ] "Focus terminal" active iTerm2 sur le bon TTY
- [ ] "Refresh maintenant" force une mise a jour
- [ ] "Quitter" ferme proprement l'application

### Notifications
- [ ] Notification native quand permission pending detectee
- [ ] Notification quand tous les todos d'une session sont completes
- [ ] Sons preserves (module sounds reutilise)

### Performance
- [ ] L'UI se met a jour en < 500ms apres un changement
- [ ] Consommation CPU < 5% en idle
- [ ] Consommation memoire stable (pas de leak)

### Reutilisation du backend
- [ ] Le module client.py est reutilise sans modification majeure
- [ ] Le module monitor.py est reutilise sans modification majeure
- [ ] Le module sounds.py est reutilise sans modification majeure
- [ ] Le module logger.py est reutilise sans modification majeure

### Robustesse
- [ ] L'application survit a l'absence d'instances OpenCode
- [ ] L'application survit a des erreurs reseau temporaires
- [ ] L'application survit a des reponses JSON malformees
- [ ] Les erreurs sont loguees mais ne crashent pas l'app

## Sous-taches

- 5.1 - Prototype rumps minimal (icone + menu basique)
- 5.2 - Integration du monitoring async dans la boucle rumps
- 5.3 - Construction dynamique des menus (instances, agents, tools)
- 5.4 - Actions sur les items de menu (focus terminal, refresh)
- 5.5 - Notifications natives macOS
- 5.6 - Indicateurs visuels dans la menu bar (couleur, compteur)
- 5.7 - Cleanup et deprecation du plugin SwiftBar

## Priorite des sous-taches

| Priorite | Sous-tache | Dependances |
|----------|------------|-------------|
| 1 | 5.1 - Prototype rumps | Aucune |
| 2 | 5.2 - Integration async | 5.1 |
| 3 | 5.3 - Menus dynamiques | 5.2 |
| 4 | 5.4 - Actions menu | 5.3 |
| 5 | 5.5 - Notifications | 5.3 |
| 6 | 5.6 - Indicateurs visuels | 5.3 |
| 7 | 5.7 - Cleanup SwiftBar | 5.4, 5.5, 5.6 |

## Notes techniques pour l'executeur

- **rumps** : `pip install rumps` - bibliotheque legere pour menu bar apps
- **asyncio + rumps** : rumps utilise PyObjC, il faudra integrer la boucle async proprement
- **Sous-menus** : `rumps.MenuItem` supporte les enfants via le parametre `children`
- **Icones** : rumps supporte les icones PNG/ICNS dans la menu bar
- **Threading** : attention au thread principal PyObjC, utiliser `@rumps.clicked` pour les callbacks
