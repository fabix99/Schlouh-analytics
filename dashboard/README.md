# Schlouh Analytics dashboard

Streamlit scouting app. Reads **DuckDB marts** by default (`SCHLOUH_USE_WAREHOUSE=1`).

## Run

```bash
streamlit run dashboard/app.py
```

## Pages (core only)

| Section | Page | File |
|---------|------|------|
| Overview | Home | `app.py` |
| Scouting | Discover | `pages/8_🔎_Discover.py` |
| | Profile | `pages/2_📋_Profile.py` |
| | Compare | `pages/3_⚖️_Compare.py` |
| | Shortlist | `pages/4_🎯_Shortlist.py` |
| Teams | Team Analysis | `pages/6_🏆_Teams.py` |

## Data

Warehouse path: see `docs/PLATFORM.md` and `PLAN.md`.  
Core tables: player season/career/percentiles/form/consistency/progression/opponent context, scouting profiles, heatmaps, team season + tactical profiles, match summary.
