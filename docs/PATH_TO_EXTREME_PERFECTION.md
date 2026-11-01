# Path to Extreme Perfection — Schlouh Analytics

This document is a single roadmap to take the **Schlouh Analytics** app (Sofascore scraping + Streamlit dashboard) from its current strong state to **extreme perfection**: best-in-class UX, performance, reliability, and maintainability.

---

## Execution status (implemented)

| Done | Item |
|------|------|
| ✅ | **Test doc vs app** — `FULL_APP_TEST_PROMPT.md` Home section aligned with current app (Data Coverage & Season Availability table, Discover select + button, no Top Scorers on Home). |
| ✅ | **Cache strategy** — `STREAMLIT_CACHE_TTL` env (default 3600); all `@st.cache_data` in `dashboard/utils/data.py` use it; **🔄 Refresh data** button in sidebar clears cache and reruns. |
| ✅ | **Sentry** — `app.py` calls `init_sentry(dsn=os.environ.get("SENTRY_DSN"))` when DSN is set. |
| ✅ | **Graceful schema** — `load_players_index`, `load_scouting_profiles`, `load_incidents` (and existing loaders) return empty DataFrame on missing file/KeyError; Home shows error + Retry on load failure. |
| ✅ | **Home empty/error** — Home shows “No data yet” when `df` empty; on load exception shows message + Retry (clears cache and reruns). |
| ✅ | **Shared page frame** — `dashboard/utils/page_frame.py`: `render_page_frame(title, icon)` does set_page_config + render_sidebar; Discover page uses it. |
| ✅ | **Data freshness** — `get_pipeline_last_run_utc()` reads `data/index/latest_successful_run.json`; sidebar footer shows “Data as of YYYY-MM-DD” when present. |
| ✅ | **Discover table cap** — Results capped at 5,000 rows with caption “Showing first 5,000 of M results. Narrow filters to see others.” |

**Remaining (from roadmap):** loading states on every page, URL-driven Compare/Team state, copy link/export, onboarding hints, lazy load on heavy pages, Plotly responsive/titles, CI validation, health check, more loader try/except, shared page frame on all pages, tests, footer polish.

---

## What the app is today (summary)

- **Data pipeline:** Discover matches → Extract raw (Sofascore API) → Orchestrator builds derived/processed parquet → DQ + validation. Heatmaps/shotmaps supported.
- **Dashboard:** Single Streamlit app (`dashboard/app.py`) with Scouting (Discover, Profile, Compare, Shortlist), Teams & Tactics (Teams, Team Directory, Tactical Profile, Opponent Prep, League Trends), and Data (Explore). Shared design system (dark + gold), sidebar, responsive CSS, accessibility utilities, monitoring hooks.
- **Docs:** README, intention, setup, consumption, production checklist, deploy (Streamlit Cloud), full app test prompt, fixing validation failures.

**Current strengths:** Clear structure, one app/one URL, design tokens and CSS, safe validation helpers, cached data loaders, WCAG-oriented accessibility module, monitoring (Sentry/timing) available, comprehensive test checklist.

---

## 1. User experience (UX) — “Feels perfect”

| Priority | Action | Why |
|----------|--------|-----|
| **P0** | **Loading states everywhere** | Every page that calls `load_*` or heavy compute should show a single, clear spinner (or skeleton) and never a blank screen. Audit all pages for missing `st.spinner` / `st.empty` + progress. |
| **P0** | **Empty and error states** | Every list/table/view has a defined empty state (message + CTA, e.g. “Find players”). Every data failure path shows a clear message + “Retry” where applicable. Use the “Edge cases and errors” section in `dashboard/docs/FULL_APP_TEST_PROMPT.md` as the checklist. |
| **P1** | **Consistent “Back” and “Jump”** | Same pattern on every page: primary action (e.g. “← Back to Discover”) and optional “Jump to” / page links. Sidebar already helps; ensure in-page CTAs match. |
| **P1** | **URL-driven state** | Profile already supports `?player_id=…`. Extend where useful: Compare (hash or query with player IDs), Shortlist (optional read-only share), Team/Tactics pages (team_id, opponent_id) so links are shareable and bookmarkable. |
| **P1** | **Copy/export and share** | Profile has Export; add “Copy link to profile” and “Copy link to compare” (URL + optional copy-to-clipboard via JS or Streamlit). Shortlist export (CSV/JSON) if not already present. |
| **P2** | **Onboarding / first-time hints** | When no shortlist and no compare list, one-time dismissible hint: “Add players from Discover to compare or shortlist.” Same for “Select a team” on Tactics. |
| **P2** | **Keyboard and focus** | Rely on `dashboard/utils/accessibility.py` (focus, ARIA). Ensure every interactive flow is keyboard-completable and focus order is logical (sidebar → main content). |
| **P2** | **Microcopy and tooltips** | Every metric in “Metric Definitions” and key KPIs have short tooltips or expanders. Same for filters (e.g. “Min minutes” = “Minimum minutes played in the season”). |

