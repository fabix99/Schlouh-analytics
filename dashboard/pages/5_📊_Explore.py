"""Explore Data — dataset overview, distributions, ad-hoc tables, and form trends."""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils.data import (
    load_enriched_season_stats,
    load_extraction_progress,
    load_players_index,
    load_rolling_form,
    load_peak_age_by_position,
    get_player_match_log,
)
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, POSITION_NAMES, MIN_MINUTES_DEFAULT,
)
from dashboard.utils.charts import rating_trend
from dashboard.utils.sidebar import render_sidebar

st.set_page_config(page_title="Explore · Schlouh", page_icon="📊", layout="wide")
render_sidebar()

with st.spinner("Loading data…"):
    df_all = load_enriched_season_stats()
    df_extract = load_extraction_progress()
    df_index = load_players_index()

st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">📊 Explore Data</div>
        <div class="page-hero-sub">
            Understand your dataset, build ad-hoc tables, and visualize distributions and trends.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Age filter: apply to all tabs (histograms, scatter, age curves)
if "age_at_season_start" in df_all.columns:
    with st.expander("🔽 Age range (applies to all charts)", expanded=False):
        a1, a2, _ = st.columns([1, 1, 2])
        with a1:
            explore_age_min = st.number_input("Min age", 15, 50, 16, 1, key="explore_age_min")
        with a2:
            explore_age_max = st.number_input("Max age", 15, 50, 45, 1, key="explore_age_max")
    if explore_age_min > explore_age_max:
        explore_age_min, explore_age_max = explore_age_max, explore_age_min
    df_explore = df_all[
        (df_all["age_at_season_start"].fillna(0) >= explore_age_min) &
        (df_all["age_at_season_start"].fillna(99) <= explore_age_max)
    ].copy()
else:
    df_explore = df_all.copy()

