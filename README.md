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
3. **Orchestrator** — Rebuild derived + processed + run quality gates: `python scripts/run_pipeline.py`
4. **DQ** — `python scripts/build/dq_check.py` (run by orchestrator; use remediation hint if match-id sync fails)
5. **Validate** — `python scripts/validate_data.py` (run by orchestrator)
6. **Dashboard / export** — Use `data/processed/` and `data/derived/` for Streamlit dashboard or export scripts.

See `docs/fixing_validation_failures.md` when validation or dq_check fails. For environment and path overrides, see **`docs/setup.md`**. For where to read data (dashboard/export), see **`docs/consumption.md`**.

## Publishing to GitHub

Before your first push, see **`PREP_FOR_GITHUB.md`** for a checklist (secrets, user data, large files, and first commit).

## First run / forks (no data in repo)

This repo does **not** include `data/raw/`, `data/derived/`, `data/processed/`, or `data/index/` so it stays small. After cloning or forking you need to create data once. For a full list of what is excluded from the repo when publishing, see **`docs/PUBLISH.md`**.

1. **Minimal (dashboard works with a few matches):**  
   `python scripts/quickstart_data.py`  
   This discovers one competition, extracts a small number of matches, runs the pipeline, and leaves you with enough data to run the dashboard.

2. **Full run:**  
   Run discover → extract → pipeline for the competitions and seasons you want (see Operational checklist above).

## Intention

See **`docs/intention.md`** for what we want to capture and how the project is scoped (no implementation details).
