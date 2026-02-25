"""Scout Players — find, filter, rank, and profile players."""

import sys
import pathlib

_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from unicodedata import normalize as unicode_normalize

from dashboard.utils.data import (
    load_enriched_season_stats,
    get_player_match_log,
    load_scouting_profiles,
    load_rolling_form,
    load_career_stats,
    load_player_progression,
    load_opponent_context_summary,
    load_player_consistency,
    load_team_season_stats,
    load_tactical_profiles,
    get_similar_players,
    build_player_narrative,
    reliability_tier_from_minutes,
)
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, POSITION_NAMES, POSITION_ORDER,
    SCOUT_DISPLAY_COLS, RANKING_STATS, PLAYER_COLORS, MIN_MINUTES_DEFAULT,
    TOP_5_LEAGUES, AGE_BANDS, STAT_TOOLTIPS,
)
from dashboard.utils.filters import apply_filters, display_filter_summary
from dashboard.utils.filter_components import (
    EnhancedFilterPanel,
    render_no_results_state,
    FilterDefaults,
    filter_loading_state,
)
from dashboard.utils.state import (
    init_compare_list, add_to_compare, get_compare_list, get_compare_count, clear_compare,
    display_compare_widget, set_profile_player, clear_profile_player,
    get_profile_player, is_profile_view_active,
)
from dashboard.utils.components import (
    player_header_card, season_kpis, league_benchmark_badge,
    strength_pills, consistency_badge, form_metrics_row, big_game_metrics,
    progression_deltas, stat_columns, goalkeeper_card,
    career_overview_card, similar_players_cards, player_match_log,
    export_player_brief,
)
from dashboard.utils.sidebar import render_sidebar


def _normalize_search_text(text) -> str:
    """Normalize text for search (handles accents, case). Mbappé -> mbappe."""
    if pd.isna(text):
        return ""
    normalized = unicode_normalize("NFKD", str(text).lower()).encode("ASCII", "ignore").decode()
    return normalized


