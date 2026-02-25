"""Compare Players — radar charts, bar comparisons, side-by-side stats."""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils.data import (
    load_enriched_season_stats,
    reliability_tier_from_minutes,
    format_metric,
    format_rating,
    format_per90,
    format_percentile,
    format_minutes,
)
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, POSITION_NAMES, POSITION_ORDER,
    RADAR_STATS_BY_POSITION, RADAR_STATS_UNIVERSAL, PLAYER_COLORS,
    MIN_MINUTES_DEFAULT,
)
from dashboard.utils.charts import radar_chart, multi_bar_comparison
from dashboard.utils.sidebar import render_sidebar
from dashboard.utils.state import (
    init_compare_list,
    get_compare_list,
    remove_from_compare,
    clear_compare,
    add_to_compare,
    get_compare_count,
)

st.set_page_config(page_title="Compare · Schlouh", page_icon="⚖️", layout="wide")
def _render_comparison_view(
    df_all: pd.DataFrame,
    player_id_to_name: dict,
    player_id_to_pos: dict,
) -> None:
    """Render the full comparison view for selected players."""
    st.markdown("<div class='section-header'>2. Comparison Context</div>", unsafe_allow_html=True)

    compare_ids = get_compare_list()
    player_data = df_all[df_all["player_id"].isin(compare_ids)]

    avail_seasons = sorted(player_data["season"].unique(), reverse=True)
    avail_comps = sorted(player_data["competition_slug"].unique())

    ctx1, ctx2, ctx3, ctx4 = st.columns(4)
    with ctx1:
        ctx_season = st.selectbox(
            "Season context",
            options=avail_seasons,
            key="ctx_season",
            help="Select the season for comparison. Players without data in this season will show blanks.",
        )
    with ctx2:
        avail_comps_for_season = sorted(
            player_data[player_data["season"] == ctx_season]["competition_slug"].unique()
        )
        ctx_comp = st.selectbox(
            "League context",
            options=avail_comps_for_season if avail_comps_for_season else avail_comps,
            format_func=lambda x: f"{COMP_FLAGS.get(x, '🏆')} {COMP_NAMES.get(x, x)}",
            key="ctx_comp",
        )
    with ctx3:
        ctx_min_mins = st.number_input(
            "Min. minutes (indicator)",
            min_value=0,
            max_value=4000,
            value=MIN_MINUTES_DEFAULT,
            step=90,
            key="ctx_mins",
            help="Players below this threshold are flagged with ⚠️.",
        )
    with ctx4:
        pct_context = st.selectbox(
            "Percentile context",
            options=["same_league", "all_leagues"],
            format_func=lambda x: "Same league/season" if x == "same_league" else "All leagues (same season)",
            key="pct_context",
            help="Controls the pool used to compute radar percentile ranks.",
        )

    # Build comparison DataFrame
    compare_rows = []
    for pid in compare_ids:
        prows = player_data[
            (player_data["player_id"] == pid) &
            (player_data["season"] == ctx_season) &
            (player_data["competition_slug"] == ctx_comp)
        ]
        if not prows.empty:
            compare_rows.append(prows.iloc[0])
        else:
            # Fallback to any season for this player
            fallback = player_data[player_data["player_id"] == pid]
            if not fallback.empty:
                fb_row = fallback.sort_values("season", ascending=False).iloc[0]
                fb_row = fb_row.copy()
                fb_row["_missing_context"] = True
                compare_rows.append(fb_row)
            else:
                compare_rows.append(
                    pd.Series({
                        "player_id": pid,
                        "player_name": player_id_to_name.get(pid, str(pid)),
                        "_no_data": True,
                    })
                )

    df_compare = pd.DataFrame(compare_rows).reset_index(drop=True)
    df_compare["_missing_context"] = df_compare.get("_missing_context", False)
    df_compare["_no_data"] = df_compare.get("_no_data", False)

    # Summary cards
    st.markdown("<div class='section-header'>3. Summary Cards</div>", unsafe_allow_html=True)
    _render_summary_cards(df_compare, compare_ids, ctx_min_mins)

    # Radar Chart
    st.markdown("<div class='section-header'>4. Radar Chart (Percentile Rankings)</div>", unsafe_allow_html=True)
    _render_radar_chart(df_compare, df_all, compare_ids, ctx_season, ctx_comp, pct_context)

    # Bar chart comparison
    st.markdown("<div class='section-header'>5. Metric Comparison (Bar Charts)</div>", unsafe_allow_html=True)
    _render_bar_comparison(df_compare)

    # Side-by-side stats table
    st.markdown("<div class='section-header'>6. Full Stats Table</div>", unsafe_allow_html=True)
    _render_stats_table(df_compare)

    # Export comparison
    st.markdown("---")
    cta1, cta2 = st.columns(2)
    with cta1:
        csv_bytes = df_compare.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export comparison (CSV)", data=csv_bytes, file_name="comparison.csv", mime="text/csv")
    with cta2:
        st.page_link("pages/1_🔍_Scout.py", label="🔍 Add more players from Scout", use_container_width=True)


