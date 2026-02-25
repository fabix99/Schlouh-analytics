#!/usr/bin/env python3
"""
Rebuild the matches index by adding any match that exists in raw but is not in the index.
Never removes existing index rows; only appends new rows.

Scans data/raw/{season}/{realm}/{competition_slug}/{match_id}/ for lineups.csv.
For each such match, if match_id is not already in data/index/matches.csv, adds a row
with: match_id, season, realm, competition_slug (from path), home_team_name, away_team_name
(from lineups), and placeholder/empty for other columns.

Usage:
  python scripts/rebuild_index_from_raw.py
  python scripts/rebuild_index_from_raw.py --dry-run
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import INDEX_PATH, RAW_BASE

INDEX_COLUMNS = [
    "match_id", "season", "realm", "competition_slug",
    "home_team_id", "home_team_name", "away_team_id", "away_team_name",
    "match_date", "round", "status_code", "status_type",
]


def iter_raw_matches():
    """Yield (match_id, season, realm, competition_slug, match_dir) for each raw match with lineups.csv."""
    if not RAW_BASE.exists():
        return
    for season_dir in sorted(RAW_BASE.iterdir()):
        if not season_dir.is_dir() or season_dir.name.startswith("."):
            continue
        season = season_dir.name
        for realm_dir in sorted(season_dir.iterdir()):
            if not realm_dir.is_dir() or realm_dir.name.startswith("."):
                continue
            realm = realm_dir.name
            for comp_dir in sorted(realm_dir.iterdir()):
                if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                    continue
                competition_slug = comp_dir.name
                for match_dir in sorted(comp_dir.iterdir()):
                    if not match_dir.is_dir() or match_dir.name.startswith("."):
                        continue
                    if not (match_dir / "lineups.csv").exists():
                        continue
                    match_id = match_dir.name
                    if not match_id.isdigit():
                        continue
                    yield match_id, season, realm, competition_slug, match_dir


def team_names_from_lineups(lineups_path: Path):
    """Read lineups.csv and return (home_team_name, away_team_name)."""
    try:
        df = pd.read_csv(lineups_path, usecols=["side", "team"], nrows=1000)
    except Exception:
        return "", ""
    home = df.loc[df["side"] == "home", "team"]
    away = df.loc[df["side"] == "away", "team"]
    home_name = home.iloc[0] if len(home) else ""
    away_name = away.iloc[0] if len(away) else ""
    return (str(home_name).strip() if pd.notna(home_name) else "", str(away_name).strip() if pd.notna(away_name) else "")


def main():
    ap = argparse.ArgumentParser(description="Add raw-only matches to index (never remove)")
    ap.add_argument("--dry-run", action="store_true", help="Print what would be added, do not write")
    args = ap.parse_args()

    # Load existing index
    if INDEX_PATH.exists():
        existing = pd.read_csv(INDEX_PATH)
        existing["match_id"] = existing["match_id"].astype(str)
        existing_ids = set(existing["match_id"])
    else:
        existing = pd.DataFrame(columns=INDEX_COLUMNS)
        existing_ids = set()

    # Build new rows from raw
    new_rows = []
    for match_id, season, realm, competition_slug, match_dir in iter_raw_matches():
        if match_id in existing_ids:
            continue
        home_name, away_name = team_names_from_lineups(match_dir / "lineups.csv")
        new_rows.append({
            "match_id": match_id,
            "season": season,
            "realm": realm,
            "competition_slug": competition_slug,
            "home_team_id": -1,
            "home_team_name": home_name,
            "away_team_id": -2,
            "away_team_name": away_name,
            "match_date": 1609459200,  # placeholder (2021-01-01 UTC) for validation
            "round": "",
            "status_code": 100,
            "status_type": "finished",
        })
        existing_ids.add(match_id)  # avoid duplicates from same match in multiple yields (shouldn't happen)

    if not new_rows:
        print("No new matches to add. Index already contains all matches found in raw.")
        return

    new_df = pd.DataFrame(new_rows, columns=INDEX_COLUMNS)
    print(f"Found {len(new_df)} match(es) in raw that are not in the index.")
    if new_df["competition_slug"].nunique() > 1:
        print(new_df.groupby("competition_slug").size().to_string())
    else:
        print(f"  Competition: {new_df['competition_slug'].iloc[0]}")

    if args.dry_run:
        print("Dry run: not writing index.")
        return

    combined = pd.concat([existing, new_df], ignore_index=True)
    combined.to_csv(INDEX_PATH, index=False)
    print(f"Wrote {INDEX_PATH} ({len(combined)} total rows, {len(new_df)} added).")


if __name__ == "__main__":
    main()
