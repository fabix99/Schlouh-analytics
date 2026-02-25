# Plan: Production-grade pipeline (collection → consumption)

Goal: Harden the Sofascore pipeline so it is **repeatable**, **observable**, **recoverable**, and **consumption-ready** — from data collection to dashboard/export.

---

## Principles

- **Repeatable**: Same inputs → same outputs; runs are scheduled or triggerable; config is explicit.
- **Observable**: Every run is logged; failures are visible and, where possible, alerted.
- **Recoverable**: Clear backfill and retention; known recovery steps for common failures.
- **Consumption-ready**: Consumers get a defined “published” surface (e.g. latest-successful or versioned snapshots) and optional freshness guarantees.

---

## Phase 1 — Configuration and environment

**Objective**: Single source of truth for environment and run mode; no implicit paths or keys.

| # | Task | Deliverable | Notes |
|---|------|-------------|--------|
| 1.1 | Define env matrix | `config/env.yaml` (or `.env.example` + doc) | Keys: `RAW_BASE`, `INDEX_PATH`, `API_BASE`, optional `API_KEY`, `LOG_DIR`, `ENV=dev|staging|prod`. |
| 1.2 | Load config in code | All entrypoints (discover, extract, run_pipeline) read base paths and API base from config/env | Prefer one small `src/config.py` or `config/load.py` used by all scripts. |
| 1.3 | Document required env | `docs/setup.md` or README section | What to set for local run vs CI vs “production”. |

**Exit criterion**: Running the pipeline with a different `RAW_BASE` (or env) works without code change.

---

## Phase 2 — Run history and observability

**Objective**: Every pipeline and key script run is recorded; failures are visible.

| # | Task | Deliverable | Notes |
|---|------|-------------|--------|
| 2.1 | Pipeline run log | Append-only `data/index/pipeline_runs.csv` (or similar) | Columns: `run_id`, `started_utc`, `ended_utc`, `steps_run`, `status` (ok/fail), `failed_step`, `env`. |
| 2.2 | Instrument orchestrator | `run_pipeline.py` writes one row per run (start; end with status) | Reuse or extend existing “runs” pattern (like extraction_progress_runs). |
| 2.3 | Optional: discover/extract run log | Same or separate log for discover + extract runs | At least: which comp/season, started/ended, success/fail. |
| 2.4 | Run summary script | `scripts/list_recent_runs.py` (or section in a small ops CLI) | Print last N runs and status for quick inspection. |

**Exit criterion**: After each pipeline run, a human or script can see “last run: time, status, failed step if any”.

---

## Phase 3 — Scheduling and alerting

**Objective**: Pipeline can run on a schedule; someone is notified when it fails.

| # | Task | Deliverable | Notes |
|---|------|-------------|--------|
| 3.1 | Schedule definition | Document or config: recommended cron (e.g. daily after matches) | e.g. `0 6 * * *` for 06:00; document in `docs/ops.md`. |
| 3.2 | Wrapper script for cron | `scripts/run_scheduled_pipeline.sh` | Sets env, runs orchestrator, exits with 0/1; logs to `data/logs/` or similar. |
| 3.3 | Failure notification | On non-zero exit: send alert (e.g. email, Slack webhook, or append to a “failures” log) | Start simple: append to `data/index/pipeline_failures.log` with timestamp and last lines of stderr. |
| 3.4 | Optional: success heartbeat | Optional “last success” file or metric | e.g. `data/index/last_successful_run.txt` with ISO timestamp. |

**Exit criterion**: Cron (or manual trigger) runs the pipeline; on failure, a defined alert path is used (even if only a log file).

---

## Phase 4 — Upstream resilience (API and schema)

**Objective**: API changes and rate limits are handled predictably; optional incremental discovery.

| # | Task | Deliverable | Notes |
|---|------|-------------|--------|
| 4.1 | Response shape checklist | `docs/api_contract.md` or list in code | Minimum expected keys for event, lineups, incidents (e.g. `event.tournament.slug`, `startTimestamp`). |
| 4.2 | Optional: contract test | Script that fetches one event and asserts required keys | Run in CI or before big runs; fail fast if API shape changed. |
| 4.3 | Circuit breaker / backoff policy | Document or implement: after N consecutive 429/5xx, pause or abort extract run | e.g. in `extract_batch.py`: if failure rate > X% in last Y requests, stop and write run as “partial_fail”. |
| 4.4 | Incremental discovery (optional) | Only discover seasons/matches that might have new data | e.g. “since last run” or “only 2025-26” flag; avoid full re-discover every time if not needed. |

