"""
Discover match IDs for a Sofascore competition and build/update the matches index.

Usage:
  python src/discover_matches.py spain-laliga
  python src/discover_matches.py spain-laliga --seasons 2022-23 2023-24
  python src/discover_matches.py spain-laliga --index-only

Outputs:
  data/index/matches.csv  (or matches.parquet) - central index of all discovered matches
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parent))

import pandas as pd
import requests
import yaml

from config import API_BASE, ROOT, INDEX_PATH as CONFIG_INDEX_PATH

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}

# Season label (e.g. 2022-23) -> Sofascore season ID
# Fetched from API; pre-filled to avoid extra request when API is used
LA_LIGA_SEASON_IDS = {
    "2022-23": 42409,
    "2023-24": 52376,
    "2024-25": 61643,
    "2025-26": 77559,
}
# German Bundesliga (tournament_id 42). Optional: add season IDs here when API returns 403.
# Or run: python src/fetch_seasons_browser.py 42 --out config/germany_bundesliga_seasons.json
# and discover_matches will read config/germany_bundesliga_seasons.json when present.
BUNDESLIGA_SEASON_IDS = {}


def load_config() -> dict:
    path = ROOT / "config" / "competitions.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_403_challenge(response) -> bool:
    """Sofascore returns 403 with body like {"error": {"code": 403, "reason": "challenge"}}."""
    if response.status_code != 403:
        return False
    try:
        data = response.json()
        err = (data or {}).get("error") or {}
        return err.get("code") == 403 and (err.get("reason") or "").lower() == "challenge"
    except Exception:
        return True  # assume challenge on any 403


def fetch_json(url: str, retries: int = 3) -> dict:
    """GET JSON; on 403 challenge retry with backoff; on 503/429/502 retry with short backoff."""
    delays_403 = [5, 15, 45]  # seconds for 403
    delays_5xx = [3, 8, 20]   # seconds for 503/502/429
    last_response = None
    attempt = 0
    max_attempts = (retries + 1) * 2  # allow retries for both 403 and 5xx
    while attempt < max_attempts:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
        last_response = r
        if r.status_code == 403 and _is_403_challenge(r) and attempt < retries + 1:
            wait = delays_403[min(attempt, len(delays_403) - 1)]
            print(f"  403 challenge on {url}; retrying in {wait}s (attempt {attempt + 1})...")
            time.sleep(wait)
            attempt += 1
            continue
        if r.status_code in (429, 502, 503) and attempt < max_attempts - 1:
            wait = delays_5xx[min(attempt % 3, len(delays_5xx) - 1)]
            print(f"  {r.status_code} on {url}; retrying in {wait}s (attempt {attempt + 1})...")
            time.sleep(wait)
            attempt += 1
            continue
        break
    if last_response is not None and last_response.status_code == 403:
        raise RuntimeError(
            "Sofascore returned 403 (challenge) after retries. Try again later, use a different "
            "network/VPN, or use browser automation (e.g. Playwright) to obtain a session and cookies."
        ) from None
    if last_response is not None:
        last_response.raise_for_status()
    return last_response.json() if last_response else {}


def _seasons_path(tournament_id: int, api_path: Optional[str]) -> str:
    """API path for seasons: tournament or unique-tournament (website uses latter for e.g. UCL)."""
    if api_path == "unique-tournament":
        return f"{API_BASE}/unique-tournament/{tournament_id}/seasons"
    return f"{API_BASE}/tournament/{tournament_id}/seasons"


def _events_path(
    tournament_id: int, season_id: int, api_path: Optional[str]
) -> str:
    """API path for events (same path style as seasons: tournament vs unique-tournament)."""
    if api_path == "unique-tournament":
        return f"{API_BASE}/unique-tournament/{tournament_id}/season/{season_id}/events"
    return f"{API_BASE}/tournament/{tournament_id}/season/{season_id}/events"


def fetch_seasons(tournament_id: int, api_path: Optional[str] = None) -> dict:
    """Return mapping season_label -> season_id (e.g. 2022-23 -> 42409)."""
    url = _seasons_path(tournament_id, api_path)
    data = fetch_json(url)
    mapping = {}
    for s in data.get("seasons", []):
        year = s.get("year", "")
        if not year:
            continue
        # Convert "22/23" -> "2022-23", "25/26" -> "2025-26"
        parts = year.split("/")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            y1, y2 = int(parts[0]), int(parts[1])
            label = f"20{y1}-{y2}"
            mapping[label] = s["id"]
        # Single calendar year "2024" -> "2023-24" (season ending in that year)
        elif year.isdigit() and len(year) == 4:
            y = int(year)
            if 2020 <= y <= 2030:
                label = f"{y - 1}-{str(y)[2:]}"
                mapping[label] = s["id"]
    return mapping


def fetch_events(tournament_id: int, season_id: int, api_path: Optional[str] = None) -> list:
    """Fetch all events for a tournament season. Raises on 404."""
    url = _events_path(tournament_id, season_id, api_path)
    data = fetch_json(url)
    return data.get("events", [])


def _season_date_range(season: str) -> tuple[str, str]:
    """Return (start_date, end_date) ISO for a season label e.g. 2025-26 -> (2025-07-01, 2026-06-30)."""
    parts = season.split("-")
    if len(parts) != 2:
        return ("2020-07-01", "2021-06-30")
    y1, y2_short = int(parts[0]), int(parts[1])
    y2 = 2000 + y2_short if y2_short < 100 else y2_short
    return (f"{y1}-07-01", f"{y2}-06-30")


def fetch_events_via_scheduled_dates(
    slug: str,
    season_id: int,
    season: str,
    delay: float = 0.3,
) -> list:
    """
    Fallback: discover events by iterating over scheduled-events by date.
    Use when /unique-tournament/{id}/season/{id}/events returns 404 (e.g. UEFA Champions League).
    Filters by tournament slug and season.id; returns finished events only (code 100).
    """
    from datetime import datetime, timedelta

    start_s, end_s = _season_date_range(season)
    start_d = datetime.strptime(start_s, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_s, "%Y-%m-%d").date()
    seen_ids: set[int] = set()
    out: list[dict] = []
    day = start_d
    consecutive_403 = 0
    max_consecutive_403 = 5  # give up fallback for this season after 5 straight 403s
    while day <= end_d:
        time.sleep(delay)
        url = f"{API_BASE}/sport/football/scheduled-events/{day.isoformat()}"
        try:
            data = fetch_json(url)
            consecutive_403 = 0
        except Exception as e:
            day += timedelta(days=1)
            if "403" in str(e) or (hasattr(e, "response") and getattr(e.response, "status_code", None) == 403):
                consecutive_403 += 1
                if consecutive_403 >= max_consecutive_403:
                    break
            continue
        for event in data.get("events") or []:
            t = event.get("tournament") or {}
            if t.get("slug") != slug:
                continue
            season_info = event.get("season") or {}
            if season_info.get("id") != season_id:
                continue
            if event.get("id") in seen_ids:
                continue
            seen_ids.add(event["id"])
            if (event.get("status") or {}).get("code") == 100:
                out.append(event)
        day += timedelta(days=1)
    return out


def event_to_row(event: dict, season: str, realm: str, slug: str) -> dict:
    """Convert one event to index row."""
    status = event.get("status") or {}
    return {
        "match_id": event.get("id"),
        "season": season,
        "realm": realm,
        "competition_slug": slug,
        "home_team_id": (event.get("homeTeam") or {}).get("id"),
        "home_team_name": (event.get("homeTeam") or {}).get("name"),
        "away_team_id": (event.get("awayTeam") or {}).get("id"),
        "away_team_name": (event.get("awayTeam") or {}).get("name"),
        "match_date": event.get("startTimestamp"),
        "round": (event.get("roundInfo") or {}).get("round"),
        "status_code": status.get("code"),
        "status_type": status.get("type"),
    }


def _allowed_tournament_slugs(comp: dict, slug: str) -> set:
    """Return set of allowed API tournament.slug values for identity validation."""
    allowed = comp.get("expected_tournament_slugs")
    if allowed is not None:
        return set(s for s in allowed if s)
    return {comp.get("slug", slug)}


def _validate_event_tournament_identity(
    event: dict,
    expected_season_id: int,
    allowed_slugs: set,
) -> Tuple[bool, Optional[str]]:
    """
    Validate event belongs to expected tournament and season.
    Returns (accepted, rejection_reason). rejection_reason is None if accepted.
    """
    t = event.get("tournament") or {}
    event_slug = (t.get("slug") or "").strip()
    season_info = event.get("season") or {}
    event_season_id = season_info.get("id")

    if event_slug not in allowed_slugs:
        return False, "slug_mismatch"
    if event_season_id != expected_season_id:
        return False, "season_mismatch"
    return True, None


def discover_competition(
    slug: str,
    tournament_id: int,
    realm: str,
    season_ids: dict[str, int],
    delay: float = 0.5,
    api_path: Optional[str] = None,
    comp_config: Optional[dict] = None,
) -> pd.DataFrame:
    """Discover all finished matches for a competition across seasons.
    Only accepts events whose tournament.slug and season.id match config (identity guardrails).
    """
    comp_config = comp_config or {}
    allowed_slugs = _allowed_tournament_slugs(comp_config, slug)
    rows = []
    run_summary = {"fetched_events": 0, "accepted_events": 0, "rejected_slug_mismatch": 0, "rejected_season_mismatch": 0}
    seen_mismatched_slugs = set()

    for season, sid in season_ids.items():
        time.sleep(delay)
        events = None
        try:
            events = fetch_events(tournament_id, sid, api_path=api_path)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                print(f"  Events URL 404 for {season}; trying discovery via scheduled-events by date...")
                events = fetch_events_via_scheduled_dates(slug, sid, season, delay=delay)
            else:
                raise
        if events is not None:
            finished = [e for e in events if (e.get("status") or {}).get("code") == 100]
            run_summary["fetched_events"] += len(finished)
            for e in finished:
                accepted, reason = _validate_event_tournament_identity(e, sid, allowed_slugs)
                if accepted:
                    rows.append(event_to_row(e, season, realm, slug))
                    run_summary["accepted_events"] += 1
                else:
                    if reason == "slug_mismatch":
                        run_summary["rejected_slug_mismatch"] += 1
                        api_slug = (e.get("tournament") or {}).get("slug") or ""
                        if api_slug:
                            seen_mismatched_slugs.add(api_slug)
                    else:
                        run_summary["rejected_season_mismatch"] += 1
    if run_summary["rejected_slug_mismatch"] or run_summary["rejected_season_mismatch"]:
        msg = (
            f"  Identity check: accepted={run_summary['accepted_events']}, "
            f"rejected_slug_mismatch={run_summary['rejected_slug_mismatch']}, "
            f"rejected_season_mismatch={run_summary['rejected_season_mismatch']}"
        )
        if seen_mismatched_slugs:
            msg += f" — Add to expected_tournament_slugs: {sorted(seen_mismatched_slugs)}"
        print(msg)
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Discover Sofascore match IDs")
    parser.add_argument("competition", help="Competition slug (e.g. spain-laliga)")
    parser.add_argument(
        "--seasons",
        nargs="*",
        default=["2022-23", "2023-24", "2024-25", "2025-26"],
        help="Season labels to fetch",
    )
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    parser.add_argument("--index-path", default=None, help="Output path for index CSV/Parquet")
    args = parser.parse_args()

    config = load_config()
    if args.competition not in config:
        print(f"Unknown competition: {args.competition}")
        print(f"Available: {list(config.keys())}")
        sys.exit(1)

    comp = config[args.competition]
    tournament_id = comp["tournament_id"]
    realm = comp.get("realm", "club")
    slug = comp.get("slug", args.competition)
    api_path = comp.get("api_path")

    # Resolve season IDs: use pre-filled when available, else fetch from API
    if slug == "spain-laliga":
        season_ids = {s: LA_LIGA_SEASON_IDS[s] for s in args.seasons if s in LA_LIGA_SEASON_IDS}
        if not season_ids:
            season_ids = {s: LA_LIGA_SEASON_IDS.get(s) for s in args.seasons}
            season_ids = {k: v for k, v in season_ids.items() if v is not None}
    elif slug == "germany-bundesliga":
        # Prefer JSON file from fetch_seasons_browser.py, then hardcoded dict, then API
        season_ids = {}
        json_path = ROOT / "config" / "germany_bundesliga_seasons.json"
        if json_path.exists():
            try:
                with open(json_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                season_ids = {s: int(loaded[s]) for s in args.seasons if s in loaded}
            except Exception:
                pass
        if not season_ids and BUNDESLIGA_SEASON_IDS:
            season_ids = {s: BUNDESLIGA_SEASON_IDS[s] for s in args.seasons if s in BUNDESLIGA_SEASON_IDS}
        if not season_ids:
            all_seasons = fetch_seasons(tournament_id, api_path=api_path)
            season_ids = {s: all_seasons[s] for s in args.seasons if s in all_seasons}
    else:
        all_seasons = fetch_seasons(tournament_id, api_path=api_path)
        season_ids = {s: all_seasons[s] for s in args.seasons if s in all_seasons}

    if not season_ids:
        print("No valid seasons found")
        sys.exit(1)

    print(f"Discovering {args.competition} for seasons {list(season_ids.keys())}...")
    df = discover_competition(
        slug, tournament_id, realm, season_ids,
        delay=args.delay, api_path=api_path, comp_config=comp,
    )
    print(f"Found {len(df)} finished matches")

    index_path = Path(args.index_path) if args.index_path else CONFIG_INDEX_PATH
    index_path.parent.mkdir(parents=True, exist_ok=True)

    # Merge into existing index: NEVER remove matches. Add new match_ids; overwrite only placeholder rows with API metadata.
    PLACEHOLDER_HOME_ID = -1
    PLACEHOLDER_AWAY_ID = -2
    PLACEHOLDER_MATCH_DATE = 1609459200  # 2021-01-01 UTC

    if index_path.exists():
        existing = pd.read_csv(index_path)
        existing["match_id"] = existing["match_id"].astype(str)
        existing_ids = set(existing["match_id"])
        if df.empty:
            combined = existing
            added = 0
            updated = 0
        else:
            df["match_id"] = df["match_id"].astype(str)
            discovered_ids = set(df["match_id"])
            new_ids = discovered_ids - existing_ids
            # Rows that are placeholders (rebuilt-from-raw with no API metadata)
            home_ph = pd.to_numeric(existing["home_team_id"], errors="coerce") == PLACEHOLDER_HOME_ID
            away_ph = pd.to_numeric(existing["away_team_id"], errors="coerce") == PLACEHOLDER_AWAY_ID
            date_ph = pd.to_numeric(existing["match_date"], errors="coerce") == PLACEHOLDER_MATCH_DATE
            is_placeholder = home_ph | away_ph | date_ph
            placeholder_ids = set(existing.loc[is_placeholder, "match_id"])
            replace_ids = discovered_ids & placeholder_ids  # rediscovered and currently placeholder -> overwrite
            # Keep: not rediscovered, or rediscovered but not a placeholder (keep real metadata)
            existing_keep = existing[
                ~existing["match_id"].isin(discovered_ids)
                | (existing["match_id"].isin(discovered_ids) & ~existing["match_id"].isin(placeholder_ids))
            ]
            # From df: add new match_ids + rows that replace placeholders
            ids_from_df = new_ids | replace_ids
            df_to_add = df[df["match_id"].isin(ids_from_df)]
            combined = pd.concat([existing_keep, df_to_add], ignore_index=True)
            added = len(new_ids)
            updated = len(replace_ids)
    else:
        updated = 0
        if df.empty:
            combined = pd.DataFrame(columns=[
                "match_id", "season", "realm", "competition_slug",
                "home_team_id", "home_team_name", "away_team_id", "away_team_name",
                "match_date", "round", "status_code", "status_type",
            ])
            added = 0
        else:
            combined = df
            added = len(df)
    combined.to_csv(index_path, index=False)
    msg = f"Wrote {index_path} ({len(combined)} total matches in index, {added} new)"
    if updated:
        msg += f", {updated} refreshed with API metadata"
    print(msg)
    return df


if __name__ == "__main__":
    main()
