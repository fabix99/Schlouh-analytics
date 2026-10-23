#!/usr/bin/env python3
"""
Rebuild platform/fixtures from local derived/processed data (Belgium Pro League slice).

Run from project root after you have data/derived and data/processed.
CI uses the committed fixtures; this script regenerates them locally.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "platform" / "fixtures"
N_MATCHES = 30
COMP = "belgium-pro-league"


def main() -> int:
    app_path = ROOT / "data" / "derived" / "player_appearances.parquet"
    matches_path = ROOT / "data" / "index" / "matches.csv"
    players_path = ROOT / "data" / "index" / "players.csv"
    ms_path = ROOT / "data" / "processed" / "02_match_summary.parquet"

    for p in (app_path, matches_path, players_path, ms_path):
        if not p.exists():
            print(f"Missing required data: {p}", file=sys.stderr)
            return 1

    OUT.mkdir(parents=True, exist_ok=True)
    app = pd.read_parquet(app_path)
    app["match_id"] = app["match_id"].astype(str)
    bel = app[app["competition_slug"] == COMP]
    if bel.empty:
        print(f"No appearances for {COMP}", file=sys.stderr)
        return 1
    season = bel["season"].value_counts().idxmax()
    bel = bel[bel["season"] == season]
    mids = bel["match_id"].drop_duplicates().head(N_MATCHES).tolist()
    app_slice = bel[bel["match_id"].isin(mids)].copy()

    core_cols = [
        "match_id", "season", "realm", "competition_slug", "match_date", "round",
        "side", "team", "player_id", "player_name", "player_shortName", "player_slug",
        "player_position", "player_height", "player_dateOfBirthTimestamp",
        "substitute", "stat_minutesPlayed", "stat_rating", "stat_goals", "stat_goalAssist",
        "stat_totalPass", "stat_accuratePass", "stat_totalShots", "stat_onTargetScoringAttempt",
        "stat_keyPass", "stat_duelWon", "stat_duelLost", "stat_totalTackle", "stat_interceptionWon",
        "stat_expectedGoals", "stat_expectedAssists", "home_team_name", "away_team_name",
        "home_team_id", "away_team_id", "status_type",
    ]
    app_slice = app_slice[[c for c in core_cols if c in app_slice.columns]]

    matches = pd.read_csv(matches_path)
    matches["match_id"] = matches["match_id"].astype(str)
    matches_slice = matches[matches["match_id"].isin(mids)].copy()

    players = pd.read_csv(players_path)
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    pids = set(pd.to_numeric(app_slice["player_id"], errors="coerce").dropna().astype(int))
    players_slice = players[players["player_id"].isin(pids)].copy()

    ms = pd.read_parquet(ms_path)
    ms["match_id"] = ms["match_id"].astype(str)
    ms_keep = [
        "match_id", "season", "competition_slug", "match_date_utc", "round",
        "home_team_name", "away_team_name", "home_score", "away_score", "result", "total_goals",
        "home_xg", "away_xg", "home_possession", "away_possession", "home_shots", "away_shots",
        "home_shots_on_target", "away_shots_on_target", "referee_name", "venue_name", "venue_city",
    ]
    ms_slice = ms[ms["match_id"].isin(mids)][[c for c in ms_keep if c in ms.columns]].copy()

    app_slice.to_parquet(OUT / "player_appearances.parquet", index=False)
    matches_slice.to_csv(OUT / "matches.csv", index=False)
    players_slice.to_csv(OUT / "players.csv", index=False)
    ms_slice.to_parquet(OUT / "match_summary.parquet", index=False)

    meta = {
        "competition_slug": COMP,
        "season": season,
        "n_matches": len(mids),
        "n_appearances": int(len(app_slice)),
        "n_players": int(len(players_slice)),
        "match_ids": mids,
    }
    (OUT / "fixture_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
