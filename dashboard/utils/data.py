"""Cached data loaders and aggregation helpers."""

from __future__ import annotations

import pathlib
import numpy as np
import pandas as pd
import streamlit as st

# Resolve project root (two levels up from this file: dashboard/utils/ → project root)
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Global formatting helpers for consistent data display
# ---------------------------------------------------------------------------

def format_metric(value, decimals: int = 2, missing: str = "—", suffix: str = "") -> str:
    """Format a metric value consistently across all dashboards.

    Args:
        value: The value to format (number or None/NaN)
        decimals: Number of decimal places (default: 2)
        missing: String to display for missing values (default: "—")
        suffix: Optional suffix (e.g., "%", "th") to append

    Returns:
        Formatted string representation of the value

    Examples:
        >>> format_metric(7.456, decimals=2)
        '7.46'
        >>> format_metric(None, decimals=1)
        '—'
        >>> format_metric(85.5, decimals=0, suffix="th")
        '86th'
        >>> format_metric(1234.5, decimals=1)  # Large numbers get commas
        '1,234.5'
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return missing
    try:
        if decimals == 0:
            formatted = f"{int(value):,}"
        else:
            formatted = f"{value:,.{decimals}f}"
        return f"{formatted}{suffix}"
    except (TypeError, ValueError):
        return missing


def format_rating(value) -> str:
    """Format player rating with 2 decimal places."""
    return format_metric(value, decimals=2)


def format_per90(value) -> str:
    """Format per-90 statistics with 2 decimal places."""
    return format_metric(value, decimals=2)


def format_percentage(value, decimals: int = 1) -> str:
    """Format percentage values."""
    return format_metric(value, decimals=decimals, suffix="%")


def format_percentile(value) -> str:
    """Format percentile rank with 'th' suffix."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    try:
        v = int(round(value))
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(v % 10, "th")
        if 11 <= v % 100 <= 13:  # Special case for 11th, 12th, 13th
            suffix = "th"
        return f"{v}{suffix}"
    except (TypeError, ValueError):
        return "—"


def format_minutes(value) -> str:
    """Format minutes with comma separator."""
    return format_metric(value, decimals=0)


# ---------------------------------------------------------------------------
# Raw loaders (all cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def load_player_season_stats() -> pd.DataFrame:
    """Primary scouting DataFrame: one row per player × season × competition."""
    try:
        df = pd.read_parquet(_PROJECT_ROOT / "data/processed/03_player_season_stats.parquet")
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=3600)
def load_team_lookup() -> pd.DataFrame:
    """Lightweight lookup: player_id × season × competition_slug → team."""
    try:
        df = pd.read_parquet(
            _PROJECT_ROOT / "data/derived/player_appearances.parquet",
            columns=["player_id", "season", "competition_slug", "team"],
        )
        lookup = (
            df.groupby(["player_id", "season", "competition_slug"])["team"]
            .agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "Unknown")
            .reset_index()
        )
        return lookup
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=3600)
def load_extraction_progress() -> pd.DataFrame:
    try:
        return pd.read_csv(_PROJECT_ROOT / "data/index/extraction_progress.csv")
    except Exception:
        # Return empty DataFrame with expected columns so callers (app.py, get_available_comp_seasons)
        # can safely use ep["extracted"] and ep[ep["extracted"] > 0] without KeyError.
        return pd.DataFrame(columns=["competition_slug", "season", "extracted"])


@st.cache_data(show_spinner=False, ttl=3600)
def load_players_index() -> pd.DataFrame:
    return pd.read_csv(_PROJECT_ROOT / "data/index/players.csv")


@st.cache_data(show_spinner=False, ttl=3600)
def load_scouting_profiles() -> pd.DataFrame:
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/08_player_scouting_profiles.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_rolling_form() -> pd.DataFrame:
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/07_player_rolling_form.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_incidents() -> pd.DataFrame:
    return pd.read_parquet(
        _PROJECT_ROOT / "data/derived/player_incidents.parquet",
        columns=["player_id", "player_name", "incidentType", "incidentClass",
                 "time", "season", "competition_slug", "match_date_utc"],
    )


