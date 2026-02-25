"""Scouts Dashboard — Player Profile.

Deep scouting report with position-aware sections, radar chart,
percentile toggle, badges, and form visualization.
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

from dashboard.utils.data import (
    load_enriched_season_stats,
    load_rolling_form,
    load_player_consistency,
    load_opponent_context_summary,
    load_scouting_profiles,
    get_similar_players,
    get_player_match_log,
)
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, POSITION_NAMES,
    RADAR_STATS_BY_POSITION, PLAYER_COLORS,
)
from dashboard.utils.scope import CURRENT_SEASON, filter_to_default_scope
from dashboard.utils.charts import radar_chart
from dashboard.utils.badges import calculate_badges, format_badge_for_display
from dashboard.scouts.layout import (
    render_scouts_sidebar,
    load_shortlist_from_file,
    save_shortlist_to_file,
)
from dashboard.scouts.compare_state import load_scouts_compare_list, save_scouts_compare_list

# Page config
st.set_page_config(
    page_title="Player Profile · Scouts",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_scouts_sidebar()

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

def _load_shortlist_for_profile():
    return load_shortlist_from_file()

def _render_player_row(player, key_prefix="row"):
    """Render one player row: card in cols[0], View Profile in cols[1], Quick Add in cols[2]. Caller must use st.columns([4,1,1])."""
    pos_label = POSITION_NAMES.get(player.get("player_position"), player.get("player_position", ""))
    team = player.get("team", "") or "—"
    league = player.get("league_name", "") or "—"
    st.markdown(
        f"""
        <div style="padding:10px;background:#161B22;border-radius:6px;border:1px solid #30363D;">
            <span style="font-weight:600;color:#F0F6FC;">{player.get('player_name', '')}</span>
            <span style="color:#8B949E;font-size:0.85rem;margin-left:10px;">
                {pos_label} · {team} · {league}
            </span>
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
        <div class="page-hero">
            <div class="page-hero-title">📋 Player Profile</div>
            <div class="page-hero-sub">
                Open a player to view their full scouting report — radar, form, badges, and match log.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
                _render_player_row(p, key_prefix="sl")
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
                    _render_player_row(p, key_prefix="sr")
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
            st.info("No players found — try a different name or position.")
    else:
        # No search: show top 20 by rating (default scope) so the list is meaningful
        df_scope = filter_to_default_scope(df_all)
        if not df_scope.empty and "avg_rating" in df_scope.columns and "total_minutes" in df_scope.columns:
            df_scope = df_scope.copy()
            df_scope["_w"] = df_scope["avg_rating"] * df_scope["total_minutes"]
            g = df_scope.groupby("player_id")
            agg = g.agg(total_minutes=("total_minutes", "sum"), _sum_w=("_w", "sum"))
            from dashboard.utils.validation import safe_divide
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
            st.caption(f"Top 20 by season rating ({CURRENT_SEASON}, main leagues + UEFA). Or search by name / filter by position above.")
            for _, row in matching.iterrows():
                p = row.to_dict()
                pid = p["player_id"]
                cols = st.columns([4, 1, 1])
                with cols[0]:
                    _render_player_row(p, key_prefix="top")
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
            st.caption("Search by name or filter by position to open a profile.")

    st.markdown("---")
    st.caption("To discover more players by league, age, or stats, use **Find Players**.")
    st.stop()

# ---------------------------------------------------------------------------
# Player loaded — display profile
# ---------------------------------------------------------------------------

# Get player data
player_rows = df_all[df_all["player_id"] == player_id].sort_values("season", ascending=False)

if player_rows.empty:
    st.error("Player not found in database")
    st.stop()

# Player info
player_name = player_rows.iloc[0]["player_name"]
player_position = player_rows.iloc[0]["player_position"]

