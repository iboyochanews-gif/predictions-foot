"""
Ratings Elo adaptés au football :
- avantage domicile additif
- multiplicateur d'écart de buts (style FIFA Elo)
- conversion en 1X2 avec probabilité de nul dépendante de la proximité des ratings
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from config import ELO_INITIAL, ELO_K, ELO_HOME_ADVANTAGE


class EloRatings:
    def __init__(self, k: float = ELO_K, home_adv: float = ELO_HOME_ADVANTAGE,
                 initial: float = ELO_INITIAL):
        self.k = k
        self.home_adv = home_adv
        self.initial = initial
        self.ratings: dict[str, float] = defaultdict(lambda: initial)

    @staticmethod
    def _expected(r_a: float, r_b: float) -> float:
        return 1.0 / (1 + 10 ** ((r_b - r_a) / 400))

    def update(self, home: str, away: str, fthg: int, ftag: int) -> None:
        r_h = self.ratings[home]
        r_a = self.ratings[away]
        exp_h = self._expected(r_h + self.home_adv, r_a)

        if fthg > ftag:
            actual_h = 1.0
        elif fthg < ftag:
            actual_h = 0.0
        else:
            actual_h = 0.5

        # Multiplicateur d'écart de buts (FIFA / clubelo style)
        gd = abs(fthg - ftag)
        if gd <= 1:
            mult = 1.0
        elif gd == 2:
            mult = 1.5
        else:
            mult = (11 + gd) / 8.0

        delta = self.k * mult * (actual_h - exp_h)
        self.ratings[home] = r_h + delta
        self.ratings[away] = r_a - delta

    def fit(self, matches: pd.DataFrame) -> "EloRatings":
        """Parcours chronologique de toutes les rencontres pour stabiliser les ratings."""
        for _, row in matches.iterrows():
            self.update(row["HomeTeam"], row["AwayTeam"],
                        int(row["FTHG"]), int(row["FTAG"]))
        return self

    def predict(self, home: str, away: str) -> dict[str, float]:
        r_h = self.ratings[home]
        r_a = self.ratings[away]
        p_home_2way = self._expected(r_h + self.home_adv, r_a)

        # Probabilité de nul empirique : plus les ratings sont proches, plus le nul est fréquent.
        diff = abs(r_h + self.home_adv - r_a)
        p_draw = 0.30 * float(np.exp(-(diff ** 2) / (2 * 150 ** 2)))
        p_draw = min(max(p_draw, 0.10), 0.32)

        p_home = p_home_2way * (1 - p_draw)
        p_away = (1 - p_home_2way) * (1 - p_draw)
        return {"home_win": p_home, "draw": p_draw, "away_win": p_away}
