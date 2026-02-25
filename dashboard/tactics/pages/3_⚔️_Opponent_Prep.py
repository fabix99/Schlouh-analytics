"""Tactics Dashboard — Opponent Preparation (Enhanced).

Enhanced matchup analysis with:
- Side-by-side tactical comparison
- Formation visualization
- Opposition scouting report generation
- Match prediction
- Key player exploitation recommendations
"""

import os
import sys
import pathlib
from urllib.parse import urlencode

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from typing import Optional
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from dashboard.utils.data import (
    load_team_season_stats,
    load_tactical_profiles,
    load_enriched_season_stats,
    get_team_last_matches,
)
try:
    from dashboard.utils.data import get_head_to_head
except ImportError:
    # Local definition when data.py doesn't expose it (path/cache issues)
    def _load_match_summary():
        try:
            from dashboard.utils.data import load_match_summary
            return load_match_summary()
        except Exception:
            try:
                p = _project_root / "data/processed/02_match_summary.parquet"
                return pd.read_parquet(p) if p.exists() else pd.DataFrame()
            except Exception:
                return pd.DataFrame()

    def get_head_to_head(
        team_a: str,
        team_b: str,
        n: int = 5,
        season: Optional[str] = None,
        competition_slug: Optional[str] = None,
    ) -> pd.DataFrame:
        """Return last N meetings between team_a and team_b (from team_a's perspective), by recency."""
        ms = _load_match_summary()
        if ms.empty:
            return pd.DataFrame()
        mask = (
            ((ms["home_team_name"] == team_a) & (ms["away_team_name"] == team_b)) |
            ((ms["home_team_name"] == team_b) & (ms["away_team_name"] == team_a))
        )
        if season is not None:
            mask = mask & (ms["season"] == season)
        if competition_slug is not None:
            mask = mask & (ms["competition_slug"] == competition_slug)
        h2h = ms[mask].copy().sort_values("match_date_utc", ascending=False).head(n)
        if h2h.empty:
            return pd.DataFrame()
        rows = []
        for _, row in h2h.iterrows():
            h, a = row["home_score"], row["away_score"]
            if pd.isna(h) or pd.isna(a):
                continue
            h, a = int(h), int(a)
            is_home_a = row["home_team_name"] == team_a
            gf = h if is_home_a else a
            ga = a if is_home_a else h
            result = "W" if gf > ga else "D" if gf == ga else "L"
            rows.append({
                "date": row.get("match_date_utc"),
                "opponent": team_b,
                "home_away": "H" if is_home_a else "A",
                "score": f"{gf}–{ga}",
                "result": result,
                "xg_for": row.get("home_xg" if is_home_a else "away_xg"),
                "xg_against": row.get("away_xg" if is_home_a else "home_xg"),
                "match_id": row.get("match_id"),
            })
        return pd.DataFrame(rows)

from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS
from dashboard.utils.scope import CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.tactics.layout import render_tactics_sidebar
from dashboard.tactics.components.tactical_components import (
    render_tactical_radar_comparison,
    render_head_to_head_comparison,
    render_opposition_scouting_card,
    render_match_prediction_card,
    render_formation_pitch,
    get_tactical_percentiles,
)

# Scout checklist (used in report export and in checklist UI below)
checklist_items = [
    "Watch for: Their build-up patterns from goal kicks",
    "Watch for: How they react when losing possession",
    "Watch for: Set piece routines (corners & free kicks)",
    "Watch for: Individual duels to exploit",
    "Watch for: Tracking of our wide players",
    "Watch for: Defensive line height and offside trap",
]

