# 🤖 Twitch Channel Points Miner - Bot Telegram de Gestion Dynamique

## 📋 Vue d'ensemble

Ce système vous permet de **gérer vos streamers et paramètres via Telegram SANS redémarrer le programme**. Fini les modifications manuelles dans le code !

---

## 🚀 Installation

### 1️⃣ Installer les dépendances Python

```bash
pip install python-telegram-bot
```

### 2️⃣ Structure des fichiers

Placez ces nouveaux fichiers dans le même dossier que votre `main.py` :

```
votre-projet/
├── main.py (votre ancien fichier)
├── main_dynamic.py (nouveau - à utiliser)
├── TelegramBot.py (nouveau)
├── config_loader.py (nouveau)
├── streamers_config.json (nouveau - sera créé automatiquement)
└── TwitchChannelPointsMiner/ (dossier existant)
```

### 3️⃣ Configuration initiale

1. **Éditez `main_dynamic.py`** :
   - Remplacez `"write-your-secure-psw"` par votre vrai mot de passe Twitch
   - Vérifiez que votre token Telegram et chat_id sont corrects

2. **Créez votre fichier de configuration** :
   - Copiez le contenu de `streamers_config.json` fourni
   - Modifiez la liste des streamers selon vos besoins
   - Sauvegardez le fichier dans le dossier du projet

---

## 🎮 Utilisation

### Démarrer le miner

```bash
python main_dynamic.py
```

Le programme va :
1. ✅ Charger les streamers depuis `streamers_config.json`
2. ✅ Démarrer le bot Telegram
3. ✅ Lancer le mining normalement

### Commandes Telegram disponibles

#### 📋 Gestion des streamers

| Commande | Description | Exemple |
|----------|-------------|---------|
| `/start` ou `/help` | Afficher l'aide complète | `/start` |
| `/add <username>` | Ajouter un nouveau streamer | `/add ninja` |
| `/remove <username>` | Retirer un streamer | `/remove ninja` |
| `/list` | Voir tous les streamers configurés | `/list` |
| `/status` | Statut en temps réel (online/offline) | `/status` |

#### ⚙️ Modification des paramètres

| Commande | Description | Exemple |
|----------|-------------|---------|
| `/set_bet <username> <percentage>` | Modifier le % de bet | `/set_bet suns1de999 10` |
| `/set_max_points <username> <points>` | Modifier le max de points à bet | `/set_max_points ohnepixel 5000` |
| `/enable_predictions <username>` | Activer les prédictions | `/enable_predictions dorozea` |
| `/disable_predictions <username>` | Désactiver les prédictions | `/disable_predictions dorozea` |

#### 📊 Informations

| Commande | Description |
|----------|-------------|
| `/stats` | Statistiques globales (points totaux, uptime, etc.) |

---

## 🔄 Comment ça marche ?

### Architecture

```
┌─────────────────────┐
│  Telegram App       │
│  (Vous)             │
└──────────┬──────────┘
           │ Commandes
           ▼
┌─────────────────────┐
│  TelegramBot.py     │
│  (Bot de gestion)   │
└──────────┬──────────┘
           │ Modifie
           ▼
┌─────────────────────┐
│ streamers_config.json│
│ (Configuration)     │
└──────────┬──────────┘
           │ Lu par
           ▼
┌─────────────────────┐
│  main_dynamic.py    │
│  (Mining)           │
└─────────────────────┘
```

### Workflow

