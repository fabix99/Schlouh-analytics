"""
Fetch Sofascore event + lineups + statistics + incidents + managers + graph; export to data/raw/.

Usage:
  python src/extract_match_lineups.py <match_id_or_url>
  python src/extract_match_lineups.py 14083327

Outputs in data/raw/:
  - lineups_{id}.csv       one row per player, all stats
  - team_statistics_{id}.csv  team stats (by period if available)
  - incidents_{id}.csv     goals, cards, substitutions
  - managers_{id}.json     manager info
  - graph_{id}.json        momentum / graph data
"""

import json
import os
import random
import re
import sys
import time
from typing import Optional, Tuple

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parent))

import pandas as pd
import requests

from config import API_BASE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}

# Retry on these statuses or timeout
RETRIABLE_STATUSES = {403, 429, 500, 502, 503, 504}
RETRY_DELAYS = [2, 5, 12]
MAX_RETRIES = 3


def _is_403_challenge(response: requests.Response) -> bool:
    if response.status_code != 403:
        return False
    try:
        data = response.json()
        err = (data or {}).get("error") or {}
        return err.get("code") == 403 and (err.get("reason") or "").lower() == "challenge"
    except Exception:
        return True


def _jitter(base_sec: float) -> float:
    return base_sec * (0.8 + 0.4 * random.random())


def fetch_json(url: str) -> dict:
    """One-shot fetch; raises on non-2xx. Prefer fetch_json_resilient for batch use."""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_json_resilient(url: str) -> Tuple[Optional[dict], Optional[str]]:
    """Fetch with retries and jitter. Returns (data, None) on success or (None, error_class) on failure.
    Retries on 403 challenge, 429, 5xx, timeout. Does not retry on 4xx (except 403/429)."""
    last_response = None
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            last_response = r
            if r.status_code == 200:
                return (r.json(), None)
            if r.status_code in RETRIABLE_STATUSES and attempt < MAX_RETRIES:
                if r.status_code == 403 and not _is_403_challenge(r):
                    last_error = "http_403"
                    break
                wait = _jitter(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                last_error = f"http_{r.status_code}"
                break
        except requests.exceptions.Timeout:
            last_error = "timeout"
            if attempt < MAX_RETRIES:
                time.sleep(_jitter(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]))
                continue
            break
        except requests.exceptions.RequestException as e:
            last_error = type(e).__name__
            if attempt < MAX_RETRIES:
                time.sleep(_jitter(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]))
                continue
            break
    return (None, last_error or "unknown")


def parse_match_id(match_id_or_url: str) -> str:
    """Extract numeric match ID from a URL or return as-is if already numeric."""
    s = match_id_or_url.strip()
    # URL with #id:14083327
    m = re.search(r"#id:(\d+)", s)
    if m:
        return m.group(1)
    # URL with /event/14083327
    m = re.search(r"/event/(\d+)", s)
    if m:
        return m.group(1)
    # Plain ID
    if s.isdigit():
        return s
    raise ValueError(f"Cannot parse match ID from: {match_id_or_url}")