def _render_summary_cards(df_compare: pd.DataFrame, compare_ids: list, ctx_min_mins: int) -> None:
    """Render player summary cards."""
    card_cols = st.columns(len(compare_ids))

    for i, (_, row) in enumerate(df_compare.iterrows()):
        pid = row.get("player_id")
        pname = row.get("player_name", str(pid))
        color = PLAYER_COLORS[i % len(PLAYER_COLORS)]

        with card_cols[i]:
            if row.get("_no_data"):
                st.markdown(
                    f"<div style='border:1px solid {color}55;border-radius:10px;padding:1rem;text-align:center;'>"
                    f"<b style='color:{color};'>{pname}</b><br>"
                    f"<span style='color:#8B949E;font-size:0.85rem;'>No data available</span></div>",
                    unsafe_allow_html=True,
                )
                continue

            mins = row.get("total_minutes", 0) or 0
            mins_int = int(mins) if pd.notna(mins) else 0
            warn = "⚠️ " if mins_int < ctx_min_mins else ""
            rel_tier = reliability_tier_from_minutes(mins)
            rel_colors = {"High": "#C9A840", "Medium": "#FFD93D", "Low": "#FF6B6B"}
            rel_color = rel_colors.get(rel_tier, "#8B949E")

            pos_label = POSITION_NAMES.get(row.get("player_position"), row.get("player_position", "?"))
            season_label = row.get("season", "—")
            league_label = COMP_NAMES.get(row.get("competition_slug"), row.get("competition_slug", "—"))
            team_label = row.get("team", "—")
            missing_note = " (⚠️ data from different context)" if row.get("_missing_context") else ""

            rating = row.get("avg_rating")
            goals = row.get("goals", 0)
            assists = row.get("assists", 0)
            apps = row.get("appearances", 0)
            xg90 = row.get("expectedGoals_per90")
            xa90 = row.get("expectedAssists_per90")

            st.markdown(
                f"""<div style='border:1px solid {color}55;border-radius:10px;padding:1rem;'>
                <div style='text-align:center;margin-bottom:0.5rem;'>
                    <b style='color:{color};font-size:1.05rem;'>{pname}</b>
                </div>
                <div style='font-size:0.8rem;color:#8B949E;text-align:center;margin-bottom:0.3rem;'>
                    {pos_label} · {team_label}<br>{league_label} {season_label}{missing_note}
                </div>
                <div style='font-size:0.72rem;text-align:center;margin-bottom:0.5rem;'>
                    Based on <b>{mins_int:,}</b> min &nbsp;
                    <span style='background:{rel_color}22;border:1px solid {rel_color}55;border-radius:10px;padding:1px 6px;color:{rel_color};'>Sample: {rel_tier}</span>
                </div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:0.88rem;'>
                    <div style='background:#161B22;border-radius:6px;padding:5px 8px;'>
                        <div style='color:#8B949E;font-size:0.75rem;'>Apps</div>
                        <b>{format_metric(apps, decimals=0)}</b>
                    </div>
                    <div style='background:#161B22;border-radius:6px;padding:5px 8px;'>
                        <div style='color:#8B949E;font-size:0.75rem;'>Mins {warn}</div>
                        <b>{format_minutes(mins_int)}</b>
                    </div>
                    <div style='background:#161B22;border-radius:6px;padding:5px 8px;'>
                        <div style='color:#8B949E;font-size:0.75rem;'>Rating</div>
                        <b>{format_rating(rating)}</b>
                    </div>
                    <div style='background:#161B22;border-radius:6px;padding:5px 8px;'>
                        <div style='color:#8B949E;font-size:0.75rem;'>G + A</div>
                        <b>{format_metric(goals, decimals=0)} + {format_metric(assists, decimals=0)}</b>
                    </div>
                    <div style='background:#161B22;border-radius:6px;padding:5px 8px;'>
                        <div style='color:#8B949E;font-size:0.75rem;'>xG/90</div>
                        <b>{format_per90(xg90)}</b>
                    </div>
                    <div style='background:#161B22;border-radius:6px;padding:5px 8px;'>
                        <div style='color:#8B949E;font-size:0.75rem;'>xA/90</div>
                        <b>{format_per90(xa90)}</b>
                    </div>
                </div>
                </div>""",
                unsafe_allow_html=True,
            )


