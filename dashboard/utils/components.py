"""Reusable UI components for dashboard pages."""

from html import escape as _html_escape
from typing import Optional, List, Dict, Any, Callable
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from dashboard.utils.constants import (
    PLAYER_COLORS, POSITION_NAMES, COMP_FLAGS, COMP_NAMES,
    STAT_TOOLTIPS, RELIABILITY_MINUTES_LOW, RELIABILITY_MINUTES_MEDIUM,
)
from dashboard.utils.charts import rating_trend, xg_trend
from dashboard.utils.types import safe_get_player_name


def player_header_card(
    prow: pd.Series,
    flag: str,
    pos: str,
    apps_val: int,
    mins_val: int,
    rel_tier: str,
) -> None:
    """Display the player profile header card with key info."""
    rel_colors = {"High": "#C9A840", "Medium": "#FFD93D", "Low": "#FF6B6B"}
    rel_color = rel_colors.get(rel_tier, "#8B949E")
    team = prow.get("team", "—")
    age = prow.get("age_at_season_start")
    age_str = f"{age:.0f}" if pd.notna(age) else "Unknown"

    st.markdown(
        f"<div style='color:#8B949E;margin-bottom:0.4rem;'>"
        f"{flag} <b>{prow.get('league_name', '—')}</b> &nbsp;·&nbsp; {pos} &nbsp;·&nbsp; "
        f"{team} &nbsp;·&nbsp; Age {age_str}"
        f"</div>"
        f"<div style='font-size:0.85rem;color:#8B949E;margin-bottom:1rem;'>"
        f"Based on <b>{apps_val}</b> apps, <b>{mins_val:,}</b> min &nbsp;"
        f"<span style='background:{rel_color}22;border:1px solid {rel_color}55;border-radius:12px;"
        f"padding:2px 8px;font-size:0.78rem;font-weight:600;color:{rel_color};'>"
        f"Sample: {rel_tier}</span></div>",
        unsafe_allow_html=True,
    )


def metrics_row(
    metrics: Dict[str, Any],
    columns: int = 6,
) -> None:
    """Display a row of metrics in equal columns."""
    cols = st.columns(columns)
    for i, (label, value) in enumerate(metrics.items()):
        with cols[i % columns]:
            st.metric(label, value)


def season_kpis(prow: pd.Series) -> None:
    """Display season KPI metrics for a player."""
    st.markdown("<div class='section-header'>📊 Season Stats</div>", unsafe_allow_html=True)

    metrics = {
        "Apps": int(prow.get("appearances", 0) or 0),
        "Minutes": f"{int(prow.get('total_minutes', 0)):,}",
        "Rating": f"{prow.get('avg_rating', 0):.2f}",
        "Goals": int(prow.get("goals", 0) or 0),
        "Assists": int(prow.get("assists", 0) or 0),
        "xG/90": f"{prow.get('expectedGoals_per90', 0):.2f}",
    }
    metrics_row(metrics)


def league_benchmark_badge(
    df_all: pd.DataFrame,
    prow: pd.Series,
    chosen_season: str,
    chosen_comp: str,
) -> None:
    """Display league benchmark comparison badges."""
    from dashboard.utils.data import get_league_avg_stats

    league_avg = get_league_avg_stats(
        df_all, chosen_season, chosen_comp,
        ["avg_rating", "expectedGoals_per90", "expectedAssists_per90"],
        position=prow.get("player_position"),
        min_minutes=450,
    )

    if league_avg.empty:
        return

    vs_parts = []
    if "avg_rating" in league_avg and pd.notna(league_avg["avg_rating"]):
        r_val = prow.get("avg_rating")
        if pd.notna(r_val):
            vs_parts.append(f"Rating vs league avg: {r_val - league_avg['avg_rating']:+.2f}")

    if "expectedGoals_per90" in league_avg and pd.notna(league_avg["expectedGoals_per90"]):
        xg_val = prow.get("expectedGoals_per90")
        if pd.notna(xg_val):
            vs_parts.append(f"xG/90 vs avg: {xg_val - league_avg['expectedGoals_per90']:+.2f}")

    if "expectedAssists_per90" in league_avg and pd.notna(league_avg["expectedAssists_per90"]):
        xa_val = prow.get("expectedAssists_per90")
        if pd.notna(xa_val):
            vs_parts.append(f"xA/90 vs avg: {xa_val - league_avg['expectedAssists_per90']:+.2f}")

    if vs_parts:
        st.caption("📊 " + "  ·  ".join(vs_parts) + " (vs position in same league/season, min 450 min)")


