# Production Readiness Review — Sofascore Scraping

This document summarizes the result of a full edit of the repository against production-grade criteria (config, observability, scheduling, resilience, lifecycle, consumption, testing).

---

## Executive summary

| Area | Status | Notes |
|------|--------|--------|
| **Configuration** | ✅ Ready | `config/env.yaml` + env overrides; `src/config.py` single source of truth; `docs/setup.md` documents all keys. |
| **Observability** | ✅ Ready | `pipeline_runs.csv`, `list_recent_runs.py`, run_id and failed_step recorded. |
| **Scheduling & alerting** | ✅ Ready | `run_scheduled_pipeline.sh`, `docs/ops.md`, failure log + last success file. |
| **API resilience** | ✅ Ready | `docs/api_contract.md`, `check_api_contract.py`, circuit breaker in `extract_batch.py` (6 consecutive failures). |
| **Lifecycle** | ✅ Ready | `docs/retention.md`, `docs/backfill.md`; DQ 15 vs 01 is WARN with remediation. |
| **Consumption** | ✅ Ready | `docs/consumption.md`, `latest_successful_run.json`, optional freshness in DQ. |
| **Testing / CI** | ✅ Ready | `smoke_test.sh` (config + API contract + short pipeline if index exists), `.github/workflows/ci.yml`. |
| **Path consistency** | ⚠️ Addressed | Build scripts and `validate_data.py` now prefer central config so CI/prod overrides work everywhere. |

**Verdict:** The project is **production-ready** for running from the repo root with default or env-overridden paths. The plan in `docs/plan_production_grade.md` is fully implemented; the only follow-up was ensuring all components (build steps, DQ, validation) use the same config for paths so that alternate roots (CI, staging, prod volumes) behave consistently.

---

## What was verified

### 1. Configuration and environment

- **`config/env.yaml`** — Present with `raw_base`, `index_path`, `api_base`, `log_dir`, `derived_dir`, `processed_dir`, `index_dir`, `env`.
- **`src/config.py`** — Loads YAML and overrides with `SOFASCORE_*` and `ENV`; exports `ROOT`, `RAW_BASE`, `INDEX_PATH`, `API_BASE`, `LOG_DIR`, `DERIVED_DIR`, `PROCESSED_DIR`, `INDEX_DIR`, `ENV`.
- **Entrypoints** — `run_pipeline.py`, `discover_matches.py`, `extract_batch.py`, `build_player_appearances.py`, `progress.py` use config for paths/API base.
- **`docs/setup.md`** — Documents all keys, env overrides, local/CI/production usage.

### 2. Run history and observability

- **`data/index/pipeline_runs.csv`** — Append-only; columns: `run_id`, `started_utc`, `ended_utc`, `steps_run`, `status`, `failed_step`, `env`.
- **`run_pipeline.py`** — Writes one row per run (start + update on end); writes `latest_successful_run.json` on success.
- **`scripts/list_recent_runs.py`** — Uses `INDEX_DIR` from config; prints last N runs and status.

### 3. Scheduling and alerting

- **`docs/ops.md`** — Cron example (e.g. `0 6 * * *`), wrapper script, failure log, success heartbeat.
- **`scripts/run_scheduled_pipeline.sh`** — Sets cwd, logs to `SOFASCORE_LOG_DIR`/default, appends to `pipeline_failures.log` on non-zero exit, writes `last_successful_run.txt` on success.

### 4. Upstream resilience (API and schema)

- **`docs/api_contract.md`** — Documents required keys for event, lineups, incidents, statistics.
- **`scripts/check_api_contract.py`** — Fetches one event (and lineups/incidents), asserts required keys; uses `API_BASE` from config.
- **`src/extract_batch.py`** — Circuit breaker: stops after 6 consecutive failed matches (`CONSECUTIVE_FAILURES_BREAK`).

### 5. Data lifecycle and recovery

