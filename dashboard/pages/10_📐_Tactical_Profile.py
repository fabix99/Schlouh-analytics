"""Tactics Dashboard — Tactical Profile (Enhanced).

Deep team analysis with:
- Formation visualizations
- Tactical indices radar
- Strengths/weaknesses with data insights
- Squad composition and player roles
- Tactical evolution tracking
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from dashboard.utils.data import (
    load_team_season_stats,
    load_tactical_profiles,
    load_enriched_season_stats,
    get_team_wdl,
    get_team_last_matches,
    load_match_summary,
    get_raw_match_dir_for_match_id,
    format_percentile,
)
# Import formation helpers; load from project file so we always get formation_from_heatmaps_season (avoids cache/shadowing)
import importlib.util
_formation_heatmaps_path = _project_root / "dashboard" / "utils" / "formation_from_heatmaps.py"
if _formation_heatmaps_path.exists():
    _formation_spec = importlib.util.spec_from_file_location("formation_from_heatmaps", _formation_heatmaps_path)
    _formation_mod = importlib.util.module_from_spec(_formation_spec)
    sys.modules[_formation_spec.name] = _formation_mod  # required so dataclass type resolution finds the module
    _formation_spec.loader.exec_module(_formation_mod)
    formation_from_heatmaps = _formation_mod.formation_from_heatmaps
    formation_from_heatmaps_season = getattr(_formation_mod, "formation_from_heatmaps_season", None)
    formation_from_heatmaps_to_render_args = _formation_mod.formation_from_heatmaps_to_render_args
    load_lineups_for_match = _formation_mod.load_lineups_for_match
else:
    formation_from_heatmaps_season = None
    from dashboard.utils.formation_from_heatmaps import (
        formation_from_heatmaps,
        formation_from_heatmaps_to_render_args,
        load_lineups_for_match,
    )
try:
    from dashboard.utils.data import get_team_season_selector_options
except ImportError:
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
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS, TACTICAL_INDEX_LABELS, TACTICAL_TAGS, AGE_BANDS, POSITION_NAMES
from dashboard.utils.scope import CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.utils.validation import safe_divide
from dashboard.utils.sidebar import render_sidebar
# Import enhanced tactical components
from dashboard.tactics.components.tactical_components import (
    render_formation_pitch,
    render_formation_pitch_from_heatmaps,
    infer_formation_from_players,
    render_opposition_scouting_card,
    render_tactical_style_evolution,
    TACTICAL_RADAR_INDICES,
    normalize_tactical_radar_to_100,
    get_tactical_percentiles,
)

# Page config (title reflects selected team when set — improvement #28)
_page_title = "Tactical Profile · Tactics"
if st.session_state.get("selected_team") and isinstance(st.session_state["selected_team"], dict):
    _page_title = f"{st.session_state['selected_team'].get('name', 'Team')} · Tactical Profile · Schlouh"
st.set_page_config(
    page_title=_page_title,
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar()

# Initialize session state
if "selected_team" not in st.session_state:
    st.session_state.selected_team = None

# Load data (lazy: player_df only when we have a selected team, to speed up Home/Directory)
team_stats = load_team_season_stats()
tactical_df = load_tactical_profiles()
player_df = pd.DataFrame()

# ---------------------------------------------------------------------------
# Team Selection
# ---------------------------------------------------------------------------
if st.session_state.selected_team is None:
    st.markdown(
        """
        <div class="page-hero">
            <div class="page-hero-title">📐 Tactical Profile</div>
            <div class="page-hero-sub">
                Select a team to analyze their tactical identity, formations, and evolution.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Team selector (default: current season + leagues/UEFA) — shared helper for consistency with Opponent Prep
    if not team_stats.empty:
        team_options = get_team_season_selector_options(
            team_stats,
            default_season=CURRENT_SEASON,
            default_competition_slugs=DEFAULT_COMPETITION_SLUGS,
            label_format="full",
            comp_name_getter=COMP_NAMES.get,
        )
        if not team_options.empty:
            st.caption("Default: current season, selected leagues + UEFA. Select team to analyze.")
            selected_label = st.selectbox("Select team:", team_options["label"].tolist(), key="profile_team_select")
            selected_row = team_options[team_options["label"] == selected_label].iloc[0]
            comps_for_team = selected_row.get("competitions") or team_stats[
                (team_stats["team_name"] == selected_row["team_name"]) &
                (team_stats["season"] == selected_row["season"])
            ]["competition_slug"].unique().tolist()
            st.session_state.selected_team = {
                "name": selected_row["team_name"],
                "season": selected_row["season"],
                "competition": selected_row["competition_slug"],
                "competitions": comps_for_team,
            }
            if st.button("Analyze Team", type="primary", use_container_width=True):
                st.rerun()
        else:
            st.error("No team data in default scope")
    else:
        st.error("No team data available")
    st.stop()

# Sentinel for "all competitions" when team plays in multiple
ALL_COMPETITIONS = "__all__"

# ---------------------------------------------------------------------------
# Display Team Profile (one team; filter by competition or show all merged)
# ---------------------------------------------------------------------------
team_info = st.session_state.selected_team
team_name = team_info["name"]
season = team_info["season"]
# Support both legacy single "competition" and new "competitions" list from Directory
comps_list = team_info.get("competitions") or []
if not comps_list:
    comps_list = [team_info.get("competition", "")] if team_info.get("competition") else []

if len(comps_list) > 1:
    # Build option labels: "All" first, then each competition
    match_counts = {}
    for c in comps_list:
        r = team_stats[(team_stats["team_name"] == team_name) & (team_stats["season"] == season) & (team_stats["competition_slug"] == c)]
        match_counts[c] = int(r["matches_total"].iloc[0]) if not r.empty and "matches_total" in r.columns else 0
    total_matches = sum(match_counts.get(c, 0) for c in comps_list)
    comp_options = [ALL_COMPETITIONS] + comps_list
    comp_option = st.selectbox(
        "View data from:",
        options=comp_options,
        format_func=lambda c: (
            f"All competitions ({total_matches} matches)" if c == ALL_COMPETITIONS
            else f"{COMP_FLAGS.get(c, '🏆')} {COMP_NAMES.get(c, c)} ({match_counts.get(c, 0)} matches)"
        ),
        key="tactical_profile_comp_filter",
        help="Default: all data. Or select a single competition (e.g. Bundesliga or Champions League).",
    )
    competition = comp_option
else:
    competition = comps_list[0] if comps_list else team_info.get("competition", "")

# Subtitle: "All competitions" or single comp name
if competition == ALL_COMPETITIONS:
    _subtitle = f"All competitions · {season}"
else:
    _subtitle = f"{COMP_FLAGS.get(competition, '🏆')} {COMP_NAMES.get(competition, competition)} · {season}"