---

## 2. Performance — “Feels instant”

| Priority | Action | Why |
|----------|--------|-----|
| **P0** | **Cache strategy** | All `load_*` in `dashboard/utils/data.py` use `@st.cache_data(ttl=3600)`. Add one place (e.g. config or env) to set TTL (e.g. 0 in dev, 3600 in prod). Optional: cache invalidation button in sidebar (e.g. “Refresh data”) that clears caches and reruns. |
| **P1** | **Lazy load heavy pages** | Teams, Tactical Profile, Opponent Prep, Explore: load only the data needed for the current tab or selection. Defer building large DataFrames until the user picks a team/league/metric. |
| **P1** | **DataFrame size caps** | For Discover and any large tables, cap rows (e.g. 5k) with a “Showing first N of M” and optional “Load more” or pagination. Avoid rendering 50k rows at once. |
| **P1** | **Plotly** | Use `config={ "responsive": True }` and fixed height where appropriate so layout doesn’t thrash. Reuse `PLOTLY_LAYOUT_TACTICS` (and a shared base layout) everywhere. |
| **P2** | **Sentry + performance** | Wire `init_sentry()` in `app.py` when `SENTRY_DSN` is set. Use `@timing_decorator` (or similar from `dashboard/utils/monitoring.py`) on the heaviest loaders and log slow ops. |
| **P2** | **Bundle size** | Prefer `pyarrow` and `pandas` only where needed; avoid importing heavy libs on every page load. Lazy-import tactics/review components if they’re not used on Home/Discover. |

---

## 3. Data and pipeline — “Correct and trustworthy”

| Priority | Action | Why |
|----------|--------|-----|
| **P0** | **Single source of truth** | Home “Data Coverage” and “Season Availability” should match one definition (e.g. from `get_coverage_from_appearances()` or from extraction progress). Document in `docs/HOME_PAGE_DATA.md` and remove duplication. |
| **P0** | **Validation and DQ in CI** | Run `scripts/validate_data.py` and `scripts/build/dq_check.py` (or the orchestrator step that runs them) in CI when `data/` is present, so PRs don’t break “last known good” state. |
| **P1** | **Data version / freshness** | Show “Data as of &lt;date&gt;” or “Last pipeline run: &lt;date&gt;” on Home or in sidebar (from a small metadata file written by the pipeline). |
| **P1** | **Graceful schema evolution** | If parquet columns change, catch `KeyError`/missing columns in loaders and show a clear message (“Data format outdated; please re-run the pipeline”) instead of a stack trace. |
| **P2** | **Scope vs coverage** | Align `config/scope.yaml` with `config/competitions.yaml` and docs: which competitions are “supported” vs “configured”. Document in README or intention. |

---

## 4. Code quality and maintainability — “Easy to perfect further”