def _render_rankings_tab(df_all: pd.DataFrame) -> None:
    """Render the Top N Rankings tab."""
    st.markdown("<div class='section-header'>🏆 Top N by Metric</div>", unsafe_allow_html=True)

    r1, r2, r3, r4, r5 = st.columns(5)
    with r1:
        rank_league = st.selectbox(
            "League",
            options=["All"] + sorted(df_all["competition_slug"].unique()),
            format_func=lambda x: "All leagues" if x == "All" else f"{COMP_FLAGS.get(x,'🏆')} {COMP_NAMES.get(x,x)}",
            key="rank_league",
        )
    with r2:
        rank_season_opts = (
            ["All"] + sorted(df_all["season"].unique(), reverse=True) if rank_league == "All"
            else ["All"] + sorted(df_all[df_all["competition_slug"] == rank_league]["season"].unique(), reverse=True)
        )
        rank_season = st.selectbox("Season", rank_season_opts, key="rank_season")
    with r3:
        rank_pos = st.selectbox(
            "Position",
            options=["All"] + [p for p in POSITION_ORDER if p in df_all["player_position"].dropna().unique()],
            format_func=lambda x: "All" if x == "All" else POSITION_NAMES.get(x, x),
            key="rank_pos",
        )
    with r4:
        rank_metric = st.selectbox(
            "Rank by",
            options=list(RANKING_STATS.keys()),
            format_func=lambda x: RANKING_STATS[x],
            key="rank_metric",
        )
    with r5:
        rank_min_mins = st.number_input("Min. minutes", 0, 4000, 450, step=90, key="rank_mins")

    rq1, rq2 = st.columns(2)
    with rq1:
        rank_age = st.multiselect("Age band", options=AGE_BANDS, default=[], placeholder="All ages", key="rank_age")
    with rq2:
        rank_teams = st.multiselect(
            "Team",
            options=sorted(df_all["team"].dropna().unique()),
            default=[],
            placeholder="All teams",
            key="rank_teams",
        )

    show_big_game = st.checkbox("Sort by big-game rating (vs top opposition)", key="rank_big_game")
    rank_n = st.slider("Top N", 5, 50, 20, step=5, key="rank_n")

    # Apply filters using centralized function
    config = {
        "leagues": [] if rank_league == "All" else [rank_league],
        "seasons": [] if rank_season == "All" else [rank_season],
        "positions": [] if rank_pos == "All" else [rank_pos],
        "min_minutes": rank_min_mins,
        "age_bands": rank_age,
        "teams": rank_teams,
    }
    df_rank = apply_filters(df_all, config)

    if show_big_game:
        df_opp_ctx = load_opponent_context_summary()
        merge_cols = ["player_id", "season", "competition_slug", "rating_vs_top", "big_game_rating_delta"]
        merge_opp = df_opp_ctx[[c for c in merge_cols if c in df_opp_ctx.columns]].copy()
        df_rank = df_rank.merge(merge_opp, on=["player_id", "season", "competition_slug"], how="left")
        sort_col = "rating_vs_top"
        metric_label = "Rating vs Top Teams"
    else:
        sort_col = rank_metric
        metric_label = RANKING_STATS.get(rank_metric, rank_metric)

    if sort_col not in df_rank.columns:
        st.warning(f"Metric '{sort_col}' not available in data.")
    else:
        if rank_league == "All" or rank_season == "All":
            df_rank = df_rank.loc[df_rank.groupby("player_id")[sort_col].idxmax()].copy()

        df_top = df_rank.dropna(subset=[sort_col]).nlargest(rank_n, sort_col).reset_index(drop=True)
        df_top.index += 1

        fig_rank = go.Figure(go.Bar(
            y=df_top["player_name"],
            x=df_top[sort_col],
            orientation="h",
            marker_color=PLAYER_COLORS[0],
            text=df_top[sort_col].round(2).astype(str),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>" + metric_label + ": %{x:.2f}<extra></extra>",
        ))
        fig_rank.update_layout(
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            font=dict(color="#E6EDF3"),
            xaxis=dict(gridcolor="#30363D", title=metric_label),
            yaxis=dict(categoryorder="total ascending", tickfont=dict(size=11), gridcolor="#30363D"),
            margin=dict(l=20, r=60, t=30, b=30),
            height=max(300, 35 * rank_n + 60),
            title=dict(text=f"Top {rank_n} — {metric_label}", font=dict(size=15)),
        )
        st.plotly_chart(fig_rank, use_container_width=True)

        rank_cols = ["player_name", "player_position", "team", "league_name", "season", "total_minutes"]
        if sort_col != "avg_rating":
            rank_cols.append("avg_rating")
        if show_big_game and "big_game_rating_delta" in df_top.columns:
            rank_cols += ["rating_vs_top", "big_game_rating_delta"]
        rank_cols.append(sort_col)

        rank_display = df_top[[c for c in rank_cols if c in df_top.columns]].copy()
        rank_display = rank_display.rename(columns={
            "player_name": "Player",
            "player_position": "Pos",
            "team": "Team",
            "league_name": "League",
            "season": "Season",
            "total_minutes": "Mins",
            "avg_rating": "Rating",
            sort_col: metric_label,
            "rating_vs_top": "Rating vs Top",
            "big_game_rating_delta": "Big Game Δ",
        })
        for col in ["Mins"]:
            if col in rank_display.columns:
                rank_display[col] = rank_display[col].fillna(0).astype(int)
        for col in rank_display.select_dtypes("float").columns:
            rank_display[col] = rank_display[col].round(2)
        st.dataframe(rank_display, use_container_width=True, hide_index=False)

        if not df_top.empty:
            st.markdown("---")
            rank_add_players = st.multiselect(
                "Add players from ranking to compare list",
                options=df_top["player_id"].tolist(),
                format_func=lambda x: df_top.set_index("player_id").loc[x, "player_name"] if x in df_top["player_id"].values else str(x),
                key="rank_add_compare",
            )
            if st.button("➕ Add selected to compare", key="rank_add_btn"):
                added = 0
                for rpid in rank_add_players:
                    player_rows = df_all[df_all["player_id"] == rpid]
                    if not player_rows.empty:
                        player_name = player_rows.iloc[0]["player_name"]
                        if add_to_compare(rpid, player_name):
                            added += 1
                st.toast(f"Added {added} player(s)") if added else st.info("No new players added.")