def fetch_json(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def flatten_player(player_obj: dict, side: str, team_name: str, match_id: str) -> dict:
    """Turn one player from lineups API into a flat dict for one CSV row."""
    out = {
        "match_id": match_id,
        "side": side,
        "team": team_name,
    }
    # Player identity (nested under 'player' in many APIs)
    player = player_obj.get("player") or player_obj
    if isinstance(player, dict):
        for k, v in player.items():
            if isinstance(v, (dict, list)):
                continue
            out[f"player_{k}"] = v
    # Top-level player fields
    for key in ("position", "shirtNumber", "jerseyNumber", "substitute", "captain"):
        if key in player_obj and key not in out:
            out[key] = player_obj[key]
    # Statistics (nested dict → prefix with stat_)
    stats = player_obj.get("statistics") or player_obj.get("stats") or {}
    if isinstance(stats, dict):
        for k, v in stats.items():
            if isinstance(v, (dict, list)):
                continue
            out[f"stat_{k}"] = v
    return out


def get_team_name(event_data: dict, side: str) -> str:
    """Get team name from event payload (event.event.homeTeam / awayTeam)."""
    inner = event_data.get("event") or event_data
    team_key = "homeTeam" if side == "home" else "awayTeam"
    team = (inner.get(team_key) or {}) if isinstance(inner, dict) else {}
    return (team.get("name") or team.get("shortName")) or ""


def extract_lineups(event_id: str, out_dir: str = "data/raw", flat_filenames: bool = False) -> str:
    """Fetch event + lineups, build CSV, save to out_dir. Returns path.
    If flat_filenames=True, saves as lineups.csv (for match-specific folders).
    Uses resilient fetch (retries on 403/429/5xx/timeout). Raises on failure after retries."""
    event, err = fetch_json_resilient(f"{API_BASE}/event/{event_id}")
    if err:
        raise RuntimeError(f"event: {err}")
    lineups, err = fetch_json_resilient(f"{API_BASE}/event/{event_id}/lineups")
    if err:
        raise RuntimeError(f"lineups: {err}")

    rows = []
    for side, key in (("home", "home"), ("away", "away")):
        team_block = lineups.get(key) or {}
        team_name = ""
        if isinstance(team_block.get("team"), dict):
            team_name = (team_block["team"].get("name") or team_block["team"].get("shortName")) or ""
        if not team_name:
            team_name = get_team_name(event, side)
        players = team_block.get("players") or []
        for p in players:
            row = flatten_player(p, side, team_name, event_id)
            rows.append(row)

    if not rows:
        for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
            team_block = lineups.get(key) or {}
            team_name = (team_block.get("name") or team_block.get("shortName")) or get_team_name(event, side)
            players = team_block.get("players") or team_block.get("lineup") or []
            for p in players:
                row = flatten_player(p, side, team_name, event_id)
                rows.append(row)

    df = pd.DataFrame(rows)
    os.makedirs(out_dir, exist_ok=True)
    fname = "lineups.csv" if flat_filenames else f"lineups_{event_id}.csv"
    path = os.path.join(out_dir, fname)
    df.to_csv(path, index=False)
    return path


def _fetch_optional(url: str) -> Optional[dict]:
    """Fetch with retries; returns None on any failure (no raise)."""
    data, _ = fetch_json_resilient(url)
    return data


def extract_statistics(event_id: str, out_dir: str, flat_filenames: bool = False) -> Optional[str]:
    """Fetch /event/{id}/statistics, flatten to CSV. Returns path or None."""
    data = _fetch_optional(f"{API_BASE}/event/{event_id}/statistics")
    if not data or "statistics" not in data:
        return None
    rows = []
    for period_block in data.get("statistics", []):
        period = period_block.get("period") or "ALL"
        for group in period_block.get("groups", []):
            group_name = group.get("groupName") or group.get("name") or ""
            for stat in group.get("statisticsItems", []) or group.get("items", []):
                row = {"match_id": event_id, "period": period, "group": group_name}
                if isinstance(stat, dict):
                    row["name"] = stat.get("name")
                    row["home"] = stat.get("home") or stat.get("homeValue")
                    row["away"] = stat.get("away") or stat.get("awayValue")
                rows.append(row)
    if not rows:
        return None
    fname = "team_statistics.csv" if flat_filenames else f"team_statistics_{event_id}.csv"
    path = os.path.join(out_dir, fname)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def extract_incidents(event_id: str, out_dir: str, flat_filenames: bool = False) -> Optional[str]:
    """Fetch /event/{id}/incidents, flatten to CSV. Returns path or None."""
    data = _fetch_optional(f"{API_BASE}/event/{event_id}/incidents")
    if not data or "incidents" not in data:
        return None
    rows = []
    for inc in data.get("incidents", []):
        row = {"match_id": event_id}
        for k, v in inc.items():
            if isinstance(v, (dict, list)):
                continue
            row[k] = v
        if "player" in inc and isinstance(inc["player"], dict):
            row["player_id"] = inc["player"].get("id")
            row["player_name"] = inc["player"].get("name")
        rows.append(row)
    if not rows:
        return None
    fname = "incidents.csv" if flat_filenames else f"incidents_{event_id}.csv"
    path = os.path.join(out_dir, fname)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def extract_managers(event_id: str, out_dir: str, flat_filenames: bool = False) -> Optional[str]:
    """Fetch /event/{id}/managers, save as JSON. Returns path or None."""
    data = _fetch_optional(f"{API_BASE}/event/{event_id}/managers")
    if not data:
        return None
    fname = "managers.json" if flat_filenames else f"managers_{event_id}.json"
    path = os.path.join(out_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def extract_graph(event_id: str, out_dir: str, flat_filenames: bool = False) -> Optional[str]:
    """Fetch /event/{id}/graph (momentum), save as JSON. Returns path or None."""
    data = _fetch_optional(f"{API_BASE}/event/{event_id}/graph")
    if not data:
        return None
    fname = "graph.json" if flat_filenames else f"graph_{event_id}.json"
    path = os.path.join(out_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/extract_match_lineups.py <match_id_or_url>")
        sys.exit(1)
    match_id_or_url = sys.argv[1]
    try:
        event_id = parse_match_id(match_id_or_url)
    except ValueError as e:
        print(e)
        sys.exit(1)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    path = extract_lineups(event_id, out_dir=out_dir)
    print(f"Wrote {path}")
    for name, fn in [
        ("team_statistics", lambda: extract_statistics(event_id, out_dir)),
        ("incidents", lambda: extract_incidents(event_id, out_dir)),
        ("managers", lambda: extract_managers(event_id, out_dir)),
        ("graph", lambda: extract_graph(event_id, out_dir)),
    ]:
        p = fn()
        if p:
            print(f"Wrote {p}")


if __name__ == "__main__":
    main()
