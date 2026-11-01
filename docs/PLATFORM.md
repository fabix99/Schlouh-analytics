# Schlouh data platform

**Yes — still Python.** DLT, Airflow, extractors, Streamlit, and most tooling are Python. dbt adds SQL models/tests on the warehouse.

**Canonical production path:**

```text
Sofascore API
    → DLT extract resources (Python) and/or file extract → data/raw
    → Python builds (remaining feature tables → parquet)
    → DLT load into DuckDB (raw_sofascore.*)
    → dbt transforms + serving marts (analytics_marts.*)
    → Streamlit reads DuckDB marts only
    → Airflow orchestrates the path
```

## Honest scope

| Layer | Role |
|-------|------|
| **Extract** | **DLT** `platform/pipelines/sofascore_extract.py` (API → DuckDB) + legacy `extract_batch` (API → `data/raw`) |
| **Core transforms** | **dbt SQL** for player season stats, match summary, team season rollups, scouting profiles (from appearances) |
| **Feature transforms** | Python `scripts/build/*` for remaining derived tables (percentiles, rolling form, etc.) → parquet → DLT |
| **ELT into warehouse** | **DLT** loads index + derived + processed into **DuckDB** |
| **Serving contract** | **dbt** publishes tested `analytics_marts.*` (dashboard reads these) |
| **Orchestration** | **Airflow** DAG `schlouh_platform_pipeline` |
| **AI bridge** | DuckDB FTS over marts (`platform/ai/`) |
| **CI** | Fixture slice: DLT + dbt core marts (`use_processed_sources: false`) |

So: the **product path is consistently warehouse-backed** (DLT → DuckDB → dbt → app). Core scouting marts are computed in dbt; remaining feature tables still land via Python builds then DLT.

## Commands

```bash
# Production refresh (existing extracts → warehouse → app)
bash platform/scripts/run_platform_full.sh
# or skip re-running pandas if processed/ already fresh:
bash platform/scripts/run_platform_full.sh --skip-pandas

# CI / fixture slice
bash platform/scripts/run_platform.sh

# Live Sofascore E2E (small N)
python platform/scripts/run_e2e_live.py --limit 2

# DLT live extract (API → DuckDB dataset raw_sofascore_api)
python platform/pipelines/sofascore_extract.py \
  --competition england-premier-league --season 2025-26 --limit 2

# Airflow
bash platform/scripts/setup_airflow.sh
source platform/airflow_home/.env
airflow dags test schlouh_platform_pipeline $(date -u +%Y-%m-%d)
```

Streamlit defaults to DuckDB marts (`SCHLOUH_USE_WAREHOUSE=1`). Opt out with `SCHLOUH_USE_WAREHOUSE=0` or `SCHLOUH_ALLOW_PARQUET_FALLBACK=1`.

## CV framing (accurate)

> Built a football scouting data platform in Python: **DLT** extracts and loads Sofascore data into **DuckDB**, **dbt** runs tested SQL transforms for core player/match/team marts, **Airflow** orchestrates refreshes, and Streamlit serves from the warehouse—with CI on a fixture slice.

Shorter bullets:

- DLT → DuckDB ELT for Sofascore lake + live API extract resources  
- dbt SQL marts (player season / match / team / scouting) with tests  
- Airflow DAG + Streamlit on warehouse marts (CI fixture path)