- **`docs/retention.md`** — What to keep (raw, index, derived, processed, logs); what can be recreated.
- **`docs/backfill.md`** — Re-run pipeline from step; re-extract competition/season; full pipeline.
- **DQ `team_names_all_in_01`** — Implemented as **WARN** with remediation (re-run from step 01); documented in retention.

### 6. Consumption and freshness

- **`docs/consumption.md`** — Published paths (`data/processed/`, `data/derived/`, index files); latest run files; optional freshness.
- **`data/index/latest_successful_run.json`** — Written by `run_pipeline.py` on success.
- **DQ** — Optional 48h freshness warn for `02_match_summary` in `dq_check.py`.

### 7. Testing and CI

- **`scripts/smoke_test.sh`** — Config load check, API contract check, optional short pipeline (index → step 00) when index exists.
- **`.github/workflows/ci.yml`** — Runs on push/PR to main/master; Python 3.10; installs deps; runs smoke test with `SOFASCORE_LOG_DIR` set.

### 8. Documentation and references

- **README** — Checklist, first run (quickstart + full), links to `docs/intention.md`, `docs/setup.md`, `docs/consumption.md`, `docs/fixing_validation_failures.md`.
- **`docs/intention.md`** — Goals and scope (no implementation).
- **`docs/fixing_validation_failures.md`** — Remediation for DQ/validation failures (match-id sync, extraction progress, player_appearances, etc.).
- **`scripts/fix_extraction_progress.py`** — Present (referenced in fixing doc).

---

## Gaps addressed in this review

1. **Path consistency**  
   - **Issue:** `scripts/build/utils.py` and `scripts/validate_data.py` used hardcoded `ROOT / "data" / ...` paths, so `SOFASCORE_RAW_BASE`, `SOFASCORE_PROCESSED_DIR`, etc. were not respected by build steps or validation when running in CI or with custom data roots.  
   - **Change:** `utils.py` now prefers `src.config` for `RAW_BASE`, `DERIVED_DIR`, `PROCESSED_DIR`, `INDEX_DIR` (with fallback to repo-relative paths). `validate_data.py` now prefers config for `INDEX`, `DERIVED`, `PROCESSED`, `RAW` so the same overrides apply.

2. **Secrets / .env**  
   - **Issue:** `.gitignore` did not list `.env`; plan mentioned optional `API_KEY`.  
   - **Change:** `.env` added to `.gitignore`. No API key is required for the current public API; if you add one later, use env vars or a local `.env` (not committed).

---

## Optional next steps (not required for production)

- **Pin dependency versions** — `requirements.txt` uses lower bounds (e.g. `pandas>=2.0.0`). For strict reproducibility, consider pinning exact versions or using a lock file.
- **`.env.example`** — Add a file listing optional env vars (e.g. `SOFASCORE_RAW_BASE`, `SOFASCORE_INDEX_PATH`, `ENV`) with no secrets, so new deployers know what can be overridden.
- **Slack/webhook on failure** — `run_scheduled_pipeline.sh` has a comment for adding a webhook; implement if you want immediate alerts.
- **Golden snapshots** — Documented in retention; automate a post-run copy to `data/snapshots/<timestamp>/` if you need point-in-time rollback.

---

## How to run in production

1. Set environment (e.g. `ENV=prod`, `SOFASCORE_LOG_DIR` to a persistent path).
2. Use **`scripts/run_scheduled_pipeline.sh`** from cron (see `docs/ops.md`).
3. Monitor **`data/index/pipeline_failures.log`** and **`data/index/last_successful_run.txt`** (or `latest_successful_run.json`) for freshness.
4. Use **`scripts/list_recent_runs.py`** to inspect run history.

Data paths can be overridden via `config/env.yaml` or `SOFASCORE_*` env vars so that raw/processed/derived/index live on the correct volumes; all pipeline steps and validation now respect these when config is available.
