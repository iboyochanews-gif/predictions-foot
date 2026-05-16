"""
Calcul du signal de forme récente d'une équipe (points/match et diff de buts/match
sur les N derniers matchs).
"""
from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
import pandas as pd


def compute_team_form(matches: pd.DataFrame, n_games: int = 5) -> dict[str, dict]:
    """
    Parcourt l'historique et renvoie, par équipe, le ppg et la diff de buts/match
    sur les N derniers matchs (à jour à la dernière date du DataFrame).
    """
    matches = matches.sort_values("Date")
    history: dict[str, deque] = defaultdict(lambda: deque(maxlen=n_games))

    for _, row in matches.iterrows():
        h_goals, a_goals = int(row["FTHG"]), int(row["FTAG"])
        if h_goals > a_goals:
            h_pts, a_pts = 3, 0
        elif h_goals < a_goals:
            h_pts, a_pts = 0, 3
        else:
            h_pts, a_pts = 1, 1

        history[row["HomeTeam"]].append({"points": h_pts, "gd": h_goals - a_goals})
        history[row["AwayTeam"]].append({"points": a_pts, "gd": a_goals - h_goals})

    out: dict[str, dict] = {}
    for team, recents in history.items():
        if not recents:
            out[team] = {"ppg": 1.0, "gd_per_game": 0.0, "n": 0}
            continue
        ppg = float(np.mean([m["points"] for m in recents]))
        gdpg = float(np.mean([m["gd"] for m in recents]))
        out[team] = {"ppg": ppg, "gd_per_game": gdpg, "n": len(recents)}
    return out


def form_signal(form_map: dict[str, dict], home: str, away: str) -> float:
    """
    Transforme la différence de forme en un signal ∈ [-1, +1]
    (positif = avantage domicile).
    """
    h = form_map.get(home, {"ppg": 1.0, "gd_per_game": 0.0})
    a = form_map.get(away, {"ppg": 1.0, "gd_per_game": 0.0})
    diff_ppg = h["ppg"] - a["ppg"]            # ∈ [-3, +3]
    diff_gd = h["gd_per_game"] - a["gd_per_game"]
    signal = 0.4 * (diff_ppg / 3.0) + 0.6 * (diff_gd / 3.0)
    return float(np.clip(signal, -1.0, 1.0))
