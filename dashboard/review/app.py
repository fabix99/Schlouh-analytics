"""Schlouh Analytics — Review Dashboard.

Entry point: streamlit run dashboard/review/app.py

For match analysts and scouts attending games.
Core job: Quick pre-match preview, structured post-match notes.
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from dashboard.utils.data import (
    load_match_summary,
    load_enriched_season_stats,
)
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS
from dashboard.utils.scope import filter_to_default_scope, CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS

st.set_page_config(
    page_title="Review · Schlouh",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.review.layout import render_review_sidebar

render_review_sidebar()

# ---------------------------------------------------------------------------
# Page hero
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">📝 Review Dashboard</div>
        <div class="page-hero-sub">
            Prepare for upcoming matches, review games with structured analysis,
            and maintain your personal scouting notebook.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data (default scope: current season + leagues/UEFA only)
# ---------------------------------------------------------------------------
with st.spinner("Loading match data…"):
    matches_raw = load_match_summary()
    players_raw = load_enriched_season_stats()
# Apply default scope so nowhere do we show old scope by default
if matches_raw is not None and not matches_raw.empty and "competition_slug" in matches_raw.columns:
    matches = matches_raw[matches_raw["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS)].copy()
    if "season" in matches.columns:
        matches = matches[matches["season"] == CURRENT_SEASON]
else:
    matches = matches_raw if matches_raw is not None else pd.DataFrame()
if players_raw is not None and not players_raw.empty:
    players = filter_to_default_scope(players_raw)
else:
    players = players_raw if players_raw is not None else pd.DataFrame()

# ---------------------------------------------------------------------------
# Quick action buttons
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🚀 Quick Actions</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div style="background:#161B22;padding:20px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:2rem;margin-bottom:10px;">📅</div>
            <div style="font-size:1.1rem;font-weight:600;color:#F0F6FC;margin-bottom:8px;">View Schedule</div>
            <div style="font-size:0.85rem;color:#8B949E;margin-bottom:15px;">
                Upcoming matches and quick previews
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("See Schedule", key="btn_schedule", use_container_width=True):
        st.switch_page("pages/1_📅_Schedule.py")

with col2:
    st.markdown(
        """
        <div style="background:#161B22;padding:20px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:2rem;margin-bottom:10px;">🔍</div>
            <div style="font-size:1.1rem;font-weight:600;color:#F0F6FC;margin-bottom:8px;">Pre-Match Prep</div>
            <div style="font-size:0.85rem;color:#8B949E;margin-bottom:15px;">
                Deep analysis before the game
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Prep Match", key="btn_prematch", use_container_width=True):
        st.switch_page("pages/2_🔍_Pre_Match.py")

with col3:
    st.markdown(
        """
        <div style="background:#161B22;padding:20px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:2rem;margin-bottom:10px;">📝</div>
            <div style="font-size:1.1rem;font-weight:600;color:#F0F6FC;margin-bottom:8px;">My Notebook</div>
            <div style="font-size:0.85rem;color:#8B949E;margin-bottom:15px;">
                Personal scouting database
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Notebook", key="btn_notebook", use_container_width=True):
        st.switch_page("pages/4_📝_Notebook.py")

st.markdown("---")

# ---------------------------------------------------------------------------
# Upcoming matches (default scope only — use Schedule filters to include more)
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>📅 This Week's Matches</div>", unsafe_allow_html=True)
st.caption(f"Current season ({CURRENT_SEASON}), leagues + UEFA only.")

date_col = "match_date_utc" if matches is not None and "match_date_utc" in matches.columns else "match_date"
if matches is not None and not matches.empty and date_col in matches.columns:
    try:
        matches[date_col] = pd.to_datetime(matches[date_col])
        today = datetime.now()
        next_week = today + timedelta(days=7)
        upcoming = matches[
            (matches[date_col] >= today) &
            (matches[date_col] <= next_week)
        ].sort_values(date_col).head(6)
        home_col = 'home_team_name' if 'home_team_name' in matches.columns else 'home_team'
        away_col = 'away_team_name' if 'away_team_name' in matches.columns else 'away_team'
        if not upcoming.empty:
            cols = st.columns(2)
            for i, (_, match) in enumerate(upcoming.iterrows()):
                with cols[i % 2]:
                    home = match.get(home_col, 'TBD')
                    away = match.get(away_col, 'TBD')
                    match_date = match.get(date_col)
                    league = match.get('competition_slug', '')
                    
                    date_str = match_date.strftime('%a %d %b') if pd.notna(match_date) else 'TBC'
                    
                    st.markdown(
                        f"""
                        <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;margin-bottom:10px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                                <span style="font-size:0.75rem;color:#8B949E;">{COMP_FLAGS.get(league, '🏆')} {COMP_NAMES.get(league, league)}</span>
                                <span style="font-size:0.75rem;color:#C9A840;">{date_str}</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div style="text-align:left;">
                                    <div style="font-weight:600;color:#F0F6FC;">{home}</div>
                                </div>
                                <div style="color:#8B949E;font-size:0.9rem;">vs</div>
                                <div style="text-align:right;">
                                    <div style="font-weight:600;color:#F0F6FC;">{away}</div>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(f"Analyze", key=f"match_{match.get('match_id', i)}", use_container_width=True):
                        st.session_state["selected_match_id"] = match.get('match_id')
                        st.switch_page("pages/2_🔍_Pre_Match.py")
        else:
            st.info("No upcoming matches in next 7 days — check Schedule page for full calendar")
    except Exception as e:
        st.info("Match schedule temporarily unavailable — data format mismatch")
        st.caption(f"Debug: {e}")
else:
    st.info("Match data loading...")

st.markdown("---")

# ---------------------------------------------------------------------------
# Quick tips
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>💡 Workflow Tips</div>", unsafe_allow_html=True)

tip1, tip2, tip3 = st.columns(3)

with tip1:
    st.markdown(
        """
        <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;">
            <div style="font-weight:600;color:#C9A840;margin-bottom:8px;">1. Pre-Match</div>
            <div style="font-size:0.85rem;color:#8B949E;">
                Check form, head-to-head, and tactical preview before kickoff
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with tip2:
    st.markdown(
        """
        <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;">
            <div style="font-weight:600;color:#C9A840;margin-bottom:8px;">2. During Match</div>
            <div style="font-size:0.85rem;color:#8B949E;">
                Use the Notebook to jot quick observations on players
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with tip3:
    st.markdown(
        """
        <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;">
            <div style="font-weight:600;color:#C9A840;margin-bottom:8px;">3. Post-Match</div>
            <div style="font-size:0.85rem;color:#8B949E;">
                Review key stats and save structured analysis to Notebook
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
