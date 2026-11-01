#!/usr/bin/env python3
"""
End-to-end live test: Sofascore API → raw extract → derived → DLT → DuckDB → dbt → AI index.

Default: 3 finished Belgium Pro League 2025-26 matches (rate-limit friendly).

Usage (from project root):
  python platform/scripts/run_e2e_live.py
  python platform/scripts/run_e2e_live.py --limit 2
  python platform/scripts/run_e2e_live.py --skip-extract
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from config import RAW_BASE  # noqa: E402
from extract_match_lineups import (  # noqa: E402
    extract_graph,
    extract_incidents,
    extract_lineups,
    extract_managers,
    extract_statistics,
)

LIVE_DIR = ROOT / "platform" / "live_source"
WAREHOUSE = ROOT / "data" / "warehouse" / "schlouh_e2e.duckdb"


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print(f"\n$ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(cwd))
    if r.returncode != 0:
        raise SystemExit(f"Command failed ({r.returncode}): {' '.join(cmd)}")


def pick_matches(competition: str, season: str, limit: int) -> pd.DataFrame:
    index = pd.read_csv(ROOT / "data" / "index" / "matches.csv")
    index["match_id"] = index["match_id"].astype(str)
    subset = index[(index["competition_slug"] == competition) & (index["season"] == season)].copy()
    if subset.empty:
        raise SystemExit(f"No matches in index for {competition} {season}. Run discover first.")
    if "status_type" in subset.columns:
        finished = subset[subset["status_type"].astype(str).str.lower() == "finished"]
        if not finished.empty:
            subset = finished
    subset = subset.sort_values("match_date", ascending=False).drop_duplicates("match_id").head(limit)
    print("Selected matches:")
    print(subset[["match_id", "home_team_name", "away_team_name", "match_date"]].to_string(index=False))
    return subset


def extract_one(row: pd.Series, delay: float) -> bool:
    match_id = str(row["match_id"])
    season = row["season"]
    realm = row.get("realm", "club") or "club"
    competition = row["competition_slug"]
    match_dir = RAW_BASE / season / realm / competition / match_id
    match_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n--- Live extract {match_id} → {match_dir.relative_to(ROOT)} ---")
    try:
        extract_lineups(match_id, str(match_dir), flat_filenames=True)
        time.sleep(delay)
        extract_statistics(match_id, str(match_dir), flat_filenames=True)
        time.sleep(delay)
        extract_incidents(match_id, str(match_dir), flat_filenames=True)
        time.sleep(delay)
        extract_managers(match_id, str(match_dir), flat_filenames=True)
        time.sleep(delay)
        extract_graph(match_id, str(match_dir), flat_filenames=True)
        print(f"OK extract {match_id}")
        return True
    except Exception as e:
        print(f"FAIL extract {match_id}: {e}", file=sys.stderr)
        return False


def build_live_source(match_ids: list[str], competition: str, season: str) -> Path:
    print("\n=== Build derived appearances ===")
    run([sys.executable, str(ROOT / "src" / "build_player_appearances.py")])

    app = pd.read_parquet(ROOT / "data" / "derived" / "player_appearances.parquet")
    app["match_id"] = app["match_id"].astype(str)
    app_slice = app[app["match_id"].isin(match_ids)].copy()
    if app_slice.empty:
        raise SystemExit("No appearances for selected matches after extract.")

    matches = pd.read_csv(ROOT / "data" / "index" / "matches.csv")
    matches["match_id"] = matches["match_id"].astype(str)
    matches_slice = matches[matches["match_id"].isin(match_ids)].copy()

    players = pd.read_csv(ROOT / "data" / "index" / "players.csv")
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    pids = set(pd.to_numeric(app_slice["player_id"], errors="coerce").dropna().astype(int))
    players_slice = players[players["player_id"].isin(pids)].copy()

    scores_path = ROOT / "data" / "derived" / "match_scores.parquet"
    scores = pd.read_parquet(scores_path) if scores_path.exists() else pd.DataFrame()
    if not scores.empty:
        scores["match_id"] = scores["match_id"].astype(str)
        scores = scores[scores["match_id"].isin(match_ids)]

    ms_path = ROOT / "data" / "processed" / "02_match_summary.parquet"
    if ms_path.exists():
        ms = pd.read_parquet(ms_path)
        ms["match_id"] = ms["match_id"].astype(str)
        ms_slice = ms[ms["match_id"].isin(match_ids)].copy()
    else:
        ms_slice = matches_slice.merge(scores, on="match_id", how="left") if not scores.empty else matches_slice.copy()

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

    ms_keep = [
        "match_id", "season", "competition_slug", "match_date_utc", "round",
        "home_team_name", "away_team_name", "home_score", "away_score", "result", "total_goals",
        "home_xg", "away_xg", "home_possession", "away_possession", "home_shots", "away_shots",
        "home_shots_on_target", "away_shots_on_target", "referee_name", "venue_name", "venue_city",
    ]
    for col in ("season", "competition_slug", "home_team_name", "away_team_name", "round"):
        if col not in ms_slice.columns and col in matches_slice.columns:
            ms_slice = ms_slice.drop(columns=[col], errors="ignore").merge(
                matches_slice[["match_id", col]], on="match_id", how="left"
            )
    # Prefer scores columns when summary missing scores
    if not scores.empty:
        for col in ("home_score", "away_score"):
            if col in scores.columns and (col not in ms_slice.columns or ms_slice[col].isna().all()):
                ms_slice = ms_slice.drop(columns=[col], errors="ignore").merge(
                    scores[["match_id", col]], on="match_id", how="left"
                )

    if LIVE_DIR.exists():
        shutil.rmtree(LIVE_DIR)
    LIVE_DIR.mkdir(parents=True)

    app_slice.to_parquet(LIVE_DIR / "player_appearances.parquet", index=False)
    matches_slice.to_csv(LIVE_DIR / "matches.csv", index=False)
    players_slice.to_csv(LIVE_DIR / "players.csv", index=False)
    ms_out = ms_slice[[c for c in ms_keep if c in ms_slice.columns]].copy()
    if "match_id" not in ms_out.columns:
        ms_out = matches_slice[
            [c for c in ["match_id", "season", "competition_slug", "home_team_name", "away_team_name", "round"] if c in matches_slice.columns]
        ].copy()
    ms_out.to_parquet(LIVE_DIR / "match_summary.parquet", index=False)

    meta = {
        "mode": "e2e_live",
        "competition_slug": competition,
        "season": season,
        "n_matches": len(match_ids),
        "n_appearances": int(len(app_slice)),
        "n_players": int(len(players_slice)),
        "match_ids": match_ids,
    }
    (LIVE_DIR / "fixture_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    return LIVE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Sofascore → platform E2E")
    parser.add_argument("--competition", default="belgium-pro-league")
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--skip-extract", action="store_true")
    args = parser.parse_args()

    os.environ["SOFASCORE_WAREHOUSE_PATH"] = str(WAREHOUSE)

    print("=== 0) API contract (live Sofascore) ===")
    run([sys.executable, str(ROOT / "scripts" / "check_api_contract.py")])

    selected = pick_matches(args.competition, args.season, args.limit)
    match_ids = selected["match_id"].astype(str).tolist()

    if not args.skip_extract:
        print("\n=== 1) Live extract from Sofascore API ===")
        ok = 0
        for _, row in selected.iterrows():
            if extract_one(row, args.delay):
                ok += 1
            time.sleep(args.delay)
        if ok == 0:
            raise SystemExit("All live extracts failed.")
        print(f"Extracted OK: {ok}/{len(match_ids)}")
    else:
        print("\n=== 1) skip-extract ===")

    print("\n=== 2) Build live_source ===")
    source = build_live_source(match_ids, args.competition, args.season)

    if WAREHOUSE.exists():
        WAREHOUSE.unlink()
    print(f"\n=== 3) DLT load → {WAREHOUSE} ===")
    run(
        [
            sys.executable,
            str(ROOT / "platform" / "pipelines" / "sofascore_load.py"),
            "--source",
            str(source.relative_to(ROOT)),
            "--warehouse",
            str(WAREHOUSE.relative_to(ROOT)),
        ]
    )

    profiles_main = ROOT / "platform" / "dbt" / "profiles.yml"
    profiles_main.write_text(
        """schlouh_platform:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "../../data/warehouse/schlouh.duckdb"
      schema: analytics
      threads: 4
    e2e:
      type: duckdb
      path: "../../data/warehouse/schlouh_e2e.duckdb"
      schema: analytics
      threads: 4
