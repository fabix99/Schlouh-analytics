#!/usr/bin/env python3
"""Export dbt core marts to processed parquet for downstream pandas steps / dual-write."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = Path(os.environ.get("SOFASCORE_WAREHOUSE_PATH", ROOT / "data/warehouse/schlouh.duckdb"))
if not WAREHOUSE.is_absolute():
    WAREHOUSE = ROOT / WAREHOUSE
PROCESSED = ROOT / "data" / "processed"

EXPORTS = [
    ("analytics_marts.mart_player_season_stats", "03_player_season_stats.parquet"),
    ("analytics_marts.mart_player_scouting_profiles", "08_player_scouting_profiles.parquet"),
]


def main() -> int:
    if not WAREHOUSE.exists():
        print(f"FAIL: warehouse missing {WAREHOUSE}", file=sys.stderr)
        return 1
    PROCESSED.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    for table, filename in EXPORTS:
        out = PROCESSED / filename
        n = con.execute(f"select count(*) from {table}").fetchone()[0]
        con.execute(f"copy (select * from {table}) to '{out}' (format parquet)")
        print(f"exported {table} → {out} ({n} rows)")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