def _render_overview_tab(df_all: pd.DataFrame, df_index: pd.DataFrame, df_extract: pd.DataFrame) -> None:
    """Render the Overview tab."""
    st.markdown("<div class='section-header'>Dataset Snapshot</div>", unsafe_allow_html=True)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Unique Players", f"{df_all['player_id'].nunique():,}")
    with k2:
        st.metric("Total Rows", f"{len(df_all):,}")
    with k3:
        st.metric("Unique Teams", f"{df_all['team'].nunique():,}")
    with k4:
        st.metric("Seasons", f"{df_all['season'].nunique()}")
    with k5:
        st.metric("Competitions", f"{df_all['competition_slug'].nunique()}")

    st.markdown("---")
    st.markdown("<div class='section-header'>Extraction Coverage Heatmap</div>", unsafe_allow_html=True)

    if df_extract.empty:
        st.info("Extraction progress file not found. Skipping coverage heatmap.")
    else:
        df_map = df_extract.copy()
        df_map["competition"] = df_map["competition_slug"].map(COMP_NAMES).fillna(df_map["competition_slug"])
        df_map["display"] = df_map["competition_slug"] + " " + df_map["season"].astype(str)

        # extraction_progress.csv uses "extracted" (match count), not "players_extracted"
        value_col = "extracted" if "extracted" in df_map.columns else "players_extracted" if "players_extracted" in df_map.columns else None
        if value_col is None:
            z_numeric = np.zeros((len(df_map), 1))
        else:
            z_numeric = pd.to_numeric(df_map[value_col], errors="coerce").fillna(0).values.reshape(-1, 1)
        comps = df_map["display"].tolist()

        hm_fig = go.Figure(
            data=go.Heatmap(
                z=z_numeric,
                y=comps,
                x=["Extracted"] if value_col else ["—"],
                colorscale="YlGnBu",
                hovertemplate="<b>%{y}</b><br>Players: %{z}<extra></extra>",
            )
        )
        hm_fig.update_layout(
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            font=dict(color="#E6EDF3"),
            margin=dict(l=170, r=20, t=30, b=50),
            height=max(300, len(comps) * 22 + 60),
            yaxis=dict(categoryorder="total ascending"),
        )
        st.plotly_chart(hm_fig, use_container_width=True)

        with st.expander("Raw extraction progress"):
            raw_cols = [c for c in ["competition", "season", "extracted", "players_extracted", "extraction_date"] if c in df_map.columns]
            if raw_cols:
                disp = df_map[raw_cols]
                if "season" in disp.columns and "competition" in disp.columns:
                    disp = disp.sort_values(["season", "competition"], ascending=[False, True])
                st.dataframe(disp, hide_index=True, use_container_width=True)
            else:
                st.dataframe(df_map, hide_index=True, use_container_width=True)

    # Position breakdown
    st.markdown("<div class='section-header'>Position Breakdown</div>", unsafe_allow_html=True)
    pos_counts = df_all["player_position"].value_counts().reset_index()
    pos_counts.columns = ["Position", "Count"]
    pos_counts["Position Label"] = pos_counts["Position"].map(POSITION_NAMES).fillna(pos_counts["Position"])
    fig_pos = px.bar(
        pos_counts,
        y="Position",
        x="Count",
        color="Position",
        orientation="h",
        color_discrete_sequence=px.colors.sequential.YlOrBr,
        hover_data={"Position": True, "Position Label": True, "Count": True},
    )
    fig_pos.update_layout(
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3"),
        xaxis=dict(gridcolor="#30363D"),
        yaxis=dict(gridcolor="#30363D"),
        showlegend=False,
        margin=dict(l=100, r=20, t=30, b=30),
    )
    st.plotly_chart(fig_pos, use_container_width=True)

    # Top scorers per league
    st.markdown("<div class='section-header'>Top Scorers per League (Last 5 Seasons)</div>", unsafe_allow_html=True)
    top_seasons = sorted(df_all["season"].unique())[-5:]
    top_s = df_all[df_all["season"].isin(top_seasons)].copy()
    top_s = top_s.loc[top_s.groupby(["season", "competition_slug"])["goals"].idxmax()].reset_index(drop=True)
    top_s["League"] = top_s["competition_slug"].map(COMP_FLAGS).fillna("🏆") + " " + top_s["competition_slug"].map(COMP_NAMES).fillna(top_s["competition_slug"])
    top_s = top_s[["season", "League", "player_name", "goals", "team"]].sort_values(["season", "League"])
    st.dataframe(top_s.rename(columns={"player_name": "Player", "goals": "Goals"}), hide_index=True, use_container_width=True)

    # Season availability
    st.markdown("<div class='section-header'>Season Availability</div>", unsafe_allow_html=True)
    season_matrix = (
        df_all.groupby(["competition_slug", "season"]).size().unstack(fill_value=0).astype(bool).astype(int)
    )
    fig_season = px.imshow(
        season_matrix,
        labels=dict(x="Season", y="League", color="Data Available"),
        x=season_matrix.columns,
        y=[COMP_NAMES.get(c, c) for c in season_matrix.index],
        color_continuous_scale=["#30363D", "#C9A840"],
    )
    fig_season.update_layout(
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3"),
        xaxis=dict(gridcolor="#30363D", tickangle=0),
        yaxis=dict(gridcolor="#30363D"),
        margin=dict(l=120, r=20, t=30, b=50),
        height=max(300, len(season_matrix) * 22 + 60),
    )
    st.plotly_chart(fig_season, use_container_width=True)


