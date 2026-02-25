# Setup and environment

## Required

- **Python 3.9+** with pandas, pyyaml, requests (and other deps from the project).
- **Project root**: All paths are relative to the repo root unless overridden.

## Configuration

Paths and API base are defined in **`config/env.yaml`** and can be overridden by environment variables so you can run the same code with different roots (e.g. CI, staging, production).

| Key in `env.yaml` | Env var override | Default | Description |
|-------------------|------------------|---------|-------------|
| `raw_base` | `SOFASCORE_RAW_BASE` | `data/raw` | Root for raw scraped match data. |
| `index_path` | `SOFASCORE_INDEX_PATH` | `data/index/matches.csv` | Matches index file. |
| `api_base` | `SOFASCORE_API_BASE` | `https://api.sofascore.com/api/v1` | Sofascore API base URL. |
| `log_dir` | `SOFASCORE_LOG_DIR` | `data/logs` | Directory for pipeline and scheduled run logs. |
| `derived_dir` | `SOFASCORE_DERIVED_DIR` | `data/derived` | Derived artifacts (player_appearances, etc.). |
| `processed_dir` | `SOFASCORE_PROCESSED_DIR` | `data/processed` | Processed build outputs (00–16). |
| `index_dir` | `SOFASCORE_INDEX_DIR` | `data/index` | Index directory (progress, runs, etc.). |
| `env` | `ENV` | `dev` | Run mode: `dev`, `staging`, or `prod`. |

Paths in `env.yaml` are **relative to the project root**. To use an absolute path, set the corresponding env var (e.g. `export SOFASCORE_RAW_BASE=/mnt/data/sofascore/raw`).

## Local run

```bash
cd /path/to/Sofascore-Scrapping
python src/discover_matches.py spain-laliga --seasons 2025-26
python src/extract_batch.py spain-laliga 2025-26
python scripts/run_pipeline.py
```

No env vars are required for default behaviour; `config/env.yaml` is used if present.

## CI / alternate root

To run with a different data root (e.g. CI or a mounted volume):

```bash
export SOFASCORE_RAW_BASE=/ci/raw
export SOFASCORE_INDEX_PATH=/ci/index/matches.csv
export SOFASCORE_LOG_DIR=/ci/logs
export ENV=ci
python scripts/run_pipeline.py
```

## Production

- Set `ENV=prod` when running in production.
- Point `SOFASCORE_LOG_DIR` to a persistent log directory.
- Use `scripts/run_scheduled_pipeline.sh` for cron; see `docs/ops.md`.
