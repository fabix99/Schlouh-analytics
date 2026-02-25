"""Review Dashboard — Find by team.

You know who you're facing. Search for a team to see their matches and open Pre-Match or Post-Match.
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import streamlit as st

from dashboard.utils.data import load_match_summary
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS
from dashboard.review.layout import render_review_sidebar
from dashboard.review.components.schedule_components import (
    render_match_card,
    render_export_section,
)
from dashboard.review.schedule_priorities import load_schedule_priorities, save_schedule_priorities

# Page config
st.set_page_config(
    page_title="Find by team · Review",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_review_sidebar()

# Initialize session state
if "scout_notes" not in st.session_state:
    st.session_state.scout_notes = []
if "selected_match" not in st.session_state:
    st.session_state.selected_match = None
if "schedule_priorities" not in st.session_state:
    st.session_state.schedule_priorities = load_schedule_priorities()

# Load data
with st.spinner("Loading match data…"):
    matches = load_match_summary()

if matches.empty:
    st.info("No match data available")
    st.stop()

date_col = "match_date_utc" if "match_date_utc" in matches.columns else "match_date"
home_col = "home_team_name" if "home_team_name" in matches.columns else "home_team"
away_col = "away_team_name" if "away_team_name" in matches.columns else "away_team"

if date_col not in matches.columns:
    st.info("No date column in match data")
    st.stop()

matches = matches.copy()
matches[date_col] = pd.to_datetime(matches[date_col], utc=True)

# All unique team names (home + away)
all_teams = sorted(
    set(matches[home_col].dropna().astype(str)) | set(matches[away_col].dropna().astype(str))
)

# ---------------------------------------------------------------------------
# Page: Find by team
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">Find by team</div>
        <div class="page-hero-sub">
            You know who you're facing. Pick a team to see their matches and open Pre-Match or Post-Match.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# One main filter: team
team_query = st.text_input(
    "Team name",
    placeholder="Type to search (e.g. Liverpool, Real Madrid…)",
    key="team_lookup_query",
)
# If many teams, require typing to narrow the list
min_chars = 2 if len(all_teams) > 80 else 0
if team_query:
    options = [t for t in all_teams if team_query.strip().lower() in t.lower()]
elif min_chars > 0:
    options = []
else:
    options = all_teams

if not options:
    if min_chars > 0 and not team_query:
        st.caption("Type at least 2 characters to search teams.")
    else:
        st.info("No team matches that search. Try a different name.")
    st.stop()

selected_team = st.selectbox(
    "Select team",
    options=options,
    index=0,
    key="team_lookup_select",
    format_func=lambda x: x,
)

# Optional: narrow by competition
league_filter = None
if "competition_slug" in matches.columns and selected_team:
    team_matches = matches[
        (matches[home_col].astype(str) == selected_team)
        | (matches[away_col].astype(str) == selected_team)
    ]
    comps = sorted(team_matches["competition_slug"].unique())
    if len(comps) > 1:
        league_filter = st.multiselect(
            "Competition (optional)",
            options=comps,
            default=comps,
            format_func=lambda x: f"{COMP_FLAGS.get(x, '🏆')} {COMP_NAMES.get(x, x)}",
            key="team_lookup_league",
        )

# Filter matches for selected team
filtered_matches = matches[
    (matches[home_col].astype(str) == selected_team)
    | (matches[away_col].astype(str) == selected_team)
].sort_values(date_col, ascending=False)

if league_filter:
    filtered_matches = filtered_matches[filtered_matches["competition_slug"].isin(league_filter)]

# ---------------------------------------------------------------------------
# List of matches for this team
# ---------------------------------------------------------------------------
if filtered_matches.empty:
    st.info(f"No matches found for **{selected_team}** with the selected filters.")
else:
    st.markdown(f"**{len(filtered_matches)}** matches for **{selected_team}**")
    st.divider()

    def on_analyze(match, analysis_type):
        st.session_state["selected_match"] = {
            "id": match.get("match_id"),
            "home": match.get(home_col),
            "away": match.get(away_col),
            "date": match.get(date_col),
            "league": match.get("competition_slug"),
        }
        if analysis_type == "pre":
            st.switch_page("pages/2_🔍_Pre_Match.py")
        elif analysis_type == "post":
            st.switch_page("pages/3_📊_Post_Match.py")

    priorities = st.session_state.schedule_priorities
    for _, match in filtered_matches.iterrows():
        match_id = match.get("match_id")
        mid = str(match_id) if match_id is not None else ""
        with st.container():
            render_match_card(
                match.to_dict(),
                date_col=date_col,
                home_col=home_col,
                away_col=away_col,
                show_form=True,
                on_analyze=on_analyze,
            )
            # Minimal: to scout / importance in a single row
            p = priorities.get(mid, {})
            c1, c2 = st.columns(2)
            with c1:
                to_scout = st.checkbox("To scout", value=p.get("to_scout", False), key=f"ts_{mid}")
            with c2:
                imp = st.selectbox(
                    "Importance",
                    options=["Low", "Medium", "High"],
                    index=["Low", "Medium", "High"].index(p.get("importance", "Medium")),
                    key=f"imp_{mid}",
                )
            priorities[mid] = {"to_scout": to_scout, "importance": imp}
        st.markdown("---")

    st.session_state.schedule_priorities = priorities
    save_schedule_priorities(priorities)

    render_export_section(filtered_matches)

# Footer
st.markdown("---")
if st.button("← Back to Review Home", use_container_width=True):
    st.switch_page("app.py")
