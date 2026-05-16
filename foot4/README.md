# FOOT/4 — Site de combo prédictif quotidien

Site personnel statique qui affiche un combo 4 matchs basé sur l'algorithme
prédictif (Dixon-Coles + Elo + forme récente) sur les 5 ligues majeures
européennes. **Actualisé toutes les 6 heures** via GitHub Actions, hébergement
**gratuit** sur GitHub Pages.

## Architecture

```
                    ┌───────────────────────────┐
   GitHub Actions   │  scripts/update_predictions.py
   cron 0 */6 * * * │  • charge l'historique CSV (football-data.co.uk)
                    │  • entraîne Dixon-Coles + Elo
                    │  • fetch fixtures (football-data.org API)
                    │  • génère data/predictions.json
                    │  • commit + push
                    └────────────┬──────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────┐
              │  data/predictions.json (commit)  │
              └────────────┬─────────────────────┘
                           │
                           ▼
              ┌──────────────────────────────────┐
              │  GitHub Pages sert site/         │
              │  index.html ⟶ app.js ⟶ JSON      │
              └──────────────────────────────────┘
```

Aucun serveur, aucun coût, aucune base de données.

## Mise en place (15 minutes)

### 1. Récupère une clé API football-data.org (gratuite)

1. Va sur https://www.football-data.org/client/register
2. Crée un compte (email + mot de passe, pas de carte bancaire)
3. Récupère ton token dans le profil (`X-Auth-Token`)
4. Le tier gratuit donne 10 requêtes/min — largement suffisant (on en fait 5
   par run, une par ligue)

### 2. Crée un nouveau repo GitHub

```bash
gh repo create foot4 --public --clone
cd foot4
```

Ou via l'interface web : New repository → public.

### 3. Copie le contenu de ce projet dans le repo

```bash
cp -r /chemin/vers/football_predictor_site/* .
git add .
git commit -m "Initial commit"
git push
```

### 4. Configure le secret API

Dans ton repo sur github.com : **Settings → Secrets and variables → Actions →
New repository secret** :

- Name: `FOOTBALL_DATA_API_KEY`
- Value: ton token football-data.org

### 5. Active GitHub Pages

**Settings → Pages** :
- Source : `Deploy from a branch`
- Branch : `main`
- Folder : `/ (root)`

Sauvegarde. Au bout de 1 minute, ton site est en ligne à :
`https://<ton-username>.github.io/<nom-du-repo>/site/`

Tu peux ajouter un fichier `index.html` redirigeant vers `site/` à la racine si
tu veux raccourcir l'URL :

```html
<!DOCTYPE html><meta http-equiv="refresh" content="0;url=site/">
```

Ou configurer un domaine perso (Settings → Pages → Custom domain).

### 6. Lance le premier build

**Actions → Update predictions → Run workflow → Run**.

Au bout de ~3 minutes le `data/predictions.json` est mis à jour et committé.
Recharge ton site, le combo s'affiche.

## Fonctionnement automatique

Une fois en place, **plus rien à faire**. GitHub Actions exécute le workflow
toutes les 6 heures (00:00, 06:00, 12:00, 18:00 UTC) :

- ✅ Si des matchs sont programmés dans les 3 jours et qu'au moins 4 sélections
  dépassent 65% de confiance → combo affiché
- ✅ Si pas assez de sélections confiantes → état "Pas de combo aujourd'hui"
- ✅ Si aucun match programmé → état "Aucun match dans les 5 ligues"
- ⚠️ Si erreur → état d'erreur affiché avec message

## Lancer en local pour tester

```bash
pip install -r requirements.txt

# Génère predictions.json (nécessite ta clé API)
FOOTBALL_DATA_API_KEY=ton_token python scripts/update_predictions.py

# Servi en local
python -m http.server 8000
# → http://localhost:8000/site/
```

## Réglages

Tout est dans `algo/config.py` :