def strength_pills(scout_row: Optional[pd.Series]) -> None:
    """Display strength pills from scouting profile."""
    if scout_row is None or scout_row.empty:
        return

    strength_pills_list = []
    for i in range(1, 4):
        sname = scout_row.get(f"top_pct_stat_{i}_name")
        spct = scout_row.get(f"top_pct_stat_{i}_pct")
        sval = scout_row.get(f"top_pct_stat_{i}_value")
        if pd.notna(sname) and pd.notna(spct):
            label = str(sname).replace("_per90", "/90").replace("_", " ").title()
            strength_pills_list.append(
                f"{label} ({spct:.0f}th pct, {sval:.2f})" if pd.notna(sval) else f"{label} ({spct:.0f}th pct)"
            )

    if strength_pills_list:
        st.markdown(
            f"<div class='section-header'>⭐ Strengths</div>",
            unsafe_allow_html=True,
        )
        pills_html = "".join(f"<span class='strength-pill'>{p}</span>" for p in strength_pills_list)
        st.markdown(f"<div>{pills_html}</div><br>", unsafe_allow_html=True)


def consistency_badge(cons_row: Optional[pd.Series]) -> str:
    """Generate HTML for consistency badge."""
    if cons_row is None or cons_row.empty:
        return ""

    tier = cons_row.get("consistency_tier", "")
    tier_colors = {"Elite": "#C9A840", "High": "#6BCB77", "Medium": "#FFD93D", "Low": "#FF6B6B"}
    tier_color = tier_colors.get(tier, "#8B949E")
    r_min = float(cons_row.get("rating_min") or 0)
    r_max = float(cons_row.get("rating_max") or 0)
    r_cv_raw = cons_row.get("rating_cv")
    r_cv = float(r_cv_raw) if pd.notna(r_cv_raw) else 0.0

    return (
        f"<span class='consistency-badge' style='background:{tier_color}22;"
        f"border:1px solid {tier_color}55;color:{tier_color};'>"
        f"{tier} consistency · Range {r_min:.1f}–{r_max:.1f} · CV {r_cv:.2f}</span>"
    )


def form_metrics_row(form_row: Optional[pd.Series]) -> None:
    """Display rolling form metrics in a row."""
    if form_row is None or form_row.empty:
        return

    st.markdown("<div class='section-header'>🔥 Recent Form (Last 5 Matches)</div>", unsafe_allow_html=True)

    fm1, fm2, fm3, fm4, fm5 = st.columns(5)
    fm1.metric("Form Rating", f"{form_row.get('avg_rating', 0):.2f}")
    fm2.metric("Goals", int(form_row.get("goals", 0) or 0))
    fm3.metric("Assists", int(form_row.get("assists", 0) or 0))
    fm4.metric("xG", f"{form_row.get('xg_total', 0):.2f}")
    fm5.metric("xA", f"{form_row.get('xa_total', 0):.2f}")

    st.markdown("---")


def big_game_metrics(opp_row: Optional[pd.Series]) -> None:
    """Display big game performance metrics."""
    if opp_row is None or opp_row.empty:
        return

    st.markdown("<div class='section-header'>🎯 Big Game Performance</div>", unsafe_allow_html=True)

    og1, og2, og3 = st.columns(3)
    og1.metric("vs Top Teams", f"{opp_row.get('rating_vs_top', 0):.2f}")
    og2.metric("vs Bottom Teams", f"{opp_row.get('rating_vs_bottom', 0):.2f}")
    delta = opp_row.get("big_game_rating_delta", 0)
    og3.metric(
        "Big Game Delta",
        f"{delta:+.2f}",
        delta_color="normal" if delta >= 0 else "inverse",
        help="Positive = performs better vs top opposition",
    )