| Priority | Action | Why |
|----------|--------|-----|
| **P0** | **Test doc vs app** | `dashboard/docs/FULL_APP_TEST_PROMPT.md` mentions “All-Time Top Scorers” and “Season Availability” on Home; current Home has Data Coverage table + Position Breakdown + Jump To. Either add missing sections to Home or update the test doc so the checklist matches the app 1:1. |
| **P1** | **Shared page frame** | Every page does `set_page_config`, `render_sidebar()`, and often injects CSS. Consider a single `render_page_frame(title, icon)` that does all three so new pages can’t forget sidebar or styles. |
| **P1** | **Typing and contracts** | Use `dashboard/utils/types.py` (and add to it) so that key functions (loaders, filters) have clear argument/return types. Enables safer refactors and better IDE support. |
| **P1** | **Errors to user message** | Replace generic `except Exception` with specific handling and user-facing messages; log full trace with `logger.exception`. Prefer `st.error("…")` + optional “Retry” over silent fallback where the user expects data. |
| **P2** | **Tests** | `dashboard/tests/` has search and filters tests. Add tests for critical paths: loaders (with fixture parquet), filter logic, and state (shortlist/compare) so regressions are caught. |
| **P2** | **Constants** | Keep `COMP_NAMES`, `COMP_FLAGS`, `POSITION_NAMES`, etc. in one place (`dashboard/utils/constants.py`); avoid magic strings in pages. |

---

## 5. Ops and deployment — “Production-grade”

| Priority | Action | Why |
|----------|--------|-----|
| **P0** | **Secrets** | No secrets in repo (already in PRODUCTION_CHECKLIST). For Streamlit Cloud, use only env/secrets; document in `docs/DEPLOY_STREAMLIT_CLOUD.md` and `docs/setup.md`. |
| **P1** | **Health check** | Optional lightweight endpoint or script that loads app and checks one cached loader (e.g. `load_enriched_season_stats`) without rendering full UI. Useful for uptime checks. |
| **P1** | **Streamlit config** | `.streamlit/config.toml` already has theme, server headless, browser usage off. Add any production tweaks (e.g. `maxUploadSize`, `server.enableCORS`) in one place and document. |
| **P2** | **Logging** | Structured logging (e.g. JSON) in production with level from env (e.g. `LOG_LEVEL=INFO`). `dashboard/utils/monitoring` already has logging; ensure it’s used in loaders and error paths. |

---

## 6. Polish and “wow” — “Feels premium”

| Priority | Action | Why |
|----------|--------|-----|
| **P1** | **Animations and transitions** | Subtle CSS transitions are already in place (buttons, cards). Add short transitions for tab switches and expanders if Streamlit allows (e.g. via custom components or minimal JS). |
| **P1** | **Charts** | All Plotly charts use the same dark theme and font; add a minimal “Chart: …” title or subtitle where it helps (e.g. “Goals per 90 by position”). |
| **P2** | **Empty state illustrations** | Replace plain text empty states with a small SVG or icon (e.g. empty shortlist, no compare players) to match the brand. |
| **P2** | **Footer** | One line: “Schlouh Analytics · Football Intelligence · Data from Sofascore” and optional “Data as of …” / “Refresh” as in section 3. |

---

## 7. Suggested order of execution

1. **Week 1 – Foundation**  
   - P0 UX: loading and empty/error states on every page; align FULL_APP_TEST_PROMPT with current app.  
   - P0 Data: single source for coverage/availability; document in HOME_PAGE_DATA.

2. **Week 2 – Performance and reliability**  
   - Cache TTL and optional “Refresh data”; lazy load on heavy pages; Sentry in app entry when DSN set.  
   - Graceful handling of missing columns/schema in loaders.

3. **Week 3 – UX and shareability**  
   - URL-driven state for Compare/Team/Profile; copy link and export; onboarding hints.

4. **Week 4 – Maintainability and polish**  
   - Shared page frame; typing; tests for loaders and filters; data freshness in UI; chart titles and footer.

---

## 8. How to use this doc

- **Product/owner:** Use sections 1–2 and 6 for roadmap and “definition of done” for releases.
- **Developers:** Use sections 2–5 for implementation tasks; tie each task to a small PR and, where applicable, to the checklist in `FULL_APP_TEST_PROMPT.md`.
- **QA:** After each batch of changes, run the full app test prompt and the “Edge cases and errors” section; keep the checklist up to date with the app.

When all P0 items are done and P1s are largely covered, the app will be at **extreme perfection** for its scope: reliable, fast, clear, shareable, and maintainable.
