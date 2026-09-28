# Plan 04 - Refonte du backend en Python

## Contexte

Les backends actuels (`opencode-eventd` et `opencode-usaged`) sont ecrits en Bash et souffrent de limitations majeures :
- **Appels HTTP sequentiels** : Pour N instances avec M sessions, le daemon fait potentiellement 4*N*M appels curl un par un, resultant en des cycles de 13+ secondes
- **Parsing JSON externe** : Chaque extraction de donnee necessite un appel a jq, ajoutant de la latence
- **Pas de parallelisation native** : Bash ne permet pas de faire des requetes HTTP en parallele simplement
- **Debugging difficile** : Pas de logging structure, difficile de tracer les problemes
- **Maintenance complexe** : Construction de JSON par concatenation de strings, gestion d'erreurs fragile

Ce plan est **prioritaire et fondamental** : tous les plans futurs (01, 02, 03) beneficieront de cette base propre et performante.

## Objectif

Remplacer les backends Bash par un backend Python unique utilisant `asyncio` pour atteindre :
- **Performance** : Cycle de polling < 500ms (au lieu de 13s)
- **Reactivite** : Mise a jour en < 1 seconde apres un evenement
- **Maintenabilite** : Code type, structure en modules, logging structure
- **Fiabilite** : Validation des donnees, gestion d'erreurs robuste

## Comportement attendu

### 1. Daemon unique et unifie

L'utilisateur lance un seul daemon Python qui remplace les deux daemons Bash existants.

**Ce que l'utilisateur voit** :
- Un seul processus a lancer/arreter
- Le daemon detecte automatiquement les instances OpenCode en cours d'execution
- Les fichiers de state sont mis a jour en continu (`/tmp/opencode-state.json`, `/tmp/opencode-usage.json`)
- Le plugin SwiftBar continue de fonctionner sans modification

**Ce qui se passe** :
- Le daemon poll les instances OpenCode et l'API Anthropic
- Toutes les requetes HTTP sont executees en parallele
- Le state est mis a jour des qu'une information change
- SwiftBar est notifie uniquement quand le state change reellement

### 2. Detection et monitoring des instances

**Ce que l'utilisateur observe** :
- Les nouvelles instances OpenCode apparaissent dans le menu en moins de 2 secondes apres leur demarrage
- Les instances fermees disparaissent automatiquement
- Chaque instance affiche ses sessions/agents avec leur statut (busy/idle)
- Les sessions en cours de travail affichent les tools en execution

**Informations collectees par instance** :
- Port d'ecoute
- TTY associe (pour focus iTerm)
- Liste des sessions actives
- Pour chaque session : titre, repertoire, statut, tools en cours, todos
- Detection des permissions en attente (tool running > 5s)

### 3. Requetes HTTP paralleles

**Comportement attendu** :
- Toutes les requetes vers les differentes instances sont lancees en parallele
- Pour une meme instance, les requetes vers differents endpoints peuvent etre parallelisees
- Timeout sur chaque requete (5 secondes max)
- En cas d'echec d'une instance, les autres continuent de fonctionner

**Performance cible** :
- 5 instances avec 3 sessions chacune : < 500ms (au lieu de ~15s en Bash)
- Detection d'une nouvelle instance : < 2s
- Reaction a un evenement SSE : < 100ms

### 4. Gestion de l'usage Anthropic

**Ce que l'utilisateur voit** :
- Pourcentage d'utilisation 5h et 7j dans le menu
- Mise a jour toutes les 5 minutes
- Indicateurs de couleur (vert/jaune/orange/rouge) bases sur le niveau

**Ce qui se passe** :
- Lecture du token OAuth depuis `~/.local/share/opencode/auth.json`
- Verification de l'expiration du token
- Requete vers `https://api.anthropic.com/api/oauth/usage`
- Ecriture du resultat dans `/tmp/opencode-usage.json`

### 5. Logging et debugging

**Ce que l'utilisateur peut faire** :
- Activer le mode debug via variable d'environnement (`OPENCODE_DEBUG=1`)
- Consulter les logs dans un fichier dedie (`/tmp/opencode-status-bar.log`)
- Voir les logs en temps reel avec `tail -f`

**Niveaux de log** :
- DEBUG : Toutes les requetes HTTP, parsing de donnees, details internes
- INFO : Demarrage/arret, detection d'instances, changements de state
- WARN : Timeouts, erreurs recuperables
- ERROR : Echecs critiques, problemes de parsing

### 6. Format du fichier state

Le daemon produit un fichier `/tmp/opencode-state.json` compatible avec le plugin SwiftBar existant.

