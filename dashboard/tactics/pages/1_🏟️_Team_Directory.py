"""Tactics Dashboard — Team Directory.

Browse and filter teams by tactical style, league, and performance.
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

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
    team_season_agg = []
    for (team_name, season), grp in df.groupby(["team_name", "season"]):
        first = grp.iloc[0].to_dict()
        first["competitions"] = grp["competition_slug"].tolist()
        team_season_agg.append(first)
    return pd.DataFrame(team_season_agg)

from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, TACTICAL_INDEX_LABELS,
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
from dashboard.tactics.layout import render_tactics_sidebar

# Page config
st.set_page_config(
    page_title="Team Directory · Tactics",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_tactics_sidebar()

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
            Browse teams by league and tactical style. Find opponents to analyze.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Filters (default: current season + leagues & UEFA only; expand to include more)
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🔍 Filter Teams</div>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    avail_seasons = sorted(team_stats["season"].unique(), reverse=True) if not team_stats.empty else []
    default_seasons = st.session_state.get("dir_saved_season") or ([CURRENT_SEASON] if CURRENT_SEASON in avail_seasons else [])
    if default_seasons and avail_seasons and not all(s in avail_seasons for s in default_seasons):
        default_seasons = [CURRENT_SEASON] if CURRENT_SEASON in avail_seasons else []
    season_filter = st.multiselect(
        "Season:",
        options=avail_seasons,
        default=default_seasons,
        placeholder="All seasons",
        key="dir_season",
        help="Default: current season only.",
    )

with col2:
    all_comps = sorted(team_stats["competition_slug"].unique()) if not team_stats.empty else []
    default_leagues = st.session_state.get("dir_saved_league") or [c for c in DEFAULT_COMPETITION_SLUGS if c in all_comps]
    if default_leagues and all_comps and not all(c in all_comps for c in default_leagues):
        default_leagues = [c for c in DEFAULT_COMPETITION_SLUGS if c in all_comps]
    league_filter = st.multiselect(
        "League / Competition:",
        options=all_comps,
        format_func=lambda x: f"{COMP_FLAGS.get(x, '🏆')} {COMP_NAMES.get(x, x)}",
        default=default_leagues,
        placeholder="All leagues",
        key="dir_league",
        help="Default: leagues + UEFA only. Add cups to include more.",
    )

with col3:
    style_filters = {
        "High Pressing": "pressing_index",
        "Possession-Based": "possession_index",
        "Direct Play": "directness_index",
        "Aerial Play": "aerial_index",
        "Wing Play": "crossing_index",
    }
    style_filter = st.selectbox(
        "Tactical Style:",
        options=["Any"] + list(style_filters.keys()),
        index=0
    )

with col4:
    search_team = st.text_input("Search team:", placeholder="Team name...")

# Apply filters (cached)
filtered_teams = get_filtered_teams_tactics(
    tuple(season_filter or []),
    tuple(league_filter or []),
    style_filter or "Any",
    search_team.strip() if search_team else "",
)

# ---------------------------------------------------------------------------
# Sorting (incl. xG Diff and by tactical index when style filter applied)
# ---------------------------------------------------------------------------
sort_options = {
    "League position": "position_ordinal",
    "Team name": "team_name",
    "Goals for": "goals_for",
    "Goals against": "goals_against",
    "xG For": "xg_for_total",
    "xG Diff": "xg_diff",
    "Possession": "possession_avg",
}
# Add xG Diff column if not present
if not filtered_teams.empty and "xg_for_total" in filtered_teams.columns and "xg_against_total" in filtered_teams.columns:
    filtered_teams = filtered_teams.copy()
    filtered_teams["xg_diff"] = filtered_teams["xg_for_total"].fillna(0) - filtered_teams["xg_against_total"].fillna(0)
if style_filter != "Any" and style_filter in style_filters and not tactical_df.empty and not filtered_teams.empty:
    style_col = style_filters[style_filter]
    if style_col in tactical_df.columns:
        sort_options[f"Tactical: {style_filter}"] = f"_tac_{style_col}"
sort_cols_avail = [k for k, v in sort_options.items() if (v in filtered_teams.columns if not filtered_teams.empty else v == "team_name") or (isinstance(v, str) and v.startswith("_tac_"))]
if not sort_cols_avail:
    sort_cols_avail = ["Team name"]
sort_by_label = st.selectbox("Sort by", options=sort_cols_avail, key="dir_sort_by")
sort_asc = st.checkbox("Ascending", value=(sort_by_label != "xG Diff"), key="dir_sort_asc")
sort_col = sort_options.get(sort_by_label, "team_name")
if sort_col.startswith("_tac_"):
    tac_col = sort_col.replace("_tac_", "")
    merged = filtered_teams.merge(
        tactical_df[["team_name", "season", tac_col]].drop_duplicates(subset=["team_name", "season"]),
        on=["team_name", "season"],
        how="left",
    )
    filtered_teams = merged.sort_values(tac_col, ascending=sort_asc, na_position="last").reset_index(drop=True)
elif sort_col in filtered_teams.columns and not filtered_teams.empty:
    filtered_teams = filtered_teams.sort_values(
        sort_col,
        ascending=sort_asc,
        na_position="last"
    ).reset_index(drop=True)
st.caption(f"Sorted by **{sort_by_label}** ({'ascending' if sort_asc else 'descending'}) · **{len(filtered_teams)}** teams")

# Export filtered list (Consider #66)
if not filtered_teams.empty:
    export_cols = [c for c in ["team_name", "season", "position_ordinal", "matches_total", "goals_for", "goals_against", "xg_for_total", "xg_against_total", "possession_avg"] if c in filtered_teams.columns]
    if export_cols:
        export_df = filtered_teams[export_cols].copy()
        if "competitions" in filtered_teams.columns:
            export_df["competitions"] = filtered_teams["competitions"].apply(lambda x: ";".join(x) if isinstance(x, list) else str(x))
        st.download_button("📥 Download filtered teams (CSV)", data=export_df.to_csv(index=False).encode("utf-8"), file_name="tactics_teams_filtered.csv", mime="text/csv", key="dir_export_csv", use_container_width=False)

# ---------------------------------------------------------------------------
# Display Teams (pagination: page size, jump to page)
# ---------------------------------------------------------------------------
if "dir_page_size" not in st.session_state:
    st.session_state["dir_page_size"] = 24
TEAMS_PAGE_SIZE = st.selectbox("Per page", options=[12, 24, 48], index=1, key="dir_page_size")
saved_page = st.session_state.get("dir_saved_page")
if saved_page is not None and isinstance(saved_page, int):
    st.session_state["team_directory_page"] = max(0, saved_page)
if "team_directory_page" not in st.session_state:
    st.session_state["team_directory_page"] = 0
total_teams = len(filtered_teams)
total_pages = max(1, (total_teams + TEAMS_PAGE_SIZE - 1) // TEAMS_PAGE_SIZE)
current_page = st.session_state["team_directory_page"]
current_page = max(0, min(current_page, total_pages - 1))
st.session_state["team_directory_page"] = current_page

st.markdown(f"<div class='section-header'>📋 Teams ({total_teams})</div>", unsafe_allow_html=True)

# Jump to page
if total_pages > 1:
    jump = st.number_input("Go to page", min_value=1, max_value=total_pages, value=current_page + 1, key="dir_jump")
    if jump != current_page + 1:
        st.session_state["team_directory_page"] = int(jump) - 1
        st.rerun()

if filtered_teams.empty:
    st.info("No teams match your filters. Try widening **league** or **season**.")
else:
    # Paginate
    start = current_page * TEAMS_PAGE_SIZE
    end = min(start + TEAMS_PAGE_SIZE, total_teams)
    teams_display = filtered_teams.iloc[start:end]

    # Pagination controls
    pag_col1, pag_col2, pag_col3 = st.columns([1, 2, 1])
    with pag_col1:
        if st.button("← Previous", key="dir_prev", disabled=(current_page == 0)):
            st.session_state["team_directory_page"] = current_page - 1
            st.rerun()
    with pag_col2:
        st.markdown(
            f"<p style='text-align:center;color:#8B949E;margin:0.5rem 0;'>"
            f"Page {current_page + 1} of {total_pages} · Showing {start + 1}–{end} of {total_teams}</p>",
            unsafe_allow_html=True,
        )
    with pag_col3:
        if st.button("Next →", key="dir_next", disabled=(current_page >= total_pages - 1)):
            st.session_state["team_directory_page"] = current_page + 1
            st.rerun()

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
                comp_labels = " · ".join(f"{COMP_FLAGS.get(c, '🏆')} {COMP_NAMES.get(c, c)}" for c in comps[:3])
                if len(comps) > 3:
                    comp_labels += " …"
                goals_for = int(team.get("goals_for", 0))
                goals_against = int(team.get("goals_against", 0))
                wdl = get_team_wdl(team_name, season, first_comp) if first_comp else {}
                wdl_str = f"{wdl.get('W', 0)}-{wdl.get('D', 0)}-{wdl.get('L', 0)}" if wdl else "—"
                form_info = get_team_form(team_name, season, first_comp, n=5) if first_comp else {}
                form_str = form_info.get("form_string", "") if isinstance(form_info, dict) else (form_info[0] if isinstance(form_info, tuple) else "")
                # Get tactical mini-radar if available (use first competition)
                tac_data = None
                if not tactical_df.empty and first_comp:
                    tac_row = tactical_df[
                        (tactical_df["team_name"] == team_name) &
                        (tactical_df["season"] == season) &
                        (tactical_df["competition_slug"] == first_comp)
                    ]
                    if not tac_row.empty:
                        tac_data = tac_row.iloc[0]
                
                # Team card (one per team-season; competitions shown as tags)
                st.markdown(
                    f"""
                    <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;margin-bottom:10px;height:100%;">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                            <div style="font-size:1.1rem;font-weight:600;color:#F0F6FC;">{team_name}</div>
                            <span style="background:#C9A84020;color:#C9A840;padding:3px 8px;border-radius:10px;font-size:0.75rem;">
                                #{position}
                            </span>
                        </div>
                        <div style="font-size:0.8rem;color:#8B949E;margin-bottom:8px;">
                            {comp_labels} · {season}
                        </div>
                        <div style="font-size:0.75rem;color:#8B949E;margin-bottom:6px;">W-D-L: {wdl_str} · Form: {form_str or '—'}</div>
                        <div style="display:flex;gap:12px;margin-bottom:10px;flex-wrap:wrap;">
                            <div><span style="font-size:0.7rem;color:#8B949E;">M</span> <span style="color:#F0F6FC;">{matches}</span></div>
                            <div><span style="font-size:0.7rem;color:#8B949E;">GF</span> <span style="color:#F0F6FC;">{goals_for}</span></div>
                            <div><span style="font-size:0.7rem;color:#8B949E;">GA</span> <span style="color:#F0F6FC;">{goals_against}</span></div>
                            <div><span style="font-size:0.7rem;color:#8B949E;">xG+</span> <span style="color:#F0F6FC;">{team.get('xg_for_total', 0):.1f}</span></div>
                            <div><span style="font-size:0.7rem;color:#8B949E;">xG-</span> <span style="color:#F0F6FC;">{team.get('xg_against_total', 0):.1f}</span></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                # Mini tactical radar if data available (normalized 0–100 so chart renders correctly)
                if tac_data is not None:
                    pool = tactical_df[
                        (tactical_df["season"] == season) &
                        (tactical_df["competition_slug"] == first_comp)
                    ] if first_comp else pd.DataFrame()
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
                        st.switch_page("pages/2_📐_Tactical_Profile.py")
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
                        st.switch_page("pages/3_⚔️_Opponent_Prep.py")

