# Sofascore scraping (Schlouh Analytics)

Football scouting data platform: Sofascore extracts → local lake → DuckDB warehouse → Streamlit.

**Roadmap:** [`PLAN.md`](PLAN.md)  
**Architecture:** [`docs/PLATFORM.md`](docs/PLATFORM.md)

## One product path (not two)

There is **one** refresh path:

```text
discover / extract (best-effort; never wipe existing raw)
  → Python feature builds (scripts/build + run_pipeline, inside the platform script)
  → DLT load into DuckDB
  → dbt marts + tests
  → Streamlit reads DuckDB
```

Command:

```bash
bash platform/scripts/run_platform_full.sh
# or, if processed tables are already fresh:
bash platform/scripts/run_platform_full.sh --skip-pandas
```

Parquet under `data/processed/` is an **intermediate** of that path, not a second product. Do not run “parquet-only dashboard” as the happy path.

Sofascore live API often returns **403**. Existing `data/raw` is sacred — never delete it to “simplify.”

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-platform.txt
bash platform/scripts/run_platform_full.sh --skip-pandas   # needs existing data/
streamlit run dashboard/app.py
```

Airflow (after Phase 1 in `PLAN.md`): prefer **one** setup — Docker Compose profile `airflow` *or* `platform/scripts/setup_airflow.sh` — document only the one you use.

## Folder structure

| Path | Purpose |
|------|---------|
| `data/raw/` | Precious scraped match files (do not delete) |
| `data/derived/`, `data/processed/` | Intermediate build outputs |
| `data/warehouse/` | DuckDB warehouse |
| `platform/` | DLT, dbt, Airflow DAG, AI index |
| `src/` | Discover + extract |
| `scripts/build/` | Feature builders used by the platform path |
| `dashboard/` | Streamlit scouting app |
| `config/` | Competitions + env paths |
| `docs/` | Setup, ops, platform notes |

## Operational checklist

1. **Discover** — `python src/discover_matches.py <competition> --seasons 2025-26`
2. **Extract** — `python src/extract_batch.py <competition> <season>` (add `--extract-player-maps` for heatmaps). Skip existing matches by default. Never `--force` unless you mean it.
3. **Refresh warehouse** — `bash platform/scripts/run_platform_full.sh`
4. **Validate** — `python platform/scripts/validate_warehouse_full.py`
5. **Dashboard** — `streamlit run dashboard/app.py` (DuckDB marts by default)

Optional DQ: `python scripts/build/dq_check.py` / `python platform/scripts/dq_raw_extracts.py <competition> <season>`

## Secrets

Use environment variables. Do not commit `.streamlit/secrets.toml` with real secrets.

## Intention

See `docs/intention.md` for what we capture and scope.
