#!/usr/bin/env python3
"""
Contract test: fetch one event and assert minimum required API response keys.
Exits 0 if contract holds, 1 otherwise. Use before big runs or in CI.
Usage:
  python scripts/check_api_contract.py
  python scripts/check_api_contract.py --event-id 14083327
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import API_BASE

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}

# One known live-ish event ID (LaLiga); override with --event-id
DEFAULT_EVENT_ID = "14083327"


def check_event(data: dict) -> list[str]:
    errs = []
    inner = data.get("event") or data
    if not isinstance(inner, dict):
        errs.append("event: root or event must be a dict")
        return errs
    if not (inner.get("tournament") or inner.get("uniqueTournament")):
        errs.append("event: missing tournament or uniqueTournament")
    if inner.get("startTimestamp") is None:
        errs.append("event: missing startTimestamp")
    for key in ("homeTeam", "awayTeam"):
        if not (inner.get(key) and isinstance(inner[key], dict)):
            errs.append(f"event: missing or invalid {key}")
    return errs


def check_lineups(data: dict) -> list[str]:
    errs = []
    if not isinstance(data, dict):
        errs.append("lineups: root must be a dict")
        return errs
    has_home = "home" in data and isinstance(data["home"], dict)
    has_away = "away" in data and isinstance(data["away"], dict)
    if not (has_home or "homeTeam" in data):
        errs.append("lineups: missing home / homeTeam")
    if not (has_away or "awayTeam" in data):
        errs.append("lineups: missing away / awayTeam")
    return errs


def check_incidents(data: dict) -> list[str]:
    if not isinstance(data, dict):
        return ["incidents: root must be a dict"]
    if "incidents" not in data:
        return ["incidents: missing 'incidents' key"]
    if not isinstance(data["incidents"], list):
        return ["incidents: 'incidents' must be a list"]
    return []


def main():
    ap = argparse.ArgumentParser(description="Check Sofascore API response contract")
    ap.add_argument("--event-id", default=DEFAULT_EVENT_ID, help="Event ID to fetch")
    args = ap.parse_args()

    event_id = args.event_id
    base = API_BASE.rstrip("/")
    all_errors = []

    # Event
    r = requests.get(f"{base}/event/{event_id}", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        all_errors.append(f"GET /event/{event_id} returned {r.status_code}")
    else:
        try:
            data = r.json()
            all_errors.extend(check_event(data))
        except Exception as e:
            all_errors.append(f"event parse: {e}")

    # Lineups
    r = requests.get(f"{base}/event/{event_id}/lineups", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        all_errors.append(f"GET /event/{{id}}/lineups returned {r.status_code}")
    else:
        try:
            data = r.json()
            all_errors.extend(check_lineups(data))
        except Exception as e:
            all_errors.append(f"lineups parse: {e}")

    # Incidents
    r = requests.get(f"{base}/event/{event_id}/incidents", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        all_errors.append(f"GET /event/{{id}}/incidents returned {r.status_code}")
    else:
        try:
            data = r.json()
            all_errors.extend(check_incidents(data))
        except Exception as e:
            all_errors.append(f"incidents parse: {e}")

    if all_errors:
        print("API contract check FAILED:", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print("API contract check passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
