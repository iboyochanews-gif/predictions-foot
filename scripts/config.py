"""
Configuration centrale de l'algorithme de pronostic.
Toutes les valeurs ajustables sont ici.
"""

# Les 5 ligues majeures avec leurs codes football-data.co.uk
LEAGUES = {
    "E0":  {"name": "Premier League", "country": "Angleterre"},
    "SP1": {"name": "La Liga",        "country": "Espagne"},
    "I1":  {"name": "Serie A",        "country": "Italie"},
    "D1":  {"name": "Bundesliga",     "country": "Allemagne"},
    "F1":  {"name": "Ligue 1",        "country": "France"},
}

BASE_URL = "https://www.football-data.co.uk/mmz4281"

# --- Dixon-Coles ---
# Décroissance temporelle : les matchs anciens comptent moins.
# 0.0065/jour ≈ demi-vie de 106 jours, recommandé par Dixon & Coles (1997)
DC_TIME_DECAY = 0.0065
DC_MAX_GOALS = 8     # grille de scores tronquée à 8-8

# --- Elo ---
ELO_INITIAL = 1500
ELO_K = 20           # taux d'apprentissage
ELO_HOME_ADVANTAGE = 65   # ≈ avantage typique d'un match domicile en foot

# --- Pondération de l'ensemble ---
WEIGHT_DIXON_COLES = 0.60
WEIGHT_ELO         = 0.25
WEIGHT_FORM        = 0.15

# --- Construction du combo ---
MIN_CONFIDENCE = 0.65   # proba minimum pour qu'une sélection soit éligible
COMBO_SIZE = 4
