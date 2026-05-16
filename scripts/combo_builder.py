"""
Construction du combo quotidien :
  1. Pour chaque match du jour, on génère toutes les sélections candidates
     (1, X, 2, 1X, X2, 12, BTTS Oui/Non, +1.5, -1.5, +2.5, -2.5).
  2. On garde, par match, la meilleure sélection qui dépasse MIN_CONFIDENCE.
  3. On prend les COMBO_SIZE matchs avec les probabilités les plus élevées.

Note importante:
  Le combo multiplie les probabilités → un combo 4 picks à 75% chacun =
  ~31.6% de succès. Le but est donc d'identifier les MEILLEURS picks possibles
  d'une journée, pas de garantir un combo gagnant.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from config import COMBO_SIZE, LEAGUES, MIN_CONFIDENCE
from ensemble import EnsembleModel


def candidate_picks(probs: dict[str, float], home: str, away: str) -> list[dict]:
    """À partir de toutes les probabilités d'un match, génère les sélections."""
    p = probs
    picks = [
        {"market": "1",       "selection": f"Victoire {home}",      "prob": p["home_win"]},
        {"market": "X",       "selection": "Match nul",             "prob": p["draw"]},
        {"market": "2",       "selection": f"Victoire {away}",      "prob": p["away_win"]},
        {"market": "1X",      "selection": f"{home} ou nul",        "prob": p["home_win"] + p["draw"]},
        {"market": "X2",      "selection": f"{away} ou nul",        "prob": p["draw"] + p["away_win"]},
        {"market": "12",      "selection": "Pas de nul",            "prob": p["home_win"] + p["away_win"]},
        {"market": "BTTS Oui","selection": "Les deux marquent",     "prob": p["btts_yes"]},
        {"market": "BTTS Non","selection": "Au moins un clean sheet","prob": p["btts_no"]},
        {"market": "+1.5",    "selection": "2 buts ou plus",        "prob": p["over_1.5"]},
        {"market": "-1.5",    "selection": "Moins de 2 buts",       "prob": p["under_1.5"]},
        {"market": "+2.5",    "selection": "3 buts ou plus",        "prob": p["over_2.5"]},
        {"market": "-2.5",    "selection": "Moins de 3 buts",       "prob": p["under_2.5"]},
    ]
    for pick in picks:
        pick["fair_odds"] = round(1.0 / pick["prob"], 2) if pick["prob"] > 0 else float("inf")
    return picks


def analyze_match(home: str, away: str, league: str, model: EnsembleModel,
                  form_signal: float = 0.0) -> dict:
    probs = model.predict(home, away, form_signal)
    picks = candidate_picks(probs, home, away)
    picks.sort(key=lambda x: x["prob"], reverse=True)
    return {
        "home": home,
        "away": away,
        "league": league,
        "league_name": LEAGUES.get(league, {}).get("name", league),
        "xg_home": probs["xg_home"],
        "xg_away": probs["xg_away"],
        "picks": picks,
    }


def best_pick_above(picks: list[dict], threshold: float) -> Optional[dict]:
    """La meilleure sélection au-dessus du seuil de confiance."""
    eligibles = [p for p in picks if p["prob"] >= threshold]
    return max(eligibles, key=lambda x: x["prob"]) if eligibles else None


def build_combo(fixtures: list[tuple[str, str, str]],
                model: EnsembleModel,
                form_signals: Optional[list[float]] = None,
                combo_size: int = COMBO_SIZE,
                min_confidence: float = MIN_CONFIDENCE) -> dict:
    """
    fixtures: liste de (home, away, league_code)
    Renvoie un dict avec la sélection du combo + tous les candidats analysés.
    """
    if form_signals is None:
        form_signals = [0.0] * len(fixtures)

    analyses = []
    for (h, a, lg), fs in zip(fixtures, form_signals):
        analyses.append(analyze_match(h, a, lg, model, fs))

    # Meilleure sélection éligible par match
    candidates = []
    for m in analyses:
        best = best_pick_above(m["picks"], min_confidence)
        if best is None:
            continue
        candidates.append({
            **best,
            "match": f"{m['home']} vs {m['away']}",
            "league_name": m["league_name"],
            "xg": f"{m['xg_home']:.2f} – {m['xg_away']:.2f}",
        })

    # Tri par probabilité décroissante
    candidates.sort(key=lambda x: x["prob"], reverse=True)

    if len(candidates) < combo_size:
        return {
            "combo": None,
            "reason": f"Pas assez de sélections au-dessus de {min_confidence:.0%} de confiance "
                      f"({len(candidates)} disponibles, {combo_size} requises).",
            "all_candidates": candidates,
            "all_analyses": analyses,
        }

    combo = candidates[:combo_size]
    joint_prob = float(np.prod([c["prob"] for c in combo]))
    joint_odds = float(np.prod([c["fair_odds"] for c in combo]))

    return {
        "combo": combo,
        "joint_probability": joint_prob,
        "fair_combined_odds": joint_odds,
        "all_candidates": candidates,
        "all_analyses": analyses,
    }
