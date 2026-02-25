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

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
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
    load_player_progression,
    format_percentile,
)
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS, TACTICAL_INDEX_LABELS, TACTICAL_TAGS
from dashboard.utils.scope import CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.utils.validation import safe_divide
from dashboard.tactics.layout import render_tactics_sidebar
# Import enhanced tactical components
from dashboard.tactics.components.tactical_components import (
    render_formation_pitch,
    render_formation_selector,
    render_tactical_roles_matrix,
    render_opposition_scouting_card,
    render_tactical_style_evolution,
    TACTICAL_RADAR_INDICES_FULL,
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

render_tactics_sidebar()

# Initialize session state
if "selected_team" not in st.session_state:
    st.session_state.selected_team = None
if "selected_formation" not in st.session_state:
    st.session_state.selected_formation = "4-3-3"

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

    # Team selector (default: current season + leagues/UEFA)
    if not team_stats.empty:
        default_scope = team_stats[
            (team_stats["season"] == CURRENT_SEASON) &
            (team_stats["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS))
        ]
        team_options = (default_scope if not default_scope.empty else team_stats)[["team_name", "season", "competition_slug"]].drop_duplicates()
        # Match count per (team, season, comp) for dropdown label
        match_counts = team_stats.groupby(["team_name", "season", "competition_slug"]).size().reset_index(name="n_matches")
        team_options = team_options.merge(match_counts, on=["team_name", "season", "competition_slug"], how="left")
        team_options["label"] = team_options.apply(
            lambda r: f"{r['team_name']} ({r['season']}, {COMP_NAMES.get(r['competition_slug'], r['competition_slug'])} — {int(r.get('n_matches', 0))} matches)",
            axis=1
        )
        st.caption("Default: current season, leagues + UEFA. Select team to analyze.")

        selected_label = st.selectbox("Select team:", team_options["label"].tolist(), key="profile_team_select")
        selected_row = team_options[team_options["label"] == selected_label].iloc[0]
        comps_for_team = team_stats[
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
        st.error("No team data available")
    st.stop()

# ---------------------------------------------------------------------------
# Display Team Profile (one team; filter by competition when team plays in multiple)
# ---------------------------------------------------------------------------
team_info = st.session_state.selected_team
team_name = team_info["name"]
season = team_info["season"]
# Support both legacy single "competition" and new "competitions" list from Directory
comps_list = team_info.get("competitions")
if comps_list:
    # Build option labels with match count
    match_counts = {}
    for c in comps_list:
        r = team_stats[(team_stats["team_name"] == team_name) & (team_stats["season"] == season) & (team_stats["competition_slug"] == c)]
        match_counts[c] = int(r["matches_total"].iloc[0]) if not r.empty and "matches_total" in r.columns else 0
    comp_option = st.selectbox(
        "View data from:",
        options=comps_list,
        format_func=lambda c: f"{COMP_FLAGS.get(c, '🏆')} {COMP_NAMES.get(c, c)} ({match_counts.get(c, 0)} matches)",
        key="tactical_profile_comp_filter",
        help="Same team in multiple competitions (e.g. league + UCL). Choose which to analyze.",
    )
    competition = comp_option
else:
    competition = team_info.get("competition", "")

st.markdown(
    f"""
    <div class="page-hero">
        <div class="page-hero-title">📐 {team_name}</div>
        <div class="page-hero-sub">
            {COMP_FLAGS.get(competition, '🏆')} {COMP_NAMES.get(competition, competition)} · {season}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Get team data
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
tac_data = tac_row.iloc[0] if not tac_row.empty else None

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
    pool = tactical_df[
        (tactical_df["season"] == tac_data.get("season")) &
        (tactical_df["competition_slug"] == tac_data.get("competition_slug"))
    ]
    if pool.empty:
        pool = tactical_df
    percentiles = get_tactical_percentiles(tac_data, pool)

# Build strengths/weaknesses with cited metrics (for briefing and S&W section)
def _pct_label(idx: str) -> str:
    for k, label in TACTICAL_RADAR_INDICES_FULL:
        if k == idx:
            return label
    return idx.replace("_index", "").replace("_", " ").title()

_strengths_with_citation = []
_weaknesses_with_citation = []
if tac_data is not None:
    if tac_data.get("possession_index", 0) > 75:
        _strengths_with_citation.append(("Excellent ball retention and control", "possession_index"))
    if tac_data.get("pressing_index", 0) > 75:
        _strengths_with_citation.append(("Aggressive high press disrupts opponents", "pressing_index"))
    if tac_data.get("chance_creation_index", 0) > 75:
        _strengths_with_citation.append(("Creates high-quality scoring opportunities", "chance_creation_index"))
    if tac_data.get("defensive_solidity", 0) > 75:
        _strengths_with_citation.append(("Strong defensive organization", "defensive_solidity"))
    if team_data.get("xg_for_total", 0) > (team_data.get("goals_for", 0) or 0) * 1.1:
        _strengths_with_citation.append(("Creates more chances than goals suggest (unlucky)", None))
    if tac_data.get("defensive_solidity", 0) < 40:
        _weaknesses_with_citation.append(("Defensive vulnerabilities", "defensive_solidity"))
    if tac_data.get("pressing_index", 0) < 30:
        _weaknesses_with_citation.append(("Passive without ball - allows opponents to build", "pressing_index"))
    if tac_data.get("possession_index", 0) < 30:
        _weaknesses_with_citation.append(("Struggles to retain possession under pressure", "possession_index"))
    if (team_data.get("xg_against_total", 0) or 0) > (team_data.get("goals_against", 0) or 0) * 1.1:
        _weaknesses_with_citation.append(("Conceding fewer than xG suggests (lucky - may regress)", None))
    if (team_data.get("goals_against", 0) or 0) > (team_data.get("matches_total", 0) or 1) * 1.5:
        _weaknesses_with_citation.append(("High goals conceded rate", None))

# ---------------------------------------------------------------------------
# Briefing summary (one-block opponent profile headline)
# ---------------------------------------------------------------------------
_form_info = _team_form(team_name, season, competition or "", n=5)
_last5_brief = get_team_last_matches(team_name, season, competition or "", n=5) if competition else pd.DataFrame()
_brief_form = st.session_state.get("selected_formation", "4-3-3")
_brief_styles = []
if tac_data is not None:
    for idx, (thr, label) in TACTICAL_TAGS.items():
        if tac_data.get(idx, 0) >= thr:
            _brief_styles.append(label)
if tac_data.get("second_half_intensity", 0) >= 65:
    _brief_styles.append("Second-half team")
if tac_data.get("home_away_consistency", 0) >= 65:
    _brief_styles.append("Strong home/away consistency")
if not _brief_styles:
    _brief_styles = ["Balanced approach"]
_brief_strength_str = ", ".join([s[0] for s in _strengths_with_citation[:3]]) if _strengths_with_citation else "—"
_brief_weak_str = ", ".join([w[0] for w in _weaknesses_with_citation[:3]]) if _weaknesses_with_citation else "—"
_brief_form_str = _form_info.get("form_string", "") or "—"
_brief_pts = _form_info.get("points", 0)
st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#161B22 0%,#0D1117 100%);border:1px solid #30363D;border-radius:8px;padding:16px;margin-bottom:16px;">
        <div style="font-size:0.75rem;color:#8B949E;margin-bottom:6px;">📋 Briefing summary</div>
        <div style="font-size:0.9rem;color:#E6EDF3;line-height:1.5;">
            <strong>Formation (est.):</strong> {_brief_form} · <strong>Style:</strong> {", ".join(_brief_styles)}<br/>
            <strong>Strengths:</strong> {_brief_strength_str} · <strong>Weaknesses:</strong> {_brief_weak_str}<br/>
            <strong>Last 5:</strong> {_brief_form_str} ({_brief_pts} pts)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header Stats (incl. W-D-L, GD, per-game)
# ---------------------------------------------------------------------------
st.markdown("---")
wdl = get_team_wdl(team_name, season, competition) if competition else {}
matches_total = int(team_data.get("matches_total", 0)) or 1
goals_for = int(team_data.get("goals_for", 0))
goals_against = int(team_data.get("goals_against", 0))
gd = goals_for - goals_against
xgd = (team_data.get("xg_for_total", 0) or 0) - (team_data.get("xg_against_total", 0) or 0)
points = 3 * wdl.get("W", 0) + wdl.get("D", 0)

cols = st.columns(8)
metrics = [
    ("Position", f"#{team_data.get('position_ordinal', '?')}"),
    ("Matches", f"{int(team_data.get('matches_total', 0))}"),
    ("W-D-L", f"{wdl.get('W', 0)}-{wdl.get('D', 0)}-{wdl.get('L', 0)}" if wdl else "—"),
    ("Pts", f"{points}" if wdl else "—"),
    ("GD", f"{gd:+d}"),
    ("xGD", f"{xgd:+.1f}"),
    ("G/game", f"{safe_divide(goals_for, matches_total, default=0):.1f}" if matches_total else "—"),
    ("xG/game", f"{safe_divide(team_data.get('xg_for_total', 0) or 0, matches_total, default=0):.1f}" if matches_total else "—"),
]

for col, (label, value) in zip(cols, metrics):
    with col:
        st.markdown(
            f"""
            <div style="text-align:center;padding:10px;background:#161B22;border-radius:6px;border:1px solid #30363D;">
                <div style="font-size:0.75rem;color:#8B949E;">{label}</div>
                <div style="font-size:1.2rem;font-weight:700;color:#C9A840;">{value}</div>
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
        # Pool already computed above for briefing/percentiles
        radar_vals = normalize_tactical_radar_to_100(tac_data, pool, TACTICAL_RADAR_INDICES_FULL)
        labels = [l for _, l in TACTICAL_RADAR_INDICES_FULL]

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
        # Tactical style description
        st.markdown("**Playing Style**")

        # Determine dominant styles using TACTICAL_TAGS (threshold, label)
        dominant = []
        for idx, (threshold, label) in TACTICAL_TAGS.items():
            if tac_data.get(idx, 0) >= threshold:
                dominant.append(label)

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

        # Index breakdown with league percentile when pool available (improvement #23)
        st.markdown("**Key Metrics** (value · league percentile)")
        for idx, label in TACTICAL_RADAR_INDICES_FULL[:5]:
            val = tac_data.get(idx)
            if pd.notna(val) and not pool.empty and idx in pool.columns:
                pct_rank = (pool[idx] < val).sum() / len(pool) * 100 if len(pool) > 0 else 50
                pct_str = f" · {int(pct_rank)}th in league"
            else:
                pct_str = ""
            if pd.notna(val):
                bar_width = min(100, max(0, int(val)))
                st.markdown(
                    f"""
                    <div style="margin:8px 0;">
                        <div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:2px;">
                            <span style="color:#8B949E;">{label}</span>
                            <span style="color:#F0F6FC;">{val:.0f}{pct_str}</span>
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
# Recent Form (last 5 + form summary)
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>📈 Recent Form</div>", unsafe_allow_html=True)
if competition:
    last5 = get_team_last_matches(team_name, season, competition, n=5)
    if not last5.empty:
        form_info = _team_form(team_name, season, competition, n=5)
        form_str = form_info.get("form_string", "") or "—"
        pts = form_info.get("points", 0)
        xg_f = last5["xg_for"].sum() if "xg_for" in last5.columns else None
        xg_a = last5["xg_against"].sum() if "xg_against" in last5.columns else None
        if xg_f is not None and pd.notna(xg_f) and xg_a is not None and pd.notna(xg_a):
            summary_line = f"**Form:** {form_str} ({pts} pts) · **xG last 5:** {xg_f:.1f} for, {xg_a:.1f} against"
        else:
            summary_line = f"**Form:** {form_str} ({pts} pts)"
        st.markdown(summary_line)
        for _, m in last5.iterrows():
            res = m.get("result", "?")
            res_color = "#3FB950" if res == "W" else "#C9A840" if res == "D" else "#F85149"
            xg_str = ""
            if "xg_for" in m and pd.notna(m.get("xg_for")):
                xg_str = f" (xG: {m.get('xg_for', 0):.1f}-{m.get('xg_against', 0):.1f})"
            st.markdown(
                f"<div style='padding:6px 0;'><span style='color:{res_color};font-weight:600;'>{res}</span> "
                f"{m.get('home_away', '')} {m.get('score', '')} vs {m.get('opponent', '')}{xg_str}</div>",
                unsafe_allow_html=True,
            )
        st.caption("Last 5 matches in this competition. xG when available.")
    else:
        st.caption("No match history available for this season/competition.")
else:
    st.caption("Select a competition to see recent form.")

# ---------------------------------------------------------------------------
# Home vs Away
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🏠 Home vs Away</div>", unsafe_allow_html=True)
if competition:
    ha = _team_home_away_summary(team_name, season, competition)
    h, a = ha["home"], ha["away"]
    hm, am = h["matches"] or 1, a["matches"] or 1
    col_h, col_a = st.columns(2)
    with col_h:
        st.markdown("**Home**")
        st.markdown(f"W-D-L: {h['W']}-{h['D']}-{h['L']} ({h['matches']} matches)")
        st.markdown(f"Goals: {h['goals_for']} for, {h['goals_against']} against")
        if h.get("xg_for") is not None and pd.notna(h.get("xg_for")):
            st.markdown(f"xG: {h['xg_for']:.1f} for, {h['xg_against']:.1f} against")
        if hm > 0:
            st.caption(f"xG/game: {(h.get('xg_for') or 0) / hm:.1f} for · {(h.get('xg_against') or 0) / hm:.1f} against")
    with col_a:
        st.markdown("**Away**")
        st.markdown(f"W-D-L: {a['W']}-{a['D']}-{a['L']} ({a['matches']} matches)")
        st.markdown(f"Goals: {a['goals_for']} for, {a['goals_against']} against")
        if a.get("xg_for") is not None and pd.notna(a.get("xg_for")):
            st.markdown(f"xG: {a['xg_for']:.1f} for, {a['xg_against']:.1f} against")
        if am > 0:
            st.caption(f"xG/game: {(a.get('xg_for') or 0) / am:.1f} for · {(a.get('xg_against') or 0) / am:.1f} against")
else:
    st.caption("Select a competition to see home/away split.")

# ---------------------------------------------------------------------------
# Squad: All players (table) — right after form/context so you know WHO they are
# ---------------------------------------------------------------------------
if not player_df.empty:
    squad_table_df = player_df[
        (player_df["team"] == team_name) &
        (player_df["season"] == season) &
        (player_df["competition_slug"] == competition)
    ].copy()

    if not squad_table_df.empty:
        st.markdown("---")
        st.markdown("<div class='section-header'>📋 Squad — All players & statistics</div>", unsafe_allow_html=True)
        st.caption("Full squad for this season/competition. Sort by clicking column headers. Use this to get to know every player.")

        display_cols = [
            "player_name", "player_position", "age_at_season_start", "age_band",
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
            "age_band": "Age band",
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

        for col in table_df.select_dtypes(include=[np.floating]).columns:
            table_df[col] = table_df[col].round(2)
        if "Mins" in table_df.columns:
            table_df["Mins"] = table_df["Mins"].fillna(0).astype(int)
        if "Apps" in table_df.columns:
            table_df["Apps"] = table_df["Apps"].fillna(0).astype(int)

        st.dataframe(table_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Formation Visualization
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>⚽ Formation Analysis</div>", unsafe_allow_html=True)
formation_col, squad_col = st.columns([2, 1])

with formation_col:
    available_formations = ['4-3-3', '4-4-2', '3-4-3', '5-3-2', '4-2-3-1']
    selected_formation = render_formation_selector(
        available_formations,
        default=st.session_state.get('selected_formation', '4-3-3'),
        key='formation_select'
    )
    st.session_state.selected_formation = selected_formation

    team_players = []
    if not player_df.empty:
        team_players_df = player_df[
            (player_df["team"] == team_name) &
            (player_df["season"] == season) &
            (player_df["competition_slug"] == competition)
        ].sort_values("total_minutes", ascending=False)
        for _, player in team_players_df.head(11).iterrows():
            team_players.append({
                'name': player['player_name'],
                'position': player['player_position'],
                'rating': player.get('avg_rating', 6.5),
                'role': player.get('tactical_role', 'Standard')
            })

    if team_players:
        render_formation_pitch(
            formation=selected_formation,
            players=team_players,
            width=700,
            height=550
        )
    else:
        st.info("Player data not available for formation display")

with squad_col:
    st.markdown("**Squad Composition**")
    if not player_df.empty:
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
                    band_counts = bands.value_counts().sort_index()
                else:
                    band_counts = team_players_full[age_col].value_counts()
                st.markdown("**Age profile**")
                for band, count in band_counts.items():
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 0;'><span style='color:#8B949E;'>{band}</span><span style='color:#F0F6FC;'>{count}</span></div>", unsafe_allow_html=True)
                st.divider()
            pos_dist = team_players_full.groupby("player_position")["player_id"].nunique()
            st.markdown("**By Position**")
            for pos, count in pos_dist.items():
                pos_name = {'G': 'Goalkeeper', 'D': 'Defender', 'M': 'Midfielder', 'F': 'Forward'}.get(pos, pos)
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #30363D;'><span style='color:#8B949E;'>{pos_name}</span><span style='color:#F0F6FC;font-weight:500;'>{count}</span></div>",
                    unsafe_allow_html=True
                )
            st.divider()
            st.markdown("**Top Performers**")
            top_players = team_players_full.nlargest(3, "avg_rating")
            try:
                prog_df = load_player_progression()
            except Exception:
                prog_df = pd.DataFrame()
            prog_season_col = "season_to" if "season_to" in prog_df.columns else "season" if "season" in prog_df.columns else None
            rating_delta_col = "avg_rating_delta" if "avg_rating_delta" in prog_df.columns else "rating_delta" if "rating_delta" in prog_df.columns else None
            for _, player in top_players.iterrows():
                pid = player.get("player_id")
                trend = ""
                if not prog_df.empty and pid is not None and "player_id" in prog_df.columns and prog_season_col and rating_delta_col:
                    pr = prog_df[(prog_df["player_id"] == pid) & (prog_df[prog_season_col] == season)]
                    if not pr.empty and pr[rating_delta_col].iloc[0] > 0:
                        trend = " ↑ vs last season"
                st.markdown(
                    f"<div style='padding:10px;background:#161B22;border-radius:6px;border:1px solid #30363D;margin:6px 0;'><div style='font-weight:500;color:#F0F6FC;font-size:0.9rem;'>{player['player_name']}</div><div style='font-size:0.75rem;color:#8B949E;'>{player['player_position']} • {int(player['total_minutes'])} mins</div><div style='font-size:0.75rem;color:#C9A840;margin-top:4px;'>Rating: {player.get('avg_rating', 0):.2f}{trend}</div></div>",
                    unsafe_allow_html=True,
                )
                _scouts_url = __import__("os").environ.get("SCOUTS_APP_URL", "")
                if _scouts_url:
                    st.link_button("View in Scouts", _scouts_url.rstrip("/") + (f"?player_id={pid}" if pid is not None else ""), key=f"scout_link_{pid}", use_container_width=True)

# ---------------------------------------------------------------------------
# Tactical Evolution (if historical data available)
# ---------------------------------------------------------------------------
if not team_stats.empty:
    historical_data = team_stats[
        (team_stats["team_name"] == team_name) &
        (team_stats["competition_slug"] == competition)
    ].sort_values("season")

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
# Player Roles Matrix (Enhanced)
# ---------------------------------------------------------------------------
if not player_df.empty:
    team_players_roles = player_df[
        (player_df["team"] == team_name) &
        (player_df["season"] == season) &
        (player_df["competition_slug"] == competition)
    ].sort_values("avg_rating", ascending=False).head(10)

    if not team_players_roles.empty and 'player_name' in team_players_roles.columns:
        st.markdown("---")
        st.markdown("<div class='section-header'>🎭 Player Role Compatibility</div>", unsafe_allow_html=True)

        # Define tactical roles
        roles = [
            'Deep-Lying Playmaker',
            'Box-to-Box Midfielder',
            'Advanced Playmaker',
            'Target Forward',
            'Pressing Forward',
            'Wing-Back',
            'Ball-Winning Midfielder',
            'Complete Defender'
        ]

        render_tactical_roles_matrix(team_players_roles, roles)

# ---------------------------------------------------------------------------
# Build profile Markdown for download
# ---------------------------------------------------------------------------
_profile_md_lines = [
    f"# Tactical Profile: {team_name}",
    f"{COMP_FLAGS.get(competition, '')} {COMP_NAMES.get(competition, competition)} · {season}",
    "",
    "## Summary",
    f"- **Position:** #{team_data.get('position_ordinal', '?')} · **Matches:** {int(team_data.get('matches_total', 0))}",
    f"- **W-D-L:** {wdl.get('W', 0)}-{wdl.get('D', 0)}-{wdl.get('L', 0)} · **Pts:** {points} · **GD:** {gd:+d} · **xGD:** {xgd:+.1f}",
    f"- **Formation (est.):** {st.session_state.get('selected_formation', '4-3-3')}",
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
    ha_dl = _team_home_away_summary(team_name, season, competition)
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
            st.switch_page("pages/1_🏟️_Team_Directory.py")
    with col3:
        if st.button("⚔️ Opponent Prep", use_container_width=True):
            st.session_state["opponent_team"] = team_info
            st.switch_page("pages/3_⚔️_Opponent_Prep.py")
        st.caption("Use this profile as the opponent in Opponent Prep to get matchup analysis and full report.")
    with col4:
        if st.button("🗑️ Clear Selection", use_container_width=True, key="clear_sel_btn"):
            st.session_state["confirm_clear"] = True
            st.rerun()
