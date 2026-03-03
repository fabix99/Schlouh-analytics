"""Scouts Dashboard — Player Profile.

Deep scouting report with position-aware sections, radar chart,
percentile toggle, badges, and form visualization.

Structure: player selector, hero, season picker, recommendation, narrative,
metrics, badges, radar, position sections, big game, match log, form, similar, export.
"""

import logging
import sys
import pathlib
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)

_project_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from dashboard.utils.data import (
    load_enriched_season_stats,
    load_rolling_form,
    load_player_consistency,
    load_opponent_context_summary,
    load_scouting_profiles,
    load_career_stats,
    load_player_progression,
    get_similar_players,
    get_player_match_log,
    get_player_heatmap,
    load_match_summary,
    load_team_season_stats,
    load_tactical_profiles,
)
from dashboard.utils.recommendation import build_player_narrative_blobs
from dashboard.utils.percentiles import get_percentile_zscore
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, POSITION_NAMES,
    RADAR_STATS_BY_POSITION, PLAYER_COLORS,
)
from dashboard.utils.scope import CURRENT_SEASON, filter_to_default_scope
from dashboard.utils.validation import safe_divide
from dashboard.utils.styles import TOKENS
from dashboard.utils.charts import radar_chart
from dashboard.utils.badges import calculate_badges, format_badge_for_display
from dashboard.utils.fit_score import calculate_fit_score
from dashboard.utils.sidebar import render_sidebar
from dashboard.scouts.layout import load_shortlist_from_file, save_shortlist_to_file
from dashboard.scouts.compare_state import load_scouts_compare_list, save_scouts_compare_list


def _get_player_heatmap_season(player_id: int, season: str, competition_slug: Optional[str] = None) -> Optional[dict]:
    """Season heatmap points (inlined so Profile does not depend on data.get_player_heatmap_season)."""
    try:
        path = _project_root / "data" / "processed" / "18_heatmap_points.parquet"
        if not path.exists():
            return None
        df_hm = pd.read_parquet(path)
        if df_hm.empty or "match_id" not in df_hm.columns or "player_id" not in df_hm.columns:
            return None
        ms = load_match_summary()
        if ms.empty or "match_id" not in ms.columns or "season" not in ms.columns:
            return None
        season_str = str(season)
        mask = ms["season"].astype(str) == season_str
        if competition_slug and str(competition_slug) != "All" and "competition_slug" in ms.columns:
            mask &= ms["competition_slug"].astype(str) == str(competition_slug)
        match_ids = set(ms.loc[mask, "match_id"].astype(str).unique())
        if not match_ids:
            return None
        sub = df_hm[
            (df_hm["player_id"] == player_id)
            & (df_hm["match_id"].astype(str).isin(match_ids))
        ]
        if sub.empty or "x" not in sub.columns or "y" not in sub.columns:
            return None
        return {"heatmap": sub[["x", "y"]].to_dict("records")}
    except Exception:
        return None


# Local pitch heatmap (no dependency on charts.pitch_heatmap_figure so it always runs)
_PITCH_COLOR = "#2E7D32"
_LINE_COLOR = "rgba(255,255,255,0.9)"
_FIG_BG = "#0D1117"
_TEXT_COLOR = "#E6EDF3"


