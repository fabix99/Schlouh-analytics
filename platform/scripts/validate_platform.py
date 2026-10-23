#!/usr/bin/env python3
"""
End-to-end validation for the Schlouh data platform slice.

Checks:
  1. Fixtures exist
  2. Warehouse DuckDB exists and raw + mart tables are populated
  3. Row counts are consistent with fixtures
  4. Sample SQL queries return sane results

Exit 0 on success, 1 on failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "platform" / "fixtures"
WAREHOUSE = ROOT / "data" / "warehouse" / "schlouh.duckdb"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    for name in (
        "matches.csv",
        "players.csv",
        "player_appearances.parquet",
        "match_summary.parquet",
        "fixture_meta.json",
    ):
        if not (FIXTURES / name).exists():
            fail(f"missing fixture {name}")

    meta = json.loads((FIXTURES / "fixture_meta.json").read_text())
    if not WAREHOUSE.exists():
        fail(f"warehouse missing: {WAREHOUSE} (run DLT + dbt first)")

    con = duckdb.connect(str(WAREHOUSE), read_only=True)

    raw_counts = {
        "matches": con.execute("select count(*) from raw_sofascore.matches").fetchone()[0],
        "players": con.execute("select count(*) from raw_sofascore.players").fetchone()[0],
        "player_appearances": con.execute(
            "select count(*) from raw_sofascore.player_appearances"
        ).fetchone()[0],
        "match_summary": con.execute(
            "select count(*) from raw_sofascore.match_summary"
        ).fetchone()[0],
    }
    print("raw counts:", raw_counts)

    if raw_counts["matches"] != meta["n_matches"]:
        fail(f"matches count {raw_counts['matches']} != fixture {meta['n_matches']}")
    if raw_counts["player_appearances"] != meta["n_appearances"]:
        fail(
            f"appearances {raw_counts['player_appearances']} != fixture {meta['n_appearances']}"
        )
    if raw_counts["players"] != meta["n_players"]:
        fail(f"players {raw_counts['players']} != fixture {meta['n_players']}")

    mart_match = con.execute(
        "select count(*) from analytics_marts.mart_match_summary"
    ).fetchone()[0]
    mart_season = con.execute(
        "select count(*) from analytics_marts.mart_player_season_stats"
    ).fetchone()[0]
    mart_scout = con.execute(
        "select count(*) from analytics_marts.mart_player_scouting_profiles"
    ).fetchone()[0]
    print(
        "mart counts:",
        {"match_summary": mart_match, "season_stats": mart_season, "scouting": mart_scout},
    )

    if mart_match != meta["n_matches"]:
        fail(f"mart_match_summary {mart_match} != {meta['n_matches']}")
    if mart_season < 1 or mart_scout < 1:
        fail("marts are empty")

    top = con.execute(
        """
        select player_name, goals, assists, total_minutes, avg_rating
        from analytics_marts.mart_player_season_stats
        order by goals desc, assists desc
        limit 5
        """
    ).fetchdf()
    print("top scorers (slice):\n", top.to_string(index=False))

    # Compare season goals vs fixture appearances for a spot check
    app = pd.read_parquet(FIXTURES / "player_appearances.parquet")
    if "stat_goals" in app.columns:
        fixture_goals = float(pd.to_numeric(app["stat_goals"], errors="coerce").fillna(0).sum())
        mart_goals = float(
            con.execute(
                "select coalesce(sum(goals),0) from analytics_marts.mart_player_season_stats"
            ).fetchone()[0]
        )
        print(f"goal totals: fixture={fixture_goals} mart={mart_goals}")
        if abs(fixture_goals - mart_goals) > 0.01:
            fail(f"goal totals mismatch fixture={fixture_goals} mart={mart_goals}")

    con.close()
    print("VALIDATION_OK: platform DLT → DuckDB → dbt marts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
