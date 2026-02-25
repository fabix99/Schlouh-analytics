"""Teams — deep-dive team analysis, playing styles, strengths/weaknesses, and match log."""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from typing import Optional
from unicodedata import normalize as unicode_normalize
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from dashboard.utils.data import (
    load_team_season_stats,
    load_match_summary,
    load_tactical_profiles,
    load_match_momentum,
    load_incidents,
    get_team_wdl,
    get_team_last_matches,
    get_similar_teams,
    build_team_narrative,
    load_managers,
    get_form_xi,
    get_team_sub_impact,
    load_manager_career_stats,
)
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, TACTICAL_INDEX_LABELS, TACTICAL_TAGS, PLAYER_COLORS, MIN_MINUTES_DEFAULT,
)
from dashboard.utils.charts import radar_chart
from dashboard.utils.sidebar import render_sidebar


def _normalize_team_search(text: str) -> str:
    """Normalize text for team search (accents, case)."""
    if not text:
        return ""
    return unicode_normalize("NFKD", str(text).lower()).encode("ASCII", "ignore").decode()


def _wdl_from_matches(matches_df: pd.DataFrame, team_score_col: str, opp_score_col: str) -> dict:
    """Compute W-D-L from a DataFrame of matches where team score and opp score columns are known."""
    wins = draws = losses = 0
    for _, row in matches_df.iterrows():
        t, o = row.get(team_score_col), row.get(opp_score_col)
        if pd.isna(t) or pd.isna(o):
            continue
        t, o = int(t), int(o)
        if t > o:
            wins += 1
        elif t < o:
            losses += 1
        else:
            draws += 1
    return {"W": wins, "D": draws, "L": losses}


st.set_page_config(page_title="Teams · Schlouh", page_icon="🏆", layout="wide")
render_sidebar()

with st.spinner("Loading team data…"):
    df_teams = load_team_season_stats()
    df_matches = load_match_summary()
    df_tac = load_tactical_profiles()

st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">🏆 Teams</div>
        <div class="page-hero-sub">
            Deep-dive team analysis: playing styles, strengths/weaknesses, tactical identity,
            and match-by-match performance.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def _render_team_analysis(
    team_name: str,
    team_season: str,
    team_comp: str,
    team_row: pd.Series,
    tac_row: Optional[pd.Series],
    df_teams: pd.DataFrame,
    df_matches: pd.DataFrame,
) -> None:
    """Render complete team analysis view."""
    st.markdown(f"## {team_name}")

    # Header info
    flag = COMP_FLAGS.get(team_comp, "🏆")
    pos = team_row.get("position_ordinal", team_row.get("position_desc", "N/A"))
    apps_val = int(team_row.get("matches_total", 0) or 0)
    rel_tier = "High" if apps_val >= 15 else ("Medium" if apps_val >= 10 else "Low")
    rel_colors = {"High": "#C9A840", "Medium": "#FFD93D", "Low": "#FF6B6B"}
    rel_color = rel_colors.get(rel_tier, "#8B949E")

    st.markdown(
        f"<div style='color:#8B949E;margin-bottom:0.4rem;'>"
        f"{flag} <b>{COMP_NAMES.get(team_comp, team_comp)} {team_season}</b> &nbsp;·&nbsp; "
        f"<b>League position:</b> {pos}"
        f"</div>"
        f"<div style='font-size:0.85rem;color:#8B949E;margin-bottom:1rem;'>"
        f"Based on <b>{apps_val}</b> matches &nbsp;"
        f"<span style='background:{rel_color}22;border:1px solid {rel_color}55;border-radius:12px;"
        f"padding:2px 8px;font-size:0.78rem;font-weight:600;color:{rel_color};'>"
        f"Sample: {rel_tier}</span></div>",
        unsafe_allow_html=True,
    )

    # Tabs
    tab_overview, tab_style, tab_matches, tab_manager, tab_opponent, tab_inspire = st.tabs([
        "Overview", "Playing Style", "Matches", "Manager", "Opponent Analysis", "League Inspiration",
    ])

    with tab_overview:
        _render_team_overview(team_name, team_season, team_comp, team_row, tac_row, df_teams, df_matches)

    with tab_style:
        _render_playing_style(team_name, team_season, team_comp, team_row, tac_row, df_teams)

    with tab_matches:
        _render_matches_tab(team_name, team_season, team_comp, team_row, df_matches)

    with tab_manager:
        _render_manager_tab(team_name, team_season, team_comp)

    with tab_opponent:
        _render_opponent_analysis(team_name, team_season, team_comp, df_teams, team_row)

    with tab_inspire:
        _render_league_inspiration(team_name, team_season, team_comp, df_teams, team_row)


