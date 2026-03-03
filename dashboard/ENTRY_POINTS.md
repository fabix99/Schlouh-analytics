# Dashboard entry point

There is **one app** for the full platform. Legacy separate entry points (Scouts, Tactics, Review apps) have been removed; all pages live under `dashboard/pages/` and the single sidebar in `dashboard/utils/sidebar.py`.

| Command (from project root) | What you get |
|-----------------------------|--------------|
| `streamlit run dashboard/app.py` | Single app: Home + Scouting (Discover, Profile, Compare, Shortlist) + Teams & Tactics (Teams, Team Directory, Tactical Profile, Opponent Prep, League Trends) + Data (Explore) |

Use the **sidebar** to move between sections. Deploy to Streamlit Cloud with **Main file path:** `dashboard/app.py` — see `docs/DEPLOY_STREAMLIT_CLOUD.md`.