# Page config
st.set_page_config(
    page_title="Opponent Prep · Tactics",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_tactics_sidebar()

# Review dashboard base URL for Schedule / Pre-Match links (separate app)
REVIEW_APP_URL = os.environ.get("REVIEW_APP_URL", "http://localhost:8513")

# Initialize session state; pre-fill your_team from selected_team when coming from Directory/Profile
if "your_team" not in st.session_state:
    st.session_state.your_team = None
if "opponent_team" not in st.session_state:
    st.session_state.opponent_team = None
if st.session_state.your_team is None and st.session_state.get("selected_team"):
    sel = st.session_state["selected_team"]
    st.session_state.your_team = {
        "name": sel["name"],
        "season": sel["season"],
        "competition": sel.get("competitions", [sel.get("competition")])[0] if sel.get("competitions") else sel.get("competition", ""),
        "competitions": sel.get("competitions", []),
    }

# Load data
with st.spinner("Loading team data…"):
    team_stats = load_team_season_stats()
    tactical_df = load_tactical_profiles()
    player_df = load_enriched_season_stats()

# Page header
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">⚔️ Opponent Preparation</div>
        <div class="page-hero-sub">
            Analyze matchups, identify tactical clashes, and generate comprehensive scouting reports.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Team Selection
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🎯 Select Matchup</div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Your Team**")

    if not team_stats.empty:
        # Apply pending swap before any selectbox is rendered (Streamlit forbids editing widget state after widget creation)
        if "_swap_pending_your" in st.session_state and "_swap_pending_opp" in st.session_state:
            st.session_state["your_team_select"] = st.session_state.pop("_swap_pending_your")
            st.session_state["opp_team_select"] = st.session_state.pop("_swap_pending_opp")
        default_scope = team_stats[
            (team_stats["season"] == CURRENT_SEASON) &
            (team_stats["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS))
        ]
        your_options = (default_scope if not default_scope.empty else team_stats)[["team_name", "season", "competition_slug"]].drop_duplicates()
        your_options["label"] = your_options.apply(
            lambda r: f"{r['team_name']} ({r['season']})",
            axis=1
        )
        your_options = your_options.drop_duplicates(subset=["team_name", "season"], keep="first")

        if st.session_state.your_team:
            try:
                default_index = list(your_options["label"]).index(
                    f"{st.session_state.your_team['name']} ({st.session_state.your_team['season']})"
                )
            except ValueError:
                default_index = 0
        else:
            default_index = 0

        your_label = st.selectbox("Select your team:", your_options["label"].tolist(), index=default_index, key="your_team_select")
        your_row = your_options[your_options["label"] == your_label].iloc[0]
        your_comps = team_stats[(team_stats["team_name"] == your_row["team_name"]) & (team_stats["season"] == your_row["season"])]["competition_slug"].unique().tolist()
        st.session_state.your_team = {
            "name": your_row["team_name"],
            "season": your_row["season"],
            "competition": your_row["competition_slug"],
            "competitions": your_comps,
        }

with col2:
    st.markdown("**Opponent**")

    if not team_stats.empty:
        default_scope_opp = team_stats[
            (team_stats["season"] == CURRENT_SEASON) &
            (team_stats["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS))
        ]
        opp_options = (default_scope_opp if not default_scope_opp.empty else team_stats)[["team_name", "season", "competition_slug"]].drop_duplicates()
        opp_options["label"] = opp_options.apply(
            lambda r: f"{r['team_name']} ({r['season']})",
            axis=1
        )
        opp_options = opp_options.drop_duplicates(subset=["team_name", "season"], keep="first")

        if st.session_state.opponent_team:
            try:
                default_index = list(opp_options["label"]).index(
                    f"{st.session_state.opponent_team['name']} ({st.session_state.opponent_team['season']})"
                )
            except ValueError:
                default_index = 0
        else:
            default_index = 0

        opp_label = st.selectbox("Select opponent:", opp_options["label"].tolist(), index=default_index, key="opp_team_select")
        opp_row = opp_options[opp_options["label"] == opp_label].iloc[0]
        opp_comps = team_stats[(team_stats["team_name"] == opp_row["team_name"]) & (team_stats["season"] == opp_row["season"])]["competition_slug"].unique().tolist()
        st.session_state.opponent_team = {
            "name": opp_row["team_name"],
            "season": opp_row["season"],
            "competition": opp_row["competition_slug"],
            "competitions": opp_comps,
        }

# Swap teams button (when both selected)
if st.session_state.your_team and st.session_state.opponent_team:
    if st.button("⇄ Swap Your team ↔ Opponent", key="swap_teams"):
        st.session_state.your_team, st.session_state.opponent_team = st.session_state.opponent_team, st.session_state.your_team
        # Defer syncing selectbox state to next run (cannot modify widget keys after widgets are instantiated)
        st.session_state["_swap_pending_your"] = f"{st.session_state.your_team['name']} ({st.session_state.your_team['season']})"
        st.session_state["_swap_pending_opp"] = f"{st.session_state.opponent_team['name']} ({st.session_state.opponent_team['season']})"
        st.rerun()

# Empty state when one or both missing
if not st.session_state.your_team or not st.session_state.opponent_team:
    st.info("Select your team and opponent above to see tactical clash, scouting report and prediction.")
    st.stop()

# Formation options (match render_formation_pitch supported formations)
PREP_FORMATIONS = ["4-3-3", "4-2-3-1", "4-4-2", "3-5-2", "3-4-3", "5-3-2"]
if "prep_our_formation" not in st.session_state:
    st.session_state["prep_our_formation"] = "4-3-3"
if "prep_opp_formation" not in st.session_state:
    st.session_state["prep_opp_formation"] = "4-3-3"
# ---------------------------------------------------------------------------
# Matchup Analysis
# ---------------------------------------------------------------------------
if st.session_state.your_team and st.session_state.opponent_team:
    your = st.session_state.your_team
    opp = st.session_state.opponent_team
    # Normalize: when coming from Directory, team has "competitions" list
    if your.get("competitions") and not your.get("competition"):
        st.session_state.your_team["competition"] = your["competitions"][0]
        your = st.session_state.your_team
    if opp.get("competitions") and not opp.get("competition"):
        st.session_state.opponent_team["competition"] = opp["competitions"][0]
        opp = st.session_state.opponent_team
    # Allow switching opponent context (e.g. league vs UCL) when team plays in multiple
    if opp.get("competitions") and len(opp["competitions"]) > 1:
        idx = opp["competitions"].index(opp["competition"]) if opp["competition"] in opp["competitions"] else 0
        new_comp = st.selectbox(
            "Opponent context (competition):",
            options=opp["competitions"],
            format_func=lambda c: f"{COMP_FLAGS.get(c, '🏆')} {COMP_NAMES.get(c, c)}",
            index=idx,
            key="opp_comp_context",
        )
        if new_comp != opp.get("competition"):
            st.session_state.opponent_team = {**opp, "competition": new_comp}
            opp = st.session_state.opponent_team

    # Get tactical data
    your_tac_mask = (
        (tactical_df["team_name"] == your["name"]) &
        (tactical_df["season"] == your["season"])
    )
    if "competition_slug" in tactical_df.columns and your.get("competition"):
        your_tac_mask &= tactical_df["competition_slug"] == your["competition"]
    your_tac = tactical_df[your_tac_mask]

    opp_tac_mask = (
        (tactical_df["team_name"] == opp["name"]) &
        (tactical_df["season"] == opp["season"])
    )
    if "competition_slug" in tactical_df.columns and opp.get("competition"):
        opp_tac_mask &= tactical_df["competition_slug"] == opp["competition"]
    opp_tac = tactical_df[opp_tac_mask]

    # Get team stats
    your_stats_mask = (
        (team_stats["team_name"] == your["name"]) &
        (team_stats["season"] == your["season"])
    )
    if "competition_slug" in team_stats.columns and your.get("competition"):
        your_stats_mask &= team_stats["competition_slug"] == your["competition"]
    your_stats = team_stats[your_stats_mask]

    opp_stats_mask = (
        (team_stats["team_name"] == opp["name"]) &
        (team_stats["season"] == opp["season"])
    )
    if "competition_slug" in team_stats.columns and opp.get("competition"):
        opp_stats_mask &= team_stats["competition_slug"] == opp["competition"]
    opp_stats = team_stats[opp_stats_mask]

    st.markdown("---")
    st.markdown("<div class='section-header'>📊 Tactical Clash Analysis</div>", unsafe_allow_html=True)

    if not your_tac.empty and not opp_tac.empty:
        your_tac_data = your_tac.iloc[0].to_dict()
        opp_tac_data = opp_tac.iloc[0].to_dict()

        # Pool for normalizing radar to 0–100 (same season, both competitions)
        pool_radar = tactical_df[
            (tactical_df["season"] == your["season"]) &
            (tactical_df["competition_slug"].isin([your.get("competition"), opp.get("competition")]))
        ].dropna(how="all")
        if pool_radar.empty:
            pool_radar = tactical_df
        if len(pool_radar) < 5:
            st.info("Few teams in this league/season — tactical percentiles are less reliable. Run pipeline on full data for better comparisons.")

        # Side-by-side radar comparison
        radar_col, stats_col = st.columns(2)

        with radar_col:
            st.markdown("**Tactical Radar Comparison**")
            render_tactical_radar_comparison(
                your_tac_data,
                opp_tac_data,
                your["name"],
                opp["name"],
                pool_df=pool_radar,
            )

        with stats_col:
            st.markdown("**Season comparison**")
            st.caption("Your team vs opponent over the season (totals and per-match averages).")
            if not your_stats.empty and not opp_stats.empty:
                y_row, o_row = your_stats.iloc[0], opp_stats.iloc[0]
                m1 = int(y_row.get("matches_total") or 1)
                m2 = int(o_row.get("matches_total") or 1)
                def _pct(v):
                    if v is None or (isinstance(v, float) and (np.isnan(v) or v < 0)):
                        return None
                    f = float(v)
                    return f * 100 if f <= 1.5 else f
                def _per_match(total, matches):
                    if total is None or matches is None or int(matches) == 0:
                        return None
                    return float(total) / int(matches)
                def _pass_pct(row):
                    pa = row.get("pass_accuracy_avg")
                    if pa is not None and pd.notna(pa):
                        return float(pa) * 100 if float(pa) <= 1.5 else float(pa)
                    acc, tot = row.get("accurate_passes_total"), row.get("passes_total")
                    if tot and float(tot) > 0 and acc is not None:
                        return float(acc) / float(tot) * 100
                    return None
                your_derived = {
                    "possession_pct": _pct(y_row.get("possession_avg")),
                    "shots_per_match": _per_match(y_row.get("shots_total"), y_row.get("matches_total")),
                    "xg_for_total": float(y_row["xg_for_total"]) if pd.notna(y_row.get("xg_for_total")) else None,
                    "goals_for": int(y_row.get("goals_for", 0)) if pd.notna(y_row.get("goals_for")) else None,
                    "pass_completion_pct": _pass_pct(y_row),
                    "tackles_per_match": _per_match(y_row.get("tackles_total"), y_row.get("matches_total")),
                }
                opp_derived = {
                    "possession_pct": _pct(o_row.get("possession_avg")),
                    "shots_per_match": _per_match(o_row.get("shots_total"), o_row.get("matches_total")),
                    "xg_for_total": float(o_row["xg_for_total"]) if pd.notna(o_row.get("xg_for_total")) else None,
                    "goals_for": int(o_row.get("goals_for", 0)) if pd.notna(o_row.get("goals_for")) else None,
                    "pass_completion_pct": _pass_pct(o_row),
                    "tackles_per_match": _per_match(o_row.get("tackles_total"), o_row.get("matches_total")),
                }
                season_metrics = [
                    ("possession_pct", "Possession % (avg)"),
                    ("shots_per_match", "Shots per match (avg)"),
                    ("xg_for_total", "Total xG (season total)"),
                    ("goals_for", "Goals (season total)"),
                    ("pass_completion_pct", "Pass completion % (avg)"),
                    ("tackles_per_match", "Tackles per match (avg)"),
                ]
                render_head_to_head_comparison(
                    pd.Series(your_derived),
                    pd.Series(opp_derived),
                    your["name"],
                    opp["name"],
                    metrics=season_metrics,
                )
            # Last 5 H2H (all seasons, by recency)
            h2h = get_head_to_head(your["name"], opp["name"], n=5)
            if not h2h.empty:
                n_h2h = len(h2h)
                h2h_label = f"Last 5 H2H ({n_h2h} match{'es' if n_h2h != 1 else ''})"
                st.markdown(f"**{h2h_label}**")
                def _mm_yy(d):
                    if pd.isna(d):
                        return "—"
                    try:
                        dt = pd.to_datetime(d)
                        return dt.strftime("%m/%y")
                    except Exception:
                        return "—"
                rows_html = []
                for _, m in h2h.iterrows():
                    res = m.get("result", "?")
                    res_color = "#3FB950" if res == "W" else "#C9A840" if res == "D" else "#F85149"
                    date_str = _mm_yy(m.get("date"))
                    score = m.get("score", "")
                    ha = m.get("home_away", "")
                    rows_html.append(
                        f"<tr style='border-bottom: 1px solid #21262D;'>"
                        f"<td style='padding: 4px 6px; font-size: 0.8rem; color: #8B949E;'>{date_str}</td>"
                        f"<td style='padding: 4px 6px; font-weight: 600; color: {res_color};'>{res}</td>"
                        f"<td style='padding: 4px 6px; font-size: 0.9rem; color: #E6EDF3;'>{score}</td>"
                        f"<td style='padding: 4px 6px; font-size: 0.8rem; color: #8B949E; text-align: center;'>{ha}</td>"
                        f"</tr>"
                    )
                st.markdown(
                    "<table style='table-layout: fixed; width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 4px;'>"
                    "<colgroup><col style='width: 22%'><col style='width: 10%'><col style='width: 60%'><col style='width: 8%'></colgroup>"
                    "<thead><tr style='border-bottom: 1px solid #30363D;'>"
                    "<th style='text-align: left; padding: 4px 6px; color: #8B949E; font-size: 0.75rem; font-weight: 500;'>Date</th>"
                    "<th style='text-align: left; padding: 4px 6px; color: #8B949E; font-size: 0.75rem; font-weight: 500;'></th>"
                    "<th style='text-align: left; padding: 4px 6px; color: #8B949E; font-size: 0.75rem; font-weight: 500;'>Score</th>"
                    "<th style='text-align: center; padding: 4px 6px; color: #8B949E; font-size: 0.75rem; font-weight: 500;'>Venue</th>"
                    "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table>",
                    unsafe_allow_html=True,
                )

        # ---------------------------------------------------------------------------
        # Scouting Report (Enhanced)
        # ---------------------------------------------------------------------------
        st.markdown("---")

        # Percentile-based comparison (raw indices are on different scales; use league-relative rank)
        opp_pct = get_tactical_percentiles(opp_tac_data, pool_radar)
        your_pct = get_tactical_percentiles(your_tac_data, pool_radar)

        # Generate comprehensive scouting data
        opp_players = player_df[
            (player_df["team"] == opp["name"]) &
            (player_df["season"] == opp["season"])
        ].sort_values("avg_rating", ascending=False)

        _opp_key = (opp.get("name") or "opp").replace(" ", "_")
        key_opp_players = []
        if not opp_players.empty:
            pos_to_role = {"G": "Goalkeeper", "D": "Defender", "M": "Midfielder", "F": "Forward"}
            for _, player in opp_players.head(5).iterrows():
                threat_level = "High" if player.get('avg_rating', 0) > 7.5 else "Medium" if player.get('avg_rating', 0) > 7.0 else "Low"
                pos = player.get('player_position', '') or 'M'
                role = pos_to_role.get(pos, pos)
                xg90 = round(player.get('expectedGoals_per90', 0) or 0, 2)
                xa90 = round(player.get('expectedAssists_per90', 0) or 0, 2)
                goals = int(player.get('goals', 0) or 0)
                strengths = []
                if xg90 > 0.1:
                    strengths.append("xG/90 threat" if xg90 > 0.25 else "xG/90 contributor")
                if xa90 > 0.05:
                    strengths.append("Creative (xA/90)" if xa90 > 0.15 else "Creates chances")
                if goals >= 2:
                    strengths.append("Goals threat")
                if (player.get('avg_rating', 0) or 0) >= 7.5:
                    strengths.append("Consistent performer")
                pa_pct = player.get("pass_accuracy_pct")
                pa_ratio = player.get("pass_accuracy") or player.get("passAccuracy")
                if pa_pct is not None and pd.notna(pa_pct) and float(pa_pct) < 80:
                    weaknesses = "Under pressure (pass % low)"
                elif pa_ratio is not None and pd.notna(pa_ratio) and float(pa_ratio) < 0.8:
                    weaknesses = "Under pressure (pass % low)"
                else:
                    weaknesses = ""
                instruction = "Deny space and show onto weak foot" if pos in ("F", "M") else "Track runs and close down"
                note_key = f"prep_player_note_{_opp_key}_{len(key_opp_players)}_{(player['player_name'] or '').replace(' ', '_')}"
                key_opp_players.append({
                    'name': player['player_name'],
                    'position': pos,
                    'role': role,
                    'rating': player.get('avg_rating', 6.5),
                    'threat_level': threat_level,
                    'goals': goals,
                    'assists': int(player.get('assists', 0) or 0),
                    'xg90': xg90,
                    'xa90': xa90,
                    'strengths': strengths or ["Key player"],
                    'weaknesses': weaknesses,
                    'instruction': instruction,
                    '_note_key': note_key,
                })
            # Lowest-rated usual starters (min minutes) — under Weaknesses to balance key strengths
            min_mins = 450
            if "total_minutes" in opp_players.columns:
                starters = opp_players.loc[opp_players["total_minutes"].fillna(0) >= min_mins].copy()
            elif "appearances" in opp_players.columns:
                starters = opp_players.loc[opp_players["appearances"].fillna(0) >= 5].copy()
            else:
                starters = opp_players.copy()
            starters = starters.sort_values("avg_rating", ascending=True).head(5)
            lowest_rated_starters = [
                {"name": row["player_name"], "position": row.get("player_position", "?") or "?", "rating": float(row.get("avg_rating", 0) or 0)}
                for _, row in starters.iterrows()
            ]
        else:
            lowest_rated_starters = []

        # Identify threats (top quartile in league = strength)
        threats = []
        if opp_pct.get("pressing_index", 50) > 75:
            threats.append("High press intensity (top quartile in league)")
        if opp_pct.get("aerial_index", 50) > 75:
            threats.append(f"Aerial dominance (top quartile)")
        if opp_pct.get("possession_index", 50) > 75:
            threats.append(f"Ball retention strength (top quartile)")
        if not threats:
            threats.append("Balanced approach - no extreme threats identified")

        # Identify weaknesses (bottom quartile = exploitable)
        weaknesses = []
        if opp_pct.get("defensive_solidity", 50) < 25:
            weaknesses.append("Defensive vulnerabilities - exploit in transition")
        if opp_pct.get("pressing_index", 50) < 25:
            weaknesses.append("Low press intensity - build from the back")
        if opp_pct.get("aerial_index", 50) < 25:
            weaknesses.append("Aerial weakness - target set pieces and crosses")
        if not weaknesses:
            weaknesses.append("Well-balanced team - focus on individual quality moments")

        # Predicted tactics (use percentiles so thresholds are meaningful)
        predicted = f"{opp['name']} likely to play a "
        if opp_pct.get("possession_index", 50) > 75:
            predicted += "possession-based game with patient build-up."
        elif opp_pct.get("directness_index", 50) > 75:
            predicted += "direct, vertical style with quick transitions."
        elif opp_pct.get("pressing_index", 50) > 75:
            predicted += "high-pressing, aggressive approach to win the ball early."
        else:
            predicted += "balanced, adaptable approach based on game state."
        second_half = opp_tac_data.get("second_half_intensity")
        if second_half is not None and pd.notna(second_half) and float(second_half) >= 1.0:
            predicted += " Strong second-half intensity."
        home_away = opp_tac_data.get("home_away_consistency")
        if home_away is not None and pd.notna(home_away) and float(home_away) >= 0.6:
            predicted += " Consistent home and away."

        # Store for export
        st.session_state["prep_threats"] = threats
        st.session_state["prep_weaknesses"] = weaknesses
        st.session_state["prep_key_players"] = key_opp_players
        st.session_state["prep_predicted"] = predicted
        st.session_state["prep_opp_tac"] = dict(opp_tac_data) if hasattr(opp_tac_data, "get") else {}
        st.session_state["prep_your_tac"] = dict(your_tac_data) if hasattr(your_tac_data, "get") else {}

        # Render scouting card (formation from selector)
        render_opposition_scouting_card(
            opponent_name=opp["name"],
            formation=st.session_state.get("prep_opp_formation", "4-3-3"),
            key_players=key_opp_players,
            threats=threats,
            weaknesses=weaknesses,
            predicted_tactics=predicted,
            lowest_rated_starters=lowest_rated_starters,
        )

        # ---------------------------------------------------------------------------
        # Key player cards (expanded: role, strengths, weaknesses, instruction, optional note)
        # ---------------------------------------------------------------------------
        st.markdown("---")
        st.markdown("<div class='section-header'>🃏 Key player cards</div>", unsafe_allow_html=True)
        for idx, p in enumerate(key_opp_players):
            strengths_str = ", ".join(p.get("strengths", [])) if isinstance(p.get("strengths"), list) else str(p.get("strengths", ""))
            note_key = p.get("_note_key", f"prep_player_note_{_opp_key}_{idx}")
            if note_key not in st.session_state:
                st.session_state[note_key] = ""
            with st.expander(f"**{p.get('name', '?')}** — {p.get('role', p.get('position', ''))} · {p.get('threat_level', '')} threat"):
                st.markdown(f"**Role:** {p.get('role', '')} · **Rating:** {p.get('rating', 0):.2f}")
                st.markdown(f"**Strengths:** {strengths_str}")
                st.markdown(f"**Weaknesses:** {p.get('weaknesses', '') or '—'}")
                st.markdown(f"**One instruction:** {p.get('instruction', '')}")
                st.text_input("Note (optional)", value=st.session_state.get(note_key, ""), key=note_key, placeholder="e.g. Prefers left foot, drops deep", label_visibility="collapsed")

        # ---------------------------------------------------------------------------
        # Opponent form (last 5 matches)
        # ---------------------------------------------------------------------------
        st.markdown("---")
        st.markdown("<div class='section-header'>📅 Opponent form (last 5)</div>", unsafe_allow_html=True)
        try:
            last5 = get_team_last_matches(opp["name"], opp["season"], opp["competition"], n=5)
            if not last5.empty:
                for _, m in last5.iterrows():
                    res = m.get("result", "?")
                    res_color = "#3FB950" if res == "W" else "#C9A840" if res == "D" else "#F85149"
                    xg_for, xg_ag = m.get("xg_for"), m.get("xg_against")
                    try:
                        f_for = float(xg_for) if xg_for is not None and pd.notna(xg_for) else None
                        f_ag = float(xg_ag) if xg_ag is not None and pd.notna(xg_ag) else None
                        has_xg = (f_for is not None and f_ag is not None) and (f_for > 0 or f_ag > 0)
                        xg_str = f" (xG: {f_for:.1f}-{f_ag:.1f})" if has_xg else " (xG: —)"
                    except (TypeError, ValueError):
                        xg_str = " (xG: —)"
                    st.markdown(
                        f"<div style='padding:6px 0;'><span style='color:{res_color};font-weight:600;'>{res}</span> "
                        f"{m.get('home_away', '')} {m.get('score', '')} vs {m.get('opponent', '')}{xg_str}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No match history available for this season.")
        except Exception:
            st.caption("Match history unavailable.")

        # ---------------------------------------------------------------------------
        # Match Prediction
        # ---------------------------------------------------------------------------
        st.markdown("---")

        # Prediction from percentile-based composite (so scales are comparable)
        your_score = (
            your_pct.get("defensive_solidity", 50) * 0.3 +
            your_pct.get("chance_creation_index", 50) * 0.3 +
            your_pct.get("pressing_index", 50) * 0.2 +
            50
        ) / 1.3
        opp_score = (
            opp_pct.get("defensive_solidity", 50) * 0.3 +
            opp_pct.get("chance_creation_index", 50) * 0.3 +
            opp_pct.get("pressing_index", 50) * 0.2 +
            50
        ) / 1.3

        # Convert to probabilities
        diff = your_score - opp_score
        win_prob_yours = 33 + (diff / 2)
        draw_prob = 33 - (abs(diff) / 4)
        win_prob_opp = 100 - win_prob_yours - draw_prob

        # Clamp values
        win_prob_yours = max(20, min(60, win_prob_yours))
        draw_prob = max(15, min(40, draw_prob))
        win_prob_opp = max(20, min(60, win_prob_opp))

        # Normalize to sum to 100 (guard division by zero)
        total = win_prob_yours + draw_prob + win_prob_opp
        if total and total > 0:
            win_prob_yours = (win_prob_yours / total) * 100
            draw_prob = (draw_prob / total) * 100
            win_prob_opp = (win_prob_opp / total) * 100

        # Predicted score (from percentile chance creation as proxy for goal threat)
        your_cc = your_pct.get("chance_creation_index", 50) or 50
        opp_cc = opp_pct.get("chance_creation_index", 50) or 50
        your_xg = (your_cc / 100) * 2.5 + 0.5
        opp_xg = (opp_cc / 100) * 2.5 + 0.5
        predicted_score = f"{your_xg:.1f}-{opp_xg:.1f}"

        # Confidence level
        if abs(diff) > 15:
            confidence = "High"
        elif abs(diff) > 8:
            confidence = "Medium"
        else:
            confidence = "Low"

        # Key factors (show league percentile so numbers are interpretable)
        key_factors = [
            f"{your['name']} defensive solidity: {your_pct.get('defensive_solidity', 50):.0f}th %ile in league",
            f"{opp['name']} pressing intensity: {opp_pct.get('pressing_index', 50):.0f}th %ile in league",
            f"Tactical clash: {'Favorable' if diff > 5 else 'Even' if abs(diff) < 5 else 'Unfavorable'} matchup",
        ]

        st.caption("Based on tactical indices (league percentiles) and form. For best quality, run pipeline steps 01 (team_season_stats) and 15 (team_tactical_profiles).")
        render_match_prediction_card(
            team1_name=your["name"],
            team2_name=opp["name"],
            win_prob=(win_prob_yours, draw_prob, win_prob_opp),
            predicted_score=predicted_score,
            confidence=confidence,
            key_factors=key_factors
        )
        # Store for report export
        st.session_state["prep_win_prob"] = (win_prob_yours, draw_prob, win_prob_opp)
        st.session_state["prep_predicted_score"] = predicted_score
        st.session_state["prep_confidence"] = confidence
        st.session_state["prep_key_factors"] = key_factors

        # Staff talking points (auto from threats, weaknesses, factors, key players — up to 3 Watch)
        talking_points = []
        for t in threats:
            talking_points.append(f"Be aware: {t}")
        for w in weaknesses:
            talking_points.append(f"Exploit: {w}")
        for f in key_factors:
            talking_points.append(f"Match-up: {f}")
        for p in key_opp_players[:3]:
            talking_points.append(f"Watch: {p.get('name', '?')} – {p.get('position', '')} ({p.get('threat_level', '')} threat)")
        st.session_state["prep_talking_points"] = talking_points[:10]

        # Us vs them template (optional overrides in session state, keyed by opponent)
        _want_key = "prep_us_vs_them_want_" + _opp_key
        _avoid_key = "prep_us_vs_them_avoid_" + _opp_key
        if _want_key not in st.session_state:
            st.session_state[_want_key] = ""
        if _avoid_key not in st.session_state:
            st.session_state[_avoid_key] = ""
        def _clean_weakness(w):
            return w.replace(" - exploit in transition", " in transition").replace(" - build from the back", "").replace(" - target set pieces and crosses", "").strip()
        weak_clean = [_clean_weakness(w) for w in weaknesses[:2]]
        us_want_template = "Play in their half when they sit deep. Exploit their " + " and ".join(weak_clean) + "." if weak_clean else "Control the game in key areas."
        us_avoid_template = ("Don't get drawn into " + (threats[0] if threats else "their strengths") + ". Protect against " + (threats[1] if len(threats) > 1 else "their main threat") + ".") if threats else "Avoid losing the ball in dangerous areas."
        st.session_state["prep_us_vs_them_want_template"] = us_want_template
        st.session_state["prep_us_vs_them_avoid_template"] = us_avoid_template

        # Non-negotiables (keyed by opponent)
        for i in range(1, 4):
            k = "prep_non_neg_" + str(i) + "_" + _opp_key
            if k not in st.session_state:
                st.session_state[k] = ""

        # ---------------------------------------------------------------------------
        # Tabs: Full prep | Match-day brief
        # ---------------------------------------------------------------------------
        tab_full, tab_brief = st.tabs(["Full prep", "Match-day brief"])

        with tab_full:
            # ---------------------------------------------------------------------------
            # Us vs them summary
            # ---------------------------------------------------------------------------
            st.markdown("---")
            st.markdown("<div class='section-header'>🎯 Us vs them</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Where we want the game**")
                st.text_area(
                    "Where we want the game",
                    value=st.session_state.get(_want_key) or us_want_template,
                    key=_want_key,
                    placeholder=us_want_template,
                    height=60,
                    label_visibility="collapsed",
                )
            with c2:
                st.markdown("**What we must avoid**")
                st.text_area(
                    "What we must avoid",
                    value=st.session_state.get(_avoid_key) or us_avoid_template,
                    key=_avoid_key,
                    placeholder=us_avoid_template,
                    height=60,
                    label_visibility="collapsed",
                )

            # ---------------------------------------------------------------------------
            # Your Players Who Can Exploit
            # ---------------------------------------------------------------------------
            st.markdown("---")
            st.markdown("<div class='section-header'>💪 Your Best Weapons</div>", unsafe_allow_html=True)

            your_players = player_df[
                (player_df["team"] == your["name"]) &
                (player_df["season"] == your["season"])
            ].sort_values("avg_rating", ascending=False)

            if not your_players.empty:
                for w in weaknesses[:2]:
                    st.markdown(f"**Players to exploit: {w}**")
                    if "aerial" in w.lower():
                        suggested = your_players.nlargest(3, "aerialWon_per90") if "aerialWon_per90" in your_players.columns else your_players.head(3)
                    elif "defensive" in w.lower() or "transition" in w.lower():
                        suggested = your_players.nlargest(3, "keyPass_per90") if "keyPass_per90" in your_players.columns else your_players.head(3)
                    else:
                        suggested = your_players.head(3)
                    player_cols = st.columns(3)
                    for i, (_, player) in enumerate(suggested.iterrows()):
                        with player_cols[i]:
                            st.markdown(
                                f"""
                                <div style="background:#161B22;padding:10px;border-radius:6px;border:1px solid #30363D;margin:4px 0;">
                                    <div style="font-weight:500;color:#F0F6FC;">{player['player_name']}</div>
                                    <div style="font-size:0.75rem;color:#8B949E;">{player['player_position']}</div>
                                    <div style="font-size:0.75rem;color:#C9A840;margin-top:4px;">Rating: {player.get('avg_rating', 0):.2f}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

            # ---------------------------------------------------------------------------
            # Formation Comparison
            # ---------------------------------------------------------------------------
            st.markdown("---")
            st.markdown("<div class='section-header'>⚽ Formation Comparison</div>", unsafe_allow_html=True)

            form_sel_col1, form_sel_col2 = st.columns(2)
            with form_sel_col1:
                _our_f = st.session_state.get("prep_our_formation", "4-3-3")
                _idx_our = PREP_FORMATIONS.index(_our_f) if _our_f in PREP_FORMATIONS else 0
                st.session_state["prep_our_formation"] = st.selectbox(
                    f"Our formation ({your['name']})",
                    options=PREP_FORMATIONS,
                    index=_idx_our,
                    key="prep_our_formation_select",
                )
            with form_sel_col2:
                _opp_f = st.session_state.get("prep_opp_formation", "4-3-3")
                _idx_opp = PREP_FORMATIONS.index(_opp_f) if _opp_f in PREP_FORMATIONS else 0
                st.session_state["prep_opp_formation"] = st.selectbox(
                    f"Opponent formation ({opp['name']})",
                    options=PREP_FORMATIONS,
                    index=_idx_opp,
                    key="prep_opp_formation_select",
                )

            form_col1, form_col2 = st.columns(2)
            with form_col1:
                st.markdown(f"**{your['name']}** — Probable XI by rating (formation estimated)")
                your_formation = st.session_state.get("prep_our_formation", "4-3-3")
                your_form_players = []
                if not your_players.empty:
                    for _, player in your_players.head(11).iterrows():
                        your_form_players.append({
                            'name': player['player_name'],
                            'position': player['player_position'],
                            'rating': player.get('avg_rating', 6.5),
                            'role': 'Standard'
                        })
                if your_form_players:
                    render_formation_pitch(your_formation, your_form_players, width=350, height=300)

            with form_col2:
                st.markdown(f"**{opp['name']}** — Probable XI by rating (formation estimated)")
                opp_formation = st.session_state.get("prep_opp_formation", "4-3-3")
                opp_form_players = []
                if not opp_players.empty:
                    for _, player in opp_players.head(11).iterrows():
                        opp_form_players.append({
                            'name': player['player_name'],
                            'position': player['player_position'],
                            'rating': player.get('avg_rating', 6.5),
                            'role': 'Standard'
                        })
                if opp_form_players:
                    render_formation_pitch(opp_formation, opp_form_players, width=350, height=300)

            # ---------------------------------------------------------------------------
            # Match-up table (Our XI vs Their XI, paired by index)
            # ---------------------------------------------------------------------------
            if your_form_players and opp_form_players:
                st.markdown("---")
                st.markdown("<div class='section-header'>📋 Match-up table</div>", unsafe_allow_html=True)
                n_pair = min(len(your_form_players), len(opp_form_players))
                matchup_rows = []
                for i in range(n_pair):
                    ours = your_form_players[i]
                    theirs = opp_form_players[i]
                    matchup_rows.append({
                        "Our player": ours.get("name", "?"),
                        "Our pos": ours.get("position", ""),
                        "vs": "vs",
                        "Their player": theirs.get("name", "?"),
                        "Their pos": theirs.get("position", ""),
                    })
                st.dataframe(
                    pd.DataFrame(matchup_rows),
                    use_container_width=True,
                    hide_index=True,
                )
                st.session_state["prep_matchup_rows"] = matchup_rows

        with tab_brief:
            st.markdown(f"**{your['name']}** vs **{opp['name']}** · {COMP_FLAGS.get(opp.get('competition', ''), '')} {COMP_NAMES.get(opp.get('competition', ''), opp.get('competition', ''))} · {opp.get('season', '')}")
            st.markdown("---")
            st.markdown("**Formations**")
            st.markdown(f"- Our team: **{st.session_state.get('prep_our_formation', '4-3-3')}** · Opponent: **{st.session_state.get('prep_opp_formation', '4-3-3')}**")
            st.markdown("---")
            st.markdown("**Three non-negotiables**")
            st.text_input("1", value=st.session_state.get("prep_non_neg_1_" + _opp_key, ""), placeholder="E.g. Press their back line on goal kicks", key="prep_non_neg_1_" + _opp_key, label_visibility="collapsed")
            st.text_input("2", value=st.session_state.get("prep_non_neg_2_" + _opp_key, ""), placeholder="E.g. Track their 10 when we lose the ball", key="prep_non_neg_2_" + _opp_key, label_visibility="collapsed")
            st.text_input("3", value=st.session_state.get("prep_non_neg_3_" + _opp_key, ""), placeholder="E.g. Win second balls in midfield", key="prep_non_neg_3_" + _opp_key, label_visibility="collapsed")
            st.markdown("---")
            st.markdown("**Staff talking points**")
            for pt in st.session_state.get("prep_talking_points", []):
                st.markdown(f"- {pt}")
            st.markdown("---")
            st.markdown("**Us vs them**")
            st.markdown(f"- **Where we want the game:** {st.session_state.get(_want_key) or us_want_template}")
            st.markdown(f"- **What we must avoid:** {st.session_state.get(_avoid_key) or us_avoid_template}")
            st.markdown("---")
            _report_md = st.session_state.get("prep_report_md", "")
            if _report_md:
                st.download_button(
                    "Download full report (Markdown)",
                    data=_report_md,
                    file_name=f"opponent_prep_{opp.get('name', 'report').replace(' ', '_')}.md",
                    mime="text/markdown",
                    key="brief_download_report",
                    use_container_width=True,
                )
            else:
                st.caption("Download the full report (Markdown) below to share with staff.")

        # Build report and store for Match-day brief download and bottom section
        _notes_k = "prep_notes_" + (opp.get("name") or "opp")
        _scout_notes = st.session_state.get(_notes_k, "")
        _set_key = "prep_set_piece_notes_" + _opp_key
        _set_notes = st.session_state.get(_set_key, "") or "(none)"
        _us_want = st.session_state.get("prep_us_vs_them_want_" + _opp_key) or st.session_state.get("prep_us_vs_them_want_template", "")
        _us_avoid = st.session_state.get("prep_us_vs_them_avoid_" + _opp_key) or st.session_state.get("prep_us_vs_them_avoid_template", "")
        _n1 = st.session_state.get("prep_non_neg_1_" + _opp_key, "")
        _n2 = st.session_state.get("prep_non_neg_2_" + _opp_key, "")
        _n3 = st.session_state.get("prep_non_neg_3_" + _opp_key, "")
        _tp = st.session_state.get("prep_talking_points", [])
        _report_lines = [
            f"# Opponent Prep: {your.get('name', 'Your team')} vs {opp.get('name', 'Opponent')}",
            f"\n**Season:** {opp.get('season', '')} · **Competition:** {opp.get('competition', '')}\n",
            "## Tactical brief (match-day)",
            f"- **Formations:** Our team {st.session_state.get('prep_our_formation', '4-3-3')} · Opponent {st.session_state.get('prep_opp_formation', '4-3-3')}",
            "- **Three non-negotiables:**",
            f"  1. {_n1 or '(not set)'}",
            f"  2. {_n2 or '(not set)'}",
            f"  3. {_n3 or '(not set)'}",
            "- **Staff talking points:**",
            *("  - " + t for t in _tp),
            "- **Us vs them:**",
            f"  - Where we want the game: {_us_want}",
            f"  - What we must avoid: {_us_avoid}",
            "",
            "## Formations",
            f"- **Our team:** {st.session_state.get('prep_our_formation', '4-3-3')}",
            f"- **Opponent:** {st.session_state.get('prep_opp_formation', '4-3-3')}",
            "",
            "## Tactical summary",
            st.session_state.get("prep_predicted", ""),
            "## Match prediction",
            f"Expected xG (us–them): {st.session_state.get('prep_predicted_score', '—')}",
            f"Win / Draw / Loss: {st.session_state.get('prep_win_prob', (0, 0, 0))[0]:.0f}% / {st.session_state.get('prep_win_prob', (0, 0, 0))[1]:.0f}% / {st.session_state.get('prep_win_prob', (0, 0, 0))[2]:.0f}%",
            f"Confidence: {st.session_state.get('prep_confidence', '')}",
            "## Key factors",
            *("- " + f for f in st.session_state.get("prep_key_factors", [])),
            "## Threats",
            *("- " + t for t in st.session_state.get("prep_threats", [])),
            "## Weaknesses",
            *("- " + w for w in st.session_state.get("prep_weaknesses", [])),
            "## Key players to watch",
            *(
                "- **" + p.get("name", "?") + "** (" + str(p.get("role", p.get("position", ""))) + ") – " + str(p.get("threat_level", ""))
                + (f" · G:{p.get('goals', 0)} A:{p.get('assists', 0)} xG/90:{p.get('xg90', 0)}" if p.get("goals") is not None or p.get("assists") is not None else "")
                + (f"\n  - Strengths: {', '.join(p.get('strengths', [])) if isinstance(p.get('strengths'), list) else str(p.get('strengths', ''))}" if p.get("strengths") else "")
                + (f"\n  - Weaknesses: {p.get('weaknesses', '')}" if p.get("weaknesses") else "")
                + (f"\n  - Instruction: {p.get('instruction', '')}" if p.get("instruction") else "")
                + (f"\n  - Note: {st.session_state.get(p.get('_note_key', ''), '')}" if (st.session_state.get(p.get("_note_key", ""), "") or "").strip() else "")
                for p in st.session_state.get("prep_key_players", [])
            ),
            "## Match-up table",
            *([f"- {r.get('Our player', '?')} ({r.get('Our pos', '')}) vs {r.get('Their player', '?')} ({r.get('Their pos', '')})" for r in st.session_state.get("prep_matchup_rows", [])] or ["(Review Full prep tab for match-up table)"]),
            "## Scout notes",
            _scout_notes or "(none)",
            "## Set pieces",
            _set_notes,
            "## Video / clip links",
            st.session_state.get("prep_video_links_" + _opp_key, "") or "(none)",
            "## Checklist (review before match)",
            *checklist_items,
        ]
        st.session_state["prep_report_md"] = "\n".join(_report_lines)

    else:
        st.info("Tactical data not available for one or both teams")

# ---------------------------------------------------------------------------
# Scout notes (persisted in session)
# ---------------------------------------------------------------------------
if st.session_state.your_team and st.session_state.opponent_team:
    notes_key = "prep_notes_" + (st.session_state.opponent_team.get("name") or "opp")
    if notes_key not in st.session_state:
        st.session_state[notes_key] = ""
    st.markdown("---")
    st.markdown("<div class='section-header'>📝 Scout notes</div>", unsafe_allow_html=True)
    st.text_area(
        "Notes for this matchup",
        value=st.session_state.get(notes_key, ""),
        key=notes_key,
        placeholder="Add pre-match observations, set piece plans, etc.",
        height=120,
    )

# ---------------------------------------------------------------------------
# Set pieces (notes; data coming later)
# ---------------------------------------------------------------------------
if st.session_state.your_team and st.session_state.opponent_team:
    opp_name = st.session_state.opponent_team.get("name") or "opp"
    set_piece_key = "prep_set_piece_notes_" + opp_name.replace(" ", "_")
    if set_piece_key not in st.session_state:
        st.session_state[set_piece_key] = ""
    st.markdown("---")
    st.markdown("<div class='section-header'>🎯 Set pieces</div>", unsafe_allow_html=True)
    st.text_area(
        "Set piece notes (corners, free kicks, throw-ins)",
        value=st.session_state.get(set_piece_key, ""),
        key=set_piece_key,
        placeholder="Their routines, our defensive assignments, our attacking options. Data-driven set-piece stats will appear here when available.",
        height=100,
        help="Their routines, our defensive assignments, our attacking options.",
    )
    video_links_key = "prep_video_links_" + opp_name.replace(" ", "_")
    if video_links_key not in st.session_state:
        st.session_state[video_links_key] = ""
    st.text_area(
        "Video / clip links (optional)",
        value=st.session_state.get(video_links_key, ""),
        key=video_links_key,
        placeholder="Paste URLs to Wyscout, Hudl, or other clip reels for this opponent.",
        height=60,
        help="Optional: paste links to video clips for staff.",
    )
else:
    set_piece_key = None
    video_links_key = None

# ---------------------------------------------------------------------------
# Scout Checklist
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>✅ Scout Checklist</div>", unsafe_allow_html=True)

for i, item in enumerate(checklist_items):
    st.checkbox(item, key=f"prep_check_{i}")

# Export report and navigation
st.markdown("---")
if st.session_state.your_team and st.session_state.opponent_team:
    your = st.session_state.your_team
    opp = st.session_state.opponent_team
    threats = st.session_state.get("prep_threats", [])
    weaknesses = st.session_state.get("prep_weaknesses", [])
    key_players = st.session_state.get("prep_key_players", [])
    predicted = st.session_state.get("prep_predicted", "")
    notes_key = "prep_notes_" + (opp.get("name") or "opp")
    scout_notes = st.session_state.get(notes_key, "")

    our_form = st.session_state.get("prep_our_formation", "4-3-3")
    opp_form = st.session_state.get("prep_opp_formation", "4-3-3")
    set_piece_notes_key = "prep_set_piece_notes_" + (opp.get("name") or "opp").replace(" ", "_")
    set_piece_notes = st.session_state.get(set_piece_notes_key, "") or "(none)"
    _ro_key = (opp.get("name") or "opp").replace(" ", "_")
    us_want_report = st.session_state.get("prep_us_vs_them_want_" + _ro_key) or st.session_state.get("prep_us_vs_them_want_template", "")
    us_avoid_report = st.session_state.get("prep_us_vs_them_avoid_" + _ro_key) or st.session_state.get("prep_us_vs_them_avoid_template", "")
    non_neg_1 = st.session_state.get("prep_non_neg_1_" + _ro_key, "")
    non_neg_2 = st.session_state.get("prep_non_neg_2_" + _ro_key, "")
    non_neg_3 = st.session_state.get("prep_non_neg_3_" + _ro_key, "")
    talking_points_report = st.session_state.get("prep_talking_points", [])

    report_md = st.session_state.get("prep_report_md", "")
    if not report_md:
        report_lines = [
            f"# Opponent Prep: {your.get('name', 'Your team')} vs {opp.get('name', 'Opponent')}",
            f"\n**Season:** {opp.get('season', '')} · **Competition:** {opp.get('competition', '')}\n",
            "## Tactical summary",
            predicted,
            "## Match prediction",
            f"Expected xG (us–them): {st.session_state.get('prep_predicted_score', '—')}",
            f"Win / Draw / Loss: {st.session_state.get('prep_win_prob', (0, 0, 0))[0]:.0f}% / {st.session_state.get('prep_win_prob', (0, 0, 0))[1]:.0f}% / {st.session_state.get('prep_win_prob', (0, 0, 0))[2]:.0f}%",
            "## Key factors",
            *("- " + f for f in st.session_state.get("prep_key_factors", [])),
            "## Threats",
            *("- " + t for t in threats),
            "## Weaknesses",
            *("- " + w for w in weaknesses),
            "## Key players to watch",
            *("- " + p.get("name", "?") + f" ({p.get('position', '')}) – " + str(p.get("threat_level", "")) for p in key_players),
            "## Scout notes",
            scout_notes or "(none)",
            "## Set pieces",
            set_piece_notes,
            "## Checklist (review before match)",
            *checklist_items,
        ]
        report_md = "\n".join(report_lines)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📄 Download report (Markdown)",
            data=report_md,
            file_name=f"opponent_prep_{opp.get('name', 'report').replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col2:
        if st.button("← Back to Directory", use_container_width=True):
            st.switch_page("pages/1_🏟️_Team_Directory.py")

    # Link to Review (open in new tab so user keeps Prep state)
    st.markdown("**Open in Review** (opens in new tab)")
    q = {}
    if your.get("name"):
        q["home"] = your["name"]
    if opp.get("name"):
        q["away"] = opp["name"]
    schedule_url = f"{REVIEW_APP_URL}/pages/1_📅_Schedule"
    if q:
        schedule_url += "?" + urlencode(q)
    pre_match_url = f"{REVIEW_APP_URL}/pages/2_🔍_Pre_Match"
    st.markdown(
        f'<a href="{schedule_url}" target="_blank" rel="noopener" style="display:inline-block;margin-right:12px;padding:8px 16px;background:#21262D;color:#C9A840;border-radius:6px;text-decoration:none;border:1px solid #30363D;">📅 Add to Schedule</a> '
        f'<a href="{pre_match_url}" target="_blank" rel="noopener" style="display:inline-block;padding:8px 16px;background:#21262D;color:#C9A840;border-radius:6px;text-decoration:none;border:1px solid #30363D;">🔍 Open Pre-Match</a>',
        unsafe_allow_html=True,
    )
else:
    if st.button("← Back to Directory", use_container_width=True):
        st.switch_page("pages/1_🏟️_Team_Directory.py")
