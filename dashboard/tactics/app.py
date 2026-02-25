"""Schlouh Analytics — Tactics Dashboard.

Entry point: streamlit run dashboard/tactics/app.py

For tactical analysts, coaches, and opposition scouts.
Core job: Understand team playing styles, prepare for specific opponents.
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st
import pandas as pd

from dashboard.utils.data import (
    load_team_season_stats,
    load_tactical_profiles,
    load_match_summary,
)
try:
    from dashboard.utils.data import validate_tactics_data
except ImportError:
    def validate_tactics_data(_team_stats, _tactical_profiles):
        return []
try:
    from dashboard.utils.data import get_tactics_data_refresh_date
except ImportError:
    def get_tactics_data_refresh_date():
        return None
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS
from dashboard.utils.scope import filter_to_default_scope, CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS

st.set_page_config(
    page_title="Tactics · Schlouh",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.tactics.layout import render_tactics_sidebar

render_tactics_sidebar()

# ---------------------------------------------------------------------------
# Load data (default scope: current season + leagues/UEFA only)
# ---------------------------------------------------------------------------
with st.spinner("Loading team datasets…"):
    team_stats_raw = load_team_season_stats()
    tactical_profiles_raw = load_tactical_profiles()
    matches = load_match_summary()

# Validation: friendly error if schema changed (only when we have data)
_ts = team_stats_raw if team_stats_raw is not None else pd.DataFrame()
_tp = tactical_profiles_raw if tactical_profiles_raw is not None else pd.DataFrame()
if not _ts.empty or not _tp.empty:
    missing = validate_tactics_data(_ts, _tp)
    if missing:
        st.error(f"Data schema issue: missing columns ({', '.join(missing)}). Check parquet files.")
        st.stop()

team_stats = filter_to_default_scope(team_stats_raw) if team_stats_raw is not None and not team_stats_raw.empty else team_stats_raw
tactical_profiles = filter_to_default_scope(tactical_profiles_raw) if tactical_profiles_raw is not None and not tactical_profiles_raw.empty else tactical_profiles_raw

# ---------------------------------------------------------------------------
# Page hero (dynamic league count, data refresh)
# ---------------------------------------------------------------------------
n_leagues_hero = int(team_stats["competition_slug"].nunique()) if team_stats is not None and not team_stats.empty else 9
refresh_str = ""
try:
    refresh_date = get_tactics_data_refresh_date()
    if refresh_date:
        refresh_str = f" · Data as of {refresh_date}"
except Exception:
    pass
st.markdown(
    f"""
    <div class="page-hero">
        <div class="page-hero-title">📐 Tactics Dashboard</div>
        <div class="page-hero-sub">
            Analyze team playing styles, formations, and prepare for opponents across {n_leagues_hero} leagues.{refresh_str}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# I want to... (same section title and card style as Scouts)
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🚀 I want to...</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div style="background:#161B22;padding:12px 16px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:1.5rem;margin-bottom:6px;">🏟️</div>
            <div style="font-size:1.05rem;font-weight:600;color:#F0F6FC;margin-bottom:4px;">Browse Teams</div>
            <div style="font-size:0.8rem;color:#8B949E;margin-bottom:0;">
                View all teams with tactical filters
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Team Directory", key="btn_teams", use_container_width=True):
        st.switch_page("pages/1_🏟️_Team_Directory.py")

