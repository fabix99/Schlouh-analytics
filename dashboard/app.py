"""Schlouh Analytics — Player Scouting Dashboard.

Entry point: streamlit run dashboard/app.py
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st
import pandas as pd

from dashboard.utils.data import (
    load_enriched_season_stats,
    load_extraction_progress,
    get_available_comp_seasons,
    load_players_index,
)
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS, POSITION_NAMES
from dashboard.utils.sidebar import render_sidebar

st.set_page_config(
    page_title="Schlouh Scouting",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS is injected by render_sidebar()
render_sidebar()

# ---------------------------------------------------------------------------
# Page hero
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">⚽ Player Scouting Dashboard</div>
        <div class="page-hero-sub">
            Data-driven recruitment intelligence across 9 leagues and multiple seasons.
            Filter, rank, and shortlist players — or dive into team tactics and trends.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.spinner("Loading dataset…"):
    df = load_enriched_season_stats()
    ep = load_extraction_progress()
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
with st.expander("ℹ️ Data quality & coverage", expanded=False):
    st.markdown(
        """
        - **Player & team stats:** All leagues and seasons with extracted match data shown below.
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
    st.markdown("<div class='section-header'>📋 Data Coverage</div>", unsafe_allow_html=True)

    coverage = (
        ep[ep["extracted"] > 0]
        .groupby("competition_slug")
        .agg(seasons=("season", "nunique"), matches=("extracted", "sum"))
        .reset_index()
    )
    coverage["league"] = coverage["competition_slug"].map(COMP_NAMES).fillna(coverage["competition_slug"])
    coverage["flag"]   = coverage["competition_slug"].map(COMP_FLAGS).fillna("🏆")
    coverage = coverage.sort_values("matches", ascending=False)

    _max_matches = max(coverage["matches"]) if len(coverage) and coverage["matches"].notna().any() else 1
    for _, row in coverage.iterrows():
        pct   = min(row["matches"] / _max_matches, 1.0) if _max_matches and _max_matches > 0 else 0.0
        bar_w = int(pct * 180)
        col_card, col_cta = st.columns([4, 1])
        with col_card:
            st.markdown(
                f"""
                <div class='info-card'>
                    <span style='font-size:1.1rem;'>{row['flag']}</span>
                    <strong style='margin-left:6px;color:#F0F6FC;'>{row['league']}</strong>
                    <span style='color:#8B949E;font-size:0.82rem;margin-left:8px;'>
                        {row['seasons']} season{'s' if row['seasons'] > 1 else ''} · {row['matches']:,} matches
                    </span>
                    <div style='margin-top:7px;background:#30363D;border-radius:4px;height:5px;'>
                        <div style='background:#C9A840;border-radius:4px;height:5px;width:{bar_w}px;'></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_cta:
            if st.button("Scout", key=f"scout_league_{row['competition_slug']}", use_container_width=True):
                st.session_state["scout_prefill_league"] = row["competition_slug"]
                st.switch_page("pages/1_🔍_Scout.py")

with right:
    st.markdown("<div class='section-header'>📊 Position Breakdown</div>", unsafe_allow_html=True)

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

    st.markdown("<div class='section-header'>🥇 All-Time Top Scorers</div>", unsafe_allow_html=True)
    top_scorers = (
        df.groupby("player_name")["goals"]
        .sum()
        .nlargest(5)
        .reset_index()
        .rename(columns={"goals": "Goals"})
    )
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, row in top_scorers.iterrows():
        st.markdown(
            f"<div class='info-card'>{medals[i]} <b style='color:#F0F6FC;'>{row['player_name']}</b>"
            f"<span style='float:right;color:#FFD93D;font-weight:600;'>{int(row['Goals'])} ⚽</span></div>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Season availability grid
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🗓️ Season Availability</div>", unsafe_allow_html=True)

pivot = (
    ep[ep["extracted"] > 0]
    .pivot_table(
        index="competition_slug", columns="season",
        values="extracted", aggfunc="sum", fill_value=0,
    )
)
pivot.index = [
    f"{COMP_FLAGS.get(c, '🏆')} {COMP_NAMES.get(c, c)}" for c in pivot.index
]
pivot = pivot.map(lambda x: f"{x:,}" if x > 0 else "—")

st.dataframe(pivot, use_container_width=True)

# ---------------------------------------------------------------------------
# Navigation shortcuts
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🚀 Jump To</div>", unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.page_link(
        "pages/1_🔍_Scout.py",
        label="🔍 Scout Players — filter, rank, and shortlist by any metric",
        use_container_width=True,
    )
with c2:
    st.page_link(
        "pages/4_🏆_Teams.py",
        label="🏆 Team Analysis — tactics, formation, match log, manager",
        use_container_width=True,
    )
with c3:
    st.page_link(
        "pages/2_⚖️_Compare.py",
        label="⚖️ Compare Players — radar & bar charts side by side",
        use_container_width=True,
    )
with c4:
    st.page_link(
        "pages/3_📊_Explore.py",
        label="📊 Explore Data — distributions, league tables, age curves",
        use_container_width=True,
    )
with c5:
    st.page_link(
        "pages/5_🤖_AI_Scout.py",
        label="🤖 AI Scout — ask questions about the database (RAG + Groq)",
        use_container_width=True,
    )