def _render_distributions_tab(df_all: pd.DataFrame) -> None:
    """Render the Distributions tab."""
    st.markdown("<div class='section-header'>Metric Distributions</div>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        dist_leagues = st.multiselect("League(s)", options=sorted(df_all["competition_slug"].unique()), key="dist_leagues")
    with col2:
        avail_seasons = sorted(df_all["season"].unique(), reverse=True)
        dist_seasons = st.multiselect("Season(s)", options=avail_seasons, key="dist_seasons")
    with col3:
        dist_pos = st.selectbox(
            "Position",
            options=["All"] + [p for p in ["F", "M", "D", "G"] if p in df_all["player_position"].dropna().unique()],
            format_func=lambda x: "All" if x == "All" else POSITION_NAMES.get(x, x),
            key="dist_pos",
        )
    with col4:
        dist_mins = st.number_input("Min. minutes", 0, 4000, MIN_MINUTES_DEFAULT, 90, key="dist_mins")

    dpool = df_all.copy()
    if dist_leagues:
        dpool = dpool[dpool["competition_slug"].isin(dist_leagues)]
    if dist_seasons:
        dpool = dpool[dpool["season"].isin(dist_seasons)]
    if dist_pos != "All":
        dpool = dpool[dpool["player_position"] == dist_pos]
    if dist_mins > 0:
        dpool = dpool[dpool["total_minutes"] >= dist_mins]

    st.markdown(f"**Pool size:** {len(dpool):,} rows · {dpool['player_id'].nunique():,} players")

    if dpool.empty:
        st.warning("No players match the selected filters.")
    else:
        from dashboard.utils.charts import distribution_hist

        numeric_cols = [
            "avg_rating", "expectedGoals_per90", "expectedAssists_per90", "keyPass_per90",
            "goals_per90", "totalTackle_per90", "interceptionWon_per90", "duelWon_per90",
            "aerialWon_per90", "ballRecovery_per90", "totalPass_per90", "pass_accuracy_pct",
        ]
        avail_numeric = [c for c in numeric_cols if c in dpool.columns]

        sel_hist = st.selectbox("Select metric for histogram", avail_numeric, key="hist_metric")
        fig_hist = distribution_hist(dpool[sel_hist], f"Distribution of {sel_hist}", sel_hist)
        st.plotly_chart(fig_hist, use_container_width=True)

        st.markdown("---")
        st.markdown("<div class='section-header'>Scatter Explorer</div>", unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            x_col = st.selectbox("X-axis", avail_numeric, index=1, key="scatter_x")
        with c2:
            y_col = st.selectbox("Y-axis", avail_numeric, index=2, key="scatter_y")
        with c3:
            size_col = st.selectbox("Size by (optional)", ["None"] + avail_numeric, key="scatter_size")
        with c4:
            color_col = st.selectbox("Color by", ["None", "player_position", "league_name", "team"], key="scatter_color")

        fig_scatter = px.scatter(
            dpool,
            x=x_col,
            y=y_col,
            size=size_col if size_col != "None" else None,
            color=color_col if color_col != "None" else None,
            hover_data=["player_name", "team", "season", "avg_rating"],
            opacity=0.7,
        )
        fig_scatter.update_traces(marker=dict(line=dict(width=1, color="#0D1117")))
        fig_scatter.update_layout(
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            font=dict(color="#E6EDF3"),
            xaxis=dict(gridcolor="#30363D", title=x_col),
            yaxis=dict(gridcolor="#30363D", title=y_col),
            legend=dict(bgcolor="#161B22"),
            margin=dict(l=40, r=20, t=30, b=40),
        )
        st.plotly_chart(fig_scatter, use_container_width=True)


def _render_adhoc_tab(df_all: pd.DataFrame) -> None:
    """Render the Ad-hoc Table tab."""
    st.markdown("<div class='section-header'>Ad-hoc Player Table</div>", unsafe_allow_html=True)
    st.caption("Define your own columns and export a CSV table.")

    col1, col2, col3 = st.columns(3)
    with col1:
        adhoc_leagues = st.multiselect("Leagues", options=sorted(df_all["competition_slug"].unique()), key="adhoc_leagues")
    with col2:
        adhoc_seasons = st.multiselect("Seasons", options=sorted(df_all["season"].unique(), reverse=True), key="adhoc_seasons")
    with col3:
        adhoc_mins = st.number_input("Min. minutes", 0, 4000, 0, 90, key="adhoc_mins")

    df_adhoc = df_all.copy()
    if adhoc_leagues:
        df_adhoc = df_adhoc[df_adhoc["competition_slug"].isin(adhoc_leagues)]
    if adhoc_seasons:
        df_adhoc = df_adhoc[df_adhoc["season"].isin(adhoc_seasons)]
    if adhoc_mins > 0:
        df_adhoc = df_adhoc[df_adhoc["total_minutes"] >= adhoc_mins]

    st.markdown(f"**Rows:** {len(df_adhoc):,}")

    stats_for_table = st.multiselect(
        "Select stats to include",
        options=[c for c in df_adhoc.columns if c not in ["player_id", "season_id", "statline_id"]],
        default=["player_name", "league_name", "season", "team", "player_position", "total_minutes", "avg_rating",
                 "goals", "assists", "goals_per90", "expectedGoals_per90", "expectedAssists_per90", "keyPass_per90"],
        key="adhoc_cols",
    )
    if not stats_for_table:
        stats_for_table = ["player_name", "season", "avg_rating"]

    st.dataframe(df_adhoc[stats_for_table], use_container_width=True, height=400)
    csv_bytes = df_adhoc[stats_for_table].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="adhoc_table.csv", mime="text/csv")


def _render_form_trends_tab(df_all: pd.DataFrame) -> None:
    """Render the Form & Trends tab."""
    st.markdown("<div class='section-header'>Form & Trends</div>", unsafe_allow_html=True)

    available_rolling = load_rolling_form()

    form1, form2, form3 = st.columns(3)
    with form1:
        trend_leagues = st.multiselect("League(s)", options=sorted(df_all["competition_slug"].unique()), key="trend_leagues")
    with form2:
        trend_seasons = st.multiselect("Season(s)", options=sorted(df_all["season"].unique(), reverse=True), key="trend_seasons")
    with form3:
        trend_pos = st.selectbox(
            "Position",
            ["All"] + [p for p in ["F", "M", "D", "G"] if p in df_all["player_position"].dropna().unique()],
            format_func=lambda x: "All" if x == "All" else POSITION_NAMES.get(x, x),
            key="trend_pos",
        )

    pool = df_all.copy()
    if trend_leagues:
        pool = pool[pool["competition_slug"].isin(trend_leagues)]
    if trend_seasons:
        pool = pool[pool["season"].isin(trend_seasons)]
    if trend_pos != "All":
        pool = pool[pool["player_position"] == trend_pos]

    st.markdown(f"**Pool:** {pool['player_id'].nunique():,} players")

    if not available_rolling.empty:
        st.markdown("<div class='section-header'>League Rating Trends (All Rolling Windows)</div>", unsafe_allow_html=True)
        league_trend_opts = ["All"] + sorted(df_all["competition_slug"].unique())
        trend_league_sel = st.selectbox(
            "League trend",
            league_trend_opts,
            format_func=lambda x: "All leagues" if x == "All" else COMP_NAMES.get(x, x),
            key="league_trend_sel",
        )
        trend_rolling = available_rolling.copy()
        if trend_league_sel != "All":
            trend_rolling = trend_rolling[trend_rolling["competition_slug"] == trend_league_sel]
        if trend_seasons:
            trend_rolling = trend_rolling[trend_rolling["season"].isin(trend_seasons)]

        if not trend_rolling.empty:
            trend_agg = trend_rolling.groupby(["window"])["avg_rating"].mean().reset_index()
            fig_lt = go.Figure(go.Scatter(
                x=trend_agg["window"],
                y=trend_agg["avg_rating"],
                mode="lines+markers",
                line=dict(color="#C9A840", width=2),
                marker=dict(size=7),
                hovertemplate="<b>Window %{x}</b><br>Avg rating %{y:.2f}<extra></extra>",
            ))
            fig_lt.update_layout(
                paper_bgcolor="#0D1117",
                plot_bgcolor="#0D1117",
                font=dict(color="#E6EDF3"),
                xaxis=dict(gridcolor="#30363D", title="Rolling Window (matches)", dtick=1),
                yaxis=dict(gridcolor="#30363D", title="Avg Rating"),
                margin=dict(l=40, r=20, t=30, b=40),
                height=320,
            )
            st.plotly_chart(fig_lt, use_container_width=True)

    # Player-level form
    st.markdown("<div class='section-header'>Player-Level Rolling Form</div>", unsafe_allow_html=True)

    up = pool[["player_id", "player_name"]].drop_duplicates().sort_values("player_name")
    player_id_to_name = {r["player_id"]: r["player_name"] for _, r in up.iterrows()}
    sel_pid = st.selectbox("Player", options=up["player_id"].tolist(), format_func=lambda x: player_id_to_name.get(x, str(x)), key="form_player")
    sel_seasons = st.multiselect("Seasons (match-level)", options=sorted(df_all["season"].unique(), reverse=True), key="form_seasons")

    if sel_pid and sel_seasons:
        mlogs = [get_player_match_log(sel_pid, season=s) for s in sel_seasons]
        mlog = pd.concat(mlogs, ignore_index=True) if mlogs else pd.DataFrame()
        if not mlog.empty:
            st.plotly_chart(rating_trend(mlog, player_id_to_name.get(sel_pid, str(sel_pid))), use_container_width=True)
        else:
            st.info("No match-level data for this player/season.")


def _render_league_tab(df_all: pd.DataFrame) -> None:
    """Render the League Comparison tab."""
    st.markdown("<div class='section-header'>League Comparison</div>", unsafe_allow_html=True)

    l1, l2, l3 = st.columns(3)
    with l1:
        league_compare_league = st.selectbox(
            "League to analyze",
            options=sorted(df_all["competition_slug"].unique()),
            format_func=lambda x: f"{COMP_FLAGS.get(x,'🏆')} {COMP_NAMES.get(x,x)}",
            key="league_analyze",
        )
    with l2:
        league_compare_season = st.selectbox(
            "Season",
            options=sorted(df_all[df_all["competition_slug"] == league_compare_league]["season"].unique(), reverse=True),
            key="league_season",
        )
    with l3:
        compare_against = st.selectbox(
            "Compare against",
            options=["All other leagues (same season)", f"{league_compare_season} (all leagues)"],
            key="league_compare_against",
        )

    league_pool = df_all[
        (df_all["competition_slug"] == league_compare_league) &
        (df_all["season"] == league_compare_season)
    ]
    other_pool = df_all[
        (df_all["competition_slug"] != league_compare_league) &
        (df_all["season"] == league_compare_season)
    ]

    # Team-level comparison (only if team-level columns exist in df_all)
    st.markdown("<div class='section-header'>Team-Level Metrics</div>", unsafe_allow_html=True)
    team_metric_options = ["possession_avg", "pass_accuracy_avg", "goals_for", "goals_against", "xg_for_total", "xg_against_total"]
    team_metric_avail = [c for c in team_metric_options if c in df_all.columns]
    if not team_metric_avail:
        st.info("No team-level metrics in this dataset (player-level only). Skip to Player-Level Distribution below.")
    else:
        sel_team_metric = st.selectbox("Select team metric", team_metric_avail, key="team_metric", format_func=lambda x: x.replace("_", " ").title())
        if sel_team_metric and sel_team_metric in league_pool.columns:
            fig_t = go.Figure()
            fig_t.add_trace(go.Bar(
                y=[COMP_NAMES.get(league_compare_league, league_compare_league)],
                x=[league_pool[sel_team_metric].mean()],
                orientation="h",
                marker_color="#C9A840",
                name="Selected League",
            ))
            if not other_pool.empty and sel_team_metric in other_pool.columns:
                comp_means = other_pool.groupby("competition_slug")[sel_team_metric].mean().reset_index()
                for _, row in comp_means.iterrows():
                    fig_t.add_trace(go.Bar(
                        y=[COMP_NAMES.get(row["competition_slug"], row["competition_slug"])],
                        x=[row[sel_team_metric]],
                        orientation="h",
                        marker_color="#6C7A89",
                        name=row["competition_slug"],
                        showlegend=False,
                    ))
            fig_t.update_layout(
                paper_bgcolor="#0D1117",
                plot_bgcolor="#0D1117",
                font=dict(color="#E6EDF3"),
                xaxis=dict(gridcolor="#30363D", title=sel_team_metric.replace("_", " ").title()),
                yaxis=dict(gridcolor="#30363D", categoryorder="total ascending"),
                margin=dict(l=120, r=20, t=30, b=40),
                height=max(300, len(set(df_all["competition_slug"])) * 22 + 60),
            )
            st.plotly_chart(fig_t, use_container_width=True)

    # Player-level distribution
    st.markdown("<div class='section-header'>Player-Level Distribution</div>", unsafe_allow_html=True)
    player_metric_options = ["avg_rating", "goals_per90", "expectedGoals_per90", "keyPass_per90", "totalTackle_per90"]
    player_metric_avail = [c for c in player_metric_options if c in df_all.columns]
    if not player_metric_avail:
        st.info("No player metrics available for distribution.")
    else:
        sel_player_metric = st.selectbox("Select player metric", player_metric_avail, key="player_metric", format_func=lambda x: x.replace("_", " ").title())
        if not sel_player_metric or sel_player_metric not in league_pool.columns:
            st.warning("Selected metric not in data.")
        else:
            fig_pv = go.Figure()
            fig_pv.add_trace(go.Violin(
                y=[COMP_NAMES.get(league_compare_league, league_compare_league)] * len(league_pool),
                x=league_pool[sel_player_metric].dropna(),
                orientation="h",
                line=dict(color="#C9A840"),
                fillcolor="rgba(201,168,64,0.25)",
                name=COMP_NAMES.get(league_compare_league, league_compare_league),
                box_visible=True,
                meanline_visible=True,
            ))
            for comp in df_all["competition_slug"].unique():
                if comp != league_compare_league:
                    other_comp = df_all[(df_all["competition_slug"] == comp) & (df_all["season"] == league_compare_season)]
                    if not other_comp.empty:
                        fig_pv.add_trace(go.Violin(
                            y=[COMP_NAMES.get(comp, comp)] * len(other_comp),
                            x=other_comp[sel_player_metric].dropna(),
                            orientation="h",
                            line=dict(color="#6C7A89"),
                            fillcolor="rgba(108,122,137,0.15)",
                            name=COMP_NAMES.get(comp, comp),
                            box_visible=True,
                            meanline_visible=True,
                            opacity=0.6,
                        ))
            fig_pv.update_layout(
                paper_bgcolor="#0D1117",
                plot_bgcolor="#0D1117",
                font=dict(color="#E6EDF3"),
                xaxis=dict(gridcolor="#30363D", title=sel_player_metric.replace("_", " ").title()),
                yaxis=dict(gridcolor="#30363D", categoryorder="total ascending"),
                margin=dict(l=120, r=20, t=30, b=40),
                height=max(300, len(df_all["competition_slug"].unique()) * 35 + 60),
                violinmode="overlay",
                showlegend=False,
            )
            st.plotly_chart(fig_pv, use_container_width=True)


def _render_age_curves_tab(df_all: pd.DataFrame) -> None:
    """Render the Age Curves tab."""
    st.markdown("<div class='section-header'>Age Curves</div>", unsafe_allow_html=True)
    st.caption("Metric evolution by age across positions.")

    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        age_leagues = st.multiselect("League(s)", options=sorted(df_all["competition_slug"].unique()), key="age_leagues")
    with ac2:
        age_pos = st.selectbox(
            "Position",
            ["All"] + [p for p in ["F", "M", "D", "G"] if p in df_all["player_position"].dropna().unique()],
            format_func=lambda x: "All" if x == "All" else POSITION_NAMES.get(x, x),
            key="age_pos",
        )
    with ac3:
        age_metric_options = ["avg_rating", "goals_per90", "expectedGoals_per90", "expectedAssists_per90", "keyPass_per90"]
        age_metric_avail = [c for c in age_metric_options if c in df_all.columns]
        age_metric = st.selectbox("Metric", age_metric_avail, key="age_metric", format_func=lambda x: x.replace("_", " ").title())

    pool = df_all.copy()
    if age_leagues:
        pool = pool[pool["competition_slug"].isin(age_leagues)]
    if age_pos != "All":
        pool = pool[pool["player_position"] == age_pos]
    if pool.empty:
        st.warning("No players match filters.")
        return

    ages = pool["age_at_season_start"].dropna()
    if ages.empty:
        st.warning("No age data available.")
        return

    # Scatter plot with mean curve
    fig_ac = go.Figure()
    fig_ac.add_trace(go.Scatter(
        x=ages,
        y=pool[age_metric],
        mode="markers",
        marker=dict(color="#C9A840", size=5, opacity=0.5),
        name="Players",
    ))

    # Mean by age
    mean_by_age = pool.groupby("age_at_season_start")[age_metric].mean().reset_index()
    fig_ac.add_trace(go.Scatter(
        x=mean_by_age["age_at_season_start"],
        y=mean_by_age[age_metric],
        mode="lines",
        line=dict(color="#FFFFFF", width=2),
        name="Mean",
    ))

    fig_ac.update_layout(
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3"),
        xaxis=dict(gridcolor="#30363D", title="Age at Season Start"),
        yaxis=dict(gridcolor="#30363D", title=age_metric.replace("_", " ").title()),
        margin=dict(l=40, r=20, t=30, b=40),
        height=400,
        legend=dict(bgcolor="#161B22"),
    )
    st.plotly_chart(fig_ac, use_container_width=True)

    # Squad age distribution
    if "age_band" in pool.columns:
        st.markdown("<div class='section-header'>Squad Age Distribution</div>", unsafe_allow_html=True)
        age_band_counts = pool["age_band"].value_counts().reset_index()
        age_band_counts.columns = ["Age Band", "Count"]
        fig_ab = px.bar(
            age_band_counts,
            x="Age Band",
            y="Count",
            color="Age Band",
            color_discrete_sequence=px.colors.sequential.YlOrBr,
        )
        fig_ab.update_layout(
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            font=dict(color="#E6EDF3"),
            xaxis=dict(gridcolor="#30363D"),
            yaxis=dict(gridcolor="#30363D"),
            showlegend=False,
            margin=dict(l=40, r=20, t=30, b=40),
        )
        st.plotly_chart(fig_ab, use_container_width=True)

    # Peak age by position (if data available)
    peak_age_data = load_peak_age_by_position()
    if not peak_age_data.empty:
        st.markdown("<div class='section-header'>Peak Age by Position</div>", unsafe_allow_html=True)
        st.dataframe(peak_age_data, use_container_width=True, hide_index=True)


# =============================================================================
# TABS (must be after function definitions so names are defined)
# =============================================================================
tab_overview, tab_dist, tab_adhoc, tab_form, tab_league, tab_age = st.tabs([
    "Overview", "Distributions", "Ad-hoc Table", "Form & Trends", "League Comparison", "Age Curves",
])

with tab_overview:
    _render_overview_tab(df_explore, df_index, df_extract)

with tab_dist:
    _render_distributions_tab(df_explore)

with tab_adhoc:
    _render_adhoc_tab(df_explore)

with tab_form:
    _render_form_trends_tab(df_explore)

with tab_league:
    _render_league_tab(df_explore)

with tab_age:
    _render_age_curves_tab(df_explore)
