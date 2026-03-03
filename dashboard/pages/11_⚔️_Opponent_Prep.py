"""Tactics Dashboard — Opponent Preparation (Enhanced).

Enhanced matchup analysis with:
- Side-by-side tactical comparison
- Formation visualization
- Opposition scouting report generation
- Key player exploitation recommendations
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).resolve().parent.parent.parent
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
    from dashboard.utils.data import get_team_season_selector_options
except ImportError:
    # Fallback when data.py is loaded from another path (e.g. Streamlit cwd)
    def get_team_season_selector_options(team_stats, default_season=None, default_competition_slugs=None, *, label_format="short", comp_name_getter=None):
        if team_stats.empty:
            return pd.DataFrame()
        df = team_stats.copy()
        if default_season:
            df = df[df["season"] == default_season]
        if default_competition_slugs:
            df = df[df["competition_slug"].isin(default_competition_slugs)]
        if df.empty:
            df = team_stats.copy()
        df["n_matches"] = df["matches_total"].fillna(0).astype(int) if "matches_total" in df.columns else 0
        if label_format == "full" and comp_name_getter:
            df["comp_label"] = df["competition_slug"].map(lambda c: comp_name_getter(c) or c)
            df["label"] = df.apply(lambda r: f"{r['team_name']} ({r['season']}, {r['comp_label']} — {int(r['n_matches'])} matches)", axis=1)
            out = df[["team_name", "season", "competition_slug", "label", "n_matches"]].copy()
            out["competitions"] = out.apply(lambda r: team_stats[(team_stats["team_name"] == r["team_name"]) & (team_stats["season"] == r["season"])]["competition_slug"].unique().tolist(), axis=1)
            return out.drop_duplicates(subset=["team_name", "season", "competition_slug"])
        agg = df.groupby(["team_name", "season"]).agg(competition_slug=("competition_slug", "first"), n_matches=("n_matches", "sum")).reset_index()
        agg["label"] = agg.apply(lambda r: f"{r['team_name']} ({r['season']})", axis=1)
        agg["competitions"] = agg.apply(lambda r: team_stats[(team_stats["team_name"] == r["team_name"]) & (team_stats["season"] == r["season"])]["competition_slug"].unique().tolist(), axis=1)
        return agg[["team_name", "season", "competition_slug", "label", "competitions", "n_matches"]]
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


def _suggest_non_negotiables(
    threats: list,
    weaknesses: list,
    key_opp_players: list,
) -> list:
    """Build 3 suggested non-negotiables from threats, weaknesses, and top key player.
    Returns a list of 3 actionable one-liners (edit as needed).
    """
    out = []
    # 1) From first threat
    if threats:
        t = (threats[0] or "").lower()
        if "press" in t and "high" in t:
            out.append("Match their press — clear options for the man on the ball, don't get trapped in our third.")
        elif "aerial" in t:
            out.append("Compete on second balls and set pieces — don't give them free headers.")
        elif "possession" in t or "retention" in t or "ball" in t:
            out.append("Press in moments when the ball is loose — don't let them settle.")
        else:
            out.append("Stay compact and disciplined — force them to play in front of us.")
    else:
        out.append("Stay compact and disciplined — force them to play in front of us.")

    # 2) From first weakness
    if weaknesses:
        w = (weaknesses[0] or "").lower()
        if "transition" in w or "defensive" in w:
            out.append("Exploit in transition — when we win the ball, break quickly and use the space behind.")
        elif "press" in w and "low" in w:
            out.append("Build from the back — we have time on the ball, use it to find the right pass.")
        elif "aerial" in w:
            out.append("Target set pieces and crosses — get the ball in the box and compete in the air.")
        else:
            out.append("Focus on individual quality in key moments.")
    else:
        out.append("Focus on individual quality in key moments.")

    # 3) From top key player
    if key_opp_players:
        p = key_opp_players[0]
        name = p.get("name") or "their key player"
        inst = (p.get("instruction") or "").strip()
        if inst and len(inst) < 80:
            out.append(f"Track {name} when we lose the ball — {inst}")
        else:
            out.append(f"Track {name} when we lose the ball — deny space, don't let him turn.")
    else:
        out.append("Win second balls in midfield — don't give them easy follow-ups.")

    return out[:3]


from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS
from dashboard.utils.scope import CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.utils.sidebar import render_sidebar
from dashboard.tactics.components.tactical_components import (
    render_tactical_radar_comparison,
    render_head_to_head_comparison,
    render_opposition_scouting_card,
    render_formation_pitch,
    get_xi_ordered_by_formation,
    get_opposition_slot_index,
    get_tactical_percentiles,
    render_recent_form_block,
)

# Page config
st.set_page_config(
    page_title="Opponent Prep · Tactics",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar()

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

# Default matchup: Westerlo (home/your) vs Union Saint-Gilloise (opponent) when nothing selected yet
DEFAULT_HOME_TEAM = "Westerlo"
DEFAULT_AWAY_TEAM = "Union Saint-Gilloise"
if st.session_state.your_team is None and st.session_state.opponent_team is None and not team_stats.empty:
    _teams = team_stats["team_name"].dropna().astype(str).tolist()
    _home = next((t for t in _teams if "westerlo" in t.lower()), None)
    _away = next((t for t in _teams if "union" in t.lower() and ("saint" in t.lower() or "gilloise" in t.lower())), None) or next((t for t in _teams if "union saint" in t.lower() or "saint-gilloise" in t.lower()), None)
    if _home and _away:
        _scope = team_stats[(team_stats["season"] == CURRENT_SEASON) & (team_stats["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS))]
        _scope = _scope if not _scope.empty else team_stats
        for _label, _name in [("your", _home), ("opp", _away)]:
            _rows = _scope[_scope["team_name"] == _name]
            if _rows.empty:
                _rows = team_stats[team_stats["team_name"] == _name]
            if not _rows.empty:
                r = _rows.iloc[0]
                _comps = team_stats[(team_stats["team_name"] == _name) & (team_stats["season"] == r["season"])]["competition_slug"].unique().tolist()
                if _label == "your":
                    st.session_state.your_team = {"name": r["team_name"], "season": r["season"], "competition": r["competition_slug"], "competitions": _comps}
                else:
                    st.session_state.opponent_team = {"name": r["team_name"], "season": r["season"], "competition": r["competition_slug"], "competitions": _comps}

# Deep link: ?your=TeamName&opp=OpponentName to open a specific matchup
_your_param = st.query_params.get("your", "").strip()
_opp_param = st.query_params.get("opp", "").strip()
if _your_param and _opp_param and not team_stats.empty:
    _teams = team_stats["team_name"].dropna().unique().tolist()
    _match_your = next((t for t in _teams if str(t).strip().lower() == _your_param.lower()), None) or next(
        (t for t in _teams if _your_param.lower() in str(t).lower()), None
    )
    _match_opp = next((t for t in _teams if str(t).strip().lower() == _opp_param.lower()), None) or next(
        (t for t in _teams if _opp_param.lower() in str(t).lower()), None
    )
    if _match_your and _match_opp:
        _row_your = team_stats[(team_stats["team_name"] == _match_your) & (team_stats["season"] == CURRENT_SEASON)]
        _row_opp = team_stats[(team_stats["team_name"] == _match_opp) & (team_stats["season"] == CURRENT_SEASON)]
        if _row_your.empty:
            _row_your = team_stats[team_stats["team_name"] == _match_your].iloc[:1]
        if _row_opp.empty:
            _row_opp = team_stats[team_stats["team_name"] == _match_opp].iloc[:1]
        if not _row_your.empty and not _row_opp.empty:
            r1, r2 = _row_your.iloc[0], _row_opp.iloc[0]
            _comps_your = team_stats[(team_stats["team_name"] == _match_your) & (team_stats["season"] == r1["season"])]["competition_slug"].unique().tolist()
            _comps_opp = team_stats[(team_stats["team_name"] == _match_opp) & (team_stats["season"] == r2["season"])]["competition_slug"].unique().tolist()
            st.session_state.your_team = {"name": r1["team_name"], "season": r1["season"], "competition": r1["competition_slug"], "competitions": _comps_your}
            st.session_state.opponent_team = {"name": r2["team_name"], "season": r2["season"], "competition": r2["competition_slug"], "competitions": _comps_opp}
            st.rerun()

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
        your_options = get_team_season_selector_options(
            team_stats, default_season=CURRENT_SEASON, default_competition_slugs=DEFAULT_COMPETITION_SLUGS, label_format="short"
        )
        if not your_options.empty:
            labels = your_options["label"].tolist()
            if st.session_state.your_team:
                try:
                    default_index = labels.index(f"{st.session_state.your_team['name']} ({st.session_state.your_team['season']})")
                except ValueError:
                    default_index = 0
            else:
                default_index = 0
            your_label = st.selectbox("Select your team:", labels, index=default_index, key="your_team_select")
            your_row = your_options[your_options["label"] == your_label].iloc[0]
            st.session_state.your_team = {
                "name": your_row["team_name"],
                "season": your_row["season"],
                "competition": your_row["competition_slug"],
                "competitions": your_row.get("competitions") or team_stats[(team_stats["team_name"] == your_row["team_name"]) & (team_stats["season"] == your_row["season"])]["competition_slug"].unique().tolist(),
            }

with col2:
    st.markdown("**Opponent**")

    if not team_stats.empty:
        opp_options = get_team_season_selector_options(
            team_stats, default_season=CURRENT_SEASON, default_competition_slugs=DEFAULT_COMPETITION_SLUGS, label_format="short"
        )
        if not opp_options.empty:
            labels = opp_options["label"].tolist()
            if st.session_state.opponent_team:
                try:
                    default_index = labels.index(f"{st.session_state.opponent_team['name']} ({st.session_state.opponent_team['season']})")
                except ValueError:
                    default_index = 0
            else:
                default_index = 0
            opp_label = st.selectbox("Select opponent:", labels, index=default_index, key="opp_team_select")
            opp_row = opp_options[opp_options["label"] == opp_label].iloc[0]
            st.session_state.opponent_team = {
                "name": opp_row["team_name"],
                "season": opp_row["season"],
                "competition": opp_row["competition_slug"],
                "competitions": opp_row.get("competitions") or team_stats[(team_stats["team_name"] == opp_row["team_name"]) & (team_stats["season"] == opp_row["season"])]["competition_slug"].unique().tolist(),
            }

# Swap teams button and Home/Away (when both selected)
if st.session_state.your_team and st.session_state.opponent_team:
    swap_col, venue_col = st.columns([1, 1])
    with swap_col:
        if st.button("⇄ Swap Your team ↔ Opponent", key="swap_teams"):
            st.session_state.your_team, st.session_state.opponent_team = st.session_state.opponent_team, st.session_state.your_team
            st.session_state["_swap_pending_your"] = f"{st.session_state.your_team['name']} ({st.session_state.your_team['season']})"
            st.session_state["_swap_pending_opp"] = f"{st.session_state.opponent_team['name']} ({st.session_state.opponent_team['season']})"
            st.rerun()
    with venue_col:
        if "prep_we_are_home" not in st.session_state:
            st.session_state["prep_we_are_home"] = True
        st.radio(
            "We are:",
            options=[True, False],
            format_func=lambda x: "🏠 Home" if x else "🚌 Away",
            index=0 if st.session_state["prep_we_are_home"] else 1,
            key="prep_we_are_home",
            horizontal=True,
        )

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
    # Allow switching competition context when team plays in multiple (league vs UCL etc.)
    _multi_your = your.get("competitions") and len(your["competitions"]) > 1
    _multi_opp = opp.get("competitions") and len(opp["competitions"]) > 1
    if _multi_your or _multi_opp:
        _cy, _co = st.columns(2)
        with _cy:
            if _multi_your:
                idx_y = your["competitions"].index(your["competition"]) if your["competition"] in your["competitions"] else 0
                new_comp_your = st.selectbox(
                    "Your team context (competition):",
                    options=your["competitions"],
                    format_func=lambda c: f"{COMP_FLAGS.get(c, '🏆')} {COMP_NAMES.get(c, c)}",
                    index=idx_y,
                    key="your_comp_context",
                )
                if new_comp_your != your.get("competition"):
                    st.session_state.your_team = {**your, "competition": new_comp_your}
                    your = st.session_state.your_team
            else:
                st.caption("Your team: single competition")
        with _co:
            if _multi_opp:
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
            else:
                st.caption("Opponent: single competition")

    # Venue: we're home or away (for fixture display and report)
    _we_are_home = st.session_state.get("prep_we_are_home", True)
    _fixture_home = your["name"] if _we_are_home else opp["name"]
    _fixture_away = opp["name"] if _we_are_home else your["name"]
    _venue_label = "🏠 We're home" if _we_are_home else "🚌 We're away"

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
                    "xg_against_total": float(y_row["xg_against_total"]) if pd.notna(y_row.get("xg_against_total")) else None,
                    "goals_against": int(y_row.get("goals_against", 0)) if pd.notna(y_row.get("goals_against")) else None,
                    "pass_completion_pct": _pass_pct(y_row),
                    "tackles_per_match": _per_match(y_row.get("tackles_total"), y_row.get("matches_total")),
                }
                opp_derived = {
                    "possession_pct": _pct(o_row.get("possession_avg")),
                    "shots_per_match": _per_match(o_row.get("shots_total"), o_row.get("matches_total")),
                    "xg_for_total": float(o_row["xg_for_total"]) if pd.notna(o_row.get("xg_for_total")) else None,
                    "goals_for": int(o_row.get("goals_for", 0)) if pd.notna(o_row.get("goals_for")) else None,
                    "xg_against_total": float(o_row["xg_against_total"]) if pd.notna(o_row.get("xg_against_total")) else None,
                    "goals_against": int(o_row.get("goals_against", 0)) if pd.notna(o_row.get("goals_against")) else None,
                    "pass_completion_pct": _pass_pct(o_row),
                    "tackles_per_match": _per_match(o_row.get("tackles_total"), o_row.get("matches_total")),
                }
                season_metrics = [
                    ("possession_pct", "Possession % (avg)"),
                    ("shots_per_match", "Shots per match (avg)"),
                    ("xg_for_total", "Total xG (season total)"),
                    ("goals_for", "Goals (season total)"),
                    ("xg_against_total", "Total xGA (season total)"),
                    ("goals_against", "Goals conceded (season total)"),
                    ("pass_completion_pct", "Pass completion % (avg)"),
                    ("tackles_per_match", "Tackles per match (avg)"),
                ]
                render_head_to_head_comparison(
                    pd.Series(your_derived),
                    pd.Series(opp_derived),
                    your["name"],
                    opp["name"],
                    metrics=season_metrics,
                    lower_is_better_keys=("xg_against_total", "goals_against"),
                )

        # Last 5 H2H — full width below radar and season comparison
        h2h = get_head_to_head(your["name"], opp["name"], n=5)
        if not h2h.empty:
            n_h2h = len(h2h)
            h2h_label = f"Last 5 H2H ({n_h2h} match{'es' if n_h2h != 1 else ''})"
            st.markdown(f"**{h2h_label}**")
            w_count = int((h2h["result"] == "W").sum())
            d_count = int((h2h["result"] == "D").sum())
            l_count = int((h2h["result"] == "L").sum())
            total_h2h = w_count + d_count + l_count
            if total_h2h > 0:
                w_pct = (w_count / total_h2h) * 100
                d_pct = (d_count / total_h2h) * 100
                l_pct = (l_count / total_h2h) * 100
                st.markdown(
                    f"""
                    <div style="display: flex; height: 28px; border-radius: 6px; overflow: hidden; margin: 8px 0 12px 0;">
                        <div style="width: {w_pct}%; background: #3FB950; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 0.8rem;">{w_count} W</div>
                        <div style="width: {d_pct}%; background: #8B949E; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 0.8rem;">{d_count} D</div>
                        <div style="width: {l_pct}%; background: #F85149; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 0.8rem;">{l_count} L</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
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
                # Best stats for card (up to 4 notable metrics)
                top_stats = []
                if goals > 0:
                    top_stats.append(("Goals", str(goals)))
                a = int(player.get('assists', 0) or 0)
                if a > 0:
                    top_stats.append(("Assists", str(a)))
                if xg90 > 0.05:
                    top_stats.append(("xG/90", f"{xg90:.2f}"))
                if xa90 > 0.05:
                    top_stats.append(("xA/90", f"{xa90:.2f}"))
                kp90 = player.get('keyPass_per90') or 0
                if kp90 and float(kp90) > 0.5:
                    top_stats.append(("Key passes/90", f"{float(kp90):.1f}"))
                if pos in ("D", "M"):
                    t90 = player.get('totalTackle_per90') or player.get('wonTackle_per90') or 0
                    if t90 and float(t90) > 1.0:
                        top_stats.append(("Tackles/90", f"{float(t90):.1f}"))
                if pos == "G":
                    s90 = player.get('saves_per90') or 0
                    if s90 and float(s90) > 0:
                        top_stats.append(("Saves/90", f"{float(s90):.1f}"))
                key_opp_players.append({
                    'name': player['player_name'],
                    'position': pos,
                    'role': role,
                    'rating': player.get('avg_rating', 6.5),
                    'threat_level': threat_level,
                    'goals': goals,
                    'assists': a,
                    'xg90': xg90,
                    'xa90': xa90,
                    'top_stats': top_stats[:4],
                    'strengths': strengths or ["Key player"],
                    'weaknesses': weaknesses,
                    'instruction': instruction,
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
        # Key player cards — one card per player, best stats + why rated high (no scroll)
        # ---------------------------------------------------------------------------
        st.markdown("---")
        st.markdown("<div class='section-header'>🃏 Key player cards</div>", unsafe_allow_html=True)
        n_players = len(key_opp_players)
        if n_players == 0:
            st.caption("No key players loaded.")
        else:
            cols = st.columns(min(n_players, 5))
            for idx, p in enumerate(key_opp_players):
                col = cols[idx % len(cols)]
                with col:
                    top_stats = p.get("top_stats") or []
                    strengths_list = p.get("strengths") if isinstance(p.get("strengths"), list) else [str(p.get("strengths", ""))]
                    strengths_str = " · ".join(strengths_list) if strengths_list else "Key player"
                    stats_line = " · ".join(f"{k}: {v}" for k, v in top_stats) if top_stats else "—"
                    instruction = (p.get("instruction") or "").strip()
                    weaknesses = (p.get("weaknesses") or "").strip()
                    # Actionable blocks: how to play against + what to exploit (when we have them)
                    action_html = ""
                    if instruction:
                        action_html += f'<div style="font-size: 0.75rem; color: #3FB950; margin-top: 6px;"><strong>How to play against:</strong> {instruction}</div>'
                    if weaknesses:
                        action_html += f'<div style="font-size: 0.75rem; color: #F85149; margin-top: 4px;"><strong>Exploit:</strong> {weaknesses}</div>'
                    st.markdown(
                        f"""
                        <div style="
                            background: #21262D;
                            border: 1px solid #30363D;
                            border-radius: 10px;
                            padding: 12px;
                            margin-bottom: 12px;
                        ">
                            <div style="font-weight: 700; color: #F0F6FC; font-size: 0.95rem;">{p.get('name', '?')}</div>
                            <div style="font-size: 0.8rem; color: #8B949E; margin-top: 2px;">{p.get('role', p.get('position', ''))} · Rating {p.get('rating', 0):.2f}</div>
                            <div style="font-size: 0.75rem; color: #C9A840; margin-top: 8px;"><strong>Best stats:</strong> {stats_line}</div>
                            <div style="font-size: 0.75rem; color: #E6EDF3; margin-top: 6px;"><strong>Why rated high:</strong> {strengths_str}</div>
                            {action_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # ---------------------------------------------------------------------------
        # Recent Form (last 5) — same design as Tactical Profile: pills, pts, xG bar, match cards
        # ---------------------------------------------------------------------------
        st.markdown("---")
        st.markdown("<div class='section-header'>📈 Recent Form</div>", unsafe_allow_html=True)
        form_col1, form_col2 = st.columns(2)
        with form_col1:
            try:
                your_last5 = get_team_last_matches(your["name"], your["season"], your["competition"], n=5)
                render_recent_form_block(
                    your["name"],
                    your_last5,
                    show_team_heading=True,
                    caption_suffix="",
                )
            except Exception:
                st.caption("Match history unavailable.")
        with form_col2:
            try:
                opp_last5 = get_team_last_matches(opp["name"], opp["season"], opp["competition"], n=5)
                render_recent_form_block(
                    opp["name"],
                    opp_last5,
                    show_team_heading=True,
                    caption_suffix="",
                )
            except Exception:
                st.caption("Match history unavailable.")

        # Staff talking points (auto from threats, weaknesses, key players)
        talking_points = []
        for t in threats:
            talking_points.append(f"Be aware: {t}")
        for w in weaknesses:
            talking_points.append(f"Exploit: {w}")
        for p in key_opp_players[:3]:
            talking_points.append(f"Watch: {p.get('name', '?')} – {p.get('position', '')} ({p.get('threat_level', '')} threat)")
        st.session_state["prep_talking_points"] = talking_points[:10]

        # Non-negotiables (keyed by opponent)
        for i in range(1, 4):
            k = "prep_non_neg_" + str(i) + "_" + _opp_key
            if k not in st.session_state:
                st.session_state[k] = ""

        # ---------------------------------------------------------------------------
        # Tabs: Full prep | Match-day brief | Gaffer sheet
        # ---------------------------------------------------------------------------
        tab_full, tab_brief, tab_gaffer = st.tabs(["Full prep", "Match-day brief", "📄 Gaffer sheet"])

        with tab_full:
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
                    render_formation_pitch(your_formation, your_form_players, width=420, height=360, key="formation_your")

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
                    render_formation_pitch(opp_formation, opp_form_players, width=420, height=360, key="formation_opp")

            # ---------------------------------------------------------------------------
            # Expected duels (our XI vs their XI ordered by formation slot, same slot = same role)
            # ---------------------------------------------------------------------------
            if your_form_players and opp_form_players:
                st.markdown("---")
                st.markdown("<div class='section-header'>📋 Expected duels (by formation)</div>", unsafe_allow_html=True)
                st.caption("Cross-pitch pairings: who our player typically faces (e.g. our LB vs their RW, our LW vs their RB). Use for marking assignments and individual matchups.")
                our_ordered = get_xi_ordered_by_formation(your_formation, your_form_players)
                their_ordered = get_xi_ordered_by_formation(opp_formation, opp_form_players)
                n_our = len(our_ordered)
                n_their = len(their_ordered)
                matchup_rows = []
                for i in range(n_our):
                    ours, slot_our = our_ordered[i]
                    j = get_opposition_slot_index(i, your_formation)
                    if j < n_their:
                        theirs, slot_their = their_ordered[j]
                    else:
                        theirs, slot_their = {"name": "?", "position": ""}, "?"
                    matchup_rows.append({
                        "Our slot": slot_our,
                        "Our player": ours.get("name", "?"),
                        "Our pos": ours.get("position", ""),
                        "vs": "vs",
                        "Their player": theirs.get("name", "?") if isinstance(theirs, dict) else "?",
                        "Their pos": theirs.get("position", "") if isinstance(theirs, dict) else "",
                        "Their slot": slot_their,
                    })
                st.dataframe(
                    pd.DataFrame(matchup_rows),
                    use_container_width=True,
                    hide_index=True,
                )
                st.session_state["prep_matchup_rows"] = matchup_rows

            # ---------------------------------------------------------------------------
            # Opponent squad — All players & statistics (one row per player, aggregated across competitions)
            # ---------------------------------------------------------------------------
            if not opp_players.empty:
                st.markdown("---")
                st.markdown("<div class='section-header'>📋 Opponent squad — All players & statistics</div>", unsafe_allow_html=True)
                st.caption(f"Full squad for {opp['name']} ({opp['season']}) — one row per player (stats averaged/aggregated across all competitions). Sort by clicking column headers.")
                # Aggregate by player: one row per player (merge rows from multiple competitions)
                group_col = "player_id" if "player_id" in opp_players.columns else "player_name"
                sum_cols = [c for c in ["total_minutes", "appearances", "goals", "assists"] if c in opp_players.columns]
                first_cols = [c for c in ["player_name", "player_position", "age_at_season_start"] if c in opp_players.columns]
                wavg_cols = [c for c in [
                    "avg_rating", "pass_accuracy", "goals_per90", "expectedGoals_per90", "expectedAssists_per90",
                    "keyPass_per90", "bigChanceCreated_per90", "totalTackle_per90", "interceptionWon_per90",
                    "duelWon_per90", "aerialWon_per90", "ballRecovery_per90", "totalPass_per90",
                    "progressiveBallCarriesCount_per90", "saves_per90", "goalsPrevented_per90",
                ] if c in opp_players.columns]
                agg_dict = {c: "sum" for c in sum_cols}
                agg_dict.update({c: "first" for c in first_cols if c != group_col})
                squad_table_df = opp_players.groupby(group_col, as_index=False).agg(agg_dict)
                for c in first_cols:
                    if c != group_col and c not in squad_table_df.columns:
                        squad_table_df[c] = opp_players.groupby(group_col)[c].first().values
                for c in wavg_cols:
                    squad_table_df[c] = (
                        opp_players.groupby(group_col).apply(
                            lambda g: np.average(g[c].fillna(0), weights=g["total_minutes"].fillna(0))
                            if g["total_minutes"].fillna(0).sum() > 0 else np.nan
                        ).values
                    )
                if "pass_accuracy" in squad_table_df.columns and "pass_accuracy_pct" not in squad_table_df.columns:
                    squad_table_df["pass_accuracy_pct"] = (squad_table_df["pass_accuracy"] * 100).round(1)
                display_cols = [
                    "player_name", "player_position", "age_at_season_start",
                    "appearances", "total_minutes", "avg_rating",
                    "goals", "assists",
                    "goals_per90", "expectedGoals_per90", "expectedAssists_per90",
                    "keyPass_per90", "bigChanceCreated_per90",
                    "totalTackle_per90", "interceptionWon_per90", "duelWon_per90", "aerialWon_per90",
                    "ballRecovery_per90", "totalPass_per90", "pass_accuracy_pct",
                    "progressiveBallCarriesCount_per90",
                    "saves_per90", "goalsPrevented_per90",
                ]
                existing = [c for c in display_cols if c in squad_table_df.columns]
                squad_table_df = squad_table_df[existing].copy()
                if "total_minutes" in squad_table_df.columns:
                    squad_table_df = squad_table_df.sort_values("total_minutes", ascending=False)
                col_rename = {
                    "player_name": "Player", "player_position": "Pos", "age_at_season_start": "Age",
                    "appearances": "Apps", "total_minutes": "Mins", "avg_rating": "Rating",
                    "goals": "Goals", "assists": "Assists", "goals_per90": "G/90",
                    "expectedGoals_per90": "xG/90", "expectedAssists_per90": "xA/90",
                    "keyPass_per90": "KP/90", "bigChanceCreated_per90": "BCC/90",
                    "totalTackle_per90": "Tkl/90", "interceptionWon_per90": "Int/90",
                    "duelWon_per90": "DW/90", "aerialWon_per90": "Air/90",
                    "ballRecovery_per90": "Rec/90", "totalPass_per90": "Pass/90",
                    "pass_accuracy_pct": "Pass%", "progressiveBallCarriesCount_per90": "ProgC/90",
                    "saves_per90": "Sv/90", "goalsPrevented_per90": "GkPrev/90",
                }
                squad_table_df = squad_table_df.rename(columns={k: v for k, v in col_rename.items() if k in squad_table_df.columns})
                if "Age" in squad_table_df.columns:
                    age_ser = pd.to_numeric(squad_table_df["Age"], errors="coerce").round(0)
                    try:
                        squad_table_df["Age"] = age_ser.astype("Int64")
                    except (TypeError, ValueError):
                        squad_table_df["Age"] = age_ser.where(age_ser.notna(), np.nan).astype(float)
                for count_col in ["Mins", "Apps", "Goals", "Assists"]:
                    if count_col in squad_table_df.columns:
                        squad_table_df[count_col] = squad_table_df[count_col].fillna(0).astype(int)
                if "Rating" in squad_table_df.columns:
                    squad_table_df["Rating"] = pd.to_numeric(squad_table_df["Rating"], errors="coerce").round(1)
                for col in squad_table_df.columns:
                    if col in ("Player", "Pos", "Age", "Mins", "Apps", "Goals", "Assists"):
                        continue
                    if squad_table_df[col].dtype in (np.floating, "float64"):
                        squad_table_df[col] = squad_table_df[col].round(2)
                st.dataframe(squad_table_df, use_container_width=True, hide_index=True)

        with tab_brief:
            _report_md = st.session_state.get("prep_report_md", "")
            if _report_md:
                st.download_button(
                    "📄 Download full report (Markdown)",
                    data=_report_md,
                    file_name=f"opponent_prep_{opp.get('name', 'report').replace(' ', '_')}.md",
                    mime="text/markdown",
                    key="brief_download_report",
                    use_container_width=True,
                    type="primary",
                )
            st.markdown("---")
            st.markdown(f"**{_fixture_home}** vs **{_fixture_away}** · {_venue_label} · {COMP_FLAGS.get(opp.get('competition', ''), '')} {COMP_NAMES.get(opp.get('competition', ''), opp.get('competition', ''))} · {opp.get('season', '')}")
            st.markdown("---")
            st.markdown("**Formations**")
            st.markdown(f"- Our team: **{st.session_state.get('prep_our_formation', '4-3-3')}** · Opponent: **{st.session_state.get('prep_opp_formation', '4-3-3')}**")
            st.markdown("---")
            st.markdown("**Three non-negotiables**")
            _threats_for_suggest = st.session_state.get("prep_threats", [])
            _weaknesses_for_suggest = st.session_state.get("prep_weaknesses", [])
            _kp_for_suggest = st.session_state.get("prep_key_players", [])
            if st.button("✨ Suggest 3", key="prep_suggest_3", help="Fill from threats, weaknesses and key player — edit as needed."):
                _suggested = _suggest_non_negotiables(_threats_for_suggest, _weaknesses_for_suggest, _kp_for_suggest)
                for i, _text in enumerate(_suggested[:3]):
                    st.session_state["prep_non_neg_" + str(i + 1) + "_" + _opp_key] = _text
                st.rerun()
            st.text_input("1", value=st.session_state.get("prep_non_neg_1_" + _opp_key, ""), placeholder="E.g. Press their back line on goal kicks", key="prep_non_neg_1_" + _opp_key, label_visibility="collapsed")
            st.text_input("2", value=st.session_state.get("prep_non_neg_2_" + _opp_key, ""), placeholder="E.g. Track their 10 when we lose the ball", key="prep_non_neg_2_" + _opp_key, label_visibility="collapsed")
            st.text_input("3", value=st.session_state.get("prep_non_neg_3_" + _opp_key, ""), placeholder="E.g. Win second balls in midfield", key="prep_non_neg_3_" + _opp_key, label_visibility="collapsed")
            st.markdown("---")
            st.markdown("**Staff talking points**")
            for pt in st.session_state.get("prep_talking_points", []):
                st.markdown(f"- {pt}")
            if not _report_md:
                st.caption("Generate the full report by viewing the Full prep tab once, then return here to download.")

        with tab_gaffer:
            # One-page gaffer sheet: same data as Match-day brief, layout optimized for A4 print.
            _n1 = st.session_state.get("prep_non_neg_1_" + _opp_key, "")
            _n2 = st.session_state.get("prep_non_neg_2_" + _opp_key, "")
            _n3 = st.session_state.get("prep_non_neg_3_" + _opp_key, "")
            _tp = st.session_state.get("prep_talking_points", [])[:7]
            _threats = st.session_state.get("prep_threats", [])
            _weaknesses = st.session_state.get("prep_weaknesses", [])
            _kp = st.session_state.get("prep_key_players", [])[:5]
            _duels = st.session_state.get("prep_matchup_rows", [])
            _our_f = st.session_state.get("prep_our_formation", "4-3-3")
            _opp_f = st.session_state.get("prep_opp_formation", "4-3-3")
            _comp_label = f"{COMP_FLAGS.get(opp.get('competition', ''), '')} {COMP_NAMES.get(opp.get('competition', ''), opp.get('competition', ''))}"

            def _h(s: str) -> str:
                if not s:
                    return ""
                return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            _title = _h(f"{_fixture_home} vs {_fixture_away}")
            _venue = _h(_venue_label)
            _gaffer_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Gaffer sheet — {_title}</title>
<style>
@page {{ size: A4; margin: 12mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: system-ui, -apple-system, sans-serif; font-size: 9pt; line-height: 1.25; color: #1a1a1a; margin: 0; padding: 10px; max-width: 210mm; }}
.gaffer {{ width: 100%; }}
h1 {{ font-size: 14pt; margin: 0 0 6px 0; border-bottom: 2px solid #333; padding-bottom: 4px; }}
.meta {{ font-size: 8pt; color: #555; margin-bottom: 8px; }}
.section {{ margin-bottom: 8px; break-inside: avoid; }}
.section h2 {{ font-size: 10pt; margin: 0 0 4px 0; color: #333; }}
.section ul {{ margin: 0; padding-left: 16px; }}
.section li {{ margin: 2px 0; }}
.duels {{ font-size: 7.5pt; border-collapse: collapse; width: 100%; }}
.duels th, .duels td {{ border: 1px solid #ccc; padding: 2px 4px; text-align: left; }}
.duels th {{ background: #eee; }}
@media print {{ body {{ padding: 0; }} .section {{ break-inside: avoid; }} }}
</style>
</head>
<body>
<div class="gaffer">
<h1>{_title}</h1>
<p class="meta">{_venue} · {_h(_comp_label)} · {_h(opp.get('season', ''))}</p>
<p class="meta"><strong>Formations:</strong> Us {_our_f} — Opponent {_opp_f}</p>

<div class="section">
<h2>Non-negotiables</h2>
<ol>
<li>{_h(_n1) or "—"}</li>
<li>{_h(_n2) or "—"}</li>
<li>{_h(_n3) or "—"}</li>
</ol>
</div>

<div class="section">
<h2>Talking points</h2>
<ul>
"""
            for pt in _tp:
                _gaffer_html += f"<li>{_h(pt)}</li>\n"
            _gaffer_html += """</ul>
</div>

<div class="section">
<h2>Threats</h2>
<ul>
"""
            for t in _threats:
                _gaffer_html += f"<li>{_h(t)}</li>\n"
            _gaffer_html += """</ul>
</div>

<div class="section">
<h2>Exploit</h2>
<ul>
"""
            for w in _weaknesses:
                _gaffer_html += f"<li>{_h(w)}</li>\n"
            _gaffer_html += """</ul>
</div>

<div class="section">
<h2>Key players</h2>
<ul>
"""
            for p in _kp:
                name = _h(p.get("name", "?"))
                role = _h(p.get("role", p.get("position", "")))
                inst = _h((p.get("instruction") or "").strip())
                _gaffer_html += f"<li><strong>{name}</strong> ({role})" + (f" — {inst}" if inst else "") + "</li>\n"
            _gaffer_html += """</ul>
</div>
"""
            if _duels:
                _gaffer_html += """<div class="section">
<h2>Duels</h2>
<table class="duels"><thead><tr><th>Us</th><th>Player</th><th></th><th>Player</th><th>Them</th></tr></thead><tbody>
"""
                for r in _duels:
                    _gaffer_html += f"<tr><td>{_h(r.get('Our slot', ''))}</td><td>{_h(r.get('Our player', ''))}</td><td>vs</td><td>{_h(r.get('Their player', ''))}</td><td>{_h(r.get('Their slot', ''))}</td></tr>\n"
                _gaffer_html += "</tbody></table>\n</div>\n"
            _gaffer_html += "</div>\n</body>\n</html>"

            st.caption("One-page brief for the bench. Download the HTML, open in a browser, then **Print → Save as PDF** or print on A4.")
            st.download_button(
                "📄 Download Gaffer sheet (HTML)",
                data=_gaffer_html,
                file_name=f"gaffer_sheet_{opp.get('name', 'match').replace(' ', '_')}.html",
                mime="text/html",
                key="gaffer_download",
                use_container_width=True,
                type="primary",
            )
            with st.expander("Preview (compact)"):
                st.markdown(f"**{_fixture_home}** vs **{_fixture_away}** · {_venue_label}")
                st.markdown(f"*Formations:* {_our_f} / {_opp_f}")
                st.markdown("**Non-negotiables:** 1. " + (_n1 or "—") + " 2. " + (_n2 or "—") + " 3. " + (_n3 or "—"))
                st.markdown("**Talking points:** " + " | ".join(_tp[:5]))
                st.markdown("**Threats:** " + "; ".join(_threats[:3]))
                st.markdown("**Exploit:** " + "; ".join(_weaknesses[:3]))
                st.markdown("**Key players:** " + ", ".join(p.get("name", "?") for p in _kp))

        # Build report and store for Match-day brief download and bottom section
        _n1 = st.session_state.get("prep_non_neg_1_" + _opp_key, "")
        _n2 = st.session_state.get("prep_non_neg_2_" + _opp_key, "")
        _n3 = st.session_state.get("prep_non_neg_3_" + _opp_key, "")
        _tp = st.session_state.get("prep_talking_points", [])
        _report_lines = [
            f"# Opponent Prep: {_fixture_home} vs {_fixture_away} ({_venue_label})",
            f"\n**Season:** {opp.get('season', '')} · **Competition:** {opp.get('competition', '')} · **Venue:** {_venue_label}\n",
            "## Tactical brief (match-day)",
            f"- **Formations:** Our team {st.session_state.get('prep_our_formation', '4-3-3')} · Opponent {st.session_state.get('prep_opp_formation', '4-3-3')}",
            "- **Three non-negotiables:**",
            f"  1. {_n1 or '(not set)'}",
            f"  2. {_n2 or '(not set)'}",
            f"  3. {_n3 or '(not set)'}",
            "- **Staff talking points:**",
            *("  - " + t for t in _tp),
            "",
            "## Formations",
            f"- **Our team:** {st.session_state.get('prep_our_formation', '4-3-3')}",
            f"- **Opponent:** {st.session_state.get('prep_opp_formation', '4-3-3')}",
            "",
            "## Tactical summary",
            st.session_state.get("prep_predicted", ""),
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
                for p in st.session_state.get("prep_key_players", [])
            ),
            "## Expected duels (by formation)",
            *([f"- **{r.get('Our slot', '')}** {r.get('Our player', '?')} ({r.get('Our pos', '')}) vs **{r.get('Their slot', '')}** {r.get('Their player', '?')} ({r.get('Their pos', '')})" for r in st.session_state.get("prep_matchup_rows", [])] or ["(Review Full prep tab for expected duels)"]),
        ]
        st.session_state["prep_report_md"] = "\n".join(_report_lines)

    else:
        st.warning("Tactical data not available for one or both teams.")
        st.caption(
            "Run pipeline steps **01** (team_season_stats) and **15** (team_tactical_profiles) for full tactical clash, radars, and prediction."
        )

# Export report and navigation
st.markdown("---")
if st.session_state.your_team and st.session_state.opponent_team:
    your = st.session_state.your_team
    opp = st.session_state.opponent_team
    threats = st.session_state.get("prep_threats", [])
    weaknesses = st.session_state.get("prep_weaknesses", [])
    key_players = st.session_state.get("prep_key_players", [])
    predicted = st.session_state.get("prep_predicted", "")
    _ro_key = (opp.get("name") or "opp").replace(" ", "_")
    non_neg_2 = st.session_state.get("prep_non_neg_2_" + _ro_key, "")
    non_neg_3 = st.session_state.get("prep_non_neg_3_" + _ro_key, "")
    talking_points_report = st.session_state.get("prep_talking_points", [])

    report_md = st.session_state.get("prep_report_md", "")
    if not report_md:
        _we_home = st.session_state.get("prep_we_are_home", True)
        _home = your.get("name", "Your team") if _we_home else opp.get("name", "Opponent")
        _away = opp.get("name", "Opponent") if _we_home else your.get("name", "Your team")
        _venue = "🏠 We're home" if _we_home else "🚌 We're away"
        report_lines = [
            f"# Opponent Prep: {_home} vs {_away} ({_venue})",
            f"\n**Season:** {opp.get('season', '')} · **Competition:** {opp.get('competition', '')} · **Venue:** {_venue}\n",
            "## Tactical summary",
            predicted,
            "## Threats",
            *("- " + t for t in threats),
            "## Weaknesses",
            *("- " + w for w in weaknesses),
            "## Key players to watch",
            *("- " + p.get("name", "?") + f" ({p.get('position', '')}) – " + str(p.get("threat_level", "")) for p in key_players),
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
            st.switch_page("pages/9_🏟️_Team_Directory.py")

else:
    if st.button("← Back to Directory", use_container_width=True):
        st.switch_page("pages/9_🏟️_Team_Directory.py")
