# Schlouh Analytics — Football Scouting & Tactics Dashboard

A single, production-ready Streamlit app for football scouting, tactical analysis, and match review. Built for **GitHub** and **Streamlit Cloud** so you can share one URL.

---

## How to run (one app)

```bash
# From the project root:
streamlit run dashboard/app.py
```

The app opens at **http://localhost:8501**. All sections (Scouting, Teams & Tactics, Data) are in this single app with one sidebar.

---

## Deploy to Streamlit Cloud

To get a shareable URL (e.g. for job applications):

1. Push the repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io/) → New app.
3. Set **Main file path** to `dashboard/app.py`.
4. (Optional) Add any app secrets in Streamlit Cloud Secrets if needed.

See **[docs/DEPLOY_STREAMLIT_CLOUD.md](../docs/DEPLOY_STREAMLIT_CLOUD.md)** for the full deployment guide.

---

## Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| UI | **Streamlit** | Interactive, Python-native; ideal for data-heavy dashboards. |
| Charts | **Plotly** | Radar, bar, scatter; dark-theme styling. |
| Data | **Pandas + PyArrow** | Fast parquet reads; filters stay under ~50 ms. |

### Data freshness

Data loaders use a 1-hour cache. After running the pipeline or updating parquet files, **restart the Streamlit app** (or wait for cache expiry) to see the latest data.

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

The app resolves data paths **relative to the project root**. No environment variable needed as long as you run from the project root or any subdirectory. The single place that defines the project root is **`dashboard/utils/paths.py`** — update `PROJECT_ROOT` there if you move the repo or dashboard.

---

## Pages (all in one app)

| Section | Page | File | What it does |
|---------|------|------|--------------|
| Overview | 🏠 Home | `app.py` | KPIs, coverage, top scorers, jump links to all sections |
| Scouting | 🔎 Discover | `pages/8_🔎_Discover.py` | Find players, saved filters, results table, profile/shortlist/compare |
| | 📋 Profile | `pages/2_📋_Profile.py` | Deep player report, radar, badges, similar players |
| | ⚖️ Compare | `pages/3_⚖️_Compare.py` | 2–5 players, radar, tactical fit, cross-league adjustment |
| | 🎯 Shortlist | `pages/4_🎯_Shortlist.py` | Track targets, status, notes |
| Teams & Tactics | 🏆 Teams | `pages/6_🏆_Teams.py` | Team analysis, formation, match log |
| | 🏟️ Team Directory | `pages/9_🏟️_Team_Directory.py` | Browse teams by style, league |
| | 📐 Tactical Profile | `pages/10_📐_Tactical_Profile.py` | Formation, indices, strengths/weaknesses |
| | ⚔️ Opponent Prep | `pages/11_⚔️_Opponent_Prep.py` | Matchup analysis, key battles |
| | 📊 League Trends | `pages/12_📊_League_Trends.py` | Macro tactical analysis by league |
| Data | 📊 Explore | `pages/5_📊_Explore.py` | Distributions, league tables, age curves |

---

## Key logic

### Data layer (`dashboard/utils/data.py`)

- All loaders decorated with `@st.cache_data` — loaded once per session.
- `load_enriched_season_stats()`: joins `03_player_season_stats.parquet` (18K rows) with a lightweight team lookup (derived from `player_appearances.parquet`). This is the primary DataFrame for scouting and comparison.
- `get_player_match_log()`: loads slim columns from `player_appearances.parquet` for a single player's match-by-match view.
- Percentiles for radar charts are computed on-the-fly using `pandas.Series.rank(pct=True)` within the selected season × competition pool — no need to load the 1 M-row percentile file at startup.

### Scouting: Discover (`pages/8_🔎_Discover.py`)

**Discover** is the main player-finding page: saved filters, scope (leagues, seasons, positions), stat and percentile filters, column templates (Default, Forwards, Midfield, Defence, Goalkeepers), results table with sort/pagination, View profile (→ Profile page), Add to Shortlist, bulk Add to Compare, shareable URL and CSV export. Filters apply as boolean masks on the enriched stats DataFrame.

### Comparison (`pages/3_⚖️_Compare.py`)

The compare list is the **single source of truth**: `dashboard/scouts/compare_list_scouts.json`, managed by `dashboard.scouts.compare_state`. Players can be added from Discover, Profile, or Shortlist; the sidebar shows the queue count. Radar chart percentiles are computed within the selected league/season pool.

### Exploration (`pages/5_📊_Explore.py`)

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
- [x] **Clean, readable layout** — dark theme with gold accent (`#C9A840`); metric cards with subtle borders; section headers with uppercase gold labels; consistent spacing.
