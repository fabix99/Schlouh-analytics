"""Review Dashboard — Pre-Match Analysis (Enhanced).

Deep pre-match analysis with:
- Match preview cards with form indicators
- H2H history
- Momentum charts
- Key player battles
- Tactical preview
- Exportable scout notes
"""

import sys
import pathlib
from datetime import datetime

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from dashboard.utils.data import (
    load_match_summary,
    load_team_season_stats,
    load_tactical_profiles,
    load_enriched_season_stats,
    get_team_last_matches,
)
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS
from dashboard.utils.scope import filter_to_default_scope
from dashboard.review.layout import render_review_sidebar
from dashboard.review.components.analysis_components import (
    render_match_preview_card,
    render_momentum_indicator,
    render_h2h_analysis,
    render_key_battles,
    export_analysis_report,
)

# Page config
st.set_page_config(
    page_title="Pre-Match · Review",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_review_sidebar()

# Initialize session state
if "selected_match" not in st.session_state:
    st.session_state.selected_match = None
if "scout_notes" not in st.session_state:
    st.session_state.scout_notes = []

# Load data (default scope: current season + leagues/UEFA only)
with st.spinner("Loading match data…"):
    matches = load_match_summary()
    team_stats = load_team_season_stats()
    tactical_df = load_tactical_profiles()
    player_df = load_enriched_season_stats()
if matches is not None and not matches.empty:
    matches = filter_to_default_scope(matches)
if player_df is not None and not player_df.empty:
    player_df = filter_to_default_scope(player_df)

# Page header
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">🔍 Pre-Match Analysis</div>
        <div class="page-hero-sub">
            Comprehensive preview with form analysis, H2H history, and tactical insights.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Match Selection (deep link: ?match_id= or ?home= & ?away=; or selected_match_id from Home)
# ---------------------------------------------------------------------------
if st.session_state.selected_match is None and not matches.empty:
    home_col = "home_team_name" if "home_team_name" in matches.columns else "home_team"
    away_col = "away_team_name" if "away_team_name" in matches.columns else "away_team"
    date_col = "match_date_utc" if "match_date_utc" in matches.columns else "match_date"
    match_id_param = st.query_params.get("match_id") or st.session_state.get("selected_match_id")
    home_param = st.query_params.get("home")
    away_param = st.query_params.get("away")
    if match_id_param is not None and "match_id" in matches.columns:
        try:
            mid = int(match_id_param)
            row = matches[matches["match_id"] == mid]
            if not row.empty:
                match_row = row.iloc[0]
                st.session_state.selected_match = {
                    "id": match_row.get("match_id"),
                    "home": match_row[home_col],
                    "away": match_row[away_col],
                    "date": match_row.get(date_col),
                    "league": match_row.get("competition_slug"),
                    "season": match_row.get("season"),
                }
                st.rerun()
        except (TypeError, ValueError):
            pass
    if home_param is not None and away_param is not None and st.session_state.selected_match is None:
        home_str = str(home_param).strip()
        away_str = str(away_param).strip()
        row = matches[
            (matches[home_col].astype(str).str.strip() == home_str) &
            (matches[away_col].astype(str).str.strip() == away_str)
        ]
        if not row.empty:
            match_row = row.iloc[0]
            st.session_state.selected_match = {
                "id": match_row.get("match_id"),
                "home": match_row[home_col],
                "away": match_row[away_col],
                "date": match_row.get(date_col),
                "league": match_row.get("competition_slug"),
                "season": match_row.get("season"),
            }
            st.rerun()

if st.session_state.selected_match is None:
    st.markdown("<div class='section-header'>🎯 Select Match</div>", unsafe_allow_html=True)
    st.caption("Matches in default scope (current season, leagues + UEFA) only. Use Schedule to see more.")

    if not matches.empty:
        home_col = "home_team_name" if "home_team_name" in matches.columns else "home_team"
        away_col = "away_team_name" if "away_team_name" in matches.columns else "away_team"
        date_col = "match_date_utc" if "match_date_utc" in matches.columns else "match_date"
        matches["label"] = matches.apply(
            lambda r: f"{r[home_col]} vs {r[away_col]} ({r.get(date_col, 'TBC')})",
            axis=1
        )

        selected = st.selectbox("Choose match:", matches["label"].tolist())
        match_row = matches[matches["label"] == selected].iloc[0]

        st.session_state.selected_match = {
            "id": match_row.get("match_id"),
            "home": match_row[home_col],
            "away": match_row[away_col],
            "date": match_row.get(date_col),
            "league": match_row.get("competition_slug"),
            "season": match_row.get("season"),
        }

        if st.button("Analyze Match", type="primary", use_container_width=True):
            st.rerun()
    else:
        st.error("No match data available")
    st.stop()

# ---------------------------------------------------------------------------
# Display Match Analysis
# ---------------------------------------------------------------------------
match = st.session_state.selected_match
home_team = match["home"]
away_team = match["away"]
league = match.get("league", "")
match_date = match.get("date")

# Get team stats
home_data = team_stats[team_stats["team_name"] == home_team].sort_values("season", ascending=False)
away_data = team_stats[team_stats["team_name"] == away_team].sort_values("season", ascending=False)

home_latest = home_data.iloc[0] if not home_data.empty else None
away_latest = away_data.iloc[0] if not away_data.empty else None
season = match.get("season")
if season is None and home_latest is not None:
    season = home_latest.get("season")
if season is None and away_latest is not None:
    season = away_latest.get("season")

# Real form from match history (last 5)
def _form_string_and_data(team_name: str, comp: str, seas) -> tuple:
    if not comp or pd.isna(seas):
        return "—", pd.DataFrame()
    try:
        df = get_team_last_matches(team_name, str(seas), comp, n=5)
        if df.empty:
            return "—", pd.DataFrame()
        form_str = "".join(df["result"].astype(str).tolist())
        form_data = df.rename(columns={"date": "date", "result": "result", "opponent": "opponent"})[["date", "result", "opponent"]].copy()
        form_data["date"] = pd.to_datetime(form_data["date"], errors="coerce")
        return form_str, form_data
    except Exception:
        return "—", pd.DataFrame()

home_form, home_form_data = _form_string_and_data(home_team, league, season)
away_form, away_form_data = _form_string_and_data(away_team, league, season)

# Render match preview card
render_match_preview_card(
    home_team=home_team,
    away_team=away_team,
    league=league,
    match_date=match_date,
    home_form=home_form,
    away_form=away_form,
    home_stats=home_latest,
    away_stats=away_latest,
    importance="High"
)

# ---------------------------------------------------------------------------
# Momentum & Form Analysis
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📈 Momentum & Form</div>", unsafe_allow_html=True)

momentum_cols = st.columns(2)

with momentum_cols[0]:
    if not home_form_data.empty:
        render_momentum_indicator(home_form_data, home_team)
    else:
        st.info(f"No recent form data for {home_team}")

with momentum_cols[1]:
    if not away_form_data.empty:
        render_momentum_indicator(away_form_data, away_team)
    else:
        st.info(f"No recent form data for {away_team}")

# ---------------------------------------------------------------------------
# Head-to-Head History
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>⚔️ Head-to-Head History</div>", unsafe_allow_html=True)

# Real H2H from match summary
h_col = "home_team_name" if "home_team_name" in matches.columns else "home_team"
a_col = "away_team_name" if "away_team_name" in matches.columns else "away_team"
hs_col = "home_score" if "home_score" in matches.columns else None
as_col = "away_score" if "away_score" in matches.columns else None
h2h_mask = (
    ((matches[h_col] == home_team) & (matches[a_col] == away_team)) |
    ((matches[h_col] == away_team) & (matches[a_col] == home_team))
)
h2h_matches = matches.loc[h2h_mask].copy()
if "match_date_utc" in h2h_matches.columns:
    h2h_matches = h2h_matches.sort_values("match_date_utc", ascending=False)
h2h_rows = []
for _, row in h2h_matches.head(10).iterrows():
    ht, at = row[h_col], row[a_col]
    g1 = row[hs_col] if hs_col and pd.notna(row.get(hs_col)) else 0
    g2 = row[as_col] if as_col and pd.notna(row.get(as_col)) else 0
    try:
        g1, g2 = int(g1), int(g2)
    except (TypeError, ValueError):
        g1, g2 = 0, 0
    if ht != home_team:
        ht, at, g1, g2 = at, ht, g2, g1
    hg, ag = g1, g2
    winner = home_team if hg > ag else (away_team if ag > hg else "Draw")
    h2h_rows.append({"date": row.get("match_date_utc", row.get("match_date")), "home_team": ht, "away_team": at, "home_goals": hg, "away_goals": ag, "winner": winner})
h2h_data = pd.DataFrame(h2h_rows) if h2h_rows else pd.DataFrame(columns=["date", "home_team", "away_team", "home_goals", "away_goals", "winner"])

render_h2h_analysis(h2h_data, home_team, away_team)

# ---------------------------------------------------------------------------
# Tactical Preview
# ---------------------------------------------------------------------------
if not tactical_df.empty:
    st.markdown("---")
    st.markdown("<div class='section-header'>🎯 Tactical Preview</div>", unsafe_allow_html=True)

    home_tac = tactical_df[tactical_df["team_name"] == home_team].sort_values("season", ascending=False)
    away_tac = tactical_df[tactical_df["team_name"] == away_team].sort_values("season", ascending=False)

    if not home_tac.empty and not away_tac.empty:
        home_tac_latest = home_tac.iloc[0]
        away_tac_latest = away_tac.iloc[0]

        tac_col1, tac_col2, tac_col3 = st.columns(3)

        with tac_col1:
            st.markdown(f"**{home_team}**")
            indices = [
                ("possession_index", "Possession"),
                ("pressing_index", "Pressing"),
                ("directness_index", "Directness"),
                ("aerial_index", "Aerial"),
            ]
            for idx, label in indices:
                val = home_tac_latest.get(idx, 0)
                st.markdown(
                    f"""
                    <div style="margin:6px 0;">
                        <span style="color:#8B949E;font-size:0.8rem;">{label}</span>
                        <span style="float:right;color:#C9A840;">{val:.0f}</span>
                        <div style="background:#21262D;border-radius:2px;height:4px;margin-top:2px;">
                            <div style="background:#C9A840;border-radius:2px;height:4px;width:{int(val)}%"></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with tac_col2:
            st.markdown(f"**{away_team}**")
            for idx, label in indices:
                val = away_tac_latest.get(idx, 0)
                st.markdown(
                    f"""
                    <div style="margin:6px 0;">
                        <span style="color:#8B949E;font-size:0.8rem;">{label}</span>
                        <span style="float:right;color:#58A6FF;">{val:.0f}</span>
                        <div style="background:#21262D;border-radius:2px;height:4px;margin-top:2px;">
                            <div style="background:#58A6FF;border-radius:2px;height:4px;width:{int(val)}%"></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with tac_col3:
            st.markdown("**Key Tactical Clash**")

            # Identify key battles
            battles = []
            if home_tac_latest.get("pressing_index", 50) > 70 and away_tac_latest.get("possession_index", 50) > 70:
                battles.append(f"🔥 Your high press vs their possession build")
            elif home_tac_latest.get("possession_index", 50) > 70 and away_tac_latest.get("pressing_index", 50) > 70:
                battles.append(f"⚠️ Their press will challenge your buildup")

            if home_tac_latest.get("aerial_index", 50) > away_tac_latest.get("aerial_index", 50) + 20:
                battles.append(f"⬆️ Aerial advantage for {home_team}")
            elif away_tac_latest.get("aerial_index", 50) > home_tac_latest.get("aerial_index", 50) + 20:
                battles.append(f"⬆️ Aerial advantage for {away_team}")

            if home_tac_latest.get("directness_index", 50) > 70 and away_tac_latest.get("defensive_solidity", 50) < 40:
                battles.append(f"🚀 Direct approach may exploit their defense")

            for battle in battles:
                st.markdown(f"<div style='padding:8px;background:#161B22;border-radius:4px;margin:6px 0;font-size:0.85rem;'>{battle}</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Key Player Battles
# ---------------------------------------------------------------------------
if not player_df.empty:
    st.markdown("---")
    st.markdown("<div class='section-header'>⚔️ Key Player Battles</div>", unsafe_allow_html=True)

    home_players = player_df[player_df["team"] == home_team].sort_values("avg_rating", ascending=False)
    away_players = player_df[player_df["team"] == away_team].sort_values("avg_rating", ascending=False)

    if not home_players.empty and not away_players.empty:
        # Define interesting battles
        battles = [
            (home_players.iloc[0]['player_name'] if len(home_players) > 0 else "Home Star",
             away_players.iloc[0]['player_name'] if len(away_players) > 0 else "Away Star",
             "Top Performers"),
            (home_players[home_players['player_position'] == 'F'].iloc[0]['player_name'] if len(home_players[home_players['player_position'] == 'F']) > 0 else "Home Forward",
             away_players[away_players['player_position'] == 'D'].iloc[0]['player_name'] if len(away_players[away_players['player_position'] == 'D']) > 0 else "Away Defender",
             "Attack vs Defense"),
        ]

        render_key_battles(home_players, away_players, battles)

# ---------------------------------------------------------------------------
# Set pieces (stub — data coming soon)
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🎯 Set pieces</div>", unsafe_allow_html=True)
st.info("Set pieces (data coming soon). Corners and free-kick stats will appear here when available.")

# ---------------------------------------------------------------------------
# Scout Checklist
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>✅ Pre-Match Checklist</div>", unsafe_allow_html=True)

checklist = [
    "Review team news - injuries and suspensions",
    "Check recent form (last 5 games)",
    "Review head-to-head history",
    "Identify key tactical battles",
    "Note set-piece threats",
    "Prepare player observation list",
    "Confirm venue and weather conditions",
    "Review referee tendencies",
]

completed = 0
for item in checklist:
    if st.checkbox(item, key=f"check_{item}"):
        completed += 1

_prog = (completed / len(checklist)) if checklist else 0.0
st.progress(min(1.0, max(0.0, _prog)), text=f"Checklist: {completed}/{len(checklist)} completed")

# ---------------------------------------------------------------------------
# Pre-Match Notes
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📝 Pre-Match Notes</div>", unsafe_allow_html=True)

notes_key = f"prematch_notes_{match.get('id', 'unknown')}"

if notes_key not in st.session_state:
    st.session_state[notes_key] = ""

notes = st.text_area(
    "Add observations before kickoff:",
    value=st.session_state[notes_key],
    placeholder="Key players to watch, tactical observations, potential match dynamics...",
    key=f"notes_input_{notes_key}"
)

cols = st.columns([1, 1, 1])
with cols[0]:
    if st.button("💾 Save Notes"):
        st.session_state[notes_key] = notes
        note_entry = {
            "type": "pre-match",
            "match_id": match.get("id"),
            "home": home_team,
            "away": away_team,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        }
        st.session_state.scout_notes.append(note_entry)
        st.success("Notes saved!")

with cols[1]:
    # Export report
    if st.button("📄 Export Report"):
        sections = [
            ("Match Preview", f"{home_team} vs {away_team}"),
            ("Form Analysis", f"{home_team}: {home_form}\n{away_team}: {away_form}"),
            ("Notes", notes),
        ]
        report = export_analysis_report(match, sections, format="markdown")
        st.download_button(
            "Download Markdown",
            data=report,
            file_name=f"prematch_analysis_{home_team}_vs_{away_team}.md",
            mime="text/markdown"
        )

# Footer
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    if st.button("← Back to Schedule", use_container_width=True):
        st.switch_page("pages/1_📅_Schedule.py")
with col2:
    if st.button("📊 Go to Post-Match", use_container_width=True):
        st.switch_page("pages/3_📊_Post_Match.py")
