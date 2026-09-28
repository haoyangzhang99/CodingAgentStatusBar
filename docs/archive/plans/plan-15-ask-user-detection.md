# Plan 15 - Detection MCP Notify ask_user

## Contexte

Le MCP Notify permet aux agents d'envoyer des notifications a l'utilisateur via le tool `notify_ask_user`. Quand un agent pose une question a l'utilisateur, il envoie une notification puis **attend la reponse** en passant en mode idle.

Actuellement, OpenCode Status Bar ne detecte pas ces demandes d'interaction. L'utilisateur doit verifier manuellement chaque terminal pour savoir si un agent attend une reponse.

## Objectif

Detecter quand un agent a envoye un `ask_user` et attend une reponse de l'utilisateur, puis l'afficher dans le menu pour permettre un suivi visuel.

## Comportement attendu

### Detection
1. Quand une session est **idle** et que son dernier message contient un tool `notify_ask_user` complete
2. L'agent est considere comme "en attente de reponse"
3. Une icone 🔔 s'affiche a cote de l'agent dans le menu
4. Une icone 🔔 s'affiche dans le titre de la barre de menu

### Resolution
1. Quand la session repasse en **busy** (l'utilisateur a repondu)
2. L'indicateur 🔔 est retire
3. Le titre de la barre de menu est mis a jour

### Affichage menu
```
🤖 2 🔔 ⏳3 🟢45%        <- Titre avec indicateur ask_user
─────────────────────
🤖 Agent Principal
    🔧 bash: make test
💤 Agent en attente       <- Session idle normale
🔔 Agent Question         <- Session idle avec ask_user en attente
    └ "Validation requise"  <- Optionnel: titre de la question
```

---

## Specifications Techniques

### Structure API - Tool notify_ask_user

```json
{
    "type": "tool",
    "tool": "notify_ask_user",
    "state": {
        "status": "completed",
        "input": {
            "title": "Validation requise",
            "question": "Je merge sur main ?",
            "options": ["Oui", "Non"],
            "urgency": "normal",
            "agent": "Executeur",
            "task": "Plan-14"
        },
        "output": "⚠️ Question sent [Executeur]: Validation requise",
        "time": {
            "start": 1767037254987,
            "end": 1767037254994
        }
    }
}
```

**Note importante** : Le tool se termine immediatement apres l'envoi de la notification (quelques millisecondes). Il ne reste PAS en status "running".

### Algorithme de detection (Heuristique)

```
POUR chaque session:
  
  SI session.status == IDLE:
    messages = GET /session/{id}/message?limit=1
    
    POUR chaque part dans messages[0].parts:
      SI part.type == "tool"
         ET part.tool == "notify_ask_user"
         ET part.state.status == "completed":
        
        -> ASK_USER EN ATTENTE DETECTE
        -> Extraire: title, question, agent depuis part.state.input
  
  SI session.status == BUSY:
    -> Session active, pas d'ask_user en attente
```

### Fichiers a modifier

| Fichier | Modification |
|---------|-------------|
| `models.py` | Ajouter `has_pending_ask_user: bool` et `ask_user_title: str` sur `Agent` |
| `monitor.py` | Nouvelle fonction `check_pending_ask_user(messages) -> tuple[bool, str]` |
| `monitor.py` | Appeler cette fonction pour les sessions idle dans `fetch_instance()` |
| `menu.py` | Afficher 🔔 au lieu de 💤 si `agent.has_pending_ask_user` |
| `app.py` | Ajouter 🔔 dans le titre si `state.has_any_pending_ask_user` |
| `models.py` | Ajouter property `has_any_pending_ask_user` sur `State` |

### Pseudo-code implementation

```python
# monitor.py
def check_pending_ask_user(messages: list) -> tuple[bool, str]:
    """Check if last message contains a completed notify_ask_user.
    
    Returns: (has_pending, title)
    """
    if not messages:
        return False, ""
    
    parts = messages[0].get("parts", [])
    for part in parts:
        if part.get("type") == "tool" and part.get("tool") == "notify_ask_user":
            state = part.get("state", {})
            if state.get("status") == "completed":
                title = state.get("input", {}).get("title", "")
                return True, title
    
    return False, ""

# Dans fetch_instance(), pour les sessions idle:
if session_status == "idle":
    messages = await client.get_session_messages(session_id, limit=1)
    has_ask, ask_title = check_pending_ask_user(messages)
    agent = Agent(
        ...,
        status=SessionStatus.IDLE,
        has_pending_ask_user=has_ask,
        ask_user_title=ask_title,
    )
```

---

## Checklist de validation

### Detection
- [x] Session idle avec notify_ask_user recent -> has_pending_ask_user = true
- [x] Session idle sans notify_ask_user -> has_pending_ask_user = false
- [x] Session busy -> has_pending_ask_user = false (toujours)
- [x] Extraction du titre de la question

### Affichage menu
- [x] Icone 🔔 a cote des agents avec ask_user en attente
- [x] Icone 🔔 dans le titre menubar si au moins un ask_user
- [x] Tooltip avec le titre de la question (optionnel)

### Resolution
- [x] Quand l'utilisateur repond, la session passe en busy
- [x] L'indicateur 🔔 disparait automatiquement
- [x] Le titre menubar se met a jour

### Edge cases
- [x] Plusieurs sessions avec ask_user simultanement
- [x] Session qui envoie plusieurs ask_user successifs
- [x] Session idle mais sans message recent

---

## Notes d'implementation

### Difference avec la detection de permissions (Plan 14)

| Aspect | Permissions | ask_user |
|--------|------------|----------|
| Condition | Tool running > 5s | Session idle + tool completed |
| Tool | bash, edit, write... | notify_ask_user |
| Icone | 🔒 | 🔔 |
| Resolution | Tool passe a completed | Session passe a busy |

### Performance

La detection des ask_user necessite de fetcher les messages uniquement pour les sessions **idle**. Comme on fetch deja les messages pour les sessions busy, cela ajoute des requetes uniquement pour les sessions idle (generalement peu nombreuses ou rapides).

### Extensibilite future

Cette architecture permet d'ajouter facilement :
- D'autres types de notifications MCP
- Un historique des ask_user
- Des statistiques d'utilisation

---

## Documentation

### Lien avec OpenFlow

Le serveur MCP Notify est defini dans le projet **[OpenFlow](https://github.com/OpenClaudeAgent/open-flow)** :
- Repo : https://github.com/OpenClaudeAgent/open-flow
- Chemin : `servers/notify/server.py`
- Config OpenCode : `~/.config/opencode/opencode.json` (section `mcp.notify`)

OpenCode Status Bar detecte les appels a ce serveur MCP via l'API OpenCode, sans modification du serveur Notify lui-meme.

### Mise a jour README.md

Ajouter dans le README principal (pas de nouveau fichier) :

**Section Features** - Ajouter :
```
- **Permission detection** 🔒 heuristic indicator for tools waiting approval
- **MCP Notify tracking** 🔔 indicator when agent awaits user response
```

**Section Menu Bar Display** - Mettre a jour :
```
🤖 2 🔒 🔔 ⏳3 🟢45%

- 🔒 - Permission may be pending (tool running > 5s)
- 🔔 - Agent awaits user response (MCP Notify ask_user)
```

**Section Menu Contents** - Ajouter exemples :
```
🔒 bash: npm install        ← May need permission (running 15s)
🔔 Agent Question           ← Awaiting user response
```

### Checklist documentation
- [x] Mettre a jour section Features dans README.md
- [x] Mettre a jour section Menu Bar Display avec 🔒 et 🔔
- [x] Ajouter exemples dans Menu Contents
- [x] Mentionner la dependance optionnelle a OpenFlow/MCP Notify

---

## Bonus - Evolutions d'implementation

### Scan fichiers disque (vs API)

L'algorithme initial prevoyait d'utiliser l'API OpenCode (`GET /session/{id}/message`). L'implementation finale utilise le **scan direct des fichiers session** sur disque (`~/.local/share/opencode/storage/message/{session_id}/`).

**Raisons du changement :**
- Performance : evite des appels API supplementaires pour les sessions idle
- Fiabilite : fonctionne meme si l'instance OpenCode n'est plus active
- Detection zombie : permet de filtrer les sessions mortes via le cache de ports

### Timeout configurable

Un nouveau setting a ete ajoute dans `settings.py` :

| Setting | Default | Description |
|---------|---------|-------------|
| `ask_user_timeout` | 1800s (30min) | Duree avant de masquer une notification sans reponse |

**Note** : La detection des sessions zombies (ports morts) est geree separement par le cache de ports dans `app.py`, qui ejecte les sessions en ~5-10s quand leur port meurt.

### UI Preferences

Le timeout est configurable via le menu **⚙️ Preferences** :
- **🔔 Ask user timeout** : 5m / 15m / 30m / 1h
