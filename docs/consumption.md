# Consumption: where to read data from

## Product path

**Dashboard reads DuckDB marts** (`analytics_marts.*` via `SCHLOUH_USE_WAREHOUSE=1`).

## Core tables (keep)

| Layer | Content |
|-------|---------|
| `data/index/` | Match + player index |
| `data/derived/` | Appearances, incidents, match scores |
| `data/processed/` | Core builds: 00–11, 15 tactical, 18 heatmaps, league_strength |
| `data/warehouse/schlouh.duckdb` | DLT + dbt serving layer |

## Not part of the core product path

Older parquet for cut features (12/13/14/16/17/19, etc.) may still sit on disk. They are **not** rebuilt or loaded into the warehouse anymore. Safe to leave; do not treat as product contract.

## Freshness

Use warehouse validation and `data/index` run metadata after `run_platform_full.sh`.
