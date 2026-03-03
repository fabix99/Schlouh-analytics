"""Scouts Dashboard — Discover Players.

Smart entry point for scouts with trending players, saved filters,
and quick actions to find the right candidates.

Sections: saved filters, filter panel, aggregation, results table, quick actions, footer.
"""

import sys
import pathlib
import json

_project_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.utils.data import (
    load_enriched_season_stats,
    compute_percentiles,
)
try:
    from dashboard.utils.data import compute_percentiles_zscore
except ImportError:
    compute_percentiles_zscore = compute_percentiles  # fallback if not yet deployed
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, POSITION_NAMES, POSITION_ORDER,
    AGE_BANDS, MIN_MINUTES_DEFAULT, RANKING_STATS,
)
from dashboard.utils.filters import (
    apply_filters,
    create_league_selector,
    create_season_selector,
    create_position_selector,
    create_min_minutes_input,
    create_team_selector,
    display_filter_summary,
)
from dashboard.utils.scope import filter_to_default_scope, CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.utils.sidebar import render_sidebar
from dashboard.scouts.layout import load_shortlist_from_file, save_shortlist_to_file
from dashboard.scouts.compare_state import load_scouts_compare_list, save_scouts_compare_list

# Constants for saved filters (under dashboard/scouts/)
SAVED_FILTERS_FILE = pathlib.Path(__file__).resolve().parent.parent / "scouts" / "saved_filters.json"