def _render_rising_stars_tab(df_all: pd.DataFrame) -> None:
    """Render the Rising Stars tab."""
    st.markdown("<div class='section-header'>📈 Rising Stars — Top Improvers</div>", unsafe_allow_html=True)
    st.caption("Ranks players by improvement vs. their previous season using progression deltas.")

    rs1, rs2, rs3, rs4 = st.columns(4)
    with rs1:
        rise_league = st.selectbox(
            "League",
            ["All"] + sorted(df_all["competition_slug"].unique()),
            format_func=lambda x: "All leagues" if x == "All" else f"{COMP_FLAGS.get(x,'🏆')} {COMP_NAMES.get(x,x)}",
            key="rise_league",
        )
    with rs2:
        rise_pos = st.selectbox(
            "Position",
            ["All"] + [p for p in POSITION_ORDER if p in df_all["player_position"].dropna().unique()],
            format_func=lambda x: "All" if x == "All" else POSITION_NAMES.get(x, x),
            key="rise_pos",
        )
    with rs3:
        rise_metric = st.selectbox(
            "Improvement metric",
            options=["avg_rating_delta", "expectedGoals_per90_delta", "expectedAssists_per90_delta",
                     "goals_per90_delta", "totalTackle_per90_delta"],
            format_func=lambda x: {
                "avg_rating_delta": "Rating improvement",
                "expectedGoals_per90_delta": "xG/90 improvement",
                "expectedAssists_per90_delta": "xA/90 improvement",
                "goals_per90_delta": "Goals/90 improvement",
                "totalTackle_per90_delta": "Tackles/90 improvement",
            }.get(x, x),
            key="rise_metric",
        )
    with rs4:
        rise_min_mins = st.number_input("Min. minutes", 0, 4000, 450, step=90, key="rise_mins")

    rise_n = st.slider("Top N", 5, 30, 15, step=5, key="rise_n")

    df_prog_all = load_player_progression()
    prog_filtered = df_prog_all.copy()

    if rise_league != "All":
        prog_filtered = prog_filtered[prog_filtered["competition_to"] == rise_league]
    if rise_pos != "All":
        prog_filtered = prog_filtered[prog_filtered["player_position"] == rise_pos]

    merged_prog = prog_filtered.merge(
        df_all[["player_id", "season", "competition_slug", "total_minutes", "team", "league_name", "avg_rating"]].rename(
            columns={"season": "season_to", "competition_slug": "competition_to"}
        ),
        on=["player_id", "season_to", "competition_to"],
        how="inner",
    )
    if rise_min_mins > 0:
        merged_prog = merged_prog[merged_prog["total_minutes"] >= rise_min_mins]

    if rise_metric not in merged_prog.columns:
        st.warning(f"Metric '{rise_metric}' not in progression data.")
    elif merged_prog.empty:
        st.info("No progression data for the selected filters.")
    else:
        top_risers = (
            merged_prog.dropna(subset=[rise_metric])
            .nlargest(rise_n, rise_metric)
            .reset_index(drop=True)
        )
        top_risers.index += 1

        metric_label_map = {
            "avg_rating_delta": "Rating Δ",
            "expectedGoals_per90_delta": "xG/90 Δ",
            "expectedAssists_per90_delta": "xA/90 Δ",
            "goals_per90_delta": "Goals/90 Δ",
            "totalTackle_per90_delta": "Tackles/90 Δ",
        }
        ml = metric_label_map.get(rise_metric, rise_metric)

        fig_rise = go.Figure(go.Bar(
            y=top_risers["player_name"],
            x=top_risers[rise_metric],
            orientation="h",
            marker_color="#6BCB77",
            text=top_risers[rise_metric].round(3).astype(str),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>" + ml + ": %{x:+.3f}<extra></extra>",
        ))
        fig_rise.update_layout(
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            font=dict(color="#E6EDF3"),
            xaxis=dict(gridcolor="#30363D", title=ml),
            yaxis=dict(categoryorder="total ascending", gridcolor="#30363D"),
            margin=dict(l=20, r=60, t=30, b=30),
            height=max(300, 35 * rise_n + 60),
            title=dict(text=f"Top {rise_n} Improvers — {ml}", font=dict(size=15)),
        )
        st.plotly_chart(fig_rise, use_container_width=True)

        rise_display_cols = ["player_name", "player_position", "team", "league_name",
                              "season_from", "season_to", "total_minutes", "avg_rating", rise_metric]
        rise_display = top_risers[[c for c in rise_display_cols if c in top_risers.columns]].copy()
        rise_display = rise_display.rename(columns={
            "player_name": "Player",
            "player_position": "Pos",
            "team": "Team",
            "league_name": "League",
            "season_from": "From",
            "season_to": "To",
            "total_minutes": "Mins",
            "avg_rating": "Current Rating",
            rise_metric: ml,
        })
        if "Mins" in rise_display.columns:
            rise_display["Mins"] = rise_display["Mins"].fillna(0).astype(int)
        for col in rise_display.select_dtypes("float").columns:
            rise_display[col] = rise_display[col].round(3)
        st.dataframe(rise_display, use_container_width=True, hide_index=False)


