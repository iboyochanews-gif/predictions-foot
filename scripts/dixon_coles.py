"""
Modèle Dixon-Coles (1997) — référence académique pour la prédiction football.

Idée: chaque équipe a une force d'attaque α et une force de défense β.
- λ (buts attendus à domicile) = exp(α_home + β_away + γ)   avec γ = avantage domicile
- μ (buts attendus à l'extérieur) = exp(α_away + β_home)
Les scores suivent deux Poisson (presque) indépendants, avec une correction τ
pour rétablir la corrélation observée sur les petits scores (0-0, 1-0, 0-1, 1-1).

Référence : Dixon, M.J. & Coles, S.G. (1997). "Modelling Association Football
Scores and Inefficiencies in the Football Betting Market".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from config import DC_TIME_DECAY, DC_MAX_GOALS


def dc_correction(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Correction Dixon-Coles pour scores faibles."""
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


class DixonColesModel:
    def __init__(self):
        self.attack: dict[str, float] = {}
        self.defense: dict[str, float] = {}
        self.home_adv: float = 0.25
        self.rho: float = -0.10
        self.teams: list[str] = []

    # ------------------------------------------------------------------ FIT
    def fit(self, matches: pd.DataFrame, reference_date=None) -> "DixonColesModel":
        if reference_date is None:
            reference_date = matches["Date"].max()

        teams = sorted(set(matches["HomeTeam"]) | set(matches["AwayTeam"]))
        self.teams = teams
        n = len(teams)
        team_idx = {t: i for i, t in enumerate(teams)}

        # Pré-extraction en arrays NumPy (≫ rapide qu'un boucle pandas)
        h_idx = matches["HomeTeam"].map(team_idx).to_numpy()
        a_idx = matches["AwayTeam"].map(team_idx).to_numpy()
        fthg = matches["FTHG"].to_numpy(dtype=int)
        ftag = matches["FTAG"].to_numpy(dtype=int)
        days_ago = (reference_date - matches["Date"]).dt.days.to_numpy()
        weights = np.exp(-DC_TIME_DECAY * days_ago)

        def neg_log_likelihood(params):
            attack = params[:n]
            defense = params[n:2 * n]
            home_adv = params[2 * n]
            rho = params[2 * n + 1]

            lam = np.exp(attack[h_idx] + defense[a_idx] + home_adv)
            mu = np.exp(attack[a_idx] + defense[h_idx])

            log_p = poisson.logpmf(fthg, lam) + poisson.logpmf(ftag, mu)

            # Correction Dixon-Coles (vectorisée, ne s'applique qu'aux scores ≤1)
            tau = np.ones_like(lam)
            m_00 = (fthg == 0) & (ftag == 0)
            m_01 = (fthg == 0) & (ftag == 1)
            m_10 = (fthg == 1) & (ftag == 0)
            m_11 = (fthg == 1) & (ftag == 1)
            tau = np.where(m_00, 1 - lam * mu * rho, tau)
            tau = np.where(m_01, 1 + lam * rho, tau)
            tau = np.where(m_10, 1 + mu * rho, tau)
            tau = np.where(m_11, 1 - rho, tau)
            tau = np.clip(tau, 1e-10, None)

            log_p = log_p + np.log(tau)
            ll = (weights * log_p).sum()

            # Pénalité pour identifiabilité (moyenne des α et β centrée)
            penalty = 100.0 * (attack.mean() ** 2 + defense.mean() ** 2)
            return -ll + penalty

        x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25], [-0.10]])
        bounds = ([(-3, 3)] * n + [(-3, 3)] * n + [(-1, 1), (-0.2, 0.2)])

        result = minimize(neg_log_likelihood, x0, method="L-BFGS-B",
                          bounds=bounds,
                          options={"maxiter": 300, "ftol": 1e-7})

        p = result.x
        self.attack = dict(zip(teams, p[:n]))
        self.defense = dict(zip(teams, p[n:2 * n]))
        self.home_adv = float(p[2 * n])
        self.rho = float(p[2 * n + 1])
        return self

    # --------------------------------------------------------------- PREDICT
    def _lambdas(self, home: str, away: str) -> tuple[float, float]:
        a_h = self.attack.get(home, 0.0)
        d_h = self.defense.get(home, 0.0)
        a_a = self.attack.get(away, 0.0)
        d_a = self.defense.get(away, 0.0)
        lam = float(np.exp(a_h + d_a + self.home_adv))
        mu = float(np.exp(a_a + d_h))
        return lam, mu

    def score_matrix(self, home: str, away: str, max_goals: int = DC_MAX_GOALS) -> np.ndarray:
        lam, mu = self._lambdas(home, away)
        x = np.arange(max_goals + 1)
        p_h = poisson.pmf(x, lam)
        p_a = poisson.pmf(x, mu)
        M = np.outer(p_h, p_a)
        # Correction sur la grille 2x2
        M[0, 0] *= 1 - lam * mu * self.rho
        M[0, 1] *= 1 + lam * self.rho
        M[1, 0] *= 1 + mu * self.rho
        M[1, 1] *= 1 - self.rho
        M = np.maximum(M, 0)
        M /= M.sum()
        return M

    def predict(self, home: str, away: str) -> dict[str, float]:
        """Renvoie les probabilités des marchés principaux."""
        M = self.score_matrix(home, away)
        p_home = float(np.tril(M, -1).sum())
        p_draw = float(np.trace(M))
        p_away = float(np.triu(M, 1).sum())

        p_btts_yes = float(M[1:, 1:].sum())
        p_btts_no = 1.0 - p_btts_yes

        n = M.shape[0]
        ii, jj = np.indices((n, n))
        p_over_25 = float(M[(ii + jj) >= 3].sum())
        p_under_25 = 1.0 - p_over_25
        p_over_15 = float(M[(ii + jj) >= 2].sum())
        p_under_15 = 1.0 - p_over_15

        # Buts attendus (xG implicite du modèle)
        lam, mu = self._lambdas(home, away)

        return {
            "home_win":  p_home,
            "draw":      p_draw,
            "away_win":  p_away,
            "btts_yes":  p_btts_yes,
            "btts_no":   p_btts_no,
            "over_2.5":  p_over_25,
            "under_2.5": p_under_25,
            "over_1.5":  p_over_15,
            "under_1.5": p_under_15,
            "xg_home":   lam,
            "xg_away":   mu,
        }
