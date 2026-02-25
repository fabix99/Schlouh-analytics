"""Tactics Dashboard — League Trends (Enhanced).

Macro tactical analysis with:
- League tactical profiles
- Trend over time visualization
- Team similarity matrix
- Style evolution tracking
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from dashboard.utils.data import (
    load_tactical_profiles,
    load_team_season_stats,
)
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS, TOP_5_LEAGUES
from dashboard.utils.scope import filter_to_default_scope, CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.tactics.layout import render_tactics_sidebar
from dashboard.tactics.components.tactical_components import (
    render_league_trends_dashboard,
    render_team_similarity_matrix,
    render_tactical_style_evolution,
)

# Page config
st.set_page_config(
    page_title="League Trends · Tactics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_tactics_sidebar()

# Load data
with st.spinner("Loading league data…"):
    tactical_df = load_tactical_profiles()
    team_stats = load_team_season_stats()

# Scope selector (improvement #48): season + Top 5 vs All
if not tactical_df.empty:
    tactical_df = filter_to_default_scope(tactical_df)
if not team_stats.empty:
    team_stats = filter_to_default_scope(team_stats)
scope_label = st.radio("Scope", options=["Leagues + UEFA (default)", "Top 5 leagues only"], index=0, key="trends_scope", horizontal=True)
if scope_label == "Top 5 leagues only" and not tactical_df.empty:
    tactical_df = tactical_df[tactical_df["competition_slug"].isin(TOP_5_LEAGUES)]
if scope_label == "Top 5 leagues only" and not team_stats.empty:
    team_stats = team_stats[team_stats["competition_slug"].isin(TOP_5_LEAGUES)]

# Empty state (improvement #49)
if tactical_df.empty:
    st.warning("No tactical data in selected scope. Try **Leagues + UEFA (default)** or check data.")
    if st.button("Reset scope", key="trends_reset"):
        st.rerun()
    st.stop()

# Page header
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">📊 League Trends</div>
        <div class="page-hero-sub">
            Macro tactical analysis across leagues and seasons. Compare styles, track evolution, find similarities.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(f"Default: {CURRENT_SEASON}, leagues + UEFA only.")

# ---------------------------------------------------------------------------
# League Comparison Overview
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🏆 League Tactical Profiles</div>", unsafe_allow_html=True)

# Calculate league averages — only for columns that exist
_agg_candidates = [
    "possession_index", "pressing_index", "directness_index",
    "aerial_index", "crossing_index", "defensive_solidity", "chance_creation_index",
]
_agg_cols = {c: "mean" for c in _agg_candidates if c in tactical_df.columns}
league_avg = tactical_df.groupby("competition_slug").agg(_agg_cols).round(1)
team_count = tactical_df.groupby("competition_slug")["team_name"].nunique()
league_avg = league_avg.reset_index()
league_avg["league_name"] = league_avg["competition_slug"].map(COMP_NAMES)
league_avg["flag"] = league_avg["competition_slug"].map(COMP_FLAGS)
league_avg["team_count"] = league_avg["competition_slug"].map(team_count).fillna(0).astype(int)

# Download League Trends data (CSV, optional Excel)
st.markdown("**Export**")
dl_c1, dl_c2 = st.columns(2)
with dl_c1:
    csv_bytes = league_avg.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download CSV",
        data=csv_bytes,
        file_name="league_trends_profiles.csv",
        mime="text/csv",
        key="league_trends_csv",
        use_container_width=True,
    )
with dl_c2:
    try:
        import io
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "League Profiles"
        for r_idx, row in enumerate(league_avg.itertuples(index=False), start=1):
            for c_idx, val in enumerate(row, start=1):
                ws.cell(row=r_idx, column=c_idx, value=val)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        st.download_button(
            "📥 Download Excel",
            data=buf.getvalue(),
            file_name="league_trends_profiles.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="league_trends_xlsx",
            use_container_width=True,
        )
    except Exception as e:
        st.caption("Excel export unavailable (install openpyxl).")
st.markdown("---")

# Display league cards
league_cols = st.columns(min(len(league_avg), 3))

for i, (_, league) in enumerate(league_avg.iterrows()):
    with league_cols[i % 3]:
        n_teams = int(league.get("team_count", 0))
        st.markdown(
            f"""
            <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;margin-bottom:10px;">
                <div style="display:flex;align-items:center;margin-bottom:10px;">
                    <span style="font-size:1.5rem;margin-right:10px;">{league['flag']}</span>
                    <div style="font-size:1.1rem;font-weight:600;color:#F0F6FC;">{league['league_name']}</div>
                </div>
                <div style="font-size:0.8rem;color:#8B949E;margin-bottom:8px;">{n_teams} teams</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                    <div style="background:#21262D;padding:6px;border-radius:4px;text-align:center;">
                        <div style="font-size:0.7rem;color:#8B949E;">Possession</div>
                        <div style="font-size:0.9rem;color:#C9A840;">{league.get('possession_index', 0):.0f}</div>
                    </div>
                    <div style="background:#21262D;padding:6px;border-radius:4px;text-align:center;">
                        <div style="font-size:0.7rem;color:#8B949E;">Pressing</div>
                        <div style="font-size:0.9rem;color:#C9A840;">{league.get('pressing_index', 0):.0f}</div>
                    </div>
                    <div style="background:#21262D;padding:6px;border-radius:4px;text-align:center;">
                        <div style="font-size:0.7rem;color:#8B949E;">Directness</div>
                        <div style="font-size:0.9rem;color:#C9A840;">{league.get('directness_index', 0):.0f}</div>
                    </div>
                    <div style="background:#21262D;padding:6px;border-radius:4px;text-align:center;">
                        <div style="font-size:0.7rem;color:#8B949E;">Defense</div>
                        <div style="font-size:0.9rem;color:#C9A840;">{league.get('defensive_solidity', 0):.0f}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# League Trends Over Time (New Enhancement)
