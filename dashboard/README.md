# Schlouh Analytics — Player Scouting Dashboard

A full-featured football player scouting dashboard built with **Streamlit** and **Plotly**.

---

## Stack choice

| Layer | Choice | Reason |
|-------|--------|--------|
| UI framework | **Streamlit 1.50** | Fast to build, interactive, Python-native. Perfect for data-heavy dashboards without JavaScript overhead. |
| Charts | **Plotly** | Interactive, responsive, supports radar, bar, scatter, histograms. Consistent dark-theme styling. |
| Data | **Pandas + PyArrow** | Parquet reading is fast; pre-aggregated `03_player_season_stats.parquet` keeps every filter under ~50 ms. |

---

## How to run

```bash
# From the project root:
streamlit run dashboard/app.py
```

The app opens at **http://localhost:8501** by default.

### Specialized dashboards (Scouts, Tactics, Review)

Three separate Streamlit apps target different personas. Run from the project root:

| Dashboard | Command | Typical port |
|-----------|---------|--------------|
| **Scouts** (discovery, profiles, compare, shortlist) | `streamlit run dashboard/scouts/app.py` | 8501 |
| **Tactics** (team directory, tactical profiles, opponent prep, league trends) | `streamlit run dashboard/tactics/app.py` | 8502 |
| **Review** (schedule, pre-match, post-match, notebook) | `streamlit run dashboard/review/app.py` | 8503 |

Each has its own sidebar and pages under `dashboard/scouts/`, `dashboard/tactics/`, and `dashboard/review/`. They share `dashboard/utils/` (data loaders, charts, components, constants, badges, projections, fit_score). The main dashboard (`dashboard/app.py`) is unchanged and independent.

### Requirements

All dependencies are already in the project's `requirements.txt`. Additionally, the dashboard needs:

```
streamlit>=1.40
plotly>=5.0
pyarrow>=14.0
pandas>=2.0
```

Install if needed:
```bash
pip install streamlit plotly pyarrow pandas
```

### Data path

The app resolves data paths **relative to the project root** (two levels above `dashboard/`). No environment variable needed as long as you run from the project root or any subdirectory.

If you move the `dashboard/` folder, update `_PROJECT_ROOT` in `dashboard/utils/data.py`.

---

## Pages

| Page | File | What it does |
|------|------|-------------|
| 🏠 Overview | `app.py` | Dataset KPIs, coverage heatmap, top scorers, season availability grid |
| 🔍 Scout | `pages/1_🔍_Scout.py` | Rich filters (league, season, position, age, team, min-minutes), sortable table, Top-N rankings, per-player profile with match log and form charts |
| ⚖️ Compare | `pages/2_⚖️_Compare.py` | Add up to 6 players, radar chart (percentile-based), multi-metric bar comparison, full side-by-side stats table |
| 📊 Explore | `pages/3_📊_Explore.py` | Coverage heatmap, player-count trends, stat distributions with scatter overlay, ad-hoc queryable table with CSV export, rolling form trends |

---

## Key logic

### Data layer (`dashboard/utils/data.py`)

- All loaders decorated with `@st.cache_data` — loaded once per session.
- `load_enriched_season_stats()`: joins `03_player_season_stats.parquet` (18K rows) with a lightweight team lookup (derived from `player_appearances.parquet`). This is the primary DataFrame for scouting and comparison.
- `get_player_match_log()`: loads slim columns from `player_appearances.parquet` for a single player's match-by-match view.
- Percentiles for radar charts are computed on-the-fly using `pandas.Series.rank(pct=True)` within the selected season × competition pool — no need to load the 1 M-row percentile file at startup.

### Scouting (`pages/1_🔍_Scout.py`)

Filters applied as boolean masks on the 18K-row DataFrame — sub-millisecond response. The player profile view re-uses the same cached DataFrame plus a lazy-loaded match log.

### Comparison (`pages/2_⚖️_Compare.py`)

`st.session_state.compare_list` (list of `player_id` ints) persists across pages. Players can be added from Scout or from the Compare page's own search. Radar chart percentiles are computed within the selected league/season pool.

### Exploration (`pages/3_📊_Explore.py`)

Distributions and scatter plots work on filtered subsets of `df_all`. Rolling form uses `07_player_rolling_form.parquet` (31K rows).

### Phase 2 utilities (badges, projections, fit)

- **`dashboard/utils/badges.py`**: Rule-based player badges; `infer_transfer_success_features()` infers transfers from team changes and labels success; `train_badge_ml_model()` trains a small classifier on transfer outcomes.
- **`dashboard/utils/projections.py`**: League quality scores and stat projection for cross-league comparison; `analyze_transfer_effects()` infers transfers from team lookup + season stats and computes before/after deltas; `calculate_league_adjustment_factors_from_transfers()` builds position/stat adjustment factors from those deltas.
- **`dashboard/utils/fit_score.py`**: Tactical fit between player and team (statistical similarity, squad gap fill, style alignment).

All data loaders use `@st.cache_data` for session-level caching.

---

## Scouts profile improvements (done & next)

- **Done:** Indice de performance (“Top X% de son championnat”) and **Axes d’amélioration** (stats &lt; 25e centile) on the Scouts Profile page.
- **Done:** Similar players can be searched **cross-league** (Top 5) via the “Inclure les Top 5 championnats” checkbox; `get_similar_players(..., cross_league=True)` in `data.py`.
- **Next (easy):** In Compare, add optional “Comparer à la saison précédente” (same player, previous season) and “Comparer au joueur médian” (synthetic median of the league pool) as extra radar traces. Data is already available; only UI and one extra trace per option.

---

## Known limitations

- **Comparison context**: radar percentiles are computed within a single season × league. When players come from different leagues, you can still compare raw values via the bar charts and stats table. Cross-league similar players use Top 5 leagues when the checkbox is enabled.
- **Player detail**: match log requires `player_appearances.parquet` (408K rows). First load is ~1 s; subsequent loads are cached.
- **Turkey Süper Lig**: extraction success rate is very low (< 10% of matches), so player coverage there is sparse.
- **France Ligue 1 2022–2025**: most seasons are skipped; only 2025-26 has meaningful data.
- **No live data**: all data is static as of the last ETL run.

---

## UX checklist

- [x] **Fast load and filter response** — primary DataFrame is 18K rows; all filters are in-memory boolean masks. Caching means the parquet files are read once per session.
- [x] **Clear labels and tooltips** — competition slugs mapped to human names everywhere; stats explained via `STAT_TOOLTIPS` in constants; chart axes labelled.
- [x] **Obvious navigation** — persistent sidebar on every page with page links; breadcrumb "← Back to Scout" in profile view.
- [x] **Immediate feedback on interaction** — `st.toast()` for add-to-compare; `st.spinner()` for expensive loads; loading states shown during data fetch.
- [x] **Clean, readable layout** — dark theme with teal accent (`#00D4AA`); metric cards with subtle borders; section headers with uppercase teal labels; consistent spacing.