def _add_pitch_shapes_to_fig(fig: go.Figure) -> None:
    """Add football pitch lines (Opta 0–100). x = length (goals left/right), y = width."""
    fig.add_shape(type="rect", x0=0, y0=0, x1=100, y1=100, line=dict(color=_LINE_COLOR, width=2), fillcolor=_PITCH_COLOR, layer="below")
    fig.add_shape(type="line", x0=50, y0=0, x1=50, y1=100, line=dict(color=_LINE_COLOR, width=2), layer="above")
    fig.add_shape(type="circle", x0=40, y0=40, x1=60, y1=60, line=dict(color=_LINE_COLOR, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="circle", x0=49.4, y0=49.4, x1=50.6, y1=50.6, line=dict(color=_LINE_COLOR, width=1), fillcolor=_LINE_COLOR, layer="above")
    fig.add_shape(type="rect", x0=0, y0=20, x1=15, y1=80, line=dict(color=_LINE_COLOR, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="rect", x0=85, y0=20, x1=100, y1=80, line=dict(color=_LINE_COLOR, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="rect", x0=0, y0=37, x1=5, y1=63, line=dict(color=_LINE_COLOR, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="rect", x0=95, y0=37, x1=100, y1=63, line=dict(color=_LINE_COLOR, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="path", path="M 41 15 A 9 9 0 0 0 59 15", line=dict(color=_LINE_COLOR, width=2), layer="above")
    fig.add_shape(type="path", path="M 41 85 A 9 9 0 0 1 59 85", line=dict(color=_LINE_COLOR, width=2), layer="above")
    for path in ["M 0 2 A 2 2 0 0 1 2 0", "M 98 0 A 2 2 0 0 1 100 2", "M 0 98 A 2 2 0 0 1 2 100", "M 98 100 A 2 2 0 0 1 100 98"]:
        fig.add_shape(type="path", path=path, line=dict(color=_LINE_COLOR, width=2), layer="above")
    fig.add_shape(type="circle", x0=10.2, y0=49.2, x1=11.8, y1=50.8, line=dict(color=_LINE_COLOR, width=1), fillcolor=_LINE_COLOR, layer="above")
    fig.add_shape(type="circle", x0=88.2, y0=49.2, x1=89.8, y1=50.8, line=dict(color=_LINE_COLOR, width=1), fillcolor=_LINE_COLOR, layer="above")


def _profile_pitch_heatmap(x: pd.Series, y: pd.Series) -> go.Figure:
    """Build pitch + density heatmap. x = length (goals L/R), y = width; aspect 105:68."""
    x_arr = np.asarray(x, dtype=float).ravel()
    y_arr = np.asarray(y, dtype=float).ravel()
    mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr, y_arr = x_arr[mask], y_arr[mask]
    fig = go.Figure()
    layout_common = dict(
        paper_bgcolor=_FIG_BG,
        plot_bgcolor=_PITCH_COLOR,
        font=dict(color=_TEXT_COLOR),
        xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, showticklabels=False, constrain="domain"),
        yaxis=dict(range=[0, 100], showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=68 / 105),
        height=420,
        margin=dict(l=44, r=44, t=24, b=44),
        showlegend=False,
    )
    if x_arr.size == 0:
        fig.update_layout(**layout_common)
        _add_pitch_shapes_to_fig(fig)
        return fig
    fig.add_trace(go.Histogram2d(
        x=x_arr, y=y_arr,
        nbinsx=45, nbinsy=35,
        colorscale=[
            [0.0, _PITCH_COLOR],   # 0 touches = pitch green (blends with grass)
            [0.2, "#7CB342"],      # light green
            [0.4, "#FDD835"],      # yellow
            [0.7, "#FB8C00"],      # orange
            [1.0, "#E53935"],      # red (high activity)
        ],
        zsmooth="best",
        showscale=True,
        colorbar=dict(title="Touches", thickness=14, len=0.5, bgcolor=_FIG_BG, tickfont=dict(color=_TEXT_COLOR), title_font=dict(color=_TEXT_COLOR)),
        hovertemplate="x: %{x:.0f}<br>y: %{y:.0f}<br>Count: %{z}<extra></extra>",
    ))
    _add_pitch_shapes_to_fig(fig)
    fig.update_layout(**layout_common)
    return fig


def _get_team_data_for_fit_aggregated(
    team_name: str,
    season: str,
    df_all: pd.DataFrame,
    team_stats_df: pd.DataFrame,
    tactical_df: pd.DataFrame,
) -> Tuple[pd.Series, Optional[pd.Series]]:
    """Team data for fit score: current season aggregated across all competitions. Returns (team_row, tactical_row or None)."""
    team_key = "team_name" if "team_name" in team_stats_df.columns else "team"
    tr = team_stats_df[
        (team_stats_df[team_key].astype(str) == str(team_name))
        & (team_stats_df["season"].astype(str) == str(season))
    ]
    if tr.empty:
        team_row = pd.Series(dtype=object)
    else:
        id_cols = [c for c in ["team_name", "team", "season"] if c in tr.columns]
        numeric = [c for c in tr.columns if c not in id_cols and pd.api.types.is_numeric_dtype(tr[c])]
        agg = {c: tr[c].iloc[0] for c in id_cols}
        for c in numeric:
            agg[c] = tr[c].mean()
        team_row = pd.Series(agg)
    subset = df_all[
        (df_all["team"].astype(str) == str(team_name))
        & (df_all["season"].astype(str) == str(season))
    ]
    pos_stats = [
        "goals_per90", "expectedGoals_per90", "keyPass_per90", "expectedAssists_per90",
        "pass_accuracy", "duelWon_per90", "interceptionWon_per90", "totalTackle_per90",
        "aerialWon_per90", "saves_per90", "goalsPrevented_per90",
    ]
    for pos in ["F", "M", "D", "G"]:
        sub = subset[subset["player_position"] == pos]
        if sub.empty:
            continue
        for stat in pos_stats:
            if stat not in sub.columns:
                continue
            team_row[f"{pos}_{stat}_avg"] = sub[stat].mean()
    tactical_row = None
    if not tactical_df.empty:
        tc = "team_name" if "team_name" in tactical_df.columns else "team"
        tac = tactical_df[
            (tactical_df[tc].astype(str) == str(team_name))
            & (tactical_df["season"].astype(str) == str(season))
        ]
        if not tac.empty:
            tactical_row = tac.select_dtypes(include=[np.number]).mean()
    return (team_row, tactical_row)


# Page config
st.set_page_config(
    page_title="Player Profile · Scouts",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar()

# Sync shortlist from file (source of truth)
st.session_state["shortlist"] = load_shortlist_from_file()

# Initialize session state
if "compare_list" not in st.session_state:
    st.session_state.compare_list = load_scouts_compare_list()
if "profile_player_id" not in st.session_state:
    st.session_state.profile_player_id = None
# Deep link: ?player_id=xxx opens this profile
pid = st.query_params.get("player_id")
if pid is not None:
    try:
        st.session_state.profile_player_id = int(pid)
    except (TypeError, ValueError):
        pass
if "percentile_context" not in st.session_state:
    st.session_state.percentile_context = "all"  # all, top5, league

# Load data
with st.spinner("Loading player data…"):
    df_all = load_enriched_season_stats()
    form_df = load_rolling_form()
    consistency_df = load_player_consistency()
    opponent_df = load_opponent_context_summary()
    profiles_df = load_scouting_profiles()
    team_stats_df = load_team_season_stats()
    tactical_df = load_tactical_profiles()
    try:
        career_df = load_career_stats()
    except Exception:
        career_df = pd.DataFrame()
    try:
        progression_df = load_player_progression()
    except Exception:
        progression_df = pd.DataFrame()

def _load_shortlist_for_profile() -> list:
    """Load shortlist from file for profile page."""
    return load_shortlist_from_file()


def _render_player_row(player: Any, rank: Optional[int] = None) -> None:
    """Render one player row with optional rank. Caller must use st.columns([4,1,1])."""
    pos_label = POSITION_NAMES.get(player.get("player_position"), player.get("player_position", ""))
    team = player.get("team", "") or "—"
    league = player.get("league_name", "") or "—"
    rank_str = f"#{rank}" if rank is not None else ""
    st.markdown(
        f"""
        <div class="top-list-row">
            <span class="top-list-rank">{rank_str}</span>
            <span class="top-list-name">{player.get('player_name', '')}</span>
            <span class="top-list-meta">{pos_label} · {team} · {league}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Check for player selection
player_id = st.session_state.get("profile_player_id")

# Player selector if none selected
if player_id is None or player_id not in df_all["player_id"].values:
    st.markdown(
        """
        <div class="hero-v2">
            <div class="hero-v2-title">Player Profile</div>
            <div class="hero-v2-sub">
                Open a player to view their full scouting report — radar, form, badges, and match log.
            </div>
            <div class="hero-v2-tagline">Choose from your shortlist, search by name, or browse top performers.</div>
            <div class="hero-v2-accent" aria-hidden="true"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # Primary CTA: one clear path to discover players
    _cta_col, _ = st.columns([2, 4])
    with _cta_col:
        if st.button("Find players", key="profile_find_players", type="primary", use_container_width=True):
            st.switch_page("pages/8_🔎_Discover.py")
    st.markdown("---")

    # Keep session shortlist in sync with file (so "Your shortlist" shows when opening Profile first)
    try:
        file_shortlist = _load_shortlist_for_profile()
        if file_shortlist:
            st.session_state.shortlist = file_shortlist
    except Exception:
        pass

    shortlist_ids = [p["id"] for p in st.session_state.shortlist if isinstance(p.get("id"), (int, float))]
    shortlist_df = df_all[df_all["player_id"].isin(shortlist_ids)][
        ["player_id", "player_name", "player_position", "team", "league_name"]
    ].drop_duplicates("player_id") if shortlist_ids else pd.DataFrame()

    # 1) Your shortlist (if any)
    if not shortlist_df.empty:
        st.markdown("<div class='section-header'>🎯 Your shortlist</div>", unsafe_allow_html=True)
        st.caption("Players you’re tracking. Open a profile or add to Compare.")
        for _, row in shortlist_df.iterrows():
            p = row.to_dict()
            pid = p["player_id"]
            cols = st.columns([4, 1, 1])
            with cols[0]:
                _render_player_row(p)
            with cols[1]:
                if st.button("View Profile", key=f"sl_view_{pid}", use_container_width=True):
                    st.session_state["profile_player_id"] = pid
                    st.rerun()
            with cols[2]:
                if st.button("Quick Add", key=f"sl_add_{pid}", use_container_width=True):
                    if pid not in st.session_state.compare_list:
                        st.session_state.compare_list.append(pid)
                        save_scouts_compare_list(st.session_state.compare_list)
                        st.success("Added to compare!")
        st.markdown("---")

    # 2) Search or browse
    st.markdown("<div class='section-header'>🔍 Search or browse</div>", unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("Search by name:", placeholder="e.g., Mbappé, Bellingham...", key="profile_search")
    with col2:
        position_filter = st.multiselect(
            "Filter by position:",
            options=["F", "M", "D", "G"],
            format_func=lambda x: POSITION_NAMES.get(x, x),
            default=[],
            key="profile_pos",
        )

    has_search = bool(search_term and search_term.strip())
    has_position = bool(position_filter)

    if has_search or has_position:
        # Search/filter active: show all matches (cap at 50)
        matching = df_all.copy()
        if has_search:
            matching = matching[matching["player_name"].str.contains(search_term.strip(), case=False, na=False)]
        if has_position:
            matching = matching[matching["player_position"].isin(position_filter)]
        matching = matching[["player_id", "player_name", "player_position", "team", "league_name"]].drop_duplicates("player_id")
        matching = matching.head(50)
        if not matching.empty:
            st.markdown(f"**Found {len(matching)} player(s)** — select one to open their profile.")
            for _, row in matching.iterrows():
                p = row.to_dict()
                pid = p["player_id"]
                cols = st.columns([4, 1, 1])
                with cols[0]:
                    _render_player_row(p)
                with cols[1]:
                    if st.button("View Profile", key=f"sr_view_{pid}", use_container_width=True):
                        st.session_state["profile_player_id"] = pid
                        st.rerun()
                with cols[2]:
                    if st.button("Quick Add", key=f"sr_add_{pid}", use_container_width=True):
                        if pid not in st.session_state.compare_list:
                            st.session_state.compare_list.append(pid)
                            save_scouts_compare_list(st.session_state.compare_list)
                            st.success("Added to compare!")
        else:
            st.info("No players found. Try a different name or position, or use **Find players** to explore.")
    else:
        # No search: show top 20 by rating (default scope) so the list is meaningful
        df_scope = filter_to_default_scope(df_all)
        if not df_scope.empty and "avg_rating" in df_scope.columns and "total_minutes" in df_scope.columns:
            df_scope = df_scope.copy()
            df_scope["_w"] = df_scope["avg_rating"] * df_scope["total_minutes"]
            g = df_scope.groupby("player_id")
            agg = g.agg(total_minutes=("total_minutes", "sum"), _sum_w=("_w", "sum"))
            agg["avg_rating"] = agg.apply(
                lambda r: safe_divide(r["_sum_w"], r["total_minutes"], default=np.nan),
                axis=1,
            )
            idx = df_scope.groupby("player_id")["total_minutes"].idxmax()
            primary = df_scope.loc[idx, ["player_id", "player_name", "player_position", "team", "league_name"]].set_index("player_id")
            agg = agg.join(primary)
            max_mins = float(df_scope["total_minutes"].max())
            if max_mins and max_mins > 0:
                min_mins = 0.5 * max_mins
                agg = agg[agg["total_minutes"] >= min_mins].sort_values("avg_rating", ascending=False).head(20)
            else:
                agg = agg.sort_values("avg_rating", ascending=False).head(20)
            matching = agg.reset_index()[["player_id", "player_name", "player_position", "team", "league_name"]]
        else:
            matching = pd.DataFrame()

        if not matching.empty:
            st.caption(f"Top 20 by season rating ({CURRENT_SEASON}, main leagues + UEFA). Or search by name or filter by position above.")
            for i, (_, row) in enumerate(matching.iterrows(), start=1):
                p = row.to_dict()
                pid = p["player_id"]
                cols = st.columns([4, 1, 1])
                with cols[0]:
                    _render_player_row(p, rank=i)
                with cols[1]:
                    if st.button("View Profile", key=f"top_view_{pid}", use_container_width=True):
                        st.session_state["profile_player_id"] = pid
                        st.rerun()
                with cols[2]:
                    if st.button("Quick Add", key=f"top_add_{pid}", use_container_width=True):
                        if pid not in st.session_state.compare_list:
                            st.session_state.compare_list.append(pid)
                            save_scouts_compare_list(st.session_state.compare_list)
                            st.success("Added to compare!")
        else:
            st.caption("Search by name or filter by position to open a profile. Or use **Find players** to explore by league and filters.")

    st.markdown("---")
    st.caption("To discover more players by league, age, or stats, use **Find players**.")
    st.stop()

# ---------------------------------------------------------------------------
# Player loaded — display profile
# ---------------------------------------------------------------------------

# Back button: return to profile list (no player selected)
_back_col, _ = st.columns([1, 5])
with _back_col:
    if st.button("← Back to player list", key="profile_back_to_list", use_container_width=True):
        st.session_state.profile_player_id = None
        if "player_id" in st.query_params:
            del st.query_params["player_id"]
        st.rerun()

# Get player data
player_rows = df_all[df_all["player_id"] == player_id].sort_values("season", ascending=False)

if player_rows.empty:
    st.error("Player not found in database")
    st.stop()

# Player info
player_name = player_rows.iloc[0]["player_name"]
player_position = player_rows.iloc[0]["player_position"]

# Hero: player name + position (one clear title, gold accent)
st.markdown(
    f"""
    <div class="hero-v2">
        <div class="hero-v2-title">{player_name}</div>
        <div class="hero-v2-sub">{POSITION_NAMES.get(player_position, player_position)} profile</div>
        <div class="hero-v2-accent" aria-hidden="true"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Season selection (default to current season when available)
season_opts = player_rows[["season", "competition_slug", "league_name", "team"]].drop_duplicates()
season_opts["label"] = season_opts.apply(
    lambda r: f"{r['league_name']} {r['season']} ({r['team']})", axis=1
)
labels = season_opts["label"].tolist()
# Prefer current season: put it first so index 0 is default
current_season_opts = season_opts[season_opts["season"] == CURRENT_SEASON]
if not current_season_opts.empty:
    current_labels = current_season_opts["label"].tolist()
    other = [l for l in labels if l not in current_labels]
    labels = current_labels + other
index = 0
chosen_label = st.selectbox("Select season:", labels, index=index)
chosen_row = season_opts[season_opts["label"] == chosen_label].iloc[0]
chosen_season = chosen_row["season"]
chosen_comp = chosen_row["competition_slug"]
chosen_team = chosen_row["team"]

# Season history table (all seasons: team, league, minutes, rating)
with st.expander("📅 Season history", expanded=False):
    hist_cols = [c for c in ["season", "team", "league_name", "total_minutes", "avg_rating", "appearances", "matches_total"] if c in player_rows.columns]
    if hist_cols:
        hist = player_rows[hist_cols].copy()
        renames = {"season": "Season", "team": "Team", "league_name": "League", "total_minutes": "Minutes", "avg_rating": "Rating", "appearances": "Apps", "matches_total": "Apps"}
        hist = hist.rename(columns={k: v for k, v in renames.items() if k in hist.columns})
        if "Minutes" in hist.columns:
            hist["Minutes"] = hist["Minutes"].fillna(0).astype(int)
        if "Rating" in hist.columns:
            hist["Rating"] = hist["Rating"].round(2)
        st.dataframe(hist.sort_values("Season", ascending=False), use_container_width=True, hide_index=True)

# Get season-specific data
prow = player_rows[
    (player_rows["season"] == chosen_season) & 
    (player_rows["competition_slug"] == chosen_comp)
].iloc[0]

# Percentile context and Per-90 toggle (needed before pool computation)
st.markdown("---")
percentile_options = {
    "all": "All Leagues",
    "top5": "Top 5 Leagues",
    "league": f"Same League ({chosen_row['league_name']})"
}
st.session_state.percentile_context = st.radio(
    "Compare against:",
    options=list(percentile_options.keys()),
    format_func=lambda x: percentile_options[x],
    horizontal=True,
    key="percentile_toggle",
)
stats_display = st.radio(
    "Stats display:",
    options=["Per 90", "Total"],
    horizontal=True,
    key="profile_per90_display",
)
profile_show_per90 = stats_display == "Per 90"

# Calculate pool and percentiles
context = st.session_state.percentile_context
from dashboard.utils.constants import TOP_5_LEAGUES
if context == "all":
    pool = df_all[
        (df_all["player_position"] == player_position) &
        (df_all["season"] == chosen_season)
    ]
    pool_label = f"All leagues · {chosen_season} · {POSITION_NAMES.get(player_position, player_position)}"
elif context == "top5":
    pool = df_all[
        (df_all["player_position"] == player_position) &
        (df_all["season"] == chosen_season) &
        (df_all["competition_slug"].isin(TOP_5_LEAGUES))
    ]
    pool_label = f"Top 5 leagues · {chosen_season} · {POSITION_NAMES.get(player_position, player_position)}"
else:
    pool = df_all[
        (df_all["player_position"] == player_position) &
        (df_all["season"] == chosen_season) &
        (df_all["competition_slug"] == chosen_comp)
    ]
    pool_label = f"{chosen_row['league_name']} · {chosen_season} · {POSITION_NAMES.get(player_position, player_position)}"

radar_stats = RADAR_STATS_BY_POSITION.get(player_position, RADAR_STATS_BY_POSITION["F"])
pct_list = []
for stat_key, stat_label in radar_stats:
    if stat_key not in prow.index or stat_key not in pool.columns:
        continue
    pct = get_percentile_zscore(prow[stat_key], pool[stat_key].dropna())
    if pd.notna(pct):
        pct_list.append((stat_key, stat_label, pct))

performance_index_value = None
performance_index_label = None
weaknesses_list = []
if pct_list:
    pcts_only = [p for _, _, p in pct_list]
    performance_index_value = sum(pcts_only) / len(pcts_only)
    pool_scores = []
    for _, row in pool.iterrows():
        row_pcts = [
            get_percentile_zscore(row.get(stat_key), pool[stat_key].dropna())
            for stat_key, _, _ in pct_list
            if stat_key in row.index and stat_key in pool.columns
        ]
        row_pcts = [p for p in row_pcts if pd.notna(p)]
        if row_pcts:
            pool_scores.append(sum(row_pcts) / len(row_pcts))
    if pool_scores:
        top_pct = get_percentile_zscore(performance_index_value, pd.Series(pool_scores))
        if top_pct >= 50:
            performance_index_label = f"Top {100 - int(top_pct)}%"
        else:
            performance_index_label = f"Bottom {int(top_pct)}%"
    weaknesses_list = [(label, pct) for _, label, pct in pct_list if pct < 25]

# Badges (needed for narrative and display)
badge_prow = prow.copy()
cons_row = consistency_df[
    (consistency_df["player_id"] == player_id) &
    (consistency_df["season"] == chosen_season) &
    (consistency_df["competition_slug"] == chosen_comp)
]
if not cons_row.empty:
    c = cons_row.iloc[0]
    if "rating_cv" in c.index and pd.notna(c.get("rating_cv")):
        badge_prow["cv_rating"] = c["rating_cv"]
        badge_prow["rating_cv"] = c["rating_cv"]
opp_summary = opponent_df[
    (opponent_df["player_id"] == player_id) &
    (opponent_df["season"] == chosen_season) &
    (opponent_df["competition_slug"] == chosen_comp)
]
if not opp_summary.empty:
    o = opp_summary.iloc[0]
    r_top = o.get("rating_vs_top")
    r_bottom = o.get("rating_vs_bottom")
    if pd.notna(r_top) and pd.notna(r_bottom) and r_bottom and float(r_bottom) > 0:
        badge_prow["big_game_ratio"] = float(r_top) / float(r_bottom)
    else:
        badge_prow["big_game_ratio"] = 1.0
    for col in ["rating_vs_top", "rating_vs_bottom", "big_game_rating_delta"]:
        if col in o.index:
            badge_prow[col] = o[col]
if career_df is not None and not career_df.empty:
    career_row = career_df[career_df["player_id"] == player_id]
    if not career_row.empty:
        cr = career_row.iloc[0]
        badge_prow["seasons_at_level"] = cr.get("n_seasons", 0)
        badge_prow["appearances_career"] = cr.get("appearances", 0) or 0
if progression_df is not None and not progression_df.empty:
    prog = progression_df[
        (progression_df["player_id"] == player_id) &
        (progression_df["season_to"] == chosen_season)
    ]
    if not prog.empty:
        pr = prog.iloc[0]
        badge_prow["progression_delta"] = pr.get("rating_delta") or pr.get("avg_rating_delta") or 0
        direction = pr.get("progression_direction") or "flat"
        badge_prow["trend_direction"] = "up" if direction == "improving" else ("down" if direction == "declining" else "flat")
        if direction == "declining" and (badge_prow.get("age_at_season_start") or 0) >= 28:
            badge_prow["minutes_decline"] = True
badges = calculate_badges(badge_prow, pool)

# ---------- 1. Header (one line) + actions ----------
st.markdown("---")
pos_label = POSITION_NAMES.get(player_position, player_position)
flag = COMP_FLAGS.get(chosen_comp, "🏆")
st.markdown(
    f"""
    <div class="profile-summary-card" style="margin-bottom:12px;">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
            <div style="display:flex;align-items:center;gap:12px;">
                <span style="font-size:1.5rem;" aria-hidden="true">{flag}</span>
                <div>
                    <span style="font-size:1.25rem;font-weight:700;color:#F0F6FC;">{player_name}</span>
                    <span class="profile-summary-stat-label" style="margin-left:8px;">{pos_label} · {chosen_team} · {chosen_row['league_name']} · {chosen_season}</span>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
header_actions = st.columns([1, 1, 1, 3])
with header_actions[0]:
    in_shortlist = player_id in [p["id"] for p in st.session_state.shortlist]
    if in_shortlist:
        st.button("✅ In Shortlist", disabled=True, use_container_width=True, key="ph_shortlist")
    else:
        if st.button("🎯 Add to Shortlist", use_container_width=True, type="primary", key="ph_shortlist"):
            st.session_state.shortlist.append({"id": player_id, "name": player_name, "status": "Watching", "added_date": pd.Timestamp.now().strftime("%Y-%m-%d")})
            save_shortlist_to_file(st.session_state.shortlist)
            st.toast("Added to shortlist!")
            st.rerun()
with header_actions[1]:
    in_compare = player_id in st.session_state.compare_list
    if in_compare:
        st.button("✅ In Compare", disabled=True, use_container_width=True, key="ph_compare")
    else:
        if st.button("⚖️ Add to Compare", use_container_width=True, key="ph_compare"):
            st.session_state.compare_list.append(player_id)
            save_scouts_compare_list(st.session_state.compare_list)
            st.toast("Added to compare!")
            st.rerun()
with header_actions[2]:
    if st.button("🔎 Find Similar", use_container_width=True, key="ph_similar"):
        st.switch_page("pages/8_🔎_Discover.py")

# ---------- 2. Recommendation (team-based) ----------
st.markdown("<div class='section-header'>🎯 Recommendation</div>", unsafe_allow_html=True)
# Current season only; one entry per team (no per-competition / per-season options)
team_key_ts = "team_name" if "team_name" in team_stats_df.columns else "team"
if not team_stats_df.empty and "season" in team_stats_df.columns:
    _ts = team_stats_df[team_stats_df["season"].astype(str) == str(CURRENT_SEASON)]
    _teams = sorted(_ts[team_key_ts].dropna().unique().tolist()) if team_key_ts in _ts.columns else []
elif not tactical_df.empty and "season" in tactical_df.columns:
    _tk = "team_name" if "team_name" in tactical_df.columns else "team"
    _tc = tactical_df[tactical_df["season"].astype(str) == str(CURRENT_SEASON)]
    _teams = sorted(_tc[_tk].dropna().unique().tolist()) if _tk in _tc.columns else []
else:
    _teams = []
team_choices = ["— Select a team —"] + _teams
selected_team_name = st.selectbox("Recommendation for:", team_choices, key="profile_recommendation_team")
st.caption(f"Current season ({CURRENT_SEASON}) · fit based on team data across all competitions.")
team_name_sel = team_label_sel = None
if selected_team_name and selected_team_name != "— Select a team —":
    team_name_sel = selected_team_name
    team_label_sel = f"{selected_team_name} ({CURRENT_SEASON}, all competitions)"

fit_result_display = None
team_tactical_row = None
if team_name_sel:
    try:
        team_data_series, team_tactical_row = _get_team_data_for_fit_aggregated(
            team_name_sel, CURRENT_SEASON, df_all, team_stats_df, tactical_df
        )
        if team_tactical_row is None:
            team_tactical_row = pd.Series(dtype=float)
        fit_result = calculate_fit_score(
            player_data=prow,
            team_data=team_data_series,
            team_tactical_profile=team_tactical_row,
            position=player_position,
        )
        # League modifier: same league 1.0, same tier 0.95, step up cap 0.9, step down 1.05
        # Team is aggregated across all comps; use player's league for comparison
        player_comp = chosen_comp
        team_comp = chosen_comp  # conservative: treat as same league when aggregated
        same_league = player_comp == team_comp
        player_top5 = player_comp in TOP_5_LEAGUES
        team_top5 = team_comp in TOP_5_LEAGUES
        if same_league:
            mod = 1.0
        elif player_top5 and team_top5:
            mod = 0.95
        elif team_top5 and not player_top5:
            mod = 0.9
        elif player_top5 and not team_top5:
            mod = 1.05
        else:
            mod = 1.0
        raw_score = fit_result["overall_score"]
        recommendation_pct = min(100, max(0, raw_score * mod))
        if recommendation_pct >= 85:
            recommendation_label = "Strong recommendation"
        elif recommendation_pct >= 70:
            recommendation_label = "Recommended"
        elif recommendation_pct >= 55:
            recommendation_label = "Conditional"
        else:
            recommendation_label = "Not recommended"
        fit_result_display = {
            "overall_score": raw_score,
            "recommendation_pct": recommendation_pct,
            "recommendation_label": recommendation_label,
            "explanation": fit_result.get("explanation", ""),
            "recommendation": fit_result.get("recommendation", ""),
            "selected_team_label": team_label_sel,
        }
    except Exception:
        team_tactical_row = None
        fit_result_display = {"selected_team_label": team_label_sel, "recommendation_pct": 0, "recommendation_label": "Error", "explanation": "Could not compute fit for this team."}
elif team_name_sel is None:
    fit_result_display = None

if fit_result_display:
    pct = fit_result_display["recommendation_pct"]
    label = fit_result_display["recommendation_label"]
    color = "#3FB950" if pct >= 70 else "#C9A840" if pct >= 55 else "#F85149"
    raw_expl = (fit_result_display.get("explanation") or "").strip()
    # Never show technical jargon (scores, percentages, "Statistical match", etc.)
    if "Statistical match" in raw_expl or "Squad upgrade:" in raw_expl or "/100" in raw_expl:
        if pct >= 85:
            summary = "He would be a clear upgrade and fits how we play very well."
        elif pct >= 70:
            summary = "He would strengthen the squad and fits our style well."
        elif pct >= 55:
            summary = "He would add to the squad but may need a clear role or time to adapt."
        else:
            summary = "Would not improve the squad or doesn't align well with our profile."
    else:
        summary = raw_expl
    st.markdown(
        f"""
        <div class="performance-index-card" style="border-left:4px solid {color};">
            <div style="font-size:1.1rem;font-weight:700;color:{color};">{pct:.0f}% – {label}</div>
            <div class="profile-summary-stat-label" style="margin-top:6px;font-size:0.95rem;line-height:1.4;">{summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        if team_tactical_row is None or (hasattr(team_tactical_row, "empty") and team_tactical_row.empty):
            st.caption("Recommendation based on statistical fit only (no tactical profile for this team).")
    except NameError:
        pass
else:
    st.info(
        "**Work in progress.** This recommendation feature is under development. "
        "Select a team above to see how this player fits that club."
    )

# ---------- 3. Executive summary / narrative ----------
st.markdown("<div class='section-header'>📝 Executive summary</div>", unsafe_allow_html=True)
# Rolling form (07) may not have season/competition_slug; filter only on existing columns
_base = form_df[form_df["player_id"] == player_id] if not form_df.empty and "player_id" in form_df.columns else pd.DataFrame()
if _base.empty:
    form_row = pd.DataFrame()
elif "season" in form_df.columns and "competition_slug" in form_df.columns:
    form_row = _base[
        (_base["season"].astype(str) == str(chosen_season)) &
        (_base["competition_slug"] == chosen_comp)
    ].head(1)
else:
    # No season/comp in form data; prefer window=5 (last 5 games) if present
    form_row = _base[_base["window"] == 5].head(1) if "window" in _base.columns else _base.head(1)
# Scouting profiles may not have season/competition_slug; filter only on existing columns
_prof_base = profiles_df[profiles_df["player_id"] == player_id] if not profiles_df.empty and "player_id" in profiles_df.columns else pd.DataFrame()
if _prof_base.empty:
    _scout = pd.DataFrame()
elif "season" in profiles_df.columns and "competition_slug" in profiles_df.columns:
    _scout = _prof_base[
        (_prof_base["season"].astype(str) == str(chosen_season)) &
        (_prof_base["competition_slug"] == chosen_comp)
    ]
else:
    _scout = _prof_base.head(1)
scout_row = _scout.iloc[0] if not _scout.empty else None

role_para, strengths_para, concerns_para = build_player_narrative_blobs(
    prow, badges, form_row if not form_row.empty else None, scout_row, fit_result_display,
    performance_index_label=performance_index_label,
    pool_label=pool_label,
)
st.markdown(f"<p class='narrative-box'>{role_para}</p>", unsafe_allow_html=True)
st.markdown(f"<p class='narrative-box'>{strengths_para}</p>", unsafe_allow_html=True)
st.markdown(f"<p class='narrative-box'>{concerns_para}</p>", unsafe_allow_html=True)
st.markdown(
    """
    <p class='narrative-box' style='border-left:4px solid #E5A00D;color:#9CA3AF;font-style:italic;'>
        Adding more meaningful interpretation is work in progress.
    </p>
    """,
    unsafe_allow_html=True,
)

# ---------- 4. Key metrics strip ----------
st.markdown("<div class='section-header'>📊 Key metrics</div>", unsafe_allow_html=True)
kpi_list = [
    ("avg_rating", "Rating"),
    ("total_minutes", "Minutes"),
    ("goals_per90", "Goals/90"),
    ("expectedGoals_per90", "xG/90"),
    ("keyPass_per90", "Key Pass/90"),
    ("expectedAssists_per90", "xA/90"),
]
kpi_cols = st.columns(min(len(kpi_list), 6))
for i, (col, (key, label)) in enumerate(zip(kpi_cols, kpi_list)):
    with col:
        val = prow.get(key)
        if key == "total_minutes":
            disp = f"{int(val):,}" if pd.notna(val) else "—"
        else:
            disp = f"{val:.2f}" if pd.notna(val) else "—"
        st.metric(label, disp)

# ---------- 5. Badges ----------
st.markdown("---")
st.markdown("<div class='section-header'>🏷️ Scouting Badges</div>", unsafe_allow_html=True)
if badges:
    positive = [b for b in badges if b.is_positive]
    negative = [b for b in badges if not b.is_positive]
    if positive:
        st.markdown("**Strengths:** " + " ".join([format_badge_for_display(b) for b in positive]), unsafe_allow_html=True)
    if negative:
        st.markdown("**Concerns:** " + " ".join([format_badge_for_display(b) for b in negative]), unsafe_allow_html=True)
else:
    st.info("Insufficient data for badge generation")

# ---------- 6. Performance index + radar ----------
if performance_index_value is not None and performance_index_label:
    idx_col, weak_col = st.columns([1, 1])
    with idx_col:
        st.markdown(
            f"""
            <div class="performance-index-card">
                <div class="performance-index-label">Performance index</div>
                <div class="performance-index-value">{performance_index_label} in comparison pool</div>
                <div class="performance-index-scope">{pool_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with weak_col:
        if weaknesses_list:
            st.markdown("<div class='section-header'>Improvement areas</div>", unsafe_allow_html=True)
            for label, pct in sorted(weaknesses_list, key=lambda x: x[1])[:6]:
                st.markdown(f'<span class="weakness-chip">{label} ({pct:.0f}th pct)</span>', unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size:0.85rem;color:#8B949E;'>No weak areas (all radar stats above 25th percentile).</div>", unsafe_allow_html=True)
    st.markdown("")

# ---------- 7. Radar + Key percentiles ----------
radar_col, bars_col = st.columns([2, 1])

with radar_col:
    st.markdown("<div class='section-header'>🎯 Performance Radar</div>", unsafe_allow_html=True)
    
    # Use precomputed pct_list for radar; fallback to on-the-fly if empty
    if pct_list:
        radar_data = [pct for _, _, pct in pct_list]
        stat_labels = [label for _, label, _ in pct_list]
    else:
        radar_data = []
        stat_labels = []
        for stat_key, stat_label in radar_stats:
            if stat_key in prow.index and stat_key in pool.columns:
                pct = get_percentile_zscore(prow[stat_key], pool[stat_key].dropna())
                if pd.notna(pct):
                    radar_data.append(pct)
                    stat_labels.append(stat_label)
    
    # Create radar chart
    if radar_data:
        fig = go.Figure()
        # Clamp to [0, 100] for safe polar display
        r_safe = [max(0.0, min(100.0, float(v))) if np.isfinite(v) else 50.0 for v in radar_data]
        radar_data_closed = r_safe + [r_safe[0]]
        stat_labels_closed = stat_labels + [stat_labels[0]]
        
        fig.add_trace(go.Scatterpolar(
            r=radar_data_closed,
            theta=stat_labels_closed,
            fill="toself",
            fillcolor="rgba(201,168,64,0.2)",
            line=dict(color="#C9A840", width=2),
            name=player_name,
            hovertemplate="<b>%{theta}</b><br>Percentile: %{r:.0f}<extra></extra>",
        ))
        
        fig.update_layout(
            polar=dict(
                bgcolor="#0D1117",
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    showticklabels=False,
                    gridcolor="#30363D",
                    linecolor="#30363D",
                ),
                angularaxis=dict(
                    gridcolor="#30363D",
                    linecolor="#30363D",
                    tickfont=dict(size=10, color="#E6EDF3"),
                ),
            ),
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            font=dict(color="#E6EDF3"),
            margin=dict(l=44, r=44, t=30, b=30),
            height=350,
            showlegend=False,
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"ℹ️ Percentiles within: {pool_label} (n={len(pool)})")

with bars_col:
    st.markdown("<div class='section-header'>📈 Key Percentiles</div>", unsafe_allow_html=True)
    
    # Per-90 vs Total: pick stat set
    key_stats_per90 = [
        ("avg_rating", "Overall Rating"),
        ("goals_per90", "Goals/90"),
        ("expectedGoals_per90", "xG/90"),
        ("expectedAssists_per90", "xA/90"),
        ("keyPass_per90", "Key Passes/90"),
    ]
    key_stats_total = [
        ("avg_rating", "Overall Rating"),
        ("goals", "Goals"),
        ("assists", "Assists"),
        ("expected_goals", "xG"),
        ("keyPass", "Key Passes"),
    ]
    key_stats = key_stats_per90 if profile_show_per90 else key_stats_total
    
    for stat_key, stat_label in key_stats:
        if stat_key in prow.index and stat_key in pool.columns:
            val = prow[stat_key]
            pct = get_percentile_zscore(val, pool[stat_key].dropna())

            if pd.isna(pct):
                continue  # skip stats with no percentile data

            # Color based on percentile
            if pct >= 80:
                color = "#3FB950"  # Green
            elif pct >= 60:
                color = "#C9A840"  # Gold
            else:
                color = "#8B949E"  # Gray

            val_str = f"{val:.2f}" if pd.notna(val) else "N/A"
            st.markdown(
                f"""
                <div class="percentile-bar-row">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span class="label">{stat_label}</span>
                        <span class="value" style="color:{color};">{pct:.0f}th</span>
                    </div>
                    <div class="bar-bg"><div class="bar-fill" style="background:{color};width:{pct:.1f}%;"></div></div>
                    <div class="raw">{val_str}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Position-Specific Sections
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📋 Detailed Analysis</div>", unsafe_allow_html=True)

# Human-readable labels for detailed analysis stats (optional overrides)
STAT_LABELS = {
    "totalShots_per90": "Shots/90",
    "onTargetScoringAttempt_per90": "Shots on target/90",
    "goals_per90": "Goals/90",
    "expectedGoals_per90": "xG/90",
    "bigChanceCreated_per90": "Big chances created/90",
    "expectedAssists_per90": "xA/90",
    "keyPass_per90": "Key Passes/90",
    "totalPass_per90": "Passes/90",
    "pass_accuracy_pct": "Pass accuracy %",
    "longPass_per90": "Long passes/90",
    "progressivePass_per90": "Progressive passes/90",
    "progressiveBallCarriesCount_per90": "Progressive carries/90",
    "dribble_per90": "Dribbles/90",
    "ballRecovery_per90": "Ball recoveries/90",
    "touches_per90": "Touches/90",
    "totalTackle_per90": "Tackles/90",
    "interceptionWon_per90": "Interceptions/90",
    "duelWon_per90": "Duels won/90",
    "totalClearance_per90": "Clearances/90",
    "blockedScoringAttempt_per90": "Blocked shots/90",
    "aerialWon_per90": "Aerial won/90",
    "aerial_lost_per90": "Aerial lost/90",
    "aerial_win_rate": "Aerial win %",
    "touches_in_box_per90": "Touches in box/90",
    "saves_per90": "Saves/90",
    "goalsPrevented_per90": "Goals prevented/90",
    "goodHighClaim_per90": "High claims/90",
    "totalKeeperSweeper_per90": "Sweeper actions/90",
    "savedShotsFromInsideTheBox_per90": "Saves in box/90",
    "accurateKeeperSweeper_per90": "Accurate sweeper/90",
    "punches_per90": "Punches/90",
    "penaltySave_per90": "Penalty saves/90",
    "crossNotClaimed_per90": "Crosses not claimed/90",
    "keeperSaveValue_per90": "Save value/90",
    "goalkeeperValueNormalized_per90": "GK value (norm)/90",
}

# All outfield sections: same content for F/M/D, only order changes by position.
# Every outfield player sees Attacking, Chance Creation, Movement, Passing, Progression, Defensive Actions, Aerial Duels.
OUTFIELD_SECTIONS = {
    "Attacking": ["totalShots_per90", "onTargetScoringAttempt_per90", "goals_per90", "expectedGoals_per90", "bigChanceCreated_per90"],
    "Chance Creation": ["expectedAssists_per90", "keyPass_per90"],
    "Movement": ["dribble_per90", "touches_in_box_per90", "touches_per90"],
    "Passing": ["totalPass_per90", "pass_accuracy_pct", "keyPass_per90", "expectedAssists_per90", "longPass_per90"],
    "Progression": ["progressivePass_per90", "progressiveBallCarriesCount_per90", "dribble_per90", "ballRecovery_per90", "touches_per90"],
    "Defensive Actions": ["totalTackle_per90", "interceptionWon_per90", "duelWon_per90", "totalClearance_per90", "blockedScoringAttempt_per90"],
    "Aerial Duels": ["aerialWon_per90", "aerial_win_rate", "aerial_lost_per90"],
}
# Order of sections by position (narrative: role-first, then rest).
OUTFIELD_SECTION_ORDER = {
    "F": ["Attacking", "Chance Creation", "Movement", "Passing", "Progression", "Defensive Actions", "Aerial Duels"],
    "M": ["Attacking", "Passing", "Progression", "Defensive Actions", "Chance Creation", "Movement", "Aerial Duels"],
    "D": ["Defensive Actions", "Aerial Duels", "Progression", "Passing", "Attacking", "Chance Creation", "Movement"],
}

# Goalkeeper: all keeper-related sections from the pipeline (03 STAT_COLS → *_per90). Everything visible.
KEEPER_SECTIONS = [
    ("Shot Stopping", [
        "saves_per90", "goalsPrevented_per90", "savedShotsFromInsideTheBox_per90",
        "penaltySave_per90", "keeperSaveValue_per90", "goalkeeperValueNormalized_per90",
    ]),
    ("Distribution", ["pass_accuracy_pct", "totalPass_per90"]),
    ("Command", [
        "goodHighClaim_per90", "totalKeeperSweeper_per90", "accurateKeeperSweeper_per90",
        "punches_per90", "crossNotClaimed_per90",
    ]),
]

def _get_detailed_analysis_sections(position: str):
    """Return list of (section_name, stat_keys) for Detailed Analysis. Outfield: all sections in position order; G: all keeper sections."""
    if position == "G":
        return KEEPER_SECTIONS
    order = OUTFIELD_SECTION_ORDER.get(position, OUTFIELD_SECTION_ORDER["F"])
    return [(name, OUTFIELD_SECTIONS[name]) for name in order]

sections = _get_detailed_analysis_sections(player_position)

for section_name, stats in sections:
    with st.expander(f"📊 {section_name}", expanded=True):
        stats_present = [s for s in stats if s in prow.index]
        # Order stats by percentile (strongest first) so each section reads top-to-bottom as strengths → weaknesses
        def _pct_for_sort(sk):
            if sk not in pool.columns or sk not in prow.index:
                return -1.0
            v = prow[sk]
            if pd.isna(v):
                return -1.0
            p = get_percentile_zscore(v, pool[sk].dropna())
            return float(p) if pd.notna(p) else -1.0
        stats_present = sorted(stats_present, key=_pct_for_sort, reverse=True)
        for stat_key in stats_present:
            val = prow[stat_key]
            if stat_key in pool.columns and pd.notna(val):
                pct = get_percentile_zscore(val, pool[stat_key].dropna())
            else:
                pct = float("nan")

            pct_display = f"{pct:.0f}th" if pd.notna(pct) else "N/A"
            val_str = f"{val:.2f}" if pd.notna(val) else "—"
            if stat_key.endswith("_pct") or "win_rate" in stat_key:
                val_str = f"{val:.1f}%" if pd.notna(val) else "—"

            if pd.notna(pct) and pct >= 80:
                color = "#3FB950"
            elif pd.notna(pct) and pct >= 50:
                color = "#C9A840"
            elif pd.notna(pct):
                color = "#F85149"
            else:
                color = "#8B949E"
            bar_pct = float(pct) if pd.notna(pct) else 0.0

            label = STAT_LABELS.get(stat_key, stat_key.replace("_per90", "/90").replace("_", " ").title())
            st.markdown(
                f"""
                <div class="percentile-bar-row">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span class="label">{label}</span>
                        <span class="value" style="color:{color};">{pct_display}</span>
                    </div>
                    <div class="bar-bg"><div class="bar-fill" style="background:{color};width:{bar_pct:.1f}%;"></div></div>
                    <div class="raw">{val_str}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Big Game Performance
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🔥 Big Game Performance</div>", unsafe_allow_html=True)

opp_row = opponent_df[
    (opponent_df["player_id"] == player_id) &
    (opponent_df["season"] == chosen_season) &
    (opponent_df["competition_slug"] == chosen_comp)
]

if not opp_row.empty:
    opp = opp_row.iloc[0]
    # Baseline = rating vs weaker teams (bottom third); ratio = vs top / vs bottom
    rating_vs_bottom = opp.get("rating_vs_bottom")
    rating_vs_top = opp.get("rating_vs_top")
    baseline = float(rating_vs_bottom) if pd.notna(rating_vs_bottom) else 0.0
    ratio = safe_divide(float(rating_vs_top) if pd.notna(rating_vs_top) else 0.0, float(rating_vs_bottom) if pd.notna(rating_vs_bottom) else 0.0, 1.0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Baseline Rating", f"{baseline:.2f}")
    with col2:
        vs_top = opp.get("rating_vs_top", 0)
        st.metric("Rating vs Top Teams", f"{vs_top:.2f}")
    with col3:
        delta = opp.get("big_game_rating_delta", 0)
        delta_color = "normal" if delta >= 0 else "inverse"
        st.metric("Big Game Δ", f"{delta:+.2f}", delta_color=delta_color)
    with col4:
        st.metric("Performance Ratio", f"{ratio:.2f}x")
else:
    st.info("No big game context data available for this season")

# ---------------------------------------------------------------------------
# Match log
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📋 Match log</div>", unsafe_allow_html=True)
try:
    match_log = get_player_match_log(player_id, chosen_season)
    if not match_log.empty:
        log_cols = ["match_date_utc", "opponent"]
        if "stat_minutesPlayed" in match_log.columns:
            log_cols.append("stat_minutesPlayed")
        if "stat_rating" in match_log.columns:
            log_cols.append("stat_rating")
        if "stat_goals" in match_log.columns:
            log_cols.append("stat_goals")
        if "stat_goalAssist" in match_log.columns:
            log_cols.append("stat_goalAssist")
        log_cols = [c for c in log_cols if c in match_log.columns]
        log_display = match_log[log_cols].head(15).copy()
        log_display = log_display.rename(columns={
            "match_date_utc": "Date", "opponent": "Opponent",
            "stat_minutesPlayed": "Min", "stat_rating": "Rating",
            "stat_goals": "G", "stat_goalAssist": "A",
        })
        st.dataframe(log_display, use_container_width=True, hide_index=True)
    else:
        st.caption("Match log coming soon for this season.")
except Exception:
    st.caption("Match log coming soon.")

# ---------------------------------------------------------------------------
# Positioning heatmap (season average or per match)
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🗺️ Positioning heatmap</div>", unsafe_allow_html=True)
heatmap_mode = st.radio(
    "View",
    ["Season average", "Per match"],
    index=0,
    horizontal=True,
    key="profile_heatmap_mode",
    help="Season average aggregates all touches in the selected season; per match shows a single game.",
)

if heatmap_mode == "Season average":
    comp_for_heatmap = chosen_comp if (chosen_comp and chosen_comp != "All") else None
    hm_season = _get_player_heatmap_season(player_id, chosen_season, comp_for_heatmap)
    if hm_season and hm_season.get("heatmap"):
        pts = hm_season["heatmap"]
        df_hm = pd.DataFrame(pts)
        if not df_hm.empty and "x" in df_hm.columns and "y" in df_hm.columns:
            fig = _profile_pitch_heatmap(df_hm["x"], df_hm["y"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No heatmap points for this player this season.")
    else:
        st.caption("No heatmap data for this player this season. Run step 18 (build heatmap parquet) after extracting player maps (e.g. extract with --extract-player-maps).")

else:
    # Per match
    match_log_for_heatmap = get_player_match_log(player_id, chosen_season)
    if "competition_slug" in match_log_for_heatmap.columns and chosen_comp and chosen_comp != "All":
        match_log_for_heatmap = match_log_for_heatmap[match_log_for_heatmap["competition_slug"] == chosen_comp]

    if match_log_for_heatmap.empty:
        st.caption("No match log for this season. Heatmaps show touch/position data per match when available.")
    elif "match_id" not in match_log_for_heatmap.columns:
        st.caption("Match IDs are required for per-match heatmaps. Rebuild derived data (player_appearances.parquet) so the match log includes match_id.")
    else:
        st.caption("Select a match to see this player's touch/position map (when heatmap data was extracted).")
        match_options = []
        for _, row in match_log_for_heatmap.head(20).iterrows():
            mid = row.get("match_id")
            if pd.isna(mid) or mid == "":
                continue
            date_str = ""
            if "match_date_utc" in row.index and pd.notna(row.get("match_date_utc")):
                try:
                    date_str = str(pd.Timestamp(row["match_date_utc"]).date())
                except Exception:
                    date_str = str(row.get("match_date_utc", ""))[:10]
            opp = row.get("opponent", row.get("away_team_name") if row.get("side") == "home" else row.get("home_team_name"))
            opp = opp or "—"
            label = f"{date_str} · vs {opp}"
            match_options.append((str(mid), label))
        if match_options:
            option_labels = [o[1] for o in match_options]
            option_ids = [o[0] for o in match_options]
            idx = st.selectbox("Match", range(len(option_labels)), format_func=lambda i: option_labels[i], key="profile_heatmap_match")
            selected_match_id = option_ids[idx]
            if st.button("Show heatmap", key="profile_show_heatmap"):
                hm = get_player_heatmap(selected_match_id, player_id)
                if hm and hm.get("heatmap"):
                    pts = hm["heatmap"]
                    df_hm = pd.DataFrame(pts)
                    if not df_hm.empty and "x" in df_hm.columns and "y" in df_hm.columns:
                        fig = _profile_pitch_heatmap(df_hm["x"], df_hm["y"])
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No heatmap points for this match.")
                else:
                    st.info("No heatmap data for this player in this match. Heatmaps are available when extracted with player maps (e.g. extract with --extract-player-maps or run step 18).")
        else:
            st.caption("No matches with match_id in the log for this view.")

# ---------------------------------------------------------------------------
# Form Chart
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📈 Recent Form (10 Games)</div>", unsafe_allow_html=True)

# Get recent form from match log (07 rolling form has no per-match rows)
match_log = get_player_match_log(player_id, season=chosen_season)
if "competition_slug" in match_log.columns and chosen_comp and chosen_comp != "All":
    match_log = match_log[match_log["competition_slug"] == chosen_comp]
player_form = match_log.sort_values("match_date_utc", ascending=False).head(10) if not match_log.empty else pd.DataFrame()

if not player_form.empty and "stat_rating" in player_form.columns:
    season_avg = float(prow.get("avg_rating", 7.0))
    # One point per game (oldest to newest), only games with valid rating — line connects consecutive dots.
    form_oldest_first = player_form.sort_values("match_date_utc", ascending=True)
    valid = form_oldest_first["stat_rating"].notna()
    form_valid = form_oldest_first.loc[valid]
    if form_valid.empty:
        form_valid = form_oldest_first
    x_vals = list(range(1, len(form_valid) + 1))
    y_vals = [float(form_valid.iloc[i]["stat_rating"]) for i in range(len(form_valid))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode="lines+markers",
        name="Rating",
        line=dict(color="#C9A840", width=2),
        marker=dict(size=8),
        hovertemplate="Game %{x}<br>Rating: %{y:.2f}<extra></extra>",
    ))
    fig.add_hline(
        y=season_avg,
        line_dash="dash",
        line_color="#8B949E",
        annotation_text=f"Season ({season_avg:.2f})",
        annotation_position="right"
    )
    fig.update_layout(
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3"),
        xaxis=dict(title="Match", gridcolor="#30363D", showgrid=True),
        yaxis=dict(title="Rating", gridcolor="#30363D", range=[5, 10]),
        margin=dict(l=44, r=44, t=30, b=44),
        height=250,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No match-by-match form data available for this season")

# ---------------------------------------------------------------------------
# Similar Players — always from CURRENT SEASON (2025-26)
# Reference style from the profile's selected season so past players (e.g. Kroos 2023/24) still get matches.
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>👥 Similar Players</div>", unsafe_allow_html=True)
# Reference = this profile's season (normalized). Pool = current season only.
_raw_ref = str(chosen_season).strip() if chosen_season is not None and pd.notna(chosen_season) else ""
reference_season = _raw_ref.replace("/", "-") if _raw_ref and _raw_ref.lower() != "nan" else CURRENT_SEASON
# Ensure reference_season is one this player has data for (avoid "nan" or bad value)
_df_season_norm = df_all["season"].astype(str).str.strip().str.replace("/", "-", regex=False)
has_ref = not df_all[(df_all["player_id"] == player_id) & (_df_season_norm == reference_season)].empty
if not has_ref:
    player_seasons = _df_season_norm[df_all["player_id"] == player_id].drop_duplicates().tolist()
    reference_season = player_seasons[0] if player_seasons else CURRENT_SEASON

# After switch_page, first run can have widget/cache timing issues; trigger one rerun so Similar Players runs with stable state.
_similar_stable_key = f"_profile_similar_ran_{player_id}_{reference_season}"
if _similar_stable_key not in st.session_state:
    st.session_state[_similar_stable_key] = True
    st.rerun()

st.caption(f"This profile's numbers (**{reference_season}**) vs **current season** ({CURRENT_SEASON}) players — who in {CURRENT_SEASON} is most similar by playing style.")
similar_league_option = st.radio(
    "League scope for similar players",
    options=["This league only", "Top 5 leagues", "All leagues"],
    index=0,
    key="profile_similar_league",
    horizontal=True,
)
cross_league = similar_league_option == "Top 5 leagues"
include_all_leagues = similar_league_option == "All leagues"

similar = None
similar_scope_note = None
# Coerce to plain str so Streamlit cache and data.py comparisons are stable (no numpy/pandas types)
_comp = str(chosen_comp).strip() if chosen_comp is not None and pd.notna(chosen_comp) else ""
_pos = str(player_position).strip() if player_position is not None and pd.notna(player_position) else ""
_pid = int(player_id)
try:
    similar = get_similar_players(
        player_id=_pid,
        season=CURRENT_SEASON,
        competition_slug=_comp,
        position=_pos,
        df_all=df_all,
        n=3,
        cross_league=cross_league,
        include_all_leagues=include_all_leagues,
        reference_season=reference_season,
        min_minutes=1000,
    )
    if (similar is None or similar.empty) and not include_all_leagues:
        similar = get_similar_players(
            player_id=_pid,
            season=CURRENT_SEASON,
            competition_slug=_comp,
            position=_pos,
            df_all=df_all,
            n=3,
            cross_league=True,
            include_all_leagues=False,
            reference_season=reference_season,
            min_minutes=1000,
        )
        if similar is not None and not similar.empty:
            similar_scope_note = "No others in this league; showing closest from **Top 5 leagues**."
    if similar is None or similar.empty:
        similar = get_similar_players(
            player_id=_pid,
            season=CURRENT_SEASON,
            competition_slug=_comp,
            position=_pos,
            df_all=df_all,
            n=3,
            cross_league=False,
            include_all_leagues=True,
            reference_season=reference_season,
            min_minutes=1000,
        )
        if similar is not None and not similar.empty:
            similar_scope_note = "Showing closest from **all leagues** (current season)."
except Exception:
    logger.exception("Similar players failed")
    similar = None

if (similar is None or similar.empty) and df_all is not None and not df_all.empty:
    try:
        similar = get_similar_players(
            player_id=_pid,
            season=CURRENT_SEASON,
            competition_slug=_comp,
            position=_pos,
            df_all=df_all,
            n=3,
            cross_league=False,
            include_all_leagues=True,
            reference_season=reference_season,
            min_minutes=1000,
        )
        if similar is not None and not similar.empty and not similar_scope_note:
            similar_scope_note = "Showing closest from **all leagues**."
    except Exception:
        pass

# Fallback: if 1000 min filter left pool empty, retry with 450 min so we still show similar players
if (similar is None or similar.empty) and df_all is not None and not df_all.empty:
    try:
        similar = get_similar_players(
            player_id=_pid,
            season=CURRENT_SEASON,
            competition_slug=_comp,
            position=_pos,
            df_all=df_all,
            n=3,
            cross_league=False,
            include_all_leagues=True,
            reference_season=reference_season,
            min_minutes=450,
        )
        if similar is not None and not similar.empty:
            similar_scope_note = "Showing players with 450+ minutes (no results with 1000+ min)."
    except Exception:
        pass

if similar is None or similar.empty:
    logger.warning(
        "Similar players empty: player_id=%s ref_season=%s comp=%s pos=%s df_all_len=%s",
        _pid, reference_season, _comp, _pos, len(df_all) if df_all is not None else 0,
    )

if similar is not None and not similar.empty:
    if similar_scope_note:
        st.caption(similar_scope_note)
    sim_cols = st.columns(len(similar))
    for i, (_, sim_player) in enumerate(similar.iterrows()):
        with sim_cols[i]:
            dist = sim_player.get("similarity_dist", float("nan"))
            dist_label = f"{dist:.2f}" if pd.notna(dist) else "N/A"

            sim_comp = sim_player.get("competition_slug", chosen_comp)
            sim_comp_label = COMP_NAMES.get(sim_comp, sim_comp) if isinstance(sim_comp, str) else chosen_comp
            sim_name = sim_player.get("player_name", "Unknown")
            st.markdown(
                f"""
                <div class="sim-card">
                    <div style="font-weight:600;color:#F0F6FC;">{sim_name}</div>
                    <div class="profile-summary-stat-label" style="margin:4px 0;">
                        {player_position} · {sim_comp_label}
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:10px;">
                        <span class="profile-summary-stat-label">Distance</span>
                        <span class="profile-summary-stat-value accent">{dist_label}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            sim_pid = sim_player.get("player_id")
            try:
                sim_pid_int = int(sim_pid) if pd.notna(sim_pid) else None
            except (TypeError, ValueError):
                sim_pid_int = None
            if sim_pid_int is not None and st.button("View", key=f"sim_{sim_pid_int}_{i}", use_container_width=True):
                st.session_state["profile_player_id"] = sim_pid_int
                st.rerun()
else:
    st.info("Could not load similar players. Use **Find players** to explore the database.")

# Profile report export (HTML)
st.markdown("---")
st.markdown("<div class='section-header'>📤 Export</div>", unsafe_allow_html=True)
_report_lines = [
    f"<h1>{player_name}</h1>",
    f"<p>{POSITION_NAMES.get(player_position, player_position)} · {chosen_team} · {chosen_row.get('league_name', '')} {chosen_season}</p>",
    f"<p>Age: {int(prow.get('age_at_season_start', 0))} · Apps: {int(prow.get('appearances', 0))} · Mins: {int(prow.get('total_minutes', 0)):,} · Rating: {prow.get('avg_rating', 0):.2f}</p>",
]
profile_html = "<html><body>" + "\n".join(_report_lines) + "</body></html>"
st.download_button(
    "⬇️ Download profile report (HTML)",
    data=profile_html,
    file_name=f"profile_{player_id}_{chosen_season}.html",
    mime="text/html",
    key="profile_export_html",
)

# Data attribution
st.markdown("---")
st.markdown("<div class='section-header'>Coverage</div>", unsafe_allow_html=True)
st.markdown("<div class='kpi-accent' aria-hidden='true'></div>", unsafe_allow_html=True)
st.markdown(
    f'<p class="data-attribution">Data: SofaScore. Percentiles vs {pool_label}. Use <strong>Find players</strong> to change scope.</p>',
    unsafe_allow_html=True,
)

# Footer navigation
st.markdown("---")
st.markdown("<div class='section-header'>Navigate</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("← Back to Find Players", use_container_width=True):
        st.switch_page("pages/8_🔎_Discover.py")
with col2:
    if st.button("⚖️ Compare", use_container_width=True):
        st.switch_page("pages/3_⚖️_Compare.py")
with col3:
    if st.button("🎯 Shortlist", use_container_width=True):
        st.switch_page("pages/4_🎯_Shortlist.py")
