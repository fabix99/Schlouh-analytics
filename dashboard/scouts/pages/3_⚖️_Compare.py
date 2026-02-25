"""Scouts Dashboard — Compare Players.

Deep comparison (2–5 players) with cross-league adjustment and tactical fit analysis.
"""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dashboard.utils.data import (
    load_enriched_season_stats,
    load_player_consistency,
    load_opponent_context_summary,
    load_tactical_profiles,
    load_team_season_stats,
    format_metric,
    format_rating,
    format_per90,
    format_percentile,
)
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, POSITION_NAMES, POSITION_ORDER,
    RADAR_STATS_BY_POSITION, PLAYER_COLORS, MIN_MINUTES_DEFAULT,
)
from dashboard.utils.scope import filter_to_default_scope, CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.utils.filters import FilterPanel, apply_filters
from dashboard.utils.charts import radar_chart, _hex_to_rgba
from dashboard.utils.projections import project_stat_to_baseline, get_league_quality_score
from dashboard.utils.fit_score import calculate_fit_score
from dashboard.utils.badges import calculate_badges
from dashboard.scouts.layout import render_scouts_sidebar, load_shortlist_from_file
from dashboard.scouts.compare_state import (
    load_scouts_compare_list,
    load_scouts_compare_entries,
    save_scouts_compare_list,
)

# Compare limits
MIN_COMPARE = 2
MAX_COMPARE = 5

# Profile presets: (label, positions, age_max, age_min, stat_constraints)
# stat_constraints: list of (column, min_value) e.g. ("expectedGoals_per90", 0.2)
COMPARE_PROFILES = [
    ("Any", [], None, None, []),
    ("Young goalscorer", ["F", "AM"], 23, None, [("expectedGoals_per90", 0.15)]),
    ("Creative midfielder", ["M", "AM"], None, None, [("keyPass_per90", 1.0), ("expectedAssists_per90", 0.1)]),
    ("Ball-winning midfielder", ["M", "DM"], None, None, [("totalTackle_per90", 1.5), ("interceptionWon_per90", 0.5)]),
    ("Box-to-box", ["M"], None, None, [("total_minutes", 900), ("avg_rating", 6.8)]),
    ("Winger / direct", ["F", "AM"], None, None, [("expectedAssists_per90", 0.12), ("keyPass_per90", 0.8)]),
    ("Target / aerial", ["F", "D"], None, None, [("aerialWon_per90", 2.0)]),
]

def _apply_profile_to_df(df: pd.DataFrame, profile_key: str) -> pd.DataFrame:
    """Apply profile preset filters. profile_key is the label (e.g. 'Young goalscorer')."""
    if not profile_key or profile_key == "Any":
        return df
    for label, positions, age_max, age_min, stat_constraints in COMPARE_PROFILES:
        if label != profile_key:
            continue
        out = df.copy()
        if positions:
            out = out[out["player_position"].isin(positions)]
        if age_max is not None and "age_at_season_start" in out.columns:
            out = out[out["age_at_season_start"] <= age_max]
        if age_min is not None and "age_at_season_start" in out.columns:
            out = out[out["age_at_season_start"] >= age_min]
        for col, min_val in stat_constraints:
            if col in out.columns:
                out = out[out[col].fillna(0) >= min_val]
        return out
    return df

