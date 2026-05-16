"""
Téléchargement et nettoyage des données football-data.co.uk
- Source gratuite et fiable avec cotes historiques.
- Couvre les 5 ligues sur de nombreuses saisons.
"""
from __future__ import annotations

import os
import urllib.request
from datetime import datetime
from typing import List, Optional

import pandas as pd

from config import LEAGUES, BASE_URL


def season_str(year_start: int) -> str:
    """Convertit 2024 -> '2425'."""
    return f"{year_start % 100:02d}{(year_start + 1) % 100:02d}"


def download_season(league_code: str, year_start: int, cache_dir: str = "data") -> Optional[str]:
    """Télécharge le CSV d'une ligue-saison si pas déjà en cache."""
    os.makedirs(cache_dir, exist_ok=True)
    season = season_str(year_start)
    filepath = os.path.join(cache_dir, f"{league_code}_{season}.csv")
    url = f"{BASE_URL}/{season}/{league_code}.csv"

    if not os.path.exists(filepath):
        try:
            print(f"   📥 {LEAGUES[league_code]['name']} {season} ...", end="", flush=True)
            urllib.request.urlretrieve(url, filepath)
            print(" ok")
        except Exception as e:
            print(f" échec ({e})")
            return None
    return filepath


def load_matches(
    leagues: Optional[List[str]] = None,
    seasons: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Charge tous les CSV en un seul DataFrame propre.
    Colonnes finales: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, League, SeasonStart
    + cotes Bet365 si disponibles.
    """
    if leagues is None:
        leagues = list(LEAGUES.keys())

    if seasons is None:
        now = datetime.now()
        # Une saison commence en juillet/août : si on est avant juillet, la saison
        # en cours est l'année précédente.
        current_season = now.year if now.month >= 7 else now.year - 1
        seasons = list(range(current_season - 2, current_season + 1))

    frames = []
    for lg in leagues:
        for yr in seasons:
            fp = download_season(lg, yr)
            if fp is None or not os.path.exists(fp):
                continue
            try:
                df = pd.read_csv(fp, encoding="latin-1")
            except Exception as e:
                print(f"   ⚠️  lecture {fp} échouée: {e}")
                continue
            df["League"] = lg
            df["SeasonStart"] = yr
            frames.append(df)

    if not frames:
        raise RuntimeError("Aucune donnée chargée. Vérifie ta connexion internet.")

    raw = pd.concat(frames, ignore_index=True, sort=False)

    keep = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
            "League", "SeasonStart"]
    odds_cols = ["B365H", "B365D", "B365A", "B365>2.5", "B365<2.5"]
    keep += [c for c in odds_cols if c in raw.columns]

    df = raw[[c for c in keep if c in raw.columns]].copy()
    df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG"])

    # Parse date, plusieurs formats possibles selon les saisons
    df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    mask = df["Date"].isna()
    if mask.any():
        df.loc[mask, "Date"] = pd.to_datetime(
            raw.loc[mask, "Date"] if "Date" in raw.columns else None,
            format="%d/%m/%y",
            errors="coerce",
        )

    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    df["FTHG"] = df["FTHG"].astype(int)
    df["FTAG"] = df["FTAG"].astype(int)
    return df