1. **Vous envoyez une commande** sur Telegram (ex: `/add ninja`)
2. **Le bot modifie** `streamers_config.json`
3. **La configuration est sauvegardée** immédiatement
4. ⚠️ **Note actuelle** : Le miner doit être redémarré pour appliquer les changements (pour l'instant)

---

## 📝 Format du fichier de configuration

### Structure JSON

```json
{
  "streamers": [
    {
      "username": "nom_du_streamer",
      "settings": {
        "make_predictions": false,
        "follow_raid": true,
        "claim_drops": true,
        "watch_streak": true,
        "community_goals": true,
        "bet": {
          "strategy": "SMART",
          "percentage": 5,
          "stealth_mode": true,
          "percentage_gap": 20,
          "max_points": 1000,
          "delay_mode": "FROM_END",
          "delay": 6,
          "minimum_points": 20000,
          "filter_condition": {
            "by": "TOTAL_USERS",
            "where": "LTE",
            "value": 800
          }
        }
      }
    }
  ],
  "global_settings": {
    "default_bet_percentage": 5,
    "default_max_points": 1000,
    "default_make_predictions": false
  }
}
```

### Valeurs possibles

#### Strategies de bet
- `"SMART"` - Stratégie intelligente (recommandé)
- `"PERCENTAGE"` - Pourcentage fixe
- `"SMART_MONEY"` - Suivre les gros parieurs
- `"HIGH_ODDS"` - Parier sur les cotes élevées
- `"MOST_VOTED"` - Suivre la majorité

#### Delay modes
- `"FROM_START"` - Délai depuis le début
- `"FROM_END"` - Délai avant la fin (recommandé)
- `"PERCENTAGE"` - Pourcentage du temps

#### Filter conditions
- `by`: `"TOTAL_USERS"`, `"TOTAL_POINTS"`, `"ODDS"`, etc.
- `where`: `"LTE"` (≤), `"GTE"` (≥), `"LT"` (<), `"GT"` (>)

---

## 🔧 Personnalisation avancée

### Ajouter vos propres commandes

Éditez `TelegramBot.py` et ajoutez votre fonction :

```python
async def cmd_ma_commande(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ma commande personnalisée"""
    await update.message.reply_text("Hello!")

# Dans start(), ajoutez :
app.add_handler(CommandHandler("ma_commande", self.cmd_ma_commande))
```

### Modifier les paramètres par défaut

Éditez la section `global_settings` dans `streamers_config.json`.

---

## ⚠️ Limitations actuelles

### 🔴 Rechargement à chaud non implémenté

Pour l'instant, les modifications via Telegram sont **sauvegardées dans le JSON** mais nécessitent un **redémarrage du miner** pour être appliquées.

### 🟢 Ce qui fonctionne
- ✅ Ajout/suppression de streamers dans la config
- ✅ Modification des paramètres dans la config
- ✅ Affichage du statut en temps réel
- ✅ Statistiques

### 🟡 Prochaines améliorations
- 🔄 Rechargement à chaud sans redémarrage
- 📊 Graphiques de statistiques
- 🔔 Alertes personnalisées
- 💾 Backup automatique de la config

---

## 🆘 Dépannage

### Le bot ne répond pas
- Vérifiez que le token Telegram est correct
- Vérifiez que le bot est bien lancé (voir les logs)
- Essayez `/start` pour vérifier la connexion

### Les streamers ne se chargent pas
- Vérifiez le format du fichier JSON
- Regardez les logs pour les erreurs
- Vérifiez les noms d'utilisateur (pas de majuscules inutiles)

### Erreur de connexion Twitch
- Vérifiez votre username et password
- Vérifiez votre connexion Internet
- Attendez quelques minutes (rate limiting)

---

## 📚 Ressources

- [Documentation Twitch API](https://dev.twitch.tv/)
- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [Repo original du miner](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2)

---

## 🎯 Migration depuis l'ancien main.py

Si vous avez déjà une liste de streamers dans votre `main.py`, vous pouvez :

1. Utiliser le script `config_loader.py` pour exporter :
   ```python
   from config_loader import export_current_config_to_json
   export_current_config_to_json(vos_streamers)
   ```

2. Ou créer manuellement le JSON en copiant vos streamers

---

## 💡 Conseils

1. **Faites un backup** de votre `main.py` original
2. **Testez d'abord** avec 2-3 streamers
3. **Surveillez les logs** la première fois
4. **Utilisez `/status`** régulièrement pour vérifier
5. **Gardez `streamers_config.json`** sous contrôle de version (git)

---

## 🤝 Support

Si vous rencontrez des problèmes :
1. Vérifiez les logs du programme
2. Vérifiez le format du JSON
3. Testez les commandes Telegram une par une

Bon farming ! 🎮💰