# Page config
st.set_page_config(
    page_title="Compare Players · Scouts",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_scouts_sidebar()

# Sync shortlist from file
st.session_state["shortlist"] = load_shortlist_from_file()

# URL state: ?compare=id1,id2,id3 to open with those players
qp_compare = st.query_params.get("compare")
if qp_compare:
    try:
        ids_from_url = [int(x.strip()) for x in qp_compare.split(",") if x.strip()][:MAX_COMPARE]
        if ids_from_url and (not st.session_state.get("compare_list") or st.session_state.get("compare_from_url")):
            st.session_state.compare_list = ids_from_url
            st.session_state.compare_from_url = True
    except ValueError:
        pass

# Initialize session state (persist across refresh)
if "compare_list" not in st.session_state:
    st.session_state.compare_list = load_scouts_compare_list()
if "compare_seasons" not in st.session_state:
    entries = load_scouts_compare_entries()
    st.session_state.compare_seasons = {
        e["player_id"]: {"season": e["season"], "competition": e["competition_slug"]}
        for e in entries if e.get("player_id")
    }
    if not st.session_state.compare_seasons and st.session_state.compare_list:
        st.session_state.compare_seasons = {}

# Load data
with st.spinner("Loading comparison data…"):
    df_all = load_enriched_season_stats()
    consistency_df = load_player_consistency()
    opponent_df = load_opponent_context_summary()
    tactical_df = load_tactical_profiles()
    team_stats_df = load_team_season_stats()

# Page header
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">⚖️ Compare Players</div>
        <div class="page-hero-sub">
            Deep comparison with cross-league adjustment and tactical fit analysis.
            Select between 2 and 5 players to compare side-by-side.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Player Selection
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🎯 Select Players to Compare</div>", unsafe_allow_html=True)

# Filters and profile (build candidate pool)
with st.expander("🔧 Filters & profile", expanded=True):
    st.caption("Narrow by league, season, position, age and minutes. Optionally pick a profile to find specific types of players.")
    # Default scope for compare picker (same as Discover)
    if "compare_picker_leagues" not in st.session_state:
        avail = sorted(df_all["competition_slug"].unique())
        st.session_state["compare_picker_leagues"] = [s for s in DEFAULT_COMPETITION_SLUGS if s in avail]
    if "compare_picker_seasons" not in st.session_state:
        st.session_state["compare_picker_seasons"] = [CURRENT_SEASON] if CURRENT_SEASON in df_all["season"].astype(str).unique() else []
    panel = FilterPanel(
        df_all, "compare_picker",
        show_top5_toggle=True,
        show_age=True,
        show_teams=True,
        default_min_minutes=MIN_MINUTES_DEFAULT,
    )
    filter_config = panel.render()
    profile_label = st.selectbox(
        "Profile (optional)",
        options=[p[0] for p in COMPARE_PROFILES],
        key="compare_profile",
        help="Pre-set filters for role types (e.g. Young goalscorer, Creative midfielder).",
    )

# Build candidate pool: apply filters then profile
df_candidates = apply_filters(df_all, filter_config)
df_candidates = _apply_profile_to_df(df_candidates, profile_label)
# One row per player (best season by minutes) for browse/list
if not df_candidates.empty:
    idx_best = df_candidates.groupby("player_id")["total_minutes"].idxmax()
    df_candidates_one = df_candidates.loc[idx_best].sort_values("avg_rating", ascending=False).reset_index(drop=True)
else:
    df_candidates_one = df_candidates

# Show current compare queue
if st.session_state.compare_list:
    n_selected = len(st.session_state.compare_list)
    st.markdown(f"**Current queue:** {n_selected}/{MAX_COMPARE} players selected")
    
    # Display selected players with season/comp selector and remove button each
    selected_cols = st.columns(len(st.session_state.compare_list))
    for i, player_id in enumerate(st.session_state.compare_list):
        player_rows = df_all[df_all["player_id"] == player_id]
        stored = st.session_state.compare_seasons.get(player_id, {})
        s, c = stored.get("season"), stored.get("competition")
        player_info = None
        if s and c:
            match = player_rows[(player_rows["season"] == s) & (player_rows["competition_slug"] == c)]
            if not match.empty:
                player_info = match.iloc[0]
        if player_info is None:
            default_scope_rows = player_rows[
                (player_rows["season"] == CURRENT_SEASON) &
                (player_rows["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS))
            ]
            player_info = (default_scope_rows.iloc[0] if not default_scope_rows.empty else player_rows.sort_values("season", ascending=False).iloc[0])
            if player_id not in st.session_state.compare_seasons or not st.session_state.compare_seasons[player_id].get("season"):
                st.session_state.compare_seasons[player_id] = {"season": str(player_info.get("season", "")), "competition": str(player_info.get("competition_slug", ""))}
                save_scouts_compare_list(st.session_state.compare_list, st.session_state.compare_seasons)
        opts = player_rows[["season", "competition_slug", "league_name"]].drop_duplicates()
        opts["label"] = opts.apply(lambda r: f"{COMP_FLAGS.get(r['competition_slug'], '🏆')} {r['league_name']} {r['season']}", axis=1)
        option_labels = opts["label"].tolist()
        option_keys = list(zip(opts["season"], opts["competition_slug"]))
        current_label = f"{COMP_FLAGS.get(player_info.get('competition_slug'), '🏆')} {player_info.get('league_name')} {player_info.get('season')}"
        idx_sel = next((j for j, lab in enumerate(option_labels) if lab == current_label), 0)
        with selected_cols[i]:
            st.markdown(
                f"""
                <div style="background:#161B22;padding:10px;border-radius:6px;border:1px solid #C9A840;margin-bottom:6px;">
                    <div style="font-weight:600;color:#F0F6FC;">{player_info['player_name']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            sel = st.selectbox("Season", option_labels, index=min(idx_sel, len(option_labels) - 1), key=f"compare_sel_{player_id}", label_visibility="collapsed")
            if sel and option_labels:
                j = option_labels.index(sel)
                new_s, new_c = option_keys[j]
                if st.session_state.compare_seasons.get(player_id, {}).get("season") != new_s or st.session_state.compare_seasons.get(player_id, {}).get("competition") != new_c:
                    st.session_state.compare_seasons[player_id] = {"season": new_s, "competition": new_c}
                    save_scouts_compare_list(st.session_state.compare_list, st.session_state.compare_seasons)
                    st.rerun()
            if st.button("✕ Remove", key=f"remove_compare_{player_id}", use_container_width=True):
                st.session_state.compare_list = [p for p in st.session_state.compare_list if p != player_id]
                st.session_state.compare_seasons.pop(player_id, None)
                save_scouts_compare_list(st.session_state.compare_list, st.session_state.compare_seasons)
                st.toast("Removed from compare")
                st.rerun()
    
    # Clear with confirmation
    if st.session_state.get("confirm_clear_compare"):
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Yes, clear all", type="primary"):
                st.session_state.compare_list = []
                st.session_state.compare_seasons = {}
                st.session_state.confirm_clear_compare = False
                save_scouts_compare_list([], {})
                st.toast("Compare list cleared")
                st.rerun()
        with c2:
            if st.button("Cancel"):
                st.session_state.confirm_clear_compare = False
                st.rerun()
    else:
        if st.button("🗑️ Clear Selection"):
            st.session_state.confirm_clear_compare = True
            st.rerun()

# Player selection interface (show when under max so user can add more)
if len(st.session_state.compare_list) < MAX_COMPARE:
    remaining = MAX_COMPARE - len(st.session_state.compare_list)
    need_more = MIN_COMPARE - len(st.session_state.compare_list)
    if need_more > 0:
        st.markdown(f"**Select at least {need_more} more player(s) to compare (min {MIN_COMPARE}, max {MAX_COMPARE}):**")
    else:
        st.markdown(f"**Add more players (optional, up to {remaining} more):**")
    
    # Helper: accent-insensitive search (e.g. "Mbappe" finds "Mbappé")
    def _normalize_search_text(text):
        if pd.isna(text):
            return ""
        from unicodedata import normalize as unicode_normalize
        return unicode_normalize("NFKD", str(text).lower()).encode("ASCII", "ignore").decode()
    
    n_candidates = df_candidates_one["player_id"].nunique() if not df_candidates_one.empty and "player_id" in df_candidates_one.columns else 0
    st.caption(f"Candidates: **{n_candidates}** players match your filters and profile.")
    search = st.text_input(
        "Search player name:",
        placeholder="e.g. Bellingham, Mbappé (min 2 characters)",
        help="Search within the filtered candidate list. Use filters above to narrow by league, age, position or profile.",
        key="compare_search_input",
    )
    search_clean = (search or "").strip()
    
    if len(search_clean) >= 2:
        norm_names = df_candidates["player_name"].fillna("").apply(_normalize_search_text)
        query_norm = _normalize_search_text(search_clean)
        matches = df_candidates[norm_names.str.contains(query_norm, na=False)]
        matches = matches[["player_id", "player_name", "team", "league_name", "season",
                           "player_position", "competition_slug"]].drop_duplicates("player_id")
        matches = matches.head(15)
        if not matches.empty:
            st.caption(f"Showing up to 15 results from your filtered list. Select a player to add.")
            for idx, player in matches.iterrows():
                cols = st.columns([4, 1])
                with cols[0]:
                    pos_label = POSITION_NAMES.get(player["player_position"], player["player_position"])
                    st.markdown(
                        f"""
                        <div style="padding:8px;background:#161B22;border-radius:4px;border:1px solid #30363D;margin:4px 0;">
                            <span style="font-weight:500;color:#F0F6FC;">{player['player_name']}</span>
                            <span style="color:#8B949E;font-size:0.8rem;margin-left:10px;">
                                {pos_label} · {player['team']} · {player['league_name']} {player['season']}
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with cols[1]:
                    if player["player_id"] not in st.session_state.compare_list:
                        if st.button("➕ Add", key=f"add_{player['player_id']}_{idx}"):
                            st.session_state.compare_list.append(player["player_id"])
                            st.session_state.compare_seasons[player["player_id"]] = {
                                "season": player["season"],
                                "competition": player["competition_slug"]
                            }
                            save_scouts_compare_list(st.session_state.compare_list, st.session_state.compare_seasons)
                            st.toast(f"Added {player['player_name']} to compare")
                            st.rerun()
        else:
            st.info("No players found in the filtered list. Try relaxing filters, a different name, or clear the search.")
    elif search_clean:
        st.caption("Type at least 2 characters to search.")
    
    # Browse: show top candidates from filtered list (no search required)
    if not df_candidates_one.empty:
        already = set(st.session_state.compare_list)
        browse_df = df_candidates_one[~df_candidates_one["player_id"].isin(already)].head(20)
        if not browse_df.empty:
            st.markdown("**Or browse top candidates** (by rating, from your filters)")
        for i in range(len(browse_df)):
            row = browse_df.iloc[i]
            pid = int(row["player_id"])
            pos_label = POSITION_NAMES.get(row.get("player_position"), row.get("player_position", ""))
            flag = COMP_FLAGS.get(row.get("competition_slug"), "🏆")
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(
                    f"""
                    <div style="padding:8px;background:#161B22;border-radius:4px;border:1px solid #30363D;margin:4px 0;">
                        <span style="font-weight:500;color:#F0F6FC;">{row['player_name']}</span>
                        <span style="color:#8B949E;font-size:0.8rem;margin-left:10px;">
                            {pos_label} · {row['team']} · {flag} {row['league_name']} {row['season']} · Rating {row.get('avg_rating', 0):.2f}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with cols[1]:
                if st.button("➕ Add", key=f"browse_add_{pid}"):
                    st.session_state.compare_list.append(pid)
                    st.session_state.compare_seasons[pid] = {"season": row["season"], "competition": row["competition_slug"]}
                    save_scouts_compare_list(st.session_state.compare_list, st.session_state.compare_seasons)
                    st.toast(f"Added {row['player_name']} to compare")
                    st.rerun()
else:
    st.caption(f"You have {MAX_COMPARE} players selected. Remove one to add a different player.")

if len(st.session_state.compare_list) > 0 and len(st.session_state.compare_list) < MIN_COMPARE:
    st.info(f"Add at least {MIN_COMPARE - len(st.session_state.compare_list)} more player(s) to see the comparison.")

# ---------------------------------------------------------------------------
# Comparison Display (when 2–5 players selected)
# ---------------------------------------------------------------------------
if len(st.session_state.compare_list) >= MIN_COMPARE:
    st.markdown("---")
    st.markdown("<div class='section-header'>📊 Comparison Analysis</div>", unsafe_allow_html=True)
    
    # League adjustment notice
    players_data = []
    leagues = []
    
    for pid in st.session_state.compare_list:
        pseason = st.session_state.compare_seasons.get(pid, {})
        season = pseason.get("season")
        comp = pseason.get("competition")
        
        if season and comp:
            prow = df_all[
                (df_all["player_id"] == pid) &
                (df_all["season"] == season) &
                (df_all["competition_slug"] == comp)
            ]
        else:
            # Prefer current season + default scope when no selection stored
            prow = df_all[df_all["player_id"] == pid]
            default_prow = prow[
                (prow["season"] == CURRENT_SEASON) &
                (prow["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS))
            ]
            if not default_prow.empty:
                prow = default_prow
            else:
                prow = prow.sort_values("season", ascending=False)
        
        if not prow.empty:
            players_data.append(prow.iloc[0])
            leagues.append(prow.iloc[0].get("league_name", "Unknown"))
    
    # Check if cross-league comparison
    unique_leagues = set(leagues)
    if len(unique_leagues) > 1:
        st.info(f"📊 Cross-league comparison detected. Stats adjusted to Premier League equivalent for fairness.")
    
    # -----------------------------------------------------------------------
    # Side-by-side player cards
    # -----------------------------------------------------------------------
    cols = st.columns(len(players_data))
    
    for i, (col, player) in enumerate(zip(cols, players_data)):
        with col:
            # Player card
            flag = COMP_FLAGS.get(player.get("competition_slug"), "🏆")
            pos = POSITION_NAMES.get(player.get("player_position"), "Unknown")
            league_quality = get_league_quality_score(player.get("league_name", "Unknown"))
            
            st.markdown(
                f"""
                <div style="background:#161B22;padding:15px;border-radius:8px;border:2px solid {PLAYER_COLORS[i]};margin-bottom:15px;">
                    <div style="font-size:1.3rem;font-weight:700;color:#F0F6FC;margin-bottom:5px;">{player['player_name']}</div>
                    <div style="font-size:0.85rem;color:#8B949E;margin-bottom:10px;">
                        {pos} · {flag} {player.get('league_name', '')} {player.get('season', '')}
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                        <span style="font-size:0.75rem;color:#8B949E;">League Quality</span>
                        <span style="font-size:0.75rem;color:#C9A840;">{league_quality:.0%}</span>
                    </div>
                    <div style="font-size:0.75rem;color:#8B949E;">Age: {format_metric(player.get('age_at_season_start'), decimals=0)} · Rating: {format_rating(player.get('avg_rating'))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Individual radar
            position = player.get("player_position", "F")
            p_season = player.get("season")
            p_comp = player.get("competition_slug")
            radar_stats = RADAR_STATS_BY_POSITION.get(position, RADAR_STATS_BY_POSITION["F"])

            radar_data = []
            stat_labels = []

            # Pool: same position × season × competition
            pool_mask = df_all["player_position"] == position
            if p_season:
                pool_mask &= df_all["season"] == p_season
            if p_comp:
                pool_mask &= df_all["competition_slug"] == p_comp
            pool = df_all[pool_mask]
            pool_desc = f"{COMP_NAMES.get(p_comp, p_comp)} {p_season} · {POSITION_NAMES.get(position, position)} (n={len(pool)})"

            for stat_key, stat_label in radar_stats[:6]:  # Limit to 6 for clarity
                if stat_key in player.index:
                    raw_val = player[stat_key]
                    if stat_key in pool.columns and not pool.empty:
                        clean = pool[stat_key].dropna()
                        n = len(clean)
                        pct = float(((clean < raw_val).sum() + 0.5 * (clean == raw_val).sum()) / n * 100) if n > 0 else 50.0
                    else:
                        pct = 50.0
                    radar_data.append(pct)
                    stat_labels.append(stat_label)
            
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
                    fillcolor=_hex_to_rgba(PLAYER_COLORS[i], 0.2),
                    line=dict(color=PLAYER_COLORS[i], width=2),
                    hovertemplate="<b>%{theta}</b><br>Percentile: %{r:.0f}<extra></extra>",
                ))
                
                fig.update_layout(
                    polar=dict(
                        bgcolor="#0D1117",
                        radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor="#30363D"),
                        angularaxis=dict(gridcolor="#30363D", tickfont=dict(size=9)),
                    ),
                    paper_bgcolor="#0D1117",
                    plot_bgcolor="#0D1117",
                    font=dict(color="#E6EDF3", size=10),
                    margin=dict(l=30, r=30, t=20, b=20),
                    height=200,
                    showlegend=False,
                )
                
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"ℹ️ {pool_desc}")

            # Badges
            badges = calculate_badges(player, pool)
            if badges:
                positive = [b for b in badges if b.is_positive][:3]  # Top 3
                if positive:
                    st.markdown("**Top badges:**")
                    for badge in positive:
                        st.markdown(
                            f"<span style='font-size:0.75rem;background:rgba(59,185,80,0.2);color:#3FB950;padding:2px 6px;border-radius:10px;margin:2px;'>{badge.icon} {badge.name}</span>",
                            unsafe_allow_html=True,
                        )
    
    # -----------------------------------------------------------------------
    # Combined Radar Comparison
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.markdown("<div class='section-header'>🎯 Combined Radar Comparison</div>", unsafe_allow_html=True)
    
    # Use universal stats for cross-position comparison
    from dashboard.utils.constants import RADAR_STATS_UNIVERSAL
    
    fig_combined = go.Figure()
    
    # For the combined radar, compute each player's percentile within their own
    # season × competition × position pool so shapes are directly comparable.
    for i, player in enumerate(players_data):
        radar_data = []
        stat_labels = []

        position = player.get("player_position", "F")
        p_season = player.get("season")
        p_comp = player.get("competition_slug")
        pool_mask = df_all["player_position"] == position
        if p_season:
            pool_mask &= df_all["season"] == p_season
        if p_comp:
            pool_mask &= df_all["competition_slug"] == p_comp
        pool = df_all[pool_mask]

        for stat_key, stat_label in RADAR_STATS_UNIVERSAL:
            if stat_key in player.index:
                raw_val = player[stat_key]
                if stat_key in pool.columns and not pool.empty:
                    clean = pool[stat_key].dropna()
                    n = len(clean)
                    pct = float(((clean < raw_val).sum() + 0.5 * (clean == raw_val).sum()) / n * 100) if n > 0 else 50.0
                else:
                    pct = 50.0
                radar_data.append(pct)
                stat_labels.append(stat_label)
        
        r_safe = [max(0.0, min(100.0, float(v))) if np.isfinite(v) else 50.0 for v in radar_data]
        radar_data_closed = r_safe + [r_safe[0]]
        stat_labels_closed = stat_labels + [stat_labels[0]]
        
        fig_combined.add_trace(go.Scatterpolar(
            r=radar_data_closed,
            theta=stat_labels_closed,
            fill="toself",
            fillcolor=_hex_to_rgba(PLAYER_COLORS[i], 0.15),
            line=dict(color=PLAYER_COLORS[i], width=2),
            name=player["player_name"],
            hovertemplate="<b>%{fullData.name}</b><br>%{theta}<br>Percentile: %{r:.0f}<extra></extra>",
        ))
    
    fig_combined.update_layout(
        polar=dict(
            bgcolor="#0D1117",
            radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor="#30363D"),
            angularaxis=dict(gridcolor="#30363D", tickfont=dict(size=11)),
        ),
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3"),
        margin=dict(l=44, r=44, t=40, b=40),
        height=400,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(color="#E6EDF3"),
        ),
    )
    
    st.plotly_chart(fig_combined, use_container_width=True)
    st.caption(
        "ℹ️ Each player's percentile is computed within their own season × league × position pool "
        "(same-context ranking). Shapes are comparable — a larger polygon means better relative "
        "performance in that player's own competition."
    )

    # -----------------------------------------------------------------------
    # Comparison Table
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.markdown("<div class='section-header'>📋 Stat Comparison Table</div>", unsafe_allow_html=True)
    
    # Stats to compare
    compare_stats = [
        ("avg_rating", "Rating"),
        ("goals_per90", "Goals/90"),
        ("expectedGoals_per90", "xG/90"),
        ("expectedAssists_per90", "xA/90"),
        ("keyPass_per90", "Key Passes/90"),
        ("bigChanceCreated_per90", "Big Chances/90"),
        ("totalTackle_per90", "Tackles/90"),
        ("interceptionWon_per90", "Interceptions/90"),
        ("duelWon_per90", "Duels Won/90"),
        ("pass_accuracy_pct", "Pass Accuracy %"),
    ]
    
    # Build comparison rows
    comparison_rows = []
    
    for stat_key, stat_label in compare_stats:
        row = {"Stat": stat_label}
        
        for i, player in enumerate(players_data):
            val = player.get(stat_key, np.nan)
            
            # Cross-league adjustment
            if len(unique_leagues) > 1 and not pd.isna(val):
                league = player.get("league_name", "Unknown")
                projection = project_stat_to_baseline(val, league, "Premier League", stat_key)
                adjusted = projection["projected_value"]
                original = projection["original_value"]
                
                if abs(adjusted - original) > 0.01:
                    display_val = f"{adjusted:.2f}*"
                    tooltip = f"Original: {original:.2f} in {league}"
                else:
                    display_val = f"{val:.2f}"
                    tooltip = ""
            else:
                display_val = f"{val:.2f}" if not pd.isna(val) else "N/A"
                tooltip = ""
            
            row[f"Player {i+1}"] = display_val
            row[f"Player {i+1}_tooltip"] = tooltip
        
        comparison_rows.append(row)
    
    comparison_df = pd.DataFrame(comparison_rows)
    
    # Display with highlighting
    def highlight_best(s):
        """Highlight the best value in each row."""
        try:
            vals = pd.to_numeric(s.str.replace('*', ''), errors='coerce')
            if not vals.empty and not vals.isna().all():
                max_idx = vals.idxmax()
                return ['background-color: rgba(59,185,80,0.2)' if i == max_idx else '' for i in s.index]
        except:
            pass
        return [''] * len(s)
    
    styled_df = comparison_df[["Stat"] + [f"Player {i+1}" for i in range(len(players_data))]].style.apply(highlight_best, subset=[f"Player {i+1}" for i in range(len(players_data))])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    if len(unique_leagues) > 1:
        st.caption("* Stats adjusted to Premier League equivalent")
    
    # -----------------------------------------------------------------------
    # Tactical Fit Section
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.markdown("<div class='section-header'>🎯 Tactical Fit Analysis</div>", unsafe_allow_html=True)
    
    # Team selector
    available_teams = tactical_df["team_name"].unique() if tactical_df is not None else []
    
    if len(available_teams) > 0:
        selected_team = st.selectbox("Select team to assess fit:", [""] + list(available_teams))
        
        if selected_team:
            team_profile = tactical_df[tactical_df["team_name"] == selected_team].iloc[0]
            team_stats = team_stats_df[team_stats_df["team_name"] == selected_team]
            
            st.markdown(f"**Fit scores for {selected_team}:**")
            
            fit_cols = st.columns(len(players_data))
            
            for i, (col, player) in enumerate(zip(fit_cols, players_data)):
                with col:
                    position = player.get("player_position", "F")
                    
                    # Calculate fit
                    fit_result = calculate_fit_score(
                        player_data=player,
                        team_data=team_profile,
                        team_tactical_profile=team_profile,
                        position=position
                    )
                    
                    score = fit_result["overall_score"]
                    grade = fit_result["grade"]
                    
                    if score >= 80:
                        color = "#3FB950"
                    elif score >= 60:
                        color = "#C9A840"
                    else:
                        color = "#F85149"
                    
                    st.markdown(
                        f"""
                        <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid {color};margin-bottom:10px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                                <span style="font-weight:600;color:#F0F6FC;">{player['player_name']}</span>
                                <span style="font-size:1.5rem;font-weight:700;color:{color};">{grade}</span>
                            </div>
                            <div style="background:#21262D;border-radius:4px;height:8px;margin-bottom:8px;">
                                <div style="background:{color};border-radius:4px;height:8px;width:{score}%"></div>
                            </div>
                            <div style="font-size:0.85rem;color:#8B949E;">{fit_result['explanation']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    
                    st.caption(fit_result["recommendation"])
    else:
        st.info("Team tactical profiles not available")
    
    # -----------------------------------------------------------------------
    # Consistency Comparison
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.markdown("<div class='section-header'>📊 Consistency Comparison</div>", unsafe_allow_html=True)
    
    consistency_data = []
    
    for player in players_data:
        cons_row = consistency_df[consistency_df["player_id"] == player["player_id"]]
        if not cons_row.empty:
            cons = cons_row.iloc[0]
            consistency_data.append({
                "Player": player["player_name"],
                "Rating CV": cons.get("rating_cv", 0),
                "xG CV": cons.get("xg_per90_cv", 0),
                "Minutes Reliability": cons.get("minutes_reliability", "Unknown"),
            })
    
    if consistency_data:
        cons_df = pd.DataFrame(consistency_data)
        st.dataframe(cons_df, use_container_width=True, hide_index=True)
        st.caption("CV = Coefficient of Variation (lower = more consistent)")

# Export and share (when comparison is shown)
if len(st.session_state.compare_list) >= MIN_COMPARE:
    st.markdown("---")
    st.markdown("<div class='section-header'>📤 Export & share</div>", unsafe_allow_html=True)
    ex1, ex2 = st.columns(2)
    with ex1:
        share_ids = ",".join(str(pid) for pid in st.session_state.compare_list)
        share_query = f"?compare={share_ids}"
        st.text_input("Share link (copy query params)", value=share_query, key="compare_share_url", label_visibility="collapsed")
    with ex2:
        report_lines = ["<h1>Compare</h1>"]
        for p in players_data:
            report_lines.append(f"<p><strong>{p.get('player_name')}</strong> · {p.get('league_name')} {p.get('season')} · Rating {p.get('avg_rating', 0):.2f}</p>")
        compare_html = "<html><body>" + "\n".join(report_lines) + "</body></html>"
        st.download_button("⬇️ Download report (HTML)", data=compare_html, file_name="compare_report.html", mime="text/html", key="compare_export_html")

# Footer navigation
st.markdown("---")
if st.button("← Back to Discover", use_container_width=True):
    st.switch_page("pages/1_🔎_Discover.py")