# ---------------------------------------------------------------------------
if 'season' in tactical_df.columns and tactical_df['season'].nunique() > 1:
    st.markdown("---")
    st.markdown("<div class='section-header'>📈 League Evolution Over Time</div>", unsafe_allow_html=True)

    # Trend metric selector
    trend_metric = st.selectbox(
        "Select metric to analyze trends:",
        options=[
            ("possession_index", "Possession Index"),
            ("pressing_index", "Pressing Index"),
            ("directness_index", "Directness Index"),
            ("defensive_solidity", "Defensive Solidity"),
        ],
        format_func=lambda x: x[1],
        key="trend_metric"
    )

    # Prepare trend data
    trend_data = tactical_df.groupby(['competition_slug', 'season']).agg({
        trend_metric[0]: 'mean'
    }).reset_index()
    trend_data['league'] = trend_data['competition_slug'].map(COMP_NAMES)

    render_league_trends_dashboard(trend_data, trend_metric[0])

# ---------------------------------------------------------------------------
# Tactical Index Comparison Chart
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📊 Cross-League Comparison</div>", unsafe_allow_html=True)

# Select indices to compare — only show options where data exists
_all_idx_options = [
    ("possession_index", "Possession"),
    ("pressing_index", "Pressing"),
    ("directness_index", "Directness"),
    ("aerial_index", "Aerial Play"),
    ("crossing_index", "Crossing"),
    ("defensive_solidity", "Defensive Solidity"),
    ("chance_creation_index", "Chance Creation"),
]
_available_idx_options = [(col, label) for col, label in _all_idx_options if col in league_avg.columns]
_default_indices = [(col, label) for col, label in _available_idx_options
                    if col in ("possession_index", "pressing_index", "directness_index")]
selected_indices = st.multiselect(
    "Select tactical indices to compare:",
    options=_available_idx_options,
    format_func=lambda x: x[1],
    default=_default_indices if _default_indices else (_available_idx_options[:3] if len(_available_idx_options) >= 3 else _available_idx_options),
)