def _display_fit_analysis(
    prow: pd.Series,
    df_all: pd.DataFrame,
    chosen_season: str,
    chosen_comp: str,
    tac_row: pd.Series,
) -> None:
    """Display player-team fit analysis."""
    pool_fit = df_all[
        (df_all["season"] == chosen_season) &
        (df_all["competition_slug"] == chosen_comp)
    ]

    def pct_of(col):
        """Midpoint percentile: fraction below + half fraction equal, scaled 0–100."""
        if col not in pool_fit.columns:
            return 50
        s = pool_fit[col].dropna()
        v = prow.get(col)
        if pd.isna(v) or len(s) == 0:
            return 50
        below = (s < v).sum()
        equal = (s == v).sum()
        return float((below + 0.5 * equal) / len(s) * 100)

    fit_dims = {
        "Press Fit": (
            tac_row.get("pressing_index", 50) / 100 * pct_of("ballRecovery_per90") +
            tac_row.get("pressing_index", 50) / 100 * pct_of("totalTackle_per90")
        ) / 2,
        "Possession Fit": (
            tac_row.get("possession_index", 50) / 100 * pct_of("totalPass_per90") +
            tac_row.get("possession_index", 50) / 100 * pct_of("pass_accuracy_pct")
        ) / 2,
        "Aerial Fit": tac_row.get("aerial_index", 50) / 100 * pct_of("aerialWon_per90"),
        "Creative Fit": (
            tac_row.get("chance_creation_index", 50) / 100 * pct_of("keyPass_per90") +
            tac_row.get("crossing_index", 50) / 100 * pct_of("bigChanceCreated_per90")
        ) / 2,
        "Defensive Fit": tac_row.get("defensive_solidity", 50) / 100 * pct_of("duelWon_per90"),
    }

    overall_fit = np.mean(list(fit_dims.values()))
    st.markdown(f"**Overall fit score: {overall_fit:.0f} / 100**")
    for dim, score in fit_dims.items():
        st.progress(int(min(score, 100)) / 100, text=f"{dim}: {score:.0f}")
st.set_page_config(page_title="Scout · Schlouh", page_icon="🔍", layout="wide")
render_sidebar()
init_compare_list()

with st.spinner("Loading scouting data…"):
    df_all = load_enriched_season_stats()

# Data loader error handling: show message and retry if critical data missing
_critical_cols = ["player_id", "player_name", "player_position", "season"]
if df_all.empty or not all(c in df_all.columns for c in _critical_cols):
    st.error("Data temporarily unavailable. Please try again.")
    if st.button("Retry", type="primary"):
        load_enriched_season_stats.clear()
        st.rerun()
    st.stop()


