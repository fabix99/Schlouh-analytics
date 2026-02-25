# What is excluded from GitHub (publish cleanup)

This page lists (1) **paths in `.gitignore`** that are not published, and (2) **docs and scripts** and what belongs on GitHub vs internal only.

---

## Paths in .gitignore (do not publish)

### Build and runtime (do not publish)

| Path | Reason |
|------|--------|
| `web/dist/` | Build output; regenerate with `npm run build`. |
| `web/node_modules/` | Dependencies; regenerate with `npm install`. |
| `web/*.tsbuildinfo`, `web/**/*.tsbuildinfo` | TypeScript incremental build cache. |
| `web/vite.config.d.ts` | Generated from `vite.config.ts`. |

### Local and secrets

| Path | Reason |
|------|--------|
| `.env`, `.env.local` | Optional overrides; may contain secrets. |
| `.cursor/` | Cursor IDE project state. |
| `.streamlit/` | Streamlit local config (e.g. theme). |
| `.idea/`, `.vscode/` | IDE settings. |

### Data (repo stays small)

| Path | Reason |
|------|--------|
| `data/raw/` | Raw scraped match data; large. |
| `data/derived/` | Built from raw; regenerate with pipeline. |
| `data/processed/` | Build steps 00–16; regenerate with pipeline. |
| `data/logs/` | Pipeline and cron logs. |
| `data/index/` | All index files (matches.csv, players.csv, pipeline_runs, etc.); generated or runtime. |

After cloning, run `python scripts/quickstart_data.py` or the full discover → extract → pipeline flow to create data. For CI, use `SOFASCORE_INDEX_PATH` (and optional fixture under `ci/fixtures/`) if you add a small index for tests.

### OS and Python

- `.DS_Store`, `Thumbs.db`
- `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `env/`

---

If you already committed any of these (e.g. before adding them to `.gitignore`), remove from the index but keep on disk:

```bash
git rm -r --cached data/index/   # example
git rm -r --cached web/node_modules/
```

Then commit the change and push.

---

## Docs and scripts: what belongs on GitHub

### Docs **published** (keep on GitHub)

| Doc | Purpose |
|-----|---------|
| `README.md` | Project overview, checklist, first run. |
| `docs/intention.md` | Goals and scope. |
| `docs/setup.md` | Environment and paths. |
| `docs/consumption.md` | Where to read data (processed/derived). |
| `docs/retention.md`, `docs/backfill.md` | Data lifecycle and recovery. |
| `docs/ops.md` | Scheduling and alerting. |
| `docs/api_contract.md`, `docs/api_endpoints.md` | API reference. |
| `docs/fixing_validation_failures.md` | Remediation for DQ/validation. |
| `docs/plan_production_grade.md` | Production plan (reference). |
| `docs/PRODUCTION_READINESS.md` | One-time readiness audit. |
| `docs/PUBLISH.md` | This file. |
| `config/README.md`, `dashboard/README.md`, `export/README.md`, `web/README.md`, `viz/README.md` | Per-folder readmes. |

### Internal docs (deleted after use)

These were one-off / internal and have been removed from the repo: dashboard audit (CAO), data analysis snapshot, and the 2025-26 focus runbook. Nothing in the published docs or pipeline depends on them.

### Scripts: all **published** (core + optional helpers)

| Script | Role |
|--------|------|
| `scripts/run_pipeline.py`, `scripts/smoke_test.sh`, `scripts/run_scheduled_pipeline.sh` | **Core** — pipeline and CI. |
| `scripts/validate_data.py`, `scripts/check_api_contract.py`, `scripts/list_recent_runs.py` | **Core** — validation and ops. |
| `scripts/build/*.py` (00–16, dq_check, utils) | **Core** — build steps. |
| `scripts/quickstart_data.py`, `scripts/fix_extraction_progress.py` | **Core** — first run and remediation. |
| `scripts/validate_competition_ids.py`, `scripts/build_derived_player_csvs.py` | **Helpers** — referenced in config/README and fixing_validation_failures. |
| `scripts/full_progress_table.py`, `scripts/assess_data_gaps.py` | **Optional** — progress/gap reports (used from internal runbook). |
| `scripts/run_2025_26_focus.sh`, `scripts/run_extraction_top5_ucl.sh` | **Optional** — example workflows for a set of leagues; keep as examples or remove if you prefer a minimal repo. |

If you want a **minimal** publish, you could delete the two optional shell scripts and the two optional Python helpers; the main README and pipeline do not depend on them.
