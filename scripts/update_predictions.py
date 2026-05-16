"""
Script principal : génère data/predictions.json à partir des modèles
entraînés sur l'historique et des fixtures à venir.

Lancé toutes les 6 heures par GitHub Actions.

Usage :
    FOOTBALL_DATA_API_KEY=xxxxx python scripts/update_predictions.py

Variables d'env optionnelles :
    SEASONS_BACK   nb de saisons d'entraînement (défaut: 3)
    LOOKAHEAD_DAYS combien de jours à prédire (défaut: 3)
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ajoute le répertoire racine du projet au path pour importer le package algo
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "algo"))

from combo_builder import build_combo, analyze_match
from config import COMBO_SIZE, LEAGUES, MIN_CONFIDENCE
from data_loader import load_matches
from dixon_coles import DixonColesModel
from elo import EloRatings
from ensemble import EnsembleModel
from features import compute_team_form, form_signal
from fixtures_fetcher import fetch_fixtures
from team_mapping import map_team


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    seasons_back = int(os.environ.get("SEASONS_BACK", 3))
    lookahead = int(os.environ.get("LOOKAHEAD_DAYS", 3))
    output_path = ROOT / "data" / "predictions.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    next_update = now + timedelta(hours=6)

    print(f"[{iso_now()}] Démarrage de la génération des prédictions")

    # --- 1. Charger les données historiques --------------------------------
    current_season = now.year if now.month >= 7 else now.year - 1
    seasons = list(range(current_season - seasons_back + 1, current_season + 1))
    print(f"   Saisons : {seasons}")

    try:
        matches = load_matches(seasons=seasons)
    except RuntimeError as e:
        _write_error(output_path, str(e), now, next_update)
        sys.exit(1)

    print(f"   {len(matches)} matchs historiques chargés")

    # --- 2. Entraîner les modèles ------------------------------------------
    reference_date = matches["Date"].max()
    print(f"   Entraînement Dixon-Coles (réf. {reference_date.date()})...")
    dc = DixonColesModel().fit(matches, reference_date=reference_date)
    print(f"   Entraînement Elo...")
    elo = EloRatings().fit(matches)
    model = EnsembleModel(dc, elo)
    form_map = compute_team_form(matches)
    training_teams = sorted(set(matches["HomeTeam"]) | set(matches["AwayTeam"]))

    # --- 3. Récupérer les fixtures -----------------------------------------
    try:
        print(f"   Récupération fixtures (lookahead {lookahead}j)...")
        fixtures = fetch_fixtures(
            date_from=now,
            date_to=now + timedelta(days=lookahead),
        )
    except RuntimeError as e:
        _write_error(output_path, str(e), now, next_update)
        sys.exit(1)
    except Exception as e:
        _write_error(output_path, f"Erreur fixtures : {e}", now, next_update)
        sys.exit(1)

    print(f"   {len(fixtures)} fixtures récupérées")

    # --- 4. Mapper les noms d'équipes et regrouper par jour -----------------
    by_day: dict[str, list[dict]] = defaultdict(list)
    unmatched: list[tuple[str, str]] = []

    for fx in fixtures:
        home = map_team(fx["home_raw"], training_teams)
        away = map_team(fx["away_raw"], training_teams)
        if home is None or away is None:
            unmatched.append((fx["home_raw"], fx["away_raw"]))
            continue
        kickoff = datetime.fromisoformat(fx["kickoff"].replace("Z", "+00:00"))
        day_key = kickoff.date().isoformat()
        by_day[day_key].append({
            "home": home,
            "away": away,
            "league": fx["league"],
            "kickoff": fx["kickoff"],
        })

    if unmatched:
        print(f"   ⚠️  {len(unmatched)} matchs non mappés :")
        for h, a in unmatched[:5]:
            print(f"       · {h} vs {a}")

    # --- 5. Pour chaque jour, générer analyses + combo ---------------------
    days_output = []
    today_str = now.date().isoformat()

    for day_key in sorted(by_day.keys()):
        day_fixtures = by_day[day_key]
        fixtures_list = [(f["home"], f["away"], f["league"]) for f in day_fixtures]
        signals = [form_signal(form_map, h, a) for h, a, _ in fixtures_list]

        analyses_payload = []
        for (h, a, lg), fx, sig in zip(fixtures_list, day_fixtures, signals):
            analysis = analyze_match(h, a, lg, model, sig)
            best = analysis["picks"][0]
            analyses_payload.append({
                "home": h, "away": a,
                "league": lg,
                "league_name": LEAGUES[lg]["name"],
                "kickoff": fx["kickoff"],
                "xg": [round(analysis["xg_home"], 2), round(analysis["xg_away"], 2)],
                "best_pick": {
                    "market": best["market"],
                    "selection": best["selection"],
                    "probability": round(best["prob"], 4),
                    "fair_odds": round(best["fair_odds"], 2),
                },
                "top_markets": [
                    {
                        "market": p["market"],
                        "selection": p["selection"],
                        "probability": round(p["prob"], 4),
                        "fair_odds": round(p["fair_odds"], 2),
                    } for p in analysis["picks"][:6]
                ],
            })

        result = build_combo(fixtures_list, model, signals)
        combo_payload = None
        if result["combo"]:
            combo_payload = {
                "available": True,
                "joint_probability": round(result["joint_probability"], 4),
                "fair_combined_odds": round(result["fair_combined_odds"], 2),
                "picks": [
                    {
                        "match": p["match"],
                        "league_name": p["league_name"],
                        "market": p["market"],
                        "selection": p["selection"],
                        "probability": round(p["prob"], 4),
                        "fair_odds": round(p["fair_odds"], 2),
                        "xg": p["xg"],
                    } for p in result["combo"]
                ],
            }
        else:
            combo_payload = {"available": False, "reason": result.get("reason")}

        days_output.append({
            "date": day_key,
            "is_today": day_key == today_str,
            "fixtures_count": len(day_fixtures),
            "fixtures": analyses_payload,
            "combo": combo_payload,
        })

    # --- 6. Sérialiser ------------------------------------------------------
    payload = {
        "meta": {
            "generated_at": iso_now(),
            "next_update_at": next_update.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "training": {
                "n_matches": len(matches),
                "date_range": f"{matches['Date'].min().date()} → {matches['Date'].max().date()}",
                "n_teams": len(training_teams),
            },
            "model": "Dixon-Coles + Elo + Forme récente (ensemble pondéré)",
            "params": {
                "min_confidence": MIN_CONFIDENCE,
                "combo_size": COMBO_SIZE,
                "dixon_coles_home_adv": round(dc.home_adv, 3),
                "dixon_coles_rho": round(dc.rho, 3),
            },
            "status": "ok",
        },
        "days": days_output,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[{iso_now()}] ✓ Écrit {output_path}")
    print(f"   {len(days_output)} jours avec fixtures, "
          f"{sum(1 for d in days_output if d['combo']['available'])} combo(s) disponibles")


def _write_error(output_path: Path, message: str, now: datetime, next_update: datetime):
    payload = {
        "meta": {
            "generated_at": iso_now(),
            "next_update_at": next_update.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "error",
            "error_message": message,
        },
        "days": [],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"❌ {message}")


if __name__ == "__main__":
    main()