# ---------------------------------------------------------------------------
# Tactical Style Summary (default scope only)
# ---------------------------------------------------------------------------
tactical_scope = filter_to_default_scope(tactical_df) if not tactical_df.empty else pd.DataFrame()
if not tactical_scope.empty:
    st.markdown("---")
    st.markdown("<div class='section-header'>🎯 Tactical Style Leaders</div>", unsafe_allow_html=True)
    st.caption(f"Current season ({CURRENT_SEASON}), leagues + UEFA only.")
    
    style_cols = st.columns(3)
    
    def _leader_row(team_name, value, comp_slug, style_key, idx):
        league_name = COMP_NAMES.get(comp_slug, comp_slug)
        flag = COMP_FLAGS.get(comp_slug, "🏆")
        if st.button(
            f"{team_name} — {flag} {league_name} ({value:.0f})",
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
            st.switch_page("pages/2_📐_Tactical_Profile.py")

    with style_cols[0]:
        st.markdown("**High Pressing Teams**")
        pressing_leaders = tactical_scope.nlargest(5, "pressing_index")[["team_name", "pressing_index", "competition_slug"]]
        for idx, (_, team) in enumerate(pressing_leaders.iterrows()):
            _leader_row(team["team_name"], team["pressing_index"], team["competition_slug"], "pressing", idx)

    with style_cols[1]:
        st.markdown("**Possession Teams**")
        poss_leaders = tactical_scope.nlargest(5, "possession_index")[["team_name", "possession_index", "competition_slug"]]
        for idx, (_, team) in enumerate(poss_leaders.iterrows()):
            _leader_row(team["team_name"], team["possession_index"], team["competition_slug"], "poss", idx)

    with style_cols[2]:
        st.markdown("**Direct Play Teams**")
        direct_leaders = tactical_scope.nlargest(5, "directness_index")[["team_name", "directness_index", "competition_slug"]]
        for idx, (_, team) in enumerate(direct_leaders.iterrows()):
            _leader_row(team["team_name"], team["directness_index"], team["competition_slug"], "direct", idx)

# Footer
st.markdown("---")
if st.button("← Back to Tactics Home", use_container_width=True):
    st.switch_page("app.py")
