# Plan 18 - Hooks OpenCode pour detection des permissions

## Contexte

La detection des permissions dans opencode-status-bar repose actuellement sur une heuristique de polling (plan-14) qui scanne periodiquement l'etat des sessions. Cette approche fonctionne mais presente des limites :
- Delai entre la demande de permission et sa detection (intervalle de polling)
- Consommation de ressources pour le polling constant
- Risque de faux positifs/negatifs selon le timing

OpenCode dispose d'un systeme de plugins TypeScript qui emet des evenements en temps reel, notamment :
- `permission.updated` : emis quand une demande de permission est creee
- `permission.replied` : emis quand l'utilisateur repond (accept/deny/always)

Ces hooks permettraient une detection instantanee et fiable des permissions.

## Objectif

Explorer et valider l'utilisation des hooks OpenCode comme mecanisme complementaire (ou alternatif) a l'heuristique actuelle pour la detection des permissions.

Approche en deux phases :
1. **POC** : Valider que les hooks fonctionnent et fournissent les bonnes informations
2. **Integration** : Si le POC est concluant, integrer proprement avec un webhook

## Comportement attendu

### Phase 1 - POC (Proof of Concept)

**Plugin OpenCode :**
- Un plugin TypeScript est cree dans `.opencode/plugins/`
- Le plugin ecoute les evenements `permission.updated` et `permission.replied`
- A chaque evenement, le plugin ecrit dans un fichier JSON (ex: `/tmp/opencode-permissions.json`)
- Le fichier contient : timestamp, type d'evenement, session_id, details de la permission

**Validation manuelle :**
- L'utilisateur peut observer le fichier JSON se mettre a jour en temps reel
- On compare avec la detection par heuristique (plan-14)
- On evalue : fiabilite, latence, informations disponibles

**Structure du fichier JSON (suggestion) :**
```json
{
  "last_event": {
    "timestamp": "2025-12-31T10:30:00Z",
    "type": "permission.updated",
    "session_id": "abc123",
    "permission": {
      "tool": "Bash",
      "command": "rm -rf /tmp/test",
      "status": "pending"
    }
  },
  "history": [...]
}
```

### Phase 2 - Integration webhook (si POC concluant)

**Cote opencode-status-bar :**
- Un endpoint webhook est ajoute (ex: `POST /api/permission`)
- Le endpoint recoit les notifications de permission en temps reel
- L'icone de la menubar est mise a jour instantanement (cadenas)
- La notification sonore est jouee immediatement

**Cote plugin OpenCode :**
- Le plugin appelle le webhook local au lieu d'ecrire dans un fichier
- Configuration du port/URL dans le plugin ou via variable d'environnement

**Comparaison avec l'heuristique :**
- Les deux mecanismes coexistent initialement
- On compare les resultats sur une periode de test
- Decision : garder les deux, remplacer l'heuristique, ou autre

## Checklist de validation

### Phase 1 - POC
- [ ] Plugin TypeScript cree dans `.opencode/plugins/`
- [ ] Plugin ecoute `permission.updated` et `permission.replied`
- [ ] Plugin ecrit dans `/tmp/opencode-permissions.json`
- [ ] Test : declencher une permission et verifier le fichier JSON
- [ ] Documenter les informations disponibles dans les evenements
- [ ] Comparer latence : hook vs heuristique polling
- [ ] Evaluer fiabilite : tous les cas detectes ?

### Phase 2 - Integration (si POC OK)
- [ ] Endpoint webhook dans opencode-status-bar
- [ ] Plugin modifie pour appeler le webhook
- [ ] Mise a jour icone menubar via webhook
- [ ] Notification sonore via webhook
- [ ] Tests de non-regression
- [ ] Documentation utilisateur pour installer le plugin
