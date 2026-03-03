"""Schlouh Analytics — Football Scouting & Tactics Platform.

Single entry point for GitHub + Streamlit Cloud.
Run: streamlit run dashboard/app.py
"""

import sys
import pathlib

_root = pathlib.Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import streamlit as st
import pandas as pd

from dashboard.utils.data import (
    load_enriched_season_stats,
    get_coverage_from_appearances,
    get_available_comp_seasons,
    load_players_index,
)
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS, POSITION_NAMES
from dashboard.utils.sidebar import render_sidebar

st.set_page_config(
    page_title="Schlouh Analytics | Football Intelligence",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar()

# ---------------------------------------------------------------------------
# Hero — production-ready tagline
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">⚽ Schlouh Analytics</div>
        <div class="page-hero-sub">
            Football scouting, tactical analysis, and match review in one platform.
            Player discovery, comparison, shortlists, team styles, opponent prep, and AI-powered insights.
        </div>
        <div class="page-hero-attribution">All data © Sofascore.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.spinner("Loading dataset…"):
    df = load_enriched_season_stats()
    cov = get_coverage_from_appearances()
    avail = get_available_comp_seasons()
    players_idx = load_players_index()

# ---------------------------------------------------------------------------
# Top-level KPIs
# ---------------------------------------------------------------------------
n_players     = df["player_id"].nunique()
n_seasons     = df["season"].nunique()
n_leagues     = df["competition_slug"].nunique()
n_appearances = int(df["appearances"].sum())
n_goals       = int(df["goals"].sum())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Players",      f"{n_players:,}")
c2.metric("Leagues",      n_leagues)
c3.metric("Seasons",      n_seasons)
c4.metric("Appearances",  f"{n_appearances:,}")
c5.metric("Goals logged", f"{n_goals:,}")

st.markdown("<div class='kpi-accent'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data quality note
# ---------------------------------------------------------------------------
with st.expander("ℹ️ Data quality & coverage — what's included and how to use it", expanded=False):
    st.markdown(
        """
        - **Player & team stats:** All leagues and seasons with match data shown in the table below.
        - **Match momentum & substitution impact:** Available on Team Analysis where pipeline data exists.
        - **Rolling form, consistency, big-game, progression:** From derived pipelines; coverage varies by league/season.
        - **Sample reliability:** Use the **Sample: High / Medium / Low** indicator on player profiles.
          Prefer High-sample players for recruitment decisions.
        """
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Two-column layout: coverage + quick facts
# ---------------------------------------------------------------------------
left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown("<div class='section-header'>📋 Data Coverage & Season Availability</div>", unsafe_allow_html=True)
    st.caption("Matches per league and season. Scroll within the table to see all leagues.")

    pivot = (
        cov.pivot_table(
            index="competition_slug", columns="season",
            values="matches", aggfunc="sum", fill_value=0,
        )
    )
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False)

    pivot_display = pivot.copy()
    for col in pivot_display.columns:
        pivot_display[col] = pivot_display[col].map(lambda x: f"{int(x):,}" if x > 0 else "—")
    pivot_display.index = [
        f"{COMP_FLAGS.get(c, '🏆')} {COMP_NAMES.get(c, c)}" for c in pivot_display.index
    ]
    st.dataframe(pivot_display, use_container_width=True, height=380, hide_index=True)

    if len(pivot) > 0:
        slugs = pivot.index.tolist()
        display_names = pivot_display.index.tolist()
        display_to_slug = dict(zip(display_names, slugs))
        st.caption("Open Find Players with a league pre-selected.")
        scout_col1, scout_col2 = st.columns([3, 1])
        with scout_col1:
            scout_choice = st.selectbox(
                "Find players in a league",
                options=display_names,
                key="home_scout_league",
                label_visibility="collapsed",
                placeholder="Find players in a league…",
            )
        with scout_col2:
            if st.button("Go to Find Players", key="home_scout_go", use_container_width=True) and scout_choice:
                st.session_state["discover_prefill_league"] = display_to_slug[scout_choice]
                st.switch_page("pages/8_🔎_Discover.py")

with right:
    st.markdown("<div class='section-header'>📊 Position Breakdown</div>", unsafe_allow_html=True)
    st.caption("Players by primary position.")

    pos_counts = (
        df.groupby("player_position")["player_id"]
        .nunique()
        .reindex(["F", "M", "D", "G"])
        .dropna()
    )
    for pos, cnt in pos_counts.items():
        label = POSITION_NAMES.get(pos, pos)
        st.markdown(
            f"<div class='info-card'>"
            f"<b style='color:#F0F6FC;'>{label}</b>"
            f"<span style='float:right;color:#C9A840;font-weight:600;'>{cnt:,} players</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Navigation — all sections in one app
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🚀 Jump To</div>", unsafe_allow_html=True)
st.caption("Jump to a section of the app.")

r1, r2, r3 = st.columns(3)
with r1:
    st.markdown("**Scouting**")
    st.page_link("pages/8_🔎_Discover.py", label="🔎 Find Players", use_container_width=True)
    st.page_link("pages/2_📋_Profile.py", label="📋 Player Profile", use_container_width=True)
    st.page_link("pages/3_⚖️_Compare.py", label="⚖️ Compare Players", use_container_width=True)
    st.page_link("pages/4_🎯_Shortlist.py", label="🎯 Shortlist", use_container_width=True)
with r2:
    st.markdown("**Teams & Tactics**")
    st.page_link("pages/6_🏆_Teams.py", label="🏆 Team Analysis", use_container_width=True)
    st.page_link("pages/9_🏟️_Team_Directory.py", label="🏟️ Team Directory", use_container_width=True)
    st.page_link("pages/11_⚔️_Opponent_Prep.py", label="⚔️ Opponent Prep", use_container_width=True)
    st.page_link("pages/12_📊_League_Trends.py", label="📊 League Trends", use_container_width=True)
with r3:
    st.markdown("**Data**")
    st.page_link("pages/5_📊_Explore.py", label="📊 Explore Data", use_container_width=True)
