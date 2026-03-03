"""Tactics Dashboard — Team Directory.

Browse and filter teams by tactical style, league, and performance.
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from dashboard.utils.data import (
    load_team_season_stats,
    load_tactical_profiles,
)
try:
    from dashboard.utils.data import get_team_wdl, get_team_form
except ImportError:
    get_team_wdl = lambda team_name, season, comp: {}
    get_team_form = lambda team_name, season, comp, n=5: {"form_string": "", "points": 0, "W": 0, "D": 0, "L": 0}

# Defined here so the page works even if data.py doesn't expose it (path/cache issues)
@st.cache_data(show_spinner=False, ttl=3600)
def get_filtered_teams_tactics(
    season_filter: tuple,
    league_filter: tuple,
    style_filter: str,
    search_team: str,
) -> pd.DataFrame:
    """Return filtered and aggregated team-season list for Tactics Directory."""
    team_stats = load_team_season_stats()
    tactical_df = load_tactical_profiles()
    if team_stats.empty:
        return pd.DataFrame()
    df = team_stats.copy()
    if season_filter:
        df = df[df["season"].isin(list(season_filter))]
    if league_filter:
        df = df[df["competition_slug"].isin(list(league_filter))]
    if search_team and search_team.strip():
        df = df[df["team_name"].str.contains(search_team.strip(), case=False, na=False)]
    if style_filter and style_filter != "Any" and not tactical_df.empty:
        style_cols = {
            "High Pressing": "pressing_index",
            "Possession-Based": "possession_index",
            "Direct Play": "directness_index",
            "Aerial Play": "aerial_index",
            "Wing Play": "crossing_index",
        }
        col = style_cols.get(style_filter)
        if col and col in tactical_df.columns:
            high = tactical_df[tactical_df[col] > 60]["team_name"].unique()
            df = df[df["team_name"].isin(high)]
    # Aggregate per (team_name, season) so sort/display use all competitions (match radar)
    sum_cols = [c for c in ["goals_for", "goals_against", "xg_for_total", "xg_against_total", "matches_total", "matches_home", "matches_away"] if c in df.columns]
    team_season_agg = []
    for (team_name, season), grp in df.groupby(["team_name", "season"]):
        row = grp.iloc[0].to_dict()
        row["competitions"] = grp["competition_slug"].tolist()
        for col in sum_cols:
            row[col] = grp[col].sum()
        # Position is per-competition; keep first (or best/min if numeric)
        if "position_ordinal" in grp.columns:
            pos_vals = grp["position_ordinal"].dropna()
            if len(pos_vals) and pd.api.types.is_numeric_dtype(pos_vals):
                row["position_ordinal"] = pos_vals.min()
            else:
                row["position_ordinal"] = grp["position_ordinal"].iloc[0]
        team_season_agg.append(row)
    return pd.DataFrame(team_season_agg)

from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, TACTICAL_INDEX_LABELS, LEAGUE_SLUGS,
)
from dashboard.tactics.components.tactical_components import (
    TACTICAL_RADAR_INDICES,
    normalize_tactical_radar_to_100,
)
from dashboard.utils.scope import (
    filter_to_default_scope,
    CURRENT_SEASON,
    DEFAULT_COMPETITION_SLUGS,
)
from dashboard.utils.percentiles import get_percentile_zscore
from dashboard.utils.sidebar import render_sidebar

# Page config
st.set_page_config(
    page_title="Team Directory · Tactics",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar()

# Load data
with st.spinner("Loading team data…"):
    team_stats = load_team_season_stats()
    tactical_df = load_tactical_profiles()

# Page header
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">🏟️ Team Directory</div>
        <div class="page-hero-sub">
            Filter by league and tactical style, then open a Profile or prepare for a matchup.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Filters — one row: League | Season | Style | Search | Reset
# ---------------------------------------------------------------------------
if team_stats.empty:
    all_comps = []
    avail_seasons = []
else:
    all_comps = sorted(team_stats["competition_slug"].unique())
    avail_seasons = sorted(team_stats["season"].unique(), reverse=True)
default_leagues = [c for c in DEFAULT_COMPETITION_SLUGS if c in all_comps]

# Restore saved scope when returning from Profile / Prep
if "dir_saved_league" in st.session_state and "dir_league" not in st.session_state:
    st.session_state["dir_league"] = st.session_state["dir_saved_league"]
if "dir_saved_season" in st.session_state and "dir_season" not in st.session_state:
    st.session_state["dir_season"] = st.session_state["dir_saved_season"]

style_filters = {
    "High Pressing": "pressing_index",
    "Possession-Based": "possession_index",
    "Direct Play": "directness_index",
    "Aerial Play": "aerial_index",
    "Wing Play": "crossing_index",
}

a, b, c, d, e = st.columns([2, 1, 1, 1, 0.4])
with a:
    league_filter = st.multiselect(
        "League",
        options=all_comps,
        default=st.session_state.get("dir_league", default_leagues),
        format_func=lambda x: f"{COMP_FLAGS.get(x, '')} {COMP_NAMES.get(x, x)}",
        key="dir_league",
    )
with b:
    _season_default = [CURRENT_SEASON] if CURRENT_SEASON in (avail_seasons or []) else []
    season_filter = st.multiselect(
        "Season",
        options=avail_seasons or [],
        default=st.session_state.get("dir_season", _season_default),
        key="dir_season",
        placeholder="Season",
    )
with c:
    style_filter = st.selectbox(
        "Tactical style",
        options=["Any"] + list(style_filters.keys()),
        index=0,
        key="dir_style",
    )
with d:
    search_team = st.text_input("Search team", placeholder="Team name", key="dir_search")
with e:
    if st.button("Reset", key="dir_reset", help="Current season + default leagues"):
        st.session_state["dir_league"] = default_leagues
        st.session_state["dir_season"] = [CURRENT_SEASON] if CURRENT_SEASON in (avail_seasons or []) else []
        st.rerun()

st.divider()

# Apply filters
filtered_teams = get_filtered_teams_tactics(
    tuple(season_filter or []),
    tuple(league_filter or []),
    style_filter or "Any",
    (search_team or "").strip(),
)

if not filtered_teams.empty and "xg_for_total" in filtered_teams.columns and "xg_against_total" in filtered_teams.columns:
    filtered_teams = filtered_teams.copy()
    filtered_teams["xg_diff"] = filtered_teams["xg_for_total"].fillna(0) - filtered_teams["xg_against_total"].fillna(0)

# ---------------------------------------------------------------------------
# Results bar: sort and per page
# ---------------------------------------------------------------------------
# All radar axes as sort options (normalized 0–100) so sort order matches the radars
sort_options = {
    "League position": "position_ordinal",
    "Team name": "team_name",
    "Goals for": "goals_for",
    "Goals against": "goals_against",
    "xG For": "xg_for_total",
    "xG Diff": "xg_diff",
    "Possession": "possession_avg",
    "Directness": "_tac_directness_index",
    "Pressing": "_tac_pressing_index",
    "Aerial": "_tac_aerial_index",
    "Crossing": "_tac_crossing_index",
    "Chance Creation": "_tac_chance_creation_index",
    "Defensive": "_tac_defensive_solidity",
}
sort_cols_avail = [
    k for k, v in sort_options.items()
    if (v in filtered_teams.columns if not filtered_teams.empty else v == "team_name")
    or (isinstance(v, str) and v.startswith("_tac_") and not tactical_df.empty)
]
if not sort_cols_avail:
    sort_cols_avail = ["Team name"]

# Sort and per page so checkbox doesn’t stretch
# Default sort: xG Diff (descending so best teams first)
if "dir_sort_by" not in st.session_state and "xG Diff" in sort_cols_avail:
    st.session_state["dir_sort_by"] = "xG Diff"
if "dir_sort_order" not in st.session_state:
    st.session_state["dir_sort_order"] = "Descending" if st.session_state.get("dir_sort_by") == "xG Diff" else "Ascending"

r1, r2, r3 = st.columns([2, 1, 1])
with r1:
    sort_by_label = st.selectbox("Sort by", options=sort_cols_avail, key="dir_sort_by")
with r2:
    sort_order_label = st.selectbox("Order", options=["Ascending", "Descending"], key="dir_sort_order")
with r3:
    TEAMS_PAGE_SIZE = st.selectbox("Per page", options=[12, 24, 48], index=1, key="dir_page_size")

sort_asc = sort_order_label == "Ascending"
sort_col = sort_options.get(sort_by_label, "team_name")

# Map sort column to tactical index key and its position in TACTICAL_RADAR_INDICES (for normalized value)
def _tactical_index_position(key: str):
    for i, (k, _) in enumerate(TACTICAL_RADAR_INDICES):
        if k == key:
            return i
    return 0

# Compute normalized 0–100 for a tactical index for each row (same logic as radar) so sort order matches radar
def _add_normalized_tactical_column(filtered_teams, tactical_df, index_key: str, col_name: str):
    if tactical_df.empty or index_key not in tactical_df.columns or "competitions" not in filtered_teams.columns:
        return filtered_teams, None
    idx_pos = _tactical_index_position(index_key)
    norm_list = []
    for _, row in filtered_teams.iterrows():
        comps = row.get("competitions") or []
        if not comps:
            norm_list.append(np.nan)
            continue
        tac_row = tactical_df[
            (tactical_df["team_name"] == row["team_name"]) &
            (tactical_df["season"] == row["season"]) &
            (tactical_df["competition_slug"].isin(comps))
        ]
        if tac_row.empty:
            norm_list.append(np.nan)
            continue
        tac_data = tac_row.mean(numeric_only=True).to_dict() if len(tac_row) > 1 else tac_row.iloc[0]
        pool = tactical_df[(tactical_df["season"] == row["season"]) & (tactical_df["competition_slug"].isin(comps))]
        if pool.empty:
            norm_list.append(np.nan)
            continue
        norm_vals = normalize_tactical_radar_to_100(tac_data, pool, TACTICAL_RADAR_INDICES)
        norm_list.append(norm_vals[idx_pos] if norm_vals and idx_pos < len(norm_vals) else np.nan)
    out = filtered_teams.copy()
    out[col_name] = norm_list
    return out, col_name

# Possession: use normalized so order matches radar
if sort_col == "possession_avg" and not filtered_teams.empty:
    filtered_teams, new_col = _add_normalized_tactical_column(filtered_teams, tactical_df, "possession_index", "_norm_possession")
    if new_col:
        sort_col = new_col

# Tactical: [style] – use normalized so order matches radar (not raw one-comp value)
if sort_col.startswith("_tac_") and not filtered_teams.empty:
    tac_col = sort_col.replace("_tac_", "")
    filtered_teams, new_col = _add_normalized_tactical_column(filtered_teams, tactical_df, tac_col, f"_norm_tac_{tac_col}")
    if new_col:
        sort_col = new_col
    else:
        # Fallback: merge with raw tactical (one row per team-season)
        merged = filtered_teams.merge(
            tactical_df[["team_name", "season", tac_col]].drop_duplicates(subset=["team_name", "season"]),
            on=["team_name", "season"],
            how="left",
        )
        filtered_teams = merged
        sort_col = tac_col

if sort_col in filtered_teams.columns and not filtered_teams.empty:
    filtered_teams = filtered_teams.sort_values(sort_col, ascending=sort_asc, na_position="last").reset_index(drop=True)

# ---------------------------------------------------------------------------
# Results: Teams header + pagination + grid
# ---------------------------------------------------------------------------
saved_page = st.session_state.get("dir_saved_page")
if saved_page is not None and isinstance(saved_page, int):
    p = max(0, saved_page)
    st.session_state["team_directory_page"] = p
    st.session_state["dir_page_jump"] = p + 1
if "team_directory_page" not in st.session_state:
    st.session_state["team_directory_page"] = 0
total_teams = len(filtered_teams)
total_pages = max(1, (total_teams + TEAMS_PAGE_SIZE - 1) // TEAMS_PAGE_SIZE)
current_page = st.session_state["team_directory_page"]
current_page = max(0, min(current_page, total_pages - 1))
st.session_state["team_directory_page"] = current_page

if filtered_teams.empty:
    st.markdown(f"<div class='section-header'>📋 Teams (0)</div>", unsafe_allow_html=True)
    st.info("No teams match your filters. Try widening **league** or **season**.")
else:
    start = current_page * TEAMS_PAGE_SIZE
    end = min(start + TEAMS_PAGE_SIZE, total_teams)
    teams_display = filtered_teams.iloc[start:end]
    if "dir_show_radars" not in st.session_state:
        st.session_state["dir_show_radars"] = True

    # Section title on its own line, then one bar: range | pagination | radars
    st.markdown(f"<div class='section-header'>📋 Teams ({total_teams})</div>", unsafe_allow_html=True)
    bar1, bar2, bar3 = st.columns([1.2, 2, 0.6])
    with bar1:
        st.caption(f"**{start + 1}–{end}** of **{total_teams}**")
    with bar2:
        if total_pages > 1:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if st.button("← Prev", key="dir_prev", disabled=(current_page == 0)):
                    st.session_state["team_directory_page"] = current_page - 1
                    st.session_state["dir_page_jump"] = current_page  # 1-based
                    st.rerun()
            with c2:
                page_choice = st.selectbox(
                    "Page",
                    options=list(range(1, total_pages + 1)),
                    index=current_page,
                    key="dir_page_jump",
                    label_visibility="collapsed",
                )
                if page_choice != current_page + 1:
                    st.session_state["team_directory_page"] = page_choice - 1
                    st.session_state["dir_page_jump"] = page_choice
                    st.rerun()
            with c3:
                if st.button("Next →", key="dir_next", disabled=(current_page >= total_pages - 1)):
                    st.session_state["team_directory_page"] = current_page + 1
                    st.session_state["dir_page_jump"] = current_page + 2  # 1-based
                    st.rerun()
    with bar3:
        show_radars = st.checkbox(
            "Radars",
            value=st.session_state["dir_show_radars"],
            key="dir_radars_cb",
            help="Show tactical radars (0–100 vs same league/season)",
        )
    st.session_state["dir_show_radars"] = show_radars

    # Create rows of 3 teams each
    for i in range(0, len(teams_display), 3):
        cols = st.columns(min(3, len(teams_display) - i))
        
        for j, (_, team) in enumerate(teams_display.iloc[i:i+3].iterrows()):
            with cols[j]:
                team_name = team.get("team_name", "Unknown")
                season = team.get("season", "")
                position = team.get("position_ordinal", "?")
                matches = int(team.get("matches_total", 0))
                comps = team.get("competitions", [])
                first_comp = comps[0] if comps else ""
                # On card show only leagues (no continental or cup competitions)
                leagues_only = [c for c in comps if c in LEAGUE_SLUGS]
                comps_display = (leagues_only[:2] if leagues_only else comps[:2])
                comp_labels = " · ".join(f"{COMP_FLAGS.get(c, '🏆')} {COMP_NAMES.get(c, c)}" for c in comps_display)
                if len(comps_display) < len(leagues_only) or (not leagues_only and len(comps) > 2):
                    comp_labels += " …"
                goals_for = int(team.get("goals_for", 0))
                goals_against = int(team.get("goals_against", 0))
                wdl = get_team_wdl(team_name, season, first_comp) if first_comp else {}
                wdl_str = f"{wdl.get('W', 0)}-{wdl.get('D', 0)}-{wdl.get('L', 0)}" if wdl else "—"
                form_info = get_team_form(team_name, season, first_comp, n=5) if first_comp else {}
                form_str = form_info.get("form_string", "") if isinstance(form_info, dict) else (form_info[0] if isinstance(form_info, tuple) else "")
                # Get tactical mini-radar: use all competitions (aggregated) when team has multiple, so it matches Profile "All"
                tac_data = None
                if not tactical_df.empty and comps:
                    tac_row = tactical_df[
                        (tactical_df["team_name"] == team_name) &
                        (tactical_df["season"] == season) &
                        (tactical_df["competition_slug"].isin(comps))
                    ]
                    if not tac_row.empty:
                        tac_data = tac_row.mean(numeric_only=True).to_dict() if len(tac_row) > 1 else tac_row.iloc[0]
                        if isinstance(tac_data, dict):
                            tac_data["team_name"] = team_name
                            tac_data["season"] = season
                
                # Team card
                st.markdown(
                    f"""
                    <div style="background:#161B22;padding:12px;border-radius:8px;border:1px solid #30363D;margin-bottom:10px;">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                            <div style="font-size:1rem;font-weight:600;color:#F0F6FC;">{team_name}</div>
                            <span style="background:#C9A84020;color:#C9A840;padding:2px 6px;border-radius:6px;font-size:0.7rem;">#{position}</span>
                        </div>
                        <div style="font-size:0.75rem;color:#8B949E;margin-bottom:4px;">{comp_labels} · {season}</div>
                        <div style="font-size:0.7rem;color:#8B949E;margin-bottom:6px;">W-D-L {wdl_str} · Form {form_str or '—'}</div>
                        <div style="display:flex;gap:10px;flex-wrap:wrap;font-size:0.75rem;">
                            <span title="Matches"><span style="color:#8B949E;">M</span> <span style="color:#F0F6FC;">{matches}</span></span>
                            <span title="Goals for/against"><span style="color:#8B949E;">GF</span> <span style="color:#F0F6FC;">{goals_for}</span> <span style="color:#8B949E;">GA</span> <span style="color:#F0F6FC;">{goals_against}</span></span>
                            <span title="Expected goals"><span style="color:#8B949E;">xG</span> <span style="color:#F0F6FC;">{team.get('xg_for_total', 0):.1f}</span>/<span style="color:#F0F6FC;">{team.get('xg_against_total', 0):.1f}</span></span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                # Mini tactical radar (only if toggle on and data available). Pool = same league/season so scales are meaningful per axis (e.g. Defensive doesn’t get stretched by cross-league outliers).
                if show_radars and tac_data is not None:
                    pool = tactical_df[
                        (tactical_df["season"] == season) &
                        (tactical_df["competition_slug"].isin(comps))
                    ] if comps else pd.DataFrame()
                    if pool.empty:
                        pool = tactical_df
                    radar_vals = normalize_tactical_radar_to_100(tac_data, pool, TACTICAL_RADAR_INDICES)
                    labels = [l for _, l in TACTICAL_RADAR_INDICES]
                    if radar_vals:
                        fig = go.Figure()
                        fig.add_trace(go.Scatterpolar(
                            r=radar_vals + [radar_vals[0]],
                            theta=labels + [labels[0]],
                            fill="toself",
                            fillcolor="rgba(201,168,64,0.2)",
                            line=dict(color="#C9A840", width=1.5),
                        ))
                        fig.update_layout(
                            polar=dict(
                                bgcolor="#161B22",
                                radialaxis=dict(visible=False, range=[0, 100]),
                                angularaxis=dict(tickfont=dict(size=8, color="#8B949E")),
                            ),
                            paper_bgcolor="#161B22",
                            margin=dict(l=20, r=20, t=20, b=20),
                            height=120,
                            showlegend=False,
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"radar_{i}_{j}")
                
                # Action buttons (one team-season; competition filter is on Profile / Prep)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📐 Profile", key=f"profile_{i}_{j}", use_container_width=True):
                        st.session_state["selected_team"] = {
                            "name": team_name,
                            "season": season,
                            "competitions": comps,
                        }
                        st.session_state["dir_saved_season"] = season_filter
                        st.session_state["dir_saved_league"] = league_filter
                        st.session_state["dir_saved_style"] = style_filter
                        st.session_state["dir_saved_search"] = search_team
                        st.session_state["dir_saved_page"] = current_page
                        st.switch_page("pages/10_📐_Tactical_Profile.py")
                with c2:
                    if st.button("⚔️ Prep", key=f"prep_{i}_{j}", use_container_width=True):
                        st.session_state["opponent_team"] = {
                            "name": team_name,
                            "season": season,
                            "competitions": comps,
                        }
                        st.session_state["dir_saved_season"] = season_filter
                        st.session_state["dir_saved_league"] = league_filter
                        st.session_state["dir_saved_style"] = style_filter
                        st.session_state["dir_saved_search"] = search_team
                        st.session_state["dir_saved_page"] = current_page
                        st.switch_page("pages/11_⚔️_Opponent_Prep.py")

