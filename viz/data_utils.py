"""
Data loading and transformation utilities for football visualizations.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from viz.config import (
    APPEARANCES_PATH,
    INCIDENTS_PATH,
    PLAYERS_DIR,
)

# Stat columns that can be normalized per 90
STAT_COLS = [
    "stat_goals",
    "stat_expectedGoals",
    "stat_expectedAssists",
    "stat_totalPass",
    "stat_accuratePass",
    "stat_totalLongBalls",
    "stat_accurateLongBalls",
    "stat_totalShots",
    "stat_onTargetScoringAttempt",
    "stat_keyPass",
    "stat_goalAssist",
    "stat_totalTackle",
    "stat_wonTackle",
    "stat_duelWon",
    "stat_duelLost",
    "stat_interceptionWon",
    "stat_totalClearance",
    "stat_ballRecovery",
    "stat_touches",
    "stat_fouls",
    "stat_wasFouled",
    "stat_totalCross",
    "stat_accurateCross",
    "stat_totalBallCarriesDistance",
    "stat_ballCarriesCount",
    "stat_totalProgression",
    "stat_totalProgressiveBallCarriesDistance",
    "stat_progressiveBallCarriesCount",
]

# Value metric columns (Sofascore normalized)
VALUE_COLS = [
    "stat_passValueNormalized",
    "stat_dribbleValueNormalized",
    "stat_defensiveValueNormalized",
    "stat_shotValueNormalized",
]

# Forward-relevant per-90 metrics for radar
FORWARD_RADAR_COLS = [
    "stat_expectedGoals",
    "stat_totalShots",
    "stat_keyPass",
    "stat_totalBallCarriesDistance",
    "stat_totalProgressiveBallCarriesDistance",
    "stat_duelWon",
]


def load_player(slug: str) -> pd.DataFrame:
    """Load player CSV from data/derived/players/{slug}.csv."""
    path = PLAYERS_DIR / f"{slug}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Player file not found: {path}")
    df = pd.read_csv(path)
    if "match_date_utc" in df.columns:
        df["match_date_utc"] = pd.to_datetime(df["match_date_utc"], utc=True)
    return df


def load_player_incidents(slug: str) -> pd.DataFrame:
    """Load player incidents from parquet or {slug}_incidents.csv if present."""
    inc_path = PLAYERS_DIR / f"{slug}_incidents.csv"
    if inc_path.exists():
        df = pd.read_csv(inc_path)
        if "match_date_utc" in df.columns:
            df["match_date_utc"] = pd.to_datetime(df["match_date_utc"], utc=True)
        return df
    if not INCIDENTS_PATH.exists():
        return pd.DataFrame()
    inc = pd.read_parquet(INCIDENTS_PATH)
    # Get player_id from first appearance
    app_path = PLAYERS_DIR / f"{slug}.csv"
    if not app_path.exists():
        return pd.DataFrame()
    app = pd.read_csv(app_path, nrows=1)
    pid = app["player_id"].iloc[0]
    inc = inc[inc["player_id"] == pid].copy()
    if "match_date_utc" in inc.columns:
        inc["match_date_utc"] = pd.to_datetime(inc["match_date_utc"], utc=True)
    return inc


def per_90(df: pd.DataFrame, stat_cols: Optional[list] = None) -> pd.DataFrame:
    """Add per-90 columns for given stat columns. Modifies in place, returns df."""
    cols = stat_cols or STAT_COLS
    mins = df["stat_minutesPlayed"]
    mins = mins.replace(0, pd.NA)
    for c in cols:
        if c in df.columns and df[c].dtype in ("int64", "float64"):
            df[f"{c}_per90"] = df[c] / mins * 90
    return df


def season_aggregates(
    df: pd.DataFrame,
    stat_cols: Optional[list] = None,
    minutes_col: str = "stat_minutesPlayed",
) -> pd.Series:
    """Compute season average per 90 for key stats (weighted by minutes)."""
    cols = stat_cols or STAT_COLS
    mins = df[minutes_col].fillna(0).replace(0, pd.NA)
    totals = df[cols].sum(numeric_only=True)
    total_mins = df[minutes_col].sum()
    if total_mins <= 0:
        return pd.Series(dtype=float)
    agg = {}
    for c in cols:
        if c in totals.index:
            agg[c] = totals[c] / total_mins * 90
    return pd.Series(agg)


def rolling_mean(
    df: pd.DataFrame,
    col: str,
    window: int = 5,
    date_col: str = "match_date_utc",
    per_90: bool = False,
) -> pd.Series:
    """Compute rolling mean of col, ordered by date_col.
    If per_90=True, normalize by minutes (for volume stats)."""
    df = df.sort_values(date_col).reset_index(drop=True)
    vals = df[col].fillna(0)
    if per_90:
        mins = df["stat_minutesPlayed"].fillna(0).replace(0, pd.NA)
        roll_sum = vals.rolling(window, min_periods=1).sum()
        roll_mins = df["stat_minutesPlayed"].rolling(window, min_periods=1).sum()
        roll_mins = roll_mins.replace(0, pd.NA)
        return roll_sum / roll_mins * 90
    return vals.rolling(window, min_periods=1).mean()


def rolling_std(
    df: pd.DataFrame,
    col: str,
    window: int = 5,
    date_col: str = "match_date_utc",
) -> pd.Series:
    """Rolling std of col (for confidence bands). Ordered by date_col."""
    df = df.sort_values(date_col).reset_index(drop=True)
    return df[col].fillna(0).rolling(window, min_periods=2).std()


def cv_band(cv: float) -> str:
    """Return consistency band label from coefficient of variation."""
    if cv < 0.2:
        return "Low"
    if cv < 0.5:
        return "Moderate"
    return "High"


def get_season_competition(df: pd.DataFrame) -> tuple[str, str]:
    """Return (season_label, competition_slug) from player df if cols exist."""
    season = ""
    comp = ""
    if "season_name" in df.columns and df["season_name"].notna().any():
        season = str(df["season_name"].iloc[0])
    if "competition_slug" in df.columns and df["competition_slug"].notna().any():
        comp = str(df["competition_slug"].iloc[0])
    return season, comp


def load_appearances(competition: Optional[str] = None) -> pd.DataFrame:
    """Load full player_appearances.parquet, optionally filtered by competition."""
    if not APPEARANCES_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(APPEARANCES_PATH)
    if "match_date_utc" in df.columns:
        df["match_date_utc"] = pd.to_datetime(df["match_date_utc"], utc=True)
    if competition:
        df = df[df["competition_slug"] == competition]
    return df


def get_match_row(df: pd.DataFrame, match_id: str) -> pd.Series:
    """Get single match row by match_id."""
    df = df[df["match_id"].astype(str) == str(match_id)]
    if df.empty:
        raise ValueError(f"Match {match_id} not found")
    return df.iloc[0]