**Structure attendue** (identique a l'existant) :
```json
{
  "instances": [
    {
      "port": 12345,
      "tty": "ttys001",
      "agents": [
        {
          "id": "session-uuid",
          "title": "Titre de la session",
          "dir": "nom-projet",
          "full_dir": "/chemin/complet/vers/projet",
          "status": "busy",
          "permission_pending": false
        }
      ],
      "agent_count": 1,
      "busy_count": 1
    }
  ],
  "instance_count": 1,
  "agent_count": 1,
  "busy_count": 1,
  "todos": {
    "pending": 2,
    "in_progress": 1
  },
  "permissions_pending": 0,
  "tools_running": ["Read", "Edit"],
  "updated": 1703757600,
  "connected": true
}
```

### 7. Gestion des erreurs et edge cases

**Comportements attendus** :
- JSON malform : Log warning, skip l'instance concernee
- Caracteres de controle dans les reponses : Nettoyage automatique
- Instance qui ne repond plus : Timeout apres 5s, marquee comme deconnectee
- Token expire : Message d'erreur dans le state usage, pas de crash
- Aucune instance : State avec `connected: false`, daemon continue de tourner

### 8. Integration avec les outils existants

**Compatibilite requise** :
- Le plugin SwiftBar (`plugins/opencode.2s.sh`) fonctionne sans modification
- Les fichiers de state ont le meme format
- Les chemins de fichiers sont identiques
- Le signal de refresh SwiftBar est envoye de la meme maniere

**Outils systeme utilises** :
- `lsof` pour detecter les ports des instances OpenCode
- `ps` pour obtenir le TTY d'un processus
- `open -g swiftbar://...` pour notifier SwiftBar

## Checklist de validation

### Installation et demarrage
- [ ] Le daemon Python peut etre lance avec `./bin/opencode-eventd` (meme nom)
- [ ] Un seul processus daemon tourne (singleton avec lock file)
- [ ] Le daemon s'arrete proprement sur SIGTERM/SIGINT

### Detection des instances
- [ ] Les instances OpenCode sont detectees en < 2s apres demarrage
- [ ] Les instances fermees sont supprimees du state
- [ ] Le TTY de chaque instance est correctement detecte

### Collecte des donnees
- [ ] Le statut de chaque session est correct (busy/idle)
- [ ] Les titres des sessions sont recuperes
- [ ] Les repertoires sont recuperes (nom court et chemin complet)
- [ ] Les tools en cours d'execution sont listes
- [ ] Les todos (pending et in_progress) sont comptes
- [ ] Les permissions pending sont detectees (tool > 5s)

### Performance
- [ ] Cycle de polling < 500ms avec 5 instances
- [ ] Le daemon utilise < 5% CPU en idle
- [ ] La memoire reste stable (pas de memory leak)

### Logging
- [ ] Les logs sont ecrits dans `/tmp/opencode-status-bar.log`
- [ ] Le mode debug s'active avec `OPENCODE_DEBUG=1`
- [ ] Les niveaux de log sont respectes (DEBUG, INFO, WARN, ERROR)

### Usage Anthropic
- [ ] L'usage est fetche toutes les 5 minutes
- [ ] Le format du fichier `/tmp/opencode-usage.json` est correct
- [ ] Les erreurs (token expire, API error) sont gerees

### Compatibilite
- [ ] Le plugin SwiftBar affiche les memes informations qu'avant
- [ ] Le menu deroulant montre toutes les instances et sessions
- [ ] Les indicateurs de couleur fonctionnent
- [ ] Le click sur une session focus la bonne fenetre iTerm

### Robustesse
- [ ] Le daemon survit a la perte temporaire d'une instance
- [ ] Le daemon survit a des reponses JSON malformees
- [ ] Le daemon survit a l'absence totale d'instances
- [ ] Le daemon redemarre proprement apres un crash

## Sous-taches

Ce plan peut etre divise en sous-taches pour une implementation progressive :

- 4.1 - Module de base avec types et modeles de donnees
- 4.2 - Client HTTP asynchrone pour l'API OpenCode
- 4.3 - Detection et monitoring des instances
- 4.4 - Ecriture du state et integration SwiftBar
- 4.5 - Gestion de l'usage Anthropic
- 4.6 - Logging structure et mode debug

## Priorite des sous-taches

| Priorite | Sous-tache | Dependances |
|----------|------------|-------------|
| 1 | 4.1 - Module de base | Aucune |
| 2 | 4.2 - Client HTTP async | 4.1 |
| 3 | 4.3 - Detection instances | 4.2 |
| 4 | 4.4 - State et SwiftBar | 4.3 |
| 5 | 4.5 - Usage Anthropic | 4.2 |
| 6 | 4.6 - Logging | Peut etre fait en parallele |

## Notes pour l'executeur

- Python 3.9+ est requis (disponible sur macOS par defaut)
- Seule dependance externe : `aiohttp` pour les requetes HTTP async
- Le daemon doit pouvoir tourner en arriere-plan (daemonisation)
- Conserver le meme nom d'executable pour la compatibilite
- Le backend Bash actuel peut servir de reference pour le comportement exact