# ---------------------------------------------------------------------------
# Tactical Style Leaders (default scope) — in expander to keep page focused
# ---------------------------------------------------------------------------
tactical_scope = filter_to_default_scope(tactical_df) if not tactical_df.empty else pd.DataFrame()
if not tactical_scope.empty:
    st.markdown("---")
    with st.expander("🎯 Tactical style leaders (top 5 per style)", expanded=False):
        st.caption(f"Current season ({CURRENT_SEASON}), default scope. Value = league percentile (z-score).")
        style_cols = st.columns(3)
        leader_style_map = [
            ("High Pressing", "pressing_index"),
            ("Possession", "possession_index"),
            ("Direct Play", "directness_index"),
        ]

        def _leader_row(team_name, raw_val, comp_slug, style_key, idx, pool_series):
            league_name = COMP_NAMES.get(comp_slug, comp_slug)
            flag = COMP_FLAGS.get(comp_slug, "🏆")
            if pool_series is not None and len(pool_series) >= 2 and pd.notna(raw_val):
                pct_val = get_percentile_zscore(raw_val, pool_series.dropna())
                disp = f"{pct_val:.0f}" if pd.notna(pct_val) else f"{raw_val:.0f}"
            else:
                disp = f"{raw_val:.0f}"
            if st.button(
                f"{team_name} — {flag} {league_name} ({disp})",
                key=f"leader_{style_key}_{idx}",
                use_container_width=True,
            ):
                st.session_state["selected_team"] = {
                    "name": team_name,
                    "season": CURRENT_SEASON,
                    "competitions": tactical_scope[tactical_scope["team_name"] == team_name]["competition_slug"].unique().tolist() or [comp_slug],
                }
                st.session_state["dir_saved_season"] = season_filter
                st.session_state["dir_saved_league"] = league_filter
                st.session_state["dir_saved_style"] = style_filter
                st.session_state["dir_saved_search"] = search_team
                st.switch_page("pages/10_📐_Tactical_Profile.py")

        for col_idx, (style_label, col_name) in enumerate(leader_style_map):
            if col_name not in tactical_scope.columns:
                continue
            with style_cols[col_idx]:
                st.markdown(f"**{style_label}**")
                leaders = tactical_scope.nlargest(5, col_name)[["team_name", col_name, "competition_slug"]]
                for idx, (_, team) in enumerate(leaders.iterrows()):
                    c = team["competition_slug"]
                    pool_series = tactical_scope[tactical_scope["competition_slug"] == c][col_name]
                    _leader_row(team["team_name"], team[col_name], c, f"{col_name}_{idx}", idx, pool_series)

# Footer
st.markdown("---")
if st.button("← Back to Tactics Home", use_container_width=True):
    st.switch_page("app.py")
