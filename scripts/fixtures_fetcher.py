"""
Récupération des matchs programmés via l'API gratuite football-data.org.

Pré-requis :
  - Créer un compte gratuit sur https://www.football-data.org/client/register
  - Récupérer le token dans le profil
  - L'exposer en variable d'environnement FOOTBALL_DATA_API_KEY

Limite : 10 requêtes/min sur le tier gratuit. On en fait 5 (une par ligue).
"""
from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
import json
from datetime import datetime, timedelta

API_BASE = "https://api.football-data.org/v4"

# football-data.org code  ->  football-data.co.uk code (interne au projet)
COMPETITION_MAP = {
    "PL":  "E0",   # Premier League
    "PD":  "SP1",  # La Liga
    "SA":  "I1",   # Serie A
    "BL1": "D1",   # Bundesliga
    "FL1": "F1",   # Ligue 1
}


def _api_request(path: str, params: dict, api_key: str, timeout: int = 15) -> dict:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{API_BASE}{path}?{query}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": api_key})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_fixtures(api_key: str | None = None,
                   date_from: datetime | None = None,
                   date_to: datetime | None = None,
                   rate_limit_sleep: float = 7.0) -> list[dict]:
    """
    Renvoie une liste de fixtures programmées dans la fenêtre donnée.
    Format :
        { "league": "E0", "home_raw": "Liverpool FC", "away_raw": "Wolverhampton Wanderers FC",
          "kickoff": "2026-05-16T15:30:00Z", "status": "SCHEDULED", "fd_id": 12345 }
    """
    api_key = api_key or os.environ.get("FOOTBALL_DATA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FOOTBALL_DATA_API_KEY manquant. Crée un compte gratuit sur "
            "football-data.org puis exporte la variable d'environnement."
        )

    if date_from is None:
        date_from = datetime.utcnow()
    if date_to is None:
        date_to = date_from + timedelta(days=3)

    df_str = date_from.strftime("%Y-%m-%d")
    dt_str = date_to.strftime("%Y-%m-%d")

    fixtures: list[dict] = []
    for fd_code, internal in COMPETITION_MAP.items():
        try:
            data = _api_request(
                f"/competitions/{fd_code}/matches",
                {"dateFrom": df_str, "dateTo": dt_str},
                api_key,
            )
        except urllib.error.HTTPError as e:
            print(f"   ⚠️  API {fd_code} → {e.code} {e.reason}")
            continue
        except Exception as e:
            print(f"   ⚠️  API {fd_code} → {e}")
            continue

        for m in data.get("matches", []):
            if m.get("status") not in ("SCHEDULED", "TIMED"):
                continue
            fixtures.append({
                "league":    internal,
                "home_raw":  m["homeTeam"]["name"],
                "away_raw":  m["awayTeam"]["name"],
                "kickoff":   m["utcDate"],
                "status":    m["status"],
                "fd_id":     m["id"],
            })

        # Respect du quota free tier
        time.sleep(rate_limit_sleep)

    return fixtures