def _render_radar_chart(
    df_compare: pd.DataFrame,
    df_all: pd.DataFrame,
    compare_ids: list,
    ctx_season: str,
    ctx_comp: str,
    pct_context: str,
) -> None:
    """Render radar chart comparison."""
    positions_in_compare = df_compare["player_position"].dropna().unique().tolist()
    if len(positions_in_compare) == 1 and positions_in_compare[0] in RADAR_STATS_BY_POSITION:
        default_group = positions_in_compare[0]
    else:
        default_group = "Universal"

    radar_group_opts = {
        "F": "⚡ Forwards",
        "M": "🔄 Midfielders",
        "D": "🛡️ Defenders",
        "G": "🧤 Goalkeepers",
        "Universal": "🌍 Universal",
    }
    opts = list(radar_group_opts.keys())
    default_idx = opts.index(default_group) if default_group in opts else 0
    chosen_group = st.selectbox(
        "Stat group for radar",
        options=opts,
        format_func=lambda x: radar_group_opts[x],
        index=default_idx,
        key="radar_group",
    )

    radar_stat_list = RADAR_STATS_UNIVERSAL if chosen_group == "Universal" else RADAR_STATS_BY_POSITION[chosen_group]
    stat_keys = [s for s, _ in radar_stat_list]
    stat_labels = [l for _, l in radar_stat_list]

    # Compute percentiles using selected context.
    # For position-specific radar groups, also filter by position so that e.g.
    # a forward's xG/90 is ranked only against other forwards.
    pos_filter = None
    if chosen_group in RADAR_STATS_BY_POSITION:  # not "Universal"
        pos_filter = chosen_group

    if pct_context == "same_league":
        base_mask = (df_all["season"] == ctx_season) & (df_all["competition_slug"] == ctx_comp)
        pct_pool_label = f"{COMP_NAMES.get(ctx_comp, ctx_comp)} {ctx_season}"
    else:
        base_mask = df_all["season"] == ctx_season
        pct_pool_label = f"All leagues {ctx_season}"

    if pos_filter is not None and "player_position" in df_all.columns:
        base_mask &= df_all["player_position"] == pos_filter
        pct_pool_label += f" · {POSITION_NAMES.get(pos_filter, pos_filter)}"

    pool_for_pct = df_all[base_mask].copy()

    valid_keys = [k for k in stat_keys if k in pool_for_pct.columns]
    for k in valid_keys:
        pool_for_pct[f"{k}_pct"] = pool_for_pct[k].rank(pct=True, na_option="keep") * 100

    # Build radar_df - only players with data in selected context
    radar_rows = []
    excluded_from_radar = []
    for i, row in df_compare.iterrows():
        if row.get("_no_data"):
            continue
        pid = row["player_id"]
        pname = row["player_name"]
        prow_in_pool = pool_for_pct[pool_for_pct["player_id"] == pid]

        if prow_in_pool.empty:
            excluded_from_radar.append(pname)
            continue

        prow_in_pool = prow_in_pool.iloc[0]
        for k, label in zip(stat_keys, stat_labels):
            if k in prow_in_pool.index:
                radar_rows.append({
                    "player_name": pname,
                    "stat": k,
                    "pct": prow_in_pool.get(f"{k}_pct", np.nan),
                    "raw": prow_in_pool.get(k, np.nan),
                })

    if excluded_from_radar:
        st.warning(
            f"**Excluded from radar** (no data in {pct_pool_label}): "
            + ", ".join(excluded_from_radar)
            + ". Their summary cards above show data from a different season/league."
        )

    if radar_rows:
        radar_df = pd.DataFrame(radar_rows)
        valid_stats = radar_df["stat"].unique().tolist()
        valid_labels = [l for k, l in zip(stat_keys, stat_labels) if k in valid_stats]

        pool_size = len(pool_for_pct)
        context_note = f"{pct_pool_label} (n={pool_size})"

        # Show prominent context notice for position-specific radars
        if pos_filter is not None:
            st.info(
                f"📊 **Position-specific radar**: Percentiles calculated vs only "
                f"**{POSITION_NAMES.get(pos_filter, pos_filter)}** in this league/season. "
                f"Switch to 'Universal' to compare against all positions.",
                icon="ℹ️"
            )
        else:
            st.info(
                f"📊 **Universal radar**: Percentiles calculated vs **all positions** "
                f"in this league/season. Switch to position-specific groups for more relevant comparisons.",
                icon="ℹ️"
            )

        with st.spinner("Generating radar chart…"):
            fig_radar = radar_chart(radar_df, valid_labels, title=f"Radar Comparison — {context_note}")
            st.plotly_chart(fig_radar, use_container_width=True)
        st.caption(
            f"ℹ️ Percentiles within: {context_note}. "
            "All axes 0–100 — higher = better rank vs pool. "
            "Missing values estimated from player's other stats. "
            "Players below min minutes are flagged ⚠️ in the summary cards."
        )
    else:
        st.info(
            "Not enough data to render radar chart. None of the selected players have data "
            f"in {COMP_NAMES.get(ctx_comp, ctx_comp)} {ctx_season}. "
            "Try a different season or league context."
        )