def progression_deltas(prog_row: Optional[pd.Series], season_from: str) -> None:
    """Display season-on-season progression deltas."""
    if prog_row is None or prog_row.empty:
        return

    delta_pairs = [
        ("Rating", prog_row.get("avg_rating_delta")),
        ("xG/90", prog_row.get("expectedGoals_per90_delta")),
        ("xA/90", prog_row.get("expectedAssists_per90_delta")),
        ("Tkl/90", prog_row.get("totalTackle_per90_delta")),
    ]

    deltas_html = " &nbsp;|&nbsp; ".join(
        f"<span style='color:{'#6BCB77' if v > 0 else '#FF6B6B'};'>{k}: {v:+.2f}</span>"
        for k, v in delta_pairs if pd.notna(v)
    )

    if deltas_html:
        st.markdown(
            f"<div style='font-size:0.83rem;color:#8B949E;margin-bottom:0.5rem;'>"
            f"vs {season_from}: {deltas_html}</div>",
            unsafe_allow_html=True,
        )


def stat_columns(
    left_stats: Dict[str, Any],
    right_stats: Dict[str, Any],
    left_title: str = "⚡ Attacking",
    right_title: str = "🛡️ Defensive",
) -> None:
    """Display two columns of stats."""
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(f"<div class='section-header'>{left_title}</div>", unsafe_allow_html=True)
        for k, v in left_stats.items():
            if pd.notna(v) and v > 0:
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
                    f"border-bottom:1px solid #30363D;'>"
                    f"<span style='color:#8B949E;'>{k}</span>"
                    f"<span style='font-weight:600;'>{v:.2f}</span></div>",
                    unsafe_allow_html=True,
                )

    with col_r:
        st.markdown(f"<div class='section-header'>{right_title}</div>", unsafe_allow_html=True)
        for k, v in right_stats.items():
            if pd.notna(v) and v > 0:
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
                    f"border-bottom:1px solid #30363D;'>"
                    f"<span style='color:#8B949E;'>{k}</span>"
                    f"<span style='font-weight:600;'>{v:.2f}</span></div>",
                    unsafe_allow_html=True,
                )


def goalkeeper_card(prow: pd.Series) -> None:
    """Display goalkeeper-specific stats card."""
    if prow.get("player_position") != "G":
        return

    st.markdown("<div class='section-header'>🧤 Goalkeeper Summary</div>", unsafe_allow_html=True)

    gk_specs = [
        ("saves_per90", "Saves/90"),
        ("goalsPrevented_per90", "Goals Prevented/90"),
        ("pass_accuracy_pct", "Pass %"),
        ("totalPass_per90", "Passes/90"),
        ("savedShotsFromInsideTheBox_per90", "Saves In-Box/90"),
        ("goodHighClaim_per90", "High Claims/90"),
        ("totalKeeperSweeper_per90", "Sweeper/90"),
    ]

    gk_vals = [(col, label, prow.get(col)) for col, label in gk_specs if pd.notna(prow.get(col))]
    g1, g2, g3, g4 = st.columns(4)

    for idx, (col, label, val) in enumerate(gk_vals[:8]):
        with [g1, g2, g3, g4][idx % 4]:
            fmt = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
            st.metric(label, fmt)

    st.markdown("---")


def career_overview_card(career_row: Optional[pd.Series]) -> None:
    """Display career overview in an expander."""
    if career_row is None or career_row.empty:
        return

    cr = career_row.iloc[0] if hasattr(career_row, "iloc") else career_row

    with st.expander("📋 Career Overview"):
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric(
            "Peak Rating",
            f"{cr.get('peak_rating', 0):.2f}" if pd.notna(cr.get("peak_rating")) else "—",
        )
        cc2.metric("Peak Season", cr.get("peak_rating_season", "—"))
        cc3.metric("Seasons", int(cr.get("n_seasons", 0)))
        cc4.metric("Career Apps", int(cr.get("appearances", 0)))

        comp_list = cr.get("competitions_list", "")
        if comp_list:
            comps = comp_list if isinstance(comp_list, str) else ", ".join(comp_list)
            st.markdown(f"**Competitions:** {comps}")


