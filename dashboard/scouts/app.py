"""Schlouh Analytics — Scouts Dashboard.

Entry point: streamlit run dashboard/scouts/app.py

For club scouts, recruitment analysts, and data analysts.
Core job: Find players, evaluate them, compare candidates, track targets.
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.utils.data import (
    load_enriched_season_stats,
    load_rolling_form,
    load_scouting_profiles,
)
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS, POSITION_NAMES
from dashboard.utils.scope import filter_to_default_scope, CURRENT_SEASON
from dashboard.utils.validation import safe_divide
from dashboard.scouts.layout import render_scouts_sidebar, load_shortlist_from_file

st.set_page_config(
    page_title="Scouts · Schlouh",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_scouts_sidebar()

# Sync shortlist from file so count is correct (file is source of truth)
st.session_state["shortlist"] = load_shortlist_from_file()

# ---------------------------------------------------------------------------
# Page hero
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">🔎 Scouts Dashboard</div>
        <div class="page-hero-sub">
            Find, evaluate, and track players across 9 leagues. 
            Cross-league adjusted comparisons and ML-powered insights for recruitment decisions.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.spinner("Loading datasets…"):
    df = load_enriched_season_stats()
    form_df = load_rolling_form()
    profiles_df = load_scouting_profiles()

# ---------------------------------------------------------------------------
# Three action buttons
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🚀 I want to...</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div style="background:#161B22;padding:12px 16px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:1.5rem;margin-bottom:6px;">🔎</div>
            <div style="font-size:1.05rem;font-weight:600;color:#F0F6FC;margin-bottom:4px;">Find Players</div>
            <div style="font-size:0.8rem;color:#8B949E;margin-bottom:0;">
                Search and filter by position, age, league, stats
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Start Search", key="btn_find_players", use_container_width=True):
        st.switch_page("pages/1_🔎_Discover.py")

with col2:
    st.markdown(
        """
        <div style="background:#161B22;padding:12px 16px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:1.5rem;margin-bottom:6px;">⚖️</div>
            <div style="font-size:1.05rem;font-weight:600;color:#F0F6FC;margin-bottom:4px;">Compare Players</div>
            <div style="font-size:0.8rem;color:#8B949E;margin-bottom:0;">
                Deep comparison with league-adjusted stats
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Go to Compare", key="btn_compare", use_container_width=True):
        st.switch_page("pages/3_⚖️_Compare.py")

with col3:
    shortlist_count = len(st.session_state.get("shortlist", []))
    st.markdown(
        f"""
        <div style="background:#161B22;padding:12px 16px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:1.5rem;margin-bottom:6px;">🎯</div>
            <div style="font-size:1.05rem;font-weight:600;color:#F0F6FC;margin-bottom:4px;">View Shortlist</div>
            <div style="font-size:0.8rem;color:#8B949E;margin-bottom:0;">
                {shortlist_count} player{'s' if shortlist_count != 1 else ''} tracked
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Shortlist", key="btn_shortlist", use_container_width=True):
        st.switch_page("pages/4_🎯_Shortlist.py")

st.markdown("---")

# ---------------------------------------------------------------------------
# Top performers this season (average rating across all comps, min mins = 50% of max)
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>⭐ Top performers this season</div>", unsafe_allow_html=True)
st.caption(f"Current season ({CURRENT_SEASON}) · Leagues + UEFA only. Season rating (average across competitions). Min. minutes = 50% of this season’s max.")

try:
    df_scope = filter_to_default_scope(df)
    if not df_scope.empty and "total_minutes" in df_scope.columns:
        df_scope = df_scope.copy()
        df_scope["_weighted"] = df_scope["avg_rating"] * df_scope["total_minutes"]
        g = df_scope.groupby("player_id")
        agg = g.agg(total_minutes=("total_minutes", "sum"), _sum_w=("_weighted", "sum"))
        agg["avg_rating"] = agg.apply(
            lambda r: safe_divide(r["_sum_w"], r["total_minutes"], default=np.nan),
            axis=1,
        )
        idx = df_scope.groupby("player_id")["total_minutes"].idxmax()
        primary = df_scope.loc[idx, ["player_id", "player_name", "player_position", "team"]].set_index("player_id")
        agg = agg.join(primary)
        min_mins = 0.5 * float(df_scope["total_minutes"].max())
        agg = agg[agg["total_minutes"] >= min_mins].sort_values("avg_rating", ascending=False).head(6)
        top_players = agg.reset_index()[["player_id", "player_name", "player_position", "team", "avg_rating"]]
    else:
        top_players = pd.DataFrame()
    if not top_players.empty:
        cols = st.columns(3)
        for i, (_, player) in enumerate(top_players.iterrows()):
            with cols[i % 3]:
                position_label = POSITION_NAMES.get(player.get("player_position", ""), "Unknown")
                team = player.get("team", "")
                if pd.isna(team) or team == "" or (isinstance(team, float) and np.isnan(team)):
                    team = "—"
                avg_val = player.get("avg_rating")
                avg_str = f"{avg_val:.2f}" if avg_val is not None and not (isinstance(avg_val, float) and np.isnan(avg_val)) else "—"
                st.markdown(
                    f"""
                    <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;margin-bottom:10px;">
                        <div style="font-weight:600;color:#F0F6FC;font-size:1rem;">{player['player_name']}</div>
                        <div style="font-size:0.8rem;color:#8B949E;margin:4px 0;">
                            {position_label} · {team}
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
                            <span style="font-size:0.75rem;color:#8B949E;">Season rating (avg)</span>
                            <span style="color:#C9A840;font-weight:600;">{avg_str}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(f"View Profile", key=f"home_profile_{player['player_id']}", use_container_width=True):
                    st.session_state["profile_player_id"] = player["player_id"]
                    st.switch_page("pages/2_📋_Profile.py")
    else:
        st.info("No player data for current season (leagues + UEFA) meeting min. minutes. Use **Find Players** to change scope.")
except Exception as e:
    st.error(f"Could not load top performers: {e}")
    st.info("Navigate to 'Find Players' to start scouting")

# ---------------------------------------------------------------------------
# Coverage Overview (full database) — at bottom
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📊 Coverage Overview</div>", unsafe_allow_html=True)
st.caption("By default, views focus on current season (2025-26), leagues + UEFA only. Use **Find Players** filters to change scope.")

if df is not None and not df.empty:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Players", f"{df['player_id'].nunique():,}")
    c2.metric("Leagues", df["competition_slug"].nunique())
    c3.metric("Seasons", df["season"].nunique())
    c4.metric("Appearances", f"{int(df['appearances'].sum()):,}")
else:
    st.info("No data loaded.")