def _render_bar_comparison(df_compare: pd.DataFrame) -> None:
    """Render bar chart comparison."""
    bar_stat_options = {
        "avg_rating": "Avg Rating",
        "goals_per90": "Goals/90",
        "expectedGoals_per90": "xG/90",
        "expectedAssists_per90": "xA/90",
        "keyPass_per90": "Key Passes/90",
        "bigChanceCreated_per90": "Big Chances/90",
        "totalTackle_per90": "Tackles/90",
        "interceptionWon_per90": "Interceptions/90",
        "duelWon_per90": "Duels Won/90",
        "aerialWon_per90": "Aerials Won/90",
        "ballRecovery_per90": "Ball Recovery/90",
        "totalPass_per90": "Passes/90",
        "pass_accuracy_pct": "Pass Accuracy %",
        "progressiveBallCarriesCount_per90": "Prog. Carries/90",
        "saves_per90": "Saves/90",
        "goalsPrevented_per90": "Goals Prevented/90",
        "total_minutes": "Total Minutes",
        "goals": "Total Goals",
        "assists": "Total Assists",
    }
    avail_bar_stats = {k: v for k, v in bar_stat_options.items() if k in df_compare.columns}

    sel_bar_stats = st.multiselect(
        "Select metrics to compare",
        options=list(avail_bar_stats.keys()),
        default=list(avail_bar_stats.keys())[:9],
        format_func=lambda x: avail_bar_stats[x],
        key="bar_stats_sel",
    )

    if sel_bar_stats and not df_compare.empty:
        bar_stat_pairs = [(k, avail_bar_stats[k]) for k in sel_bar_stats]
        with st.spinner("Generating bar charts…"):
            fig_bars = multi_bar_comparison(df_compare, bar_stat_pairs, max_cols=3)
            st.plotly_chart(fig_bars, use_container_width=True)


