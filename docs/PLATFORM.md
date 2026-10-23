# Schlouh data platform

Modern platform layer for Sofascore → analytics, aligned with how a data platform team ships ELT + transforms + orchestration + CI.

```text
platform/fixtures (or local extracts)
        │
        ▼
   DLT pipeline  ──►  DuckDB warehouse (raw_sofascore.*)
        │
        ▼
   dbt models    ──►  analytics_staging.* / analytics_marts.*
        │
        ▼
   AI index      ──►  ai.retrieval_documents (DuckDB FTS)  ← RAG-ready
        │
        ▼
   Airflow DAG   ──►  schlouh_platform_pipeline (dlt → dbt → validate → AI)
        │
        ▼
   CI + Docker   ──►  reproducible build + tests
```

## Why DuckDB (not Snowflake)

Same warehouse / SQL / dbt workflow as Snowflake, runnable locally and in CI with zero cloud cost. Swapping the dbt profile / DLT destination to Snowflake later is a config change, not a rewrite.

## What’s in the slice

| Layer | Tool | Content |
|-------|------|---------|
| Ingest | **DLT** | `matches`, `players`, `player_appearances`, `match_summary` → `raw_sofascore` |
| Warehouse | **DuckDB** | `data/warehouse/schlouh.duckdb` |
| Transforms | **dbt** | staging views + marts: `mart_match_summary`, `mart_player_season_stats`, `mart_player_scouting_profiles` |
| Orchestration | **Airflow** | DAG `schlouh_platform_pipeline` (SequentialExecutor locally / Compose) |
| AI bridge | **DuckDB FTS** | `ai.retrieval_documents` over player + match marts (RAG-ready, no fake chatbot) |
| CI | **GitHub Actions** | `.github/workflows/platform.yml` — fixtures only, no live API |
| Containers | **Docker Compose** | `platform` one-shot; `--profile airflow` for UI |

## What’s intentionally still Python (legacy pipeline)

Heatmaps/shotmaps, full percentile ladders, tactical profiles, rolling form, market/contract, and the Streamlit dashboard still use the existing `scripts/build/00–19` + parquet path. The platform slice proves the modern stack on the **core scouting path**; remaining steps migrate incrementally.

## Commands

From project root (with `.venv` and `requirements-platform.txt` installed):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-platform.txt

# Full slice (DLT → dbt → validate → AI index)
bash platform/scripts/run_platform.sh

# AI retrieval demo
python platform/ai/query_retrieval.py "Standard Liège" --limit 5
```

### Airflow (local)

```bash
bash platform/scripts/setup_airflow.sh
source platform/airflow_home/.env
airflow dags test schlouh_platform_pipeline $(date -u +%Y-%m-%d)
# Optional UI: airflow standalone
```

### Docker

```bash
# One-shot platform pipeline
docker compose run --rm platform

# Airflow UI (http://localhost:8080 — admin / admin)
docker compose --profile airflow up -d
```

Regenerate fixtures from full local data (optional):

```bash
python platform/scripts/build_fixtures.py
```

## CV / interview framing (honest)

> End-to-end football analytics platform: Sofascore extracts loaded with **DLT** into a **DuckDB** warehouse, modelled and tested with **dbt**, orchestrated with **Airflow**, with an **AI-ready retrieval layer** over scouting marts, gated by **CI** and runnable via **Docker**. Scouting product sits on top; advanced geospatial/tactical features remain in the Python pipeline pending migration.
