# Schlouh Analytics — Platform Plan (v1)

**Product:** Football scouting analytics — Sofascore lake → DuckDB warehouse → Streamlit.  
**Stack:** Python, DLT, DuckDB, dbt, Streamlit; Airflow for scheduled refresh (in progress).  
**Status:** Lake + warehouse + core dashboard are live. Calculation/DQ validation is green. **Airflow product DAG is the main remaining platform work.**

Mark items `[x]` when done. Prefer phases in order.

---

## Product (v1)

### App pages

Discover · Profile · Compare · Shortlist · Teams

### Data scope

| | |
|--|--|
| **Seasons** | `2024-25`, `2025-26` |
| **Domestic leagues** | Premier League, La Liga, Serie A, Ligue 1, Bundesliga, Primeira Liga, Belgian Pro League, Eredivisie, Süper Lig, Saudi Pro League, Brasileirão |
| **UEFA** | Champions League, Europa League, Conference League |

### Refresh path (one path only)

```
data/raw → derived → processed (pandas) → DLT → DuckDB → dbt marts → validate → AI index → Streamlit
```

Command: `bash platform/scripts/run_platform_full.sh`  
Offline warehouse-only: `bash platform/scripts/run_platform_full.sh --skip-pandas`

Streamlit reads **DuckDB marts** (not parquet as the happy path).

---

## Hard rules

1. **Existing extracts are sacred** — never delete or overwrite `data/raw` (or wipe the index) as part of automation.
2. **Extract is best-effort** — Sofascore may return 403; skip matches that already have lineups; no `--force` by default.
3. **Warehouse rebuild ≠ re-scrape** — DLT/dbt refresh from local lake files must work with the API down.
4. **Soft-fail live API** — scheduled jobs must not hard-fail the whole refresh on 403.
5. **Validate before claiming go-live** — DQ + calculation checks green.

### Sofascore pacing (practical)

Bulk extract: **10–15 seconds between matches** (~40–60 HTTP requests/min). Faster pacing tends to trigger sustained 403. After a 403 streak, wait before retrying.

---

## Architecture

| Layer | Role |
|-------|------|
| `data/raw/` | Per-match Sofascore extracts |
| `data/derived/` | Appearances, incidents, scores |
| `data/processed/` | Feature tables (pandas builders) |
| DLT → `raw_sofascore.*` | Bronze load into DuckDB |
| dbt `analytics_marts.*` | Gold marts for the app |
| Streamlit `dashboard/` | Product UI |
| Airflow | Schedule / orchestrate the refresh (next) |

```
Sofascore Scrapping/
├── PLAN.md
├── README.md
├── config/
├── data/                  # gitignored; precious
├── src/                   # discover, extract, derived
├── scripts/build/         # feature builders + dq_check
├── platform/
│   ├── pipelines/         # DLT
│   ├── dbt/
│   ├── airflow/dags/
│   ├── ai/
│   └── scripts/           # run_platform_full, validators
└── dashboard/
```

---

## Phases

### Phase 0 — Docs & safety lock

- [x] Single product refresh path
- [x] v1 page + competition scope locked
- [x] Calculation validator + DQ gates in place
- [ ] README: DATA SAFETY, how to run, Python version
- [ ] Confirm `.gitignore` for `data/`, secrets, Airflow logs

### Phase 1 — Airflow health

- [ ] One documented way to start Airflow locally
- [ ] Ping / health DAG green in the UI
- [ ] Timezone + ports documented
- [ ] No football logic required for this phase

### Phase 2 — Offline refresh proven

- [x] `run_platform_full` / `--skip-pandas` works from existing lake
- [x] Warehouse validate + DQ green without Sofascore HTTP
- [ ] AI index rebuild confirmed after latest lake
- [ ] Fixture/CI offline path documented

### Phase 3 — Extract policy

- [x] Rate-limit guidance recorded
- [ ] Document skip-existing + circuit-breaker defaults in README
- [ ] No scheduled `--force` unless explicit param
- [ ] Soft-fail policy for discover/extract written (`docs/` or README)
- [ ] Decide: optional soft extract in DAG **or** extract stays manual

### Phase 4 — Product DAG

```
[optional soft extract] → platform_full_offline → validate → done
```

- [ ] DAG id, schedule, timezone
- [ ] Offline path independent of extract success
- [ ] Params: `skip_extract`, `skip_pandas`, …
- [ ] Manual trigger green with API unavailable
- [ ] Runbook in README

### Phase 5 — Consumption check

- [ ] Streamlit smoke on warehouse (all five pages)
- [ ] Selectors match v1 seasons/competitions
- [ ] AI retrieval smoke
- [ ] Parquet fallback documented as emergency only

### Phase 6 — CI

- [ ] Fixtures only — no live Sofascore in Actions
- [ ] DLT + dbt + validate in CI
- [ ] CI vs CD clarified in README

### Phase 7 — Polish

- [ ] Architecture diagram in README
- [ ] Commands cheat sheet
- [ ] Known limitations (403, local DuckDB, extract not guaranteed daily)

---

## Working agreement

1. One phase at a time.  
2. CLI before Airflow task.  
3. Prefer offline warehouse refresh over fighting the API.  
4. Update this PLAN when scope or status changes.

---

## Next

1. Finish **Phase 0** README safety / run docs  
2. Start **Phase 1** — Airflow ping green  

---

## Locked decisions (quick ref)

| Topic | Decision |
|-------|----------|
| v1 pages | Discover, Profile, Compare, Shortlist, Teams |
| v1 competitions | 11 leagues + 3 UEFA |
| v1 seasons | 2024-25, 2025-26 |
| Serving layer | DuckDB dbt marts |
| Live Sofascore | Best-effort; soft 403 |
| Go-live bar | DQ + calc validation green |
| Airflow | Primary unfinished platform work for v1 ops |
