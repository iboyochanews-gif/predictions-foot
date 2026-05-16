"""
Ensemble pondéré : Dixon-Coles (1X2, BTTS, O/U) + Elo (1X2) + signal de forme (1X2).
Les marchés "buts" (BTTS / Over-Under) viennent intégralement du modèle Poisson DC,
car Elo n'a pas vocation à les estimer.
"""
from __future__ import annotations

import numpy as np

from config import WEIGHT_DIXON_COLES, WEIGHT_ELO, WEIGHT_FORM
from dixon_coles import DixonColesModel
from elo import EloRatings


class EnsembleModel:
    def __init__(self, dc: DixonColesModel, elo: EloRatings):
        self.dc = dc
        self.elo = elo

    @staticmethod
    def _form_to_1x2(signal: float) -> dict[str, float]:
        """Translate un signal ∈ [-1, +1] en une distribution 1X2 approximative."""
        p_home = 0.45 + 0.20 * signal
        p_away = 0.30 - 0.15 * signal
        p_draw = 1.0 - p_home - p_away
        p_draw = max(0.10, p_draw)
        s = p_home + p_draw + p_away
        return {"home_win": p_home / s, "draw": p_draw / s, "away_win": p_away / s}

    def predict(self, home: str, away: str, form_signal: float = 0.0) -> dict[str, float]:
        dc = self.dc.predict(home, away)
        el = self.elo.predict(home, away)
        fm = self._form_to_1x2(form_signal)

        w_dc, w_el, w_fm = WEIGHT_DIXON_COLES, WEIGHT_ELO, WEIGHT_FORM
        total = w_dc + w_el + w_fm

        p_home = (w_dc * dc["home_win"] + w_el * el["home_win"] + w_fm * fm["home_win"]) / total
        p_draw = (w_dc * dc["draw"]     + w_el * el["draw"]     + w_fm * fm["draw"])     / total
        p_away = (w_dc * dc["away_win"] + w_el * el["away_win"] + w_fm * fm["away_win"]) / total

        s = p_home + p_draw + p_away
        p_home, p_draw, p_away = p_home / s, p_draw / s, p_away / s

        return {
            "home_win":  p_home,
            "draw":      p_draw,
            "away_win":  p_away,
            "btts_yes":  dc["btts_yes"],
            "btts_no":   dc["btts_no"],
            "over_2.5":  dc["over_2.5"],
            "under_2.5": dc["under_2.5"],
            "over_1.5":  dc["over_1.5"],
            "under_1.5": dc["under_1.5"],
            "xg_home":   dc["xg_home"],
            "xg_away":   dc["xg_away"],
        }