def similar_players_cards(
    similar_df: Optional[pd.DataFrame],
    on_add_to_compare: Optional[Callable[[int, str], None]] = None,
) -> None:
    """Display similar player cards."""
    if similar_df is None or similar_df.empty:
        st.info("Not enough players in the same position/season/league for comparison.")
        return

    st.markdown("<div class='section-header'>👥 Similar Players</div>", unsafe_allow_html=True)
    st.caption("Euclidean distance on normalized per-90 stats within same position/season/league.")

    sim_cols = st.columns(min(5, len(similar_df)))

    for i, (_, sr) in enumerate(similar_df.iterrows()):
        color = PLAYER_COLORS[(i + 1) % len(PLAYER_COLORS)]
        with sim_cols[i]:
            rating_str = f"{sr.get('avg_rating', 0):.2f}" if pd.notna(sr.get("avg_rating")) else "—"
            xg_str = f"{sr.get('expectedGoals_per90', 0):.2f}" if pd.notna(sr.get("expectedGoals_per90")) else "—"
            xa_str = f"{sr.get('expectedAssists_per90', 0):.2f}" if pd.notna(sr.get("expectedAssists_per90")) else "—"

            st.markdown(
                f"<div class='sim-card'>"
                f"<b style='color:{color};font-size:0.85rem;'>{sr['player_name']}</b><br>"
                f"<span style='font-size:0.75rem;color:#8B949E;'>{sr.get('team','')}</span><br>"
                f"<span style='font-size:0.8rem;'>⭐ {rating_str} · xG {xg_str} · xA {xa_str}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            sim_pid = int(sr["player_id"])
            if on_add_to_compare and st.button(
                "➕ Compare",
                key=f"sim_add_{i}_{sim_pid}",
                use_container_width=True,
            ):
                on_add_to_compare(sim_pid, sr["player_name"])


def player_match_log(mlog: pd.DataFrame, pname: str) -> None:
    """Display player match log with charts."""
    if mlog.empty:
        st.info("No match-level data available for this season.")
        return

    st.markdown("<div class='section-header'>📈 Form over time</div>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Rating", "xG"])
    with tab1:
        st.plotly_chart(rating_trend(mlog, pname), use_container_width=True)
    with tab2:
        st.plotly_chart(xg_trend(mlog, pname), use_container_width=True)

    st.markdown("<div class='section-header'>📋 Match Log</div>", unsafe_allow_html=True)

    log_cols = [
        "match_date_utc", "stat_minutesPlayed", "stat_rating",
        "stat_goals", "stat_goalAssist", "stat_expectedGoals",
        "stat_expectedAssists", "stat_keyPass", "stat_totalTackle",
    ]
    if "opponent" in mlog.columns:
        log_cols = ["match_date_utc", "opponent"] + log_cols[1:]

    available_log_cols = [c for c in log_cols if c in mlog.columns]
    log_display = mlog[available_log_cols].rename(columns={
        "match_date_utc": "Date",
        "opponent": "Opponent",
        "stat_minutesPlayed": "Mins",
        "stat_rating": "Rating",
        "stat_goals": "Goals",
        "stat_goalAssist": "Assists",
        "stat_expectedGoals": "xG",
        "stat_expectedAssists": "xA",
        "stat_keyPass": "KP",
        "stat_totalTackle": "Tkl",
    }).copy()

    if "Date" in log_display.columns:
        log_display["Date"] = pd.to_datetime(log_display["Date"]).dt.strftime("%Y-%m-%d")

    for col in ["Mins", "Goals", "Assists", "KP", "Tkl"]:
        if col in log_display.columns:
            log_display[col] = log_display[col].fillna(0).astype(int)

    for col in ["Rating", "xG", "xA"]:
        if col in log_display.columns:
            log_display[col] = log_display[col].round(2)

    st.dataframe(log_display, use_container_width=True, hide_index=True)