with col2:
    st.markdown(
        """
        <div style="background:#161B22;padding:12px 16px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:1.5rem;margin-bottom:6px;">⚔️</div>
            <div style="font-size:1.05rem;font-weight:600;color:#F0F6FC;margin-bottom:4px;">Prepare for a Matchup</div>
            <div style="font-size:0.8rem;color:#8B949E;margin-bottom:0;">
                Analyze opponent tactics and key battles
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Prepare Matchup", key="btn_prep", use_container_width=True):
        st.switch_page("pages/3_⚔️_Opponent_Prep.py")

with col3:
    st.markdown(
        """
        <div style="background:#161B22;padding:12px 16px;border-radius:8px;border:1px solid #30363D;text-align:center;">
            <div style="font-size:1.5rem;margin-bottom:6px;">📊</div>
            <div style="font-size:1.05rem;font-weight:600;color:#F0F6FC;margin-bottom:4px;">View League Trends</div>
            <div style="font-size:0.8rem;color:#8B949E;margin-bottom:0;">
                Macro tactical analysis by league
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("View League Trends", key="btn_trends", use_container_width=True):
        st.switch_page("pages/4_📊_League_Trends.py")

st.markdown("---")

# ---------------------------------------------------------------------------
# Tactical styles this season (one featured team per style; clickable -> Profile)
# ---------------------------------------------------------------------------
if tactical_profiles is None or tactical_profiles.empty:
    st.markdown("<div class='section-header'>🎯 Tactical styles this season</div>", unsafe_allow_html=True)
    st.info("No tactical data in default scope. Use **Team Directory** to load or change filters.")
else:
    st.markdown("<div class='section-header'>🎯 Tactical styles this season</div>", unsafe_allow_html=True)
    st.caption(f"Current season ({CURRENT_SEASON}) · Leagues + UEFA only. Top team per style (index 0–100). Click a card to open Tactical Profile.")

    styles = {
        "High Pressing": "pressing_index",
        "Possession-Based": "possession_index",
        "Direct Play": "directness_index",
        "Aerial Dominance": "aerial_index",
        "Wing Play": "crossing_index",
    }
    # Only include styles whose column exists
    styles = {k: v for k, v in styles.items() if v in tactical_profiles.columns}
    if not styles:
        st.caption("No style indices available in data.")
    else:
        cols = st.columns(len(styles))
        for i, (style_name, column) in enumerate(styles.items()):
            with cols[i]:
                featured = tactical_profiles.nlargest(1, column)
                if not featured.empty:
                    team = featured.iloc[0]
                    team_name = team.get("team_name", "Unknown")
                    league = team.get("competition_slug", "")
                    value = team.get(column, 0)
                    comp_name = COMP_NAMES.get(league, league)
                    flag = COMP_FLAGS.get(league, "🏆")
                    comps_list = tactical_profiles[
                        (tactical_profiles["team_name"] == team_name) &
                        (tactical_profiles["season"] == team.get("season", CURRENT_SEASON))
                    ]["competition_slug"].unique().tolist()
                    st.markdown(
                        f"""
                        <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;margin-bottom:10px;">
                            <div style="font-weight:600;color:#F0F6FC;font-size:1rem;">{team_name}</div>
                            <div style="font-size:0.8rem;color:#8B949E;margin:4px 0;">
                                {flag} {comp_name}
                            </div>
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
                                <span style="font-size:0.75rem;color:#8B949E;">{style_name}</span>
                                <span style="color:#C9A840;font-weight:600;">{value:.1f}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button("Open Profile", key=f"style_profile_{i}", use_container_width=True):
                        st.session_state["selected_team"] = {
                            "name": team_name,
                            "season": team.get("season", CURRENT_SEASON),
                            "competitions": comps_list if comps_list else [league],
                        }
                        st.switch_page("pages/2_📐_Tactical_Profile.py")
                else:
                    st.markdown(
                        f"<div style='font-weight:600;color:#C9A840;'>{style_name}</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption("No data in scope.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Coverage Overview (same section name and caption pattern as Scouts)
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>📊 Coverage Overview</div>", unsafe_allow_html=True)
_coverage_refresh = get_tactics_data_refresh_date()
if _coverage_refresh:
    st.caption(f"Data as of {_coverage_refresh}. Default: current season, leagues + UEFA only.")
st.caption("Use **Team Directory** to change scope. [Open Team Directory](pages/1_%F0%9F%8F%9F_Team_Directory) to view or filter teams.")

if team_stats is not None and not team_stats.empty:
    n_teams = team_stats["team_name"].nunique()
    n_leagues = team_stats["competition_slug"].nunique()
    n_seasons = team_stats["season"].nunique()
    n_matches = int(matches["match_id"].nunique()) if matches is not None and not matches.empty and "match_id" in matches.columns else None

    if n_matches is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Teams", f"{n_teams:,}")
        c2.metric("Leagues", n_leagues)
        c3.metric("Seasons", n_seasons)
        c4.metric("Matches", f"{n_matches:,}")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Teams", f"{n_teams:,}")
        c2.metric("Leagues", n_leagues)
        c3.metric("Seasons", n_seasons)
    # Link to Directory
    if st.button("Open Team Directory", key="coverage_btn_dir", type="secondary"):
        st.switch_page("pages/1_🏟️_Team_Directory.py")
else:
    st.info("No team data in default scope. Use **Team Directory** to load or change filters.")
    if st.button("Open Team Directory", key="coverage_btn_dir_empty"):
        st.switch_page("pages/1_🏟️_Team_Directory.py")
