# Plan 12 - Debug systeme de preferences

## Contexte

Le systeme de preferences implemente dans le plan-08 (v2.6.0) presente un dysfonctionnement : les parametres modifies par l'utilisateur ne sont pas correctement pris en compte par l'application.

**Probleme observe** :
- L'utilisateur desactive les sons dans les preferences
- Les sons continuent a etre joues malgre la desactivation
- Le parametre semble etre ignore lors de l'execution

**Impact** :
- Experience utilisateur degradee
- Perte de confiance dans le systeme de configuration
- Bloque l'implementation du plan-10 (notifications) qui depend des preferences

## Objectif

Identifier et corriger le bug qui empeche les preferences d'etre correctement appliquees, en particulier pour les notifications sonores.

## Comportement attendu

### 1. Persistence des preferences

**Ce que l'utilisateur fait** :
- Ouvre le menu de l'application
- Va dans Preferences > Sounds
- Desactive "Completion sound"

**Ce qui devrait se passer** :
- Le parametre est sauvegarde dans le fichier de configuration
- Le parametre est immediatement applique
- Au prochain lancement, le parametre est restaure

**Ce qui se passe actuellement** :
- Le son continue a etre joue malgre la desactivation

### 2. Lecture des preferences

**Ce que l'application doit faire** :
- Charger les preferences au demarrage
- Verifier les preferences avant chaque action configurable
- Appliquer les changements de preferences immediatement

### 3. Points de verification

**Fichier de configuration** :
- Emplacement : `~/.config/opencode-status-bar/settings.json`
- Format : JSON valide
- Contenu : Tous les parametres avec leurs valeurs actuelles

**Code de lecture** :
- La fonction `get_settings()` retourne les bonnes valeurs
- Les valeurs sont lues depuis le fichier, pas les valeurs par defaut
- Le singleton est correctement initialise

**Code d'application** :
- Avant de jouer un son, verifier `settings.sound_completion`
- La verification utilise bien `get_settings()` et pas une copie locale

## Investigation requise

### 1. Verifier la sauvegarde

```bash
# Apres avoir modifie une preference
cat ~/.config/opencode-status-bar/settings.json
```

**Questions** :
- Le fichier existe-t-il ?
- Le parametre modifie est-il present ?
- La valeur est-elle correcte (true/false) ?

### 2. Verifier le chargement

**Points a verifier dans le code** :
- `Settings.load()` lit-il le bon fichier ?
- Le singleton `_settings` est-il reinitialise apres modification ?
- Y a-t-il un cache qui n'est pas invalide ?

### 3. Verifier l'application

**Points a verifier dans le code** :
- `check_and_notify_completion()` utilise-t-il `get_settings()` ?
- La verification se fait-elle a chaque appel ou une seule fois ?
- Y a-t-il une condition qui court-circuite la verification ?

## Causes possibles

### Hypothese 1 : Singleton non rafraichi

**Description** :
- `get_settings()` retourne un singleton initialise au demarrage
- La modification de preference met a jour le fichier mais pas le singleton
- Les appels suivants utilisent l'ancienne valeur en memoire

**Verification** :
- Comparer la valeur dans le fichier vs la valeur retournee par `get_settings()`

**Solution potentielle** :
- Recharger le singleton apres chaque modification
- Ou : ne pas utiliser de singleton, charger depuis le fichier a chaque fois

### Hypothese 2 : Fichier non sauvegarde

**Description** :
- Le toggle dans l'UI change l'etat visuel
- Mais `save_settings()` n'est pas appele ou echoue silencieusement

**Verification** :
- Ajouter du logging dans `save_settings()`
- Verifier que le fichier est modifie apres changement de preference

**Solution potentielle** :
- S'assurer que `save_settings()` est appele apres chaque modification
- Ajouter de la gestion d'erreur si l'ecriture echoue

### Hypothese 3 : Mauvais chemin de fichier

**Description** :
- Le fichier est sauvegarde dans un emplacement
- Mais lu depuis un autre emplacement

**Verification** :
- Logger les chemins utilises pour la lecture et l'ecriture

**Solution potentielle** :
- Utiliser une constante unique pour le chemin

### Hypothese 4 : Condition ignoree

**Description** :
- La verification `if settings.sound_completion` existe
- Mais une autre condition fait que le son est joue quand meme

**Verification** :
- Revoir la logique dans `check_and_notify_completion()`
- Ajouter du logging pour tracer le flux d'execution

**Solution potentielle** :
- Corriger la condition ou l'ordre des verifications

## Checklist de validation

### Investigation
- [ ] Verifier que le fichier settings.json existe apres modification
- [ ] Verifier que le contenu du fichier reflate les changements
- [ ] Verifier que `get_settings()` retourne les bonnes valeurs
- [ ] Tracer le flux d'execution lors d'un evenement de completion

### Correction
- [ ] Identifier la cause racine du probleme
- [ ] Implementer la correction
- [ ] Tester la desactivation des sons de completion
- [ ] Tester la reactivation des sons de completion
- [ ] Verifier la persistence apres redemarrage de l'application

### Non-regression
- [ ] Les autres preferences fonctionnent correctement
- [ ] Le toggle dans l'UI reflete bien l'etat actuel
- [ ] Pas de regression sur les fonctionnalites existantes

## Implementation

### Phase 1 : Diagnostic

1. Ajouter du logging temporaire :
   - Dans `Settings.save()` : logger le chemin et le contenu
   - Dans `Settings.load()` : logger le chemin et le contenu charge
   - Dans `get_settings()` : logger la valeur de `sound_completion`
   - Dans `check_and_notify_completion()` : logger la decision (jouer ou non)

2. Reproduire le probleme :
   - Desactiver les sons dans les preferences
   - Declencher un evenement de completion
   - Analyser les logs

### Phase 2 : Correction

1. Corriger la cause identifiee
2. Supprimer le logging temporaire
3. Tester exhaustivement

### Phase 3 : Prevention

1. Ajouter des tests unitaires pour le systeme de preferences (si applicable)
2. Documenter le fonctionnement du systeme de preferences
