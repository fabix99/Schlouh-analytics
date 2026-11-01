#!/usr/bin/env python3
"""Validate production DuckDB warehouse has serving marts populated."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = Path(os.environ.get("SOFASCORE_WAREHOUSE_PATH", ROOT / "data/warehouse/schlouh.duckdb"))
if not WAREHOUSE.is_absolute():
    WAREHOUSE = ROOT / WAREHOUSE

REQUIRED = [
    "mart_player_season_stats",
    "mart_player_scouting_profiles",
    "mart_match_summary",
    "mart_team_season_stats",
]


def main() -> int:
    if not WAREHOUSE.exists():
        print(f"FAIL: warehouse missing {WAREHOUSE}", file=sys.stderr)
        return 1
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    print(f"warehouse={WAREHOUSE}")
    for t in REQUIRED:
        n = con.execute(f"select count(*) from analytics_marts.{t}").fetchone()[0]
        print(f"  analytics_marts.{t}: {n}")
        if n < 1:
            print(f"FAIL: empty {t}", file=sys.stderr)
            return 1
    # Spot-check column continuity with legacy parquet expectations
    cols = [
        c[0]
        for c in con.execute(
            "select column_name from information_schema.columns "
            "where table_schema='analytics_marts' and table_name='mart_player_season_stats'"
        ).fetchall()
    ]
    for need in (
        "player_id",
        "season",
        "competition_slug",
        "player_name",
        "goals",
        "assists",
        "avg_rating",
        "total_minutes",
    ):
        if need not in cols:
            print(f"FAIL: missing column {need} on mart_player_season_stats", file=sys.stderr)
            return 1
    goals = con.execute(
        "select coalesce(sum(goals),0) from analytics_marts.mart_player_season_stats"
    ).fetchone()[0]
    if goals < 1:
        print("FAIL: mart_player_season_stats has no goals", file=sys.stderr)
        return 1
    print(f"  sum(goals)={goals}")
    print("VALIDATION_OK: full warehouse marts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