# =============================================================================
# PROFILE VIEW
# =============================================================================
if is_profile_view_active():
    pid, pname = get_profile_player()

    if st.button("← Back to Scout", key="back_btn"):
        clear_profile_player()
        st.rerun()

    st.markdown(f"## 👤 {pname}")

    player_rows = df_all[df_all["player_id"] == pid].sort_values("season", ascending=False)

    if player_rows.empty:
        st.warning("No season data found for this player.")
    else:
        season_opts = player_rows[["season", "competition_slug", "league_name"]].drop_duplicates()
        season_labels = {
            f"{r['league_name']} {r['season']}": (r["season"], r["competition_slug"])
            for _, r in season_opts.iterrows()
        }
        chosen_label = st.selectbox("Season / League", list(season_labels.keys()), key="profile_season")
        chosen_season, chosen_comp = season_labels[chosen_label]

        prow = player_rows[
            (player_rows["season"] == chosen_season) & (player_rows["competition_slug"] == chosen_comp)
        ]

        if prow.empty:
            st.info("No data for this season/league combination.")
        else:
            prow = prow.iloc[0]
            flag = COMP_FLAGS.get(chosen_comp, "🏆")
            pos = POSITION_NAMES.get(prow.get("player_position"), prow.get("player_position", "—"))
            mins_val = int(prow.get("total_minutes", 0) or 0)
            apps_val = int(prow.get("appearances", 0) or 0)
            rel_tier = reliability_tier_from_minutes(mins_val)

            player_header_card(prow, flag, pos, apps_val, mins_val, rel_tier)

            # Load all profile data
            with st.spinner("Loading profile data…"):
                df_scout = load_scouting_profiles()
                df_rolling = load_rolling_form()
                df_opp = load_opponent_context_summary()
                df_career = load_career_stats()
                df_prog = load_player_progression()
                df_consistency = load_player_consistency()

            scout_row = df_scout[df_scout["player_id"] == pid]
            form_mask = (df_rolling["player_id"] == pid) & (df_rolling["window"] == 5)
            if "is_current" in df_rolling.columns:
                form_mask &= df_rolling["is_current"] == True
            form_row = df_rolling[form_mask]

            # Narrative
            if not scout_row.empty:
                sr = scout_row.iloc[0]
                fr_for_narrative = form_row.iloc[0] if not form_row.empty else None
                narrative = build_player_narrative(sr, fr_for_narrative, prow)
                with st.expander("📝 Auto-Brief", expanded=True):
                    st.markdown(f"<div class='narrative-box'>{narrative}</div>", unsafe_allow_html=True)

            # Rolling form
            form_metrics_row(form_row.iloc[0] if not form_row.empty else None)

            # Strengths
            cons_row = df_consistency[
                (df_consistency["player_id"] == pid) &
                (df_consistency["season"] == chosen_season) &
                (df_consistency["competition_slug"] == chosen_comp)
            ]

            if not scout_row.empty:
                strength_pills(scout_row.iloc[0])
                if not cons_row.empty:
                    tier_badge_html = consistency_badge(cons_row.iloc[0])
                    st.markdown(
                        f"<div class='section-header'>⭐ Strengths {tier_badge_html}</div>",
                        unsafe_allow_html=True,
                    )

            # Big game performance
            opp_row = df_opp[
                (df_opp["player_id"] == pid) &
                (df_opp["season"] == chosen_season) &
                (df_opp["competition_slug"] == chosen_comp)
            ]
            big_game_metrics(opp_row.iloc[0] if not opp_row.empty else None)

            # Season stats
            season_kpis(prow)
            league_benchmark_badge(df_all, prow, chosen_season, chosen_comp)
            st.caption("💰 **Valuation:** Not in dataset — link to internal model or external provider for cost/contract context.")

            # Progression
            prog_row = df_prog[
                (df_prog["player_id"] == pid) &
                (df_prog["season_to"] == chosen_season)
            ]
            if not prog_row.empty:
                progression_deltas(prog_row.iloc[0], prog_row.iloc[0].get("season_from", "prev"))

            # Goalkeeper card
            goalkeeper_card(prow)

            # Attacking/Defensive columns
            st.markdown("---")
            attacking_stats = {
                "Goals / 90": prow.get("goals_per90"),
                "xG / 90": prow.get("expectedGoals_per90"),
                "xA / 90": prow.get("expectedAssists_per90"),
                "Key Passes / 90": prow.get("keyPass_per90"),
                "Big Chances / 90": prow.get("bigChanceCreated_per90"),
                "Shots / 90": prow.get("totalShots_per90"),
                "On Target / 90": prow.get("onTargetScoringAttempt_per90"),
            }
            defensive_stats = {
                "Tackles / 90": prow.get("totalTackle_per90"),
                "Interceptions / 90": prow.get("interceptionWon_per90"),
                "Clearances / 90": prow.get("totalClearance_per90"),
                "Aerial Won / 90": prow.get("aerialWon_per90"),
                "Duels Won / 90": prow.get("duelWon_per90"),
                "Ball Recovery / 90": prow.get("ballRecovery_per90"),
                "Fouls / 90": prow.get("fouls_per90"),
            }
            stat_columns(attacking_stats, defensive_stats)

            # Career overview
            career_row = df_career[df_career["player_id"] == pid]
            career_overview_card(career_row)

            # Player-team fit
            df_tac = load_tactical_profiles()
            all_teams_for_fit = sorted(
                df_tac[
                    (df_tac["season"] == chosen_season) &
                    (df_tac["competition_slug"] == chosen_comp)
                ]["team_name"].unique()
            )
            if all_teams_for_fit:
                with st.expander("🔗 Player–Team Fit"):
                    st.caption("Heuristic fit score: maps player percentiles to team tactical indices.")
                    fit_team = st.selectbox("Select team to assess fit", all_teams_for_fit, key="fit_team_sel")
                    tac_row = df_tac[
                        (df_tac["team_name"] == fit_team) &
                        (df_tac["season"] == chosen_season) &
                        (df_tac["competition_slug"] == chosen_comp)
                    ]
                    if not tac_row.empty:
                        _display_fit_analysis(prow, df_all, chosen_season, chosen_comp, tac_row.iloc[0])

            # Match log
            with st.spinner("Loading match log…"):
                mlog = get_player_match_log(pid, season=chosen_season)
            player_match_log(mlog, pname)

            # Similar players
            player_pos = prow.get("player_position")
            if player_pos:
                st.markdown("<div class='section-header'>👥 Similar Players</div>", unsafe_allow_html=True)
                with st.spinner("Finding similar players…"):
                    similar = get_similar_players(
                        player_id=pid,
                        season=chosen_season,
                        competition_slug=chosen_comp,
                        position=player_pos,
                        df_all=df_all,
                        n=5,
                    )

                def on_add_similar(sim_pid: int, sim_name: str):
                    if add_to_compare(sim_pid, sim_name):
                        st.toast(f"✅ {sim_name} added")
                    else:
                        st.warning("Compare list full (max 6) or already added.")

                similar_players_cards(similar, on_add_similar)

            # Export
            st.markdown("---")
            export_player_brief(
                pname, prow, chosen_season, flag, pos, apps_val, mins_val, rel_tier,
                scout_row, form_row, cons_row,
            )

            # Add to compare + CTAs
            st.markdown("---")
            col_add, col_info = st.columns([1, 3])
            with col_add:
                if pid not in get_compare_list():
                    if st.button(f"➕ Add {pname} to Compare", key="add_compare_profile", type="primary"):
                        if add_to_compare(pid, pname):
                            st.success(f"{pname} added! ({get_compare_count()}/6 players)")
                        else:
                            st.warning("Compare list is full (max 6 players).")
                else:
                    st.info(f"✅ {pname} is already in your compare list.")

            with col_info:
                if get_compare_list():
                    st.markdown(
                        f"<p style='color:#8B949E;'>You have <b>{get_compare_count()}</b> player(s) in the compare list. "
                        f"Go to <b>Compare Players</b> to view them.</p>",
                        unsafe_allow_html=True,
                    )

            st.markdown("---")
            nav1, nav2 = st.columns(2)
            with nav1:
                st.page_link("pages/2_⚖️_Compare.py", label="⚖️ Go to Compare Players", use_container_width=True)
            with nav2:
                st.page_link("pages/3_📊_Explore.py", label="📊 Explore this league's data", use_container_width=True)