**Exit criterion**: Documented contract; extract run doesn’t spin forever under repeated 429/5xx; optional incremental path documented or implemented.

---

## Phase 5 — Data lifecycle and recovery

**Objective**: Retention and backfill are defined; one known DQ gap is resolved.

| # | Task | Deliverable | Notes |
|---|------|-------------|--------|
| 5.1 | Retention policy (doc) | `docs/retention.md` | What to keep: raw (per match), derived, processed; for how long; what can be recreated. |
| 5.2 | Backfill procedure | `docs/backfill.md` | Steps to “re-run from date X” or “re-extract season Y” and then full pipeline. |
| 5.3 | Fix 15 vs 01 team names | Resolve DQ check `team_names_all_in_01` | Either align team names in build 15 with 01, or adjust DQ rule and document exception. |
| 5.4 | Optional: “golden” snapshot | Copy of last successful processed/derived to a `data/snapshots/` or timestamped dir | Enables “rollback” or A/B for consumers. |

**Exit criterion**: Retention and backfill are documented; DQ passes (or one known exception is documented); optional snapshot strategy in place.

---

## Phase 6 — Consumption surface and freshness

**Objective**: Consumers rely on a clear “published” dataset; optional freshness guarantee.

| # | Task | Deliverable | Notes |
|---|------|-------------|--------|
| 6.1 | Published path contract | Document: “consumers should read from `data/processed/` and `data/derived/`” and which artifacts are stable | Already true; make it explicit in README or `docs/consumption.md`. |
| 6.2 | Optional: “latest” symlink or manifest | e.g. `data/processed/LATEST` → timestamped dir, or `data/index/latest_successful_run.json` with paths and timestamp | Allows “point in time” reads without changing app code. |
| 6.3 | Freshness check (optional) | In DQ or validate: “no artifact older than N hours” for critical tables | Fail or warn if e.g. `matches.csv` or `02_match_summary` is stale. |

**Exit criterion**: Consumption is documented; optional latest/snapshot and freshness check are in place if desired.

---

## Phase 7 — Testing and CI (optional but recommended)

**Objective**: Critical paths are automated in CI; regressions are caught early.

| # | Task | Deliverable | Notes |
|---|------|-------------|--------|
| 7.1 | Smoke test | One pipeline run on a tiny subset (e.g. one competition, one season) in CI | Use small config or env; assert pipeline exits 0 and key artifacts exist. |
| 7.2 | Validation in CI | Run `validate_data.py` (and optionally `dq_check.py`) on CI artifacts | Ensures schema and DQ rules are kept. |
| 7.3 | Optional: API contract in CI | Run contract test (Phase 4) in CI | Catches API shape changes. |

**Exit criterion**: CI runs pipeline (or a minimal slice) and validation; failures block merge or are clearly reported.

---

## Execution order and dependencies

```
Phase 1 (config/env)     → required for all
Phase 2 (run history)    → required for observability and alerting
Phase 3 (schedule/alert) → depends on Phase 2
Phase 4 (API/schema)     → independent; can run in parallel with 2/3
Phase 5 (lifecycle)      → independent; fix 5.3 anytime
Phase 6 (consumption)    → after 1–2; optional snapshot ties to 5.4
Phase 7 (CI)             → after 1; optional
```

**Suggested order**: 1 → 2 → 3 (core ops), then 4 and 5 in parallel, then 6 and 7.

---

## Success criteria for “perfect” operational process

- [x] **Config**: One place to set env and paths (`config/env.yaml`, `src/config.py`, `docs/setup.md`).
- [x] **Observability**: Pipeline run log and list script (`pipeline_runs.csv`, `scripts/list_recent_runs.py`).
- [x] **Scheduling**: Cron doc and wrapper with failure log (`docs/ops.md`, `run_scheduled_pipeline.sh`).
- [x] **Resilience**: API contract + contract test + circuit breaker (`docs/api_contract.md`, `check_api_contract.py`, `extract_batch.py`).
- [x] **Lifecycle**: Retention and backfill docs; 15 vs 01 as WARN (`docs/retention.md`, `docs/backfill.md`, DQ).
- [x] **Consumption**: Consumption doc, latest_successful_run.json, freshness warn (`docs/consumption.md`, DQ).
- [x] **Quality**: Smoke test and CI workflow (`scripts/smoke_test.sh`, `.github/workflows/ci.yml`).

When all checkboxes above are met, the process is **production-grade** from collection to consumption.
