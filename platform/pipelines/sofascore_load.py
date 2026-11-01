#!/usr/bin/env python3
"""
DLT pipeline: load Schlouh grain + processed tables into DuckDB.

Default source mode is the full local lake:
  - data/index/matches.csv, players.csv
  - data/derived/*.parquet (appearances, incidents, scores)
  - data/processed/*.parquet (dashboard-serving tables)

Fixture / live_source dirs still work for CI and e2e slices.

Usage:
  python platform/pipelines/sofascore_load.py
  python platform/pipelines/sofascore_load.py --source platform/fixtures
  python platform/pipelines/sofascore_load.py --mode full
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import dlt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WAREHOUSE = ROOT / "data" / "warehouse" / "schlouh.duckdb"
DATASET_NAME = "raw_sofascore"

# Preserve source column names (dashboard expects parquet field names, not snake_case).
os.environ.setdefault("SCHEMA__NAMING", "direct")

# Dashboard-facing processed artifacts (filename stem -> table name)
PROCESSED_TABLES = {
    "00_match_scores_full": "match_scores_full",
    "01_team_season_stats": "team_season_stats",
    "02_match_summary": "match_summary",
    "03_player_season_stats": "player_season_stats",
    "04_player_career_stats": "player_career_stats",
    "05_competition_benchmarks": "competition_benchmarks",
    "06_player_percentile_ranks": "player_percentile_ranks",
    "07_player_rolling_form": "player_rolling_form",
    "08_player_scouting_profiles": "player_scouting_profiles",
    "09_player_progression": "player_progression",
    "10_player_consistency": "player_consistency",
    "11_player_opponent_context_summary": "player_opponent_context_summary",
    "15_team_tactical_profiles": "team_tactical_profiles",
    "18_heatmap_points": "heatmap_points",
    "league_strength": "league_strength",
}


def _warehouse_path() -> Path:
    env = os.environ.get("SOFASCORE_WAREHOUSE_PATH")
    if env:
        p = Path(env)
        return p if p.is_absolute() else ROOT / p
    return DEFAULT_WAREHOUSE


def _read_table(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing source file: {path}")
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file type: {path}")
    for col in ("match_id",):
        if col in df.columns:
            df[col] = df[col].astype(str)
    if "player_id" in df.columns:
        df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce")
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
    return df.where(pd.notnull(df), None).to_dict(orient="records")


def _resource_from_path(name: str, path: Path, primary_key=None):
    kwargs = {"name": name, "write_disposition": "replace"}
    if primary_key is not None:
        kwargs["primary_key"] = primary_key

    @dlt.resource(**kwargs)
    def _res():
        yield _read_table(path)

    return _res


@dlt.source(name="sofascore_files")
def sofascore_files(source_dir: Path | None, mode: str):
    """Load either a slice directory or the full local lake into DuckDB."""
    resources = []

    if mode == "slice":
        assert source_dir is not None
        resources.extend(
            [
                _resource_from_path("matches", source_dir / "matches.csv", "match_id"),
                _resource_from_path("players", source_dir / "players.csv", "player_id"),
                _resource_from_path(
                    "player_appearances",
                    source_dir / "player_appearances.parquet",
                    ["match_id", "player_id"],
                ),
                _resource_from_path("match_summary", source_dir / "match_summary.parquet", "match_id"),
            ]
        )
        return resources

    # full lake
    index_dir = ROOT / "data" / "index"
    derived_dir = ROOT / "data" / "derived"
    processed_dir = ROOT / "data" / "processed"

    resources.append(_resource_from_path("matches", index_dir / "matches.csv", "match_id"))
    resources.append(_resource_from_path("players", index_dir / "players.csv", "player_id"))
    resources.append(
        _resource_from_path(
            "player_appearances",
            derived_dir / "player_appearances.parquet",
            ["match_id", "player_id"],
        )
    )
    if (derived_dir / "player_incidents.parquet").exists():
        resources.append(
            _resource_from_path("player_incidents", derived_dir / "player_incidents.parquet")
        )
    if (derived_dir / "match_scores.parquet").exists():
        resources.append(
            _resource_from_path("match_scores", derived_dir / "match_scores.parquet", "match_id")
        )

    for stem, table in PROCESSED_TABLES.items():
        path = processed_dir / f"{stem}.parquet"
        if path.exists():
            resources.append(_resource_from_path(table, path))

    return resources


def run(source_dir: Path | None, warehouse: Path, mode: str) -> dlt.Pipeline:
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    pipeline = dlt.pipeline(
        pipeline_name="sofascore_platform",
        destination=dlt.destinations.duckdb(str(warehouse)),
        dataset_name=DATASET_NAME,
        progress="log",
    )
    load_info = pipeline.run(sofascore_files(source_dir, mode))
    print(load_info)
    print(f"Warehouse: {warehouse}")
    print(f"Dataset:   {DATASET_NAME}")
    print(f"Mode:      {mode}")
    return pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Load Sofascore data into DuckDB via DLT")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Slice directory (fixtures/live_source). Implies --mode slice.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "slice"],
        default=None,
        help="full = data/index+derived+processed; slice = --source dir",
    )
    parser.add_argument("--warehouse", type=Path, default=None)
    args = parser.parse_args()

    mode = args.mode
    source_dir = None
    if args.source is not None:
        mode = "slice"
        source_dir = args.source if args.source.is_absolute() else ROOT / args.source
    if mode is None:
        mode = "full"

    warehouse = args.warehouse if args.warehouse else _warehouse_path()
    if args.warehouse and not Path(args.warehouse).is_absolute():
        warehouse = ROOT / args.warehouse

    if mode == "slice" and (source_dir is None or not source_dir.is_dir()):
        print(f"Slice source directory not found: {source_dir}", file=sys.stderr)
        return 1

    run(source_dir, warehouse, mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