def _render_stats_table(df_compare: pd.DataFrame) -> None:
    """Render side-by-side stats table."""
    display_stat_cols = [
        "player_name", "player_position", "team", "league_name", "season",
        "appearances", "total_minutes", "avg_rating",
        "goals", "assists",
        "goals_per90", "expectedGoals_per90", "expectedAssists_per90",
        "keyPass_per90", "bigChanceCreated_per90",
        "totalTackle_per90", "interceptionWon_per90",
        "duelWon_per90", "aerialWon_per90",
        "ballRecovery_per90", "totalPass_per90", "pass_accuracy_pct",
        "progressiveBallCarriesCount_per90",
        "saves_per90", "goalsPrevented_per90",
    ]
    existing_cols = [c for c in display_stat_cols if c in df_compare.columns]
    table_df = df_compare[existing_cols].copy()
    table_df = table_df.rename(columns={
        "player_name": "Player", "player_position": "Pos",
        "team": "Team", "league_name": "League", "season": "Season",
        "appearances": "Apps", "total_minutes": "Mins", "avg_rating": "Rating",
        "goals": "Goals", "assists": "Assists",
        "goals_per90": "G/90", "expectedGoals_per90": "xG/90",
        "expectedAssists_per90": "xA/90", "keyPass_per90": "KP/90",
        "bigChanceCreated_per90": "BCC/90", "totalTackle_per90": "Tkl/90",
        "interceptionWon_per90": "Int/90", "duelWon_per90": "DW/90",
        "aerialWon_per90": "Air/90", "ballRecovery_per90": "Rec/90",
        "totalPass_per90": "Pass/90", "pass_accuracy_pct": "Pass%",
        "progressiveBallCarriesCount_per90": "ProgC/90",
        "saves_per90": "Sv/90", "goalsPrevented_per90": "GkPrev/90",
    })

    # Keep NaN as NaN for display — st.dataframe will show "—" for missing values
    # Round floats to 2 decimal places for display
    for col in table_df.select_dtypes("float").columns:
        table_df[col] = table_df[col].round(2)

    st.dataframe(table_df.T, use_container_width=True)
render_sidebar()
init_compare_list()

with st.spinner("Loading…"):
    df_all = load_enriched_season_stats()

st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">⚖️ Compare Players</div>
        <div class="page-hero-sub">
            Select up to 6 players and compare them side-by-side with radar charts,
            bar charts, and a full stats table.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Player picker section
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>1. Select Players</div>", unsafe_allow_html=True)

all_players = (
    df_all[["player_id", "player_name", "player_position", "team"]]
    .sort_values("player_name")
    .drop_duplicates("player_id")
)
player_id_to_name = all_players.set_index("player_id")["player_name"].to_dict()
player_id_to_pos = all_players.set_index("player_id")["player_position"].to_dict()

col_search, col_add = st.columns([3, 1])
with col_search:
    search_player = st.selectbox(
        "Search player by name",
        options=all_players["player_id"].tolist(),
        format_func=lambda x: f"{player_id_to_name.get(x, x)} ({POSITION_NAMES.get(player_id_to_pos.get(x), '?')})",
        key="compare_search",
        index=0,
    )
with col_add:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("➕ Add", key="compare_add_btn", use_container_width=True, type="primary"):
        if search_player not in get_compare_list():
            if add_to_compare(search_player, player_id_to_name.get(search_player, "")):
                st.toast(f"✅ {player_id_to_name.get(search_player)} added")
            else:
                st.warning("Max 6 players in comparison.")
        else:
            st.info("Already in comparison.")

# Show current compare list with remove buttons
if get_compare_list():
    st.markdown("<b>Current comparison:</b>", unsafe_allow_html=True)
    cols = st.columns(min(get_compare_count(), 6))
    for i, pid in enumerate(list(get_compare_list())):
        pname = player_id_to_name.get(pid, str(pid))
        color = PLAYER_COLORS[i % len(PLAYER_COLORS)]
        with cols[i]:
            st.markdown(
                f"<div style='background:{color}22;border:1px solid {color}55;"
                f"border-radius:8px;padding:0.5rem;text-align:center;'>"
                f"<b style='color:{color};'>{pname}</b></div>",
                unsafe_allow_html=True,
            )
            if st.button("✕ Remove", key=f"remove_{pid}", use_container_width=True):
                remove_from_compare(pid)
                st.rerun()

    if st.button("🗑️ Clear all", key="clear_compare_all"):
        clear_compare()
        st.rerun()
else:
    st.info("No players selected yet. Add players from the search above or from the Scout page.")

# ---------------------------------------------------------------------------
# Comparison views (only if 2+ players selected)
# ---------------------------------------------------------------------------
if get_compare_count() >= 2:
    _render_comparison_view(df_all, player_id_to_name, player_id_to_pos)
elif get_compare_count() == 1:
    st.info("Add at least one more player to start comparing.")
else:
    st.markdown(
        """
        <div style='background:#161B22;border:1px solid #30363D;border-radius:10px;padding:2rem;text-align:center;margin-top:2rem;'>
            <h3 style='color:#C9A840;'>No players selected</h3>
            <p style='color:#8B949E;'>
                Use the <b>search above</b> to add players, or go to the
                <b>Scout page</b> and click "Add to Compare" on any player.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