# =============================================================================
# SCOUT VIEW (LISTING)
# =============================================================================
else:
    st.markdown(
        """
        <div class="page-hero">
            <div class="page-hero-title">🔍 Scout Players</div>
            <div class="page-hero-sub">
                Filter, rank, and shortlist players across all competitions.
                Open a profile for detailed stats, form, and similar player recommendations.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        "Select a player in the dropdown below and click **View Profile** to open their detail. "
        "Use **Add to Compare** to add them to the comparison list."
    )

    tab_scout, tab_rankings, tab_rising = st.tabs(["🎯 Find Players", "🏆 Top N Rankings", "📈 Rising Stars"])

    # =====================================================================
    # TAB 1: FIND PLAYERS
    # =====================================================================
    with tab_scout:
        # Initialize filter state for debouncing
        if 'scout_filter_state' not in st.session_state:
            from dashboard.utils.filter_components import FilterState
            st.session_state.scout_filter_state = FilterState()

        # --- Text search (apply before filter panel: "search then filter")
        search_key = "player_text_search"
        if search_key not in st.session_state:
            st.session_state[search_key] = ""
        search_query = (st.session_state.get(search_key) or "").strip()
        df_for_panel = df_all.copy()
        if len(search_query) >= 2:
            norm = _normalize_search_text(df_for_panel["player_name"].fillna(""))
            df_for_panel = df_for_panel[norm.str.contains(_normalize_search_text(search_query), na=False)].copy()
        # Optional: recent searches (store last 5 in session)
        if "scout_recent_searches" not in st.session_state:
            st.session_state["scout_recent_searches"] = []

        search_col, clear_col = st.columns([3, 1])
        with search_col:
            st.text_input(
                "Search by player name",
                value=st.session_state.get(search_key, ""),
                key=search_key,
                placeholder="e.g. Mbappé, Salah (min 2 characters)",
                help="Type at least 2 characters to filter by name (accents ignored).",
            )
        with clear_col:
            from dashboard.utils.filter_components import FilterDefaults, render_clear_all_button
            scout_defaults = FilterDefaults(values={
                "scout_leagues": [], "scout_seasons": [], "scout_positions": [],
                "scout_mins": 500, "scout_age": [], "scout_teams": [], "scout_rating": 0.0,
                search_key: "",
            })
            if render_clear_all_button(scout_defaults, key_prefix="scout_clear_all"):
                st.rerun()

        if len(search_query) >= 2:
            recent = st.session_state.get("scout_recent_searches", [])
            if search_query not in recent:
                st.session_state["scout_recent_searches"] = [search_query] + [r for r in recent if r != search_query][:4]
        if len(search_query) >= 2 and len(df_for_panel) == 0:
            st.info("No players found for that search. Try a different spelling or fewer filters.")
            st.caption("Tip: Use 2+ characters; accents are ignored (e.g. Mbappe matches Mbappé).")
            if st.session_state.get("scout_recent_searches"):
                with st.expander("Recent searches"):
                    for r in st.session_state["scout_recent_searches"][:5]:
                        st.text(r)

        # Use EnhancedFilterPanel on search-filtered data
        panel = EnhancedFilterPanel(
            df_for_panel,
            "scout",
            show_top5_toggle=True,
            show_age=True,
            show_teams=True,
            show_rating=True,
            show_cascading=True,
        )

        config = panel.render()

        # Apply filters to search-filtered base
        with filter_loading_state("Applying filters..."):
            df_filtered = panel.apply_filters(df_for_panel, config)

        display_filter_summary(df_filtered, df_all)

        # Show enhanced no results state if empty, otherwise show results
        show_results = panel.render_no_results_if_empty(df_filtered, df_all, config)

        if show_results:
            # Build display table
            available_cols = [c for c in SCOUT_DISPLAY_COLS if c in df_filtered.columns]
            df_display = df_filtered[available_cols].copy().rename(columns=SCOUT_DISPLAY_COLS)

            for col in ["Rating", "G/90", "xG/90", "xA/90", "KP/90", "BCC/90", "Tkl/90", "Int/90", "DW/90", "Air/90", "Rec/90"]:
                if col in df_display.columns:
                    df_display[col] = df_display[col].round(2)
            for col in ["Mins", "Apps", "Goals", "Assists"]:
                if col in df_display.columns:
                    df_display[col] = df_display[col].fillna(0).astype(int)
            if "League" in df_display.columns:
                df_display["League"] = df_filtered["league_name"].values

            # Quick multi-select for compare
            st.markdown("<div class='section-header'>Quick Compare</div>", unsafe_allow_html=True)
            unique_players_for_select = (
                df_filtered[["player_id", "player_name"]].sort_values("player_name")
                .drop_duplicates("player_id")
            )
            quick_compare_ids = st.multiselect(
                "Select players to add to Compare list",
                options=unique_players_for_select["player_id"].tolist(),
                format_func=lambda x: unique_players_for_select.set_index("player_id").loc[x, "player_name"]
                    if x in unique_players_for_select["player_id"].values else str(x),
                key="quick_compare_multiselect",
                default=[],
            )
            if quick_compare_ids:
                if st.button("➕ Add selected to Compare", key="quick_compare_btn", type="primary"):
                    added = 0
                    for qpid in quick_compare_ids:
                        player_rows = df_all[df_all["player_id"] == qpid]
                        if not player_rows.empty:
                            player_name = player_rows.iloc[0]["player_name"]
                            if add_to_compare(qpid, player_name):
                                added += 1
                    if added:
                        st.toast(f"✅ {added} player(s) added to compare list")

            # Column selector
            default_visible = ["Player", "Pos", "Team", "League", "Season", "Apps", "Mins",
                               "Rating", "Goals", "Assists", "xG/90", "xA/90", "KP/90"]
            all_disp_cols = df_display.columns.tolist()
            visible_cols = st.multiselect(
                "Columns to show",
                options=all_disp_cols,
                default=[c for c in default_visible if c in all_disp_cols],
                key="visible_cols",
            )
            if not visible_cols:
                visible_cols = [c for c in default_visible if c in all_disp_cols]

            # Column config
            col_config = {}
            for display_col, tip in STAT_TOOLTIPS.items():
                if display_col in visible_cols and tip:
                    col_config[display_col] = st.column_config.NumberColumn(display_col, help=tip, format="%.2f")
            if "Rating" in visible_cols:
                col_config["Rating"] = st.column_config.ProgressColumn(
                    "Rating", help=STAT_TOOLTIPS.get("Rating", "SofaScore rating (1-10)."),
                    min_value=5.0, max_value=9.0, format="%.2f",
                )

            df_sorted = df_display[visible_cols].copy()
            if "Rating" in df_sorted.columns:
                df_sorted = df_sorted.sort_values("Rating", ascending=False, na_position="last")

            # Pagination for large result sets (PF.1)
            SCOUT_PAGE_SIZE = 50
            if "scout_table_page" not in st.session_state:
                st.session_state["scout_table_page"] = 0
            total_rows = len(df_sorted)
            total_pages = max(1, (total_rows + SCOUT_PAGE_SIZE - 1) // SCOUT_PAGE_SIZE)
            current_page = max(0, min(st.session_state["scout_table_page"], total_pages - 1))
            st.session_state["scout_table_page"] = current_page
            start_idx = current_page * SCOUT_PAGE_SIZE
            end_idx = min(start_idx + SCOUT_PAGE_SIZE, total_rows)
            df_page = df_sorted.iloc[start_idx:end_idx].reset_index(drop=True)
            st.dataframe(df_page, use_container_width=True, height=420, hide_index=True, column_config=col_config)
            if total_rows > SCOUT_PAGE_SIZE:
                p1, p2, p3 = st.columns([1, 2, 1])
                with p1:
                    if st.button("← Previous", key="scout_prev", disabled=(current_page == 0)):
                        st.session_state["scout_table_page"] = current_page - 1
                        st.rerun()
                with p2:
                    st.caption(f"Showing {start_idx + 1}–{end_idx} of {total_rows} · Page {current_page + 1} of {total_pages}")
                with p3:
                    if st.button("Next →", key="scout_next", disabled=(current_page >= total_pages - 1)):
                        st.session_state["scout_table_page"] = current_page + 1
                        st.rerun()

            # Single player actions
            col_sel, col_action = st.columns([2, 2])
            with col_sel:
                unique_players = (
                    df_filtered[["player_id", "player_name", "season"]].sort_values("season", ascending=False)
                    .drop_duplicates("player_id")
                )
                player_labels_unique = {row["player_id"]: row["player_name"] for _, row in unique_players.iterrows()}
                chosen_pid = st.selectbox(
                    "Select player for actions",
                    options=list(player_labels_unique.keys()),
                    format_func=lambda x: player_labels_unique.get(x, str(x)),
                    key="scout_player_select",
                    index=0,
                )
            with col_action:
                st.markdown("<br>", unsafe_allow_html=True)
                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("👤 View Profile", key="view_profile_btn", use_container_width=True):
                        set_profile_player(chosen_pid, player_labels_unique.get(chosen_pid, ""))
                        st.rerun()
                with bc2:
                    if st.button("➕ Add to Compare", key="add_compare_btn", use_container_width=True):
                        if chosen_pid not in get_compare_list():
                            if add_to_compare(chosen_pid, player_labels_unique.get(chosen_pid, "")):
                                st.toast(f"✅ {player_labels_unique.get(chosen_pid, '')} added")
                            else:
                                st.warning("Compare list full (max 6).")
                        else:
                            st.info("Player already in compare list.")

            display_compare_widget(df_all)
            if get_compare_list():
                if st.button("🗑️ Clear compare list", key="clear_compare_scout"):
                    clear_compare()
                    st.rerun()

            with st.expander("ℹ️ Metric Definitions"):
                for abbr, tip in STAT_TOOLTIPS.items():
                    st.markdown(f"**{abbr}** — {tip}")

            st.markdown("---")
            csv_bytes = df_filtered[available_cols].rename(columns=SCOUT_DISPLAY_COLS).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export current results (CSV)", data=csv_bytes, file_name="scout_results.csv", mime="text/csv")

    # =====================================================================
    # TAB 2: RANKINGS
    # =====================================================================
    with tab_rankings:
        _render_rankings_tab(df_all)

    # =====================================================================
    # TAB 3: RISING STARS
    # =====================================================================
    with tab_rising:
        _render_rising_stars_tab(df_all)