def load_saved_filters() -> dict:
    """Load saved filters from JSON file. Returns {} on missing or error."""
    if SAVED_FILTERS_FILE.exists():
        try:
            with open(SAVED_FILTERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (IOError, OSError, json.JSONDecodeError):
            return {}
    return {}


def save_filters_to_file(filters_dict: dict) -> None:
    """Save filters to JSON file."""
    with open(SAVED_FILTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(filters_dict, f, indent=2)


def _build_filter_summary(config_dict: dict) -> str:
    """Build the 'Active: …' filter summary string from current filter config (leagues, seasons, positions, min_minutes, age_min/max, teams)."""
    parts = []
    leagues = config_dict.get("leagues") or []
    if leagues:
        parts.append(f"{len(leagues)} league{'s' if len(leagues) != 1 else ''}")
    seasons = config_dict.get("seasons") or []
    if seasons:
        parts.append(" · ".join(seasons))
    positions = config_dict.get("positions") or []
    if positions:
        pos_label = ", ".join(POSITION_NAMES.get(p, p) for p in positions[:3]) + ("…" if len(positions) > 3 else "")
        parts.append(pos_label)
    min_minutes = config_dict.get("min_minutes")
    if min_minutes and min_minutes > 0:
        parts.append(f"Min {min_minutes} min")
    age_min = config_dict.get("age_min")
    age_max = config_dict.get("age_max")
    if age_min is not None or age_max is not None:
        a_min = age_min if age_min is not None else 16
        a_max = age_max if age_max is not None else 45
        parts.append(f"Age {a_min}–{a_max}")
    teams = config_dict.get("teams") or []
    if teams:
        parts.append(f"{len(teams)} team{'s' if len(teams) != 1 else ''}")
    return " · ".join(parts) if parts else "All filters"

# Page config
st.set_page_config(
    page_title="Find Players · Scouts",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar()

# Sync shortlist from file (source of truth)
st.session_state["shortlist"] = load_shortlist_from_file()

# Initialize session state
if "compare_list" not in st.session_state:
    st.session_state.compare_list = load_scouts_compare_list()
if "discover_view" not in st.session_state:
    st.session_state.discover_view = "filtered"  # filtered (panel visible) or table-only
if "discover_stat_filters" not in st.session_state:
    st.session_state["discover_stat_filters"] = []
if "discover_percentile_filters" not in st.session_state:
    st.session_state["discover_percentile_filters"] = []

# Load data (needed to init default filter scope)
with st.spinner("Loading scouting data…"):
    df_all = load_enriched_season_stats()

# Data loader error handling
_critical_cols = ["player_id", "player_name", "player_position", "season"]
if df_all.empty or not all(c in df_all.columns for c in _critical_cols):
    st.error("Data temporarily unavailable. Please try again.")
    if st.button("Retry", type="primary", key="discover_retry"):
        load_enriched_season_stats.clear()
        st.rerun()
    st.stop()

# URL state: override from query params for shareable links (don't pre-set session state so widget defaults apply and no Streamlit warning)
qp = st.query_params
if qp.get("seasons"):
    st.session_state["discover_seasons"] = [s.strip() for s in qp["seasons"].split(",") if s.strip()]
if qp.get("leagues"):
    avail = sorted(df_all["competition_slug"].unique())
    st.session_state["discover_leagues"] = [s.strip() for s in qp["leagues"].split(",") if s.strip() and s.strip() in avail]
if qp.get("positions"):
    st.session_state["discover_positions"] = [s.strip() for s in qp["positions"].split(",") if s.strip()]
if qp.get("min_minutes"):
    try:
        st.session_state["discover_mins"] = int(qp["min_minutes"])
    except ValueError:
        pass

# ---------------------------------------------------------------------------
# Hero — one clear value proposition + primary CTA (Show filters when hidden)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-v2">
        <div class="hero-v2-title">Find Players</div>
        <div class="hero-v2-sub">
            Set your criteria below and browse the table. Use saved filters for quick presets.
        </div>
        <div class="hero-v2-tagline">One place to search, filter, and shortlist candidates.</div>
        <div class="hero-v2-accent" aria-hidden="true"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Saved Filters Section
# ---------------------------------------------------------------------------
saved_filters = load_saved_filters()

if saved_filters:
    st.markdown("<div class='section-header'>💾 Saved Filters</div>", unsafe_allow_html=True)
    
    saved_cols = st.columns(min(len(saved_filters), 4))
    for i, (filter_name, filter_config) in enumerate(saved_filters.items()):
        with saved_cols[i % len(saved_cols)]:
            meta_parts = [
                f"{len(filter_config.get('positions', []))} pos",
                f"{len(filter_config.get('leagues', []))} leagues",
                f"Age {filter_config.get('age_min')}–{filter_config.get('age_max')}" if filter_config.get('age_min') is not None and filter_config.get('age_max') is not None else "All ages",
            ]
            if filter_config.get("stat_filters"):
                n = len(filter_config["stat_filters"])
                meta_parts.append(f"{n} stat" + ("s" if n != 1 else ""))
            meta_str = " · ".join(meta_parts)
            st.markdown(
                f"""
                <div class="saved-filter-card">
                    <div class="saved-filter-name">{filter_name}</div>
                    <div class="saved-filter-meta">{meta_str}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Load", key=f"load_filter_{filter_name}", use_container_width=True):
                    st.session_state[f"filter_config_{filter_name}"] = filter_config
                    st.session_state.discover_view = "filtered"
                    st.rerun()
            with c2:
                if st.button("🗑️", key=f"delete_filter_{filter_name}", use_container_width=True):
                    del saved_filters[filter_name]
                    save_filters_to_file(saved_filters)
                    st.rerun()
    
    st.markdown("---")

# ---------------------------------------------------------------------------
# Filters — 10/10: scoped styles, active summary, percentile = button, polish
# ---------------------------------------------------------------------------
show_filters = True
# Page-scoped CSS so borders and expander style apply (no dependency on global wrapper)
st.markdown("""
<style>
  /* Discover filters: editable inputs clearly bordered */
  [data-testid="stNumberInput"] input {
    border: 1px solid #30363D !important;
    border-radius: 6px !important;
    background: #161B22 !important;
    padding: 0.35rem 0.5rem !important;
  }
  [data-testid="stNumberInput"] input:focus {
    border-color: rgba(201,168,64,0.5) !important;
    box-shadow: 0 0 0 1px rgba(201,168,64,0.2) !important;
  }
  /* Expander = button-like (League, percentile) */
  [data-testid="stExpander"] summary {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
    border-radius: 6px !important;
    min-height: 2.5rem !important;
    padding: 0.4rem 0.6rem !important;
    align-items: center !important;
  }
  [data-testid="stExpander"] summary:hover {
    border-color: rgba(201,168,64,0.35) !important;
  }
  /* Align Scope row: League label reserves same vertical space as Season/Position labels */
  .discover-scope-label {
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: #F0F6FC !important;
    margin-bottom: 0.5rem !important;
    min-height: 1.25rem !important;
    line-height: 1.25rem !important;
  }
  [data-testid="stExpander"] summary,
  [data-testid="stMultiSelect"] > div > div,
  [data-testid="stSelectbox"] > div > div {
    min-height: 2.5rem !important;
  }
</style>
""", unsafe_allow_html=True)
st.markdown("<div class='discover-filter-card'><div class='section-header'>⚙️ Filters</div>", unsafe_allow_html=True)
if st.button("🔄 Reset to current season only", key="discover_reset_scope", help="Set Season to 2025-26 and Leagues to default (leagues + UEFA)."):
    st.session_state["discover_seasons"] = [CURRENT_SEASON] if CURRENT_SEASON in df_all["season"].astype(str).unique() else []
    avail = sorted(df_all["competition_slug"].unique())
    st.session_state["discover_leagues"] = [s for s in DEFAULT_COMPETITION_SLUGS if s in avail]
    st.rerun()

for key in list(st.session_state.keys()):
    if key.startswith("filter_config_"):
        loaded = st.session_state[key]
        if loaded.get("leagues"):
            st.session_state["discover_leagues"] = loaded["leagues"]
        if loaded.get("seasons"):
            st.session_state["discover_seasons"] = loaded["seasons"]
        if loaded.get("positions"):
            st.session_state["discover_positions"] = loaded["positions"]
        if "min_minutes" in loaded:
            st.session_state["discover_mins"] = int(loaded["min_minutes"])
        if loaded.get("age_min") is not None:
            st.session_state["discover_age_min"] = int(loaded["age_min"])
        if loaded.get("age_max") is not None:
            st.session_state["discover_age_max"] = int(loaded["age_max"])
        if loaded.get("teams"):
            st.session_state["discover_teams"] = loaded["teams"]
        st.session_state["discover_stat_filters"] = loaded.get("stat_filters", [])
        pct_loaded = loaded.get("percentile_filters", [])
        st.session_state["discover_percentile_filters"] = pct_loaded
        if pct_loaded:
            st.session_state["discover_show_percentile"] = True
        del st.session_state[key]
        break

st.markdown("<div class='discover-filters'>", unsafe_allow_html=True)
st.markdown("<div class='filter-subsection-label'>Scope</div>", unsafe_allow_html=True)
_r1, _r2, _r3 = st.columns(3)
with _r1:
    st.markdown("<div class='discover-scope-label'>League</div>", unsafe_allow_html=True)
    _avail = sorted(df_all["competition_slug"].unique())
    _default_leagues = [s for s in DEFAULT_COMPETITION_SLUGS if s in _avail]
    _current = st.session_state.get("discover_leagues", _default_leagues)
    _n = len(_current)
    _league_label = f"League ({_n} selected)" if _n else "League"
    with st.expander(_league_label, expanded=False):
        _leagues = create_league_selector(
            df_all,
            key="discover_leagues",
            top5_only_checkbox=True,
            default_scope_slugs=DEFAULT_COMPETITION_SLUGS,
        )
with _r2:
    _seasons = create_season_selector(
        df_all,
        leagues=_leagues if _leagues else None,
        key="discover_seasons",
        default_seasons=[CURRENT_SEASON],
    )
with _r3:
    _positions = create_position_selector(df_all, key="discover_positions")
_ref1, _ref2, _ref3, _ref4 = st.columns(4)
with _ref1:
    _min_minutes = create_min_minutes_input(key="discover_mins", default=MIN_MINUTES_DEFAULT)
with _ref2:
    _age_min = st.number_input("Age min", min_value=15, max_value=50, value=16, step=1, key="discover_age_min", help="Min age")
with _ref3:
    _age_max = st.number_input("Age max", min_value=15, max_value=50, value=45, step=1, key="discover_age_max", help="Max age")
with _ref4:
    _teams = create_team_selector(df_all, key="discover_teams")
st.markdown("</div>", unsafe_allow_html=True)
config = {
    "leagues": _leagues,
    "seasons": _seasons,
    "positions": _positions,
    "min_minutes": _min_minutes,
    "age_min": _age_min,
    "age_max": _age_max,
    "teams": _teams,
    "min_rating": 0.0,
}

# Active filter summary (at-a-glance feedback)
_summary_str = _build_filter_summary(config)
st.markdown(
    f"<p class='filter-active-summary'><span class='filter-active-label'>Active:</span> {_summary_str}</p>",
    unsafe_allow_html=True,
)

st.session_state.setdefault("discover_show_percentile", False)

st.markdown("<div class='filter-subsection-label'>By statistics</div>", unsafe_allow_html=True)
st.caption("Min/max for raw stats (per 90 or %). Applies to the aggregated table.")

# Stat options: RANKING_STATS plus extras that exist in aggregated table
_extra_stat_labels = {
    "touches_per90": "Touches / 90",
    "onTargetScoringAttempt_per90": "Shots on target / 90",
    "blockedScoringAttempt_per90": "Blocked shots / 90",
    "totalClearance_per90": "Clearances / 90",
    "goodHighClaim_per90": "High claims / 90",
    "savedShotsFromInsideTheBox_per90": "Saves in box / 90",
    "duel_win_rate": "Duel win %",
    "aerial_win_rate": "Aerial win %",
    "tackle_success_rate": "Tackle success %",
}
stat_options = list(RANKING_STATS.items()) + [(k, v) for k, v in _extra_stat_labels.items() if k not in RANKING_STATS]
stat_keys = [k for k, _ in stat_options]

def _stat_label(k):
    return RANKING_STATS.get(k) or _extra_stat_labels.get(k) or k

MAX_RAW_STAT_FILTERS = 5
stat_filters = st.session_state.get("discover_stat_filters", [])
to_remove = None
for i, rule in enumerate(stat_filters):
    r1, r2, r3, r4, r5, r6 = st.columns([2, 0.5, 1, 0.5, 1, 0.4])
    with r1:
        default_idx = stat_keys.index(rule["stat"]) if rule.get("stat") in stat_keys else 0
        st.selectbox(
            "Stat",
            options=stat_keys,
            format_func=_stat_label,
            key=f"stat_filter_stat_{i}",
            label_visibility="collapsed",
            index=default_idx,
        )
    with r2:
        use_min = st.checkbox("Min", value=rule.get("min") is not None, key=f"stat_filter_use_min_{i}", label_visibility="collapsed")
    with r3:
        min_val = st.number_input("Min val", min_value=0.0, value=float(rule["min"]) if rule.get("min") is not None else 0.0, step=0.05, key=f"stat_filter_min_{i}", label_visibility="collapsed", disabled=not use_min)
    with r4:
        use_max = st.checkbox("Max", value=rule.get("max") is not None, key=f"stat_filter_use_max_{i}", label_visibility="collapsed")
    with r5:
        max_val = st.number_input("Max val", min_value=0.0, value=float(rule["max"]) if rule.get("max") is not None else 10.0, step=0.05, key=f"stat_filter_max_{i}", label_visibility="collapsed", disabled=not use_max)
    with r6:
        if st.button("🗑️", key=f"stat_filter_remove_{i}", help="Remove"):
            to_remove = i
if to_remove is not None:
    stat_filters.pop(to_remove)
    st.session_state["discover_stat_filters"] = stat_filters
    st.rerun()

# Rebuild stat_filters from current widget values
_rebuilt = []
for i in range(len(stat_filters)):
    stat_key = st.session_state.get(f"stat_filter_stat_{i}")
    use_min = st.session_state.get(f"stat_filter_use_min_{i}", False)
    use_max = st.session_state.get(f"stat_filter_use_max_{i}", False)
    min_val = st.session_state.get(f"stat_filter_min_{i}") if use_min else None
    max_val = st.session_state.get(f"stat_filter_max_{i}") if use_max else None
    if stat_key:
        _rebuilt.append({"stat": stat_key, "min": min_val, "max": max_val})
st.session_state["discover_stat_filters"] = _rebuilt

# One row: Add stat filter + Percentile toggle + Clear (same button style)
_btn1, _btn2, _btn3 = st.columns([1, 1, 0.6])
with _btn1:
    if len(stat_filters) < MAX_RAW_STAT_FILTERS and st.button("➕ Add stat filter", key="add_stat_filter", use_container_width=True):
        st.session_state["discover_stat_filters"] = _rebuilt + [{"stat": "expectedGoals_per90", "min": None, "max": None}]
        st.rerun()
with _btn2:
    _pct_label = "▼ Hide percentile filters" if st.session_state["discover_show_percentile"] else "➕ Also filter by percentile (optional)"
    if st.button(_pct_label, key="toggle_percentile", use_container_width=True):
        st.session_state["discover_show_percentile"] = not st.session_state["discover_show_percentile"]
        st.rerun()
with _btn3:
    if (stat_filters or st.session_state["discover_percentile_filters"]) and st.button("Clear all", key="clear_stat_filters", use_container_width=True):
        st.session_state["discover_stat_filters"] = []
        st.session_state["discover_percentile_filters"] = []
        st.rerun()

# Percentile filter block (shown when toggled on, same visual weight as stat filters)
pct_stat_options = [
    "avg_rating", "goals_per90", "expectedGoals_per90", "expectedAssists_per90",
    "keyPass_per90", "totalTackle_per90", "duelWon_per90", "totalShots_per90",
    "pass_accuracy_pct", "duel_win_rate",
]
if st.session_state["discover_show_percentile"]:
    st.caption("Percentiles are vs position in the current filtered pool.")
    pct_filters = st.session_state["discover_percentile_filters"]
    pct_to_remove = None
    for i, rule in enumerate(pct_filters):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 0.4])
        with c1:
            _pct_idx = pct_stat_options.index(rule["stat"]) if rule.get("stat") in pct_stat_options else 0
            st.selectbox("Stat", options=pct_stat_options, key=f"pct_filter_stat_{i}", label_visibility="collapsed", index=_pct_idx)
        with c2:
            st.number_input("Min %ile", 0, 100, value=int(rule["min_pct"]) if rule.get("min_pct") is not None else 0, key=f"pct_filter_min_{i}", label_visibility="collapsed")
        with c3:
            st.number_input("Max %ile", 0, 100, value=int(rule["max_pct"]) if rule.get("max_pct") is not None else 100, key=f"pct_filter_max_{i}", label_visibility="collapsed")
        with c4:
            if st.button("🗑️", key=f"pct_filter_remove_{i}"):
                pct_to_remove = i
    if pct_to_remove is not None:
        pct_filters.pop(pct_to_remove)
        st.session_state["discover_percentile_filters"] = pct_filters
        st.rerun()
    _pct_rebuilt = []
    for i in range(len(pct_filters)):
        s = st.session_state.get(f"pct_filter_stat_{i}")
        mi = st.session_state.get(f"pct_filter_min_{i}")
        ma = st.session_state.get(f"pct_filter_max_{i}")
        if s is not None:
            _pct_rebuilt.append({"stat": s, "min_pct": mi, "max_pct": ma})
    st.session_state["discover_percentile_filters"] = _pct_rebuilt
    if st.button("➕ Add percentile filter", key="add_pct_filter"):
        st.session_state["discover_percentile_filters"] = _pct_rebuilt + [{"stat": "avg_rating", "min_pct": 0, "max_pct": 100}]
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)  # close discover-filter-card

# Merge stat filters into config for cache key
config = dict(config)
config["stat_filters"] = st.session_state["discover_stat_filters"]
config["percentile_filters"] = st.session_state["discover_percentile_filters"]

# Cache key uses only panel filters (stat filters applied post-aggregation)
_panel_only = {k: v for k, v in config.items() if k not in ("stat_filters", "percentile_filters")}
_config_key = json.dumps(_panel_only, sort_keys=True)

# Per90 and ratio columns from 03_player_season_stats / enriched (weighted avg by total_minutes)
AGG_PER90_AND_RATIOS = [
    "expectedGoals_per90", "expectedAssists_per90", "keyPass_per90", "totalTackle_per90",
    "duelWon_per90", "interceptionWon_per90", "ballRecovery_per90", "totalShots_per90",
    "onTargetScoringAttempt_per90", "touches_per90", "aerialWon_per90", "totalPass_per90",
    "pass_accuracy", "pass_accuracy_pct", "duel_win_rate", "aerial_win_rate", "tackle_success_rate",
    "bigChanceCreated_per90", "blockedScoringAttempt_per90", "totalClearance_per90",
    "saves_per90", "goodHighClaim_per90", "savedShotsFromInsideTheBox_per90",
]

def aggregate_one_row_per_player(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (player_id, season): primary row from max-minutes, sums, weighted avgs for rating and all per90/ratios."""
    if df.empty or "player_id" not in df.columns:
        return df
    group_cols = ["player_id", "season"]
    if "season" not in df.columns:
        group_cols = ["player_id"]
    idx_primary = df.groupby(group_cols)["total_minutes"].idxmax()
    primary_cols = ["player_id", "season", "player_name", "player_position", "team", "league_name", "age_at_season_start"]
    primary = df.loc[idx_primary, [c for c in primary_cols if c in df.columns]].set_index(group_cols)
    sum_cols = [c for c in ["appearances", "total_minutes", "goals", "assists"] if c in df.columns]
    sums = df.groupby(group_cols)[sum_cols].sum()
    out = primary.join(sums, how="left")
    # Weighted average rating
    if "avg_rating" in df.columns and "total_minutes" in df.columns:
        r = df.assign(_w=df["avg_rating"] * df["total_minutes"]).groupby(group_cols).agg(_sum_w=("_w", "sum"), _mins=("total_minutes", "sum"))
        out = out.join((r["_sum_w"] / r["_mins"].replace(0, np.nan)).to_frame(name="avg_rating"), how="left")
    # Goals per 90 from totals
    if "total_minutes" in out.columns and "goals" in out.columns:
        mins = out["total_minutes"].astype(float).replace(0, np.nan)
        out["goals_per90"] = 90 * out["goals"] / mins
    # Weighted average for all per90 and ratio columns that exist
    for col in AGG_PER90_AND_RATIOS:
        if col not in df.columns or "total_minutes" not in df.columns:
            continue
        tmp = df.assign(_w=df[col].fillna(0) * df["total_minutes"]).groupby(group_cols).agg(_wx=("_w", "sum"), _mins=("total_minutes", "sum"))
        out[col] = tmp["_wx"] / tmp["_mins"].replace(0, np.nan)
    out = out.reset_index()
    return out


@st.cache_data(ttl=3600)
def _cached_filter_aggregate_percentiles(_df_all: pd.DataFrame, config_key: str) -> tuple:
    """Return (df_filtered, df_agg) keyed by config_key to avoid recomputing percentiles every run."""
    if config_key == "__default__":
        df_filtered = filter_to_default_scope(_df_all)
    else:
        config = json.loads(config_key)
        df_filtered = apply_filters(_df_all, config)
    df_agg = aggregate_one_row_per_player(df_filtered)
    if not df_agg.empty and "player_position" in df_agg.columns:
        pct_group = ["season", "player_position"] if "season" in df_agg.columns else ["player_position"]
        pct_stats = [
            c for c in [
                "avg_rating", "goals_per90", "expectedGoals_per90", "expectedAssists_per90",
                "keyPass_per90", "totalTackle_per90", "duelWon_per90", "totalShots_per90",
                "pass_accuracy_pct", "duel_win_rate",
            ]
            if c in df_agg.columns
        ]
        if pct_stats:
            df_agg = compute_percentiles_zscore(df_agg, pct_group, pct_stats)
    if not df_agg.empty and "avg_rating" in df_agg.columns:
        df_agg = df_agg.sort_values("avg_rating", ascending=False, na_position="last").reset_index(drop=True)
    return (df_filtered, df_agg)


(df_filtered, df_agg) = _cached_filter_aggregate_percentiles(df_all, _config_key)

# Apply stat filters (raw values, then percentiles) on aggregated table
def apply_stat_filters(df: pd.DataFrame, raw_filters: list, pct_filters: list) -> pd.DataFrame:
    """Apply raw and percentile stat filters to aggregated dataframe. Handles missing keys in rules via .get()."""
    out = df
    for rule in raw_filters:
        stat = rule.get("stat")
        if not stat or stat not in out.columns:
            continue
        min_val, max_val = rule.get("min"), rule.get("max")
        if min_val is not None:
            out = out[out[stat].fillna(-np.inf) >= min_val]
        if max_val is not None:
            out = out[out[stat].fillna(np.inf) <= max_val]
    for rule in pct_filters:
        stat = rule.get("stat")
        pct_col = f"{stat}_pct" if stat else None
        if not pct_col or pct_col not in out.columns:
            continue
        min_pct, max_pct = rule.get("min_pct"), rule.get("max_pct")
        if min_pct is not None and min_pct > 0:
            out = out[out[pct_col].fillna(-1) >= min_pct]
        if max_pct is not None and max_pct < 100:
            out = out[out[pct_col].fillna(101) <= max_pct]
    return out

stat_filters_applied = st.session_state.get("discover_stat_filters", []) or []
percentile_filters_applied = st.session_state.get("discover_percentile_filters", []) or []
if stat_filters_applied or percentile_filters_applied:
    df_agg = apply_stat_filters(df_agg, stat_filters_applied, percentile_filters_applied)

if show_filters:
    display_filter_summary(df_filtered, df_all)
    # Show active stat filters summary
    if stat_filters_applied or percentile_filters_applied:
        parts = []
        for r in stat_filters_applied:
            lbl = RANKING_STATS.get(r["stat"], r["stat"])
            if r.get("min") is not None and r.get("max") is not None:
                parts.append(f"{lbl} {r['min']}–{r['max']}")
            elif r.get("min") is not None:
                parts.append(f"{lbl} ≥ {r['min']}")
            elif r.get("max") is not None:
                parts.append(f"{lbl} ≤ {r['max']}")
        for r in percentile_filters_applied:
            pct_col = f"{r.get('stat', '')}_pct"
            if r.get("min_pct") is not None:
                parts.append(f"{r['stat']} %ile ≥ {r['min_pct']}")
            if r.get("max_pct") is not None:
                parts.append(f"{r['stat']} %ile ≤ {r['max_pct']}")
        st.markdown(
            f"<p class='filter-summary-line'>Stat filters: <b>{' · '.join(parts)}</b></p>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Empty state: no results — clear message + single action
# ---------------------------------------------------------------------------
if df_agg.empty:
    st.info(
        "No players match the current filters. Loosen criteria or use **Reset to current season only** to see results."
    )
    if st.button("Reset to current season only", key="discover_empty_reset", type="primary"):
        st.session_state["discover_seasons"] = [CURRENT_SEASON] if CURRENT_SEASON in df_all["season"].astype(str).unique() else []
        avail = sorted(df_all["competition_slug"].unique())
        st.session_state["discover_leagues"] = [s for s in DEFAULT_COMPETITION_SLUGS if s in avail]
        st.session_state["discover_stat_filters"] = []
        st.session_state["discover_percentile_filters"] = []
        st.session_state.discover_view = "filtered"
        st.rerun()
    st.stop()

if "discover_columns_template" not in st.session_state:
    st.session_state.discover_columns_template = "Default"

# Column templates: built from actual 03/enriched schema (per90, ratios, percentiles)
COLUMN_TEMPLATES = {
    "Default": [
        "player_name", "player_position", "team", "league_name", "season",
        "age_at_season_start", "appearances", "total_minutes", "avg_rating", "avg_rating_pct",
        "goals", "assists", "goals_per90", "expectedGoals_per90", "expectedAssists_per90",
    ],
    "Forwards": [
        "player_name", "player_position", "team", "league_name", "age_at_season_start",
        "appearances", "total_minutes", "avg_rating", "avg_rating_pct",
        "goals", "goals_per90", "expectedGoals_per90", "expectedGoals_per90_pct",
        "totalShots_per90", "onTargetScoringAttempt_per90", "assists", "expectedAssists_per90",
    ],
    "Midfield": [
        "player_name", "player_position", "team", "league_name", "age_at_season_start",
        "appearances", "total_minutes", "avg_rating", "avg_rating_pct",
        "expectedAssists_per90", "expectedAssists_per90_pct", "keyPass_per90", "keyPass_per90_pct",
        "pass_accuracy_pct", "goals_per90", "expectedGoals_per90",
    ],
    "Defence": [
        "player_name", "player_position", "team", "league_name", "age_at_season_start",
        "appearances", "total_minutes", "avg_rating", "avg_rating_pct",
        "totalTackle_per90", "totalTackle_per90_pct", "duelWon_per90", "duel_win_rate",
        "interceptionWon_per90", "ballRecovery_per90", "blockedScoringAttempt_per90", "totalClearance_per90",
    ],
    "Goalkeepers": [
        "player_name", "player_position", "team", "league_name", "age_at_season_start",
        "appearances", "total_minutes", "avg_rating", "avg_rating_pct",
        "saves_per90", "savedShotsFromInsideTheBox_per90", "goodHighClaim_per90",
    ],
}
template = st.session_state.discover_columns_template
display_cols = [c for c in COLUMN_TEMPLATES.get(template, COLUMN_TEMPLATES["Default"]) if c in df_agg.columns]
df_display = df_agg[display_cols].copy()

# Rename for display (internal col name -> table header)
rename_map = {
    "player_name": "Player",
    "player_position": "Pos",
    "team": "Team",
    "league_name": "League",
    "season": "Season",
    "age_at_season_start": "Age",
    "appearances": "Apps",
    "total_minutes": "Mins",
    "avg_rating": "Rating",
    "avg_rating_pct": "Rating %ile",
    "goals": "Goals",
    "assists": "Assists",
    "goals_per90": "G/90",
    "expectedGoals_per90": "xG/90",
    "expectedGoals_per90_pct": "xG/90 %ile",
    "expectedAssists_per90": "xA/90",
    "expectedAssists_per90_pct": "xA/90 %ile",
    "keyPass_per90": "KP/90",
    "keyPass_per90_pct": "KP/90 %ile",
    "totalTackle_per90": "Tck/90",
    "totalTackle_per90_pct": "Tck/90 %ile",
    "duelWon_per90": "Duels/90",
    "duel_win_rate": "Duel %",
    "interceptionWon_per90": "Int/90",
    "ballRecovery_per90": "Rec/90",
    "totalShots_per90": "Sh/90",
    "onTargetScoringAttempt_per90": "SoT/90",
    "pass_accuracy_pct": "Pass %",
    "blockedScoringAttempt_per90": "Blk/90",
    "totalClearance_per90": "Clr/90",
    "saves_per90": "Saves/90",
    "savedShotsFromInsideTheBox_per90": "SavesBox/90",
    "goodHighClaim_per90": "Claims/90",
    "bigChanceCreated_per90": "BCC/90",
}
df_display = df_display.rename(columns={k: v for k, v in rename_map.items() if k in df_display.columns})

# Numeric formatting
for col in ["Rating", "G/90", "xG/90", "xA/90", "KP/90", "Tck/90", "Duels/90", "Int/90", "Rec/90", "Sh/90", "SoT/90", "Blk/90", "Clr/90", "Saves/90", "SavesBox/90", "Claims/90", "BCC/90", "Duel %", "Pass %"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].round(2)
for col in ["Rating %ile", "xG/90 %ile", "xA/90 %ile", "KP/90 %ile", "Tck/90 %ile"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].round(0).fillna(0)
for col in ["Apps", "Mins", "Goals", "Assists"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].fillna(0).astype(int)
if "Age" in df_display.columns:
    df_display["Age"] = df_display["Age"].fillna(0).round(0).astype(int)

# Position names
if "Pos" in df_display.columns:
    df_display["Pos"] = df_display["Pos"].map(POSITION_NAMES).fillna(df_display["Pos"])

# ---------------------------------------------------------------------------
# Results — column template, sort (full data), and data table
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>📋 Results</div>", unsafe_allow_html=True)
st.caption("Percentile columns (e.g. Rating %ile) are **z-score based** (vs season × position): distance from average maps to percentile, so top players spread clearly (e.g. 99 vs 96 instead of 100 vs 99).")
_template_list = list(COLUMN_TEMPLATES.keys())
col_template = st.selectbox(
    "Columns",
    options=_template_list,
    key="discover_columns_select",
    index=min(_template_list.index(st.session_state.discover_columns_template), len(_template_list) - 1) if st.session_state.discover_columns_template in _template_list else 0,
)
if col_template != st.session_state.discover_columns_template:
    st.session_state.discover_columns_template = col_template
    st.rerun()

# Sort by: apply to full dataset so pagination shows globally sorted rows
sortable_cols = list(df_display.columns)
if "discover_sort_column" not in st.session_state:
    st.session_state["discover_sort_column"] = "Rating" if "Rating" in df_display.columns else (sortable_cols[0] if sortable_cols else None)
if "discover_sort_ascending" not in st.session_state:
    st.session_state["discover_sort_ascending"] = False
_sort_col = st.session_state["discover_sort_column"]
if _sort_col not in df_display.columns:
    _sort_col = "Rating" if "Rating" in df_display.columns else sortable_cols[0]
    st.session_state["discover_sort_column"] = _sort_col

_sort_c1, _sort_c2 = st.columns([1, 3])
with _sort_c1:
    new_sort_col = st.selectbox(
        "Sort by (full data)",
        options=sortable_cols,
        key="discover_sort_select",
        index=sortable_cols.index(_sort_col) if _sort_col in sortable_cols else 0,
    )
with _sort_c2:
    new_sort_asc = st.checkbox("Ascending", key="discover_sort_asc", value=st.session_state["discover_sort_ascending"])
if new_sort_col != st.session_state["discover_sort_column"] or new_sort_asc != st.session_state["discover_sort_ascending"]:
    st.session_state["discover_sort_column"] = new_sort_col
    st.session_state["discover_sort_ascending"] = new_sort_asc
    st.session_state["discover_table_page"] = 0
    st.rerun()

# Sort full data then paginate (so "order" is on whole data, not current page)
try:
    df_sorted = df_display.sort_values(
        by=st.session_state["discover_sort_column"],
        ascending=st.session_state["discover_sort_ascending"],
        na_position="last",
    ).reset_index(drop=True)
except Exception:
    df_sorted = df_display

# Pagination: one page = one screenful (no scrolling inside the table)
DISCOVER_PAGE_SIZE = 20  # rows per page so table fits without vertical scroll
ROW_HEIGHT_PX = 36
TABLE_HEADER_PX = 44
if "discover_table_page" not in st.session_state:
    st.session_state["discover_table_page"] = 0
total_rows = len(df_sorted)
total_pages = max(1, (total_rows + DISCOVER_PAGE_SIZE - 1) // DISCOVER_PAGE_SIZE)
current_page = max(0, min(st.session_state["discover_table_page"], total_pages - 1))
st.session_state["discover_table_page"] = current_page
start_idx = current_page * DISCOVER_PAGE_SIZE
end_idx = min(start_idx + DISCOVER_PAGE_SIZE, total_rows)
df_page = df_sorted.iloc[start_idx:end_idx].reset_index(drop=True)
table_height = TABLE_HEADER_PX + min(len(df_page), DISCOVER_PAGE_SIZE) * ROW_HEIGHT_PX
st.dataframe(df_page, use_container_width=True, height=table_height, hide_index=True)
if total_rows > DISCOVER_PAGE_SIZE:
    d1, d2, d3 = st.columns([1, 2, 1])
    with d1:
        if st.button("← Previous", key="discover_prev", disabled=(current_page == 0)):
            st.session_state["discover_table_page"] = current_page - 1
            st.rerun()
    with d2:
        st.caption(f"Showing {start_idx + 1}–{end_idx} of {total_rows} · Page {current_page + 1} of {total_pages}")
    with d3:
        if st.button("Next →", key="discover_next", disabled=(current_page >= total_pages - 1)):
            st.session_state["discover_table_page"] = current_page + 1
            st.rerun()

# Export CSV and share link (export uses same sort order as table)
ex1, ex2 = st.columns(2)
with ex1:
    csv_full = df_sorted.to_csv(index=False)
    st.download_button(
        "⬇️ Export full filtered table (CSV)",
        data=csv_full,
        file_name=f"discover_players_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="discover_export_csv",
    )
with ex2:
    share_params = []
    if st.session_state.get("discover_seasons"):
        share_params.append("seasons=" + ",".join(st.session_state["discover_seasons"]))
    if st.session_state.get("discover_leagues"):
        share_params.append("leagues=" + ",".join(st.session_state["discover_leagues"]))
    if st.session_state.get("discover_positions"):
        share_params.append("positions=" + ",".join(st.session_state["discover_positions"]))
    if st.session_state.get("discover_mins") not in (None, 1000):
        share_params.append("min_minutes=" + str(st.session_state["discover_mins"]))
    share_query = "?" + "&".join(share_params) if share_params else ""
    st.text_input("Share this search (copy query params)", value=share_query, key="discover_share_url", label_visibility="collapsed")

# Actions for filtered results
st.markdown("<div class='section-header'>🎯 Quick Actions on Results</div>", unsafe_allow_html=True)

unique_players = df_agg[["player_id", "player_name"]].drop_duplicates("player_id").sort_values("player_name")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    selected_for_action = st.selectbox(
        "Select player:",
        options=unique_players["player_id"].tolist(),
        format_func=lambda x: unique_players.set_index("player_id").loc[x, "player_name"],
        key="action_player_select"
    )
with col2:
    if st.button("View profile", key="discover_view_profile", type="primary", use_container_width=True):
        st.session_state["profile_player_id"] = selected_for_action
        st.switch_page("pages/2_📋_Profile.py")
with col3:
    if st.button("Add to Shortlist", use_container_width=True):
        player_name = unique_players.set_index("player_id").loc[selected_for_action, "player_name"]
        if selected_for_action not in [p["id"] for p in st.session_state.shortlist]:
            st.session_state.shortlist.append({
                "id": selected_for_action,
                "name": player_name,
                "status": "Watching",
                "added_date": pd.Timestamp.now().strftime("%Y-%m-%d")
            })
            save_shortlist_to_file(st.session_state.shortlist)
            st.toast(f"Added {player_name} to shortlist!")
        else:
            st.toast(f"{player_name} already in shortlist")

# Bulk add to compare
st.markdown("---")
bulk_players = st.multiselect(
    "Select multiple players to compare:",
    options=unique_players["player_id"].tolist(),
    format_func=lambda x: unique_players.set_index("player_id").loc[x, "player_name"],
    key="bulk_compare_select"
)
if bulk_players:
    if st.button("Add Selected to Compare", key="discover_bulk_compare"):
        if "compare_list" not in st.session_state:
            st.session_state.compare_list = load_scouts_compare_list()
        added = 0
        for pid in bulk_players:
            if pid not in st.session_state.compare_list:
                st.session_state.compare_list.append(pid)
                added += 1
        save_scouts_compare_list(st.session_state.compare_list)
        st.toast(f"Added {added} players to compare list")

# ---------------------------------------------------------------------------
# Footer stats (current view — aggregated table)
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<div class='section-header'>📊 Current view</div>",
    unsafe_allow_html=True,
)
st.caption("One row per player per season. Default scope or your filter selection.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Unique players", f"{df_agg['player_id'].nunique():,}")
c2.metric("Player–seasons", f"{len(df_agg):,}")
c3.metric("Leagues", df_agg["league_name"].nunique() if "league_name" in df_agg.columns else 0)
c4.metric("Appearances", f"{int(df_agg['appearances'].sum()):,}" if "appearances" in df_agg.columns else "—")

st.markdown("<div class='kpi-accent'></div>", unsafe_allow_html=True)
st.markdown(
    '<p class="data-attribution">Data sourced from SofaScore. Default: current season, leagues + UEFA. Use Find players filters to change scope.</p>',
    unsafe_allow_html=True,
)

# Quick league breakdown (by primary league in aggregated table)
st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
if "league_name" in df_agg.columns:
    league_counts = df_agg.groupby("league_name")["player_id"].nunique().sort_values(ascending=False)
    league_cols = st.columns(min(len(league_counts), 4))
    for i, (league, count) in enumerate(league_counts.head(4).items()):
        with league_cols[i]:
            st.markdown(
                f"""
                <div class="league-breakdown-card">
                    <div class="league-breakdown-label">{league}</div>
                    <div class="league-breakdown-value">{count:,} players</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