# Season selector
st.markdown(
    f"""
    <div class="page-hero">
        <div class="page-hero-title">📋 {player_name}</div>
        <div class="page-hero-sub">
            {POSITION_NAMES.get(player_position, player_position)} Profile
        </div>
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

# ---------------------------------------------------------------------------
# Header card with quick actions
# ---------------------------------------------------------------------------
st.markdown("---")

header_col, actions_col = st.columns([3, 1])

with header_col:
    flag = COMP_FLAGS.get(chosen_comp, "🏆")
    pos_label = POSITION_NAMES.get(player_position, player_position)
    
    st.markdown(
        f"""
        <div style="background:#161B22;padding:20px;border-radius:8px;border:1px solid #30363D;">
            <div style="display:flex;align-items:center;margin-bottom:15px;">
                <span style="font-size:2rem;margin-right:15px;">{flag}</span>
                <div>
                    <div style="font-size:1.4rem;font-weight:700;color:#F0F6FC;">{player_name}</div>
                    <div style="color:#8B949E;">{pos_label} · {chosen_team} · {chosen_row['league_name']}</div>
                </div>
            </div>
            <div style="display:flex;gap:20px;">
                <div>
                    <div style="font-size:0.75rem;color:#8B949E;">Age</div>
                    <div style="font-weight:600;color:#F0F6FC;">{int(prow.get('age_at_season_start', 0))}</div>
                </div>
                <div>
                    <div style="font-size:0.75rem;color:#8B949E;">Matches</div>
                    <div style="font-weight:600;color:#F0F6FC;">{int(prow.get('appearances', 0))}</div>
                </div>
                <div>
                    <div style="font-size:0.75rem;color:#8B949E;">Minutes</div>
                    <div style="font-weight:600;color:#F0F6FC;">{int(prow.get('total_minutes', 0)):,}</div>
                </div>
                <div>
                    <div style="font-size:0.75rem;color:#8B949E;">Rating</div>
                    <div style="font-weight:600;color:#C9A840;">{prow.get('avg_rating', 0):.2f}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with actions_col:
    # Add to shortlist
    in_shortlist = player_id in [p["id"] for p in st.session_state.shortlist]
    if in_shortlist:
        st.button("✅ In Shortlist", disabled=True, use_container_width=True)
    else:
        if st.button("🎯 Add to Shortlist", use_container_width=True, type="primary"):
            st.session_state.shortlist.append({
                "id": player_id,
                "name": player_name,
                "status": "Watching",
                "added_date": pd.Timestamp.now().strftime("%Y-%m-%d")
            })
            save_shortlist_to_file(st.session_state.shortlist)
            st.toast("Added to shortlist!")
            st.rerun()
    
    # Add to compare
    in_compare = player_id in st.session_state.compare_list
    if in_compare:
        st.button("✅ In Compare", disabled=True, use_container_width=True)
    else:
        if st.button("⚖️ Add to Compare", use_container_width=True):
            st.session_state.compare_list.append(player_id)
            save_scouts_compare_list(st.session_state.compare_list)
            st.toast("Added to compare!")
            st.rerun()
    
    if st.button("🔎 Find Similar", use_container_width=True):
        st.switch_page("pages/1_🔎_Discover.py")

# ---------------------------------------------------------------------------
# Percentile context and Per-90 vs Total toggle
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📊 Percentile Context</div>", unsafe_allow_html=True)

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
    key="percentile_toggle"
)

stats_display = st.radio(
    "Stats display:",
    options=["Per 90", "Total"],
    horizontal=True,
    key="profile_per90_display",
)
profile_show_per90 = stats_display == "Per 90"

# Calculate percentiles based on context.
# Always include a season filter so percentiles are within-season comparisons.
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
else:  # league
    pool = df_all[
        (df_all["player_position"] == player_position) &
        (df_all["season"] == chosen_season) &
        (df_all["competition_slug"] == chosen_comp)
    ]
    pool_label = f"{chosen_row['league_name']} · {chosen_season} · {POSITION_NAMES.get(player_position, player_position)}"


def get_percentile(value, series: pd.Series) -> float:
    """Percentile of value within series (0–100).

    Uses the midpoint formula: (strictly_below + 0.5 * tied) / n * 100.
    Returns NaN when value is NaN or the pool is empty.
    """
    if pd.isna(value):
        return float("nan")
    clean = series.dropna()
    if clean.empty:
        return float("nan")
    n = len(clean)
    below = (clean < value).sum()
    equal = (clean == value).sum()
    return float((below + 0.5 * equal) / n * 100)


# Build percentile list for radar stats (used for index + radar + weaknesses)
radar_stats = RADAR_STATS_BY_POSITION.get(player_position, RADAR_STATS_BY_POSITION["F"])
pct_list = []
for stat_key, stat_label in radar_stats:
    if stat_key not in prow.index or stat_key not in pool.columns:
        continue
    pct = get_percentile(prow[stat_key], pool[stat_key].dropna())
    if pd.notna(pct):
        pct_list.append((stat_key, stat_label, pct))