def _render_team_overview(
    team_name: str,
    team_season: str,
    team_comp: str,
    team_row: pd.Series,
    tac_row: Optional[pd.Series],
    df_teams: pd.DataFrame,
    df_matches: pd.DataFrame,
) -> None:
    """Render team overview metrics."""
    # Core metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    wdl = get_team_wdl(team_name, team_season, team_comp)
    with c1:
        st.metric("W-D-L", f"{wdl['W']}-{wdl['D']}-{wdl['L']}")
    with c2:
        st.metric("Goals For", int(team_row.get("goals_for", 0) or 0))
    with c3:
        st.metric("Goals Against", int(team_row.get("goals_against", 0) or 0))
    with c4:
        st.metric("xG For", f"{team_row.get('xg_for_total', 0):.1f}")
    with c5:
        st.metric("xG Against", f"{team_row.get('xg_against_total', 0):.1f}")

    # Narrative (build_team_narrative expects ts, tactical_row, wdl, league_pool)
    comp_pool = df_teams[
        (df_teams["season"] == team_season) &
        (df_teams["competition_slug"] == team_comp)
    ]
    narrative = build_team_narrative(team_row, tac_row, wdl, comp_pool)
    with st.expander("📝 Team Narrative", expanded=True):
        st.markdown(f"<div class='narrative-box'>{narrative}</div>", unsafe_allow_html=True)

    # Comparison bar chart
    st.markdown("<div class='section-header'>Team vs. League Average</div>", unsafe_allow_html=True)

    compare_metrics = [
        "goals_for_per_game", "goals_against_per_game", "xg_for_per_game", "xg_against_per_game",
        "possession_avg", "pass_accuracy_avg", "shots_total_per_game", "big_chances_total_per_game",
    ]
    compare_metrics = [c for c in compare_metrics if c in df_teams.columns]

    team_vals = team_row[compare_metrics].values
    league_means = comp_pool[compare_metrics].mean().values

    labels = [c.replace("_per_game", "").replace("_", " ").title() for c in compare_metrics]

    fig_comp = go.Figure()
    fig_comp.add_trace(go.Bar(
        x=labels,
        y=team_vals,
        name=team_name,
        marker_color=PLAYER_COLORS[0],
        text=[f"{v:.2f}" for v in team_vals],
        textposition="outside",
    ))
    fig_comp.add_trace(go.Bar(
        x=labels,
        y=league_means,
        name="League Avg",
        marker_color="#6C7A89",
        text=[f"{v:.2f}" for v in league_means],
        textposition="outside",
    ))
    fig_comp.update_layout(
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3"),
        barmode="group",
        xaxis=dict(gridcolor="#30363D", tickangle=45),
        yaxis=dict(gridcolor="#30363D"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=80, b=80),
        height=400,
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    # Home/Away split (compute from df_matches; column names may vary)
    st.markdown("<div class='section-header'>Home / Away Split</div>", unsafe_allow_html=True)
    h1, h2 = st.columns(2)
    home_col = "home_team_name" if "home_team_name" in df_matches.columns else "home_team"
    away_col = "away_team_name" if "away_team_name" in df_matches.columns else "away_team"
    score_h = "goals_home" if "goals_home" in df_matches.columns else "home_score"
    score_a = "goals_away" if "goals_away" in df_matches.columns else "away_score"
    mask = (df_matches["season"] == team_season) & (df_matches["competition_slug"] == team_comp)
    with h1:
        home_m = df_matches[mask & (df_matches[home_col] == team_name)]
        home_wdl = _wdl_from_matches(home_m, score_h, score_a)
        st.metric("Home W-D-L", f"{home_wdl['W']}-{home_wdl['D']}-{home_wdl['L']}")
    with h2:
        away_m = df_matches[mask & (df_matches[away_col] == team_name)]
        away_wdl = _wdl_from_matches(away_m, score_a, score_h)
        st.metric("Away W-D-L", f"{away_wdl['W']}-{away_wdl['D']}-{away_wdl['L']}")

    # First/Second half split — use xG splits (goals-by-half not in dataset)
    st.markdown("<div class='section-header'>First Half / Second Half Split (xG)</div>", unsafe_allow_html=True)
    st.caption("Actual goals by half not in dataset — showing xG splits as proxy.")
    f1, f2, f3 = st.columns(3)
    with f1:
        fh = team_row.get("xg_for_first_half", 0)
        sh = team_row.get("xg_for_second_half", 0)
        st.metric("FH xG", f"{float(fh or 0):.1f}")
    with f2:
        st.metric("SH xG", f"{float(sh or 0):.1f}")
    with f3:
        pct = (sh / (fh + sh) * 100) if (fh + sh) > 0 else 0
        st.metric("SH xG %", f"{pct:.0f}%")

    # Substitution impact
    sub_impact = get_team_sub_impact(team_name, team_season, team_comp)
    if sub_impact:
        st.markdown("<div class='section-header'>Substitution Impact</div>", unsafe_allow_html=True)
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.metric("Subs Tracked", int(sub_impact.get("n_subs", 0)))
        with s2:
            si_rating = sub_impact.get("player_in_rating")
            st.metric("Avg Sub Rating", f"{si_rating:.2f}" if si_rating is not None else "N/A")
        with s3:
            si_goals = sub_impact.get("player_in_goals")
            st.metric("Avg Sub Goals", f"{si_goals:.2f}" if si_goals is not None else "N/A")
        with s4:
            si_mins = sub_impact.get("minutes_after_sub")
            st.metric("Avg Mins After Sub", f"{si_mins:.0f}" if si_mins is not None else "N/A")

    # Last 5 matches
    st.markdown("<div class='section-header'>Last 5 Matches</div>", unsafe_allow_html=True)
    last5 = get_team_last_matches(team_name, team_season, team_comp, n=5)
    if not last5.empty:
        disp_cols = [c for c in ["date", "opponent", "home_away", "score", "result"] if c in last5.columns]
        st.dataframe(
            last5[disp_cols].rename(columns={
                "date": "Date", "opponent": "Opponent", "home_away": "H/A",
                "score": "Score", "result": "Result",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No match data available for last 5 matches.")


def _render_playing_style(
    team_name: str,
    team_season: str,
    team_comp: str,
    team_row: pd.Series,
    tac_row: Optional[pd.Series],
    df_teams: pd.DataFrame,
) -> None:
    """Render playing style and tactical analysis."""
    if tac_row is None:
        st.info("Tactical profile data not available for this team/season.")
        return

    # Tactical radar
    st.markdown("<div class='section-header'>Tactical Identity (Radar)</div>", unsafe_allow_html=True)

    radar_stats = [
        "possession_index", "directness_index", "pressing_index", "aerial_index",
        "crossing_index", "chance_creation_index", "defensive_solidity",
        "home_away_consistency", "second_half_intensity",
    ]
    radar_stats = [s for s in radar_stats if s in tac_row.index]

    # Build percentile data for radar (season × competition pool)
    df_tac_loaded = load_tactical_profiles()
    pool_for_pct = df_tac_loaded[
        (df_tac_loaded["season"] == team_season) &
        (df_tac_loaded["competition_slug"] == team_comp)
    ].copy()
    pool_n = len(pool_for_pct)

    for s in radar_stats:
        if s in pool_for_pct.columns:
            pool_for_pct[f"{s}_pct"] = pool_for_pct[s].rank(pct=True, na_option="keep") * 100

    radar_rows = []
    team_in_pool = pool_for_pct[pool_for_pct["team_name"] == team_name] if "team_name" in pool_for_pct.columns else pd.DataFrame()
    for s in radar_stats:
        if s in tac_row.index:
            if not team_in_pool.empty and f"{s}_pct" in team_in_pool.columns:
                pct = float(team_in_pool.iloc[0][f"{s}_pct"])
            elif pool_n > 1 and s in pool_for_pct.columns:
                col = pool_for_pct[s].dropna()
                val = tac_row[s]
                pct = float(((col < val).sum() + 0.5 * (col == val).sum()) / len(col) * 100) if len(col) > 0 else 50.0
            else:
                pct = 50.0
            radar_rows.append({
                "player_name": team_name,
                "stat": s,
                "pct": pct,
                "raw": tac_row[s],
            })

    if radar_rows:
        radar_df = pd.DataFrame(radar_rows)
        labels = [TACTICAL_INDEX_LABELS.get(s, s) for s in radar_stats]
        pool_label = f"{COMP_NAMES.get(team_comp, team_comp)} {team_season} (n={pool_n})"
        fig_radar = radar_chart(radar_df, labels, title=f"Tactical Profile — {pool_label}")
        st.plotly_chart(fig_radar, use_container_width=True)
        st.caption(f"ℹ️ Percentiles within: {pool_label}. All axes 0–100 (higher = stronger tendency).")

    # Tactical identity tags
    st.markdown("<div class='section-header'>Tactical Identity</div>", unsafe_allow_html=True)

    tags = []
    for col, (threshold, tag_label) in TACTICAL_TAGS.items():
        val = tac_row.get(col)
        if pd.notna(val) and val >= threshold:
            tags.append(tag_label)

    if tags:
        tags_html = "".join(f"<span class='tag-pill'>{t}</span>" for t in tags)
        st.markdown(f"<div>{tags_html}</div><br>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='color:#8B949E;'>No strong tactical identity detected.</span>", unsafe_allow_html=True)

    # Strengths and Weaknesses
    st.markdown("<div class='section-header'>📈 Strengths & Weaknesses</div>", unsafe_allow_html=True)

    # Compute percentiles for team metrics
    comp_pool = df_teams[
        (df_teams["season"] == team_season) &
        (df_teams["competition_slug"] == team_comp)
    ]

    team_metrics = [
        "goals_for_per_game", "goals_against_per_game", "xg_for_per_game", "xg_against_per_game",
        "possession_avg", "pass_accuracy_avg", "shots_total_per_game", "big_chances_total_per_game",
    ]
    team_metrics = [c for c in team_metrics if c in team_row.index]

    pct_data = {}
    for m in team_metrics:
        if m in comp_pool.columns and pd.notna(team_row.get(m)):
            col = comp_pool[m].dropna()
            n = len(col)
            if n > 0:
                val = team_row[m]
                pct_data[m] = float(((col < val).sum() + 0.5 * (col == val).sum()) / n * 100)
            else:
                pct_data[m] = 50.0

    # Top 3 strengths
    strengths = sorted(pct_data.items(), key=lambda x: x[1], reverse=True)[:3]
    weaknesses = sorted(pct_data.items(), key=lambda x: x[1])[:3]

    s1, s2 = st.columns(2)
    with s1:
        st.markdown("<b>Strengths</b>", unsafe_allow_html=True)
        for metric, pct in strengths:
            label = metric.replace("_per_game", "").replace("_", " ").title()
            st.markdown(
                f"<span class='strength-pill'>{label}: {pct:.0f}th percentile</span>",
                unsafe_allow_html=True,
            )

    with s2:
        st.markdown("<b>Areas to Improve</b>", unsafe_allow_html=True)
        for metric, pct in weaknesses:
            label = metric.replace("_per_game", "").replace("_", " ").title()
            st.markdown(
                f"<span class='weakness-chip'>{label}: {pct:.0f}th percentile</span>",
                unsafe_allow_html=True,
            )

    # Form XI (best player per position over last N matches)
    form_xi = get_form_xi(team_name, team_season, team_comp)
    if form_xi is not None and not form_xi.empty:
        st.markdown("<div class='section-header'>Form XI (Last 5 Matches)</div>", unsafe_allow_html=True)
        st.caption("Best-rated player per position (min. 45 min played) over last 5 matches")
        xi_cols = st.columns(min(4, len(form_xi)))
        pos_col = next((c for c in ["position", "player_position"] if c in form_xi.columns), None)
        for i, (_, player) in enumerate(form_xi.iterrows()):
            with xi_cols[i % len(xi_cols)]:
                pos = player.get(pos_col, "?") if pos_col else "?"
                apps = int(player.get("appearances", 0))
                rating = player.get("avg_rating")
                stats_str = f"Apps: {apps} · Rating: {rating:.2f}" if pd.notna(rating) else f"Apps: {apps}"
                st.markdown(
                    f"<div style='background:#161B22;padding:10px;border-radius:6px;"
                    f"border:1px solid #30363D;text-align:center;'>"
                    f"<b style='color:#F0F6FC;'>{player.get('player_name', 'Unknown')}</b><br>"
                    f"<span style='font-size:0.8rem;color:#8B949E;'>{pos}</span><br>"
                    f"<span style='font-size:0.75rem;color:#C9A840;'>{stats_str}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )


def _render_matches_tab(
    team_name: str,
    team_season: str,
    team_comp: str,
    team_row: pd.Series,
    df_matches: pd.DataFrame,
) -> None:
    """Render match log and details."""
    st.markdown("<div class='section-header'>Full Match Log</div>", unsafe_allow_html=True)

    # Use actual column names from match_summary
    home_col = next((c for c in ["home_team_name", "home_team"] if c in df_matches.columns), None)
    away_col = next((c for c in ["away_team_name", "away_team"] if c in df_matches.columns), None)
    date_col = next((c for c in ["match_date_utc", "date_utc"] if c in df_matches.columns), None)
    score_h_col = next((c for c in ["home_score", "goals_home"] if c in df_matches.columns), None)
    score_a_col = next((c for c in ["away_score", "goals_away"] if c in df_matches.columns), None)

    if not home_col or not away_col:
        st.info("No match data available.")
        return

    mask = (
        ((df_matches[home_col] == team_name) | (df_matches[away_col] == team_name)) &
        (df_matches["season"] == team_season) &
        (df_matches["competition_slug"] == team_comp)
    )
    team_matches = df_matches[mask].copy()
    if date_col:
        team_matches = team_matches.sort_values(date_col, ascending=False)

    if team_matches.empty:
        st.info("No match data available.")
        return

    # Add result indicator
    def get_result(row):
        if score_h_col and score_a_col and pd.notna(row.get(score_h_col)) and pd.notna(row.get(score_a_col)):
            gh, ga = int(row[score_h_col]), int(row[score_a_col])
            if row[home_col] == team_name:
                return "W" if gh > ga else ("D" if gh == ga else "L")
            else:
                return "W" if ga > gh else ("D" if ga == gh else "L")
        return "?"

    team_matches["result"] = team_matches.apply(get_result, axis=1)

    # xG trend
    xg_h = next((c for c in ["home_xg", "xg_home_total"] if c in team_matches.columns), None)
    xg_a = next((c for c in ["away_xg", "xg_away_total"] if c in team_matches.columns), None)
    if xg_h and xg_a:
        st.markdown("<div class='section-header'>xG Trend Over Season</div>", unsafe_allow_html=True)
        team_matches_sorted = team_matches.sort_values(date_col) if date_col else team_matches
        team_xg = team_matches_sorted.apply(lambda r: r[xg_h] if r[home_col] == team_name else r[xg_a], axis=1)
        opp_xg = team_matches_sorted.apply(lambda r: r[xg_a] if r[home_col] == team_name else r[xg_h], axis=1)
        fig_xg = go.Figure()
        fig_xg.add_trace(go.Scatter(x=list(range(len(team_matches_sorted))), y=team_xg, mode="lines+markers", name=f"{team_name} xG", line=dict(color=PLAYER_COLORS[0])))
        fig_xg.add_trace(go.Scatter(x=list(range(len(team_matches_sorted))), y=opp_xg, mode="lines+markers", name="Opponent xG", line=dict(color="#6C7A89")))
        fig_xg.update_layout(paper_bgcolor="#0D1117", plot_bgcolor="#0D1117", font=dict(color="#E6EDF3"), xaxis=dict(gridcolor="#30363D", title="Match Number"), yaxis=dict(gridcolor="#30363D", title="xG"), legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(l=40, r=20, t=80, b=40), height=300)
        st.plotly_chart(fig_xg, use_container_width=True)

    # Match table
    disp_cols = [c for c in [date_col, home_col, away_col, score_h_col, score_a_col, "result"] if c]
    rename_map = {date_col: "Date", home_col: "Home", away_col: "Away", score_h_col: "H", score_a_col: "A", "result": "Res"}
    disp = team_matches[disp_cols].rename(columns=rename_map)
    if "Date" in disp.columns:
        disp["Date"] = pd.to_datetime(disp["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # Match fingerprint
    st.markdown("<div class='section-header'>Match Fingerprint (Select Match)</div>", unsafe_allow_html=True)
    st.caption("Select a match to see detailed momentum and incident data.")
    match_options = team_matches.reset_index(drop=True)
    def _match_label(row):
        d = str(row.get(date_col, ""))[:10] if date_col else "?"
        h = row.get(home_col, "?")
        a = row.get(away_col, "?")
        gh = int(row[score_h_col]) if score_h_col and pd.notna(row.get(score_h_col)) else "?"
        ga = int(row[score_a_col]) if score_a_col and pd.notna(row.get(score_a_col)) else "?"
        return f"{d} — {h} {gh}–{ga} {a}"
    match_labels = [_match_label(row) for _, row in match_options.iterrows()]
    sel_match_idx = st.selectbox("Select match", range(len(match_labels)), format_func=lambda i: match_labels[i], key="fingerprint_match")
    sel_match = match_options.iloc[sel_match_idx]

    # Show momentum if available
    match_id = sel_match.get("match_id")
    if match_id:
        try:
            momentum_all = load_match_momentum()
            momentum_data = momentum_all[momentum_all["match_id"] == match_id] if "match_id" in momentum_all.columns else pd.DataFrame()
        except Exception:
            momentum_data = pd.DataFrame()
        if not momentum_data.empty and "momentum_value" in momentum_data.columns:
            st.markdown("<div class='section-header'>Match Momentum</div>", unsafe_allow_html=True)
            fig_mom = go.Figure()
            fig_mom.add_trace(go.Scatter(
                x=momentum_data.get("minute", range(len(momentum_data))),
                y=momentum_data["momentum_value"],
                mode="lines",
                fill="tozeroy",
                line=dict(color=PLAYER_COLORS[0]),
            ))
            fig_mom.update_layout(
                paper_bgcolor="#0D1117",
                plot_bgcolor="#0D1117",
                font=dict(color="#E6EDF3"),
                xaxis=dict(gridcolor="#30363D", title="Minute"),
                yaxis=dict(gridcolor="#30363D", title="Momentum"),
                margin=dict(l=40, r=20, t=30, b=40),
                height=250,
            )
            st.plotly_chart(fig_mom, use_container_width=True)

        # Show incidents
        try:
            incidents_all = load_incidents()
            incidents = incidents_all[incidents_all.get("match_id", pd.Series()) == match_id] if "match_id" in incidents_all.columns else pd.DataFrame()
        except Exception:
            incidents = pd.DataFrame()
        if not incidents.empty:
            st.markdown("<div class='section-header'>Match Incidents</div>", unsafe_allow_html=True)
            inc_disp_cols = [c for c in ["time", "incidentType", "player_name"] if c in incidents.columns]
            st.dataframe(incidents[inc_disp_cols].rename(columns={
                "time": "Minute", "incidentType": "Type", "player_name": "Player",
            }), use_container_width=True, hide_index=True)


def _render_manager_tab(team_name: str, team_season: str, team_comp: str) -> None:
    """Render manager information."""
    st.markdown("<div class='section-header'>Manager</div>", unsafe_allow_html=True)

    try:
        managers_all = load_managers()
        mask = (managers_all.get("team_name", pd.Series()) == team_name) if "team_name" in managers_all.columns else pd.Series(dtype=bool)
        if "season" in managers_all.columns:
            mask &= managers_all["season"] == team_season
        if "competition_slug" in managers_all.columns:
            mask &= managers_all["competition_slug"] == team_comp
        managers = managers_all[mask] if not mask.empty else managers_all[managers_all.get("team_name", pd.Series()) == team_name]
    except Exception:
        managers = pd.DataFrame()

    if managers.empty:
        st.info("Manager data not available for this team/season.")
        return

    manager = managers.iloc[0]
    manager_col = next((c for c in ["manager_name", "name"] if c in manager.index), None)
    manager_name = manager.get(manager_col, "Unknown") if manager_col else "Unknown"
    st.markdown(f"**Manager:** {manager_name}")

    # Manager career stats
    if manager_name and manager_name != "Unknown":
        try:
            career_all = load_manager_career_stats()
            name_col = next((c for c in ["manager_name", "name"] if c in career_all.columns), None)
            career_stats = career_all[career_all[name_col] == manager_name].iloc[0] if name_col and not career_all.empty else pd.Series()
        except Exception:
            career_stats = pd.Series()

        if not career_stats.empty:
            st.markdown("<div class='section-header'>Manager Career</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            wins = int(career_stats.get("wins", 0) or 0)
            draws = int(career_stats.get("draws", 0) or 0)
            losses = int(career_stats.get("losses", 0) or 0)
            total = wins + draws + losses
            with c1:
                st.metric("Career Wins", wins)
            with c2:
                st.metric("Career Draws", draws)
            with c3:
                st.metric("Career Losses", losses)
            with c4:
                win_pct = wins / total * 100 if total > 0 else 0
                st.metric("Career Win %", f"{win_pct:.1f}%")

    if len(managers) > 1:
        with st.expander("Manager History"):
            hist_cols = [c for c in ["manager_name", "name", "start_date", "end_date", "matches"] if c in managers.columns]
            st.dataframe(managers[hist_cols], hide_index=True)


def _render_opponent_analysis(
    team_name: str,
    team_season: str,
    team_comp: str,
    df_teams: pd.DataFrame,
    team_row: pd.Series,
) -> None:
    """Render opponent analysis view."""
    st.markdown("<div class='section-header'>Opponent Analysis</div>", unsafe_allow_html=True)
    st.caption("Compare against a specific opponent and see head-to-head data.")

    # Select opponent
    opponents = sorted(df_teams[
        (df_teams["season"] == team_season) &
        (df_teams["competition_slug"] == team_comp) &
        (df_teams["team_name"] != team_name)
    ]["team_name"].unique())

    opponent = st.selectbox("Select opponent", options=opponents, key="opponent_select")

    if opponent:
        opp_row = df_teams[
            (df_teams["team_name"] == opponent) &
            (df_teams["season"] == team_season) &
            (df_teams["competition_slug"] == team_comp)
        ].iloc[0]

        # Side-by-side comparison
        st.markdown("<div class='section-header'>Side-by-Side Stats</div>", unsafe_allow_html=True)

        compare_metrics = [
            "goals_for_per_game", "goals_against_per_game", "xg_for_per_game", "xg_against_per_game",
            "possession_avg", "pass_accuracy_avg",
        ]
        compare_metrics = [c for c in compare_metrics if c in df_teams.columns]

        comp_data = pd.DataFrame({
            team_name: [team_row.get(m, 0) for m in compare_metrics],
            opponent: [opp_row.get(m, 0) for m in compare_metrics],
        }, index=[m.replace("_per_game", "").replace("_", " ").title() for m in compare_metrics])

        st.dataframe(comp_data, use_container_width=True)

        # Head-to-head results
        st.markdown("<div class='section-header'>Head-to-Head (This Season)</div>", unsafe_allow_html=True)

        df_h2h_src = load_match_summary()
        hc = next((c for c in ["home_team_name", "home_team"] if c in df_h2h_src.columns), None)
        ac = next((c for c in ["away_team_name", "away_team"] if c in df_h2h_src.columns), None)
        dc = next((c for c in ["match_date_utc", "date_utc"] if c in df_h2h_src.columns), None)
        shc = next((c for c in ["home_score", "goals_home"] if c in df_h2h_src.columns), None)
        sac = next((c for c in ["away_score", "goals_away"] if c in df_h2h_src.columns), None)

        if hc and ac:
            h2h_mask = (
                (((df_h2h_src[hc] == team_name) & (df_h2h_src[ac] == opponent)) |
                 ((df_h2h_src[hc] == opponent) & (df_h2h_src[ac] == team_name))) &
                (df_h2h_src["season"] == team_season) &
                (df_h2h_src["competition_slug"] == team_comp)
            )
            h2h = df_h2h_src[h2h_mask].copy()
            if dc:
                h2h = h2h.sort_values(dc)
            if not h2h.empty:
                h2h_cols = [c for c in [dc, hc, ac, shc, sac] if c]
                h2h_display = h2h[h2h_cols].rename(columns={dc: "Date", hc: "Home", ac: "Away", shc: "H", sac: "A"})
                if "Date" in h2h_display.columns:
                    h2h_display["Date"] = pd.to_datetime(h2h_display["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
                st.dataframe(h2h_display, use_container_width=True, hide_index=True)
            else:
                st.info("No head-to-head matches this season.")
        else:
            st.info("Match data column names not recognized.")


def _render_league_inspiration(
    team_name: str,
    team_season: str,
    team_comp: str,
    df_teams: pd.DataFrame,
    team_row: pd.Series,
) -> None:
    """Render league inspiration and similar teams."""
    st.markdown("<div class='section-header'>League Rankings</div>", unsafe_allow_html=True)

    # Top performers table
    _sort_col = "goal_diff" if "goal_diff" in df_teams.columns else "goals_for"
    league_teams = df_teams[
        (df_teams["season"] == team_season) &
        (df_teams["competition_slug"] == team_comp)
    ].sort_values(_sort_col, ascending=False)

    display_cols = ["team_name", "goals_for", "goals_against", "goal_diff", "xg_for_total", "possession_avg"]
    display_cols = [c for c in display_cols if c in league_teams.columns]

    st.dataframe(
        league_teams[display_cols].rename(columns={
            "team_name": "Team", "goals_for": "GF", "goals_against": "GA",
            "goal_diff": "GD", "xg_for_total": "xG For", "possession_avg": "Poss%",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # Similar teams
    st.markdown("<div class='section-header'>Similar Teams</div>", unsafe_allow_html=True)
    st.caption("Teams with similar tactical profiles across all leagues/seasons.")

    similar_teams = get_similar_teams(team_name, team_season, team_comp, n=5)
    if similar_teams.empty:
        st.info("No similar teams found.")
    else:
        sim_cols = st.columns(min(5, len(similar_teams)))
        for i, (_, sim_team) in enumerate(similar_teams.iterrows()):
            color = PLAYER_COLORS[(i + 1) % len(PLAYER_COLORS)]
            with sim_cols[i]:
                st.markdown(
                    f"<div class='sim-card'>"
                    f"<b style='color:{color};'>{sim_team['team_name']}</b><br>"
                    f"<span style='font-size:0.75rem;color:#8B949E;'>{sim_team.get('season','')} {COMP_NAMES.get(sim_team.get('competition_slug',''), sim_team.get('competition_slug',''))}</span><br>"
                    f"<span style='font-size:0.8rem;'>Similarity: {sim_team.get('similarity_score', 0):.0f}%</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # Multi-season trends
    st.markdown("<div class='section-header'>Multi-Season Trends</div>", unsafe_allow_html=True)

    team_history = df_teams[df_teams["team_name"] == team_name].sort_values("season")
    if len(team_history) > 1:
        fig_hist = go.Figure()

        metrics_for_trend = ["goals_for_per_game", "xg_for_per_game", "possession_avg"]
        metrics_for_trend = [c for c in metrics_for_trend if c in team_history.columns]

        for i, metric in enumerate(metrics_for_trend):
            fig_hist.add_trace(go.Scatter(
                x=team_history["season"],
                y=team_history[metric],
                mode="lines+markers",
                name=metric.replace("_per_game", "").replace("_", " ").title(),
                line=dict(color=PLAYER_COLORS[i]),
            ))

        fig_hist.update_layout(
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            font=dict(color="#E6EDF3"),
            xaxis=dict(gridcolor="#30363D"),
            yaxis=dict(gridcolor="#30363D"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=40, r=20, t=80, b=40),
            height=350,
        )
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Only one season of data available for this team.")

# ---------------------------------------------------------------------------
# Team Selector
# ---------------------------------------------------------------------------
st.markdown("<div class='filter-block-label'>Select a team to analyze</div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    avail_comps = sorted(df_teams["competition_slug"].unique())
    team_comp = st.selectbox(
        "League",
        options=avail_comps,
        format_func=lambda x: f"{COMP_FLAGS.get(x,'🏆')} {COMP_NAMES.get(x,x)}",
        key="team_comp",
    )
with c2:
    avail_seasons = sorted(df_teams[df_teams["competition_slug"] == team_comp]["season"].unique(), reverse=True)
    team_season = st.selectbox("Season", options=avail_seasons, key="team_season")
with c3:
    avail_teams = sorted(df_teams[
        (df_teams["competition_slug"] == team_comp) &
        (df_teams["season"] == team_season)
    ]["team_name"].unique())

# Team search (min 2 chars, normalize accents)
st.text_input(
    "Search teams by name",
    value=st.session_state.get("teams_text_search", ""),
    key="teams_text_search",
    placeholder="e.g. Manchester (min 2 characters)",
    help="Type at least 2 characters to filter the team list.",
)
team_search = (st.session_state.get("teams_text_search") or "").strip()
if len(team_search) >= 2:
    avail_teams = [t for t in avail_teams if _normalize_team_search(team_search) in _normalize_team_search(t)]

# Pagination: show first 50, then "Load more"
TEAMS_PAGE_SIZE = 50
if "teams_show_all" not in st.session_state:
    st.session_state["teams_show_all"] = False
show_all = st.session_state["teams_show_all"] or len(avail_teams) <= TEAMS_PAGE_SIZE
display_teams = avail_teams if show_all else avail_teams[:TEAMS_PAGE_SIZE]

if len(team_search) >= 2 and len(avail_teams) == 0:
    st.caption("No teams found. Try a different spelling or clear the search (min 2 characters).")

_team_options = display_teams if display_teams else ["(No teams match your filters)"]
team_name = st.selectbox("Team", options=_team_options, key="team_name")
if not team_name or team_name == "(No teams match your filters)":
    team_name = None
if not show_all and len(avail_teams) > TEAMS_PAGE_SIZE:
    if st.button(f"Show all ({len(avail_teams)} teams)", key="teams_show_all_btn"):
        st.session_state["teams_show_all"] = True
        st.rerun()

if not team_name or team_name == "(No teams match your filters)":
    st.info("Select a team to begin analysis.")
elif team_name:
    # Load team data
    team_row = df_teams[
        (df_teams["team_name"] == team_name) &
        (df_teams["season"] == team_season) &
        (df_teams["competition_slug"] == team_comp)
    ]
    if team_row.empty:
        st.error("Team data not found for selected filters.")
    else:
        team_row = team_row.iloc[0]
        tac_row = df_tac[
            (df_tac["team_name"] == team_name) &
            (df_tac["season"] == team_season) &
            (df_tac["competition_slug"] == team_comp)
        ]
        tac_row = tac_row.iloc[0] if not tac_row.empty else None

        _render_team_analysis(team_name, team_season, team_comp, team_row, tac_row, df_teams, df_matches)
