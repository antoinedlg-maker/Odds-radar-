# Odds Radar 📡

Bot Discord qui compare les cotes de **Winamax, Unibet, PMU et Betsson** et poste des alertes quand il trouve :

- 🟢 **des surebets** : en misant sur toutes les issues chez des bookmakers différents, tu gagnes quel que soit le résultat. Le bot donne la répartition des mises.
- 💎 **des value bets** : une cote nettement au-dessus de la « cote juste », estimée à partir de Pinnacle (le bookmaker le plus précis du marché) une fois sa marge retirée.

Les cotes viennent de [The Odds API](https://the-odds-api.com) (offre gratuite : 500 crédits par mois).

## Commandes

| Commande | Ce que ça fait |
|---|---|
| `/cotes <équipe>` | Tableau des cotes du prochain match de l'équipe, meilleure cote en gras |
| `/surebets` | Les 5 meilleurs surebets en cours |
| `/value` | Les 5 meilleurs value bets en cours |
| `/scan` | Relance une récupération des cotes (1 fois par quart d'heure max) |
| `/statut` | Crédits API restants, championnats suivis, seuils |
| `/sports` | Championnats disponibles et leur code (ne coûte rien) |

Le bot scanne aussi tout seul (toutes les 4 h par défaut) et poste les nouvelles alertes dans le salon choisi, sans doublons.

## Installation

1. **Clé API cotes** : crée un compte gratuit sur [the-odds-api.com](https://the-odds-api.com) et récupère ta clé.
2. **Bot Discord** : sur le [Discord Developer Portal](https://discord.com/developers/applications), crée une application, onglet *Bot* → *Reset Token* pour avoir le token. Onglet *OAuth2* → *URL Generator*, coche `bot` et `applications.commands`, permissions *Send Messages* et *Embed Links*, puis ouvre l'URL pour inviter le bot sur ton serveur.
3. **Config** :
   ```bash
   cp .env.example .env   # puis remplis DISCORD_TOKEN, ODDS_API_KEY, ALERT_CHANNEL_ID
   ```
4. **Lancement** (Python 3.10 ou plus) :
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m odds_radar
   ```

## Gérer les crédits

Chaque scan coûte **1 crédit par championnat et par marché** (les 5 bookmakers tiennent dans une seule requête). Avec les réglages par défaut (Ligue 1 + Premier League, 1N2, toutes les 4 h), ça fait environ 360 crédits par mois, plus les `/scan` manuels et un scan à chaque redémarrage du bot. Le bot s'arrête de scanner tout seul quand il reste moins de 20 crédits.

Pour suivre plus de championnats ou scanner plus souvent, il faut passer à l'offre payante (environ 30 $/mois pour 20 000 crédits).

## À savoir

- Le « Betsson » de l'API est le site international, pas une version française.
- Les surebets disparaissent vite : vérifie toujours les cotes sur le site avant de miser.
- Un value bet est un avantage sur la durée, pas une garantie de gagner le pari.

## Tests

```bash
pip install pytest && pytest
```