st.markdown(
    f"""
    <div class="page-hero">
        <div class="page-hero-title">{team_name}</div>
        <div class="page-hero-sub">
            {_subtitle}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Get team data (single competition or aggregated across all)
if competition == ALL_COMPETITIONS and comps_list:
    # Aggregate team_stats across all competitions
    team_row = team_stats[
        (team_stats["team_name"] == team_name) &
        (team_stats["season"] == season) &
        (team_stats["competition_slug"].isin(comps_list))
    ]
    if team_row.empty:
        st.error("Team data not found")
        st.stop()
    # Sum totals; weighted average for rates
    sum_cols = ["matches_total", "matches_home", "matches_away", "goals_for", "goals_against", "xg_for_total", "xg_against_total",
                "shots_total", "corners_total", "fouls_total", "passes_total", "accurate_passes_total", "tackles_total", "big_chances_total"]
    sum_cols = [c for c in sum_cols if c in team_row.columns]
    agg = team_row[sum_cols].sum()
    # Weighted averages for possession_avg, pass_accuracy_avg (by matches_total)
    m = team_row["matches_total"].sum()
    if m and m > 0:
        for col in ["possession_avg", "pass_accuracy_avg"]:
            if col in team_row.columns:
                agg[col] = (team_row[col] * team_row["matches_total"]).sum() / m
    agg["team_name"] = team_name
    agg["season"] = season
    agg["competition_slug"] = ALL_COMPETITIONS
    team_data = agg
    # Aggregate tactical: mean of indices across competitions
    tac_row = tactical_df[
        (tactical_df["team_name"] == team_name) &
        (tactical_df["season"] == season) &
        (tactical_df["competition_slug"].isin(comps_list))
    ]
    tac_data = tac_row.mean(numeric_only=True).to_dict() if not tac_row.empty else None
    if tac_data is not None:
        tac_data["team_name"] = team_name
        tac_data["season"] = season
        tac_data["competition_slug"] = ALL_COMPETITIONS
else:
    team_row = team_stats[
        (team_stats["team_name"] == team_name) &
        (team_stats["season"] == season) &
        (team_stats["competition_slug"] == competition)
    ]
    tac_row = tactical_df[
        (tactical_df["team_name"] == team_name) &
        (tactical_df["season"] == season) &
        (tactical_df["competition_slug"] == competition)
    ]
    if team_row.empty:
        st.error("Team data not found")
        st.stop()
    team_data = team_row.iloc[0]
    tac_data = tac_row.iloc[0].to_dict() if not tac_row.empty else None

# Lazy load player data only when showing a team (improvement #54)
if player_df.empty:
    with st.spinner("Loading player data…"):
        player_df = load_enriched_season_stats()

# Local form helper (avoids depending on get_team_form in data.py)
def _team_form(team_name: str, season: str, comp: str, n: int = 5) -> dict:
    last = get_team_last_matches(team_name, season, comp, n=n)
    if last.empty or "result" not in last.columns:
        return {"form_string": "", "points": 0, "W": 0, "D": 0, "L": 0}
    w = int((last["result"] == "W").sum())
    d = int((last["result"] == "D").sum())
    l = int((last["result"] == "L").sum())
    form_string = " ".join(last["result"].astype(str).tolist())
    return {"form_string": form_string, "points": 3 * w + d, "W": w, "D": d, "L": l}


def _team_wdl_all_comps(team_name: str, season: str, comps_list: list) -> dict:
    """Sum W-D-L across multiple competitions."""
    out = {"W": 0, "D": 0, "L": 0}
    for c in comps_list:
        wdl = get_team_wdl(team_name, season, c)
        out["W"] += wdl.get("W", 0)
        out["D"] += wdl.get("D", 0)
        out["L"] += wdl.get("L", 0)
    out["matches"] = out["W"] + out["D"] + out["L"]
    return out


def _team_last_matches_all_comps(team_name: str, season: str, comps_list: list, n: int = 5) -> pd.DataFrame:
    """Last N matches across competitions, sorted by date (most recent first)."""
    ms = load_match_summary()
    mask = (
        ((ms["home_team_name"] == team_name) | (ms["away_team_name"] == team_name)) &
        (ms["season"] == season) &
        (ms["competition_slug"].isin(comps_list))
    )
    team_matches = ms[mask].copy()
    if team_matches.empty or "match_date_utc" not in team_matches.columns:
        return pd.DataFrame()
    team_matches = team_matches.sort_values("match_date_utc", ascending=False)
    rows = []
    for _, row in team_matches.head(n).iterrows():
        h, a = row["home_score"], row["away_score"]
        if pd.isna(h) or pd.isna(a):
            continue
        h, a = int(h), int(a)
        is_home = row["home_team_name"] == team_name
        opponent = row["away_team_name"] if is_home else row["home_team_name"]
        gf = h if is_home else a
        ga = a if is_home else h
        if gf > ga:
            result = "W"
        elif gf == ga:
            result = "D"
        else:
            result = "L"
        rows.append({
            "date": row.get("match_date_utc"),
            "opponent": opponent,
            "home_away": "H" if is_home else "A",
            "score": f"{gf}–{ga}",
            "result": result,
            "xg_for": row.get("home_xg" if is_home else "away_xg"),
            "xg_against": row.get("away_xg" if is_home else "home_xg"),
            "match_id": row.get("match_id"),
        })
    return pd.DataFrame(rows)


def _team_home_away_summary_all_comps(team_name: str, season: str, comps_list: list) -> dict:
    """Home and away W-D-L, goals, xG aggregated across competitions. Keys: 'home', 'away'."""
    home_agg = {"W": 0, "D": 0, "L": 0, "matches": 0, "goals_for": 0, "goals_against": 0, "xg_for": 0.0, "xg_against": 0.0}
    away_agg = {"W": 0, "D": 0, "L": 0, "matches": 0, "goals_for": 0, "goals_against": 0, "xg_for": 0.0, "xg_against": 0.0}
    for c in comps_list:
        ha = _team_home_away_summary(team_name, season, c)
        for k in ["W", "D", "L", "matches", "goals_for", "goals_against"]:
            home_agg[k] += ha["home"].get(k, 0)
            away_agg[k] += ha["away"].get(k, 0)
        home_agg["xg_for"] += ha["home"].get("xg_for") or 0
        home_agg["xg_against"] += ha["home"].get("xg_against") or 0
        away_agg["xg_for"] += ha["away"].get("xg_for") or 0
        away_agg["xg_against"] += ha["away"].get("xg_against") or 0
    return {"home": home_agg, "away": away_agg}


def _team_home_away_summary(team_name: str, season: str, competition_slug: str) -> dict:
    """Home and away W-D-L, goals, xG for team in season/competition. Keys: 'home', 'away'."""
    ms = load_match_summary()
    mask = (
        ((ms["home_team_name"] == team_name) | (ms["away_team_name"] == team_name))
        & (ms["season"] == season)
        & (ms["competition_slug"] == competition_slug)
    )
    team_matches = ms[mask].copy()
    empty = {"W": 0, "D": 0, "L": 0, "matches": 0, "goals_for": 0, "goals_against": 0, "xg_for": 0.0, "xg_against": 0.0}

    def side_stats(subset: pd.DataFrame, is_home: bool) -> dict:
        if subset.empty:
            return empty.copy()
        w = d = l = goals_for = goals_against = 0
        xg_for = xg_against = 0.0
        for _, row in subset.iterrows():
            h, a = row["home_score"], row["away_score"]
            if pd.isna(h) or pd.isna(a):
                continue
            h, a = int(h), int(a)
            gf = h if is_home else a
            ga = a if is_home else h
            goals_for += gf
            goals_against += ga
            xf = row.get("home_xg") if is_home else row.get("away_xg")
            xa = row.get("away_xg") if is_home else row.get("home_xg")
            if pd.notna(xf):
                xg_for += float(xf)
            if pd.notna(xa):
                xg_against += float(xa)
            if gf > ga:
                w += 1
            elif gf == ga:
                d += 1
            else:
                l += 1
        return {"W": w, "D": d, "L": l, "matches": w + d + l, "goals_for": goals_for, "goals_against": goals_against, "xg_for": xg_for, "xg_against": xg_against}

    if team_matches.empty:
        return {"home": empty.copy(), "away": empty.copy()}
    home_m = team_matches[team_matches["home_team_name"] == team_name]
    away_m = team_matches[team_matches["away_team_name"] == team_name]
    return {"home": side_stats(home_m, True), "away": side_stats(away_m, False)}

# Pool and percentiles for tactical identity (used in briefing, radar, S&W)
pool = pd.DataFrame()
percentiles = {}
if tac_data is not None and not tactical_df.empty:
    if competition == ALL_COMPETITIONS and comps_list:
        pool = tactical_df[
            (tactical_df["season"] == season) &
            (tactical_df["competition_slug"].isin(comps_list))
        ]
    else:
        pool = tactical_df[
            (tactical_df["season"] == tac_data.get("season")) &
            (tactical_df["competition_slug"] == tac_data.get("competition_slug"))
        ]
    if pool.empty:
        pool = tactical_df
    percentiles = get_tactical_percentiles(tac_data, pool)

# Normalized 0–100 tactical values (same scale as radar); used for briefing and Playing Style so both match the radar
_radar_norm_vals = normalize_tactical_radar_to_100(tac_data, pool, TACTICAL_RADAR_INDICES) if (tac_data is not None and not pool.empty) else []
_tag_by_idx = {idx: label for idx, (_, label) in TACTICAL_TAGS.items()}

# Build strengths/weaknesses with cited metrics (for briefing and S&W section)
def _pct_label(idx: str) -> str:
    for k, label in TACTICAL_RADAR_INDICES:
        if k == idx:
            return label
    return idx.replace("_index", "").replace("_", " ").title()

# Strengths/weaknesses use league percentiles (not raw indices) so they match radar and Key Metrics
# All 7 radar axes covered; ordered by impact (extreme percentiles first)
_strengths_with_citation = []
_weaknesses_with_citation = []
if tac_data is not None:
    # Strengths: >75th percentile (aligned with radar)
    _sw = [
        (percentiles.get("possession_index", 50), "Excellent ball retention and control", "possession_index"),
        (percentiles.get("pressing_index", 50), "Aggressive high press disrupts opponents", "pressing_index"),
        (percentiles.get("chance_creation_index", 50), "Creates high-quality scoring opportunities", "chance_creation_index"),
        (percentiles.get("defensive_solidity", 50), "Strong defensive organization", "defensive_solidity"),
        (percentiles.get("directness_index", 50), "Direct in build-up", "directness_index"),
        (percentiles.get("aerial_index", 50), "Strong in the air", "aerial_index"),
        (percentiles.get("crossing_index", 50), "Effective from wide areas", "crossing_index"),
    ]
    for pct, text, idx in _sw:
        if pct > 75:
            _strengths_with_citation.append((text, idx))
    if team_data.get("xg_for_total", 0) > (team_data.get("goals_for", 0) or 0) * 1.1:
        _strengths_with_citation.append(("Creates more chances than goals suggest (unlucky)", None))
    _strengths_with_citation.sort(key=lambda x: percentiles.get(x[1], 0) if x[1] else 0, reverse=True)
    # Weaknesses: <25th percentile
    _ww = [
        (percentiles.get("defensive_solidity", 50), "Defensive vulnerabilities", "defensive_solidity"),
        (percentiles.get("pressing_index", 50), "Passive without ball - allows opponents to build", "pressing_index"),
        (percentiles.get("possession_index", 50), "Struggles to retain possession under pressure", "possession_index"),
        (percentiles.get("directness_index", 50), "Ineffective direct play", "directness_index"),
        (percentiles.get("aerial_index", 50), "Weak in the air", "aerial_index"),
        (percentiles.get("crossing_index", 50), "Limited threat from crosses", "crossing_index"),
        (percentiles.get("chance_creation_index", 50), "Struggles to create clear chances", "chance_creation_index"),
    ]
    for pct, text, idx in _ww:
        if pct < 25:
            _weaknesses_with_citation.append((text, idx))
    if (team_data.get("xg_against_total", 0) or 0) > (team_data.get("goals_against", 0) or 0) * 1.1:
        _weaknesses_with_citation.append(("Conceding fewer than xG suggests (lucky - may regress)", None))
    if (team_data.get("goals_against", 0) or 0) > (team_data.get("matches_total", 0) or 1) * 1.5:
        _weaknesses_with_citation.append(("High goals conceded rate", None))
    _weaknesses_with_citation.sort(key=lambda x: percentiles.get(x[1], 100) if x[1] else 100)

# Player-based badges: elite / poor starters (by rating vs league)
def _player_elite_poor_badges(
    player_df: pd.DataFrame,
    team_name: str,
    season: str,
    competition: str,
    comps_list: list,
    all_comp_sentinel: str,
    n_starters: int = 11,
    min_minutes_pool: int = 200,
    elite_pct: float = 85.0,
    poor_pct: float = 25.0,
) -> tuple:
    """Return (strength_badges, weakness_badges) from starter ratings vs league. Each badge is (text, None)."""
    if player_df.empty or "avg_rating" not in player_df.columns or "total_minutes" not in player_df.columns:
        return [], []
    if "team" not in player_df.columns or "season" not in player_df.columns:
        return [], []
    # League pool: same season and competition(s), minimum minutes
    if competition == all_comp_sentinel and comps_list:
        pool_df = player_df[
            (player_df["season"] == season) &
            (player_df["competition_slug"].isin(comps_list))
        ]
        if pool_df.empty:
            return [], []
        pool_agg = pool_df.groupby("player_name").agg({"avg_rating": "mean", "total_minutes": "sum"}).reset_index()
    else:
        pool_df = player_df[
            (player_df["season"] == season) &
            (player_df["competition_slug"] == competition)
        ]
        if pool_df.empty:
            return [], []
        pool_agg = pool_df.groupby("player_name").agg({"avg_rating": "mean", "total_minutes": "sum"}).reset_index()
    pool_agg = pool_agg[pool_agg["total_minutes"] >= min_minutes_pool]
    if len(pool_agg) < 5:
        return [], []
    pool_ratings = pool_agg["avg_rating"].dropna()
    if len(pool_ratings) < 3:
        return [], []
    # Team starters: same scope, top n_starters by minutes
    if competition == all_comp_sentinel and comps_list:
        team_df = player_df[
            (player_df["team"] == team_name) &
            (player_df["season"] == season) &
            (player_df["competition_slug"].isin(comps_list))
        ]
        team_agg = team_df.groupby("player_name").agg({"avg_rating": "mean", "total_minutes": "sum"}).reset_index()
    else:
        team_df = player_df[
            (player_df["team"] == team_name) &
            (player_df["season"] == season) &
            (player_df["competition_slug"] == competition)
        ]
        team_agg = team_df.groupby("player_name").agg({"avg_rating": "mean", "total_minutes": "sum"}).reset_index()
    team_agg = team_agg.sort_values("total_minutes", ascending=False).head(n_starters)
    if team_agg.empty:
        return [], []
    # Percentile of each starter's rating in league pool
    elite_count = poor_count = 0
    for _, row in team_agg.iterrows():
        r = row.get("avg_rating")
        if pd.isna(r):
            continue
        pct = (pool_ratings < float(r)).sum() / len(pool_ratings) * 100
        if pct >= elite_pct:
            elite_count += 1
        elif pct <= poor_pct:
            poor_count += 1
    strength_badges = []
    weakness_badges = []
    if elite_count >= 1:
        strength_badges.append((f"Presence of {elite_count} elite player{'s' if elite_count > 1 else ''} (top 15% by rating)", None))
    if poor_count >= 1:
        weakness_badges.append((f"Presence of {poor_count} poor starter{'s' if poor_count > 1 else ''} (bottom 25% by rating)", None))
    if elite_count == 0 and len(team_agg) >= 1:
        weakness_badges.append(("Absence of elite players among starters", None))
    return strength_badges, weakness_badges

_player_strength_badges, _player_weakness_badges = _player_elite_poor_badges(
    player_df, team_name, season, competition, comps_list, ALL_COMPETITIONS,
    n_starters=11, min_minutes_pool=200, elite_pct=85.0, poor_pct=25.0,
)
for _b in _player_strength_badges:
    _strengths_with_citation.append(_b)
for _b in _player_weakness_badges:
    _weaknesses_with_citation.append(_b)

# ---------------------------------------------------------------------------
# Briefing summary (one-block opponent profile headline)
# ---------------------------------------------------------------------------
if competition == ALL_COMPETITIONS and comps_list:
    _last5_brief = _team_last_matches_all_comps(team_name, season, comps_list, n=5)
    if _last5_brief.empty or "result" not in _last5_brief.columns:
        _form_info = {"form_string": "", "points": 0, "W": 0, "D": 0, "L": 0}
    else:
        w = int((_last5_brief["result"] == "W").sum())
        d = int((_last5_brief["result"] == "D").sum())
        l = int((_last5_brief["result"] == "L").sum())
        _form_info = {
            "form_string": " ".join(_last5_brief["result"].astype(str).tolist()),
            "points": 3 * w + d,
            "W": w, "D": d, "L": l,
        }
else:
    _form_info = _team_form(team_name, season, competition or "", n=5)
    _last5_brief = get_team_last_matches(team_name, season, competition or "", n=5) if competition else pd.DataFrame()

# Top 11 by minutes and formation inferred from position mix (used in briefing and formation viz)
_team_players_xi = []
if not player_df.empty and team_name and season:
    if competition == ALL_COMPETITIONS and comps_list:
        _tp_df = player_df[
            (player_df["team"] == team_name) &
            (player_df["season"] == season) &
            (player_df["competition_slug"].isin(comps_list))
        ]
        if "player_name" in _tp_df.columns and "total_minutes" in _tp_df.columns:
            _tp_agg = _tp_df.groupby("player_name").agg({"total_minutes": "sum", "player_position": "first", "avg_rating": "mean"}).reset_index()
            _tp_df = _tp_agg.sort_values("total_minutes", ascending=False).head(11)
    elif competition:
        _tp_df = player_df[
            (player_df["team"] == team_name) &
            (player_df["season"] == season) &
            (player_df["competition_slug"] == competition)
        ].sort_values("total_minutes", ascending=False).head(11)
    else:
        _tp_df = pd.DataFrame()
    if not _tp_df.empty and "player_name" in _tp_df.columns:
        for _, row in _tp_df.iterrows():
            _team_players_xi.append({
                "name": row["player_name"],
                "position": row["player_position"],
                "rating": float(row.get("avg_rating", 6.5) or 6.5),
                "role": row.get("tactical_role", "Standard"),
            })
_inferred_formation = infer_formation_from_players(_team_players_xi) if _team_players_xi else "4-3-3"
_brief_form = _inferred_formation

# Season-average formation from heatmaps (if available) — use ALL comps for team so we get heatmap when any match has data.
# Also compute whether we have any per-match heatmap data so we can show "Single match" even when season average fails.
_heatmap_season_result = None
_match_options_for_single = []  # list of (match_id, label, side) for matches with heatmap + lineups
_hm_path = _project_root / "data" / "processed" / "18_heatmap_points.parquet"
_ms = load_match_summary()
_hm_df = None
_team_matches_this_season = pd.DataFrame()
_tn_norm = str(team_name).strip().lower() if team_name else ""
if _hm_path.exists() and not _ms.empty and team_name and season:
    _hm_df = pd.read_parquet(_hm_path)
    _hm_match_ids = set(_hm_df["match_id"].astype(str).unique())
    # Case-insensitive team match so we find matches even with casing/spacing differences
    _home_norm = _ms["home_team_name"].fillna("").astype(str).str.strip().str.lower()
    _away_norm = _ms["away_team_name"].fillna("").astype(str).str.strip().str.lower()
    _team_in_ms = _ms[(_home_norm == _tn_norm) | (_away_norm == _tn_norm)]
    _team_matches_this_season = _team_in_ms[_team_in_ms["season"].astype(str) == str(season)]
    _team_match_ids_hm = _team_matches_this_season[
        _team_matches_this_season["match_id"].astype(str).isin(_hm_match_ids)
    ]
    # Build single-match options (matches where we have heatmap + lineups), most recent first so default selection is latest match
    _single_raw = []
    for _, _row in _team_match_ids_hm.iterrows():
        _mid = str(_row["match_id"])
        _match_dir = get_raw_match_dir_for_match_id(_mid)
        if _match_dir is None or not (_match_dir / "lineups.csv").exists():
            continue
        _date = _row.get("match_date_utc", _mid)
        try:
            _date_str = _date.strftime("%Y-%m-%d") if hasattr(_date, "strftime") else str(_date)[:10]
        except Exception:
            _date_str = str(_date)[:10] if _date else _mid
        _sort_ts = _date if hasattr(_date, "year") else _date_str  # keep datetime for sort, else YYYY-MM-DD string
        _home = _row.get("home_team_name", "Home")
        _away = _row.get("away_team_name", "Away")
        _is_home = str(_row["home_team_name"]).strip().lower() == _tn_norm
        _ha = "H" if _is_home else "A"
        _label = f"{_date_str} {_home} – {_away} ({_ha})"
        _side = "home" if _is_home else "away"
        _single_raw.append((_sort_ts, _mid, _label, _side))
    _single_raw.sort(key=lambda x: x[0], reverse=True)  # newest first
    _match_options_for_single = [(m, lb, s) for _, m, lb, s in _single_raw]
# Season average: use ALL comps this team plays this season (from match summary), not the user's competition filter
# Normalize season to str so session state (e.g. from Directory) never causes a type mismatch in the filter
_season_str = str(season).strip() if season is not None else ""
if _hm_df is not None and not player_df.empty and "player_id" in player_df.columns and formation_from_heatmaps_season is not None and _season_str:
    _comps_team_plays = _team_matches_this_season["competition_slug"].dropna().unique().tolist()
    if not _comps_team_plays:
        _comps_team_plays = comps_list if comps_list else ([competition] if competition and competition != ALL_COMPETITIONS else [])
    _tp_hm = player_df[
        (player_df["team"].fillna("").astype(str).str.strip().str.lower() == _tn_norm) &
        (player_df["season"].astype(str) == _season_str) &
        (player_df["competition_slug"].isin(_comps_team_plays))
    ]
    if not _tp_hm.empty:
        _tp_hm_agg = _tp_hm.groupby("player_id").agg(
            total_minutes=("total_minutes", "sum"),
            player_name=("player_name", "first"),
        ).reset_index()
        if "player_position" in _tp_hm.columns:
            _pos = _tp_hm.groupby("player_id")["player_position"].first()
            _tp_hm_agg["player_position"] = _tp_hm_agg["player_id"].map(_pos)
        else:
            _tp_hm_agg["player_position"] = None
        _heatmap_season_result = formation_from_heatmaps_season(
            team_name, _season_str, _comps_team_plays, _ms, _hm_df, _tp_hm_agg
        )
        if _heatmap_season_result is not None:
            _brief_form = _heatmap_season_result.formation
_has_heatmap_single_match = len(_match_options_for_single) > 0

# Playing styles from normalized 0–100 (same as radar), ordered by strength so e.g. Possession appears before Pressing when higher
_brief_styles = []
if _radar_norm_vals and tac_data is not None:
    NORM_THRESHOLD = 55
    for i, (idx, _) in enumerate(TACTICAL_RADAR_INDICES):
        if i >= len(_radar_norm_vals):
            break
        norm_val = _radar_norm_vals[i]
        label = _tag_by_idx.get(idx)
        if label and norm_val >= NORM_THRESHOLD:
            _brief_styles.append((norm_val, label))
    _brief_styles.sort(key=lambda x: -x[0])
    _brief_styles = [label for _, label in _brief_styles]
if tac_data is not None and tac_data.get("second_half_intensity", 0) >= 65:
    _brief_styles.append("Second-half team")
if tac_data is not None and tac_data.get("home_away_consistency", 0) >= 65:
    _brief_styles.append("Strong home/away consistency")
if not _brief_styles:
    _brief_styles = ["Balanced approach"]
_brief_strength_str = ", ".join([s[0] for s in _strengths_with_citation[:3]]) if _strengths_with_citation else "—"
_brief_weak_str = ", ".join([w[0] for w in _weaknesses_with_citation[:3]]) if _weaknesses_with_citation else "—"
_brief_form_str = _form_info.get("form_string", "") or "—"
_brief_pts = _form_info.get("points", 0)
# Color-code Last 5: W=green, D=gray, L=red
_form_colors = {"W": "#3FB950", "D": "#8B949E", "L": "#F85149"}
_brief_form_html = " ".join(
    f'<span style="color:{_form_colors.get(r, "#8B949E")};font-weight:700;">{r}</span>'
    for r in _brief_form_str.split() if r
) if _brief_form_str and _brief_form_str != "—" else "—"
st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#161B22 0%,#0D1117 100%);border:1px solid #30363D;border-radius:8px;padding:16px;margin-bottom:16px;">
        <div style="font-size:0.75rem;color:#8B949E;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.04em;">Briefing summary</div>
        <div style="font-size:0.9rem;color:#E6EDF3;line-height:1.65;">
            <div style="margin-bottom:6px;"><strong>Formation (est.):</strong> {_brief_form} &nbsp;·&nbsp; <strong>Style:</strong> {", ".join(_brief_styles)}</div>
            <div style="margin-bottom:6px;"><strong>Strengths:</strong> {_brief_strength_str}</div>
            <div style="margin-bottom:6px;"><strong>Weaknesses:</strong> {_brief_weak_str}</div>
            <div><strong>Last 5:</strong> {_brief_form_html} &nbsp;<span style="color:#8B949E;">({_brief_pts} pts)</span></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header Stats (incl. W-D-L, GD, per-game)
# ---------------------------------------------------------------------------
st.markdown("---")
if competition == ALL_COMPETITIONS and comps_list:
    wdl = _team_wdl_all_comps(team_name, season, comps_list)
else:
    wdl = get_team_wdl(team_name, season, competition) if competition else {}
matches_total = int(team_data.get("matches_total", 0)) or 1
goals_for = int(team_data.get("goals_for", 0))
goals_against = int(team_data.get("goals_against", 0))
gd = goals_for - goals_against
xgd = (team_data.get("xg_for_total", 0) or 0) - (team_data.get("xg_against_total", 0) or 0)
points = 3 * wdl.get("W", 0) + wdl.get("D", 0)

# Value color: gold default; green/red for GD and xGD
_gd_color = "#3FB950" if gd > 0 else ("#F85149" if gd < 0 else "#8B949E")
_xgd_color = "#3FB950" if xgd > 0 else ("#F85149" if xgd < 0 else "#8B949E")
cols = st.columns(7)
# (label, value, title tooltip, value color)
metrics = [
    ("Matches", f"{int(team_data.get('matches_total', 0))}", "Matches played", "#C9A840"),
    ("W-D-L", f"{wdl.get('W', 0)}-{wdl.get('D', 0)}-{wdl.get('L', 0)}" if wdl else "—", "Wins, draws, losses", "#C9A840"),
    ("Pts", f"{points}" if wdl else "—", "Points (3 for win, 1 for draw)", "#C9A840"),
    ("GD", f"{gd:+d}", "Goal difference (goals for − goals against)", _gd_color),
    ("xGD", f"{xgd:+.1f}", "Expected goal difference (xG for − xG against)", _xgd_color),
    ("G/game", f"{safe_divide(goals_for, matches_total, default=0):.1f}" if matches_total else "—", "Goals scored per game", "#C9A840"),
    ("xG/game", f"{safe_divide(team_data.get('xg_for_total', 0) or 0, matches_total, default=0):.1f}" if matches_total else "—", "Expected goals per game", "#C9A840"),
]

for col, (label, value, title, val_color) in zip(cols, metrics):
    with col:
        st.markdown(
            f"""
            <div title="{title}" style="text-align:center;padding:10px;background:#161B22;border-radius:6px;border:1px solid #30363D;cursor:help;">
                <div style="font-size:0.75rem;color:#8B949E;">{label}</div>
                <div style="font-size:1.2rem;font-weight:700;color:{val_color};">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Tactical Indices Radar (normalized 0–100 so chart renders correctly)
# ---------------------------------------------------------------------------
if tac_data is not None:
    st.markdown("---")
    st.markdown("<div class='section-header'>🎯 Tactical Identity</div>", unsafe_allow_html=True)

    radar_col, info_col = st.columns([2, 1])

    with radar_col:
        radar_vals = _radar_norm_vals
        labels = [l for _, l in TACTICAL_RADAR_INDICES]

        if radar_vals:
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=radar_vals + [radar_vals[0]],
                theta=labels + [labels[0]],
                fill="toself",
                fillcolor="rgba(201,168,64,0.2)",
                line=dict(color="#C9A840", width=2),
                name=team_name,
            ))
            fig.update_layout(
                polar=dict(
                    bgcolor="#0D1117",
                    radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor="#30363D"),
                    angularaxis=dict(gridcolor="#30363D", tickfont=dict(size=11, color="#E6EDF3")),
                ),
                paper_bgcolor="#0D1117",
                plot_bgcolor="#0D1117",
                font=dict(color="#E6EDF3"),
                margin=dict(l=44, r=44, t=40, b=40),
                height=400,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Values normalized to 0–100 within league/season pool. Higher = stronger tendency in that style."
            )

    with info_col:
        # Tactical style description: use same normalized 0–100 scale as radar, ordered by strength
        st.markdown("**Playing Style**")
        NORM_STYLE_THRESHOLD = 55
        style_items = []
        for i, (idx, _) in enumerate(TACTICAL_RADAR_INDICES):
            norm_val = radar_vals[i] if i < len(radar_vals) else 0.0
            label = _tag_by_idx.get(idx)
            if label and norm_val >= NORM_STYLE_THRESHOLD:
                style_items.append((norm_val, label))
        style_items.sort(key=lambda x: -x[0])
        dominant = [label for _, label in style_items]

        if dominant:
            for style in dominant:
                st.markdown(f"<span style='display:block;padding:6px 10px;background:#C9A84020;color:#C9A840;border-radius:4px;margin:4px 0;font-size:0.85rem;'>{style}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color:#8B949E;font-size:0.85rem;'>Balanced approach</span>", unsafe_allow_html=True)
        # When data: second-half intensity / home-away consistency (from 15)
        if tac_data.get("second_half_intensity", 0) >= 65:
            st.markdown("<span style='display:block;padding:6px 10px;background:#C9A84020;color:#C9A840;border-radius:4px;margin:4px 0;font-size:0.85rem;'>Second-half team</span>", unsafe_allow_html=True)
        if tac_data.get("home_away_consistency", 0) >= 65:
            st.markdown("<span style='display:block;padding:6px 10px;background:#C9A84020;color:#C9A840;border-radius:4px;margin:4px 0;font-size:0.85rem;'>Strong home/away consistency</span>", unsafe_allow_html=True)

        # Index breakdown: same 0–100 normalized scale as the radar (avoids raw-scale confusion)
        st.markdown("**Key Metrics** (0–100 vs league · percentile)")
        for i, (idx, label) in enumerate(TACTICAL_RADAR_INDICES):
            norm_val = radar_vals[i] if i < len(radar_vals) else 50.0
            if not pool.empty and idx in pool.columns:
                raw_val = tac_data.get(idx)
                pct_rank = (pool[idx] < raw_val).sum() / len(pool) * 100 if len(pool) > 0 and pd.notna(raw_val) else 50
                pct_str = f" · {int(pct_rank)}th in league"
            else:
                pct_str = ""
            bar_width = min(100, max(0, int(round(norm_val))))
            st.markdown(
                f"""
                <div style="margin:8px 0;">
                    <div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:2px;">
                        <span style="color:#8B949E;">{label}</span>
                        <span style="color:#F0F6FC;">{int(round(norm_val))}{pct_str}</span>
                    </div>
                    <div style="background:#21262D;border-radius:2px;height:4px;">
                        <div style="background:#C9A840;border-radius:2px;height:4px;width:{bar_width}%"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------------
    # Strengths & Weaknesses
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.markdown("<div class='section-header'>💪 Strengths & Weaknesses</div>", unsafe_allow_html=True)
    st.caption("Percentiles vs league (same season" + ("/competitions" if competition == ALL_COMPETITIONS else "/competition") + "). Strengths: >75th %ile · Weaknesses: <25th %ile.")

    strengths_col, weaknesses_col = st.columns(2)

    with strengths_col:
        st.markdown("**🔥 Strengths**")
        if _strengths_with_citation:
            for text, idx in _strengths_with_citation:
                cite = ""
                if idx and idx in percentiles:
                    pct = int(percentiles[idx])
                    lbl = _pct_label(idx)
                    cite = f" ({lbl} {format_percentile(pct)} %ile)"
                st.markdown(f"<div style='padding:8px;background:#3FB95020;border-left:3px solid #3FB950;margin:4px 0;border-radius:0 4px 4px 0;'><span style='color:#3FB950;font-size:0.9rem;'>{text}{cite}</span></div>", unsafe_allow_html=True)
        else:
            st.info("No clear standout strengths identified")

    with weaknesses_col:
        st.markdown("**⚠️ Weaknesses**")
        if _weaknesses_with_citation:
            for text, idx in _weaknesses_with_citation:
                cite = ""
                if idx and idx in percentiles:
                    pct = int(percentiles[idx])
                    lbl = _pct_label(idx)
                    cite = f" ({lbl} {format_percentile(pct)} %ile)"
                st.markdown(f"<div style='padding:8px;background:#F8514920;border-left:3px solid #F85149;margin:4px 0;border-radius:0 4px 4px 0;'><span style='color:#F85149;font-size:0.9rem;'>{text}{cite}</span></div>", unsafe_allow_html=True)
        else:
            st.info("No clear weaknesses identified")

# ---------------------------------------------------------------------------
# Recent Form (last 5 + form summary) — visual form bar + match cards
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📈 Recent Form</div>", unsafe_allow_html=True)
if competition:
    last5 = _last5_brief if (competition == ALL_COMPETITIONS and not _last5_brief.empty) else get_team_last_matches(team_name, season, competition, n=5)
    if not last5.empty:
        form_info = _form_info if competition == ALL_COMPETITIONS else _team_form(team_name, season, competition, n=5)
        form_str = form_info.get("form_string", "") or "—"
        pts = form_info.get("points", 0)
        xg_f = last5["xg_for"].sum() if "xg_for" in last5.columns else None
        xg_a = last5["xg_against"].sum() if "xg_against" in last5.columns else None
        _form_colors = {"W": "#3FB950", "D": "#C9A840", "L": "#F85149"}
        form_letters = form_str.split() if form_str and form_str != "—" else []
        form_pills = "".join(
            f"<span style='display:inline-block;width:28px;height:28px;line-height:26px;text-align:center;border-radius:50%;background:{_form_colors.get(r, '#8B949E')}22;color:{_form_colors.get(r, '#8B949E')};font-weight:700;font-size:0.8rem;margin-right:4px;' title='{r}'>{r}</span>"
            for r in form_letters
        )
        xg_bar_html = ""
        if xg_f is not None and pd.notna(xg_f) and xg_a is not None and pd.notna(xg_a) and (xg_f + xg_a) > 0:
            total_xg = float(xg_f) + float(xg_a)
            pct_f = float(xg_f) / total_xg * 100
            xg_bar_html = (
                f"<div style='margin-top:8px;margin-bottom:12px;'>"
                f"<div style='font-size:0.75rem;color:#8B949E;margin-bottom:4px;'>xG last 5</div>"
                f"<div style='display:flex;height:8px;border-radius:4px;overflow:hidden;background:#21262D;'>"
                f"<div style='width:{pct_f:.1f}%;background:#3FB950;'></div>"
                f"<div style='width:{100-pct_f:.1f}%;background:#F85149;'></div>"
                f"</div>"
                f"<div style='display:flex;justify-content:space-between;font-size:0.7rem;color:#8B949E;margin-top:2px;'>"
                f"<span style='color:#3FB950;'>{xg_f:.1f} for</span><span style='color:#F85149;'>{xg_a:.1f} against</span>"
                f"</div></div>"
            )
        st.markdown(
            f"<div style='display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:4px;'>"
            f"<div style='display:flex;align-items:center;'>{form_pills}</div>"
            f"<span style='color:#8B949E;font-size:0.9rem;'>{pts} pts</span>"
            f"</div>"
            f"{xg_bar_html}",
            unsafe_allow_html=True,
        )
        for _, m in last5.iterrows():
            res = m.get("result", "?")
            res_color = _form_colors.get(res, "#8B949E")
            ha = m.get("home_away", "")
            score = m.get("score", "")
            opp = m.get("opponent", "")
            xg_for = m.get("xg_for")
            xg_ag = m.get("xg_against")
            has_xg = "xg_for" in m and pd.notna(xg_for)
            xg_str = f"{float(xg_for):.1f}-{float(xg_ag):.1f}" if has_xg and pd.notna(xg_ag) else ""
            xg_span = f"<span style='color:#8B949E;font-size:0.75rem;'>(xG {xg_str})</span>" if xg_str else ""
            st.markdown(
                f"<div style='display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:10px 12px;margin:6px 0;background:#161B22;border:1px solid #30363D;border-radius:8px;border-left:4px solid {res_color};'>"
                f"<span style='width:26px;height:26px;line-height:24px;text-align:center;border-radius:50%;background:{res_color}22;color:{res_color};font-weight:700;font-size:0.75rem;flex-shrink:0;'>{res}</span>"
                f"<span style='padding:2px 8px;background:#21262D;border-radius:4px;font-weight:600;color:#F0F6FC;font-size:0.9rem;'>{score}</span>"
                f"<span style='color:#8B949E;font-size:0.8rem;'>{ha}</span>"
                f"<span style='color:#E6EDF3;font-size:0.9rem;'>vs {opp}</span>"
                f"{xg_span}"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.caption("Last 5 matches" + (" (all competitions)" if competition == ALL_COMPETITIONS else " in this competition") + ". xG when available.")
    else:
        st.caption("No match history available for this season" + ("." if competition == ALL_COMPETITIONS else "/competition."))
else:
    st.caption("Select a competition to see recent form.")

# ---------------------------------------------------------------------------
# Home vs Away — visual cards with W-D-L bars and goal/xG bars
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🏠 Home vs Away</div>", unsafe_allow_html=True)
if competition:
    ha = _team_home_away_summary_all_comps(team_name, season, comps_list) if competition == ALL_COMPETITIONS and comps_list else _team_home_away_summary(team_name, season, competition)
    h, a = ha["home"], ha["away"]
    hm, am = h["matches"] or 1, a["matches"] or 1
    _ha_colors = {"W": "#3FB950", "D": "#C9A840", "L": "#F85149"}

    def _home_away_card(label: str, data: dict, n_matches: int) -> str:
        w, d, l = data.get("W", 0), data.get("D", 0), data.get("L", 0)
        total = n_matches or 1
        wp, dp, lp = (w / total * 100, d / total * 100, l / total * 100)
        goals_f, goals_a = data.get("goals_for", 0), data.get("goals_against", 0)
        goals_t = goals_f + goals_a or 1
        goals_f_pct = goals_f / goals_t * 100
        xg_f = data.get("xg_for")
        xg_a = data.get("xg_against")
        has_xg = xg_f is not None and pd.notna(xg_f) and xg_a is not None and pd.notna(xg_a)
        xg_bar = ""
        if has_xg:
            xg_t = float(xg_f) + float(xg_a) or 1
            xg_f_pct = float(xg_f) / xg_t * 100
            xg_bar = (
                f"<div style='margin-top:10px;'><div style='font-size:0.7rem;color:#8B949E;margin-bottom:2px;'>xG</div>"
                f"<div style='height:6px;border-radius:3px;overflow:hidden;background:#21262D;display:flex;'>"
                f"<div style='width:{xg_f_pct:.1f}%;background:#3FB950;'></div><div style='width:{100-xg_f_pct:.1f}%;background:#F85149;'></div>"
                f"</div><div style='display:flex;justify-content:space-between;font-size:0.7rem;margin-top:2px;'>"
                f"<span style='color:#3FB950;'>{float(xg_f):.1f}</span><span style='color:#F85149;'>{float(xg_a):.1f}</span></div></div>"
            )
        xg_game = ""
        if n_matches > 0 and has_xg:
            xg_game = f"<div style='font-size:0.7rem;color:#8B949E;margin-top:6px;'>xG/game: <span style='color:#3FB950;'>{(float(xg_f)/n_matches):.1f}</span> · <span style='color:#F85149;'>{(float(xg_a)/n_matches):.1f}</span></div>"
        return (
            f"<div style='flex:1;min-width:0;background:#161B22;border:1px solid #30363D;border-radius:10px;padding:14px;'>"
            f"<div style='font-weight:700;font-size:1rem;color:#E6EDF3;margin-bottom:10px;'>{label}</div>"
            f"<div style='font-size:0.7rem;color:#8B949E;margin-bottom:4px;'>W-D-L</div>"
            f"<div style='height:10px;border-radius:5px;overflow:hidden;background:#21262D;display:flex;'>"
            f"<div style='width:{wp:.1f}%;background:#3FB950;' title='W'></div>"
            f"<div style='width:{dp:.1f}%;background:#C9A840;' title='D'></div>"
            f"<div style='width:{lp:.1f}%;background:#F85149;' title='L'></div>"
            f"</div>"
            f"<div style='font-size:0.8rem;color:#8B949E;margin-top:4px;'>{w}-{d}-{l} ({n_matches} matches)</div>"
            f"<div style='margin-top:10px;'><div style='font-size:0.7rem;color:#8B949E;margin-bottom:2px;'>Goals</div>"
            f"<div style='height:6px;border-radius:3px;overflow:hidden;background:#21262D;display:flex;'>"
            f"<div style='width:{goals_f_pct:.1f}%;background:#3FB950;'></div><div style='width:{100-goals_f_pct:.1f}%;background:#F85149;'></div>"
            f"</div><div style='display:flex;justify-content:space-between;font-size:0.7rem;margin-top:2px;'>"
            f"<span style='color:#3FB950;'>{goals_f} for</span><span style='color:#F85149;'>{goals_a} against</span></div></div>"
            f"{xg_bar}{xg_game}</div>"
        )

    st.markdown(
        "<div style='display:flex;gap:16px;flex-wrap:wrap;'>"
        + _home_away_card("Home", h, hm)
        + _home_away_card("Away", a, am)
        + "</div>",
        unsafe_allow_html=True,
    )
else:
    st.caption("Select a competition to see home/away split.")

# ---------------------------------------------------------------------------
# Squad: All players (table) — right after form/context so you know WHO they are
# ---------------------------------------------------------------------------
if not player_df.empty:
    if competition == ALL_COMPETITIONS and comps_list:
        _squad_raw = player_df[
            (player_df["team"] == team_name) &
            (player_df["season"] == season) &
            (player_df["competition_slug"].isin(comps_list))
        ].copy()
        # Aggregate by player: sum numeric stats, keep first for position/age
        if "player_name" in _squad_raw.columns and len(_squad_raw) > 0:
            num_cols = [c for c in _squad_raw.select_dtypes(include=[np.number]).columns if c != "player_name"]
            other_cols = [c for c in _squad_raw.columns if c not in num_cols and c != "player_name"]
            agg_dict = {c: "sum" for c in num_cols}
            agg_dict.update({c: "first" for c in other_cols})
            squad_table_df = _squad_raw.groupby("player_name", as_index=False).agg(agg_dict)
        else:
            squad_table_df = _squad_raw
    else:
        squad_table_df = player_df[
            (player_df["team"] == team_name) &
            (player_df["season"] == season) &
            (player_df["competition_slug"] == competition)
        ].copy()

    if not squad_table_df.empty:
        st.markdown("---")
        st.markdown("<div class='section-header'>📋 Squad — All players & statistics</div>", unsafe_allow_html=True)
        st.caption("Full squad for this season" + (" (all competitions)" if competition == ALL_COMPETITIONS else "/competition") + ". Sort by clicking column headers.")

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
        table_df = squad_table_df[existing].copy()

        if "total_minutes" in table_df.columns:
            table_df = table_df.sort_values("total_minutes", ascending=False)

        col_rename = {
            "player_name": "Player",
            "player_position": "Pos",
            "age_at_season_start": "Age",
            "appearances": "Apps",
            "total_minutes": "Mins",
            "avg_rating": "Rating",
            "goals": "Goals",
            "assists": "Assists",
            "goals_per90": "G/90",
            "expectedGoals_per90": "xG/90",
            "expectedAssists_per90": "xA/90",
            "keyPass_per90": "KP/90",
            "bigChanceCreated_per90": "BCC/90",
            "totalTackle_per90": "Tkl/90",
            "interceptionWon_per90": "Int/90",
            "duelWon_per90": "DW/90",
            "aerialWon_per90": "Air/90",
            "ballRecovery_per90": "Rec/90",
            "totalPass_per90": "Pass/90",
            "pass_accuracy_pct": "Pass%",
            "progressiveBallCarriesCount_per90": "ProgC/90",
            "saves_per90": "Sv/90",
            "goalsPrevented_per90": "GkPrev/90",
        }
        table_df = table_df.rename(columns={k: v for k, v in col_rename.items() if k in table_df.columns})

        # Format: Age as integer (real age at season start); counts (Apps, Mins, Goals, Assists) as int
        if "Age" in table_df.columns:
            age_ser = pd.to_numeric(table_df["Age"], errors="coerce").round(0)
            try:
                table_df["Age"] = age_ser.astype("Int64")
            except (TypeError, ValueError):
                table_df["Age"] = age_ser.where(age_ser.notna(), np.nan).astype(float)
        for count_col in ["Mins", "Apps", "Goals", "Assists"]:
            if count_col in table_df.columns:
                table_df[count_col] = table_df[count_col].fillna(0).astype(int)
        # Rating: 0–10 (Sofascore scale; normalized in pipeline when building 03)
        if "Rating" in table_df.columns:
            table_df["Rating"] = pd.to_numeric(table_df["Rating"], errors="coerce").round(1)
        for col in table_df.columns:
            if col in ("Player", "Pos", "Age", "Mins", "Apps", "Goals", "Assists"):
                continue
            if table_df[col].dtype in (np.floating, "float64"):
                table_df[col] = table_df[col].round(2)

        st.dataframe(table_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Formation Analysis: heatmap-derived (season average) when available, else position-based
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>⚽ Formation Analysis</div>", unsafe_allow_html=True)
formation_col, squad_col = st.columns([2, 1])

with formation_col:
    if _heatmap_season_result:
        # Season average available: offer Season average | Single match
        _view_hm = st.radio(
            "View",
            options=["Season average (from heatmaps)", "Single match"],
            key="formation_heatmap_view",
            horizontal=True,
            label_visibility="collapsed",
        )
        _show_single_match = _view_hm == "Single match"
        if _show_single_match and _match_options_for_single:
            _sel_label = st.selectbox("Choose a match", options=[lb for _, lb, _ in _match_options_for_single], key="formation_single_match_select")
            _sel_mid, _, _sel_side = next((mid, lb, s) for mid, lb, s in _match_options_for_single if lb == _sel_label)
            _lineups_sel = load_lineups_for_match(get_raw_match_dir_for_match_id(_sel_mid))
            if _lineups_sel is not None and not _lineups_sel.empty and _hm_df is not None:
                _res = formation_from_heatmaps(_sel_mid, _sel_side, _lineups_sel, _hm_df)
                if _res:
                    _fm, _pl = formation_from_heatmaps_to_render_args(_res)
                    render_formation_pitch_from_heatmaps(_fm, _pl, width=700, height=550, title_suffix="(from heatmaps)")
                    st.caption("Formation inferred from this match's heatmap positions.")
                else:
                    st.info("Could not infer formation for this match.")
            else:
                st.warning("Lineups not found.")
        elif not _show_single_match:
            _formation, _players = formation_from_heatmaps_to_render_args(_heatmap_season_result)
            render_formation_pitch_from_heatmaps(
                _formation,
                _players,
                width=700,
                height=550,
                title_suffix="(season average, from heatmaps)",
            )
            st.caption(
                f"**{_heatmap_season_result.formation}** inferred from heatmap data (season average). "
                "Positions = median of touch locations across all matches in scope."
            )
        else:
            st.info("No matches with heatmap data and raw lineups.")
    elif _has_heatmap_single_match and _match_options_for_single and _hm_df is not None:
        # Per-game heatmap data exists but season average failed (e.g. < 11 players with heatmaps across season) — show single-match only
        _sel_label = st.selectbox("Choose a match (formation from heatmaps)", options=[lb for _, lb, _ in _match_options_for_single], key="formation_single_match_only")
        _sel_mid, _, _sel_side = next((mid, lb, s) for mid, lb, s in _match_options_for_single if lb == _sel_label)
        _lineups_sel = load_lineups_for_match(get_raw_match_dir_for_match_id(_sel_mid))
        if _lineups_sel is not None and not _lineups_sel.empty:
            _res = formation_from_heatmaps(_sel_mid, _sel_side, _lineups_sel, _hm_df)
            if _res:
                _fm, _pl = formation_from_heatmaps_to_render_args(_res)
                render_formation_pitch_from_heatmaps(_fm, _pl, width=700, height=550, title_suffix="(from heatmaps)")
                st.caption("Formation inferred from this match's heatmap positions. Season-average formation is not available for this team (e.g. need 11+ players with heatmap data across the season).")
            else:
                render_formation_pitch(formation=_inferred_formation, players=_team_players_xi, width=700, height=550) if _team_players_xi else st.info("Could not infer formation for this match.")
                st.caption("Heatmap data exists for this match but formation could not be inferred. Showing position-based formation.")
        else:
            st.warning("Lineups not found for selected match.")
    elif _team_players_xi:
        # No heatmap-derived formation: position-based only
        render_formation_pitch(
            formation=_inferred_formation,
            players=_team_players_xi,
            width=700,
            height=550
        )
        st.caption(
            f"**Formation {_inferred_formation}** inferred from this season's most-used XI (top 11 by minutes). "
            "Players are placed by position. Heatmap-derived formation not available for this team."
        )
    else:
        st.info("Player data not available for formation display")

with squad_col:
    st.markdown("**Squad Composition**")
    if not player_df.empty:
        if competition == ALL_COMPETITIONS and comps_list:
            team_players_full = player_df[
                (player_df["team"] == team_name) &
                (player_df["season"] == season) &
                (player_df["competition_slug"].isin(comps_list))
            ]
        else:
            team_players_full = player_df[
                (player_df["team"] == team_name) &
                (player_df["season"] == season) &
                (player_df["competition_slug"] == competition)
            ]
        if not team_players_full.empty:
            if "age_at_season_start" in team_players_full.columns or "age_band" in team_players_full.columns:
                age_col = "age_band" if "age_band" in team_players_full.columns else "age_at_season_start"
                if age_col == "age_at_season_start":
                    age = team_players_full["age_at_season_start"].dropna()
                    bands = pd.cut(age, bins=[0, 21, 24, 27, 30, 100], labels=["≤21", "22–24", "25–27", "28–30", "31+"])
                    band_counts = bands.value_counts()
                else:
                    band_counts = team_players_full[age_col].value_counts()
                # Show age bands in logical order (youngest to oldest, then Unknown if present)
                age_order = [b for b in AGE_BANDS if b != "Unknown"] + ["Unknown"]
                st.markdown("**Age profile**")
                for band in age_order:
                    count = band_counts.get(band, 0)
                    if count == 0:
                        continue
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 0;'><span style='color:#8B949E;'>{band}</span><span style='color:#F0F6FC;'>{count}</span></div>", unsafe_allow_html=True)
                st.divider()
            pos_dist = team_players_full.groupby("player_position")["player_id"].nunique()
            # Show positions in formation order: G, D, M, F
            position_display_order = ("G", "D", "M", "F")
            st.markdown("**By Position**")
            for pos in position_display_order:
                if pos not in pos_dist:
                    continue
                count = pos_dist[pos]
                pos_name = POSITION_NAMES.get(pos, pos)
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #30363D;'><span style='color:#8B949E;'>{pos_name}</span><span style='color:#F0F6FC;font-weight:500;'>{count}</span></div>",
                    unsafe_allow_html=True
                )

# ---------------------------------------------------------------------------
# Tactical Evolution (if historical data available; single-competition only)
# ---------------------------------------------------------------------------
if not team_stats.empty and competition != ALL_COMPETITIONS:
    historical_data = team_stats[
        (team_stats["team_name"] == team_name) &
        (team_stats["competition_slug"] == competition)
    ].sort_values("season")
else:
    historical_data = pd.DataFrame()

if len(historical_data) > 1 and tac_data is not None:
    st.markdown("---")
    st.markdown("<div class='section-header'>📈 Tactical Evolution</div>", unsafe_allow_html=True)

    style_cols = [c for c in tactical_df.columns if 'index' in c or c == 'defensive_solidity']
    if style_cols:
        # Merge historical team stats with tactical data
        merged = historical_data.merge(
            tactical_df[tactical_df['team_name'] == team_name][['season', 'competition_slug'] + style_cols],
            on=['season', 'competition_slug'],
            how='left'
        )

        if not merged[style_cols[0]].isna().all():
            render_tactical_style_evolution(
                merged,
                style_cols[:5],  # Limit to 5 for readability
                team_name
            )

# ---------------------------------------------------------------------------
# Build profile Markdown for download
# ---------------------------------------------------------------------------
_profile_md_lines = [
    f"# Tactical Profile: {team_name}",
    f"{'All competitions' if competition == ALL_COMPETITIONS else (COMP_FLAGS.get(competition, '') + ' ' + COMP_NAMES.get(competition, competition))} · {season}",
    "",
    "## Summary",
    f"- **Matches:** {int(team_data.get('matches_total', 0))}",
    f"- **W-D-L:** {wdl.get('W', 0)}-{wdl.get('D', 0)}-{wdl.get('L', 0)} · **Pts:** {points} · **GD:** {gd:+d} · **xGD:** {xgd:+.1f}",
    f"- **Formation (from XI):** {_brief_form}",
    f"- **Style:** {', '.join(_brief_styles)}",
    f"- **Last 5:** {_brief_form_str} ({_brief_pts} pts)",
    "",
]
if _strengths_with_citation:
    _profile_md_lines.append("## Strengths")
    for text, idx in _strengths_with_citation:
        cite = f" ({_pct_label(idx)} {format_percentile(int(percentiles.get(idx, 50)))} %ile)" if idx and idx in percentiles else ""
        _profile_md_lines.append(f"- {text}{cite}")
    _profile_md_lines.append("")
if _weaknesses_with_citation:
    _profile_md_lines.append("## Weaknesses")
    for text, idx in _weaknesses_with_citation:
        cite = f" ({_pct_label(idx)} {format_percentile(int(percentiles.get(idx, 50)))} %ile)" if idx and idx in percentiles else ""
        _profile_md_lines.append(f"- {text}{cite}")
    _profile_md_lines.append("")
if competition:
    ha_dl = _team_home_away_summary_all_comps(team_name, season, comps_list) if (competition == ALL_COMPETITIONS and comps_list) else _team_home_away_summary(team_name, season, competition)
    _profile_md_lines.append("## Home vs Away")
    _profile_md_lines.append(f"- **Home:** W-D-L {ha_dl['home']['W']}-{ha_dl['home']['D']}-{ha_dl['home']['L']} · Goals {ha_dl['home']['goals_for']}-{ha_dl['home']['goals_against']}")
    _profile_md_lines.append(f"- **Away:** W-D-L {ha_dl['away']['W']}-{ha_dl['away']['D']}-{ha_dl['away']['L']} · Goals {ha_dl['away']['goals_for']}-{ha_dl['away']['goals_against']}")
    _profile_md_lines.append("")
_profile_md = "\n".join(_profile_md_lines)

# Footer actions
st.markdown("---")
confirm_clear = st.session_state.get("confirm_clear", False)
if confirm_clear:
    st.warning("Are you sure you want to clear selection? You will return to the team selector.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, clear selection", key="confirm_clear_yes"):
            st.session_state.selected_team = None
            st.session_state["confirm_clear"] = False
            st.rerun()
    with c2:
        if st.button("Cancel", key="confirm_clear_no"):
            st.session_state["confirm_clear"] = False
            st.rerun()
else:
    st.markdown("**Download & actions**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.download_button(
            "📄 Download opponent profile (Markdown)",
            data=_profile_md,
            file_name=f"tactical_profile_{team_name.replace(' ', '_')}_{season}.md",
            mime="text/markdown",
            key="profile_download_md",
            use_container_width=True,
        )
    with col2:
        if st.button("← Back to Directory", use_container_width=True):
            st.switch_page("pages/9_🏟️_Team_Directory.py")
    with col3:
        if st.button("⚔️ Opponent Prep", use_container_width=True):
            st.session_state["opponent_team"] = team_info
            st.switch_page("pages/11_⚔️_Opponent_Prep.py")
        st.caption("Use this profile as the opponent in Opponent Prep to get matchup analysis and full report.")
    with col4:
        if st.button("🗑️ Clear Selection", use_container_width=True, key="clear_sel_btn"):
            st.session_state["confirm_clear"] = True
            st.rerun()