def export_player_brief(
    pname: str,
    prow: pd.Series,
    chosen_season: str,
    flag: str,
    pos: str,
    apps_val: int,
    mins_val: int,
    rel_tier: str,
    scout_row: Optional[pd.Series],
    form_row: Optional[pd.Series],
    cons_row: Optional[pd.Series],
) -> None:
    """Generate and provide download for player brief HTML."""
    from datetime import datetime

    brief_narrative = ""
    if scout_row is not None and not scout_row.empty:
        from dashboard.utils.data import build_player_narrative
        fr_for_narrative = form_row.iloc[0] if form_row is not None and not form_row.empty else None
        brief_narrative = build_player_narrative(scout_row.iloc[0], fr_for_narrative, prow)

    brief_stats = (
        f"Apps {int(prow.get('appearances', 0) or 0)} · "
        f"Mins {int(prow.get('total_minutes', 0) or 0):,} · "
        f"Rating {prow.get('avg_rating', 0):.2f} · "
        f"G {int(prow.get('goals', 0) or 0)} A {int(prow.get('assists', 0) or 0)} · "
        f"xG/90 {prow.get('expectedGoals_per90', 0):.2f} xA/90 {prow.get('expectedAssists_per90', 0):.2f}"
    )

    brief_strengths = ""
    if scout_row is not None and not scout_row.empty:
        sr = scout_row.iloc[0]
        parts = []
        for i in range(1, 4):
            sname = sr.get(f"top_pct_stat_{i}_name")
            spct = sr.get(f"top_pct_stat_{i}_pct")
            if pd.notna(sname) and pd.notna(spct):
                parts.append(f"{str(sname).replace('_per90','/90').replace('_',' ').title()} ({spct:.0f}th pct)")
        if parts:
            brief_strengths = "Strengths: " + ", ".join(parts)

    brief_consistency = ""
    if cons_row is not None and not cons_row.empty:
        cr = cons_row.iloc[0] if hasattr(cons_row, "iloc") else cons_row
        brief_consistency = f"Consistency: {cr.get('consistency_tier','—')} (range {cr.get('rating_min',0):.1f}–{cr.get('rating_max',0):.1f})"

    brief_form = ""
    if form_row is not None and not form_row.empty:
        fr = form_row.iloc[0] if hasattr(form_row, "iloc") else form_row
        brief_form = (
            f"Last 5: Rating {fr.get('avg_rating',0):.2f} · "
            f"G {int(fr.get('goals',0) or 0)} A {int(fr.get('assists',0) or 0)} · "
            f"xG {fr.get('xg_total',0):.2f} xA {fr.get('xa_total',0):.2f}"
        )

    age = prow.get("age_at_season_start")
    age_str = f"{age:.0f}" if pd.notna(age) else "Unknown"
    team = prow.get("team", "—")

    html_brief = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Brief – {pname}</title>
</head>
<body style="font-family:sans-serif;max-width:720px;margin:24px auto;color:#1a1a1a;line-height:1.5;">
<h1>{pname}</h1>
<p style="color:#555;">{flag} {prow.get('league_name','')} {chosen_season} · {pos} · {team} · Age {age_str}</p>
<p style="font-size:0.9rem;">Based on <b>{apps_val}</b> apps, <b>{mins_val:,}</b> min · Sample: <b>{rel_tier}</b></p>
<p><b>Key stats:</b> {brief_stats}</p>
{f'<p><b>Brief:</b> {brief_narrative}</p>' if brief_narrative else ''}
{f'<p>{brief_strengths}</p>' if brief_strengths else ''}
{f'<p>{brief_consistency}</p>' if brief_consistency else ''}
{f'<p>{brief_form}</p>' if brief_form else ''}
<p style="font-size:0.85rem;color:#777;">Valuation not in dataset — link to internal model. Generated by Schlouh Scouting · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
</body>
</html>"""

    st.download_button(
        "📄 Export Player Brief (HTML)",
        data=html_brief.encode("utf-8"),
        file_name=f"brief_{pname.replace(' ', '_')}_{chosen_season}.html",
        mime="text/html",
        key="export_brief_html",
    )
