# Sofascore scraping

Structured scraping of Sofascore for football analytics.

## Folder structure

| Path | Purpose |
|------|---------|
| `data/raw/` | Raw scraped outputs (by match, by source, or by run). |
| `data/processed/` | Cleaned, merged, or analysis-ready datasets. |
| `src/` | Scripts and code used for scraping and processing. |
| `config/` | Configuration (URLs, IDs, options). |
| `docs/` | Documentation; see `docs/intention.md` for goals and scope. |
| `archive/` | Archived QA reports and section-specific test scripts (see `CLEANUP_AUDIT.md`). |

## Operational checklist (stable workflow)

1. **Discover** — Update match index: `python src/discover_matches.py <competition> --seasons 2025-26`
2. **Extract** — Fetch raw match data: `python src/extract_batch.py <competition> <season>`
   - For **Scouts heatmaps** (season-average positioning), add `--extract-player-maps` so each match gets heatmap/shotmap data; then the pipeline (step 18) builds the heatmap parquet.
3. **Orchestrator** — Rebuild derived + processed + run quality gates: `python scripts/run_pipeline.py` (includes step 18: player match maps / heatmap parquet)
4. **DQ** — `python scripts/build/dq_check.py` (run by orchestrator; use remediation hint if match-id sync fails)
5. **Validate** — `python scripts/validate_data.py` (run by orchestrator)
6. **Dashboard / export** — Use `data/processed/` and `data/derived/` for Streamlit dashboard or export scripts.  
   **Single app:** Run `streamlit run dashboard/app.py` for the full platform (scouting, tactics, match review). To deploy and share one URL (e.g. Streamlit Cloud), see **`docs/DEPLOY_STREAMLIT_CLOUD.md`**.

See `docs/fixing_validation_failures.md` when validation or dq_check fails. For environment and path overrides, see **`docs/setup.md`**. For where to read data (dashboard/export), see **`docs/consumption.md`**.

## Secrets

Use **environment variables** for any app secrets. If you use `.streamlit/secrets.toml` for local overrides, keep only placeholders there and **never commit it**; it is in `.gitignore`. See `docs/setup.md` for configuration.

## Publishing to GitHub

Before your first push (or before sharing your repo/URL for job applications), see **`docs/PRODUCTION_CHECKLIST.md`**. Also check **`docs/setup.md`** and **`.gitignore`** for secrets, user data, and first-run setup. There is no `PREP_FOR_GITHUB.md`; use the Operational checklist above and the First run section.

## First run / forks (no data in repo)

This repo does **not** include `data/raw/`, `data/derived/`, `data/processed/`, or `data/index/` so it stays small. After cloning or forking you need to create data once. See **`.gitignore`** for excluded paths.

1. **Minimal (dashboard works with a few matches):**  
   `python scripts/quickstart_data.py`  
   This discovers one competition, extracts a small number of matches, runs the pipeline, and leaves you with enough data to run the dashboard.

2. **Full run:**  
   Run discover → extract → pipeline for the competitions and seasons you want (see Operational checklist above).

## Intention

See **`docs/intention.md`** for what we want to capture and how the project is scoped (no implementation details).