if selected_indices:
    # Create grouped bar chart
    fig = go.Figure()

    for idx_code, idx_name in selected_indices:
        fig.add_trace(go.Bar(
            name=idx_name,
            x=league_avg["league_name"],
            y=league_avg[idx_code],
            marker_line_width=0,
        ))

    fig.update_layout(
        barmode="group",
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3"),
        xaxis=dict(gridcolor="#30363D", tickangle=-45),
        yaxis=dict(gridcolor="#30363D", range=[0, 100], title="Index Value"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.4,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=44, r=44, t=30, b=100),
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Team Similarity Matrix (New Enhancement)
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🔗 Team Similarity Analysis</div>", unsafe_allow_html=True)

st.markdown("Compare teams based on their tactical profiles to find similar playing styles.")

# League selector for similarity
sim_league = st.selectbox(
    "Select league for team similarity analysis:",
    options=sorted(tactical_df["competition_slug"].unique()),
    format_func=lambda x: f"{COMP_FLAGS.get(x, '🏆')} {COMP_NAMES.get(x, x)}",
    key="sim_league"
)

if sim_league:
    league_teams_tac = tactical_df[tactical_df["competition_slug"] == sim_league]

    if len(league_teams_tac) >= 2:
        all_team_names = league_teams_tac["team_name"].unique().tolist()[:12]
        find_similar_to = st.selectbox("Find similar to…", options=["(all teams)"] + all_team_names, key="find_similar_to")
        if find_similar_to and find_similar_to != "(all teams)":
            team_names = [find_similar_to] + [t for t in all_team_names if t != find_similar_to]
        else:
            team_names = all_team_names

        if len(team_names) >= 2:
            render_team_similarity_matrix(
                league_teams_tac,
                team_names,
                similarity_metric="euclidean"
            )

            st.caption("Higher values (green) = similar styles. Row for «Find similar to» shows similarity of that team to others.")
        else:
            st.info("Need at least 2 teams for similarity analysis")
    else:
        st.info("Not enough teams in league for similarity analysis")

# ---------------------------------------------------------------------------
# League Style Leaders
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🎯 League Style Characteristics</div>", unsafe_allow_html=True)

# Identify which leagues lead in each style — only include styles with data
_style_col_map = {
    "Possession": "possession_index",
    "Pressing": "pressing_index",
    "Direct Play": "directness_index",
    "Aerial Play": "aerial_index",
    "Defensive Solidity": "defensive_solidity",
}
style_leaders = {
    style: league_avg.nlargest(1, col).iloc[0]
    for style, col in _style_col_map.items()
    if col in league_avg.columns and not league_avg[col].isna().all()
}

leader_cols = st.columns(max(len(style_leaders), 1))

for col, (style, league) in zip(leader_cols, style_leaders.items()):
    with col:
        value = league.get(_style_col_map[style], 0)
        col_name = _style_col_map[style]
        second = league_avg.nlargest(2, col_name) if col_name in league_avg.columns else league_avg.head(2)
        second_row = second.iloc[1] if len(second) > 1 else None
        second_str = f"2nd: {second_row['league_name']} {second_row[col_name]:.0f}" if second_row is not None and col_name in second_row.index else ""
        st.markdown(
            f"""
            <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;text-align:center;height:100%;">
                <div style="font-size:2rem;margin-bottom:8px;">🏆</div>
                <div style="font-size:0.8rem;color:#8B949E;margin-bottom:8px;">{style}</div>
                <div style="font-size:1.1rem;font-weight:600;color:#C9A840;margin-bottom:4px;">{league['league_name']}</div>
                <div style="font-size:0.9rem;color:#F0F6FC;">{value:.0f}</div>
                <div style="font-size:0.75rem;color:#8B949E;margin-top:4px;">{second_str}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Team Clusters Within League
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🔍 Team Style Clusters</div>", unsafe_allow_html=True)

# League selector for cluster analysis
selected_league = st.selectbox(
    "Select league to analyze team clusters:",
    options=sorted(tactical_df["competition_slug"].unique()),
    format_func=lambda x: f"{COMP_FLAGS.get(x, '🏆')} {COMP_NAMES.get(x, x)}",
    key="cluster_league"
)

if selected_league:
    league_teams = tactical_df[tactical_df["competition_slug"] == selected_league]

    if not league_teams.empty:
        # Scatter plot: Possession vs Pressing (filter NaN for Plotly compatibility)
        plot_df = league_teams.copy()
        plot_df = plot_df.dropna(subset=["possession_index", "pressing_index"])

        if plot_df.empty:
            st.warning("No teams with valid data for this league.")
        else:
            if "defensive_solidity" in plot_df.columns:
                plot_df = plot_df.assign(size_plot=plot_df["defensive_solidity"].fillna(50))
            else:
                plot_df = plot_df.assign(size_plot=50)

            fig = px.scatter(
                plot_df,
                x="possession_index",
                y="pressing_index",
                text="team_name",
                size="size_plot",
                hover_data=["directness_index", "aerial_index"] if "directness_index" in plot_df.columns else None,
                title=f"Team Styles: Possession vs Pressing ({COMP_NAMES.get(selected_league, selected_league)})",
            )

            fig.update_layout(
                paper_bgcolor="#0D1117",
                plot_bgcolor="#0D1117",
                font=dict(color="#E6EDF3"),
                xaxis=dict(gridcolor="#30363D", title="Possession Index", range=[0, 100]),
                yaxis=dict(gridcolor="#30363D", title="Pressing Index", range=[0, 100]),
                margin=dict(l=44, r=44, t=50, b=44),
            )

            fig.update_traces(
                marker=dict(color="#C9A840"),
                textfont=dict(size=9, color="#E6EDF3"),
            )

            st.plotly_chart(fig, use_container_width=True)

            # Identify clusters
            st.markdown("**Identified Playing Styles:**")

            clusters = []

            high_press = league_teams[league_teams["pressing_index"] > 70]
            if not high_press.empty:
                clusters.append(("High Pressing Teams", high_press["team_name"].tolist()))

            possession = league_teams[league_teams["possession_index"] > 70]
            if not possession.empty:
                clusters.append(("Possession-Based Teams", possession["team_name"].tolist()))

            if "directness_index" in league_teams.columns:
                direct = league_teams[league_teams["directness_index"] > 70]
                if not direct.empty:
                    clusters.append(("Direct Play Teams", direct["team_name"].tolist()))

            if clusters:
                cluster_cols = st.columns(len(clusters))
                for c, (name, teams) in zip(cluster_cols, clusters):
                    with c:
                        st.markdown(f"**{name}**")
                        for team in teams[:5]:
                            st.markdown(f"<div style='padding:2px 0;color:#8B949E;'>{team}</div>", unsafe_allow_html=True)
                            if st.button("Profile", key=f"cluster_profile_{selected_league}_{team}", use_container_width=True):
                                st.session_state["selected_team"] = {"name": team, "season": tactical_df["season"].iloc[0] if not tactical_df.empty else CURRENT_SEASON, "competitions": [selected_league]}
                                st.switch_page("pages/2_📐_Tactical_Profile.py")

# ---------------------------------------------------------------------------
# Tactical Efficiency
# ---------------------------------------------------------------------------
if not team_stats.empty and not tactical_df.empty:
    st.markdown("---")
    st.markdown("<div class='section-header'>⚡ Tactical Efficiency</div>", unsafe_allow_html=True)

    # Merge stats with tactical data
    efficiency_df = team_stats.merge(
        tactical_df[["team_name", "season", "competition_slug", "possession_index", "chance_creation_index"]],
        on=["team_name", "season", "competition_slug"],
        how="inner"
    )

    if not efficiency_df.empty:
        # Calculate xG efficiency
        efficiency_df["xg_per_possession"] = efficiency_df["xg_for_total"] / (efficiency_df["possession_index"] + 1) * 100
        st.caption("xG per possession point: xG For / (possession_index + 1) × 100. Higher = more attacking output per unit of possession style.")

        # Show top efficient teams by league
        league_for_eff = st.selectbox(
            "Select league for efficiency analysis:",
            options=sorted(efficiency_df["competition_slug"].unique()),
            format_func=lambda x: f"{COMP_FLAGS.get(x, '🏆')} {COMP_NAMES.get(x, x)}",
            key="eff_league"
        )

        league_eff = efficiency_df[efficiency_df["competition_slug"] == league_for_eff].nlargest(5, "xg_per_possession")

        if not league_eff.empty:
            st.markdown("**Most Efficient Attackers (xG per possession point)**")

            for _, team in league_eff.iterrows():
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:10px;background:#161B22;border-radius:6px;border:1px solid #30363D;margin:6px 0;">
                        <div>
                            <span style="font-weight:500;color:#F0F6FC;">{team['team_name']}</span>
                            <span style="color:#8B949E;font-size:0.8rem;margin-left:10px;">
                                Poss: {team['possession_index']:.0f}%
                            </span>
                        </div>
                        <span style="color:#3FB950;font-weight:600;">{team['xg_per_possession']:.2f} xG/poss</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# Footer
st.markdown("---")
if st.button("← Back to Tactics Home", use_container_width=True):
    st.switch_page("app.py")