# Performance index: mean of radar percentiles → "Top X% of league"
performance_index_value = None
performance_index_label = None
weaknesses_list = []  # (stat_label, pct) where pct < 25
if pct_list:
    pcts_only = [p for _, _, p in pct_list]
    performance_index_value = sum(pcts_only) / len(pcts_only)
    pool_scores = []
    for _, row in pool.iterrows():
        row_pcts = [
            get_percentile(row.get(stat_key), pool[stat_key].dropna())
            for stat_key, _, _ in pct_list
            if stat_key in row.index and stat_key in pool.columns
        ]
        row_pcts = [p for p in row_pcts if pd.notna(p)]
        if row_pcts:
            pool_scores.append(sum(row_pcts) / len(row_pcts))
    if pool_scores:
        top_pct = get_percentile(performance_index_value, pd.Series(pool_scores))
        if top_pct >= 50:
            performance_index_label = f"Top {100 - int(top_pct)}%"
        else:
            performance_index_label = f"Bottom {int(top_pct)}%"
    weaknesses_list = [(label, pct) for _, label, pct in pct_list if pct < 25]

# ---------------------------------------------------------------------------
# Performance index badge + Axes d'amélioration (above radar)
# ---------------------------------------------------------------------------
if performance_index_value is not None and performance_index_label:
    idx_col, weak_col = st.columns([1, 1])
    with idx_col:
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,#C9A84022,#C9A84011);border:1px solid #C9A84055;border-radius:8px;padding:12px 16px;margin-bottom:12px;">
                <div style="font-size:0.75rem;color:#8B949E;margin-bottom:4px;">INDICE DE PERFORMANCE</div>
                <div style="font-size:1.1rem;font-weight:700;color:#C9A840;">{performance_index_label} DE SON CHAMPIONNAT</div>
                <div style="font-size:0.8rem;color:#8B949E;">Score moyen des centiles radar · {pool_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with weak_col:
        if weaknesses_list:
            st.markdown("<div class='section-header'>⚠️ Axes d'amélioration</div>", unsafe_allow_html=True)
            for label, pct in sorted(weaknesses_list, key=lambda x: x[1])[:6]:
                st.markdown(
                    f"<span style='font-size:0.8rem;background:rgba(248,81,73,0.15);color:#F85149;padding:4px 8px;border-radius:6px;margin:2px;display:inline-block;'>{label} ({pct:.0f}e pct)</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("<div style='font-size:0.85rem;color:#8B949E;'>Aucun point faible marqué (tous les radars &gt; 25e centile).</div>", unsafe_allow_html=True)
    st.markdown("")

# ---------------------------------------------------------------------------
# Radar Chart and Percentile Bars
# ---------------------------------------------------------------------------

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
                pct = get_percentile(prow[stat_key], pool[stat_key].dropna())
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
            pct = get_percentile(val, pool[stat_key].dropna())

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
                <div style="margin-bottom:12px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-size:0.85rem;color:#F0F6FC;">{stat_label}</span>
                        <span style="font-size:0.85rem;font-weight:600;color:{color};">{pct:.0f}th</span>
                    </div>
                    <div style="background:#21262D;border-radius:3px;height:6px;">
                        <div style="background:{color};border-radius:3px;height:6px;width:{pct:.1f}%"></div>
                    </div>
                    <div style="font-size:0.75rem;color:#8B949E;margin-top:2px;">{val_str}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🏷️ Scouting Badges</div>", unsafe_allow_html=True)

# Calculate badges
badges = calculate_badges(prow, pool)

if badges:
    # Separate positive and negative
    positive = [b for b in badges if b.is_positive]
    negative = [b for b in badges if not b.is_positive]
    
    if positive:
        st.markdown("**Strengths:**")
        badges_html = " ".join([format_badge_for_display(b) for b in positive])
        st.markdown(badges_html, unsafe_allow_html=True)
    
    if negative:
        st.markdown("**Concerns:**")
        badges_html = " ".join([format_badge_for_display(b) for b in negative])
        st.markdown(badges_html, unsafe_allow_html=True)
else:
    st.info("Insufficient data for badge generation")

# ---------------------------------------------------------------------------
# Position-Specific Sections
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📋 Detailed Analysis</div>", unsafe_allow_html=True)

# Define position-specific sections
POSITION_SECTIONS = {
    "F": [
        ("Finishing", ["goals_per90", "expectedGoals_per90", "onTargetScoringAttempt_per90"]),
        ("Chance Creation", ["expectedAssists_per90", "keyPass_per90", "bigChanceCreated_per90"]),
        ("Movement", ["totalShots_per90", "dribble_per90", "touches_in_box_per90"]),
    ],
    "M": [
        ("Passing", ["totalPass_per90", "pass_accuracy_pct", "keyPass_per90", "expectedAssists_per90"]),
        ("Progression", ["progressivePass_per90", "dribble_per90", "ballRecovery_per90"]),
        ("Defensive Actions", ["totalTackle_per90", "interceptionWon_per90", "duelWon_per90"]),
    ],
    "D": [
        ("Defending", ["totalTackle_per90", "interceptionWon_per90", "totalClearance_per90"]),
        ("Aerial Duels", ["aerialWon_per90", "aerial_lost_per90"]),
        ("Progression", ["pass_accuracy_pct", "totalPass_per90", "progressivePass_per90"]),
    ],
    "G": [
        ("Shot Stopping", ["saves_per90", "goalsPrevented_per90"]),
        ("Distribution", ["pass_accuracy_pct", "totalPass_per90"]),
        ("Command", ["goodHighClaim_per90", "totalKeeperSweeper_per90"]),
    ],
}

sections = POSITION_SECTIONS.get(player_position, POSITION_SECTIONS["F"])

for section_name, stats in sections:
    with st.expander(f"📊 {section_name}", expanded=True):
        cols = st.columns(min(len(stats), 4))
        
        for i, stat_key in enumerate(stats):
            with cols[i % len(cols)]:
                if stat_key in prow.index:
                    val = prow[stat_key]
                    if stat_key in pool.columns and pd.notna(val):
                        pct = get_percentile(val, pool[stat_key].dropna())
                    else:
                        pct = float("nan")

                    pct_display = f"{pct:.0f}th" if pd.notna(pct) else "N/A"
                    val_str = f"{val:.2f}" if pd.notna(val) else "—"

                    # Determine color
                    if pd.notna(pct) and pct >= 80:
                        color = "#3FB950"
                    elif pd.notna(pct) and pct >= 50:
                        color = "#C9A840"
                    else:
                        color = "#F85149"

                    st.markdown(
                        f"""
                        <div style="background:#161B22;padding:12px;border-radius:6px;border:1px solid #30363D;text-align:center;">
                            <div style="font-size:0.75rem;color:#8B949E;margin-bottom:4px;">{stat_key.replace('_per90', '/90').replace('_', ' ').title()}</div>
                            <div style="font-size:1.3rem;font-weight:600;color:{color};">{val_str}</div>
                            <div style="font-size:0.75rem;color:#8B949E;">{pct_display} percentile</div>
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
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        baseline = opp.get("baseline_rating", 0)
        st.metric("Baseline Rating", f"{baseline:.2f}")
    with col2:
        vs_top = opp.get("rating_vs_top", 0)
        st.metric("Rating vs Top Teams", f"{vs_top:.2f}")
    with col3:
        delta = opp.get("big_game_rating_delta", 0)
        delta_color = "normal" if delta >= 0 else "inverse"
        st.metric("Big Game Δ", f"{delta:+.2f}", delta_color=delta_color)
    with col4:
        ratio = opp.get("performance_ratio", 1.0)
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
    recent_form = player_form
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(1, len(recent_form) + 1)),
        y=recent_form["stat_rating"],
        mode="lines+markers",
        name="Rating",
        line=dict(color="#C9A840", width=2),
        marker=dict(size=8),
        hovertemplate="Game %{x}<br>Rating: %{y:.2f}<extra></extra>",
    ))
    
    # Add season average line
    season_avg = prow.get("avg_rating", 7.0)
    fig.add_hline(
        y=season_avg,
        line_dash="dash",
        line_color="#8B949E",
        annotation_text=f"Season Avg ({season_avg:.2f})",
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
# Similar Players
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>👥 Similar Players</div>", unsafe_allow_html=True)

similar_cross_league = st.checkbox(
    "Inclure les Top 5 championnats (pas seulement cette ligue)",
    value=False,
    key="profile_similar_cross_league",
    help="Trouve des profils similaires dans les 5 grands championnats européens.",
)
try:
    similar = get_similar_players(
        player_id=player_id,
        season=chosen_season,
        competition_slug=chosen_comp,
        position=player_position,
        df_all=df_all,
        n=3,
        cross_league=similar_cross_league,
    )

    if similar is not None and not similar.empty:
        sim_cols = st.columns(len(similar))
        for i, (_, sim_player) in enumerate(similar.iterrows()):
            with sim_cols[i]:
                dist = sim_player.get("similarity_dist", float("nan"))
                dist_label = f"{dist:.2f}" if pd.notna(dist) else "N/A"

                st.markdown(
                    f"""
                    <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;">
                        <div style="font-weight:600;color:#F0F6FC;">{sim_player['player_name']}</div>
                        <div style="font-size:0.8rem;color:#8B949E;margin:4px 0;">
                            {player_position} · {COMP_NAMES.get(chosen_comp, chosen_comp)}
                        </div>
                        <div style="display:flex;justify-content:space-between;margin-top:10px;">
                            <span style="font-size:0.75rem;color:#8B949E;">Distance</span>
                            <span style="color:#C9A840;font-weight:600;">{dist_label}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button("View", key=f"sim_{int(sim_player['player_id'])}", use_container_width=True):
                    st.session_state["profile_player_id"] = int(sim_player["player_id"])
                    st.rerun()
    else:
        st.info("No similar players found in the same season/league/position")
except Exception:
    st.info("Could not load similar players")

# ---------------------------------------------------------------------------
# Scouting Notes (persisted to file)
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📝 Scouting Notes</div>", unsafe_allow_html=True)

_notes_dir = pathlib.Path(__file__).parent.parent
_notes_file = _notes_dir / f"notes_{player_id}.json"

def _load_notes_file():
    if _notes_file.exists():
        try:
            import json
            with open(_notes_file, "r") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def _save_notes_file(by_season: dict):
    import json
    _notes_dir.mkdir(parents=True, exist_ok=True)
    with open(_notes_file, "w") as f:
        json.dump(by_season, f, indent=2)

_notes_data = _load_notes_file()
_notes_by_season = _notes_data.get("by_season", {})
_current_notes = _notes_by_season.get(str(chosen_season), "")

with st.form("notes_form"):
    notes = st.text_area(
        "Add your observations:",
        value=_current_notes,
        placeholder="e.g., Strong in 1v1s, needs to improve aerial duels, good tactical awareness...",
        key="notes_input_profile",
    )
    if st.form_submit_button("💾 Save Notes"):
        _notes_by_season[str(chosen_season)] = notes
        _save_notes_file({"by_season": _notes_by_season})
        st.toast("Notes saved!")
        st.rerun()

# Profile report export (HTML)
st.markdown("<div class='section-header'>📤 Export</div>", unsafe_allow_html=True)
_report_lines = [
    f"<h1>{player_name}</h1>",
    f"<p>{POSITION_NAMES.get(player_position, player_position)} · {chosen_team} · {chosen_row.get('league_name', '')} {chosen_season}</p>",
    f"<p>Age: {int(prow.get('age_at_season_start', 0))} · Apps: {int(prow.get('appearances', 0))} · Mins: {int(prow.get('total_minutes', 0)):,} · Rating: {prow.get('avg_rating', 0):.2f}</p>",
    "<h2>Notes</h2>",
    f"<pre>{notes or '(none)'}</pre>",
]
profile_html = "<html><body>" + "\n".join(_report_lines) + "</body></html>"
st.download_button(
    "⬇️ Download profile report (HTML)",
    data=profile_html,
    file_name=f"profile_{player_id}_{chosen_season}.html",
    mime="text/html",
    key="profile_export_html",
)

# Footer navigation
st.markdown("---")
st.markdown("<div class='section-header'>🚀 Navigate</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("← Back to Discover", use_container_width=True):
        st.switch_page("pages/1_🔎_Discover.py")
with col2:
    if st.button("⚖️ Compare", use_container_width=True):
        st.switch_page("pages/3_⚖️_Compare.py")
with col3:
    if st.button("🎯 Shortlist", use_container_width=True):
        st.switch_page("pages/4_🎯_Shortlist.py")