"""
    )

    print("\n=== 4) dbt build (e2e target) ===")
    run(
        ["dbt", "build", "--profiles-dir", ".", "--target", "e2e"],
        cwd=ROOT / "platform" / "dbt",
    )

    print("\n=== 5) Validate e2e warehouse ===")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    n_m = con.execute("select count(*) from raw_sofascore.matches").fetchone()[0]
    n_a = con.execute("select count(*) from raw_sofascore.player_appearances").fetchone()[0]
    n_s = con.execute("select count(*) from analytics_marts.mart_player_season_stats").fetchone()[0]
    print(f"matches={n_m} appearances={n_a} season_stats={n_s}")
    assert n_m == len(match_ids), f"expected {len(match_ids)} matches, got {n_m}"
    assert n_a > 0 and n_s > 0
    print(
        con.execute(
            """
            select player_name, goals, assists, total_minutes, avg_rating
            from analytics_marts.mart_player_season_stats
            order by goals desc nulls last, total_minutes desc
            limit 8
            """
        ).fetchdf().to_string(index=False)
    )
    con.close()

    print("\n=== 6) AI retrieval index ===")
    run([sys.executable, str(ROOT / "platform" / "ai" / "build_retrieval_index.py")])
    run([sys.executable, str(ROOT / "platform" / "ai" / "query_retrieval.py"), match_ids[0], "--limit", "3"])

    print("\nE2E_LIVE_OK — Sofascore API → raw → DLT → dbt → AI")
    print(f"Warehouse: {WAREHOUSE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