@st.cache_data(show_spinner=False, ttl=3600)
def load_career_stats() -> pd.DataFrame:
    """Per-player career aggregates from 04_player_career_stats.parquet."""
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/04_player_career_stats.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_player_progression() -> pd.DataFrame:
    """Season-on-season progression deltas from 09_player_progression.parquet."""
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/09_player_progression.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_opponent_context_summary() -> pd.DataFrame:
    """Player performance vs opponent strength summary from 11_player_opponent_context_summary.parquet."""
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/11_player_opponent_context_summary.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_player_consistency() -> pd.DataFrame:
    """Player rating consistency metrics from 10_player_consistency.parquet."""
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/10_player_consistency.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_team_season_stats() -> pd.DataFrame:
    """Team season aggregates from 01_team_season_stats.parquet."""
    try:
        return pd.read_parquet(_PROJECT_ROOT / "data/processed/01_team_season_stats.parquet")
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=3600)
def load_match_summary() -> pd.DataFrame:
    """Match-level summary from 02_match_summary.parquet."""
    try:
        return pd.read_parquet(_PROJECT_ROOT / "data/processed/02_match_summary.parquet")
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=3600)
def load_tactical_profiles() -> pd.DataFrame:
    """Team tactical profiles from 15_team_tactical_profiles.parquet. Returns empty DataFrame if missing."""
    try:
        path = _PROJECT_ROOT / "data/processed/15_team_tactical_profiles.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


# Aliases used by scouts/tactics/review dashboards
load_player_rolling_form = load_rolling_form
load_team_tactical_profiles = load_tactical_profiles
load_player_scouting_profiles = load_scouting_profiles


@st.cache_data(show_spinner=False, ttl=3600)
def load_managers() -> pd.DataFrame:
    """Match-level manager records from 14_managers.parquet."""
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/14_managers.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_manager_career_stats() -> pd.DataFrame:
    """Manager career stats from manager_career_stats.parquet."""
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/manager_career_stats.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_player_appearances_slim() -> pd.DataFrame:
    """Slim version of appearances for match-log displays."""
    # Read available columns (be tolerant of missing optional cols)
    desired_cols = [
        "player_id", "player_name", "season", "competition_slug", "match_date_utc",
        "round", "home_team_name", "away_team_name", "team", "side", "position",
        "stat_minutesPlayed", "stat_rating", "stat_goals", "stat_goalAssist",
        "stat_expectedGoals", "stat_expectedAssists", "stat_keyPass",
        "stat_totalTackle", "stat_interceptionWon", "stat_totalShots",
        "stat_onTargetScoringAttempt", "stat_touches", "stat_duelWon", "stat_duelLost",
    ]
    import pyarrow.parquet as pq
    pf = pq.read_table(_PROJECT_ROOT / "data/derived/player_appearances.parquet")
    available = [c for c in desired_cols if c in pf.schema.names]
    return pf.select(available).to_pandas()


@st.cache_data(show_spinner=False, ttl=3600)
def load_player_appearances_for_teams() -> pd.DataFrame:
    """Appearances subset for team formation analysis."""
    desired_cols = [
        "player_id", "player_name", "position", "team", "match_id",
        "season", "competition_slug", "match_date_utc",
        "stat_minutesPlayed", "stat_rating",
    ]
    import pyarrow.parquet as pq
    pf = pq.read_table(_PROJECT_ROOT / "data/derived/player_appearances.parquet")
    available = [c for c in desired_cols if c in pf.schema.names]
    return pf.select(available).to_pandas()


# ---------------------------------------------------------------------------
# Enriched scouting DataFrame (primary dataset with team info)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def load_enriched_season_stats() -> pd.DataFrame:
    """Season stats joined with team lookup and league display names."""
    from dashboard.utils.constants import COMP_NAMES, POSITION_NAMES

    try:
        stats = load_player_season_stats()
        teams = load_team_lookup()
        if stats.empty:
            return pd.DataFrame()
        df = stats.merge(teams, on=["player_id", "season", "competition_slug"], how="left")

        # Human-readable league name
        df["league_name"] = df["competition_slug"].map(COMP_NAMES).fillna(df["competition_slug"])

        # Human-readable position
        df["position_name"] = df["player_position"].map(POSITION_NAMES).fillna(df["player_position"])

        # Age band — C4 fix: do NOT fill NaN with 25; treat unknown age separately
        age = df["age_at_season_start"]
        conditions = [
            age.isna(),
            age <= 21,
            (age > 21) & (age <= 24),
            (age > 24) & (age <= 27),
            (age > 27) & (age <= 30),
            age > 30,
        ]
        choices = ["Unknown", "≤21", "22–24", "25–27", "28–30", "31+"]
        df["age_band"] = np.select(conditions, choices, default="Unknown")

        # Per-90 pass accuracy (0–100 range) — C3 fix
        if "pass_accuracy" in df.columns:
            df["pass_accuracy_pct"] = (df["pass_accuracy"] * 100).round(1)
        else:
            df["pass_accuracy_pct"] = np.nan

        return df
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Percentile computation (computed from enriched stats, no giant file needed)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def compute_percentiles(df: pd.DataFrame, group_cols: list, stat_cols: list) -> pd.DataFrame:
    """
    For each stat in stat_cols, compute within-group percentile rank (0–100).
    Returns df with new columns named <stat>_pct.
    """
    result = df.copy()
    for stat in stat_cols:
        if stat not in df.columns:
            continue
        result[f"{stat}_pct"] = (
            df.groupby(group_cols)[stat]
            .rank(pct=True, na_option="keep")
            .mul(100)
        )
    return result