```python
MIN_CONFIDENCE = 0.65    # seuil par sélection
COMBO_SIZE = 4           # taille du combo
DC_TIME_DECAY = 0.0065   # décroissance temporelle Dixon-Coles
WEIGHT_DIXON_COLES = 0.60
WEIGHT_ELO = 0.25
WEIGHT_FORM = 0.15
```

La fréquence de rafraîchissement se règle dans
`.github/workflows/update.yml`. Le cron `0 */6 * * *` = toutes les 6h. Pour
toutes les 3h : `0 */3 * * *`.

⚠️ Note : sur le tier gratuit GitHub Actions, les workflows planifiés peuvent
avoir un délai allant jusqu'à 15-30 minutes en heure de pointe. Pour avoir des
mises à jour pile à l'heure, il faut un runner dédié (payant) ou un autre
système (Vercel Cron, Cloudflare Workers Cron…).

## Structure des fichiers

```
.
├── README.md
├── requirements.txt
├── .github/workflows/update.yml      ← cron toutes les 6h
├── algo/                              ← l'algorithme
│   ├── config.py                      paramètres
│   ├── data_loader.py                 chargement historique
│   ├── dixon_coles.py                 modèle Poisson corrélé
│   ├── elo.py                         ratings Elo
│   ├── features.py                    forme récente
│   ├── ensemble.py                    combinaison pondérée
│   ├── combo_builder.py               logique de sélection
│   ├── fixtures_fetcher.py            API football-data.org
│   └── team_mapping.py                correspondance noms d'équipes
├── scripts/
│   └── update_predictions.py          ← orchestrateur (lancé par GH Actions)
├── data/
│   └── predictions.json               ← généré toutes les 6h
└── site/                              ← frontend (GitHub Pages)
    ├── index.html
    ├── style.css
    └── app.js
```

## Rappel important sur la performance

Le combo multiplie les probabilités, jamais les certitudes :

| Précision par pick | Probabilité combo 4/4 |
|---|---|
| 65% | 18% |
| 70% | 24% |
| 75% | 32% |
| 80% | 41% |

Le site affiche honnêtement la probabilité combinée et la cote juste
correspondante. Sur le tier gratuit, l'algo a typiquement **70-78% de
précision par sélection individuelle**, ce qui donne **25-40% de combos 4/4
gagnants**. Sur la durée, ça reste très inférieur à la "garantie" que les
sites de tipsters promettent — mais c'est honnête.

## Limites connues

- **Pas de gestion blessures/suspensions** : compositions probables non prises
  en compte. Pour ça il faut un scraper Sofascore/Whoscored.
- **Pas de cotes réelles** : les cotes affichées sont des "cotes justes"
  (1/prob), donc sans la marge bookmaker. Pour identifier les paris à valeur
  (+EV) il faudrait connecter une API de cotes (The Odds API, Pinnacle…).
- **Mapping d'équipes imparfait** : 111 équipes mappées manuellement, le
  fallback fuzzy attrape la plupart du reste mais peut rater une équipe peu
  connue. Ajoute-la dans `algo/team_mapping.py` si besoin.
- **GH Actions free tier** : 2000 min/mois, on en consomme ~4×30=120/mois,
  très large.

## Améliorer

Idées dans l'ordre de rentabilité :

1. **Calibration isotonique** sur backtest : aligner les probas prédites sur
   les fréquences observées (souvent on est trop "confiant").
2. **API de cotes** : afficher cote book vs cote juste, mettre en évidence
   les paris +EV.
3. **Compositions probables** : intégrer présence/absence des stars (Haaland,
   Mbappé, Vinicius…). Impact ~5-10% sur les probas.
4. **xG par tir** au lieu de buts marqués : StatsBomb Open Data ou Understat
   scraping.
5. **Stockage historique** : garder les prédictions des jours passés et leur
   issue, afficher un track-record en bas de page.

## Crédits

- Données historiques : [football-data.co.uk](https://www.football-data.co.uk)
- Fixtures temps réel : [football-data.org](https://www.football-data.org)
- Modèle statistique : Dixon, M.J. & Coles, S.G. (1997). *Modelling
  Association Football Scores and Inefficiencies in the Football Betting
  Market*.
