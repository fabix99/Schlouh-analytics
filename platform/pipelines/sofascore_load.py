#!/usr/bin/env python3
"""
DLT pipeline: load Sofascore platform fixtures (or local extracts) into DuckDB.

This is the ELT ingest layer for the Schlouh data platform.
Default source is platform/fixtures (CI-safe, no live API).

Usage (from project root):
  python platform/pipelines/sofascore_load.py
  python platform/pipelines/sofascore_load.py --source platform/fixtures
  SOFASCORE_WAREHOUSE_PATH=data/warehouse/schlouh.duckdb python platform/pipelines/sofascore_load.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import dlt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / "platform" / "fixtures"
DEFAULT_WAREHOUSE = ROOT / "data" / "warehouse" / "schlouh.duckdb"
DATASET_NAME = "raw_sofascore"


def _warehouse_path() -> Path:
    env = os.environ.get("SOFASCORE_WAREHOUSE_PATH")
    if env:
        p = Path(env)
        return p if p.is_absolute() else ROOT / p
    return DEFAULT_WAREHOUSE


def _read_table(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing fixture/source file: {path}")
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file type: {path}")
    # Normalize ids to strings where helpful for joins
    for col in ("match_id",):
        if col in df.columns:
            df[col] = df[col].astype(str)
    if "player_id" in df.columns:
        df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce")
    # dlt prefers JSON-serializable records; convert timestamps
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
    return df.where(pd.notnull(df), None).to_dict(orient="records")


@dlt.source(name="sofascore_files")
def sofascore_files(source_dir: Path):
    """Filesystem source: curated tabular extracts into the warehouse."""

    @dlt.resource(name="matches", write_disposition="replace", primary_key="match_id")
    def matches():
        yield _read_table(source_dir / "matches.csv")

    @dlt.resource(name="players", write_disposition="replace", primary_key="player_id")
    def players():
        yield _read_table(source_dir / "players.csv")

    @dlt.resource(
        name="player_appearances",
        write_disposition="replace",
        primary_key=["match_id", "player_id"],
        columns={
            "stat_expected_goals": {"data_type": "double"},
            "stat_expected_assists": {"data_type": "double"},
        },
    )
    def player_appearances():
        yield _read_table(source_dir / "player_appearances.parquet")

    @dlt.resource(
        name="match_summary",
        write_disposition="replace",
        primary_key="match_id",
        columns={
            "home_xg": {"data_type": "double"},
            "away_xg": {"data_type": "double"},
        },
    )
    def match_summary():
        yield _read_table(source_dir / "match_summary.parquet")

    return matches, players, player_appearances, match_summary


def run(source_dir: Path, warehouse: Path) -> dlt.Pipeline:
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    pipeline = dlt.pipeline(
        pipeline_name="sofascore_platform",
        destination=dlt.destinations.duckdb(str(warehouse)),
        dataset_name=DATASET_NAME,
        progress="log",
    )
    load_info = pipeline.run(sofascore_files(source_dir))
    print(load_info)
    print(f"Warehouse: {warehouse}")
    print(f"Dataset:   {DATASET_NAME}")
    return pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Load Sofascore data into DuckDB via DLT")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_FIXTURES,
        help="Directory with matches.csv, players.csv, player_appearances.parquet, match_summary.parquet",
    )
    parser.add_argument(
        "--warehouse",
        type=Path,
        default=None,
        help="DuckDB file path (default: data/warehouse/schlouh.duckdb or SOFASCORE_WAREHOUSE_PATH)",
    )
    args = parser.parse_args()
    source_dir = args.source if args.source.is_absolute() else ROOT / args.source
    warehouse = args.warehouse if args.warehouse else _warehouse_path()
    if args.warehouse and not Path(args.warehouse).is_absolute():
        warehouse = ROOT / args.warehouse

    if not source_dir.is_dir():
        print(f"Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    run(source_dir, warehouse)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
