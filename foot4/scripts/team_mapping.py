"""
Mapping des noms d'équipes entre football-data.org (API fixtures) et
football-data.co.uk (données historiques utilisées pour l'entraînement).

Les deux sources nomment différemment les équipes :
  API : "Manchester United FC", "Bayer 04 Leverkusen"
  CSV : "Man United", "Leverkusen"

En cas de manque, on tombe sur un matching flou via difflib.
"""
from __future__ import annotations

import unicodedata
from difflib import get_close_matches

# Correspondances manuelles pour les équipes des 5 grandes ligues
MANUAL_MAPPING: dict[str, str] = {
    # Premier League
    "Manchester United FC":       "Man United",
    "Manchester City FC":         "Man City",
    "Tottenham Hotspur FC":       "Tottenham",
    "Brighton & Hove Albion FC":  "Brighton",
    "Wolverhampton Wanderers FC": "Wolves",
    "Nottingham Forest FC":       "Nott'm Forest",
    "Newcastle United FC":        "Newcastle",
    "AFC Bournemouth":            "Bournemouth",
    "West Ham United FC":         "West Ham",
    "Aston Villa FC":             "Aston Villa",
    "Crystal Palace FC":          "Crystal Palace",
    "Liverpool FC":               "Liverpool",
    "Arsenal FC":                 "Arsenal",
    "Chelsea FC":                 "Chelsea",
    "Everton FC":                 "Everton",
    "Brentford FC":               "Brentford",
    "Fulham FC":                  "Fulham",
    "Leicester City FC":          "Leicester",
    "Ipswich Town FC":            "Ipswich",
    "Southampton FC":             "Southampton",
    "Leeds United FC":            "Leeds",
    "Burnley FC":                 "Burnley",
    "Sunderland AFC":             "Sunderland",
    # La Liga
    "Club Atlético de Madrid":    "Ath Madrid",
    "Atlético de Madrid":         "Ath Madrid",
    "Athletic Club":              "Ath Bilbao",
    "Real Madrid CF":             "Real Madrid",
    "FC Barcelona":               "Barcelona",
    "Sevilla FC":                 "Sevilla",
    "Real Sociedad de Fútbol":    "Sociedad",
    "Real Betis Balompié":        "Betis",
    "Valencia CF":                "Valencia",
    "Real Valladolid CF":         "Valladolid",
    "Deportivo Alavés":           "Alaves",
    "RCD Espanyol de Barcelona":  "Espanol",
    "RCD Mallorca":               "Mallorca",
    "RC Celta de Vigo":           "Celta",
    "Rayo Vallecano de Madrid":   "Vallecano",
    "Real Oviedo":                "Oviedo",
    "Villarreal CF":              "Villarreal",
    "Getafe CF":                  "Getafe",
    "CA Osasuna":                 "Osasuna",
    "Girona FC":                  "Girona",
    "UD Las Palmas":              "Las Palmas",
    "Elche CF":                   "Elche",
    "Levante UD":                 "Levante",
    "RCD Mallorca":               "Mallorca",
    # Serie A
    "FC Internazionale Milano":   "Inter",
    "AC Milan":                   "Milan",
    "Juventus FC":                "Juventus",
    "AS Roma":                    "Roma",
    "SS Lazio":                   "Lazio",
    "SSC Napoli":                 "Napoli",
    "Atalanta BC":                "Atalanta",
    "Bologna FC 1909":            "Bologna",
    "Hellas Verona FC":           "Verona",
    "ACF Fiorentina":             "Fiorentina",
    "Udinese Calcio":             "Udinese",
    "Torino FC":                  "Torino",
    "Empoli FC":                  "Empoli",
    "Genoa CFC":                  "Genoa",
    "Cagliari Calcio":            "Cagliari",
    "Como 1907":                  "Como",
    "Parma Calcio 1913":          "Parma",
    "US Lecce":                   "Lecce",
    "Venezia FC":                 "Venezia",
    "AC Monza":                   "Monza",
    "US Sassuolo Calcio":         "Sassuolo",
    "US Cremonese":               "Cremonese",
    "Pisa Sporting Club":         "Pisa",
    # Bundesliga
    "FC Bayern München":          "Bayern Munich",
    "Borussia Dortmund":          "Dortmund",
    "Bayer 04 Leverkusen":        "Leverkusen",
    "RB Leipzig":                 "RB Leipzig",
    "Eintracht Frankfurt":        "Ein Frankfurt",
    "VfL Wolfsburg":              "Wolfsburg",
    "Borussia Mönchengladbach":   "M'gladbach",
    "VfB Stuttgart":              "Stuttgart",
    "SC Freiburg":                "Freiburg",
    "1. FC Heidenheim 1846":      "Heidenheim",
    "FC Augsburg":                "Augsburg",
    "TSG 1899 Hoffenheim":        "Hoffenheim",
    "SV Werder Bremen":           "Werder Bremen",
    "FC St. Pauli 1910":          "St Pauli",
    "1. FSV Mainz 05":            "Mainz",
    "1. FC Union Berlin":         "Union Berlin",
    "Holstein Kiel":              "Holstein Kiel",
    "VfL Bochum 1848":            "Bochum",
    "1. FC Köln":                 "FC Koln",
    "Hamburger SV":               "Hamburg",
    "FC Schalke 04":              "Schalke 04",
    # Ligue 1
    "Paris Saint-Germain FC":     "Paris SG",
    "Olympique de Marseille":     "Marseille",
    "Olympique Lyonnais":         "Lyon",
    "OGC Nice":                   "Nice",
    "AS Monaco FC":               "Monaco",
    "RC Lens":                    "Lens",
    "LOSC Lille":                 "Lille",
    "Stade Rennais FC 1901":      "Rennes",
    "Toulouse FC":                "Toulouse",
    "FC Nantes":                  "Nantes",
    "Stade Brestois 29":          "Brest",
    "Montpellier HSC":            "Montpellier",
    "RC Strasbourg Alsace":       "Strasbourg",
    "AJ Auxerre":                 "Auxerre",
    "Angers SCO":                 "Angers",
    "Stade de Reims":             "Reims",
    "AS Saint-Étienne":           "St Etienne",
    "Le Havre AC":                "Le Havre",
    "FC Lorient":                 "Lorient",
    "Paris FC":                   "Paris FC",
    "FC Metz":                    "Metz",
}


def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def _normalize(name: str) -> str:
    """Light normalization for fuzzy matching: lowercase, no accents, no suffixes."""
    n = _strip_accents(name).lower()
    for suffix in [" fc", " cf", " ac", " sc", " bc", " calcio", " 1909", " 1907",
                   " 1913", " 1910", " 1848", " 1846", " 04", " 05", " 1899",
                   "1. ", " e.v.", " ag", " sad", " s.a.d."]:
        n = n.replace(suffix, "")
    return " ".join(n.split())


def map_team(api_name: str, training_teams: list[str]) -> str | None:
    """
    Convert a name returned by football-data.org into the name used in the
    training set. Returns None if no satisfactory match.
    """
    # 1. Manual override
    if api_name in MANUAL_MAPPING and MANUAL_MAPPING[api_name] in training_teams:
        return MANUAL_MAPPING[api_name]

    # 2. Exact match
    if api_name in training_teams:
        return api_name

    # 3. Fuzzy match on normalized strings
    norm_api = _normalize(api_name)
    norm_map = {_normalize(t): t for t in training_teams}

    if norm_api in norm_map:
        return norm_map[norm_api]

    candidates = get_close_matches(norm_api, list(norm_map.keys()), n=1, cutoff=0.70)
    if candidates:
        return norm_map[candidates[0]]
    return None
