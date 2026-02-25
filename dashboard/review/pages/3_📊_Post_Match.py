"""Review Dashboard — Post-Match Review.

Structured match review form and key moment tagging.
"""

import sys
import pathlib
from datetime import datetime, timezone
from html import escape as _html_escape

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import streamlit as st

from dashboard.utils.data import load_match_summary
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS
from dashboard.utils.scope import filter_to_default_scope
from dashboard.review.layout import render_review_sidebar

# Page config
st.set_page_config(
    page_title="Post-Match · Review",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_review_sidebar()

# Initialize session state
if "match_reviews" not in st.session_state:
    st.session_state.match_reviews = {}

if "selected_match" not in st.session_state:
    st.session_state.selected_match = None

# Load data (default scope: current season + leagues/UEFA only)
with st.spinner("Loading match data…"):
    matches = load_match_summary()
if matches is not None and not matches.empty:
    matches = filter_to_default_scope(matches)

# Page header
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">📊 Post-Match Review</div>
        <div class="page-hero-sub">
            Structured match analysis with key moment tagging.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Match Selection
# ---------------------------------------------------------------------------
if st.session_state.selected_match is None:
    st.markdown("<div class='section-header'>🎯 Select Match to Review</div>", unsafe_allow_html=True)
    st.caption("Completed matches in default scope (current season, leagues + UEFA) only.")
    
    if not matches.empty:
        # Match summary uses match_date_utc, home_team_name, away_team_name
        date_col = "match_date_utc" if "match_date_utc" in matches.columns else "match_date"
        home_col = "home_team_name" if "home_team_name" in matches.columns else "home_team"
        away_col = "away_team_name" if "away_team_name" in matches.columns else "away_team"
        matches[date_col] = pd.to_datetime(matches[date_col], utc=True)
        now = pd.Timestamp.now(tz="UTC")
        completed = matches[matches[date_col] < now].copy()
        
        if not completed.empty:
            def _fmt(r):
                d = r[date_col]
                return f"{r[home_col]} vs {r[away_col]} ({d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]})"
            completed["label"] = completed.apply(_fmt, axis=1)
            selected = st.selectbox("Choose match:", completed["label"].tolist())
            match_row = completed[completed["label"] == selected].iloc[0]
            st.session_state.selected_match = {
                "id": match_row.get("match_id"),
                "home": match_row[home_col],
                "away": match_row[away_col],
                "date": match_row[date_col],
                "league": match_row.get("competition_slug"),
            }
            if st.button("Start Review", type="primary", use_container_width=True):
                st.rerun()
        else:
            st.info("No completed matches available for review")
    else:
        st.error("No match data available")
    st.stop()

# ---------------------------------------------------------------------------
# Post-Match Review Form
# ---------------------------------------------------------------------------
match = st.session_state.selected_match
home_team = match["home"]
away_team = match["away"]
league = match.get("league", "")
review_key = f"review_{match.get('id', 'unknown')}"

# Initialize review data structure
if review_key not in st.session_state.match_reviews:
    st.session_state.match_reviews[review_key] = {
        "match_id": match.get("id"),
        "home": home_team,
        "away": away_team,
        "date": match.get("date"),
        "final_score": "",
        "ratings": {},
        "moments": [],
        "tactical_notes": "",
        "player_observations": {},
        "player_ratings": [],
        "overall_summary": "",
        "timestamp": datetime.now().isoformat(),
    }

review = st.session_state.match_reviews[review_key]

# Match header
st.markdown(
    f"""
    <div style="background:#161B22;padding:20px;border-radius:8px;border:1px solid #30363D;margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="text-align:center;flex:1;">
                <div style="font-size:1.5rem;font-weight:700;color:#F0F6FC;">{_html_escape(home_team)}</div>
            </div>
            <div style="text-align:center;padding:0 20px;">
                <span style="color:#C9A840;font-size:1.5rem;font-weight:700;">vs</span>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="font-size:1.5rem;font-weight:700;color:#F0F6FC;">{_html_escape(away_team)}</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Score input
st.markdown("<div class='section-header'>📋 Match Score</div>", unsafe_allow_html=True)
score_col1, score_col2 = st.columns(2)
with score_col1:
    home_score = st.number_input(f"{home_team} goals:", 0, 15, value=0, step=1)
with score_col2:
    away_score = st.number_input(f"{away_team} goals:", 0, 15, value=0, step=1)

review["final_score"] = f"{home_score}-{away_score}"

# Match ratings
st.markdown("---")
st.markdown("<div class='section-header'>⭐ Match Ratings</div>", unsafe_allow_html=True)

rating_categories = [
    ("Match Quality", "overall", "Entertainment value of the match"),
    ("Tactical Interest", "tactical", "Strategic complexity and tactical battles"),
    ("Individual Performances", "individual", "Standout player displays"),
    ("Scouting Value", "scouting", "Usefulness for player evaluation"),
]

for label, key, help_text in rating_categories:
    review["ratings"][key] = st.slider(
        label,
        min_value=1,
        max_value=10,
        value=review["ratings"].get(key, 5),
        help=help_text,
        key=f"rating_{key}"
    )

# Tactical observations
st.markdown("---")
st.markdown("<div class='section-header'>🎯 Tactical Analysis</div>", unsafe_allow_html=True)

review["tactical_notes"] = st.text_area(
    "Key tactical observations:",
    value=review.get("tactical_notes", ""),
    placeholder="Formation changes, pressing patterns, build-up strategies, defensive transitions...",
    key="tactical_notes"
)

# Formation checkboxes
tactic_col1, tactic_col2 = st.columns(2)
with tactic_col1:
    st.markdown(f"**{home_team}**")
    high_press = st.checkbox("High pressing intensity", key=f"hp_{home_team}")
    low_block = st.checkbox("Low block utilized", key=f"lb_{home_team}")
    possession = st.checkbox("Possession dominance", key=f"pos_{home_team}")
    direct = st.checkbox("Direct play approach", key=f"dir_{home_team}")

with tactic_col2:
    st.markdown(f"**{away_team}**")
    high_press_away = st.checkbox("High pressing intensity", key=f"hp_{away_team}")
    low_block_away = st.checkbox("Low block utilized", key=f"lb_{away_team}")
    possession_away = st.checkbox("Possession dominance", key=f"pos_{away_team}")
    direct_away = st.checkbox("Direct play approach", key=f"dir_{away_team}")

# Key moments
st.markdown("---")
st.markdown("<div class='section-header'>🔥 Key Moments</div>", unsafe_allow_html=True)

moment_types = ["Goal", "Red Card", "Penalty", "Tactical Shift", "Missed Chance", "Brilliant Save", "Other"]
moment_minute = st.number_input("Minute:", 1, 120, value=1)
moment_type = st.selectbox("Type:", moment_types)
moment_description = st.text_input("Description:", placeholder="Describe what happened...")

if st.button("➕ Add Moment", key="add_moment"):
    if moment_description:
        review["moments"].append({
            "minute": moment_minute,
            "type": moment_type,
            "description": moment_description,
        })
        st.success("Moment added!")

# Display moments
if review["moments"]:
    st.markdown("**Recorded Moments:**")
    for i, moment in enumerate(review["moments"]):
        st.markdown(
            f"""
            <div style="padding:8px;background:#161B22;border-radius:4px;border-left:3px solid #C9A840;margin:4px 0;">
                <strong>{int(moment['minute'])}'</strong> — {_html_escape(str(moment['type']))}: {_html_escape(str(moment['description']))}
            </div>
            """,
            unsafe_allow_html=True,
        )

# Player observations
st.markdown("---")
st.markdown("<div class='section-header'>👤 Player Observations</div>", unsafe_allow_html=True)

st.markdown("*Note: Player names can be entered below for future data linking*")

player_name = st.text_input("Player name:", placeholder="Player to observe...")
player_team = st.radio("Team:", [home_team, away_team], horizontal=True)
player_notes = st.text_area("Observations:", placeholder="Performance notes, strengths, weaknesses...")

if st.button("➕ Add Player Observation", key="add_player_obs"):
    if player_name and player_notes:
        if player_team not in review["player_observations"]:
            review["player_observations"][player_team] = []
        review["player_observations"][player_team].append({
            "player": player_name,
            "notes": player_notes,
        })
        st.success(f"Observation for {player_name} added!")

# Display player observations
for team, observations in review["player_observations"].items():
    if observations:
        st.markdown(f"**{_html_escape(str(team))}:**")
        for obs in observations:
            st.markdown(
                f"""
                <div style="padding:8px;background:#161B22;border-radius:4px;margin:4px 0;">
                    <strong>{_html_escape(str(obs['player']))}</strong>: {_html_escape(str(obs['notes']))}
                </div>
                """,
                unsafe_allow_html=True,
            )

# Individual player ratings (1–10 + short comment)
st.markdown("---")
st.markdown("<div class='section-header'>⭐ Individual player ratings</div>", unsafe_allow_html=True)
st.caption("Optional: rate starters/subs 1–10 with a short comment.")
if "player_ratings" not in review:
    review["player_ratings"] = []
pr_name = st.text_input("Player name:", key="pr_name", placeholder="Player name")
pr_team = st.radio("Team:", [home_team, away_team], key="pr_team", horizontal=True)
pr_rating = st.slider("Rating (1–10):", 1, 10, 6, key="pr_rating")
pr_comment = st.text_input("Short comment:", key="pr_comment", placeholder="e.g. Solid defensively")
if st.button("➕ Add player rating", key="add_pr"):
    if pr_name:
        review["player_ratings"].append({
            "player": pr_name,
            "team": pr_team,
            "rating": pr_rating,
            "comment": pr_comment or "",
        })
        st.success(f"Added rating for {pr_name}")
if review.get("player_ratings"):
    st.markdown("**Recorded ratings:**")
    for pr in review["player_ratings"]:
        st.markdown(
            f"**{_html_escape(pr['player'])}** ({pr['team']}) — {pr['rating']}/10: {_html_escape(pr.get('comment', ''))}"
        )

# Overall summary
st.markdown("---")
st.markdown("<div class='section-header'>📝 Overall Summary</div>", unsafe_allow_html=True)

review["overall_summary"] = st.text_area(
    "Match summary and takeaways:",
    value=review.get("overall_summary", ""),
    placeholder="Overall assessment, key learnings, follow-up actions needed...",
    key="overall_summary"
)

# Tags
tags = st.multiselect(
    "Tags (optional):",
    ["Upset", "Goal-fest", "Tactical Masterclass", "Boring", "Individual Brilliance", "Controversial", "Rivalry"],
    default=[],
    help="Select any applicable tags for quick filtering later"
)

# Save review
st.markdown("---")
if st.button("💾 Save Full Review", type="primary", use_container_width=True):
    review["timestamp"] = datetime.now().isoformat()
    review["tags"] = tags
    st.session_state.match_reviews[review_key] = review
    st.success("Match review saved! You can view it in the Notebook.")

# Download report (Markdown)
def _build_review_markdown(r, tag_list):
    lines = [
        f"# Post-Match Review: {r.get('home', '')} vs {r.get('away', '')}",
        f"\n**Date:** {r.get('date', '')}  \n**Score:** {r.get('final_score', '')}\n",
        "## Match ratings",
    ]
    for k, v in r.get("ratings", {}).items():
        lines.append(f"- **{k}:** {v}/10")
    lines.extend(["", "## Tactical notes", r.get("tactical_notes", "(none)"])
    lines.extend(["", "## Key moments"])
    for m in r.get("moments", []):
        lines.append(f"- **{m.get('minute', '')}'** {m.get('type', '')}: {m.get('description', '')}")
    lines.extend(["", "## Individual player ratings"])
    for pr in r.get("player_ratings", []):
        lines.append(f"- **{pr.get('player', '')}** ({pr.get('team', '')}): {pr.get('rating', 0)}/10 — {pr.get('comment', '')}")
    lines.extend(["", "## Player observations"])
    for team, obs_list in r.get("player_observations", {}).items():
        for obs in obs_list:
            lines.append(f"- **{obs.get('player', '')}** ({team}): {obs.get('notes', '')}")
    lines.extend(["", "## Summary", r.get("overall_summary", "(none)"])
    lines.extend(["", "**Tags:** " + ", ".join(tag_list) if tag_list else "—"])
    return "\n".join(lines)

review_md = _build_review_markdown(review, tags)
st.download_button(
    "📄 Download report (Markdown)",
    data=review_md,
    file_name=f"post_match_{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}.md",
    mime="text/markdown",
    use_container_width=True,
)

# Navigation
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    if st.button("← Back to Schedule", use_container_width=True):
        st.switch_page("pages/1_📅_Schedule.py")
with col2:
    if st.button("📝 View in Notebook", use_container_width=True):
        st.switch_page("pages/4_📝_Notebook.py")