def get_player_radar_data(
    player_ids: list,
    season: str,
    competition_slug: str,
    stat_keys: list,
    df_all: pd.DataFrame,
    position: str | None = None,
) -> pd.DataFrame:
    """
    For each player, compute percentile rank (rank-based, 0–100) for each
    stat_key within the season × competition × position pool, then return a
    tidy DataFrame for radar plotting.

    Args:
        player_ids: List of player_id values to include.
        season: Season string, e.g. "2024/25".
        competition_slug: Competition slug, e.g. "england-premier-league".
        stat_keys: Ordered list of stat column names.
        df_all: Enriched season stats DataFrame (from load_enriched_season_stats).
        position: Optional position code ("F"/"M"/"D"/"G") to restrict the
            reference pool. If None, the pool covers all positions in the
            selected season × competition.
    """
    pool = df_all[
        (df_all["season"] == season) & (df_all["competition_slug"] == competition_slug)
    ].copy()

    if position is not None and "player_position" in pool.columns:
        pool = pool[pool["player_position"] == position].copy()

    if pool.empty:
        return pd.DataFrame()

    valid_stats = [s for s in stat_keys if s in pool.columns]

    for stat in valid_stats:
        pool[f"{stat}_pct"] = pool[stat].rank(pct=True, na_option="keep") * 100

    rows = []
    for pid in player_ids:
        prow = pool[pool["player_id"] == pid]
        if prow.empty:
            continue
        prow = prow.iloc[0]
        for stat in valid_stats:
            rows.append(
                {
                    "player_id": pid,
                    "player_name": prow["player_name"],
                    "stat": stat,
                    "pct": prow.get(f"{stat}_pct", np.nan),
                    "raw": prow.get(stat, np.nan),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Reliability tier from minutes (P1: uncertainty indicator)
# ---------------------------------------------------------------------------
def reliability_tier_from_minutes(minutes: float) -> str:
    """Return 'Low', 'Medium', or 'High' based on minutes (sample size)."""
    from dashboard.utils.constants import RELIABILITY_MINUTES_LOW, RELIABILITY_MINUTES_MEDIUM
    if pd.isna(minutes) or minutes < RELIABILITY_MINUTES_LOW:
        return "Low"
    if minutes < RELIABILITY_MINUTES_MEDIUM:
        return "Medium"
    return "High"


# ---------------------------------------------------------------------------
# League (and optional position) averages for benchmarking
# ---------------------------------------------------------------------------
def get_league_avg_stats(
    df_all: pd.DataFrame,
    season: str,
    competition_slug: str,
    stat_columns: list[str],
    position: str | None = None,
    min_minutes: int = 0,
) -> pd.Series:
    """Return league (and optionally position) average for given stats. Weights by rows (player-season)."""
    pool = df_all[
        (df_all["season"] == season) & (df_all["competition_slug"] == competition_slug)
    ].copy()
    if min_minutes > 0 and "total_minutes" in pool.columns:
        pool = pool[pool["total_minutes"] >= min_minutes]
    if position and "player_position" in pool.columns:
        pool = pool[pool["player_position"] == position]
    result = {}
    for col in stat_columns:
        if col in pool.columns:
            result[col] = pool[col].mean()
    return pd.Series(result)


# ---------------------------------------------------------------------------
# Helper: single-player match log from slim appearances
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def get_player_match_log(player_id: int, season: str = None) -> pd.DataFrame:
    """Return match log for a player. Cached per player_id + season (M7)."""
    df = load_player_appearances_slim()
    mask = df["player_id"] == player_id
    if season:
        mask &= df["season"] == season
    log = df[mask].copy()
    if "home_team_name" in log.columns and "away_team_name" in log.columns and "side" in log.columns:
        log["opponent"] = log.apply(
            lambda r: r["away_team_name"] if r["side"] == "home" else r["home_team_name"], axis=1
        )
    log = log.sort_values("match_date_utc", ascending=False)
    return log


# ---------------------------------------------------------------------------
# Helper: available competitions & seasons (from extraction_progress)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def get_available_comp_seasons() -> pd.DataFrame:
    """Return competition-season pairs that have at least some extracted data."""
    from dashboard.utils.constants import COMP_NAMES

    ep = load_extraction_progress()
    if ep.empty or "extracted" not in ep.columns:
        return pd.DataFrame(columns=["competition_slug", "season", "league_name", "label"])
    avail = ep[ep["extracted"] > 0].copy()
    avail["league_name"] = avail["competition_slug"].map(COMP_NAMES).fillna(avail["competition_slug"])
    avail["label"] = avail["league_name"] + " " + avail["season"].astype(str)
    avail = avail.sort_values(["competition_slug", "season"])
    return avail


# ---------------------------------------------------------------------------
# Helper: derive W-D-L for a team from match_summary
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def get_team_wdl(team_name: str, season: str, competition_slug: str) -> dict:
    """Return wins, draws, losses for a team in a given season/competition."""
    ms = load_match_summary()
    mask = (
        ((ms["home_team_name"] == team_name) | (ms["away_team_name"] == team_name)) &
        (ms["season"] == season) &
        (ms["competition_slug"] == competition_slug)
    )
    team_matches = ms[mask].copy()

    wins = draws = losses = 0
    for _, row in team_matches.iterrows():
        h, a = row["home_score"], row["away_score"]
        if pd.isna(h) or pd.isna(a):
            continue
        h, a = int(h), int(a)
        if row["home_team_name"] == team_name:
            if h > a:
                wins += 1
            elif h == a:
                draws += 1
            else:
                losses += 1
        else:
            if a > h:
                wins += 1
            elif a == h:
                draws += 1
            else:
                losses += 1
    return {"W": wins, "D": draws, "L": losses, "matches": wins + draws + losses}


@st.cache_data(show_spinner=False, ttl=3600)
def get_team_last_matches(team_name: str, season: str, competition_slug: str, n: int = 5) -> pd.DataFrame:
    """Return last N matches for a team with result from team perspective."""
    ms = load_match_summary()
    mask = (
        ((ms["home_team_name"] == team_name) | (ms["away_team_name"] == team_name)) &
        (ms["season"] == season) &
        (ms["competition_slug"] == competition_slug)
    )
    team_matches = ms[mask].copy().sort_values("match_date_utc", ascending=False)

    rows = []
    for _, row in team_matches.iterrows():
        h, a = row["home_score"], row["away_score"]
        if pd.isna(h) or pd.isna(a):
            continue
        h, a = int(h), int(a)
        is_home = row["home_team_name"] == team_name
        opponent = row["away_team_name"] if is_home else row["home_team_name"]
        gf = h if is_home else a
        ga = a if is_home else h
        xg_for = row.get("home_xg" if is_home else "away_xg")
        xg_against = row.get("away_xg" if is_home else "home_xg")
        possession = row.get("home_possession" if is_home else "away_possession")
        big_chances = row.get("home_big_chances" if is_home else "away_big_chances")
        if gf > ga:
            result = "W"
        elif gf == ga:
            result = "D"
        else:
            result = "L"
        rows.append({
            "date": row.get("match_date_utc"),
            "opponent": opponent,
            "home_away": "H" if is_home else "A",
            "score": f"{gf}–{ga}",
            "result": result,
            "xg_for": xg_for,
            "xg_against": xg_against,
            "possession": possession,
            "big_chances": big_chances,
            "match_id": row.get("match_id"),
        })

    df_out = pd.DataFrame(rows)
    return df_out.head(n) if not df_out.empty else df_out


def get_team_form(
    team_name: str, season: str, competition_slug: str, n: int = 5
) -> dict:
    """Return form string (e.g. 'W D L W W'), points, and W/D/L from last N matches."""
    last = get_team_last_matches(team_name, season, competition_slug, n=n)
    if last.empty or "result" not in last.columns:
        return {"form_string": "", "points": 0, "W": 0, "D": 0, "L": 0}
    w = int((last["result"] == "W").sum())
    d = int((last["result"] == "D").sum())
    l = int((last["result"] == "L").sum())
    form_string = " ".join(last["result"].astype(str).tolist())
    points = 3 * w + d
    return {"form_string": form_string, "points": points, "W": w, "D": d, "L": l}


@st.cache_data(show_spinner=False, ttl=3600)
def get_team_home_away_summary(
    team_name: str, season: str, competition_slug: str
) -> dict:
    """Return home and away W-D-L, goals, and xG for a team in a season/competition.
    Keys: 'home' and 'away', each with W, D, L, matches, goals_for, goals_against, xg_for, xg_against.
    """
    ms = load_match_summary()
    mask = (
        ((ms["home_team_name"] == team_name) | (ms["away_team_name"] == team_name)) &
        (ms["season"] == season) &
        (ms["competition_slug"] == competition_slug)
    )
    team_matches = ms[mask].copy()

    def _empty_side() -> dict:
        return {
            "W": 0, "D": 0, "L": 0, "matches": 0,
            "goals_for": 0, "goals_against": 0,
            "xg_for": 0.0, "xg_against": 0.0,
        }

    if team_matches.empty:
        return {"home": _empty_side(), "away": _empty_side()}

    def _side_stats(subset: pd.DataFrame, is_home: bool) -> dict:
        if subset.empty:
            return _empty_side()
        w = d = l = 0
        goals_for = goals_against = 0
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
        return {
            "W": w, "D": d, "L": l,
            "matches": w + d + l,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "xg_for": xg_for,
            "xg_against": xg_against,
        }

    home_matches = team_matches[team_matches["home_team_name"] == team_name]
    away_matches = team_matches[team_matches["away_team_name"] == team_name]
    return {
        "home": _side_stats(home_matches, is_home=True),
        "away": _side_stats(away_matches, is_home=False),
    }


@st.cache_data(show_spinner=False, ttl=3600)
def get_head_to_head(
    team_a: str,
    team_b: str,
    n: int = 5,
    season: str | None = None,
    competition_slug: str | None = None,
) -> pd.DataFrame:
    """Return last N meetings between team_a and team_b (from team_a's perspective), by recency.
    If season or competition_slug are provided, filter to those; otherwise all seasons/competitions.
    """
    ms = load_match_summary()
    mask = (
        ((ms["home_team_name"] == team_a) & (ms["away_team_name"] == team_b)) |
        ((ms["home_team_name"] == team_b) & (ms["away_team_name"] == team_a))
    )
    if season is not None:
        mask = mask & (ms["season"] == season)
    if competition_slug is not None:
        mask = mask & (ms["competition_slug"] == competition_slug)
    h2h = ms[mask].copy().sort_values("match_date_utc", ascending=False).head(n)
    if h2h.empty:
        return pd.DataFrame()
    rows = []
    for _, row in h2h.iterrows():
        h, a = row["home_score"], row["away_score"]
        if pd.isna(h) or pd.isna(a):
            continue
        h, a = int(h), int(a)
        is_home_a = row["home_team_name"] == team_a
        gf = h if is_home_a else a
        ga = a if is_home_a else h
        result = "W" if gf > ga else "D" if gf == ga else "L"
        rows.append({
            "date": row.get("match_date_utc"),
            "opponent": team_b,
            "home_away": "H" if is_home_a else "A",
            "score": f"{gf}–{ga}",
            "result": result,
            "xg_for": row.get("home_xg" if is_home_a else "away_xg"),
            "xg_against": row.get("away_xg" if is_home_a else "home_xg"),
            "match_id": row.get("match_id"),
        })
    return pd.DataFrame(rows)


def validate_tactics_data(team_stats: pd.DataFrame, tactical_profiles: pd.DataFrame) -> list[str]:
    """Check required columns for tactics; return list of missing column names."""
    required_team = ["team_name", "season", "competition_slug"]
    required_tac = ["team_name", "season", "competition_slug"]
    missing = []
    if not team_stats.empty:
        for c in required_team:
            if c not in team_stats.columns:
                missing.append(f"team_stats.{c}")
    if not tactical_profiles.empty:
        for c in required_tac:
            if c not in tactical_profiles.columns:
                missing.append(f"tactical_profiles.{c}")
    return missing


@st.cache_data(show_spinner=False, ttl=3600)
def get_filtered_teams_tactics(
    season_filter: tuple,
    league_filter: tuple,
    style_filter: str,
    search_team: str,
) -> pd.DataFrame:
    """Return filtered and aggregated team-season list for Tactics Directory. Cached by filter params."""
    from dashboard.utils.scope import filter_to_default_scope
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


def get_tactics_data_refresh_date() -> str | None:
    """Return 'Data as of &lt;date&gt;' from newest of 01/15 parquet mtime, or None if unavailable."""
    import datetime
    paths = [
        _PROJECT_ROOT / "data/processed/01_team_season_stats.parquet",
        _PROJECT_ROOT / "data/processed/15_team_tactical_profiles.parquet",
    ]
    latest = None
    for p in paths:
        if p.exists():
            mtime = p.stat().st_mtime
            if latest is None or mtime > latest:
                latest = mtime
    if latest is None:
        return None
    return datetime.datetime.fromtimestamp(latest, tz=datetime.timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Additional raw loaders
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def load_match_momentum_summary() -> pd.DataFrame:
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/match_momentum_summary.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_match_momentum() -> pd.DataFrame:
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/13_match_momentum.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_substitution_impact() -> pd.DataFrame:
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/12_substitution_impact.parquet")


@st.cache_data(show_spinner=False, ttl=3600)
def load_peak_age_by_position() -> pd.DataFrame:
    return pd.read_parquet(_PROJECT_ROOT / "data/processed/16_peak_age_by_position.parquet")


# ---------------------------------------------------------------------------
# M8 / C5: Similar players (Euclidean distance on per-90 stats)
# ---------------------------------------------------------------------------

_SIMILARITY_STATS = [
    "goals_per90", "expectedGoals_per90", "expectedAssists_per90",
    "keyPass_per90", "totalTackle_per90", "interceptionWon_per90",
    "duelWon_per90", "ballRecovery_per90",
]

@st.cache_data(show_spinner=False, ttl=3600)
def get_similar_players(
    player_id: int,
    season: str,
    competition_slug: str,
    position: str,
    df_all: pd.DataFrame,
    n: int = 5,
    stat_keys: list | None = None,
    cross_league: bool = False,
) -> pd.DataFrame:
    """
    Euclidean distance on normalized per-90 stats within the same
    position × season × (competition or all leagues if cross_league) pool.
    Returns top-n similar players (excluding the reference player),
    with their distance score (lower = more similar).
    """
    if stat_keys is None:
        stat_keys = _SIMILARITY_STATS

    if cross_league:
        from dashboard.utils.constants import TOP_5_LEAGUES
        pool = df_all[
            (df_all["season"] == season) &
            (df_all["competition_slug"].isin(TOP_5_LEAGUES)) &
            (df_all["player_position"] == position)
        ].copy()
    else:
        pool = df_all[
            (df_all["season"] == season) &
            (df_all["competition_slug"] == competition_slug) &
            (df_all["player_position"] == position)
        ].copy()

    valid_stats = [s for s in stat_keys if s in pool.columns]
    if not valid_stats or pool.empty:
        return pd.DataFrame()

    # Normalize each stat to 0-1 range
    for s in valid_stats:
        mn, mx = pool[s].min(), pool[s].max()
        pool[f"_norm_{s}"] = (pool[s] - mn) / (mx - mn + 1e-9)

    ref = pool[pool["player_id"] == player_id]
    if ref.empty:
        return pd.DataFrame()
    ref = ref.iloc[0]

    norm_cols = [f"_norm_{s}" for s in valid_stats]
    ref_vec = ref[norm_cols].fillna(0).values

    others = pool[pool["player_id"] != player_id].copy()
    if others.empty:
        return pd.DataFrame()

    others["_dist"] = others[norm_cols].fillna(0).apply(
        lambda row: float(np.sqrt(np.sum((row.values - ref_vec) ** 2))),
        axis=1,
    )

    top = others.nsmallest(n, "_dist")[
        ["player_id", "player_name", "team", "avg_rating",
         "expectedGoals_per90", "expectedAssists_per90", "_dist"]
    ].copy()
    top = top.rename(columns={"_dist": "similarity_dist"})
    return top.reset_index(drop=True)


# ---------------------------------------------------------------------------
# C5 / T7: Similar teams (Euclidean on tactical indices)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def get_similar_teams(
    team_name: str,
    season: str,
    competition_slug: str,
    n: int = 3,
) -> pd.DataFrame:
    """
    Euclidean distance on normalized tactical indices (0–100) within
    the same season × competition. Returns top-n similar teams.
    """
    from dashboard.utils.constants import TACTICAL_INDEX_LABELS

    df_tac = load_tactical_profiles()
    pool = df_tac[
        (df_tac["season"] == season) &
        (df_tac["competition_slug"] == competition_slug)
    ].copy()

    idx_cols = [c for c in TACTICAL_INDEX_LABELS if c in pool.columns]
    if not idx_cols or pool.empty:
        return pd.DataFrame()

    # Normalize to 0-1 (indices are already 0-100, so divide by 100)
    for c in idx_cols:
        pool[f"_n_{c}"] = pool[c] / 100.0

    ref = pool[pool["team_name"] == team_name]
    if ref.empty:
        return pd.DataFrame()
    ref = ref.iloc[0]

    norm_cols = [f"_n_{c}" for c in idx_cols]
    ref_vec = ref[norm_cols].fillna(0).values

    others = pool[pool["team_name"] != team_name].copy()
    if others.empty:
        return pd.DataFrame()

    others["_dist"] = others[norm_cols].fillna(0).apply(
        lambda row: float(np.sqrt(np.sum((row.values - ref_vec) ** 2))),
        axis=1,
    )
    top = others.nsmallest(n, "_dist")[["team_name", "_dist"] + idx_cols].copy()
    top = top.rename(columns={"_dist": "similarity_dist"})
    return top.reset_index(drop=True)


# ---------------------------------------------------------------------------
# C1: Rule-based narrative auto-summary helpers
# ---------------------------------------------------------------------------

def build_team_narrative(ts: "pd.Series", tactical_row: "pd.Series | None",
                          wdl: dict, league_pool: "pd.DataFrame") -> str:
    """
    Generate a one-paragraph rule-based description of a team's profile.
    Uses tactical indices and key stats. No LLM.
    """
    from dashboard.utils.constants import TACTICAL_INDEX_LABELS, TACTICAL_TAGS

    parts = []
    n = wdl.get("matches", 1) or 1
    wins, draws, losses = wdl.get("W", 0), wdl.get("D", 0), wdl.get("L", 0)
    pts = wins * 3 + draws
    win_rate = wins / n if n > 0 else 0

    form_desc = "strong" if win_rate >= 0.55 else ("solid" if win_rate >= 0.40 else "inconsistent")
    parts.append(f"Season record: {wins}W-{draws}D-{losses}L ({pts} pts, {win_rate:.0%} win rate) — {form_desc} form.")

    # xG narrative
    xg_f = ts.get("xg_for_total", 0) or 0
    xg_a = ts.get("xg_against_total", 0) or 0
    xg_diff = xg_f - xg_a
    if not league_pool.empty and "xg_for_total" in league_pool.columns:
        league_xg = league_pool["xg_for_total"].mean()
        xg_label = "above-average" if xg_f > league_xg * 1.1 else ("below-average" if xg_f < league_xg * 0.9 else "average")
    else:
        xg_label = "average"
    xgf_pg = xg_f / n
    xga_pg = xg_a / n
    parts.append(
        f"Attacking output is {xg_label} (xG for: {xgf_pg:.2f}/game). "
        f"Defensively, they concede {xga_pg:.2f} xG/game (xG diff: {xg_diff:+.1f})."
    )

    # Tactical narrative (if available)
    if tactical_row is not None and not tactical_row.empty:
        tags = []
        for col, (thr, tag) in TACTICAL_TAGS.items():
            v = tactical_row.get(col)
            if pd.notna(v) and v > thr:
                tags.append(tag)
        low_tags = []
        for col, (thr, tag) in TACTICAL_TAGS.items():
            v = tactical_row.get(col)
            if pd.notna(v) and v < (100 - thr):
                low_tags.append(tag.lower())

        if tags:
            parts.append(f"Playing style: {', '.join(tags)}.")
        if low_tags:
            parts.append(f"Relatively weaker in: {', '.join(low_tags)}.")

        ha_cons = tactical_row.get("home_away_consistency")
        if pd.notna(ha_cons):
            ha_label = "consistent home/away" if ha_cons > 60 else "inconsistent home/away"
            parts.append(f"Displays {ha_label} performance (consistency index: {ha_cons:.0f}).")

    return " ".join(parts)


def build_player_narrative(scout_row: "pd.Series", form_row: "pd.Series | None",
                            prow: "pd.Series") -> str:
    """
    One-paragraph rule-based player auto-summary from scouting profile + form.
    """
    parts = []
    pos = prow.get("player_position", "?")
    team = prow.get("team", "?")
    rating = prow.get("avg_rating")
    mins = prow.get("total_minutes", 0)

    rating_desc = "elite" if rating and rating >= 7.5 else ("above average" if rating and rating >= 7.0 else "average")
    parts.append(
        f"{pos} for {team}. Season rating: {rating:.2f} ({rating_desc}). "
        f"Played {int(mins):,} minutes."
        if pd.notna(rating) else f"{pos} for {team}. Played {int(mins):,} minutes."
    )

    # Strengths
    strength_parts = []
    for i in range(1, 4):
        sname = scout_row.get(f"top_pct_stat_{i}_name")
        spct = scout_row.get(f"top_pct_stat_{i}_pct")
        if pd.notna(sname) and pd.notna(spct) and spct >= 70:
            label = sname.replace("_per90", "/90").replace("_", " ").title()
            strength_parts.append(f"{label} ({spct:.0f}th pct)")
    if strength_parts:
        parts.append(f"Key strengths: {', '.join(strength_parts)}.")

    # Form
    if form_row is not None and not form_row.empty:
        fr = form_row.iloc[0] if hasattr(form_row, "iloc") else form_row
        form_rating = fr.get("avg_rating")
        form_goals = fr.get("goals", 0)
        form_xg = fr.get("xg_total", 0)
        if pd.notna(form_rating):
            trend = "in good form" if form_rating >= 7.0 else ("in poor form" if form_rating < 6.5 else "in moderate form")
            parts.append(
                f"Recent form (last 5): {trend} ({form_rating:.2f} avg rating, "
                f"{int(form_goals)} goals, {form_xg:.2f} xG)."
            )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# C6: Form XI — best player per position over last N matches
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def get_form_xi(
    team_name: str,
    season: str,
    competition_slug: str,
    n_matches: int = 5,
    min_minutes: int = 45,
) -> pd.DataFrame:
    """
    Returns best player per position (G/D/M/F) for a team over last N matches,
    ranked by average rating with minimum minutes filter.
    """
    df_app = load_player_appearances_for_teams()
    team_app = df_app[
        (df_app["team"] == team_name) &
        (df_app["season"] == season) &
        (df_app["competition_slug"] == competition_slug)
    ].copy()

    if team_app.empty or "match_date_utc" not in team_app.columns:
        return pd.DataFrame()

    # Get last N unique match dates
    match_dates = sorted(team_app["match_date_utc"].dropna().unique(), reverse=True)
    last_n_dates = match_dates[:n_matches]
    recent = team_app[team_app["match_date_utc"].isin(last_n_dates)]

    pos_col = "position" if "position" in recent.columns else None
    rating_col = "stat_rating" if "stat_rating" in recent.columns else None
    mins_col = "stat_minutesPlayed" if "stat_minutesPlayed" in recent.columns else None

    if not pos_col or not rating_col:
        return pd.DataFrame()

    mask = pd.Series(True, index=recent.index)
    if mins_col:
        mask &= recent[mins_col].fillna(0) >= min_minutes

    filtered = recent[mask]
    if filtered.empty:
        return pd.DataFrame()

    agg = (
        filtered.groupby(["player_id", "player_name", pos_col])
        .agg(
            appearances=("player_id", "count"),
            avg_rating=(rating_col, "mean"),
            total_mins=(mins_col, "sum") if mins_col else ("player_id", "count"),
        )
        .reset_index()
    )

    best_xi = []
    for pos in ["G", "D", "M", "F"]:
        pos_players = agg[agg[pos_col] == pos].sort_values("avg_rating", ascending=False)
        if not pos_players.empty:
            best = pos_players.iloc[0].copy()
            best["position"] = pos
            best_xi.append(best)

    return pd.DataFrame(best_xi) if best_xi else pd.DataFrame()


# ---------------------------------------------------------------------------
# R6: Substitution impact by team
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def get_team_sub_impact(
    team_name: str,
    season: str,
    competition_slug: str,
) -> dict:
    """Return average sub impact metrics for a team."""
    try:
        df_sub = load_substitution_impact()
    except Exception:
        return {}

    # Join sub player_in_id → team via appearances
    df_app = load_player_appearances_for_teams()
    team_player_ids = df_app[
        (df_app["team"] == team_name) &
        (df_app["season"] == season) &
        (df_app["competition_slug"] == competition_slug)
    ]["player_id"].unique()

    sub_cols = df_sub.columns.tolist()
    player_in_col = "player_in_id" if "player_in_id" in sub_cols else None
    if not player_in_col:
        return {}

    team_subs = df_sub[
        (df_sub[player_in_col].isin(team_player_ids)) &
        (df_sub.get("season", pd.Series()).eq(season) if "season" in sub_cols else True)
    ]
    if team_subs.empty:
        return {}

    result = {}
    for col in ["player_in_rating", "player_in_goals", "player_in_xg", "minutes_after_sub"]:
        if col in team_subs.columns:
            result[col] = round(team_subs[col].mean(), 2)
    result["n_subs"] = len(team_subs)
    return result
